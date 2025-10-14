"""
Facade implementation of RAGLLMRecommendationService that delegates to
modular subcomponents under app.services.rag.*
"""
import logging
import os
import threading
import hashlib
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.rules_engine import load_engine
from app.services.query_signals import QuerySignalExtractor

from .embeddings import embed_with_siliconflow
from .db import DBManager
from .prompts import prepare_llm_prompt as _prepare_llm_prompt
from .llm_client import call_llm as _call_llm
from .parser import parse_llm_response as _parse_llm_response
from .contexts import Contexts, extract_scope_info as _extract_scope_info
from .reranker import rerank_scenarios as _rerank_scenarios
from .ragas_eval import (
    build_contexts_from_payload as _build_ragas_contexts_from_payload,
    format_answer_for_ragas as _format_answer_for_ragas,
    compute_ragas_scores as _compute_ragas_scores,
)
from .pipeline import PipelineDeps, generate_recommendation

logger = logging.getLogger(__name__)


class RAGLLMRecommendationService:
    def __init__(self) -> None:
        # DB
        self.db_config = {
            'host': os.getenv('PGHOST', 'localhost'),
            'port': int(os.getenv('PGPORT', 5432)),
            'database': os.getenv('PGDATABASE', 'acrac_db'),
            'user': os.getenv('PGUSER', 'postgres'),
            'password': os.getenv('PGPASSWORD', 'password')
        }
        try:
            self.pgvector_probes = int(os.getenv('PGVECTOR_PROBES', '20'))
        except Exception:
            self.pgvector_probes = 20
        try:
            pool_max = int(os.getenv('DB_POOL_MAX', '10'))
            pool_min = int(os.getenv('DB_POOL_MIN', '1'))
        except Exception:
            pool_max, pool_min = 10, 1
        self.db = DBManager(self.db_config, pool_min=pool_min, pool_max=pool_max, pgvector_probes=self.pgvector_probes)

        # Models
        self.api_key = os.getenv("SILICONFLOW_API_KEY") or getattr(settings, "SILICONFLOW_API_KEY", "")
        self.default_base_url = os.getenv("SILICONFLOW_BASE_URL") or getattr(settings, "SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        # Use backend/config as the config directory. From app/services/rag/*.py, parents[3] points to backend/
        config_dir = Path(__file__).resolve().parents[3] / "config"
        self.contexts = Contexts(config_dir)
        self.llm_model = self.contexts.default_inference_context.get("llm_model") or os.getenv("SILICONFLOW_LLM_MODEL", "Qwen/Qwen2.5-32B-Instruct")
        self.embedding_model = self.contexts.default_inference_context.get("embedding_model") or os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3")
        self.base_url = self.contexts.default_inference_context.get("base_url") or self.default_base_url
        self.reranker_model = self.contexts.default_inference_context.get("reranker_model") or os.getenv("SILICONFLOW_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")

        # Controls
        self.debug_mode = os.getenv("RAG_DEBUG", "false").lower() == "true"
        self.scene_recall_topk = int(os.getenv("RAG_SCENARIO_RECALL_TOPK", "3"))
        self.similarity_threshold = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.55"))
        self.use_reranker = os.getenv("RAG_USE_RERANKER", "true").lower() == "true"
        self.rerank_provider = (os.getenv("RERANK_PROVIDER", "auto") or "auto").lower()
        self.procedure_candidate_topk = int(os.getenv("PROCEDURE_CANDIDATE_TOPK", "8"))
        self.keyword_config_path = os.getenv(
            "RAG_KEYWORD_CONFIG_PATH",
            str(Path(__file__).resolve().parents[3] / "config" / "rag_keywords.json"),
        )
        self.keyword_config = self._load_keyword_config()
        self.panel_boost = float(os.getenv("RAG_PANEL_BOOST", "0.10"))
        self.topic_boost = float(os.getenv("RAG_TOPIC_BOOST", "0.20"))
        self.keyword_boost = float(os.getenv("RAG_KEYWORD_BOOST", "0.05"))
        self.rating_boost = float(os.getenv("RAG_RATING_BOOST", "0.03"))

        self.force_json_output = os.getenv("LLM_FORCE_JSON", "true").lower() == "true"
        try:
            self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "512"))
        except Exception:
            self.max_tokens = 512
        try:
            self.llm_seed = int(os.getenv("LLM_SEED", "0")) if os.getenv("LLM_SEED") else None
        except Exception:
            self.llm_seed = None

        self.top_scenarios = int(os.getenv("RAG_TOP_SCENARIOS", "2"))
        self.top_recommendations_per_scenario = int(os.getenv("RAG_TOP_RECOMMENDATIONS_PER_SCENARIO", "3"))
        self.show_reasoning = os.getenv("RAG_SHOW_REASONING", "true").lower() == "true"

        try:
            self.rules_engine = load_engine()
        except Exception:
            self.rules_engine = None

        try:
            self._signals_extractor = QuerySignalExtractor()
        except Exception as e:
            logger.warning(f"QuerySignalExtractor init failed, fallback to built-in: {e}")
            self._signals_extractor = None

        # Embedding cache
        self._emb_cache_lock = threading.Lock()
        try:
            self._emb_cache_size = int(os.getenv("EMBED_CACHE_SIZE", "256"))
        except Exception:
            self._emb_cache_size = 256
        self._emb_cache: OrderedDict[str, List[float]] = OrderedDict()

    # ---- Context helpers ----
    def _maybe_reload_contexts(self) -> None:
        if self.contexts.maybe_reload():
            prev_base = self.base_url
            self.llm_model = self.contexts.default_inference_context.get("llm_model", self.llm_model)
            self.embedding_model = self.contexts.default_inference_context.get("embedding_model", self.embedding_model)
            self.reranker_model = self.contexts.default_inference_context.get("reranker_model", self.reranker_model)
            self.base_url = self.contexts.default_inference_context.get("base_url", self.base_url)
            if self.base_url.rstrip('/') != (prev_base or '').rstrip('/'):
                logger.info("基础base_url发生变化，后续请求将使用新的推理端点")

    def _resolve_inference_context(self, scope: Dict[str, Optional[str]]) -> Dict[str, Any]:
        base = {
            "llm_model": self.llm_model,
            "embedding_model": self.embedding_model,
            "base_url": self.base_url,
            "reranker_model": self.reranker_model,
            "max_tokens": self.max_tokens,
        }
        return self.contexts.resolve_inference_context(scope, base)

    def _extract_scope_info(self, scenarios: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
        return _extract_scope_info(scenarios)

    # ---- DB ----
    def connect_db(self):
        return self.db.connect()

    def search_clinical_scenarios(self, conn, query_vector: List[float], top_k: int = 3) -> List[Dict]:
        return self.db.search_clinical_scenarios(conn, query_vector, top_k=top_k)

    def get_scenario_with_recommendations(self, conn, scenario_ids: List[str]) -> List[Dict]:
        return self.db.get_scenario_with_recommendations(conn, scenario_ids)

    def search_procedure_candidates(self, conn, query_vector: List[float], top_k: int = 15) -> List[Dict]:
        return self.db.search_procedure_candidates(conn, query_vector, top_k=top_k)

    # ---- Prompt/LLM/Parser ----
    def prepare_llm_prompt(
        self,
        query: str,
        scenarios: List[Dict],
        scenarios_with_recs: List[Dict],
        is_low_similarity: bool = False,
        top_scenarios: Optional[int] = None,
        top_recs_per_scenario: Optional[int] = None,
        show_reasoning: Optional[bool] = None,
        candidates: Optional[List[Dict]] = None,
    ) -> str:
        return _prepare_llm_prompt(
            query,
            scenarios,
            scenarios_with_recs,
            is_low_similarity=is_low_similarity,
            top_scenarios=top_scenarios if top_scenarios is not None else self.top_scenarios,
            top_recs_per_scenario=(
                top_recs_per_scenario
                if top_recs_per_scenario is not None
                else self.top_recommendations_per_scenario
            ),
            show_reasoning=self.show_reasoning if show_reasoning is None else show_reasoning,
            candidates=candidates,
        )

    def call_llm(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        ctx = dict(context or {})
        ctx.setdefault('llm_model', self.llm_model)
        ctx.setdefault('base_url', self.base_url)
        ctx.setdefault('api_key', self.api_key)
        ctx.setdefault('max_tokens', self.max_tokens)
        return _call_llm(prompt, ctx, force_json=self.force_json_output, default_max_tokens=self.max_tokens, seed=self.llm_seed)

    def parse_llm_response(self, llm_response: str) -> Dict[str, Any]:
        return _parse_llm_response(llm_response)

    # ---- RAGAS ----
    def _build_ragas_contexts_from_payload(self, payload: Dict[str, Any]) -> List[str]:
        return _build_ragas_contexts_from_payload(payload)

    def _format_answer_for_ragas(self, parsed: Dict[str, Any]) -> str:
        return _format_answer_for_ragas(parsed)

    def _compute_ragas_scores(self, user_input: str, answer: str, contexts: List[str], reference: str) -> Dict[str, float]:
        eval_ctx = dict(self.contexts.default_evaluation_context or {})
        return _compute_ragas_scores(user_input, answer, contexts, reference, eval_ctx)

    # ---- Signals ----
    def _extract_query_signals(self, query: str) -> Dict[str, Any]:
        try:
            if self._signals_extractor:
                return self._signals_extractor.extract(query)
        except Exception as e:
            logger.warning(f"signals extractor failed, fallback: {e}")
        from .signals_utils import extract_query_signals as _ex
        return _ex(query)

    # ---- Rerank ----
    def _infer_targets_from_query(self, query: str):
        q = (query or "").lower()
        panels = set()
        topics = set()
        cfg = self.keyword_config or {}
        for grp in cfg.get('groups', []):
            kws = [k.lower() for k in grp.get('keywords', [])]
            if any(k in q for k in kws):
                for p in grp.get('panels', []) or []:
                    panels.add(p)
                for t in grp.get('topics', []) or []:
                    topics.add(t)
        return panels, topics

    def _rerank_scenarios(
        self,
        query: str,
        scenarios: List[Dict],
        target_panels: Optional[set] = None,
        target_topics: Optional[set] = None,
        alpha_panel: float = 0.1,
        alpha_topic: float = 0.2,
        alpha_kw: float = 0.05,
        scenarios_with_recs: Optional[List[Dict]] = None,
        reranker_base_url: Optional[str] = None,
        reranker_model: Optional[str] = None,
    ) -> List[Dict]:
        return _rerank_scenarios(
            query,
            scenarios,
            provider=self.rerank_provider,
            base_url=reranker_base_url or self.base_url,
            model_id=reranker_model or self.reranker_model,
            use_reranker=self.use_reranker,
            target_panels=target_panels,
            target_topics=target_topics,
            keyword_config=self.keyword_config,
            alpha_panel=alpha_panel,
            alpha_topic=alpha_topic,
            alpha_kw=alpha_kw,
            scenarios_with_recs=scenarios_with_recs,
        )

    # ---- Embedding cache ----
    def _embed_cached(self, text: str, model: str, base_url: str) -> List[float]:
        key_src = f"{model}|{base_url}|{hashlib.md5((text or '').encode('utf-8')).hexdigest()}"
        with self._emb_cache_lock:
            if key_src in self._emb_cache:
                vec = self._emb_cache.pop(key_src)
                self._emb_cache[key_src] = vec
                return vec
        vec = embed_with_siliconflow(text, api_key=self.api_key, model=model, base_url=base_url)
        with self._emb_cache_lock:
            self._emb_cache[key_src] = vec
            if len(self._emb_cache) > self._emb_cache_size:
                self._emb_cache.popitem(last=False)
        return vec

    # ---- Orchestrate ----
    def generate_intelligent_recommendation(
        self,
        query: str,
        top_scenarios: Optional[int] = None,
        top_recommendations_per_scenario: Optional[int] = None,
        show_reasoning: Optional[bool] = None,
        similarity_threshold: Optional[float] = None,
        debug_flag: Optional[bool] = None,
        compute_ragas: Optional[bool] = None,
        ground_truth: Optional[str] = None,
        ctx_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self._maybe_reload_contexts()
        base_ctx = self._resolve_inference_context({})
        base_url = base_ctx.get('base_url') or self.base_url
        emb_model = base_ctx.get('embedding_model') or self.embedding_model

        deps = PipelineDeps()
        deps.embed_fn = lambda q: self._embed_cached(q, model=emb_model, base_url=base_url)
        deps.db_connect = self.connect_db
        deps.db_search_scenarios = self.search_clinical_scenarios
        deps.db_get_scenario_with_recs = self.get_scenario_with_recommendations
        deps.db_search_procedure_candidates = self.search_procedure_candidates
        deps.call_llm = self.call_llm
        deps.parse_llm = self.parse_llm_response
        deps.extract_query_signals = self._extract_query_signals
        # Allow per-request overrides to be merged into resolved context
        def _resolve(scope: Dict[str, Optional[str]]):
            base = self._resolve_inference_context(scope)
            ov = dict(ctx_overrides or {})
            # Only allow safe fields to override
            for k in ["max_tokens", "temperature", "top_p", "disable_thinking", "no_thinking_tag"]:
                if k in ov and ov[k] is not None:
                    base[k] = ov[k]
            return base
        deps.resolve_inference_context = _resolve
        deps.extract_scope_info = lambda scenarios: self._extract_scope_info(scenarios)
        # rules hooks
        def _rules_apply_rerank(ctx, scenarios):
            try:
                if self.rules_engine and getattr(self.rules_engine, 'enabled', False):
                    return self.rules_engine.apply_rerank(ctx, scenarios)
            except Exception:
                pass
            return {"scenarios": scenarios, "audit_logs": []}
        def _rules_apply_post(ctx, parsed):
            try:
                if self.rules_engine and getattr(self.rules_engine, 'enabled', False):
                    return self.rules_engine.apply_post(ctx, parsed)
            except Exception:
                pass
            return {"parsed": parsed, "audit_logs": []}
        deps.rules_apply_rerank = _rules_apply_rerank
        deps.rules_apply_post = _rules_apply_post
        # recall topk
        try:
            deps.scene_recall_topk = int(self.scene_recall_topk)
        except Exception:
            deps.scene_recall_topk = 3

        deps.debug_mode = (debug_flag is True) or self.debug_mode
        deps.top_scenarios = int(top_scenarios if top_scenarios is not None else self.top_scenarios)
        deps.top_recs_per_scenario = int(top_recommendations_per_scenario if top_recommendations_per_scenario is not None else self.top_recommendations_per_scenario)
        deps.procedure_candidate_topk = int(self.procedure_candidate_topk)
        deps.use_reranker = self.use_reranker
        deps.rerank_provider = self.rerank_provider
        deps.panel_boost = self.panel_boost
        deps.topic_boost = self.topic_boost
        deps.keyword_boost = self.keyword_boost
        deps.rating_boost = self.rating_boost
        deps.similarity_threshold = float(similarity_threshold if similarity_threshold is not None else self.similarity_threshold)
        deps.keyword_config = self.keyword_config
        deps.default_eval_context = dict(self.contexts.default_evaluation_context or {})

        return generate_recommendation(
            query,
            deps=deps,
            show_reasoning=self.show_reasoning if show_reasoning is None else show_reasoning,
            similarity_threshold=similarity_threshold,
            compute_ragas_flag=bool(compute_ragas),
            ground_truth=ground_truth,
        )

    # ---- Utils ----
    def _load_keyword_config(self) -> dict:
        try:
            path = Path(self.keyword_config_path)
            if path.exists():
                import json
                return json.loads(path.read_text(encoding='utf-8'))
        except Exception as e:
            logger.warning(f"加载关键词配置失败: {e}")
        return {
            "groups": [
                {"keywords": ["tia", "短暂性", "弥散", "dwi", "无力", "卒中", "脑缺血"],
                 "panels": ["神经内科", "神经外科", "放射科"],
                 "topics": ["脑卒中", "短暂性脑缺血", "颅脑影像"]},
                {"keywords": ["孕", "妊娠", "孕妇"],
                 "panels": ["胸外科", "心血管内科", "放射科", "妇产科"],
                 "topics": ["疑似肺栓塞", "孕期影像"]},
                {"keywords": ["肺栓塞", "pe", "栓塞", "呼吸困难", "ctpa"],
                 "panels": ["胸外科", "心血管内科", "放射科"],
                 "topics": ["疑似肺栓塞", "胸部影像"]},
                {"keywords": ["头痛", "偏头痛", "颅内", "mri", "ct"],
                 "panels": ["神经内科", "放射科"],
                 "topics": ["头痛", "颅脑影像"]}
            ],
            "keyword_groups_for_bonus": [
                ["tia", "短暂性", "弥散", "dwi", "无力"],
                ["孕", "妊娠", "孕妇"],
                ["肺栓塞", "pe", "栓塞", "呼吸困难", "ctpa", "v/q", "灌注"],
                ["头痛", "颅", "mri", "ct"]
            ]
        }
