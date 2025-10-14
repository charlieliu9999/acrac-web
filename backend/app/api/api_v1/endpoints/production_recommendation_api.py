"""Production-grade recommendation endpoints.

Provides a fast, deterministic recommendation API plus a batch upload
variant that reuses the simplified production recommendation service.
"""
from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services.production_recommendation_service import (
    ProductionRecommendationService,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class ScenarioSummary(BaseModel):
    id: Optional[str] = None
    description: Optional[str] = None
    panel: Optional[str] = None
    topic: Optional[str] = None
    similarity: Optional[float] = Field(None, description="向量相似度")
    risk_level: Optional[str] = None
    patient_population: Optional[str] = None


class RecommendationItem(BaseModel):
    rank: int
    procedure_name: str
    modality: Optional[str] = None
    appropriateness_rating: Optional[float] = Field(
        None, description="ACR appropriateness rating"
    )
    appropriateness_category: Optional[str] = Field(
        None, description="ACR appropriateness category"
    )
    similarity: float = Field(..., description="Vector similarity in [0,1]")
    scenario: ScenarioSummary


class ProductionRecommendationRequest(BaseModel):
    clinical_query: str = Field(..., min_length=3, max_length=600, description="临床描述")
    top_k: Optional[int] = Field(None, ge=1, le=10, description="返回的最大推荐数量")


class ProductionRecommendationResponse(BaseModel):
    query: str
    recommendations: List[RecommendationItem]
    processing_time_ms: int
    top_k: int
    similarity_threshold: float
    max_similarity: Optional[float] = None
    mode: Optional[str] = Field(None, description="推荐模式：hybrid-rag | llm-fallback")
    source: str
    scenarios: List[ScenarioSummary]


class BatchRecommendationResult(ProductionRecommendationResponse):
    index: int


class BatchRecommendationResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: List[BatchRecommendationResult]
    errors: List[Dict[str, Any]]


@router.post(
    "/production/recommendation",
    response_model=ProductionRecommendationResponse,
    summary="生产环境快速推荐",
    description="使用向量检索生成去调试化的推荐结果，优化延迟用于对外服务",
)
async def get_production_recommendation(
    payload: ProductionRecommendationRequest,
    db: Session = Depends(get_db),
) -> ProductionRecommendationResponse:
    service = ProductionRecommendationService(db)
    try:
        result = service.recommend(payload.clinical_query, top_k=payload.top_k)
        return ProductionRecommendationResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover - defensive catch
        logger.exception("production recommendation failed")
        raise HTTPException(status_code=500, detail="生成推荐失败，请稍后重试") from exc


@router.post(
    "/production/recommendation/upload",
    response_model=BatchRecommendationResponse,
    summary="批量上传生成推荐",
    description="基于上传文件批量生成简化推荐结果，支持CSV、Excel与JSON",
)
async def upload_production_recommendations(
    file: UploadFile = File(..., description="包含临床查询的文件"),
    top_k: Optional[int] = Query(None, ge=1, le=10, description="返回的最大推荐数量"),
    db: Session = Depends(get_db),
) -> BatchRecommendationResponse:
    queries = await _extract_queries_from_file(file)
    if not queries:
        raise HTTPException(status_code=400, detail="文件中未找到有效的临床查询")

    service = ProductionRecommendationService(db)
    batch = service.recommend_many(queries, top_k=top_k)

    results: List[BatchRecommendationResult] = []
    for item in batch["results"]:
        results.append(BatchRecommendationResult(**item))

    return BatchRecommendationResponse(
        total=batch["total"],
        succeeded=batch["succeeded"],
        failed=batch["failed"],
        results=results,
        errors=batch["errors"],
    )


async def _extract_queries_from_file(file: UploadFile) -> List[str]:
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix and suffix not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="不支持的文件类型")

    payload = await file.read()
    if len(payload) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="文件过大，超过系统限制")

    try:
        if suffix in {".csv", ""}:  # treat unknown as csv fallback
            # Attempt UTF-8 first, fallback to gbk commonly used in CN datasets
            try:
                text_stream = io.StringIO(payload.decode("utf-8"))
            except UnicodeDecodeError:
                text_stream = io.StringIO(payload.decode("gbk"))
            frame = pd.read_csv(text_stream)
        elif suffix in {".xlsx", ".xls"}:
            frame = pd.read_excel(io.BytesIO(payload))
        elif suffix == ".json":
            data = json.loads(payload.decode("utf-8"))
            if isinstance(data, list):
                frame = pd.json_normalize(data)
            else:
                frame = pd.json_normalize(data.get("records") or data)
        else:
            raise HTTPException(status_code=400, detail="暂不支持的文件类型")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("failed to parse uploaded file")
        raise HTTPException(status_code=400, detail=f"无法解析文件: {exc}") from exc

    return _extract_queries_from_frame(frame)


def _extract_queries_from_frame(frame: pd.DataFrame) -> List[str]:
    if frame.empty:
        return []

    candidates = [
        "query",
        "clinical_query",
        "clinical_description",
        "description",
        "case",
        "patient_case",
    ]
    for column in candidates:
        if column in frame.columns:
            values = [
                str(value).strip()
                for value in frame[column].tolist()
                if isinstance(value, str) or (value is not None and str(value).strip())
            ]
            filtered = [value for value in values if value]
            if filtered:
                # Deduplicate while preserving order
                seen: set = set()
                unique: List[str] = []
                for value in filtered:
                    if value in seen:
                        continue
                    seen.add(value)
                    unique.append(value)
                return unique

    raise HTTPException(
        status_code=400, detail="文件需包含 query/clinical_query/clinical_description 等列"
    )
