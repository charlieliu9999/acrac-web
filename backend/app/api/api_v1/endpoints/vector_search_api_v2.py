"""
向量检索API端点 V2 - 基于新的数据库结构
提供完整的向量搜索功能，支持所有实体类型
"""
import time
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.services.vector_search_service import VectorSearchService

logger = logging.getLogger(__name__)

router = APIRouter()

# ==================== 请求和响应模型 ====================

class VectorSearchRequest(BaseModel):
    """向量搜索请求"""
    query_text: str = Field(..., description="搜索查询文本", min_length=1, max_length=1000)
    top_k: int = Field(10, description="返回结果数量", ge=1, le=50)
    similarity_threshold: float = Field(0.0, description="相似度阈值", ge=0.0, le=1.0)

class PanelSearchResult(BaseModel):
    """科室搜索结果"""
    id: int
    semantic_id: str
    name_zh: str
    name_en: str
    description: Optional[str] = None
    similarity_score: float

class TopicSearchResult(BaseModel):
    """主题搜索结果"""
    id: int
    semantic_id: str
    name_zh: str
    name_en: str
    description: Optional[str] = None
    panel_name: Optional[str] = None
    similarity_score: float

class ScenarioSearchResult(BaseModel):
    """临床场景搜索结果"""
    id: int
    semantic_id: str
    description_zh: str
    description_en: str
    patient_population: Optional[str] = None
    risk_level: Optional[str] = None
    age_group: Optional[str] = None
    gender: Optional[str] = None
    urgency_level: Optional[str] = None
    symptom_category: Optional[str] = None
    panel_name: Optional[str] = None
    topic_name: Optional[str] = None
    similarity_score: float

class ProcedureSearchResult(BaseModel):
    """检查项目搜索结果"""
    id: int
    semantic_id: str
    name_zh: str
    name_en: str
    modality: Optional[str] = None
    body_part: Optional[str] = None
    contrast_used: Optional[bool] = None
    radiation_level: Optional[str] = None
    exam_duration: Optional[int] = None
    preparation_required: Optional[bool] = None
    description_zh: Optional[str] = None
    similarity_score: float

class RecommendationSearchResult(BaseModel):
    """临床推荐搜索结果"""
    id: int
    semantic_id: str
    appropriateness_rating: Optional[int] = None
    appropriateness_category_zh: Optional[str] = None
    reasoning_zh: Optional[str] = None
    evidence_level: Optional[str] = None
    pregnancy_safety: Optional[str] = None
    adult_radiation_dose: Optional[str] = None
    pediatric_radiation_dose: Optional[str] = None
    scenario_description: Optional[str] = None
    patient_population: Optional[str] = None
    risk_level: Optional[str] = None
    procedure_name: Optional[str] = None
    modality: Optional[str] = None
    body_part: Optional[str] = None
    panel_name: Optional[str] = None
    topic_name: Optional[str] = None
    similarity_score: float

class ComprehensiveSearchResponse(BaseModel):
    """综合搜索响应"""
    query_text: str
    search_time_ms: int
    panels: List[PanelSearchResult]
    topics: List[TopicSearchResult]
    scenarios: List[ScenarioSearchResult]
    procedures: List[ProcedureSearchResult]
    recommendations: List[RecommendationSearchResult]
    total_results: int

class DatabaseStatsResponse(BaseModel):
    """数据库统计响应"""
    panels_count: int
    panels_vector_coverage: float
    topics_count: int
    topics_vector_coverage: float
    clinical_scenarios_count: int
    clinical_scenarios_vector_coverage: float
    procedure_dictionary_count: int
    procedure_dictionary_vector_coverage: float
    clinical_recommendations_count: int
    clinical_recommendations_vector_coverage: float

# ==================== API端点 ====================

def get_vector_search_service(db: Session = Depends(get_db)) -> VectorSearchService:
    """获取向量搜索服务"""
    return VectorSearchService(db)

@router.post("/search/comprehensive", response_model=ComprehensiveSearchResponse)
async def comprehensive_search(
    request: VectorSearchRequest,
    service: VectorSearchService = Depends(get_vector_search_service)
):
    """
    综合向量搜索
    
    搜索所有实体类型：科室、主题、临床场景、检查项目、临床推荐
    """
    start_time = time.time()
    
    try:
        # 搜索所有实体类型
        panels = service.search_panels(
            query_text=request.query_text,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold
        )
        
        topics = service.search_topics(
            query_text=request.query_text,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold
        )
        
        scenarios = service.search_scenarios(
            query_text=request.query_text,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold
        )
        
        procedures = service.search_procedures(
            query_text=request.query_text,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold
        )
        
        recommendations = service.search_recommendations(
            query_text=request.query_text,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold
        )
        
        search_time_ms = int((time.time() - start_time) * 1000)
        total_results = len(panels) + len(topics) + len(scenarios) + len(procedures) + len(recommendations)
        
        return ComprehensiveSearchResponse(
            query_text=request.query_text,
            search_time_ms=search_time_ms,
            panels=[PanelSearchResult(**panel) for panel in panels],
            topics=[TopicSearchResult(**topic) for topic in topics],
            scenarios=[ScenarioSearchResult(**scenario) for scenario in scenarios],
            procedures=[ProcedureSearchResult(**procedure) for procedure in procedures],
            recommendations=[RecommendationSearchResult(**rec) for rec in recommendations],
            total_results=total_results
        )
        
    except Exception as e:
        logger.error(f"综合搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"综合搜索失败: {str(e)}")

@router.post("/search/panels", response_model=List[PanelSearchResult])
async def search_panels(
    request: VectorSearchRequest,
    service: VectorSearchService = Depends(get_vector_search_service)
):
    """搜索科室"""
    try:
        panels = service.search_panels(
            query_text=request.query_text,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold
        )
        return [PanelSearchResult(**panel) for panel in panels]
        
    except Exception as e:
        logger.error(f"搜索科室失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索科室失败: {str(e)}")

@router.post("/search/topics", response_model=List[TopicSearchResult])
async def search_topics(
    request: VectorSearchRequest,
    service: VectorSearchService = Depends(get_vector_search_service)
):
    """搜索主题"""
    try:
        topics = service.search_topics(
            query_text=request.query_text,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold
        )
        return [TopicSearchResult(**topic) for topic in topics]
        
    except Exception as e:
        logger.error(f"搜索主题失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索主题失败: {str(e)}")

@router.post("/search/scenarios", response_model=List[ScenarioSearchResult])
async def search_scenarios(
    request: VectorSearchRequest,
    service: VectorSearchService = Depends(get_vector_search_service)
):
    """搜索临床场景"""
    try:
        scenarios = service.search_scenarios(
            query_text=request.query_text,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold
        )
        return [ScenarioSearchResult(**scenario) for scenario in scenarios]
        
    except Exception as e:
        logger.error(f"搜索临床场景失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索临床场景失败: {str(e)}")

@router.post("/search/procedures", response_model=List[ProcedureSearchResult])
async def search_procedures(
    request: VectorSearchRequest,
    service: VectorSearchService = Depends(get_vector_search_service)
):
    """搜索检查项目"""
    try:
        procedures = service.search_procedures(
            query_text=request.query_text,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold
        )
        return [ProcedureSearchResult(**procedure) for procedure in procedures]
        
    except Exception as e:
        logger.error(f"搜索检查项目失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索检查项目失败: {str(e)}")

@router.post("/search/recommendations", response_model=List[RecommendationSearchResult])
async def search_recommendations(
    request: VectorSearchRequest,
    service: VectorSearchService = Depends(get_vector_search_service)
):
    """搜索临床推荐"""
    try:
        recommendations = service.search_recommendations(
            query_text=request.query_text,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold
        )
        return [RecommendationSearchResult(**rec) for rec in recommendations]
        
    except Exception as e:
        logger.error(f"搜索临床推荐失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索临床推荐失败: {str(e)}")

@router.get("/stats", response_model=DatabaseStatsResponse)
async def get_database_stats(
    service: VectorSearchService = Depends(get_vector_search_service)
):
    """获取数据库统计信息"""
    try:
        stats = service.get_database_stats()
        return DatabaseStatsResponse(**stats)
        
    except Exception as e:
        logger.error(f"获取数据库统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取数据库统计失败: {str(e)}")

@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "vector_search_v2",
        "message": "向量搜索服务V2运行正常",
        "timestamp": time.time()
    }
