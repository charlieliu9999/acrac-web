"""
RAG+LLM智能推荐服务
结合向量语义搜索和大语言模型的医疗检查推荐系统
"""

import json
import re
import logging
import time
import os
import requests
import numpy as np
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
import openai
from app.core.config import settings
from app.services.rules_engine import load_engine
from app.services.query_signals import QuerySignalExtractor
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError, Field
from typing import Union
from pathlib import Path
import threading
import hashlib
from collections import OrderedDict

# 加载环境变量：默认读取 backend/.env；若在容器环境可通过 SKIP_LOCAL_DOTENV/DOCKER_CONTEXT 禁用
try:
    if os.getenv('SKIP_LOCAL_DOTENV', '').lower() == 'true' or os.getenv('DOCKER_CONTEXT', '').lower() == 'true':
        pass
    else:
        env_path = Path(__file__).resolve().parents[2] / ".env"
        if env_path.exists():
            load_dotenv(str(env_path))
        else:
            load_dotenv()
except Exception:
    pass

logger = logging.getLogger(__name__)
# 严格嵌入模式：默认开启。为兼容本地调试，可通过 STRICT_EMBEDDING=false 放宽为随机向量兜底（仅调试）。
STRICT_EMBEDDING = (os.getenv("STRICT_EMBEDDING", "true").lower() in ("1", "true", "yes"))


def embed_with_siliconflow(
    text: str,
    api_key: Optional[str] = None,
    model: str = "BAAI/bge-m3",
    timeout: int = 60,
    base_url: Optional[str] = None,
) -> List[float]:
    """生成文本嵌入（OpenAI 兼容协议）。
    支持：SiliconFlow、OpenAI、OpenRouter、Ollama（/v1/embeddings）。
    - 当 base_url 指向 Ollama（含 11434 或 'ollama'）时，不需要 API key。
    - 其余情况优先使用提供的 api_key 或环境变量（OPENAI_API_KEY / SILICONFLOW_API_KEY / OPENROUTER_API_KEY）。
    默认严格模式：请求失败将抛错并在源头暴露配置问题；仅当 STRICT_EMBEDDING=false 时才在本地调试返回随机向量。
    """
    try:
        endpoint = (base_url
                    or os.getenv("OPENAI_BASE_URL")
                    or os.getenv("SILICONFLOW_BASE_URL")
                    or os.getenv("OLLAMA_BASE_URL")
                    or "https://api.siliconflow.cn/v1").rstrip("/")
        prefers_ollama = ("11434" in endpoint) or ("ollama" in endpoint.lower())
        # 选择 API Key（Ollama 不需要）
        key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("SILICONFLOW_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        headers = {"Content-Type": "application/json"}
        if not prefers_ollama and key:
            headers["Authorization"] = f"Bearer {key}"
        payload = {"model": model, "input": text}
        resp = requests.post(f"{endpoint}/embeddings", json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        emb = (data.get("data") or [{}])[0].get("embedding")
        if not isinstance(emb, list):
            raise ValueError("invalid embeddings response")
        return emb
    except Exception as e:
        endpoint_hint = (base_url or os.getenv("OPENAI_BASE_URL") or os.getenv("SILICONFLOW_BASE_URL") or os.getenv("OLLAMA_BASE_URL") or "unknown").rstrip("/")
        logger.error(f"Embedding request failed ({endpoint_hint}): {e}")
        if STRICT_EMBEDDING:
            # 严格模式：在源头暴露错误，便于快速定位（不再悄悄兜底）
            raise
        logger.warning("STRICT_EMBEDDING=false → using random vector for debug only")
        return np.random.rand(1024).tolist()

class RAGLLMRecommendationService:
    """增强RAG+LLM医疗检查推荐服务"""

    def __init__(self):
        self.db_config = {
            'host': os.getenv('PGHOST', 'localhost'),
            'port': int(os.getenv('PGPORT', 5432)),
            'database': os.getenv('PGDATABASE', 'acrac_db'),
            'user': os.getenv('PGUSER', 'postgres'),
            'password': os.getenv('PGPASSWORD', 'password')
        }
        # pgvector recall quality: number of inverted lists to probe
        # Higher probes improves recall at the cost of latency. Default 20.
        try:
            self.pgvector_probes = int(os.getenv('PGVECTOR_PROBES', '20'))
        except Exception:
            self.pgvector_probes = 20
        # DB连接池（按需初始化）
        self._db_pool: Optional[ThreadedConnectionPool] = None
        try:
            self._db_pool_max = int(os.getenv('DB_POOL_MAX', '10'))
            self._db_pool_min = int(os.getenv('DB_POOL_MIN', '1'))
        except Exception:
            self._db_pool_max, self._db_pool_min = 10, 1

        # 基础模型连接配置
        self.api_key = os.getenv("SILICONFLOW_API_KEY") or getattr(settings, "SILICONFLOW_API_KEY", "")
        self.default_base_url = os.getenv("SILICONFLOW_BASE_URL") or getattr(settings, "SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        self.llm_client = openai.OpenAI(api_key=self.api_key, base_url=self.default_base_url)

        # 候选数量上限（供LLM候选列表与后置约束使用）
        try:
            self.candidate_topk = int(os.getenv('RAG_CANDIDATE_TOPK', os.getenv('RAG_TOP_RECOMMENDATIONS_PER_SCENARIO', '3')))
        except Exception:
            self.candidate_topk = 3

        # 预载模型上下文（默认+场景覆盖）
        self.model_contexts: Dict[str, Dict[str, Any]] = {}
        self.scenario_overrides: List[Dict[str, Any]] = []
        self._override_index: Dict[str, List[Dict[str, Any]]] = {"panel": [], "topic": [], "scenario": [], "custom": []}
        self.default_inference_context: Dict[str, Any] = {}
        self.default_evaluation_context: Dict[str, Any] = {}
        self._load_model_contexts()

        # 配置参数（优先使用上下文，其次环境变量）
        self.llm_model = self.default_inference_context.get("llm_model") \
            or os.getenv("SILICONFLOW_LLM_MODEL") \
            or getattr(settings, "SILICONFLOW_LLM_MODEL", "Qwen/Qwen2.5-32B-Instruct")
        self.embedding_model = self.default_inference_context.get("embedding_model") \
            or os.getenv("SILICONFLOW_EMBEDDING_MODEL") \
            or "BAAI/bge-m3"
        self.base_url = self.default_inference_context.get("base_url") or self.default_base_url
        if self.base_url.rstrip('/') != self.default_base_url.rstrip('/'):
            self.llm_client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.similarity_threshold = float(os.getenv("VECTOR_SIMILARITY_THRESHOLD") or getattr(settings, "VECTOR_SIMILARITY_THRESHOLD", 0.6))
        self.debug_mode = (os.getenv("DEBUG_MODE", str(getattr(settings, "DEBUG_MODE", False))).lower() == "true")
        # 新增可调检索/候选参数
        self.scene_recall_topk = int(os.getenv("RAG_SCENE_RECALL_TOPK", "8"))  # 场景召回数量（用于检索，不等于展示数量）
        # reranker config
        self.use_reranker = os.getenv("RAG_USE_RERANKER", "true").lower() == "true"
        self.reranker_model = self.default_inference_context.get("reranker_model") \
            or os.getenv("RERANKER_MODEL") \
            or getattr(settings, "RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
        # rerank provider: auto | siliconflow | ollama | local
        self.rerank_provider = (os.getenv("RERANK_PROVIDER", "auto") or "auto").lower()
        # candidate recall topk (to control prompt length)
        self.procedure_candidate_topk = int(os.getenv("PROCEDURE_CANDIDATE_TOPK", "8"))
        # keyword config path for dynamic management
        self.keyword_config_path = os.getenv("RAG_KEYWORD_CONFIG_PATH", str(Path(__file__).resolve().parents[2] / "config" / "rag_keywords.json"))
        self.keyword_config = self._load_keyword_config()
        # rerank boosts
        self.panel_boost = float(os.getenv("RAG_PANEL_BOOST", "0.10"))
        self.topic_boost = float(os.getenv("RAG_TOPIC_BOOST", "0.20"))
        self.keyword_boost = float(os.getenv("RAG_KEYWORD_BOOST", "0.05"))
        self.rating_boost = float(os.getenv("RAG_RATING_BOOST", "0.03"))

        # RAG检索及重排优化参数
        self.dynamic_rerank = os.getenv("RAG_USE_DYNAMIC_RERANK", "true").lower() == "true"
        try:
            self.recs_fetch_topk = int(os.getenv("RAG_RECS_FETCH_TOPK", "5"))
        except Exception:
            self.recs_fetch_topk = 5

        # LLM输出优化
        self.force_json_output = os.getenv("LLM_FORCE_JSON", "true").lower() == "true"
        try:
            self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "512"))
        except Exception:
            self.max_tokens = 512
        try:
            self.llm_seed = int(os.getenv("LLM_SEED", "0")) if os.getenv("LLM_SEED") else None
        except Exception:
            self.llm_seed = None

        # 轻量嵌入缓存（进程内LRU）
        self._emb_cache_lock = threading.Lock()
        try:
            self._emb_cache_size = int(os.getenv("EMBED_CACHE_SIZE", "256"))
        except Exception:
            self._emb_cache_size = 256
        self._emb_cache: OrderedDict[str, List[float]] = OrderedDict()

        # 提示词配置参数
        self.top_scenarios = int(os.getenv("RAG_TOP_SCENARIOS", "2"))
        self.top_recommendations_per_scenario = int(os.getenv("RAG_TOP_RECOMMENDATIONS_PER_SCENARIO", "3"))
        self.show_reasoning = os.getenv("RAG_SHOW_REASONING", "true").lower() == "true"
        # Rules engine (disabled by default)
        try:
            self.rules_engine = load_engine()
        except Exception:
            self.rules_engine = None

        # 监控模型上下文文件，便于多进程环境下的热更新（每次请求前做mtime检查）
        self._contexts_path = Path(__file__).resolve().parents[2] / "config" / "model_contexts.json"
        try:
            self._contexts_mtime = self._contexts_path.stat().st_mtime
        except Exception:
            self._contexts_mtime = 0.0

        # Query signals extractor (configurable, negation-aware)
        try:
            self._signals_extractor = QuerySignalExtractor()
        except Exception as e:
            logger.warning(f"QuerySignalExtractor init failed, fallback to built-in: {e}")
            self._signals_extractor = None

    def _maybe_reload_contexts(self) -> None:
        """当检测到 model_contexts.json 发生变化时，重新加载并热更新关键参数。
        解决多worker下 /models/reload 仅作用于单进程的问题。
        """
        try:
            current_mtime = self._contexts_path.stat().st_mtime
        except Exception:
            current_mtime = 0.0
        if current_mtime != getattr(self, "_contexts_mtime", 0.0):
            self._load_model_contexts()
            self._contexts_mtime = current_mtime
            # 将默认推理上下文中的关键字段覆盖到运行时参数
            prev_base = self.base_url
            self.llm_model = self.default_inference_context.get("llm_model", self.llm_model)
            self.embedding_model = self.default_inference_context.get("embedding_model", self.embedding_model)
            self.reranker_model = self.default_inference_context.get("reranker_model", self.reranker_model)
            self.base_url = self.default_inference_context.get("base_url", self.base_url)
            if self.base_url.rstrip('/') != prev_base.rstrip('/'):
                self.llm_client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _load_model_contexts(self) -> None:
        """加载模型上下文与场景覆盖配置"""
        path = Path(__file__).resolve().parents[2] / "config" / "model_contexts.json"
        data: Dict[str, Any] = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except Exception as exc:
                logger.warning(f"读取模型上下文失败: {exc}")
        contexts = data.get('contexts') or {}
        overrides = data.get('scenario_overrides') or []
        self.model_contexts = contexts
        self.default_inference_context = self._clean_context(contexts.get('inference'))
        self.default_evaluation_context = self._clean_context(contexts.get('evaluation'))
        self.scenario_overrides = overrides
        self._override_index = self._build_override_index(overrides)

    @staticmethod
    def _clean_context(ctx: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        cleaned: Dict[str, Any] = {}
        if not ctx:
            return cleaned
        for key, value in ctx.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            cleaned[key] = value
        return cleaned

    @staticmethod
    def _build_override_index(overrides: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        index: Dict[str, List[Dict[str, Any]]] = {"panel": [], "topic": [], "scenario": [], "custom": []}
        for item in overrides or []:
            scope_type = (item.get('scope_type') or 'custom').lower()
            if scope_type not in index:
                scope_type = 'custom'
            index[scope_type].append(item)
        return index

    def _match_override(self, scope: Dict[str, Optional[str]]) -> Optional[Dict[str, Any]]:
        sid = (scope.get('scenario_id') or '').strip()
        if sid:
            for item in self._override_index.get('scenario', []):
                if (item.get('scope_id') or '').strip() == sid:
                    return item
        tid = (scope.get('topic_id') or '').strip()
        if tid:
            for item in self._override_index.get('topic', []):
                if (item.get('scope_id') or '').strip() == tid:
                    return item
        pid = (scope.get('panel_id') or '').strip()
        if pid:
            for item in self._override_index.get('panel', []):
                if (item.get('scope_id') or '').strip() == pid:
                    return item
        custom = (scope.get('custom') or '').strip()
        if custom:
            for item in self._override_index.get('custom', []):
                if (item.get('scope_id') or '').strip() == custom:
                    return item
        return None

    def _resolve_inference_context(self, scope: Dict[str, Optional[str]]) -> Dict[str, Any]:
        ctx = dict(self.default_inference_context)
        override = self._match_override(scope)
        if override and override.get('inference'):
            ctx.update(self._clean_context(override.get('inference')))
        ctx.setdefault('llm_model', self.llm_model)
        ctx.setdefault('embedding_model', self.embedding_model)
        ctx.setdefault('base_url', self.base_url)
        ctx.setdefault('reranker_model', self.reranker_model)
        # 新增：推理参数（若模型上下文提供，则透传；否则由下游默认）
        if 'temperature' not in ctx and self.default_inference_context.get('temperature') is not None:
            ctx['temperature'] = self.default_inference_context.get('temperature')
        if 'top_p' not in ctx and self.default_inference_context.get('top_p') is not None:
            ctx['top_p'] = self.default_inference_context.get('top_p')
        # 允许上下文传递 max_tokens / reasoning 开关 / 禁用思维指令
        if 'max_tokens' not in ctx and self.default_inference_context.get('max_tokens') is not None:
            ctx['max_tokens'] = self.default_inference_context.get('max_tokens')
        if 'reasoning_model' not in ctx and self.default_inference_context.get('reasoning_model') is not None:
            ctx['reasoning_model'] = self.default_inference_context.get('reasoning_model')
        if 'disable_thinking' not in ctx and self.default_inference_context.get('disable_thinking') is not None:
            ctx['disable_thinking'] = self.default_inference_context.get('disable_thinking')
        if 'no_thinking_tag' not in ctx and self.default_inference_context.get('no_thinking_tag') is not None:
            ctx['no_thinking_tag'] = self.default_inference_context.get('no_thinking_tag')
        return ctx

    def _extract_scope_info(self, scenarios: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
        if not scenarios:
            return {}
        primary = scenarios[0] or {}
        return {
            'scenario_id': primary.get('semantic_id') or primary.get('scenario_id'),
            'topic_id': primary.get('topic_semantic_id') or primary.get('topic_id'),
            'panel_id': primary.get('panel_semantic_id') or primary.get('panel_id'),
        }

    class _PooledConn:
        """轻量包装以在 close() 时归还连接池"""
        def __init__(self, raw, pool: ThreadedConnectionPool):
            self._raw = raw
            self._pool = pool
        def cursor(self, *a, **kw):
            return self._raw.cursor(*a, **kw)
        def close(self):
            try:
                self._pool.putconn(self._raw)
            except Exception:
                try:
                    self._raw.close()
                except Exception:
                    pass
        # 兼容常见方法
        def commit(self):
            return self._raw.commit()
        def rollback(self):
            return self._raw.rollback()
        @property
        def raw(self):
            return self._raw

    def _init_pool(self, host: str) -> None:
        """初始化连接池（仅一次）"""
        if self._db_pool is not None:
            return
        cfg = dict(self.db_config)
        cfg['host'] = host
        self._db_pool = ThreadedConnectionPool(
            minconn=self._db_pool_min,
            maxconn=self._db_pool_max,
            **cfg,
        )

    def connect_db(self):
        """建立数据库连接（优先连接池；带重试与Docker主机名回退）"""
        host = self.db_config.get('host') or 'localhost'
        port = int(self.db_config.get('port') or 5432)
        cfg_base = dict(self.db_config)
        # 当在容器中且配置为localhost/127.0.0.1时，尝试回退到服务名 'postgres'
        fallback_hosts = [host]
        if str(host) in ('localhost', '127.0.0.1'):
            fallback_hosts.append('postgres')
        # 重试总时长
        max_wait = int(os.getenv('DB_CONNECT_TIMEOUT', '30'))
        interval = 2
        start = time.time()
        last_err = None
        # 若已有连接池，直接取用
        if self._db_pool is not None:
            try:
                conn = self._db_pool.getconn()
                return self._PooledConn(conn, self._db_pool)
            except Exception as e:
                logger.warning(f"从连接池取连接失败，尝试重建: {e}")
                try:
                    self._db_pool.closeall()
                except Exception:
                    pass
                self._db_pool = None
        while time.time() - start < max_wait:
            for h in fallback_hosts:
                try:
                    cfg = dict(cfg_base)
                    cfg['host'] = h
                    # 首先尝试建立连接池
                    self._init_pool(h)
                    if self._db_pool is not None:
                        conn = self._db_pool.getconn()
                        if h != host:
                            logger.warning(f"DB连接使用备用主机 '{h}'（原配置: '{host}'）")
                        return self._PooledConn(conn, self._db_pool)
                    # 回退：直接单连接（极端情况）
                    raw = psycopg2.connect(**cfg)
                    if h != host:
                        logger.warning(f"DB连接使用备用主机 '{h}'（原配置: '{host}'）")
                    return raw
                except Exception as e:
                    last_err = e
                    time.sleep(interval)
        # 最终失败：给出提示信息，便于下次无需人工排查
        hint = (
            "数据库连接失败。请检查: "
            "1) 在Docker内应使用 PGHOST=postgres；"
            "2) docker-compose 服务是否已healthy；"
            "3) 端口与网络是否被占用或被防火墙阻断。"
        )
        logger.error(f"DB连接失败（host={host}, port={port}）：{last_err}; {hint}")
        raise last_err

    def search_clinical_scenarios(self, conn, query_vector: List[float], top_k: int = 3) -> List[Dict]:
        """搜索最相关的临床场景"""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Improve ANN recall quality if IVFFLAT index is used
            try:
                if self.pgvector_probes and self.pgvector_probes > 0:
                    cur.execute(f"SET LOCAL ivfflat.probes = {int(self.pgvector_probes)};")
            except Exception:
                pass
            vec_str = "[" + ",".join(map(str, query_vector)) + "]"
            sql = f"""
                SELECT
                    cs.semantic_id,
                    COALESCE(NULLIF(cs.description_zh,''), cs.description_en) AS description_zh,
                    cs.clinical_context,
                    cs.patient_population,
                    cs.risk_level,
                    cs.age_group,
                    cs.gender,
                    cs.urgency_level,
                    cs.symptom_category,
                    p.semantic_id as panel_semantic_id,
                    p.name_zh as panel_name,
                    t.semantic_id as topic_semantic_id,
                    t.name_zh as topic_name,
                    (1 - (cs.embedding <=> '{vec_str}'::vector)) AS similarity
                FROM clinical_scenarios cs
                LEFT JOIN panels p ON cs.panel_id = p.id
                LEFT JOIN topics t ON cs.topic_id = t.id
                WHERE cs.embedding IS NOT NULL AND cs.is_active = true
                ORDER BY cs.embedding <=> '{vec_str}'::vector
                LIMIT {top_k}
            """
            cur.execute(sql)
            return [dict(row) for row in cur.fetchall()]

    def get_scenario_with_recommendations(self, conn, scenario_ids: List[str]) -> List[Dict]:
        """获取场景及其相关的检查推荐（按场景组织）"""
        if not scenario_ids:
            return []

        scenario_ids_str = "','".join(scenario_ids)
        scenario_ids_placeholders = "'" + scenario_ids_str + "'"

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql = f"""
                SELECT
                    cs.semantic_id as scenario_id,
                    cs.description_zh as scenario_description,
                    cs.patient_population,
                    cs.risk_level,
                    cs.age_group,
                    cs.gender,
                    cs.urgency_level,
                    p.semantic_id as panel_semantic_id,
                    p.name_zh as panel_name,
                    t.semantic_id as topic_semantic_id,
                    t.name_zh as topic_name,
                    cr.procedure_id,
                    pd.name_zh AS procedure_name_zh,
                    pd.name_en AS procedure_name_en,
                    pd.modality,
                    pd.body_part,
                    pd.contrast_used,
                    pd.radiation_level,
                    pd.exam_duration,
                    pd.preparation_required,
                    cr.appropriateness_rating,
                    cr.appropriateness_category_zh,
                    cr.reasoning_zh,
                    cr.evidence_level,
                    cr.contraindications,
                    cr.special_considerations,
                    cr.pregnancy_safety
                FROM clinical_scenarios cs
                LEFT JOIN panels p ON cs.panel_id = p.id
                LEFT JOIN topics t ON cs.topic_id = t.id
                LEFT JOIN clinical_recommendations cr ON cs.semantic_id = cr.scenario_id
                LEFT JOIN procedure_dictionary pd ON cr.procedure_id = pd.semantic_id
                WHERE cs.semantic_id IN ({scenario_ids_placeholders})
                    AND cs.is_active = true
                    AND cr.is_active = true
                    AND pd.is_active = true
                    AND cr.appropriateness_rating > 5
                ORDER BY cs.semantic_id, cr.appropriateness_rating DESC
            """
            cur.execute(sql)
            results = [dict(row) for row in cur.fetchall()]

        # 按场景组织数据
        scenarios_with_recs = {}
        for row in results:
            scenario_id = row['scenario_id']
            if scenario_id not in scenarios_with_recs:
                scenarios_with_recs[scenario_id] = {
                    'scenario_id': scenario_id,
                    # 兼容下游评测：同时提供 scenario_description 与 description_zh
                    'scenario_description': row['scenario_description'],
                    'description_zh': row['scenario_description'],
                    'patient_population': row['patient_population'],
                    'risk_level': row['risk_level'],
                    'age_group': row['age_group'],
                    'gender': row['gender'],
                    'urgency_level': row['urgency_level'],
                    'panel_semantic_id': row.get('panel_semantic_id'),
                    'panel_name': row['panel_name'],
                    'topic_semantic_id': row.get('topic_semantic_id'),
                    'topic_name': row['topic_name'],
                    'recommendations': []
                }

            if row['procedure_id']:  # 有推荐的情况
                scenarios_with_recs[scenario_id]['recommendations'].append({
                    'procedure_name_zh': row['procedure_name_zh'],
                    'procedure_name_en': row['procedure_name_en'],
                    'modality': row['modality'],
                    'body_part': row['body_part'],
                    'contrast_used': row['contrast_used'],
                    'radiation_level': row['radiation_level'],
                    'exam_duration': row['exam_duration'],
                    'preparation_required': row['preparation_required'],
                    'appropriateness_rating': row['appropriateness_rating'],
                    'appropriateness_category_zh': row['appropriateness_category_zh'],
                    'reasoning_zh': row['reasoning_zh'],
                    'evidence_level': row['evidence_level'],
                    'contraindications': row['contraindications'],
                    'special_considerations': row['special_considerations'],
                    'pregnancy_safety': row['pregnancy_safety']
                })

        return list(scenarios_with_recs.values())

    def prepare_llm_prompt(self, query: str, scenarios: List[Dict], scenarios_with_recs: List[Dict], is_low_similarity: bool = False,
                          top_scenarios: Optional[int] = None, top_recs_per_scenario: Optional[int] = None, show_reasoning: Optional[bool] = None,
                          candidates: Optional[List[Dict]] = None) -> str:
        """准备LLM推理提示词（按场景组织推荐）"""

        # 使用传入参数或默认配置
        top_scenarios = top_scenarios if top_scenarios is not None else self.top_scenarios
        top_recs_per_scenario = top_recs_per_scenario if top_recs_per_scenario is not None else self.top_recommendations_per_scenario
        show_reasoning = show_reasoning if show_reasoning is not None else self.show_reasoning

        # 生成候选清单文本（若提供）
        candidates_block = ""
        if candidates:
            unique = []
            seen = set()
            for c in candidates:
                name = c.get('procedure_name_zh') or c.get('name_zh') or c.get('procedure_name') or ''
                modality = c.get('modality', '')
                key = (name, modality)
                if name and key not in seen:
                    seen.add(key)
                    unique.append({'name': name, 'modality': modality})
            if unique:
                lines = [f"{i+1}. {u['name']} ({u['modality']})" for i, u in enumerate(unique[:30])]
                candidates_block = "\n候选检查（必须从下列候选中选择，不得输出候选之外的检查）：\n" + "\n".join(lines) + "\n"

        if is_low_similarity:
            # 低相似度时的无RAG推理（精简版）
            prompt = f"""
你是放射科医生，根据临床情况推荐最合适的影像检查项目。

患者查询: "{query}"

注意：数据库中未找到匹配场景，请根据专业经验推荐3个最合适的影像检查项目。

 {candidates_block}

 严格输出要求：
仅输出有效JSON，不能包含任何解释、Markdown代码块或额外文字
不要使用```包裹，不要有多余的换行或注释
字段名必须严格一致；不要多输出未定义字段
JSON中不允许出现尾随逗号
若上方提供了候选检查，必须仅从候选中选择；若不合适可减少数量，但不得新增候选外检查

输出JSON格式:
{{
    "recommendations": [
        {{
            "rank": 1,
            "procedure_name": "检查项目名称",
            "modality": "检查方式",
            "appropriateness_rating": "评分/9",
            "recommendation_reason": "推荐理由",
            "clinical_considerations": "临床考虑"
        }},
        {{
            "rank": 2,
            "procedure_name": "检查项目名称",
            "modality": "检查方式",
            "appropriateness_rating": "评分/9",
            "recommendation_reason": "推荐理由",
            "clinical_considerations": "临床考虑"
        }},
        {{
            "rank": 3,
            "procedure_name": "检查项目名称",
            "modality": "检查方式",
            "appropriateness_rating": "评分/9",
            "recommendation_reason": "推荐理由",
            "clinical_considerations": "临床考虑"
        }}
    ],
    "summary": "推荐总结",
    "no_rag": true,
    "rag_note": "无RAG模式：基于医生专业经验生成"
}}
"""
        else:
            # 有RAG数据时的提示词（可配置版）
            scenarios_info = ""
            # 使用可配置的场景数量
            valid_scenarios = [s for s in scenarios_with_recs if s.get('recommendations')]
            for i, scenario_data in enumerate(valid_scenarios[:top_scenarios], 1):
                scenario_info = f"""
## 场景 {i}: {scenario_data['scenario_id']}
**描述**: {scenario_data['scenario_description']}
**科室**: {scenario_data['panel_name']}
**主题**: {scenario_data['topic_name']}

### 推荐检查:
"""

                if scenario_data['recommendations']:
                    # 使用可配置的推荐数量
                    for j, rec in enumerate(scenario_data['recommendations'][:top_recs_per_scenario], 1):
                        rec_info = f"""
{j}. **{rec['procedure_name_zh']}** ({rec['modality']})
   - 评分: {rec['appropriateness_rating']}/9 ({rec['appropriateness_category_zh']})"""

                        # 根据配置决定是否显示推荐理由
                        if show_reasoning and rec.get('reasoning_zh'):
                            reasoning = rec.get('reasoning_zh', 'N/A')
                            # 限制理由长度以控制提示词大小
                            if len(reasoning) > 200:
                                reasoning = reasoning[:200] + '...'
                            rec_info += f"\n   - 理由: {reasoning}"

                        rec_info += "\n\n"
                        scenario_info += rec_info
                else:
                    scenario_info += "   该场景暂无高评分推荐。\n\n"

                scenarios_info += scenario_info

            # 相似度信息（与配置的场景数量匹配）
            similarity_info = ""
            for i, scenario in enumerate(scenarios[:top_scenarios], 1):
                similarity_info += f"   场景{i}: {scenario['similarity']:.3f}\n"

            prompt = f"""
你是放射科医生，根据临床场景推荐最合适的影像检查项目。你要遵循医学诊断规范和ACR-AC指南的相关规则进行合理推荐.

**患者查询**: "{query}"

**相似度**:
{similarity_info}

{scenarios_info}

基于以上信息，推荐最合适的3个影像检查项目。

{candidates_block}

严格输出要求：
仅输出有效JSON，不能包含任何解释、Markdown代码块或额外文字
不要使用```包裹，不要有多余的换行或注释
字段名必须严格一致；不要多输出未定义字段
JSON中不允许出现尾随逗号
必须基于上述上下文与候选进行推荐，并从候选中选择；不得输出候选之外的检查
对于每个被选择的检查项目，appropriateness_rating 必须与候选/上下文中展示的评分一致，不得改动或臆造；若上下文未提供评分，则省略该字段

输出JSON格式:
{{
    "recommendations": [
        {{
            "rank": 1,
            "procedure_name": "检查项目名称",
            "modality": "检查方式",
            "appropriateness_rating": "评分/9",
            "recommendation_reason": "推荐理由",
            "clinical_considerations": "临床考虑"
        }},
        {{
            "rank": 2,
            "procedure_name": "检查项目名称",
            "modality": "检查方式",
            "appropriateness_rating": "评分/9",
            "recommendation_reason": "推荐理由",
            "clinical_considerations": "临床考虑"
        }},
        {{
            "rank": 3,
            "procedure_name": "检查项目名称",
            "modality": "检查方式",
            "appropriateness_rating": "评分/9",
            "recommendation_reason": "推荐理由",
            "clinical_considerations": "临床考虑"
        }}
    ],
    "summary": "推荐总结",
    "no_rag": false
}}
"""

        return prompt

    def search_procedure_candidates(self, conn, query_vector: List[float], top_k: int = 15) -> List[Dict]:
        """基于向量在procedure_dictionary中检索候选检查项目"""
        if conn is None:
            return []
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Improve ANN recall quality if IVFFLAT index is used
            try:
                if self.pgvector_probes and self.pgvector_probes > 0:
                    cur.execute(f"SET LOCAL ivfflat.probes = {int(self.pgvector_probes)};")
            except Exception:
                pass
            vec_str = "[" + ",".join(map(str, query_vector)) + "]"
            sql = f"""
                SELECT
                    pd.semantic_id,
                    pd.name_zh,
                    pd.name_en,
                    pd.modality,
                    pd.body_part,
                    pd.description_zh,
                    (1 - (pd.embedding <=> '{vec_str}'::vector)) AS similarity
                FROM procedure_dictionary pd
                WHERE pd.embedding IS NOT NULL AND pd.is_active = true
                ORDER BY pd.embedding <=> '{vec_str}'::vector
                LIMIT {top_k}
            """
            cur.execute(sql)
            rows = [dict(r) for r in cur.fetchall()]
            # 统一字段以便prompt使用
            for r in rows:
                r['procedure_name_zh'] = r.get('name_zh')
            return rows

    def call_llm(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """调用LLM进行推理（使用Qwen2.5-32B）"""
        try:
            ctx = context or {}
            model_name = ctx.get('llm_model') or self.llm_model
            base_url = ctx.get('base_url') or self.base_url
            api_key = ctx.get('api_key') or self.api_key
            client = self.llm_client
            # Ollama 端点通常无需真实 key，OpenAI SDK 需要一个值；使用占位 'ollama'
            if base_url and (('11434' in base_url) or ('ollama' in base_url.lower())) and not api_key:
                api_key = os.getenv('OLLAMA_API_KEY') or 'ollama'
            if base_url.rstrip('/') != self.base_url.rstrip('/') or api_key != self.api_key:
                client = openai.OpenAI(api_key=api_key, base_url=base_url)

            if self.debug_mode:
                logger.info(f"LLM调用模型: {model_name}")
                logger.info(f"LLM提示词长度: {len(prompt)} 字符")

            # 读取推理参数（默认按你的要求：temperature 8 0~0.3，top_p 默认 0.7；不限制 max_tokens）
            temperature = ctx.get('temperature')
            if temperature is None:
                temperature = 0.1
            top_p = ctx.get('top_p')
            if top_p is None:
                top_p = 0.7

            # 推断/读取“思维模型”与禁用思维配置
            def _looks_reasoning(name: str) -> bool:
                n = (name or '').lower()
                for key in ['gpt-oss', 'deepseek-r1', 'qwq', 'r1', 'reason']:
                    if key in n:
                        return True
                return False
            reasoning_flag = bool(ctx.get('reasoning_model')) or _looks_reasoning(model_name)
            disable_thinking = bool(ctx.get('disable_thinking'))
            no_thinking_tag = (ctx.get('no_thinking_tag') or '').strip()

            # 如需禁用思维，追加抑制性约束
            sys_inst = (
                "你是一位专业的放射科医生，擅长影像检查推荐。"
                "必须仅输出有效JSON，不得包含解释、代码块(如```json)、或任何额外文字。"
                "JSON字段名必须与要求完全一致，且不得包含尾随逗号。"
                "严禁输出<think>、思维链、推理过程、系统提示或任何与JSON无关的内容。"
            )
            user_content = prompt
            if disable_thinking and no_thinking_tag:
                user_content = f"{prompt}\n{no_thinking_tag}"

            kwargs: Dict[str, Any] = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": sys_inst},
                    {"role": "user", "content": user_content}
                ],
                "temperature": temperature,
                "top_p": top_p,
            }
            # 强制JSON输出（部分OpenAI兼容服务支持）
            is_ollama = bool(base_url and (("11434" in base_url) or ("ollama" in base_url.lower())))
            if self.force_json_output and not is_ollama:
                kwargs["response_format"] = {"type": "json_object"}
            # 限制生成长度，避免过度输出导致延迟
            max_out = ctx.get('max_tokens') if ctx.get('max_tokens') is not None else self.max_tokens
            try:
                max_out = int(max_out) if max_out is not None else None
            except Exception:
                max_out = None
            if reasoning_flag and (not max_out or max_out < 1024):
                max_out = 1024
            if max_out and max_out > 0:
                kwargs["max_tokens"] = max_out
            # 禁用思维的额外停止标记（兼容部分模型输出<think>）
            if disable_thinking:
                kwargs["stop"] = kwargs.get("stop") or ["</think>", "<think>"]
            if self.llm_seed is not None:
                kwargs["seed"] = self.llm_seed

            response = client.chat.completions.create(
                **kwargs
            )

            result = response.choices[0].message.content

            if self.debug_mode:
                logger.info(f"LLM原始响应长度: {len(result)} 字符")
                logger.info(f"LLM原始响应: {result[:500]}...")  # 只显示前500字符

            return result

        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return self._fallback_response()

    def _embed_cached(self, text: str, model: str, base_url: str) -> List[float]:
        """进程内LRU缓存的嵌入生成"""
        key_src = f"{model}|{base_url}|{hashlib.md5((text or '').encode('utf-8')).hexdigest()}"
        with self._emb_cache_lock:
            if key_src in self._emb_cache:
                # LRU: move to end
                vec = self._emb_cache.pop(key_src)
                self._emb_cache[key_src] = vec
                return vec
        vec = embed_with_siliconflow(text, api_key=self.api_key, model=model, base_url=base_url)
        with self._emb_cache_lock:
            self._emb_cache[key_src] = vec
            if len(self._emb_cache) > self._emb_cache_size:
                # pop oldest
                self._emb_cache.popitem(last=False)
        return vec

    def _fallback_response(self) -> str:
        """LLM调用失败时的降级响应"""
        return """
{
    "recommendations": [
        {
            "rank": 1,
            "procedure_name": "系统暂时无法生成推荐",
            "modality": "N/A",
            "appropriateness_rating": "N/A",
            "recommendation_reason": "LLM服务暂时不可用，请稍后重试",
            "clinical_considerations": "建议咨询专业医生"
        }
    ],
    "summary": "系统暂时无法提供智能推荐，建议使用传统向量搜索功能"
}
"""

    def parse_llm_response(self, llm_response: str) -> Dict[str, Any]:
        """解析LLM响应"""
        try:
            text = llm_response.strip()
            # 去除代码块围栏
            if text.startswith("```"):
                lines = [ln for ln in text.splitlines() if not ln.strip().startswith("```")]
                text = "\n".join(lines)

            # 规范化引号（将中文弯引号转义为 \" 以避免破坏JSON字符串）
            text = text.replace("“", '\\"').replace("”", '\\"').replace("’", "'").replace("‘", "'")

            # 提取平衡的JSON对象
            def extract_balanced_json(s: str) -> Optional[str]:
                start = s.find('{')
                if start == -1:
                    return None
                depth = 0
                in_str = False
                esc = False
                for i in range(start, len(s)):
                    ch = s[i]
                    if in_str:
                        if esc:
                            esc = False
                        elif ch == '\\':
                            esc = True
                        elif ch == '"':
                            in_str = False
                        continue
                    else:
                        if ch == '"':
                            in_str = True
                        elif ch == '{':
                            depth += 1
                        elif ch == '}':
                            depth -= 1
                            if depth == 0:
                                return s[start:i+1]
                return None

            candidate = extract_balanced_json(text)
            if not candidate:
                raise ValueError("未找到有效的JSON对象")

            # 去掉可能的尾随逗号
            candidate = re.sub(r",\s*([}\]])", r"\1", candidate)

            # 一次尝试：严格JSON解析
            try:
                data = json.loads(candidate)
            except Exception:
                # 针对部分模型（如 Ollama 上的 gpt-oss）输出的宽松JSON：
                # 1) 单引号键/值 -> 双引号；2) 未加引号的键 -> 自动补双引号
                relaxed = candidate
                # 单引号包裹的键：{'key': → {"key":
                relaxed = re.sub(r"([\{,]\s*)'([^'\n\r]+?)'(\s*:)", r'\1"\2"\3', relaxed)
                # 单引号包裹的字符串值：: 'val' → : "val"
                relaxed = re.sub(r"(:\s*)'([^'\n\r]*?)'", r'\1"\2"', relaxed)
                # 未加引号的简单键：{ key: → { "key":
                relaxed = re.sub(r"([\{,]\s*)([A-Za-z_][A-Za-z0-9_\-]*)(\s*:)", r'\1"\2"\3', relaxed)
                # 再次移除尾随逗号
                relaxed = re.sub(r",\s*([}\]])", r"\1", relaxed)
                try:
                    data = json.loads(relaxed)
                except Exception:
                    # 最后兜底：尝试使用 ast.literal_eval 解析 python风格字典
                    try:
                        import ast
                        data_py = ast.literal_eval(relaxed)
                        # 确保可序列化
                        data = json.loads(json.dumps(data_py, ensure_ascii=False))
                    except Exception as _:
                        # 维持原有异常流程，由下方容错解析兜底
                        raise

            # 结果规范化
            if not isinstance(data, dict):
                data = {"recommendations": data}
            if "recommendations" not in data or not isinstance(data["recommendations"], list):
                data["recommendations"] = []
            if "summary" not in data:
                data["summary"] = ""

            # 基于Pydantic进行校验与纠正
            class _RecItem(BaseModel):
                rank: Optional[int] = None
                procedure_name: str = Field(default_factory=str)
                modality: str = Field(default_factory=str)
                appropriateness_rating: Union[str, int, float] = Field(default_factory=str)
                recommendation_reason: str = Field(default_factory=str)
                clinical_considerations: str = Field(default_factory=str)

            class _LLMOut(BaseModel):
                recommendations: List[_RecItem] = Field(default_factory=list)
                summary: str = Field(default_factory=str)
                no_rag: Optional[bool] = None
                rag_note: Optional[str] = None

            # 同义键纠正
            fixed_recs = []
            for i, rec in enumerate(data.get("recommendations", []), start=1):
                if not isinstance(rec, dict):
                    continue
                rec = dict(rec)
                if "procedure" in rec and "procedure_name" not in rec:
                    rec["procedure_name"] = rec.pop("procedure")
                # 合并可能的理由字段
                for alt in ["reason", "reasoning", "clinical_reasoning"]:
                    if alt in rec and not rec.get("recommendation_reason"):
                        rec["recommendation_reason"] = rec.pop(alt)
                # rank默认
                if "rank" not in rec or rec["rank"] in (None, ""):
                    rec["rank"] = i
                # 评分标准化为 "x/9"
                ar = rec.get("appropriateness_rating")
                if isinstance(ar, (int, float)):
                    try:
                        val = int(round(float(ar)))
                        rec["appropriateness_rating"] = f"{val}/9"
                    except Exception:
                        rec["appropriateness_rating"] = str(ar)
                elif isinstance(ar, str):
                    # 简单归一化，如 "8" -> "8/9"
                    s = ar.strip()
                    if s.isdigit():
                        rec["appropriateness_rating"] = f"{s}/9"
                fixed_recs.append(rec)

            data["recommendations"] = fixed_recs

            try:
                validated = _LLMOut(**data)
            except ValidationError as ve:
                logger.warning(f"LLM响应字段校验警告: {ve}")
                # 尽力返回已纠正的数据
                validated = _LLMOut(recommendations=[_RecItem(**r) for r in fixed_recs], summary=data.get("summary", ""))

            # 转回dict
            out = {
                "recommendations": [r.model_dump() for r in validated.recommendations],
                "summary": validated.summary,
            }
            # 兼容前端/其他调用方字段：补充 name / recommendation / procedure 同义字段
            try:
                for rec in out.get("recommendations", []) or []:
                    pname = rec.get("procedure_name")
                    if pname:
                        rec.setdefault("name", pname)
                        rec.setdefault("recommendation", pname)
                        rec.setdefault("procedure", pname)
            except Exception:
                pass
            if validated.no_rag is not None:
                out["no_rag"] = validated.no_rag
            if validated.rag_note is not None:
                out["rag_note"] = validated.rag_note

            return out
        except Exception as e:
            logger.error(f"解析LLM响应失败: {e}")
            if self.debug_mode:
                logger.error(f"原始响应: {llm_response}")
            # 容错解析：基于正则从原始文本提取核心字段，尽力返回结构化结果
            try:
                recs = []
                txt = llm_response
                # 容许中文引号和普通引号
                q = '"“”'
                def val(pattern):
                    m = re.search(pattern, txt, re.S)
                    return m.group(1).strip() if m else ""
                # 匹配多个recommendation块
                patt = re.compile(r'"?procedure_name"?\s*:\s*(["“”])([^"“”]+)\1.*?"?modality"?\s*:\s*(["“”])([^"“”]+)\3.*?"?appropriateness_rating"?\s*:\s*(["“”])?([0-9/ ]+)\5?.*?"?recommendation_reason"?\s*:\s*(["“”])([^"“”]+)\7', re.S)
                for m in patt.finditer(txt):
                    procedure_name = m.group(2).strip()
                    modality = m.group(4).strip()
                    rating = m.group(6).strip()
                    reason = m.group(8).strip()
                    recs.append({
                        "rank": len(recs)+1,
                        "procedure_name": procedure_name,
                        "modality": modality,
                        "appropriateness_rating": rating,
                        "recommendation_reason": reason,
                        "clinical_considerations": ""
                    })
                summary = val(r'"?summary"?\s*:\s*(["“”])([^"“”]+)\1')
                if recs or summary:
                    return {"recommendations": recs, "summary": summary}
            except Exception as ee:
                logger.warning(f"容错解析也失败: {ee}")
            return {"recommendations": [], "summary": f"解析LLM响应失败: {str(e)}"}

    def generate_intelligent_recommendation(self, query: str, top_scenarios: Optional[int] = None,
                                          top_recommendations_per_scenario: Optional[int] = None,
                                          show_reasoning: Optional[bool] = None,
                                          similarity_threshold: Optional[float] = None,
                                          debug_flag: Optional[bool] = None,
                                          compute_ragas: Optional[bool] = None,
                                          ground_truth: Optional[str] = None) -> Dict[str, Any]:
        """生成智能推荐（主入口函数）"""
        start_time = time.time()
        debug_info = {}
        timings: Dict[str, int] = {"total_ms": 0}

        # 检查模型上下文是否更新（多worker下每次请求自愈热更新）
        self._maybe_reload_contexts()

        # 使用传入参数或默认配置
        current_threshold = similarity_threshold if similarity_threshold is not None else self.similarity_threshold

        try:
            # 1. 生成查询向量
            logger.info(f"开始处理查询: {query}")
            do_debug = (debug_flag is True) or self.debug_mode
            if do_debug:
                debug_info["step_1_query"] = query

            active_context = self._resolve_inference_context({})
            context_base_url = active_context.get('base_url')
            context_llm_model = active_context.get('llm_model')
            context_embedding_model = active_context.get('embedding_model')
            context_reranker = active_context.get('reranker_model')

            t_embed_start = time.time()
            # 使用带LRU的嵌入生成，减少重复请求
            query_vector = self._embed_cached(
                query,
                model=context_embedding_model,
                base_url=context_base_url,
            )
            timings["embedding_ms"] = int((time.time() - t_embed_start) * 1000)
            if do_debug:
                debug_info["step_2_vector_generation"] = {
                    "vector_dimension": len(query_vector),
                    "vector_sample": query_vector[:5],  # 只显示前5个元素
                    "embedding_model": context_embedding_model,
                    "base_url": context_base_url,
                }

            # 2. 连接数据库（失败则降级为无RAG模式）
            conn = None
            db_ok = True
            try:
                conn = self.connect_db()
            except Exception as db_err:
                db_ok = False
                logger.warning(f"数据库连接失败，将使用无RAG模式: {db_err}")
                if self.debug_mode:
                    debug_info["db_connection_error"] = str(db_err)

            # 3. 搜索相关临床场景（使用可配置的召回 Top K），若DB不可用则跳过
            logger.info("搜索相关临床场景...")
            recall_k = self.scene_recall_topk
            scenarios = []
            if db_ok and conn is not None:
                t_search_start = time.time()
                scenarios = self.search_clinical_scenarios(conn, query_vector, top_k=recall_k)
                timings["search_ms"] = int((time.time() - t_search_start) * 1000)
                # 保存原始召回顺序（按向量距离升序，即相似度降序）供trace展示
                scenarios_original = list(scenarios)
                scope_info = self._extract_scope_info(scenarios)
                scoped_context = self._resolve_inference_context(scope_info)
                if scoped_context != active_context:
                    if do_debug:
                        debug_info["context_override"] = {
                            "scope": scope_info,
                            "resolved": scoped_context,
                            "base": active_context,
                        }
                    active_context = scoped_context
                    context_base_url = scoped_context.get('base_url', context_base_url)
                    context_llm_model = scoped_context.get('llm_model', context_llm_model)
                    context_embedding_model = scoped_context.get('embedding_model', context_embedding_model)
                    context_reranker = scoped_context.get('reranker_model', context_reranker)
                # 取出召回场景的推荐，增强rerank语料（仅取前N以降低查询量）
                try:
                    fetch_n = max(1, min(self.recs_fetch_topk, len(scenarios)))
                    recall_ids = [s['semantic_id'] for s in scenarios[:fetch_n]]
                    scenarios_with_recs_all = self.get_scenario_with_recommendations(conn, recall_ids)
                except Exception as re:
                    logger.warning(f"召回场景推荐获取失败: {re}")
                    scenarios_with_recs_all = []
                # 面向 panel/topic/关键词 的软重排 + reranker（优先）；在高置信召回时可跳过rerank以提速
                try:
                    t_rerank_start = time.time()
                    skip_rerank = False
                    if self.dynamic_rerank and len(scenarios) >= 2:
                        s0, s1 = scenarios[0], scenarios[1]
                        try:
                            gap = float(s0.get('similarity', 0.0)) - float(s1.get('similarity', 0.0))
                            if float(s0.get('similarity', 0.0)) >= 0.85 and gap >= 0.05:
                                skip_rerank = True
                        except Exception:
                            pass
                    if not skip_rerank:
                        target_panels, target_topics = self._infer_targets_from_query(query)
                        scenarios = self._rerank_scenarios(
                            query,
                            scenarios,
                            target_panels=target_panels,
                            target_topics=target_topics,
                            alpha_panel=self.panel_boost,
                            alpha_topic=self.topic_boost,
                            alpha_kw=self.keyword_boost,
                            scenarios_with_recs=scenarios_with_recs_all,
                            reranker_base_url=context_base_url,
                            reranker_model=context_reranker,
                        )
                    else:
                        if do_debug:
                            logger.info("跳过rerank（高置信召回且相似度差距明显）")
                except Exception as re:
                    logger.warning(f"场景重排失败: {re}")
                    t_rerank_start = time.time()  # 确保后续赋值存在

                # 规则引擎：rerank阶段（启用时可加权/过滤），默认audit-only
                try:
                    if self.rules_engine and self.rules_engine.enabled:
                        rr_ctx = {
                            "query": query,
                            "query_signals": self._extract_query_signals(query),
                        }
                        rr_res = self.rules_engine.apply_rerank(rr_ctx, scenarios)
                        scenarios = rr_res.get('scenarios') or scenarios
                        if do_debug:
                            debug_info.setdefault('rules_audit', {})['rerank'] = rr_res.get('audit_logs') or []
                except Exception as re:
                    logger.warning(f"规则引擎(rerank)执行失败: {re}")
                finally:
                    timings["rerank_ms"] = int((time.time() - t_rerank_start) * 1000)

            if do_debug:
                debug_info["step_3_scenarios_search"] = {
                    "found_scenarios": len(scenarios),
                    "scenarios": [
                        {
                            "id": s["semantic_id"],
                            "similarity": s["similarity"],
                            "description": s["description_zh"][:50] + "..."
                        } for s in scenarios[:10]
                    ]
                }
                debug_info["step_3_recall_topk"] = recall_k
                try:
                    tp, tt = self._infer_targets_from_query(query)
                    debug_info["step_3_targets"] = {"panels": list(tp), "topics": list(tt)}
                    debug_info["step_3_boosts"] = {
                        "panel_boost": self.panel_boost,
                        "topic_boost": self.topic_boost,
                        "keyword_boost": self.keyword_boost,
                    }
                except Exception:
                    pass

            if db_ok and not scenarios:
                return {
                    "success": False,
                    "message": "未找到相关的临床场景",
                    "recommendations": [],
                    "scenarios": [],
                    "debug_info": debug_info if self.debug_mode else None
                }

            # 4. 检查相似度阈值（使用可配置阈值）
            max_similarity = max((s.get("similarity", 0.0) for s in scenarios), default=0.0)
            is_low_similarity = (not db_ok) or (max_similarity < current_threshold)

            if do_debug:
                debug_info["step_4_similarity_check"] = {
                    "max_similarity": max_similarity,
                    "threshold": current_threshold,
                    "is_low_similarity": is_low_similarity,
                    "similarity_status": "low" if is_low_similarity else "high"
                }

            # 5. 根据相似度决定处理方式
            if is_low_similarity:
                # 低相似度：无RAG模式
                logger.info(f"最高相似度 {max_similarity:.3f} 低于阈值 {current_threshold}，使用无RAG模式")

                # 候选检查（procedure_dictionary向量检索，半RAG）
                candidates = []
                if db_ok and conn is not None:
                    try:
                        candidates = self.search_procedure_candidates(conn, query_vector, top_k=self.procedure_candidate_topk)
                    except Exception as ce:
                        logger.warning(f"候选检查检索失败: {ce}")
                t_prompt_start = time.time()
                prompt = self.prepare_llm_prompt(
                    query, scenarios, [], is_low_similarity=True,
                    top_scenarios=top_scenarios,
                    top_recs_per_scenario=top_recommendations_per_scenario,
                    show_reasoning=show_reasoning,
                    candidates=candidates
                )
                timings["prompt_build_ms"] = int((time.time() - t_prompt_start) * 1000)
                scenarios_with_recs = []

                if do_debug:
                    debug_info["step_5_mode"] = "no_rag"
                    debug_info["step_6_prompt_length"] = len(prompt)
                    debug_info["step_6_prompt_preview"] = prompt[:300] + "..."
                    if candidates:
                        debug_info["step_5_candidates"] = {
                            "count": len(candidates),
                            "preview": [
                                {
                                    "name": c.get("procedure_name_zh") or c.get("name_zh"),
                                    "modality": c.get("modality"),
                                    "similarity": c.get("similarity")
                                } for c in candidates[:5]
                            ]
                        }
            else:
                # 高相似度：RAG模式
                logger.info(f"最高相似度 {max_similarity:.3f} 高于阈值 {current_threshold}，使用RAG模式")

                # 获取场景及其推荐（复用召回时已取的，若无则再取）
                scenario_ids = [s['semantic_id'] for s in scenarios]
                try:
                    # 从之前召回缓存中过滤
                    _map = {s['scenario_id']: s for s in (locals().get('scenarios_with_recs_all') or [])}
                    scenarios_with_recs = [ _map[sid] for sid in scenario_ids if sid in _map ]
                    if not scenarios_with_recs:
                        scenarios_with_recs = self.get_scenario_with_recommendations(conn, scenario_ids)
                except Exception:
                    scenarios_with_recs = self.get_scenario_with_recommendations(conn, scenario_ids)
                # 从场景推荐构建候选清单：先保证每个已选场景的前N条进入候选（保持顺序），再补全全局高分项，再融合 procedure_dictionary 候选
                # 目标上限：动态取 max(candidate_topk, top_scenarios*top_recs_per_scenario)
                try:
                    cap_dynamic = int((top_scenarios or self.top_scenarios) * (top_recs_per_scenario or self.top_recommendations_per_scenario))
                except Exception:
                    cap_dynamic = self.candidate_topk
                candidate_cap = max(int(self.candidate_topk or 0), int(cap_dynamic or 0), 1)

                candidates: List[Dict[str, Any]] = []
                seen_keys: set = set()
                # 1) 逐场景保序加入每场景Top-N，确保关键项（如CTA）不会被全局排序淹没
                for sc in scenarios_with_recs:
                    added = 0
                    for rec in (sc.get('recommendations') or [])[: max(1, int(top_recommendations_per_scenario or self.top_recommendations_per_scenario))]:
                        name = rec.get('procedure_name_zh') or rec.get('procedure_name_en')
                        if not name:
                            continue
                        key = (name, rec.get('modality') or '')
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        candidates.append({'procedure_name_zh': name, 'modality': rec.get('modality')})
                        added += 1
                        if len(candidates) >= candidate_cap:
                            break
                    if len(candidates) >= candidate_cap:
                        break

                # 2) 补全全局高分项（rating 降序，>5 分），避免漏掉其他高评分项目
                if len(candidates) < candidate_cap:
                    flat_recs: List[Dict[str, Any]] = []
                    for sc in scenarios_with_recs:
                        for rec in sc.get('recommendations', []) or []:
                            name = rec.get('procedure_name_zh') or rec.get('procedure_name_en')
                            if not name:
                                continue
                            try:
                                rating = float(rec.get('appropriateness_rating') or 0)
                            except Exception:
                                rating = 0.0
                            if rating > 5.0:
                                flat_recs.append({'procedure_name_zh': name, 'modality': rec.get('modality'), 'rating': rating})
                    # 去重保留最高分
                    best: Dict[tuple, Dict[str, Any]] = {}
                    for r in flat_recs:
                        k = (r.get('procedure_name_zh') or '', r.get('modality') or '')
                        if not k[0]:
                            continue
                        if (k not in best) or (float(r.get('rating') or 0) > float(best[k].get('rating') or 0)):
                            best[k] = r
                    for r in sorted(best.values(), key=lambda x: x.get('rating', 0.0), reverse=True):
                        k = (r.get('procedure_name_zh') or '', r.get('modality') or '')
                        if k in seen_keys:
                            continue
                        candidates.append({'procedure_name_zh': r['procedure_name_zh'], 'modality': r.get('modality')})
                        seen_keys.add(k)
                        if len(candidates) >= candidate_cap:
                            break

                # 3) 如仍不足，再融合基于 procedure_dictionary 的相似候选
                if db_ok and conn is not None:
                    try:
                        proc_candidates = self.search_procedure_candidates(conn, query_vector, top_k=self.procedure_candidate_topk)
                        for c in proc_candidates:
                            name = c.get('procedure_name_zh') or c.get('name_zh') or c.get('procedure_name')
                            modality = c.get('modality')
                            key = (name or '', modality or '')
                            if name and key not in seen_keys:
                                seen_keys.add(key)
                                candidates.append({'procedure_name_zh': name, 'modality': modality})
                                # 维持候选上限
                                if len(candidates) >= candidate_cap:
                                    break
                    except Exception as ce:
                        logger.warning(f"补充候选检索失败: {ce}")
                t_prompt_start = time.time()
                prompt = self.prepare_llm_prompt(
                    query, scenarios, scenarios_with_recs, is_low_similarity=False,
                    top_scenarios=top_scenarios,
                    top_recs_per_scenario=top_recommendations_per_scenario,
                    show_reasoning=show_reasoning,
                    candidates=candidates
                )
                timings["prompt_build_ms"] = int((time.time() - t_prompt_start) * 1000)

                if do_debug:
                    debug_info["step_5_mode"] = "rag"
                    debug_info["step_5_scenarios_with_recs"] = {
                        "scenarios_count": len(scenarios_with_recs),
                        "total_recommendations": sum(len(s.get("recommendations", [])) for s in scenarios_with_recs),
                        "scenarios_summary": [
                            {
                                "id": s["scenario_id"],
                                "description": s["scenario_description"][:50] + "...",
                                "recommendations_count": len(s.get("recommendations", []))
                            } for s in scenarios_with_recs
                        ]
                    }
                    if candidates:
                        debug_info["step_5_candidates"] = {
                            "count": len(candidates),
                            "preview": [
                                {"name": c.get("procedure_name_zh"), "modality": c.get("modality")}
                                for c in candidates[:10]
                            ]
                        }
                    debug_info["step_6_prompt_length"] = len(prompt)
                    debug_info["step_6_prompt_preview"] = prompt[:500] + "..."

            # 6. 调用LLM进行推理
            if do_debug:
                debug_info["step_6_context"] = {
                    "llm_model": context_llm_model,
                    "embedding_model": context_embedding_model,
                    "reranker_model": context_reranker,
                    "base_url": context_base_url,
                }
            logger.info("调用LLM进行推理...")
            t_llm_start = time.time()
            llm_response = self.call_llm(prompt, context={
                'llm_model': context_llm_model,
                'base_url': context_base_url,
            })
            timings["llm_infer_ms"] = int((time.time() - t_llm_start) * 1000)

            # 7. 解析LLM响应（若LLM不可用则回退到基于RAG候选的确定性结果）
            t_parse_start = time.time()
            parsed_result = self.parse_llm_response(llm_response)
            timings["parse_ms"] = int((time.time() - t_parse_start) * 1000)
            try:
                def _looks_like_llm_down(res: dict) -> bool:
                    recs = (res or {}).get("recommendations") or []
                    if len(recs) == 1 and (recs[0] or {}).get("procedure_name") == "系统暂时无法生成推荐":
                        return True
                    return False
                if _looks_like_llm_down(parsed_result):
                    # 基于已检索到的场景推荐，生成确定性Top-K作为降级结果
                    base = []
                    seen = set()
                    max_k = max(1, int(top_recommendations_per_scenario))
                    for sc in (scenarios_with_recs or []):
                        for rec in sc.get("recommendations", []) or []:
                            name = rec.get("procedure_name_zh") or rec.get("procedure_name_en")
                            if not name or name in seen:
                                continue
                            seen.add(name)
                            ar = rec.get("appropriateness_rating")
                            if isinstance(ar, (int, float)):
                                ar = f"{int(round(float(ar)))}/9"
                            elif isinstance(ar, str) and ar.strip().isdigit():
                                ar = f"{ar.strip()}/9"
                            base.append({
                                "rank": len(base) + 1,
                                "procedure_name": name,
                                "modality": rec.get("modality") or "",
                                "appropriateness_rating": ar or "",
                                "recommendation_reason": rec.get("reasoning_zh") or rec.get("special_considerations") or "",
                                "clinical_considerations": rec.get("contraindications") or "",
                            })
                            if len(base) >= max_k:
                                break
                        if len(base) >= max_k:
                            break
                    if base:
                        parsed_result = {
                            "recommendations": base,
                            "summary": "LLM不可用，已基于RAG检索与知识库生成确定性Top-K推荐"
                        }
                        if do_debug:
                            debug_info["fallback_mode"] = "baseline_from_rag"
            except Exception as _fe:
                logger.warning(f"构建降级结果失败: {_fe}")

            # 若存在候选集合，则对LLM输出做候选内约束（通用、非规则硬编码）
            try:
                if 'candidates' in locals() and candidates:
                    cand_names = set()
                    for c in candidates:
                        nm = c.get('procedure_name_zh') or c.get('name_zh') or c.get('procedure_name')
                        if nm:
                            cand_names.add(nm)
                    recs = (parsed_result or {}).get('recommendations') or []
                    filtered = [r for r in recs if (r.get('procedure_name') in cand_names)]
                    if filtered and (len(filtered) != len(recs)):
                        parsed_result = dict(parsed_result)
                        parsed_result['recommendations'] = filtered
                        if do_debug:
                            debug_info["post_filter_applied"] = {
                                "original_count": len(recs),
                                "filtered_count": len(filtered)
                            }
            except Exception as _pf:
                logger.warning(f"候选集合约束失败（不影响结果）: {_pf}")

            # 规则引擎：post阶段（审计/修订）
            try:
                if self.rules_engine and self.rules_engine.enabled:
                    post_ctx = {
                        "query": query,
                        "query_signals": self._extract_query_signals(query),
                        "scenarios": scenarios,
                    }
                    post_res = self.rules_engine.apply_post(post_ctx, parsed_result)
                    if do_debug:
                        debug_info.setdefault('rules_audit', {})['post'] = post_res.get('audit_logs') or []
                    parsed_result = post_res.get('parsed') or parsed_result
            except Exception as pe:
                logger.warning(f"规则引擎(post)执行失败: {pe}")

            end_time = time.time()
            processing_time = int((end_time - start_time) * 1000)

            if do_debug:
                debug_info["step_7_llm_response_length"] = len(llm_response)
                debug_info["step_8_parsing_success"] = "recommendations" in parsed_result
                debug_info["step_9_total_time_ms"] = processing_time

            # 构建RAGAS上下文（始终包含，用于评测）
            contexts = self._build_ragas_contexts_from_payload({
                "scenarios": scenarios,
                "scenarios_with_recommendations": scenarios_with_recs
            })

            result = {
                "success": True,
                "query": query,
                "scenarios": scenarios,
                "scenarios_with_recommendations": scenarios_with_recs,
                "llm_recommendations": parsed_result,
                "contexts": contexts,  # 新增：始终返回contexts用于RAGAS评测
                "processing_time_ms": processing_time,
                "model_used": context_llm_model,
                "embedding_model_used": context_embedding_model,
                "reranker_model_used": context_reranker,
                "similarity_threshold": current_threshold,
                "max_similarity": max_similarity,
                "is_low_similarity_mode": is_low_similarity,
                "llm_raw_response": llm_response if do_debug else None,
                "debug_info": debug_info if do_debug else None
            }

            # 构建可选的“过程追踪”与RAGAS评估
            if do_debug:
                trace = {}
                def _scenario_text(entry: Dict[str, Any]) -> Optional[str]:
                    return (
                        entry.get("clinical_scenario")
                        or entry.get("description_zh")
                        or entry.get("scenario_description")
                        or entry.get("description")
                    )

                # 原始召回（相似度降序）
                trace["recall_scenarios"] = [
                    {
                        "id": s.get("semantic_id"),
                        "panel": s.get("panel_name"),
                        "topic": s.get("topic_name"),
                        "similarity": s.get("similarity"),
                        "clinical_scenario": _scenario_text(s),
                    } for s in (scenarios_original if 'scenarios_original' in locals() else scenarios)
                ]
                # rerank 后顺序
                trace["rerank_scenarios"] = [
                    {
                        "id": s.get("semantic_id"),
                        "_rerank_score": s.get("_rerank_score"),
                        "panel": s.get("panel_name"),
                        "topic": s.get("topic_name"),
                        "similarity": s.get("similarity"),
                        "clinical_scenario": _scenario_text(s),
                    } for s in scenarios
                ]
                # 完整prompt（注意：可能较长）
                trace["final_prompt"] = prompt
                trace["llm_raw"] = llm_response
                trace["llm_parsed"] = parsed_result
                # 构造RAGAS上下文（与评测器一致）
                contexts = self._build_ragas_contexts_from_payload({
                    "scenarios": scenarios,
                    "scenarios_with_recommendations": scenarios_with_recs
                })
                trace["ragas_contexts_count"] = len(contexts)
                # 可选RAGAS评估
                if compute_ragas:
                    try:
                        t_ragas_start = time.time()
                        ragas_scores = self._compute_ragas_scores(
                            user_input=query,
                            answer=self._format_answer_for_ragas(parsed_result),
                            contexts=contexts,
                            reference=ground_truth
                        )
                        timings["ragas_ms"] = int((time.time() - t_ragas_start) * 1000)
                        trace["ragas_scores"] = ragas_scores
                    except Exception as e:
                        trace["ragas_error"] = str(e)
                # 注入耗时与模型信息
                timings["total_ms"] = processing_time
                trace["timing"] = timings
                trace["models"] = {
                    "llm": context_llm_model,
                    "embedding": context_embedding_model,
                    "reranker": context_reranker,
                    "base_url": context_base_url,
                }
                result["trace"] = trace

            if do_debug:
                logger.info(f"推荐生成完成，总耗时: {processing_time}ms")
                logger.info(f"生成推荐数量: {len(parsed_result.get('recommendations', []))}")
            return result

        except Exception as e:
            logger.error(f"生成智能推荐失败: {e}")
            return {
                "success": False,
                "message": f"生成推荐失败: {str(e)}",
                "error": str(e),
                "debug_info": debug_info if self.debug_mode else None
            }
        finally:
            if 'conn' in locals() and conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def _extract_query_signals(self, query: str) -> Dict[str, Any]:
        """Extract rule-friendly signals from query using configurable patterns.
        Falls back to minimal built-in heuristics if config unavailable.
        """
        try:
            if self._signals_extractor:
                return self._signals_extractor.extract(query)
        except Exception as e:
            logger.warning(f"signals extractor failed, fallback: {e}")
        # Fallback: preserve previous logic with simple negation guard
        q = query or ''
        signals: Dict[str, Any] = {}
        negs = ['非妊娠', '未孕', '否认妊娠', '备孕', '排除妊娠']
        if any(k in q for k in ['孕', '妊娠', '孕妇', '围产', '产后']) and not any(n in q for n in negs):
            signals['pregnancy_status'] = '妊娠/围产'
        kws = []
        for k in ['急诊', '急性', '突发', '雷击样', '霹雳样', 'TCH', 'SAH', '蛛网膜下腔出血']:
            if (k.lower() in q.lower()) or (k in q):
                kws.append(k)
        if kws:
            signals['keywords'] = kws
        return signals

    def _build_ragas_contexts_from_payload(self, payload: Dict[str, Any]) -> List[str]:
        contexts = []
        for sc in payload.get('scenarios_with_recommendations') or []:
            desc = sc.get('scenario_description') or sc.get('description_zh')
            if desc:
                contexts.append(desc)
            for r in (sc.get('recommendations') or []):
                reason = r.get('reasoning_zh')
                if reason:
                    contexts.append(reason)
        for sc in payload.get('scenarios') or []:
            desc = sc.get('description_zh')
            if desc:
                contexts.append(desc)
        return contexts

    def _format_answer_for_ragas(self, parsed: Dict[str, Any]) -> str:
        lines = []
        for r in parsed.get('recommendations') or []:
            name = r.get('procedure_name', '')
            mod = r.get('modality', '')
            rating = r.get('appropriateness_rating', '')
            reason = r.get('recommendation_reason', '')
            t = f"{name} ({mod}) - 评分: {rating}"
            if reason:
                t += f"\n理由: {reason}"
            lines.append(t)
        if parsed.get('summary'):
            lines.append(f"总结: {parsed.get('summary')}")
        return "\n".join(lines) if lines else "无"

    def _compute_ragas_scores(self, user_input: str, answer: str, contexts: List[str], reference: str) -> Dict[str, float]:
        """Compute RAGAS scores.
        Primary path runs in-process. If the runtime is under uvloop and
        ragas/nest_asyncio fails to patch the loop, fall back to an isolated
        subprocess that uses the default asyncio loop policy.
        """
        try:
            # 尝试常规（进程内）评测
            import ragas
            from datasets import Dataset
            # 使用 ragas 0.3.x 的指标导入方式（函数/可调用指标），避免旧版包装器
            from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
            from langchain_openai import ChatOpenAI, OpenAIEmbeddings

            # 使用“评测上下文”中的模型与参数，避免与推理模型混淆
            eval_ctx = dict(self.default_evaluation_context or {})
            api_key = os.getenv("SILICONFLOW_API_KEY") or os.getenv("OPENAI_API_KEY")
            base_url = eval_ctx.get("base_url") or os.getenv("SILICONFLOW_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.siliconflow.cn/v1"
            llm_model = eval_ctx.get("llm_model") or os.getenv("SILICONFLOW_LLM_MODEL", self.llm_model)
            emb_model = eval_ctx.get("embedding_model") or os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3")
            temperature = eval_ctx.get("temperature", 0.1)
            top_p = eval_ctx.get("top_p", 0.7)

            llm = ChatOpenAI(model=llm_model, api_key=api_key, base_url=base_url, temperature=temperature, top_p=top_p)
            emb = OpenAIEmbeddings(model=emb_model, api_key=api_key, base_url=base_url)

            has_ref = bool(reference and str(reference).strip())
            if has_ref:
                data_dict = {
                    "question": [user_input],
                    "answer": [answer],
                    "contexts": [contexts],
                    "ground_truth": [reference],
                }
                metrics = [
                    faithfulness,
                    answer_relevancy,
                    context_precision,
                    context_recall,
                ]
            else:
                # 未提供ground_truth时，计算不依赖参考答案的指标
                data_dict = {
                    "question": [user_input],
                    "answer": [answer],
                    "contexts": [contexts],
                }
                metrics = [
                    faithfulness,
                    answer_relevancy,
                ]

            data = Dataset.from_dict(data_dict)
            res = ragas.evaluate(
                dataset=data,
                metrics=metrics,
                llm=llm,
                embeddings=emb,
            )
            # Normalize possible output formats
            if isinstance(res, dict):
                base = res
            elif hasattr(res, 'scores') and isinstance(res.scores, dict):
                base = res.scores
            else:
                try:
                    base = dict(res)
                except Exception:
                    base = {}
            def clean(v):
                try:
                    f = float(v)
                    if f != f:  # NaN check
                        logger.warning(f"RAGAS评分为NaN: {v}")
                        return float('nan')  # 保留NaN而不是转换为0
                    return f
                except Exception as e:
                    logger.warning(f"RAGAS评分转换失败: {v}, 错误: {e}")
                    return 0.0
            
            logger.info(f"RAGAS原始结果: {base}")
            result = {
                'faithfulness': clean(base.get('faithfulness', 0.0)),
                'answer_relevancy': clean(base.get('answer_relevancy', 0.0)),
                'context_precision': clean(base.get('context_precision', 0.0)),
                'context_recall': clean(base.get('context_recall', 0.0)),
            }
            logger.info(f"RAGAS清理后结果: {result}")
            return result
        except Exception as e:
            # 进程内评测失败的兜底逻辑：
            # 1) uvloop/nest_asyncio 冲突 → 子进程隔离
            # 2) ImportError/No module named → 子进程隔离（避免热加载/路径差异导致的导入问题）
            msg = str(e)
            if isinstance(e, ImportError) or 'No module named' in msg:
                logger.warning(f"RAGAS进程内导入失败，尝试子进程隔离执行: {e}")
                try:
                    return self._compute_ragas_scores_isolated(user_input, answer, contexts, reference)
                except Exception as e2:
                    logger.error(f"RAGAS子进程评测失败: {e2}")
                    raise
            if "Can't patch loop of type <class 'uvloop.Loop'>" in msg or 'nest_asyncio' in msg or 'uvloop' in msg:
                logger.warning(f"RAGAS进程内评测失败，尝试子进程隔离执行: {e}")
                try:
                    return self._compute_ragas_scores_isolated(user_input, answer, contexts, reference)
                except Exception as e2:
                    logger.error(f"RAGAS子进程评测失败: {e2}")
                    # 将错误向上传递，让调用方在 trace 中记录 ragas_error
                    raise
            # 其它异常也上抛，由调用方记录错误
            logger.error(f"RAGAS评测失败: {e}")
            raise

    def _compute_ragas_scores_isolated(self, user_input: str, answer: str, contexts: List[str], reference: str) -> Dict[str, float]:
        """在隔离的子进程中计算RAGAS分数，避免与 uvloop 事件循环冲突。"""
        import json as _json
        import subprocess as _subprocess
        import sys as _sys

        # 使用“评测上下文”模型，避免误用推理模型
        eval_ctx = dict(self.default_evaluation_context or {})
        payload = {
            "user_input": user_input,
            "answer": answer,
            "contexts": contexts,
            "reference": reference,
            # 将评测默认模型也传给子进程以保证一致性（子进程代码如需可读取）
            "llm_model": eval_ctx.get("llm_model") or os.getenv("SILICONFLOW_LLM_MODEL", self.llm_model),
            "embedding_model": eval_ctx.get("embedding_model") or os.getenv("SILICONFLOW_EMBEDDING_MODEL", self.embedding_model),
            "base_url": eval_ctx.get("base_url", self.base_url),
        }
        code = r"""
import os, json, asyncio
# 使用标准事件循环策略，避免 uvloop
try:
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
except Exception:
    pass

cfg = json.loads(os.environ.get('RAGAS_INPUT', '{}'))
user_input = cfg.get('user_input')
answer = cfg.get('answer')
contexts = cfg.get('contexts') or []
reference = cfg.get('reference')

import ragas
from datasets import Dataset
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

api_key = os.getenv('SILICONFLOW_API_KEY')
base_url = os.getenv('SILICONFLOW_BASE_URL', 'https://api.siliconflow.cn/v1')
llm_model = os.getenv('SILICONFLOW_LLM_MODEL', cfg.get('llm_model', 'Qwen/Qwen2.5-32B-Instruct'))
emb_model = os.getenv('SILICONFLOW_EMBEDDING_MODEL', 'BAAI/bge-m3')

llm = ChatOpenAI(model=llm_model, api_key=api_key, base_url=base_url, temperature=0)
emb = OpenAIEmbeddings(model=emb_model, api_key=api_key, base_url=base_url)

has_ref = bool(reference and str(reference).strip())
if has_ref:
    data_dict = {
        'question': [user_input],
        'answer': [answer],
        'contexts': [contexts],
        'ground_truth': [reference],
    }
    metrics = [
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    ]
else:
    data_dict = {
        'question': [user_input],
        'answer': [answer],
        'contexts': [contexts],
    }
    metrics = [
        faithfulness,
        answer_relevancy,
    ]

data = Dataset.from_dict(data_dict)
res = ragas.evaluate(
    dataset=data,
    metrics=metrics,
    llm=llm,
    embeddings=emb,
)
if isinstance(res, dict):
    base = res
elif hasattr(res, 'scores') and isinstance(res.scores, dict):
    base = res.scores
elif hasattr(res, '_scores_dict') and isinstance(res._scores_dict, dict):
    # 使用_scores_dict获取原始评分
    base = {}
    for k, v in res._scores_dict.items():
        if isinstance(v, list) and len(v) > 0:
            base[k] = v[0]  # 取第一个值
        else:
            base[k] = v
else:
    try:
        base = dict(res)
    except Exception:
        base = {}

def clean(v):
    try:
        f = float(v)
        # 检查是否为NaN
        if f != f:  # NaN检查
            return 0.0
        # 检查是否为无穷大
        if f == float('inf') or f == float('-inf'):
            return 0.0
        return f
    except Exception:
        return 0.0

out = {
    'faithfulness': clean(base.get('faithfulness', 0.0)),
    'answer_relevancy': clean(base.get('answer_relevancy', 0.0)),
    'context_precision': clean(base.get('context_precision', 0.0)),
    'context_recall': clean(base.get('context_recall', 0.0)),
}
print(json.dumps(out))
"""
        env = dict(os.environ)
        env["RAGAS_INPUT"] = _json.dumps(payload, ensure_ascii=False)
        # 使用当前 Python 解释器执行子进程
        proc = _subprocess.run([
            _sys.executable, "-c", code
        ], env=env, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            raise RuntimeError(f"ragas subprocess failed: {proc.stderr.strip()}")
        try:
            return _json.loads(proc.stdout.strip())
        except Exception as je:
            raise RuntimeError(f"invalid ragas subprocess output: {je}; raw={proc.stdout[:2000]}")

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
        if not scenarios:
            return scenarios
        # Decide provider
        provider = self.rerank_provider
        base = (reranker_base_url or self.base_url or "").lower()
        is_ollama = ("11434" in base) or ("ollama" in base)
        if provider == "auto":
            provider = "ollama" if is_ollama else "siliconflow"
        if self.use_reranker:
            if provider == "siliconflow":
                try:
                    reranked = self._siliconflow_rerank_scenarios(
                        query,
                        scenarios,
                        scenarios_with_recs,
                        base_url=reranker_base_url,
                        model_id=reranker_model,
                    )
                    if reranked:
                        return reranked
                except Exception as e:
                    logger.warning(f"SiliconFlow reranker failed, will try local/keyword fallback: {e}")
            elif provider == "local" or provider == "ollama":
                # For ollama, we currently use a local transformers cross-encoder as reliable backend
                try:
                    reranked = self._local_rerank_scenarios(
                        query,
                        scenarios,
                        scenarios_with_recs,
                        model_id=(reranker_model or self.reranker_model)
                    )
                    if reranked:
                        return reranked
                except Exception as e:
                    logger.warning(f"Local reranker failed, fallback to keyword rerank: {e}")
        target_panels = target_panels or set()
        target_topics = target_topics or set()
        q = (query or "").lower()
        kw_groups = [[k.lower() for k in grp] for grp in (self.keyword_config.get('keyword_groups_for_bonus', []) or [])]
        # Map scenario_id -> top rating
        top_rating_map = {}
        if scenarios_with_recs:
            for sc in scenarios_with_recs:
                rid = sc.get('scenario_id')
                ratings = [r.get('appropriateness_rating') or 0 for r in (sc.get('recommendations') or [])]
                ratings = [int(r) for r in ratings if r is not None]
                top_rating_map[rid] = max(ratings) if ratings else 0
        def kw_bonus(desc: str) -> float:
            d = (desc or "").lower()
            bonus = 0.0
            for grp in kw_groups:
                if any(k in q for k in grp) and any(k in d for k in grp):
                    bonus += alpha_kw
            return bonus
        rescored = []
        for s in scenarios:
            sim = float(s.get("similarity", 0.0))
            panel = (s.get("panel_name") or "").strip()
            topic = (s.get("topic_name") or "").strip()
            b_panel = alpha_panel if panel in target_panels else 0.0
            b_topic = alpha_topic if topic in target_topics else 0.0
            b_kw = kw_bonus(s.get("description_zh", ""))
            # rating bonus based on top rating in scenario (scaled 0..9)
            sid = s.get('semantic_id')
            top_rt = float(top_rating_map.get(sid, 0.0))
            b_rating = self.rating_boost * (top_rt / 9.0)
            score = sim * (1.0 + b_panel + b_topic + b_kw + b_rating)
            s2 = dict(s)
            s2["_rerank_score"] = score
            rescored.append(s2)
        rescored.sort(key=lambda x: x.get("_rerank_score", 0.0), reverse=True)
        return rescored

    def _load_keyword_config(self) -> dict:
        try:
            path = Path(self.keyword_config_path)
            if path.exists():
                return json.loads(path.read_text(encoding='utf-8'))
        except Exception as e:
            logger.warning(f"加载关键词配置失败: {e}")
        # 默认内置
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

    def _siliconflow_rerank_scenarios(
        self,
        query: str,
        scenarios: List[Dict],
        scenarios_with_recs: Optional[List[Dict]] = None,
        base_url: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> List[Dict]:
        """Use SiliconFlow rerank endpoint with BAAI/bge-reranker-v2-m3.
        Fallback gracefully if the endpoint/model is unavailable.
        """
        api_key = os.getenv("SILICONFLOW_API_KEY") or self.api_key
        base = (base_url or os.getenv("SILICONFLOW_BASE_URL") or "https://api.siliconflow.cn/v1").rstrip("/")
        if not api_key:
            raise RuntimeError("SILICONFLOW_API_KEY not set")
        # Build richer docs: description + top rec names + truncated reasoning
        rec_map = {}
        if scenarios_with_recs:
            for sc in scenarios_with_recs:
                recs = sc.get('recommendations') or []
                parts = []
                for r in recs[:3]:
                    name = r.get('procedure_name_zh') or ''
                    reason = r.get('reasoning_zh') or ''
                    if len(reason) > 160:
                        reason = reason[:160] + '...'
                    parts.append(f"{name}:{reason}")
                rec_map[sc.get('scenario_id')] = " ; ".join(parts)
        docs = []
        for s in scenarios:
            sid = s.get('semantic_id')
            extras = rec_map.get(sid, '')
            txt = " | ".join(filter(None, [s.get('description_zh'), s.get('panel_name'), s.get('topic_name'), extras]))
            docs.append(txt or "")
        payload = {
            "model": model_id or self.reranker_model,
            "query": query,
            "documents": docs,
            "top_n": len(docs)
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        url = f"{base}/rerank"
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        if resp.status_code != 200:
            raise RuntimeError(f"rerank API {resp.status_code}: {resp.text}")
        data = resp.json()
        # Expect data like {"results":[{"index":i,"relevance_score":score}, ...]}
        results = data.get("results") or data.get("data") or []
        if not results:
            return []
        # Map scores back
        scored = []
        for r in results:
            idx = r.get("index") if isinstance(r, dict) else None
            score = r.get("relevance_score") if isinstance(r, dict) else None
            if idx is None or score is None:
                continue
            if 0 <= idx < len(scenarios):
                s2 = dict(scenarios[idx])
                s2["_rerank_score"] = float(score)
                scored.append(s2)
        if not scored:
            return []
        scored.sort(key=lambda x: x.get("_rerank_score", 0.0), reverse=True)
        return scored

    def _local_rerank_scenarios(
        self,
        query: str,
        scenarios: List[Dict],
        scenarios_with_recs: Optional[List[Dict]] = None,
        model_id: Optional[str] = None,
    ) -> List[Dict]:
        """Use local transformers cross-encoder (sentence-transformers) for reranking.
        Default model: BAAI/bge-reranker-v2-m3
        """
        # Prefer sentence-transformers; fallback to pure transformers
        use_st = True
        try:
            from sentence_transformers import CrossEncoder  # type: ignore
        except Exception:
            use_st = False
        # Build docs same as SF path
        rec_map = {}
        if scenarios_with_recs:
            for sc in scenarios_with_recs:
                recs = sc.get('recommendations') or []
                parts = []
                for r in recs[:3]:
                    name = r.get('procedure_name_zh') or ''
                    reason = r.get('reasoning_zh') or ''
                    if len(reason) > 160:
                        reason = reason[:160] + '...'
                    parts.append(f"{name}:{reason}")
                rec_map[sc.get('scenario_id')] = " ; ".join(parts)
        docs = []
        for s in scenarios:
            sid = s.get('semantic_id')
            extras = rec_map.get(sid, '')
            txt = " | ".join(filter(None, [s.get('description_zh'), s.get('panel_name'), s.get('topic_name'), extras]))
            docs.append(txt or "")
        # Map model id if an Ollama-like id specified
        hf_model = model_id or self.reranker_model or "BAAI/bge-reranker-v2-m3"
        if "/" in hf_model and hf_model.lower().startswith("dengcao/"):
            hf_model = "BAAI/bge-reranker-v2-m3"
        # Load and predict
        if use_st:
            ce = CrossEncoder(hf_model)
            pairs = [(query, d) for d in docs]
            scores = ce.predict(pairs)
        else:
            # transformers fallback
            import torch
            from transformers import AutoTokenizer, AutoModelForSequenceClassification  # type: ignore
            tok = AutoTokenizer.from_pretrained(hf_model)
            model = AutoModelForSequenceClassification.from_pretrained(hf_model)
            model.eval()
            scores = []
            for d in docs:
                with torch.no_grad():
                    inputs = tok(query, d, return_tensors='pt', truncation=True, max_length=512)
                    logits = model(**inputs).logits
                    # map to [0,1]
                    s = torch.sigmoid(logits.squeeze())
                    try:
                        scores.append(float(s.item()))
                    except Exception:
                        scores.append(0.0)
        # Map back to scenarios
        scored = []
        for i, s in enumerate(scenarios):
            s2 = dict(s)
            try:
                s2["_rerank_score"] = float(scores[i])
            except Exception:
                s2["_rerank_score"] = 0.0
            scored.append(s2)
        scored.sort(key=lambda x: x.get("_rerank_score", 0.0), reverse=True)
        return scored

# 创建全局服务实例
rag_llm_service = RAGLLMRecommendationService()

# --- Modular override ---
# To enable the new modular implementation while preserving import path
# and class name, we rebind the class and global instance to the facade.
try:
    from app.services.rag.facade import (
        RAGLLMRecommendationService as _ModularRAGLLMRecommendationService,
    )

    RAGLLMRecommendationService = _ModularRAGLLMRecommendationService  # type: ignore
    rag_llm_service = RAGLLMRecommendationService()  # recreate with modular facade
except Exception as _e:  # fallback to legacy class if facade import fails
    pass
