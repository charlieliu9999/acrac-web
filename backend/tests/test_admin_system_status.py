import os
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient

# 仅加载 admin_data_api，避免引入 ragas/celery 依赖
from app.api.api_v1.endpoints import admin_data_api


def create_minimal_app() -> FastAPI:
    app = FastAPI()
    app.include_router(admin_data_api.router, prefix="/admin/data")
    return app


def test_system_status_endpoint_returns_structure():
    app = create_minimal_app()
    client = TestClient(app)

    resp = client.get("/admin/data/system/status")
    assert resp.status_code == 200
    data = resp.json()

    # 基本结构存在
    assert isinstance(data, dict)
    assert "ts" in data
    assert "api" in data
    assert "db" in data  # 即便数据库不可用，也应返回错误结构

    # api 字段结构
    assert isinstance(data["api"], dict)
    assert data["api"].get("status") in {"ok", "error"}

    # db 字段结构（在无数据库时允许为 error，但必须是可解析结构）
    assert isinstance(data["db"], dict)
    assert data["db"].get("status") in {"ok", "error"}


def test_models_config_endpoint_returns_defaults():
    app = create_minimal_app()
    client = TestClient(app)

    # 不要求存在任何配置文件，接口应返回默认结构
    resp = client.get("/admin/data/models/config")
    assert resp.status_code == 200
    data = resp.json()

    # 关键字段存在
    for k in ["embedding_model", "llm_model", "reranker_model", "base_url", "contexts"]:
        assert k in data
    assert isinstance(data["contexts"], dict)
    assert "inference" in data["contexts"]
    assert "evaluation" in data["contexts"]


def test_check_single_model_endpoint_responds_even_when_service_missing():
    app = create_minimal_app()
    client = TestClient(app)

    # 构造一个本地 ollama 的示例（即便不运行，也应返回可解释的错误结构）
    payload = {
        "provider": "ollama",
        "kind": "llm",
        "model": "qwen3:4b",
        "base_url": "http://localhost:11434/v1"
    }
    resp = client.post("/admin/data/models/check-model", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    # 至少包含以下键，status 可为 ok/warning/error（本地未运行多半为 error）
    for k in ["kind", "model", "provider", "base_url", "status"]:
        assert k in data

