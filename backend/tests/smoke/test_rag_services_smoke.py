import os
from fastapi.testclient import TestClient


def _setup_env():
    os.environ.setdefault("STRICT_EMBEDDING", "false")
    os.environ.setdefault("RAG_USE_RERANKER", "false")
    os.environ.setdefault("RERANK_PROVIDER", "local")
    os.environ.setdefault("LLM_FORCE_JSON", "true")
    os.environ.setdefault("LLM_MAX_TOKENS", "256")
    os.environ.setdefault("SKIP_LOCAL_DOTENV", "true")
    os.environ.setdefault("DOCKER_CONTEXT", "true")


def test_rag_services_smoke():
    _setup_env()
    # Build a minimal app mounting only modular RAG services to avoid heavy deps
    from fastapi import FastAPI
    from app.api.api_v1.endpoints import rag_services_api
    app = FastAPI()
    app.include_router(rag_services_api.router, prefix="/api/v1/acrac/rag-services")
    client = TestClient(app)

    # Embeddings (should fallback to random vector offline)
    r = client.post("/api/v1/acrac/rag-services/embeddings", json={"text": "突发剧烈头痛"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data.get("vector"), list) and data.get("dim")

    # Prompt (no DB required)
    r = client.post(
        "/api/v1/acrac/rag-services/prompt",
        json={
            "query": "突发雷击样头痛",
            "scenarios": [],
            "scenarios_with_recs": [],
            "is_low_similarity": True,
        },
    )
    assert r.status_code == 200, r.text
    prompt = r.json()["prompt"]
    assert isinstance(prompt, str) and len(prompt) > 10

    # LLM (should return fallback JSON offline)
    r = client.post("/api/v1/acrac/rag-services/llm", json={"prompt": prompt})
    assert r.status_code == 200, r.text
    assert isinstance(r.json().get("content"), str)

    # Parse
    r = client.post(
        "/api/v1/acrac/rag-services/parse",
        json={
            "llm_response": '{"recommendations":[{"procedure_name":"CT 颅脑平扫","modality":"CT","appropriateness_rating":9}],"summary":"ok"}',
        },
    )
    assert r.status_code == 200, r.text
    parsed = r.json()
    assert parsed.get("recommendations") and parsed.get("summary")

    # Pipeline (no-RAG path; DB failure tolerated)
    r = client.post(
        "/api/v1/acrac/rag-services/pipeline/recommend",
        json={
            "clinical_query": "妊娠期胸痛，考虑肺栓塞",
            "debug_mode": True,
            "compute_ragas": False,
        },
    )
    assert r.status_code == 200, r.text
    result = r.json()
    assert result.get("success") is True
