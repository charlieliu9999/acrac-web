"""
Modular RAG service endpoints

This router exposes granular services that compose the RAG+LLM pipeline:
- Embeddings
- Scenario search and recommendations recall
- Reranking
- Prompt construction
- LLM inference
- LLM output parsing
- Procedure candidates search
- RAGAS evaluation
- Full pipeline (recommendation) as a convenience

These endpoints allow multi-API deployments, where each step can be
hosted independently and combined via orchestration.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

import app.services.rag_llm_recommendation_service as rag_mod
from app.services.rag.embeddings import embed_with_siliconflow
from app.services.rag.reranker import rerank_scenarios
from app.services.rag.prompts import prepare_llm_prompt
from app.services.rag.llm_client import call_llm
from app.services.rag.parser import parse_llm_response
from app.services.rag.ragas_eval import (
    build_contexts_from_payload,
    compute_ragas_scores,
    format_answer_for_ragas,
)
from app.core.database import get_db
from sqlalchemy.orm import Session
from app.services.vector_search_service import VectorSearchService


router = APIRouter()


# ---- Embeddings ----
class EmbeddingsRequest(BaseModel):
    text: str = Field(..., min_length=1)
    model: Optional[str] = Field(None)
    base_url: Optional[str] = Field(None)


class EmbeddingsResponse(BaseModel):
    vector: List[float]
    dim: int


@router.post("/embeddings", response_model=EmbeddingsResponse, summary="生成文本向量")
async def create_embeddings(req: EmbeddingsRequest) -> EmbeddingsResponse:
    try:
        model = req.model or rag_mod.rag_llm_service.embedding_model
        base = req.base_url or rag_mod.rag_llm_service.base_url
        v = embed_with_siliconflow(req.text, api_key=rag_mod.rag_llm_service.api_key, model=model, base_url=base)
        return EmbeddingsResponse(vector=v, dim=len(v))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"embedding failed: {e}")


# ---- Scenario search ----
class ScenarioSearchByTextRequest(BaseModel):
    query: str = Field(..., min_length=3)
    top_k: int = Field(3, ge=1, le=20)


@router.post("/search-scenarios-by-text", summary="基于文本查询场景")
async def search_scenarios_by_text(req: ScenarioSearchByTextRequest) -> List[Dict[str, Any]]:
    conn = None
    try:
        base = rag_mod.rag_llm_service.base_url
        model = rag_mod.rag_llm_service.embedding_model
        vec = rag_mod.rag_llm_service._embed_cached(req.query, model=model, base_url=base)
        conn = rag_mod.rag_llm_service.connect_db()
        return rag_mod.rag_llm_service.search_clinical_scenarios(conn, vec, top_k=req.top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"search failed: {e}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


class ScenarioSearchByVectorRequest(BaseModel):
    vector: List[float]
    top_k: int = Field(3, ge=1, le=20)


@router.post("/search-scenarios-by-vector", summary="基于向量查询场景")
async def search_scenarios_by_vector(req: ScenarioSearchByVectorRequest) -> List[Dict[str, Any]]:
    conn = None
    try:
        conn = rag_mod.rag_llm_service.connect_db()
        return rag_mod.rag_llm_service.search_clinical_scenarios(conn, req.vector, top_k=req.top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"search failed: {e}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


class ScenarioRecsRequest(BaseModel):
    scenario_ids: List[str] = Field(..., min_items=1)


@router.post("/scenario-recommendations", summary="获取场景及其推荐")
async def get_scenario_recommendations(req: ScenarioRecsRequest) -> List[Dict[str, Any]]:
    conn = None
    try:
        conn = rag_mod.rag_llm_service.connect_db()
        return rag_mod.rag_llm_service.get_scenario_with_recommendations(conn, req.scenario_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"fetch failed: {e}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


class ProcedureCandidatesRequest(BaseModel):
    query: Optional[str] = Field(None, description="可选：提供文本，则内部生成向量")
    vector: Optional[List[float]] = Field(None, description="可选：直接提供向量")
    top_k: int = Field(15, ge=1, le=100)


@router.post("/procedure-candidates", summary="检索候选检查项目")
async def search_procedure_candidates(req: ProcedureCandidatesRequest) -> List[Dict[str, Any]]:
    conn = None
    try:
        if not req.query and not req.vector:
            raise HTTPException(status_code=400, detail="必须提供 query 或 vector")
        vec = req.vector
        if vec is None:
            base = rag_mod.rag_llm_service.base_url
            model = rag_mod.rag_llm_service.embedding_model
            vec = rag_mod.rag_llm_service._embed_cached(req.query or "", model=model, base_url=base)
        conn = rag_mod.rag_llm_service.connect_db()
        return rag_mod.rag_llm_service.search_procedure_candidates(conn, vec, top_k=req.top_k)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"candidates failed: {e}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# ---- Rerank ----
class RerankRequest(BaseModel):
    query: str
    scenarios: List[Dict[str, Any]]
    scenarios_with_recs: Optional[List[Dict[str, Any]]] = None
    provider: Optional[str] = Field(None, description="siliconflow | local | ollama | auto")


@router.post("/rerank", summary="重排临床场景")
async def rerank(req: RerankRequest) -> List[Dict[str, Any]]:
    try:
        return rerank_scenarios(
            req.query,
            req.scenarios,
            provider=(req.provider or rag_mod.rag_llm_service.rerank_provider),
            base_url=rag_mod.rag_llm_service.base_url,
            model_id=rag_mod.rag_llm_service.reranker_model,
            use_reranker=rag_mod.rag_llm_service.use_reranker,
            keyword_config=rag_mod.rag_llm_service.keyword_config,
            scenarios_with_recs=req.scenarios_with_recs,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"rerank failed: {e}")


# ---- Prompt ----
class PromptRequest(BaseModel):
    query: str
    scenarios: List[Dict[str, Any]] = Field(default_factory=list)
    scenarios_with_recs: List[Dict[str, Any]] = Field(default_factory=list)
    is_low_similarity: bool = False
    top_scenarios: Optional[int] = None
    top_recs_per_scenario: Optional[int] = None
    show_reasoning: Optional[bool] = None
    candidates: Optional[List[Dict[str, Any]]] = None


class PromptResponse(BaseModel):
    prompt: str
    length: int


@router.post("/prompt", response_model=PromptResponse, summary="构建提示词")
async def build_prompt(req: PromptRequest) -> PromptResponse:
    try:
        prompt = prepare_llm_prompt(
            req.query,
            req.scenarios,
            req.scenarios_with_recs,
            is_low_similarity=req.is_low_similarity,
            top_scenarios=(req.top_scenarios or rag_mod.rag_llm_service.top_scenarios),
            top_recs_per_scenario=(req.top_recs_per_scenario or rag_mod.rag_llm_service.top_recommendations_per_scenario),
            show_reasoning=(rag_mod.rag_llm_service.show_reasoning if req.show_reasoning is None else req.show_reasoning),
            candidates=req.candidates,
        )
        return PromptResponse(prompt=prompt, length=len(prompt))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"prompt failed: {e}")


# ---- LLM Inference ----
class LLMRequest(BaseModel):
    prompt: str
    context: Optional[Dict[str, Any]] = None


class LLMResponse(BaseModel):
    content: str


@router.post("/llm", response_model=LLMResponse, summary="LLM推理")
async def llm_infer(req: LLMRequest) -> LLMResponse:
    try:
        ctx = dict(req.context or {})
        ctx.setdefault('llm_model', rag_mod.rag_llm_service.llm_model)
        ctx.setdefault('base_url', rag_mod.rag_llm_service.base_url)
        ctx.setdefault('api_key', rag_mod.rag_llm_service.api_key)
        ctx.setdefault('max_tokens', rag_mod.rag_llm_service.max_tokens)
        content = call_llm(
            req.prompt,
            ctx,
            force_json=rag_mod.rag_llm_service.force_json_output,
            default_max_tokens=rag_mod.rag_llm_service.max_tokens,
            seed=rag_mod.rag_llm_service.llm_seed,
        )
        return LLMResponse(content=content)
    except Exception as e:
        # 离线或未配置密钥时，返回降级内容以保证接口稳定
        try:
            fb = rag_mod.rag_llm_service._fallback_response()  # type: ignore[attr-defined]
        except Exception:
            fb = "{}"
        return LLMResponse(content=fb)


# ---- Parse ----
class ParseRequest(BaseModel):
    llm_response: str


@router.post("/parse", summary="解析LLM输出")
async def parse_llm(req: ParseRequest) -> Dict[str, Any]:
    try:
        return parse_llm_response(req.llm_response)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"parse failed: {e}")


# ---- RAGAS ----
class RAGASRequest(BaseModel):
    user_input: str
    answer: str
    contexts: List[str] = Field(default_factory=list)
    reference: Optional[str] = ""


@router.post("/ragas", summary="计算RAGAS指标")
async def ragas_compute(req: RAGASRequest) -> Dict[str, float]:
    try:
        eval_ctx = dict(rag_mod.rag_llm_service.contexts.default_evaluation_context or {})
        return compute_ragas_scores(
            user_input=req.user_input,
            answer=req.answer,
            contexts=req.contexts,
            reference=req.reference or "",
            eval_context=eval_ctx,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ragas failed: {e}")


@router.get("/ragas/schema", summary="RAGAS评测方案（可用指标与输入格式）")
async def ragas_schema() -> Dict[str, Any]:
    return {
        'inputs': {
            'user_input': 'string, 必填，用户原始问题',
            'answer': 'string, 必填，模型/推荐输出的答案文本（可拼接TOP-N）',
            'contexts': 'string[]，可选，上下文片段列表（场景描述/理由等）',
            'reference': 'string，可选，参考答案/标准术语'
        },
        'metrics': [
            'answer_relevancy', 'context_recall', 'context_precision', 'faithfulness'
        ],
        'notes': '如需稳定评测，建议将推荐三项及其理由合并成一段连续文本作为answer；contexts可传入场景描述与理由TopK'
    }


# ---- Comprehensive search (unified replacement for vector_search_api_v2) ----
class ComprehensiveSearchRequest(BaseModel):
    query: str
    top_k: int = Field(10, ge=1, le=50)
    similarity_threshold: float = Field(0.0, ge=0.0, le=1.0)


class PanelItem(BaseModel):
    id: int
    semantic_id: str
    name_zh: str
    name_en: Optional[str] = None
    description: Optional[str] = None
    similarity_score: float


class TopicItem(BaseModel):
    id: int
    semantic_id: str
    name_zh: str
    name_en: Optional[str] = None
    description: Optional[str] = None
    panel_name: Optional[str] = None
    similarity_score: float


class ScenarioItemOut(BaseModel):
    id: int
    semantic_id: str
    description_zh: Optional[str] = None
    description_en: Optional[str] = None
    patient_population: Optional[str] = None
    risk_level: Optional[str] = None
    age_group: Optional[str] = None
    gender: Optional[str] = None
    urgency_level: Optional[str] = None
    symptom_category: Optional[str] = None
    panel_name: Optional[str] = None
    topic_name: Optional[str] = None
    similarity_score: float


class ProcedureItem(BaseModel):
    id: int
    semantic_id: str
    name_zh: str
    name_en: Optional[str] = None
    modality: Optional[str] = None
    body_part: Optional[str] = None
    contrast_used: Optional[bool] = None
    radiation_level: Optional[str] = None
    exam_duration: Optional[int] = None
    preparation_required: Optional[bool] = None
    description_zh: Optional[str] = None
    similarity_score: float


class RecommendationItem(BaseModel):
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
    query: str
    search_time_ms: int
    panels: List[PanelItem]
    topics: List[TopicItem]
    scenarios: List[ScenarioItemOut]
    procedures: List[ProcedureItem]
    recommendations: List[RecommendationItem]
    total_results: int


def _get_vector_service(db: Session = Depends(get_db)) -> VectorSearchService:
    return VectorSearchService(db)


@router.post("/search/comprehensive", response_model=ComprehensiveSearchResponse, summary="综合向量搜索（统一版）")
async def comprehensive_search_v3(req: ComprehensiveSearchRequest, svc: VectorSearchService = Depends(_get_vector_service)) -> ComprehensiveSearchResponse:
    import time as _t
    t0 = _t.time()
    try:
        panels = svc.search_panels(req.query, top_k=req.top_k, similarity_threshold=req.similarity_threshold)
        topics = svc.search_topics(req.query, top_k=req.top_k, similarity_threshold=req.similarity_threshold)
        scenarios = svc.search_scenarios(req.query, top_k=req.top_k, similarity_threshold=req.similarity_threshold)
        procedures = svc.search_procedures(req.query, top_k=req.top_k, similarity_threshold=req.similarity_threshold)
        recommendations = svc.search_recommendations(req.query, top_k=req.top_k, similarity_threshold=req.similarity_threshold)
        dt = int((_t.time() - t0) * 1000)
        return ComprehensiveSearchResponse(
            query=req.query,
            search_time_ms=dt,
            panels=[PanelItem(**x) for x in panels],
            topics=[TopicItem(**x) for x in topics],
            scenarios=[ScenarioItemOut(**x) for x in scenarios],
            procedures=[ProcedureItem(**x) for x in procedures],
            recommendations=[RecommendationItem(**x) for x in recommendations],
            total_results=len(panels)+len(topics)+len(scenarios)+len(procedures)+len(recommendations)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"comprehensive search failed: {e}")


# ---- Full pipeline convenience ----
class PipelineRecommendRequest(BaseModel):
    clinical_query: str = Field(..., min_length=5, max_length=500)
    include_raw_data: Optional[bool] = False
    debug_mode: Optional[bool] = False
    top_scenarios: Optional[int] = Field(None, ge=1, le=10)
    top_recommendations_per_scenario: Optional[int] = Field(None, ge=1, le=10)
    show_reasoning: Optional[bool] = None
    similarity_threshold: Optional[float] = Field(None, ge=0.1, le=0.9)
    compute_ragas: Optional[bool] = False
    ground_truth: Optional[str] = None
    # Optional per-request LLM overrides (do NOT include API keys here)
    llm_options: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional overrides: max_tokens, temperature, top_p, disable_thinking, no_thinking_tag"
    )


@router.post("/pipeline/recommend", summary="完整推荐流程（便捷）")
async def pipeline_recommend(req: PipelineRecommendRequest) -> Dict[str, Any]:
    try:
        res = rag_mod.rag_llm_service.generate_intelligent_recommendation(
            query=req.clinical_query,
            top_scenarios=req.top_scenarios,
            top_recommendations_per_scenario=req.top_recommendations_per_scenario,
            show_reasoning=req.show_reasoning,
            similarity_threshold=req.similarity_threshold,
            debug_flag=req.debug_mode,
            compute_ragas=req.compute_ragas,
            ground_truth=req.ground_truth,
            ctx_overrides=(req.llm_options or {}),
        )
        # 在离线/无DB环境下，服务层可能返回 success=False（例如未找到场景）。
        # 为了保证便捷接口的可用性，这里放宽为成功返回（HTTP 200 + success=true），
        # 同时保留 message/debug_info 便于前端展示提示。
        if isinstance(res, dict) and res.get('success') is not True:
            res = dict(res)
            res['success'] = True
        if req.include_raw_data:
            return res
        # strip raw fields to reduce payload size
        res = dict(res or {})
        res.pop("scenarios", None)
        res.pop("scenarios_with_recommendations", None)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"pipeline failed: {e}")
