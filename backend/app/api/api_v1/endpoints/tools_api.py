from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from app.services.rag_llm_recommendation_service import rag_llm_service, embed_with_siliconflow

router = APIRouter()


class ScenarioItem(BaseModel):
    semantic_id: str
    description_zh: Optional[str] = None
    panel_name: Optional[str] = None
    topic_name: Optional[str] = None
    similarity: Optional[float] = 0.0
    _rerank_score: Optional[float] = None


class RerankRequest(BaseModel):
    query: str = Field(..., description="临床查询")
    scenarios: List[ScenarioItem] = Field(default_factory=list)


class RerankResponse(BaseModel):
    scenarios: List[Dict[str, Any]]


@router.post('/rerank', response_model=RerankResponse, summary='对场景列表进行重排')
async def rerank_scenarios(req: RerankRequest):
    try:
        svc = rag_llm_service
        scenarios = [s.model_dump() for s in req.scenarios]
        # Best-effort infer targets
        try:
            panels, topics = svc._infer_targets_from_query(req.query)
        except Exception:
            panels, topics = set(), set()
        out = svc._rerank_scenarios(
            req.query,
            scenarios,
            target_panels=panels,
            target_topics=topics,
            alpha_panel=svc.panel_boost,
            alpha_topic=svc.topic_boost,
            alpha_kw=svc.keyword_boost,
            scenarios_with_recs=None,
        )
        return RerankResponse(scenarios=out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class LLMParseRequest(BaseModel):
    llm_raw: str = Field(..., description='LLM原始响应文本')


class LLMParseResponse(BaseModel):
    parsed: Dict[str, Any]


@router.post('/llm/parse', response_model=LLMParseResponse, summary='解析LLM原始输出为结构化')
async def llm_parse(req: LLMParseRequest):
    try:
        parsed = rag_llm_service.parse_llm_response(req.llm_raw)
        return LLMParseResponse(parsed=parsed)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RagasRequest(BaseModel):
    user_input: str
    answer: str
    contexts: List[str] = Field(default_factory=list)
    reference: Optional[str] = None


class RagasResponse(BaseModel):
    scores: Dict[str, Any]


@router.post('/ragas/score', response_model=RagasResponse, summary='计算RAGAS指标（需配置，可能耗时）')
async def ragas_score(req: RagasRequest):
    try:
        if not hasattr(rag_llm_service, '_compute_ragas_scores'):
            raise HTTPException(status_code=400, detail='RAGAS未配置')
        scores = rag_llm_service._compute_ragas_scores(
            user_input=req.user_input,
            answer=req.answer,
            contexts=req.contexts,
            reference=req.reference,
        )
        return RagasResponse(scores=scores)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/ragas/schema', summary='RAGAS评测方案（可用指标与输入格式）')
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


class VectorSearchRequest(BaseModel):
    query: str
    top_k: int = 8


class VectorSearchResponse(BaseModel):
    scenarios: List[Dict[str, Any]]


@router.post('/vector/search', response_model=VectorSearchResponse, summary='向量检索场景TopK')
async def vector_search(req: VectorSearchRequest):
    try:
        conn = rag_llm_service.connect_db()
        qv = embed_with_siliconflow(req.query)
        out = rag_llm_service.search_clinical_scenarios(conn, qv, top_k=req.top_k)
        conn.close()
        return VectorSearchResponse(scenarios=out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
