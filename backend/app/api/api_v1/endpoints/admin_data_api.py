from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from pathlib import Path
import subprocess
import time
import os
import re
from app.core.config import settings

router = APIRouter()

# 统一定位到 backend 目录（更稳健的层级）
BACKEND_DIR = Path(__file__).resolve().parents[4]
UPLOAD_DIR = BACKEND_DIR / 'uploads'
SCRIPTS_DIR = BACKEND_DIR / 'scripts'
REGISTRY_PATH = BACKEND_DIR / 'config' / 'models_registry.json'


class ImportRequest(BaseModel):
    csv_path: Optional[str] = Field(None, description='服务器上的CSV路径（若已上传）')
    mode: str = Field('clear', description='导入模式: clear(清空重建)/add(追加)')
    embedding_model: Optional[str] = Field(None, description='SiliconFlow embedding model id, e.g., BAAI/bge-m3')
    llm_model: Optional[str] = Field(None, description='LLM model id used in service')


class ImportResponse(BaseModel):
    started: bool
    log_path: Optional[str] = None
    command: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None


class ModelsConfig(BaseModel):
    embedding_model: Optional[str] = None
    llm_model: Optional[str] = None
    reranker_model: Optional[str] = None
    base_url: Optional[str] = None
    siliconflow_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    # Defaults for RAGAS (optional)
    ragas_llm_model: Optional[str] = None
    ragas_embedding_model: Optional[str] = None


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
        with dest.open('wb') as f:
            content = await file.read()
            f.write(content)
        return { 'ok': True, 'path': str(dest) }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/import', response_model=ImportResponse, summary='从CSV导入/重建数据（同步执行，可能耗时）')
async def import_csv(req: ImportRequest) -> ImportResponse:
    try:
        # Enforce presence of API key to avoid building with random embeddings
        if not (os.getenv('SILICONFLOW_API_KEY') or settings.SILICONFLOW_API_KEY):
            raise HTTPException(status_code=400, detail='SILICONFLOW_API_KEY 未配置。为保证向量准确性，请先在 backend/.env 设置该Key。')
        csv_path = req.csv_path
        if not csv_path:
            raise HTTPException(status_code=400, detail='csv_path 必填（先上传或提供服务器绝对路径）')
        csv = Path(csv_path)
        if not csv.exists():
            raise HTTPException(status_code=400, detail='csv_path 不存在')
        log_dir = Path(__file__).resolve().parents[5] / 'backend' / 'logs'
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
    return {
        'embedding_model': os.getenv('SILICONFLOW_EMBEDDING_MODEL', ''),
        'llm_model': os.getenv('SILICONFLOW_LLM_MODEL', ''),
        'reranker_model': os.getenv('RERANKER_MODEL', 'BAAI/bge-reranker-v2-m3'),
        'base_url': os.getenv('SILICONFLOW_BASE_URL', 'https://api.siliconflow.cn/v1'),
        'keys': {
            'siliconflow_api_key': has('SILICONFLOW_API_KEY'),
            'openai_api_key': has('OPENAI_API_KEY'),
        },
        'providers': ['siliconflow','openai','local'],
        'ragas_defaults': {
            'llm_model': os.getenv('RAGAS_DEFAULT_LLM_MODEL', ''),
            'embedding_model': os.getenv('RAGAS_DEFAULT_EMBEDDING_MODEL', '')
        }
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
    base_url = os.getenv('SILICONFLOW_BASE_URL') or settings.SILICONFLOW_BASE_URL
    if (context or '').lower() == 'ragas':
        llm_model = os.getenv('RAGAS_DEFAULT_LLM_MODEL') or os.getenv('SILICONFLOW_LLM_MODEL') or settings.SILICONFLOW_LLM_MODEL
        emb_model = os.getenv('RAGAS_DEFAULT_EMBEDDING_MODEL') or os.getenv('SILICONFLOW_EMBEDDING_MODEL', 'BAAI/bge-m3')
    else:
        llm_model = os.getenv('SILICONFLOW_LLM_MODEL') or settings.SILICONFLOW_LLM_MODEL
        emb_model = os.getenv('SILICONFLOW_EMBEDDING_MODEL', 'BAAI/bge-m3')
    reranker_model = os.getenv('RERANKER_MODEL', 'BAAI/bge-reranker-v2-m3')

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
        client = openai.OpenAI(api_key=api_key, base_url=base_url)
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
        vec = embed_with_siliconflow('ping', api_key=api_key, model=emb_model)
        dim = len(vec) if isinstance(vec, list) else 0
        ok = dim >= 128  # 宽松判定
        out['embedding'] = {'status': 'ok' if ok else 'warning', 'model': emb_model, 'dimension': dim, 'context': context or 'rag_llm'}
    except Exception as e:
        out['embedding'] = {'status': 'error', 'error': str(e), 'model': emb_model, 'context': context or 'rag_llm'}

    # Reranker check（可选）
    try:
        if api_key and base_url:
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
    if not REGISTRY_PATH.exists():
        return ModelsRegistry()
    try:
        import json
        data = json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
        return ModelsRegistry(**data)
    except Exception:
        return ModelsRegistry()


def _save_registry(reg: ModelsRegistry):
    import json
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(reg.model_dump(), ensure_ascii=False, indent=2), encoding='utf-8')


@router.post('/models/config', summary='更新模型配置（写入.env并设置当前进程env）')
async def set_models_config(cfg: ModelsConfig) -> Dict[str, Any]:
    try:
        if cfg.embedding_model is not None: os.environ['SILICONFLOW_EMBEDDING_MODEL'] = cfg.embedding_model
        if cfg.llm_model is not None: os.environ['SILICONFLOW_LLM_MODEL'] = cfg.llm_model
        if cfg.reranker_model is not None: os.environ['RERANKER_MODEL'] = cfg.reranker_model
        if cfg.base_url is not None: os.environ['SILICONFLOW_BASE_URL'] = cfg.base_url
        if cfg.siliconflow_api_key is not None: os.environ['SILICONFLOW_API_KEY'] = cfg.siliconflow_api_key
        if cfg.openai_api_key is not None: os.environ['OPENAI_API_KEY'] = cfg.openai_api_key

        env_path = Path(__file__).resolve().parents[5] / 'backend' / '.env'
        text = env_path.read_text(encoding='utf-8') if env_path.exists() else ''
        for k, v in [
            ('SILICONFLOW_EMBEDDING_MODEL', cfg.embedding_model),
            ('SILICONFLOW_LLM_MODEL', cfg.llm_model),
            ('RERANKER_MODEL', cfg.reranker_model),
            ('SILICONFLOW_BASE_URL', cfg.base_url),
            ('SILICONFLOW_API_KEY', cfg.siliconflow_api_key),
            ('OPENAI_API_KEY', cfg.openai_api_key),
            # RAGAS defaults
            ('RAGAS_DEFAULT_LLM_MODEL', cfg.ragas_llm_model),
            ('RAGAS_DEFAULT_EMBEDDING_MODEL', cfg.ragas_embedding_model),
        ]:
            text = _update_env(text, k, v)
        env_path.write_text(text, encoding='utf-8')
        return {'ok': True, 'requires_restart': True}
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
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type":"application/json"}
            r = requests.post(url, json={'model': entry.model, 'input': 'ping'}, headers=headers, timeout=30)
            ok = r.status_code == 200 and isinstance(r.json().get('data'), list)
            dim = len((r.json().get('data') or [{}])[0].get('embedding') or []) if ok else 0
            out.update({'status': 'ok' if ok else 'warning', 'http_status': r.status_code, 'dimension': dim})
        elif entry.kind == 'reranker':
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
