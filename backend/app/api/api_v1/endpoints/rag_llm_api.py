"""
RAG+LLM智能推荐API端点
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import logging
from pathlib import Path
from app.core.config import settings

from app.services.rag_llm_recommendation_service import rag_llm_service

logger = logging.getLogger(__name__)

router = APIRouter()

class IntelligentRecommendationRequest(BaseModel):
    """智能推荐请求模型"""
    clinical_query: str = Field(..., description="临床查询描述", min_length=5, max_length=500)
    include_raw_data: Optional[bool] = Field(False, description="是否包含原始数据")
    debug_mode: Optional[bool] = Field(False, description="是否开启调试模式")

    # 新增可配置参数
    top_scenarios: Optional[int] = Field(None, description="显示的场景数量 (1-10)", ge=1, le=10)
    top_recommendations_per_scenario: Optional[int] = Field(None, description="每个场景的推荐数量 (1-10)", ge=1, le=10)
    show_reasoning: Optional[bool] = Field(None, description="是否显示推荐理由")
    similarity_threshold: Optional[float] = Field(None, description="相似度阈值 (0.1-0.9)", ge=0.1, le=0.9)
    # 调试/评测扩展
    compute_ragas: Optional[bool] = Field(False, description="是否计算RAGAS四项指标（单次请求较慢且有LLM成本）")
    ground_truth: Optional[str] = Field(None, description="用于RAGAS评测的标准答案/参考术语（可选）")

class IntelligentRecommendationResponse(BaseModel):
    """智能推荐响应模型"""
    success: bool
    query: Optional[str] = None
    message: Optional[str] = None
    llm_recommendations: Optional[Dict[str, Any]] = None
    scenarios: Optional[list] = None
    scenarios_with_recommendations: Optional[list] = None
    processing_time_ms: Optional[int] = None
    model_used: Optional[str] = None
    embedding_model_used: Optional[str] = None
    reranker_model_used: Optional[str] = None
    similarity_threshold: Optional[float] = None
    max_similarity: Optional[float] = None
    is_low_similarity_mode: Optional[bool] = None
    llm_raw_response: Optional[str] = None
    debug_info: Optional[Dict[str, Any]] = None
    # 为调试脚本（trace_five_cases.py）提供完整追踪信息
    trace: Optional[Dict[str, Any]] = None


class RulesConfigRequest(BaseModel):
    enabled: bool = Field(..., description="是否启用规则引擎")
    audit_only: bool = Field(True, description="仅审计不执行修订/过滤")

class RulesConfigResponse(BaseModel):
    enabled: bool
    audit_only: bool
    loaded_packs: int

class RulesPacksRequest(BaseModel):
    content: Dict[str, Any] = Field(..., description="完整规则包JSON对象，包含 packs 列表")

class RulesPacksResponse(BaseModel):
    content: Dict[str, Any]

@router.post("/intelligent-recommendation",
             response_model=IntelligentRecommendationResponse,
             summary="RAG+LLM智能推荐",
             description="基于向量语义搜索和大语言模型的智能医疗检查推荐")
async def get_intelligent_recommendation(request: IntelligentRecommendationRequest):
    """
    RAG+LLM智能推荐接口

    工作流程：
    1. 用临床场景表进行语义搜索 (Top 3)
    2. 获取对应的高评分检查推荐 (评分≥7)
    3. 将数据提供给LLM进行综合推理
    4. 返回LLM生成的最终推荐和理由
    """
    try:
        logger.info(f"收到智能推荐请求: {request.clinical_query}")

        # 调用RAG+LLM服务（支持可配置参数）
        result = rag_llm_service.generate_intelligent_recommendation(
            query=request.clinical_query,
            top_scenarios=request.top_scenarios,
            top_recommendations_per_scenario=request.top_recommendations_per_scenario,
            show_reasoning=request.show_reasoning,
            similarity_threshold=request.similarity_threshold,
            # propagate debug flag to service
            debug_flag=request.debug_mode,
            compute_ragas=request.compute_ragas,
            ground_truth=request.ground_truth
        )

        # 根据请求参数决定返回内容
        response_data = {
            "success": result["success"],
            "query": result.get("query"),
            "llm_recommendations": result.get("llm_recommendations"),
            "processing_time_ms": result.get("processing_time_ms"),
            "model_used": result.get("model_used"),
            "embedding_model_used": result.get("embedding_model_used"),
            "reranker_model_used": result.get("reranker_model_used"),
            "similarity_threshold": result.get("similarity_threshold"),
            "max_similarity": result.get("max_similarity"),
            "is_low_similarity_mode": result.get("is_low_similarity_mode")
        }

        if result["success"]:
            if request.include_raw_data:
                response_data.update({
                    "scenarios": result.get("scenarios"),
                    "scenarios_with_recommendations": result.get("scenarios_with_recommendations")
                })

            if request.debug_mode:
                response_data.update({
                    "llm_raw_response": result.get("llm_raw_response"),
                    "debug_info": result.get("debug_info"),
                    # 关键：将服务层生成的trace透传给前端/脚本
                    "trace": result.get("trace")
                })
        else:
            response_data["message"] = result.get("message", "推荐生成失败")

        return IntelligentRecommendationResponse(**response_data)

    except Exception as e:
        logger.error(f"智能推荐API错误: {e}")
        raise HTTPException(status_code=500, detail=f"智能推荐服务异常: {str(e)}")


@router.post("/rules-config", summary="配置规则引擎开关")
async def update_rules_config(req: RulesConfigRequest) -> RulesConfigResponse:
    try:
        eng = getattr(rag_llm_service, 'rules_engine', None)
        if not eng:
            raise HTTPException(status_code=500, detail="规则引擎未初始化")
        eng.enabled = bool(req.enabled)
        eng.audit_only = bool(req.audit_only)
        packs = getattr(eng, 'packs', []) or []
        return RulesConfigResponse(enabled=eng.enabled, audit_only=eng.audit_only, loaded_packs=len(packs))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新规则配置失败: {e}")


@router.get("/rules-config", summary="查看规则引擎状态")
async def get_rules_config() -> RulesConfigResponse:
    eng = getattr(rag_llm_service, 'rules_engine', None)
    if not eng:
        raise HTTPException(status_code=500, detail="规则引擎未初始化")
    packs = getattr(eng, 'packs', []) or []
    return RulesConfigResponse(enabled=eng.enabled, audit_only=eng.audit_only, loaded_packs=len(packs))


@router.get("/rules-packs", summary="获取当前规则包内容")
async def get_rules_packs() -> RulesPacksResponse:
    try:
        eng = getattr(rag_llm_service, 'rules_engine', None)
        if not eng:
            raise HTTPException(status_code=500, detail="规则引擎未初始化")
        cfg_path = Path(settings.RULES_CONFIG_PATH)
        if not cfg_path.exists():
            return RulesPacksResponse(content={"packs": []})
        data = cfg_path.read_text(encoding='utf-8')
        import json
        return RulesPacksResponse(content=json.loads(data))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取规则包失败: {e}")


@router.post("/rules-packs", summary="覆盖并重载规则包（谨慎）")
async def set_rules_packs(req: RulesPacksRequest) -> RulesPacksResponse:
    try:
        eng = getattr(rag_llm_service, 'rules_engine', None)
        if not eng:
            raise HTTPException(status_code=500, detail="规则引擎未初始化")
        cfg_path = Path(settings.RULES_CONFIG_PATH)
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        import json
        # 基础校验
        if not isinstance(req.content, dict) or 'packs' not in req.content:
            raise HTTPException(status_code=400, detail="无效规则包：需包含 packs")
        cfg_path.write_text(json.dumps(req.content, ensure_ascii=False, indent=2), encoding='utf-8')
        # 热重载
        from app.services.rules_engine import RulesEngine
        rag_llm_service.rules_engine = RulesEngine.from_file(cfg_path)
        # 保持原 enabled/audit_only 状态
        rag_llm_service.rules_engine.enabled = eng.enabled
        rag_llm_service.rules_engine.audit_only = eng.audit_only
        return RulesPacksResponse(content=req.content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入/重载规则包失败: {e}")

@router.get("/intelligent-recommendation-simple",
           summary="简单智能推荐接口",
           description="通过URL参数进行快速智能推荐")
async def get_intelligent_recommendation_simple(
    query: str = Query(..., description="临床查询", min_length=5, max_length=500),
    include_raw: bool = Query(False, description="是否包含原始数据"),
    debug: bool = Query(False, description="是否开启调试模式"),
    # 新增可配置参数
    top_scenarios: Optional[int] = Query(None, description="显示的场景数量 (1-10)", ge=1, le=10),
    top_recs: Optional[int] = Query(None, description="每个场景的推荐数量 (1-10)", ge=1, le=10),
    show_reasoning: Optional[bool] = Query(None, description="是否显示推荐理由"),
    threshold: Optional[float] = Query(None, description="相似度阈值 (0.1-0.9)", ge=0.1, le=0.9)
):
    """简化的智能推荐接口，适合快速测试"""
    try:
        request = IntelligentRecommendationRequest(
            clinical_query=query,
            include_raw_data=include_raw,
            debug_mode=debug,
            top_scenarios=top_scenarios,
            top_recommendations_per_scenario=top_recs,
            show_reasoning=show_reasoning,
            similarity_threshold=threshold
        )
        return await get_intelligent_recommendation(request)

    except Exception as e:
        logger.error(f"简单智能推荐API错误: {e}")
        raise HTTPException(status_code=500, detail=f"推荐服务异常: {str(e)}")

@router.get("/rag-llm-status",
           summary="RAG+LLM服务状态检查")
async def check_rag_llm_status():
    """检查RAG+LLM服务状态"""
    try:
        # 尝试连接数据库
        conn = rag_llm_service.connect_db()
        if conn:
            try:
                conn.close()
            except Exception:
                pass

        # LLM 健康
        test_response = rag_llm_service.call_llm("简单测试: 1+1=?")
        llm_available = bool(test_response and len(test_response) > 0)

        # Embedding 健康（尝试请求真实向量）
        from app.services.rag_llm_recommendation_service import embed_with_siliconflow
        try:
            v = embed_with_siliconflow("ping")
            emb_ok = isinstance(v, list) and len(v) >= 128
        except Exception:
            emb_ok = False

        return {
            "status": "healthy",
            "database_connection": "ok",
            "llm_service": "ok" if llm_available else "warning",
            "embedding_service": "ok" if emb_ok else "warning",
            "service_type": "RAG+LLM Intelligent Recommendation"
        }

    except Exception as e:
        logger.error(f"RAG+LLM状态检查失败: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "service_type": "RAG+LLM Intelligent Recommendation"
        }


# —— 运行日志（服务端持久化） ——
from datetime import datetime
from typing import List
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.system_models import InferenceLog

class RunLogCreate(BaseModel):
    query_text: str
    result: Dict[str, Any]
    inference_method: Optional[str] = Field('rag', description='rag | rule_based | case_voting')
    success: Optional[bool] = True
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None

class RunLogItem(BaseModel):
    id: int
    query_text: str
    success: bool
    inference_method: Optional[str] = None
    execution_time_ms: Optional[int] = None
    created_at: Optional[datetime] = None

class RunLogList(BaseModel):
    total: int
    items: List[RunLogItem]

@router.post('/runs/log', summary='保存本次运行结果到服务端', response_model=Dict[str, Any])
async def create_run_log(payload: RunLogCreate):
    db: Session = SessionLocal()
    try:
        exec_seconds = (payload.execution_time_ms or 0) / 1000.0
        row = InferenceLog(
            user_id=None,
            query_text=payload.query_text,
            inference_method=payload.inference_method or 'rag',
            result=payload.result,
            confidence_score=None,
            success=bool(payload.success),
            error_message=payload.error_message,
            execution_time=exec_seconds,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {'ok': True, 'id': row.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f'保存运行日志失败: {e}')
    finally:
        db.close()

@router.get('/runs', summary='运行历史列表', response_model=RunLogList)
async def list_run_logs(page: int = 1, page_size: int = 20):
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    db: Session = SessionLocal()
    try:
        q = db.query(InferenceLog)
        total = q.count()
        rows = q.order_by(InferenceLog.created_at.desc(), InferenceLog.id.desc()).offset((page-1)*page_size).limit(page_size).all()
        items = [RunLogItem(
            id=r.id,
            query_text=r.query_text,
            success=bool(r.success),
            inference_method=r.inference_method,
            execution_time_ms=int((r.execution_time or 0.0) * 1000),
            created_at=r.created_at,
        ) for r in rows]
        return RunLogList(total=total, items=items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'查询运行历史失败: {e}')
    finally:
        db.close()

@router.get('/runs/{log_id}', summary='运行详细', response_model=Dict[str, Any])
async def get_run_log_detail(log_id: int):
    db: Session = SessionLocal()
    try:
        r = db.query(InferenceLog).filter(InferenceLog.id == log_id).first()
        if not r:
            raise HTTPException(status_code=404, detail='未找到运行记录')
        return {
            'id': r.id,
            'query_text': r.query_text,
            'success': bool(r.success),
            'inference_method': r.inference_method,
            'execution_time_ms': int((r.execution_time or 0.0) * 1000),
            'created_at': r.created_at,
            'result': r.result,
            'error_message': r.error_message,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'获取运行详情失败: {e}')
    finally:
        db.close()
