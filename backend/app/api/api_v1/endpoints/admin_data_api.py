from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import subprocess
import time
import os
import re
import json
from app.core.config import settings

router = APIRouter()

# 统一定位到 backend 目录（更稳健的层级）
BACKEND_DIR = Path(__file__).resolve().parents[4]
UPLOAD_DIR = BACKEND_DIR / 'uploads'
SCRIPTS_DIR = BACKEND_DIR / 'scripts'
REGISTRY_PATH = BACKEND_DIR / 'config' / 'models_registry.json'
CONTEXTS_PATH = BACKEND_DIR / 'config' / 'model_contexts.json'
# 内存缓存，避免临时解析失败导致前端看到空白
_REGISTRY_CACHE = None  # type: Optional["ModelsRegistry"]
_CONTEXTS_CACHE = None  # type: Optional[Dict[str, Any]]


class ImportRequest(BaseModel):
    csv_path: Optional[str] = Field(None, description='服务器上的CSV路径（若已上传）')
    mode: str = Field('clear', description='导入模式: clear(清空重建)/add(追加)')
    embedding_model: Optional[str] = Field(None, description='SiliconFlow embedding model id, e.g., BAAI/bge-m3')
    llm_model: Optional[str] = Field(None, description='LLM model id used in service')
    embedding_dim: Optional[int] = Field(None, description='向量维度（如 1024 / 2560）。不传则自动探测或使用默认1024')
    base_url: Optional[str] = Field(None, description='嵌入API Base URL（SiliconFlow或Ollama），例如 https://api.siliconflow.cn/v1 或 http://localhost:11434/v1')


class ImportResponse(BaseModel):
    started: bool
    log_path: Optional[str] = None
    command: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None


class ContextConfig(BaseModel):
    """统一描述一个上下文的模型配置."""

    llm_model: Optional[str] = None
    embedding_model: Optional[str] = None
    reranker_model: Optional[str] = None
    base_url: Optional[str] = None
    # 新增：可配置推理超参（不强制）
    temperature: Optional[float] = None
    top_p: Optional[float] = None


class ScenarioBinding(BaseModel):
    """特定应用场景 (panel/topic/scenario/custom) 的模型覆盖."""

    scope_type: str = Field(..., description='panel/topic/scenario/custom')
    scope_id: str = Field(..., description='与场景绑定的唯一ID')
    scope_label: Optional[str] = Field(None, description='展示名称，便于前端显示')
    inference: Optional[ContextConfig] = Field(None, description='推理阶段覆盖配置')
    evaluation: Optional[ContextConfig] = Field(None, description='评测阶段覆盖配置')


class ModelsConfig(BaseModel):
    embedding_model: Optional[str] = None
    llm_model: Optional[str] = None
    reranker_model: Optional[str] = None
    base_url: Optional[str] = None
    rerank_provider: Optional[str] = None  # auto | siliconflow | local | ollama
    siliconflow_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    # Defaults for RAGAS (optional)
    ragas_llm_model: Optional[str] = None
    ragas_embedding_model: Optional[str] = None

    # 新结构：上下文配置 + 场景覆盖
    contexts: Optional[Dict[str, ContextConfig]] = None
    scenario_overrides: Optional[List[ScenarioBinding]] = None


class ModelEntry(BaseModel):
    id: Optional[str] = None
    label: Optional[str] = None
    provider: str  # e.g., siliconflow, openai, ollama, dashscope
    kind: str      # llm | embedding | reranker
    model: str     # provider-specific model id/name
    base_url: Optional[str] = None
    api_key: Optional[str] = None     # stored but never returned
    api_key_env: Optional[str] = None # preferred over api_key


class ModelsRegistry(BaseModel):
    llms: list[ModelEntry] = []
    embeddings: list[ModelEntry] = []
    rerankers: list[ModelEntry] = []


# —— 系统状态汇总 ——
@router.get('/system/status', summary='系统状态汇总（API/DB/Embedding/LLM/Reranker）')
async def system_status() -> Dict[str, Any]:
    import requests
    import time
    status: Dict[str, Any] = { 'ts': time.time() }

    # API 自身健康
    try:
        status['api'] = { 'status': 'ok', 'service': 'backend' }
    except Exception as e:
        status['api'] = { 'status': 'error', 'error': str(e) }

    # 数据库健康（计数与连接）
    try:
        import psycopg2
        cfg = {
            'host': os.getenv('PGHOST','localhost'),
            'port': int(os.getenv('PGPORT','5432')),
            'database': os.getenv('PGDATABASE','acrac_db'),
            'user': os.getenv('PGUSER','postgres'),
            'password': os.getenv('PGPASSWORD','password'),
        }
        conn = psycopg2.connect(**cfg)
        cur = conn.cursor()
        def cnt(sql: str) -> int:
            cur.execute(sql); return cur.fetchone()[0]
        db = {
            'status': 'ok',
            'tables': {
                'panels': cnt('SELECT COUNT(*) FROM panels'),
                'topics': cnt('SELECT COUNT(*) FROM topics'),
                'clinical_scenarios': cnt('SELECT COUNT(*) FROM clinical_scenarios'),
                'procedure_dictionary': cnt('SELECT COUNT(*) FROM procedure_dictionary'),
                'clinical_recommendations': cnt('SELECT COUNT(*) FROM clinical_recommendations'),
            }
        }
        conn.close()
        status['db'] = db
    except Exception as e:
        status['db'] = { 'status': 'error', 'error': str(e) }

    # 读取推理上下文（模型与base_url）
    try:
        stored = _load_contexts_payload()
        ctx = (stored.get('contexts') or {}).get('inference') or {}
        base_url = os.getenv('SILICONFLOW_BASE_URL') or ctx.get('base_url') or ''
        inf = {
            'llm_model': os.getenv('SILICONFLOW_LLM_MODEL', ctx.get('llm_model', '')),
            'embedding_model': os.getenv('SILICONFLOW_EMBEDDING_MODEL', ctx.get('embedding_model', '')),
            'reranker_model': os.getenv('RERANKER_MODEL', ctx.get('reranker_model', 'BAAI/bge-reranker-v2-m3')),
            'base_url': base_url,
        }
    except Exception:
        inf = {
            'llm_model': os.getenv('SILICONFLOW_LLM_MODEL', ''),
            'embedding_model': os.getenv('SILICONFLOW_EMBEDDING_MODEL', ''),
            'reranker_model': os.getenv('RERANKER_MODEL', ''),
            'base_url': os.getenv('SILICONFLOW_BASE_URL') or '',
        }

    # 仅返回配置信息，不做外部连通性探测（避免阻塞）
    status['embedding'] = { 'status': 'unknown' }
    status['llm'] = { 'status': 'unknown' }
    status['reranker'] = { 'status': 'unknown' }

    return status

@router.get('/validate', summary='数据合规性校验（表计数、向量覆盖、孤儿推荐）')
async def validate_data() -> Dict[str, Any]:
    try:
        import psycopg2
        cfg = {
            'host': os.getenv('PGHOST','localhost'),
            'port': int(os.getenv('PGPORT','5432')),
            'database': os.getenv('PGDATABASE','acrac_db'),
            'user': os.getenv('PGUSER','postgres'),
            'password': os.getenv('PGPASSWORD','password'),
        }
        conn = psycopg2.connect(**cfg)
        cur = conn.cursor()
        def cnt(sql: str) -> int:
            cur.execute(sql);
            return cur.fetchone()[0]
        tables = {
            'panels': cnt('SELECT COUNT(*) FROM panels'),
            'topics': cnt('SELECT COUNT(*) FROM topics'),
            'clinical_scenarios': cnt('SELECT COUNT(*) FROM clinical_scenarios'),
            'procedure_dictionary': cnt('SELECT COUNT(*) FROM procedure_dictionary'),
            'clinical_recommendations': cnt('SELECT COUNT(*) FROM clinical_recommendations'),
        }
        coverage: Dict[str, int] = {}
        for t in ['panels','topics','clinical_scenarios','procedure_dictionary','clinical_recommendations']:
            try:
                cur.execute(f"SELECT COUNT(embedding) FROM {t}")
                coverage[t] = cur.fetchone()[0]
            except Exception:
                coverage[t] = 0
        cur.execute(
            """
            SELECT COUNT(*) FROM clinical_recommendations cr
            WHERE cr.scenario_id NOT IN (SELECT semantic_id FROM clinical_scenarios)
               OR cr.procedure_id NOT IN (SELECT semantic_id FROM procedure_dictionary)
            """
        )
        orphan = cur.fetchone()[0]
        conn.close()
        return { 'tables': tables, 'embedding_coverage': coverage, 'orphan_recommendations': orphan }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/upload', summary='上传CSV文件')
async def upload_csv(file: UploadFile = File(...)) -> Dict[str, Any]:
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime('%Y%m%d_%H%M%S')
        dest = UPLOAD_DIR / f'{ts}_{file.filename}'
        #
						#   streaming 
        with dest.open('wb') as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        return { 'ok': True, 'path': str(dest) }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/import', response_model=ImportResponse, summary='从CSV导入/重建数据（同步执行，可能耗时）')
async def import_csv(req: ImportRequest) -> ImportResponse:
    try:
        # 允许两种来源：SiliconFlow（需API Key）或本地Ollama（/v1/embeddings，无需Key）
        has_sf_key = bool(os.getenv('SILICONFLOW_API_KEY') or settings.SILICONFLOW_API_KEY)
        has_ollama = bool(os.getenv('OLLAMA_BASE_URL'))
        # 请求中显式传入 base_url 也可用作判断
        req_base = (req.base_url or '').lower()
        if not (has_sf_key or has_ollama or ('ollama' in req_base) or ('11434' in req_base)):
            raise HTTPException(status_code=400, detail='缺少嵌入服务配置：请在 .env 设置 SILICONFLOW_API_KEY 或 OLLAMA_BASE_URL，或在本次请求中提供 base_url 为 http://localhost:11434/v1')
        csv_path = req.csv_path
        if not csv_path:
            raise HTTPException(status_code=400, detail='csv_path 必填（先上传或提供服务器绝对路径）')
        csv = Path(csv_path)
        if not csv.exists():
            raise HTTPException(status_code=400, detail='csv_path 不存在')
        log_dir = BACKEND_DIR / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime('%Y%m%d_%H%M%S')
        log_path = log_dir / f'import_{ts}.log'

        # Build command
        script = SCRIPTS_DIR / 'build_acrac_from_csv_siliconflow.py'
        if not script.exists():
            raise HTTPException(status_code=500, detail='构建脚本不存在')
        action = 'build'
        args = [ 'python', str(script), action, '--csv-file', str(csv) ]
        # clear: create schema; add: skip schema
        if req.mode == 'add':
            args.append('--skip-schema')
        # env overrides
        env = os.environ.copy()
        if req.embedding_model:
            env['SILICONFLOW_EMBEDDING_MODEL'] = req.embedding_model
        if req.llm_model:
            env['SILICONFLOW_LLM_MODEL'] = req.llm_model
        if req.embedding_dim:
            env['EMBEDDING_DIM'] = str(req.embedding_dim)
        if req.base_url:
            env['SILICONFLOW_BASE_URL'] = req.base_url
            env['OLLAMA_BASE_URL'] = req.base_url
        # 兜底：如选择 Ollama 模型但未切换 Base URL，提前报错
        if req.embedding_model and ('qwen' in req.embedding_model.lower() or 'ollama' in req.embedding_model.lower()):
            base = (req.base_url or os.getenv('SILICONFLOW_BASE_URL') or '').lower()
            if not base or ('siliconflow' in base and '11434' not in base and 'ollama' not in base):
                raise HTTPException(status_code=400, detail='检测到选择了 Ollama 嵌入模型，但 Base URL 仍指向 SiliconFlow。请设置为 http://host.docker.internal:11434/v1 或宿主机 Ollama 地址。')

        with log_path.open('wb') as logf:
            proc = subprocess.Popen(args, stdout=logf, stderr=logf, env=env, cwd=str(SCRIPTS_DIR))
            proc.wait()
        # Quick compliance metrics
        metrics: Dict[str, Any] = {}
        try:
            import psycopg2
            cfg = {
                'host': os.getenv('PGHOST','localhost'),
                'port': int(os.getenv('PGPORT','5432')),
                'database': os.getenv('PGDATABASE','acrac_db'),
                'user': os.getenv('PGUSER','postgres'),
                'password': os.getenv('PGPASSWORD','password'),
            }
            conn = psycopg2.connect(**cfg)
            cur = conn.cursor()
            def cnt(sql):
                cur.execute(sql)
                return cur.fetchone()[0]
            metrics['tables'] = {
                'panels': cnt('SELECT COUNT(*) FROM panels'),
                'topics': cnt('SELECT COUNT(*) FROM topics'),
                'clinical_scenarios': cnt('SELECT COUNT(*) FROM clinical_scenarios'),
                'procedure_dictionary': cnt('SELECT COUNT(*) FROM procedure_dictionary'),
                'clinical_recommendations': cnt('SELECT COUNT(*) FROM clinical_recommendations'),
            }
            cov = {}
            for t in ['panels','topics','clinical_scenarios','procedure_dictionary','clinical_recommendations']:
                try:
                    cur.execute(f"SELECT COUNT(embedding) FROM {t}")
                    cov[t] = cur.fetchone()[0]
                except Exception:
                    cov[t] = 0
            metrics['embedding_coverage'] = cov
            cur.execute(
                """
                SELECT COUNT(*) FROM clinical_recommendations cr
                WHERE cr.scenario_id NOT IN (SELECT semantic_id FROM clinical_scenarios)
                   OR cr.procedure_id NOT IN (SELECT semantic_id FROM procedure_dictionary)
                """
            )
            metrics['orphan_recommendations'] = cur.fetchone()[0]
            conn.close()
        except Exception:
            metrics = {}
        return ImportResponse(started=True, log_path=str(log_path), command=' '.join(args), metrics=metrics)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# —— 模型配置 ——
@router.get('/models/config', summary='查看模型配置（当前进程/env）')
async def get_models_config() -> Dict[str, Any]:
    def has(k: str) -> bool:
        return bool(os.getenv(k))
    stored = _load_contexts_payload()
    stored_contexts = stored.get('contexts') or {}
    scenario_overrides = stored.get('scenario_overrides') or []

    inference_defaults = stored_contexts.get('inference') or {}
    evaluation_defaults = stored_contexts.get('evaluation') or {}

    def _default_base_for_model(model: str) -> str:
        if model and ':' in str(model):
            # 形如 qwen2.5:32b -> 优先 Ollama
            return os.getenv('OLLAMA_BASE_URL') or os.getenv('SILICONFLOW_BASE_URL') or settings.SILICONFLOW_BASE_URL
        return os.getenv('SILICONFLOW_BASE_URL') or settings.SILICONFLOW_BASE_URL

    # Inference context（优先展示“已保存的上下文”，缺失时再回退到进程 env）
    inf_llm = inference_defaults.get('llm_model') or os.getenv('SILICONFLOW_LLM_MODEL', '')
    inf_emb = inference_defaults.get('embedding_model') or os.getenv('SILICONFLOW_EMBEDDING_MODEL', '')
    # base_url 优先使用保存的；若未保存且推断为 Ollama 模型（含冒号），优先 OLLAMA_BASE_URL；否则回退 SiliconFlow
    if inference_defaults.get('base_url'):
        inf_base = inference_defaults['base_url']
    else:
        if inf_llm and ':' in str(inf_llm) and os.getenv('OLLAMA_BASE_URL'):
            inf_base = os.getenv('OLLAMA_BASE_URL')
        else:
            inf_base = os.getenv('SILICONFLOW_BASE_URL') or _default_base_for_model(inf_llm)
    inference_ctx = {
        'llm_model': inf_llm,
        'embedding_model': inf_emb,
        'reranker_model': inference_defaults.get('reranker_model') or os.getenv('RERANKER_MODEL', 'BAAI/bge-reranker-v2-m3'),
        'base_url': inf_base,
        'temperature': inference_defaults.get('temperature'),
        'top_p': inference_defaults.get('top_p'),
    }

    # Evaluation (RAGAS) context（同样优先使用保存的上下文）
    eva_llm = evaluation_defaults.get('llm_model') or os.getenv('RAGAS_DEFAULT_LLM_MODEL') or inference_ctx['llm_model']
    eva_emb = evaluation_defaults.get('embedding_model') or os.getenv('RAGAS_DEFAULT_EMBEDDING_MODEL') or inference_ctx['embedding_model']
    if evaluation_defaults.get('base_url'):
        eva_base = evaluation_defaults['base_url']
    elif os.getenv('RAGAS_DEFAULT_BASE_URL'):
        eva_base = os.getenv('RAGAS_DEFAULT_BASE_URL')
    elif eva_llm and ':' in str(eva_llm) and os.getenv('OLLAMA_BASE_URL'):
        eva_base = os.getenv('OLLAMA_BASE_URL')
    else:
        eva_base = _default_base_for_model(eva_llm)
    evaluation_ctx = {
        'llm_model': eva_llm,
        'embedding_model': eva_emb,
        'reranker_model': evaluation_defaults.get('reranker_model') or os.getenv('RAGAS_DEFAULT_RERANKER_MODEL'),
        'base_url': eva_base,
        'temperature': evaluation_defaults.get('temperature'),
        'top_p': evaluation_defaults.get('top_p'),
    }

    contexts: Dict[str, Any] = {}
    for name, ctx in stored_contexts.items():
        if name not in ('inference', 'evaluation') and isinstance(ctx, dict):
            contexts[name] = ctx
    contexts['inference'] = inference_ctx
    contexts['evaluation'] = evaluation_ctx

    return {
        # 兼容旧字段
        'embedding_model': inference_ctx['embedding_model'],
        'llm_model': inference_ctx['llm_model'],
        'reranker_model': inference_ctx['reranker_model'],
        'base_url': inference_ctx['base_url'],
        'rerank_provider': os.getenv('RERANK_PROVIDER', 'auto'),
        'keys': {
            'siliconflow_api_key': has('SILICONFLOW_API_KEY'),
            'openai_api_key': has('OPENAI_API_KEY'),
        },
        'providers': ['siliconflow', 'openai', 'local'],
        'ragas_defaults': {
            'llm_model': evaluation_ctx['llm_model'],
            'embedding_model': evaluation_ctx['embedding_model'],
        },
        'contexts': contexts,
        'scenario_overrides': scenario_overrides,
    }


@router.get('/models/check', summary='连通性自检（LLM/Embedding/Reranker）')
async def check_models_connectivity(context: Optional[str] = None) -> Dict[str, Any]:
    """对当前配置进行实时连通性检查，不泄露密钥。
    - LLM：调用 chat.completions 简单对话
    - Embedding：调用 SiliconFlow embeddings 接口
    - Reranker：调用 SiliconFlow /rerank 接口（可选）
    """
    import time
    import requests
    import openai
    from app.services.rag_llm_recommendation_service import embed_with_siliconflow

    api_key = os.getenv('SILICONFLOW_API_KEY') or settings.SILICONFLOW_API_KEY
    stored = _load_contexts_payload()
    stored_contexts = stored.get('contexts') or {}

    ctx_name = (context or '').strip().lower()
    # Map common aliases
    if ctx_name in ('evaluation', 'ragas'):
        llm_model = os.getenv('RAGAS_DEFAULT_LLM_MODEL') or stored_contexts.get('evaluation', {}).get('llm_model') or os.getenv('SILICONFLOW_LLM_MODEL') or settings.SILICONFLOW_LLM_MODEL
        emb_model = os.getenv('RAGAS_DEFAULT_EMBEDDING_MODEL') or stored_contexts.get('evaluation', {}).get('embedding_model') or os.getenv('SILICONFLOW_EMBEDDING_MODEL', 'BAAI/bge-m3')
        reranker_model = os.getenv('RAGAS_DEFAULT_RERANKER_MODEL') or stored_contexts.get('evaluation', {}).get('reranker_model') or os.getenv('RERANKER_MODEL', 'BAAI/bge-reranker-v2-m3')
        # 若模型名称疑似 Ollama，则优先使用 OLLAMA_BASE_URL
        prefer_ollama = (llm_model and ':' in str(llm_model))
        if prefer_ollama and os.getenv('OLLAMA_BASE_URL'):
            base_url = os.getenv('OLLAMA_BASE_URL')
        else:
            base_url = os.getenv('RAGAS_DEFAULT_BASE_URL') or stored_contexts.get('evaluation', {}).get('base_url') or os.getenv('SILICONFLOW_BASE_URL') or settings.SILICONFLOW_BASE_URL
    elif ctx_name and ctx_name in stored_contexts:
        c = stored_contexts.get(ctx_name) or {}
        llm_model = c.get('llm_model') or os.getenv('SILICONFLOW_LLM_MODEL') or settings.SILICONFLOW_LLM_MODEL
        emb_model = c.get('embedding_model') or os.getenv('SILICONFLOW_EMBEDDING_MODEL', 'BAAI/bge-m3')
        reranker_model = c.get('reranker_model') or os.getenv('RERANKER_MODEL', 'BAAI/bge-reranker-v2-m3')
        base_url = c.get('base_url') or os.getenv('SILICONFLOW_BASE_URL') or settings.SILICONFLOW_BASE_URL
    else:
        llm_model = os.getenv('SILICONFLOW_LLM_MODEL') or settings.SILICONFLOW_LLM_MODEL
        emb_model = os.getenv('SILICONFLOW_EMBEDDING_MODEL', 'BAAI/bge-m3')
        reranker_model = os.getenv('RERANKER_MODEL', 'BAAI/bge-reranker-v2-m3')
        base_url = os.getenv('SILICONFLOW_BASE_URL') or settings.SILICONFLOW_BASE_URL

    out: Dict[str, Any] = {
        'env': {
            'has_api_key': bool(api_key),
            'base_url': base_url,
            'llm_model': llm_model,
            'embedding_model': emb_model,
            'reranker_model': reranker_model,
        }
    }

    # LLM check
    try:
        t0 = time.time()
        # Ollama 端点通常不需要有效 key
        api_key_llm = api_key
        if base_url and (('11434' in base_url) or ('ollama' in base_url.lower())):
            api_key_llm = os.getenv('OLLAMA_API_KEY') or 'ollama'
        client = openai.OpenAI(api_key=api_key_llm, base_url=base_url) if base_url else openai.OpenAI(api_key=api_key_llm)
        resp = client.chat.completions.create(
            model=llm_model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
            temperature=0
        )
        dt = int((time.time() - t0) * 1000)
        ok = bool(resp.choices and resp.choices[0].message)
        out['llm'] = {'status': 'ok' if ok else 'warning', 'latency_ms': dt, 'model': llm_model, 'context': context or 'rag_llm'}
    except Exception as e:
        out['llm'] = {'status': 'error', 'error': str(e), 'model': llm_model, 'context': context or 'rag_llm'}

    # Embedding check
    try:
        vec = embed_with_siliconflow('ping', api_key=api_key, model=emb_model, base_url=base_url)
        dim = len(vec) if isinstance(vec, list) else 0
        ok = dim >= 128  # 宽松判定
        out['embedding'] = {'status': 'ok' if ok else 'warning', 'model': emb_model, 'dimension': dim, 'context': context or 'rag_llm'}
    except Exception as e:
        out['embedding'] = {'status': 'error', 'error': str(e), 'model': emb_model, 'context': context or 'rag_llm'}

    # Reranker check（SiliconFlow 或本地 CrossEncoder）
    try:
        if base_url and (('11434' in base_url) or ('ollama' in base_url.lower())):
            # 尝试本地 CrossEncoder（优先 sentence-transformers，其次 transformers）
            test_model = reranker_model or 'BAAI/bge-reranker-v2-m3'
            if '/' in test_model and test_model.lower().startswith('dengcao/'):
                test_model = 'BAAI/bge-reranker-v2-m3'
            try:
                try:
                    from sentence_transformers import CrossEncoder  # type: ignore
                    ce = CrossEncoder(test_model)
                    _ = ce.predict([('headache', 'sudden thunderclap headache'), ('headache', 'mild chronic dull headache')])
                    out['reranker'] = {'status': 'ok', 'model': reranker_model or 'BAAI/bge-reranker-v2-m3', 'provider': 'local-st'}
                except Exception:
                    import torch
                    from transformers import AutoTokenizer, AutoModelForSequenceClassification  # type: ignore
                    tok = AutoTokenizer.from_pretrained(test_model)
                    model = AutoModelForSequenceClassification.from_pretrained(test_model)
                    model.eval()
                    with torch.no_grad():
                        inputs = tok('headache', 'sudden thunderclap headache', return_tensors='pt', truncation=True, max_length=512)
                        logits = model(**inputs).logits
                        _ = float(torch.sigmoid(logits.squeeze()).item())
                    out['reranker'] = {'status': 'ok', 'model': reranker_model or 'BAAI/bge-reranker-v2-m3', 'provider': 'local-hf'}
            except Exception as ee:
                out['reranker'] = {'status': 'warning', 'model': reranker_model, 'error': f'local rerank unavailable: {ee}'}
        elif api_key and base_url:
            url = f"{base_url.rstrip('/')}/rerank"
            payload = {
                'model': reranker_model,
                'query': 'headache',
                'documents': ['sudden thunderclap headache', 'chronic dull headache'],
                'top_n': 2
            }
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            r = requests.post(url, json=payload, headers=headers, timeout=30)
            ok = r.status_code == 200 and ('results' in r.json() or 'data' in r.json())
            out['reranker'] = {'status': 'ok' if ok else 'warning', 'model': reranker_model, 'http_status': r.status_code}
        else:
            out['reranker'] = {'status': 'warning', 'model': reranker_model, 'error': 'no api/base_url'}
    except Exception as e:
        out['reranker'] = {'status': 'error', 'model': reranker_model, 'error': str(e)}

    return out


def _update_env(text: str, key: str, value: Optional[str]) -> str:
    pattern = re.compile(rf'^{re.escape(key)}\s*=.*$', re.M)
    if value is None:
        return pattern.sub('', text)
    line = f'{key}={value}'
    if pattern.search(text):
        return pattern.sub(line, text)
    if not text.endswith('\n'):
        text += '\n'
    return text + line + '\n'


def _load_registry() -> ModelsRegistry:
    """加载模型库；如文件缺失或解析失败，回退到内存缓存。"""
    global _REGISTRY_CACHE
    if not REGISTRY_PATH.exists():
        return _REGISTRY_CACHE or ModelsRegistry()
    try:
        import json
        data = json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
        reg = ModelsRegistry(**data)
        _REGISTRY_CACHE = reg
        return reg
    except Exception:
        return _REGISTRY_CACHE or ModelsRegistry()


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + '.tmp')
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(text, encoding='utf-8')
    tmp.replace(path)


def _save_registry(reg: ModelsRegistry):
    import json
    global _REGISTRY_CACHE
    _atomic_write(REGISTRY_PATH, json.dumps(reg.model_dump(), ensure_ascii=False, indent=2))
    _REGISTRY_CACHE = reg


def _load_contexts_payload() -> Dict[str, Any]:
    """加载上下文配置；解析失败时使用内存缓存。"""
    global _CONTEXTS_CACHE
    if not CONTEXTS_PATH.exists():
        return {'contexts': {}, 'scenario_overrides': []}
    try:
        data = json.loads(CONTEXTS_PATH.read_text(encoding='utf-8'))
        _CONTEXTS_CACHE = data
        return data
    except Exception:
        return _CONTEXTS_CACHE or {'contexts': {}, 'scenario_overrides': []}


def _save_contexts_payload(payload: Dict[str, Any]) -> None:
    global _CONTEXTS_CACHE
    _CONTEXTS_CACHE = payload
    _atomic_write(CONTEXTS_PATH, json.dumps(payload, ensure_ascii=False, indent=2))


def _validate_base_url(url: str) -> None:
    """严格校验 Provider base_url：
    - 必须是 http/https
    - 路径以 /v1 结尾（OpenAI 兼容规范）
    - 基本连通性：GET <base_url>/models 返回 200/401/403 之一
    校验失败直接抛 400，阻止保存无效配置。
    """
    from urllib.parse import urlparse
    import requests
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise HTTPException(status_code=400, detail="base_url 必须以 http/https 开头且为有效 URL")
    if not p.path.rstrip('/').endswith('/v1'):
        raise HTTPException(status_code=400, detail="base_url 必须包含 /v1 路径，如 https://api.siliconflow.cn/v1 或 http://localhost:11434/v1")
    try:
        resp = requests.get(url.rstrip('/') + '/models', timeout=5)
        if resp.status_code not in (200, 401, 403):
            raise HTTPException(status_code=400, detail=f"base_url 连接成功但不兼容（/models 返回 HTTP {resp.status_code}）")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"base_url 不可达：{e}")


@router.post('/models/config', summary='更新模型配置（写入.env并设置当前进程env）')
async def set_models_config(cfg: ModelsConfig) -> Dict[str, Any]:
    try:
        incoming_contexts: Dict[str, Dict[str, Any]] = {}
        if cfg.contexts:
            for name, ctx in cfg.contexts.items():
                if isinstance(ctx, ContextConfig):
                    incoming_contexts[name] = ctx.model_dump(exclude_none=True)
                elif isinstance(ctx, dict):
                    incoming_contexts[name] = {k: v for k, v in ctx.items() if v is not None}

        # 兼容旧字段写入 inference/evaluation
        inf_ctx = dict(incoming_contexts.get('inference', {}))
        eval_ctx = dict(incoming_contexts.get('evaluation', {}))

        if cfg.embedding_model is not None:
            inf_ctx['embedding_model'] = cfg.embedding_model
        if cfg.llm_model is not None:
            inf_ctx['llm_model'] = cfg.llm_model
        if cfg.reranker_model is not None:
            inf_ctx['reranker_model'] = cfg.reranker_model
        if cfg.base_url is not None:
            inf_ctx['base_url'] = cfg.base_url

        if cfg.ragas_llm_model is not None:
            eval_ctx['llm_model'] = cfg.ragas_llm_model
        if cfg.ragas_embedding_model is not None:
            eval_ctx['embedding_model'] = cfg.ragas_embedding_model

        # 源头校验：若提供 base_url，保存前强制连通性检查
        if inf_ctx.get('base_url'):
            _validate_base_url(inf_ctx['base_url'])
        if eval_ctx.get('base_url'):
            _validate_base_url(eval_ctx['base_url'])

        contexts_to_store: Dict[str, Dict[str, Any]] = dict(incoming_contexts)
        if inf_ctx:
            contexts_to_store['inference'] = inf_ctx
        if eval_ctx:
            contexts_to_store['evaluation'] = eval_ctx

        current_payload = _load_contexts_payload()
        stored_contexts = current_payload.get('contexts') or {}
        stored_overrides = current_payload.get('scenario_overrides') or []

        updated_contexts = dict(stored_contexts)
        for name, ctx in contexts_to_store.items():
            updated_contexts[name] = ctx

        if cfg.scenario_overrides is not None:
            overrides_payload = [item.model_dump(exclude_none=True) for item in cfg.scenario_overrides]
        else:
            overrides_payload = stored_overrides

        # 更新进程环境变量
        inference_for_env = updated_contexts.get('inference', {})
        evaluation_for_env = updated_contexts.get('evaluation', {})

        if 'embedding_model' in inference_for_env:
            os.environ['SILICONFLOW_EMBEDDING_MODEL'] = inference_for_env.get('embedding_model', '')
        if 'llm_model' in inference_for_env:
            os.environ['SILICONFLOW_LLM_MODEL'] = inference_for_env.get('llm_model', '')
        if 'reranker_model' in inference_for_env:
            os.environ['RERANKER_MODEL'] = inference_for_env.get('reranker_model', '')
        if 'base_url' in inference_for_env:
            os.environ['SILICONFLOW_BASE_URL'] = inference_for_env.get('base_url', '')

        if 'llm_model' in evaluation_for_env:
            os.environ['RAGAS_DEFAULT_LLM_MODEL'] = evaluation_for_env.get('llm_model', '')
        if 'embedding_model' in evaluation_for_env:
            os.environ['RAGAS_DEFAULT_EMBEDDING_MODEL'] = evaluation_for_env.get('embedding_model', '')
        if 'base_url' in evaluation_for_env:
            os.environ['RAGAS_DEFAULT_BASE_URL'] = evaluation_for_env.get('base_url', '')
        if 'reranker_model' in evaluation_for_env:
            os.environ['RAGAS_DEFAULT_RERANKER_MODEL'] = evaluation_for_env.get('reranker_model', '')

        if cfg.siliconflow_api_key is not None:
            os.environ['SILICONFLOW_API_KEY'] = cfg.siliconflow_api_key
        if cfg.openai_api_key is not None:
            os.environ['OPENAI_API_KEY'] = cfg.openai_api_key
        if cfg.rerank_provider is not None:
            os.environ['RERANK_PROVIDER'] = cfg.rerank_provider

        # 在Docker环境中不写 .env（通过 env_file 注入），仅写入 JSON 并更新进程环境
        skip_env_write = (os.getenv('DOCKER_CONTEXT','').lower() in ('1','true','yes')) or (os.getenv('SKIP_LOCAL_DOTENV','').lower() in ('1','true','yes'))
        env_path = BACKEND_DIR / '.env'
        text = env_path.read_text(encoding='utf-8') if (env_path.exists() and not skip_env_write) else ''
        env_updates: List[Tuple[str, Optional[str]]] = []
        if 'embedding_model' in inference_for_env:
            env_updates.append(('SILICONFLOW_EMBEDDING_MODEL', inference_for_env.get('embedding_model')))
        if 'llm_model' in inference_for_env:
            env_updates.append(('SILICONFLOW_LLM_MODEL', inference_for_env.get('llm_model')))
        if 'reranker_model' in inference_for_env:
            env_updates.append(('RERANKER_MODEL', inference_for_env.get('reranker_model')))
        if 'base_url' in inference_for_env:
            env_updates.append(('SILICONFLOW_BASE_URL', inference_for_env.get('base_url')))
        if 'llm_model' in evaluation_for_env:
            env_updates.append(('RAGAS_DEFAULT_LLM_MODEL', evaluation_for_env.get('llm_model')))
        if 'embedding_model' in evaluation_for_env:
            env_updates.append(('RAGAS_DEFAULT_EMBEDDING_MODEL', evaluation_for_env.get('embedding_model')))
        if 'base_url' in evaluation_for_env:
            env_updates.append(('RAGAS_DEFAULT_BASE_URL', evaluation_for_env.get('base_url')))
        if 'reranker_model' in evaluation_for_env:
            env_updates.append(('RAGAS_DEFAULT_RERANKER_MODEL', evaluation_for_env.get('reranker_model')))
        if cfg.siliconflow_api_key is not None:
            env_updates.append(('SILICONFLOW_API_KEY', cfg.siliconflow_api_key))
        if cfg.openai_api_key is not None:
            env_updates.append(('OPENAI_API_KEY', cfg.openai_api_key))
        if cfg.rerank_provider is not None:
            env_updates.append(('RERANK_PROVIDER', cfg.rerank_provider))
        if not skip_env_write:
            for key, value in env_updates:
                text = _update_env(text, key, value)
            env_path.write_text(text, encoding='utf-8')

        _save_contexts_payload({
            'contexts': updated_contexts,
            'scenario_overrides': overrides_payload,
        })
        return {'ok': True, 'requires_restart': True, 'env_file_updated': (not skip_env_write)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/models/reload', summary='重载RAG+LLM服务实例（应用部分配置）')
async def reload_rag_service() -> Dict[str, Any]:
    try:
        from app.services.rag_llm_recommendation_service import RAGLLMRecommendationService
        from app.services import rag_llm_recommendation_service as mod
        mod.rag_llm_service = RAGLLMRecommendationService()
        return {'ok': True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/models/registry', summary='获取模型库')
async def get_models_registry() -> Dict[str, Any]:
    reg = _load_registry()
    # 若注册表为空，尝试基于环境变量提供一次性“建议项”，避免冷启动后前端下拉无选项
    if not (reg.llms or reg.embeddings or reg.rerankers):
        suggest_llms: list[ModelEntry] = []
        suggest_embs: list[ModelEntry] = []
        # LLM: 优先 evaluation/inference 默认，再回退 SiliconFlow 默认
        llm_model = os.getenv('RAGAS_DEFAULT_LLM_MODEL') or os.getenv('SILICONFLOW_LLM_MODEL') or ''
        base_llm = None
        if llm_model:
            if ':' in llm_model and (os.getenv('OLLAMA_BASE_URL')):
                base_llm = os.getenv('OLLAMA_BASE_URL')
                suggest_llms.append(ModelEntry(
                    id=f"ollama-llm-{llm_model.replace('/','_').replace(':','_')}",
                    label=llm_model,
                    provider='ollama', kind='llm', model=llm_model, base_url=base_llm,
                    api_key_env=None
                ))
            else:
                base_llm = os.getenv('SILICONFLOW_BASE_URL', settings.SILICONFLOW_BASE_URL)
                suggest_llms.append(ModelEntry(
                    id=f"siliconflow-llm-{llm_model.replace('/','_').replace(':','_')}",
                    label=llm_model,
                    provider='siliconflow', kind='llm', model=llm_model, base_url=base_llm,
                    api_key_env='SILICONFLOW_API_KEY'
                ))

        # Embedding
        emb_model = os.getenv('RAGAS_DEFAULT_EMBEDDING_MODEL') or os.getenv('SILICONFLOW_EMBEDDING_MODEL') or ''
        base_emb = None
        if emb_model:
            if ':' in emb_model and (os.getenv('OLLAMA_BASE_URL')):
                base_emb = os.getenv('OLLAMA_BASE_URL')
                suggest_embs.append(ModelEntry(
                    id=f"ollama-embedding-{emb_model.replace('/','_').replace(':','_')}",
                    label=emb_model,
                    provider='ollama', kind='embedding', model=emb_model, base_url=base_emb,
                    api_key_env=None
                ))
            else:
                base_emb = os.getenv('SILICONFLOW_BASE_URL', settings.SILICONFLOW_BASE_URL)
                suggest_embs.append(ModelEntry(
                    id=f"siliconflow-embedding-{emb_model.replace('/','_').replace(':','_')}",
                    label=emb_model,
                    provider='siliconflow', kind='embedding', model=emb_model, base_url=base_emb,
                    api_key_env='SILICONFLOW_API_KEY'
                ))

        # 仅在完全为空时提供建议项（不落盘）
        reg = ModelsRegistry(llms=suggest_llms, embeddings=suggest_embs, rerankers=[])
    # redact api_key
    def redact(items: list[ModelEntry]):
        out = []
        for it in items:
            d = it.model_dump()
            if 'api_key' in d:
                d['has_api_key'] = bool(d.get('api_key'))
                d.pop('api_key', None)
            out.append(d)
        return out
    return {
        'llms': redact(reg.llms),
        'embeddings': redact(reg.embeddings),
        'rerankers': redact(reg.rerankers),
    }


@router.post('/models/registry', summary='覆盖模型库（含密钥，慎用）')
async def set_models_registry(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        # 允许缺少 id/label，服务端自动生成
        reg = ModelsRegistry(**payload)
        def ensure_id(items: list[ModelEntry]):
            for it in items:
                if not it.id or not str(it.id).strip():
                    base = f"{it.provider}-{it.kind}-{it.model}".replace('/', '_').replace(':', '_')
                    it.id = base
                if not it.label or not str(it.label).strip():
                    it.label = it.model
        ensure_id(reg.llms)
        ensure_id(reg.embeddings)
        ensure_id(reg.rerankers)
        _save_registry(reg)
        return {'ok': True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'无效模型库: {e}')


@router.post('/models/check-model', summary='检查单个模型的连通性')
async def check_single_model(entry: ModelEntry) -> Dict[str, Any]:
    import time
    import requests
    import openai
    import re
    # resolve key
    api_key = entry.api_key
    if (not api_key) and entry.api_key_env:
        api_key = os.getenv(entry.api_key_env)
    if (not api_key) and entry.provider.lower() == 'siliconflow':
        api_key = os.getenv('SILICONFLOW_API_KEY')
    if (not api_key) and entry.provider.lower() == 'openai':
        api_key = os.getenv('OPENAI_API_KEY')
    if (not api_key) and entry.provider.lower() == 'dashscope':
        api_key = os.getenv('DASHSCOPE_API_KEY')
    if (not api_key) and entry.provider.lower() == 'ollama':
        # Ollama 的 OpenAI 兼容端点通常不校验key，但SDK需要一个占位符
        api_key = os.getenv('OLLAMA_API_KEY') or 'ollama'
    prov = (entry.provider or '').lower()
    # Provider 默认 base_url
    default_base = None
    if prov == 'siliconflow':
        default_base = os.getenv('SILICONFLOW_BASE_URL', 'https://api.siliconflow.cn/v1')
    elif prov == 'openai':
        default_base = os.getenv('OPENAI_BASE_URL')
    elif prov == 'ollama':
        # Ollama OpenAI 兼容端点（>=0.3）
        default_base = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434/v1')
    elif prov == 'dashscope':
        # 阿里云达摩院 DashScope 兼容端点
        default_base = os.getenv('DASHSCOPE_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
    base_url = entry.base_url or default_base
    # 规范化 Ollama base_url：去掉多余的 /rerank，确保以 /v1 结尾
    if prov == 'ollama':
        if base_url:
            # 去除尾部 /rerank
            base_url = re.sub(r"/+rerank/?$", "", base_url.rstrip('/'))
        if not base_url:
            base_url = 'http://localhost:11434/v1'
        if not re.search(r"/v1/?$", base_url):
            base_url = base_url.rstrip('/') + '/v1'
    out: Dict[str, Any] = {'kind': entry.kind, 'model': entry.model, 'provider': entry.provider, 'base_url': base_url}
    try:
        if entry.kind == 'llm':
            t0 = time.time()
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            resp = client.chat.completions.create(
                model=entry.model,
                messages=[{"role":"user","content":"ping"}],
                max_tokens=5, temperature=0
            )
            dt = int((time.time()-t0)*1000)
            ok = bool(resp.choices and resp.choices[0].message)
            out.update({'status': 'ok' if ok else 'warning', 'latency_ms': dt})
        elif entry.kind == 'embedding':
            url = f"{(base_url or '').rstrip('/')}/embeddings"
            headers = {"Content-Type":"application/json"}
            if api_key and not (base_url and (('11434' in base_url) or ('ollama' in base_url.lower()))):
                headers["Authorization"] = f"Bearer {api_key}"
            r = requests.post(url, json={'model': entry.model, 'input': 'ping'}, headers=headers, timeout=30)
            ok = r.status_code == 200 and isinstance(r.json().get('data'), list)
            dim = len((r.json().get('data') or [{}])[0].get('embedding') or []) if ok else 0
            out.update({'status': 'ok' if ok else 'warning', 'http_status': r.status_code, 'dimension': dim})
        elif entry.kind == 'reranker':
            # 确保以 /v1/rerank 访问
            url = f"{(base_url or '').rstrip('/')}/rerank"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type":"application/json"}
            r = requests.post(url, json={'model': entry.model, 'query': 'headache', 'documents': ['doc1','doc2'], 'top_n': 2}, headers=headers, timeout=30)
            ok = r.status_code == 200 and ('results' in r.json() or 'data' in r.json())
            out.update({'status': 'ok' if ok else 'warning', 'http_status': r.status_code})
        else:
            out.update({'status': 'error', 'error': f'未知模型类型: {entry.kind}'})
    except Exception as e:
        out.update({'status': 'error', 'error': str(e)})
    return out


@router.post('/models/registry/{kind}', summary='新增模型条目（单条）')
async def add_model_entry(kind: str, entry: ModelEntry) -> Dict[str, Any]:
    """向模型库新增单个条目。如果存在相同 id 或 provider-kind-model 组合，则覆盖该条目。"""
    kind_map = {
        'llm': 'llms', 'llms': 'llms',
        'embedding': 'embeddings', 'embeddings': 'embeddings',
        'reranker': 'rerankers', 'rerankers': 'rerankers',
    }
    lst_name = kind_map.get(kind.lower())
    if not lst_name:
        raise HTTPException(status_code=400, detail=f'无效kind: {kind}')

    reg = _load_registry()
    items = getattr(reg, lst_name)

    # 规范化 kind
    entry.kind = 'llm' if lst_name == 'llms' else ('embedding' if lst_name == 'embeddings' else 'reranker')

    # 生成缺省 id/label
    def ensure_id_label(it: ModelEntry):
        if (not it.id) or (not str(it.id).strip()):
            base = f"{it.provider}-{it.kind}-{it.model}".replace('/', '_').replace(':', '_')
            it.id = base
        if (not it.label) or (not str(it.label).strip()):
            it.label = it.model

    ensure_id_label(entry)

    # 去重：按 id 或 provider-kind-model 覆盖
    def key(it: ModelEntry) -> str:
        return f"{it.provider}-{it.kind}-{it.model}"
    new_list: list[ModelEntry] = []
    replaced = False
    for it in items:
        if it.id == entry.id or key(it) == key(entry):
            if not replaced:
                new_list.append(entry)
                replaced = True
            else:
                # 已替换一次，跳过重复
                continue
        else:
            new_list.append(it)
    if not replaced:
        new_list.append(entry)

    setattr(reg, lst_name, new_list)
    _save_registry(reg)

    # 返回去掉明文密钥的条目
    d = entry.model_dump()
    if 'api_key' in d:
        d['has_api_key'] = bool(d.get('api_key'))
        d.pop('api_key', None)
    return {'ok': True, 'item': d}


@router.patch('/models/registry/{kind}/{entry_id}', summary='更新单个模型条目（局部更新）')
async def patch_model_entry(kind: str, entry_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """按ID更新模型条目，支持 label/model/base_url/api_key_env/api_key 字段。"""
    kind_map = {
        'llm': 'llms', 'llms': 'llms',
        'embedding': 'embeddings', 'embeddings': 'embeddings',
        'reranker': 'rerankers', 'rerankers': 'rerankers',
    }
    lst_name = kind_map.get(kind.lower())
    if not lst_name:
        raise HTTPException(status_code=400, detail=f'无效kind: {kind}')
    reg = _load_registry()
    items = getattr(reg, lst_name)
    idx = next((i for i, it in enumerate(items) if (it.id == entry_id)), None)
    if idx is None:
        raise HTTPException(status_code=404, detail=f'未找到模型: {entry_id}')
    # 允许更新的字段
    allowed = {'label', 'model', 'base_url', 'api_key_env', 'api_key'}
    for k, v in payload.items():
        if k in allowed:
            setattr(items[idx], k, v)
    _save_registry(reg)
    # 返回去掉密钥的条目
    d = items[idx].model_dump()
    if 'api_key' in d:
        d['has_api_key'] = bool(d.get('api_key'))
        d.pop('api_key', None)
    return {'ok': True, 'item': d}


@router.delete('/models/registry/{kind}/{entry_id}', summary='删除单个模型条目')
async def delete_model_entry(kind: str, entry_id: str) -> Dict[str, Any]:
    kind_map = {
        'llm': 'llms', 'llms': 'llms',
        'embedding': 'embeddings', 'embeddings': 'embeddings',
        'reranker': 'rerankers', 'rerankers': 'rerankers',
    }
    lst_name = kind_map.get(kind.lower())
    if not lst_name:
        raise HTTPException(status_code=400, detail=f'无效kind: {kind}')
    reg = _load_registry()
    items = getattr(reg, lst_name)
    new_items = [it for it in items if it.id != entry_id]
    if len(new_items) == len(items):
        raise HTTPException(status_code=404, detail=f'未找到模型: {entry_id}')
    setattr(reg, lst_name, new_items)
    _save_registry(reg)
    return {'ok': True, 'deleted': entry_id}
