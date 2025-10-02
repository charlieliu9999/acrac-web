import os
import logging
from typing import List, Optional

import numpy as np
import requests

logger = logging.getLogger(__name__)

# Strict mode: fail fast on embedding errors unless explicitly disabled
STRICT_EMBEDDING = (
    os.getenv("STRICT_EMBEDDING", "true").lower() in ("1", "true", "yes")
)


def embed_with_siliconflow(
    text: str,
    api_key: Optional[str] = None,
    model: str = "BAAI/bge-m3",
    timeout: int = 60,
    base_url: Optional[str] = None,
) -> List[float]:
    """Create embeddings via OpenAI-compatible API endpoints.

    Supports SiliconFlow, OpenAI, OpenRouter, and Ollama (at /v1/embeddings).
    - If base_url points to Ollama (contains 11434 or "ollama"), no key needed.
    - Otherwise, a key is required from argument or env var.

    In strict mode (default), errors are raised to surface configuration issues.
    When STRICT_EMBEDDING=false, returns a random vector for local debugging.
    """
    try:
        endpoint = (
            base_url
            or os.getenv("OPENAI_BASE_URL")
            or os.getenv("SILICONFLOW_BASE_URL")
            or os.getenv("OLLAMA_BASE_URL")
            or "https://api.siliconflow.cn/v1"
        ).rstrip("/")
        prefers_ollama = ("11434" in endpoint) or ("ollama" in endpoint.lower())

        key = (
            api_key
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("SILICONFLOW_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
        )

        headers = {"Content-Type": "application/json"}
        if not prefers_ollama and key:
            headers["Authorization"] = f"Bearer {key}"

        payload = {"model": model, "input": text}
        resp = requests.post(
            f"{endpoint}/embeddings", json=payload, headers=headers, timeout=timeout
        )
        resp.raise_for_status()
        data = resp.json()
        emb = (data.get("data") or [{}])[0].get("embedding")
        if not isinstance(emb, list):
            raise ValueError("invalid embeddings response")
        return emb
    except Exception as e:
        endpoint_hint = (
            (base_url
            or os.getenv("OPENAI_BASE_URL")
            or os.getenv("SILICONFLOW_BASE_URL")
            or os.getenv("OLLAMA_BASE_URL")
            or "unknown")
        ).rstrip("/")
        logger.error(f"Embedding request failed ({endpoint_hint}): {e}")
        if STRICT_EMBEDDING:
            raise
        logger.warning(
            "STRICT_EMBEDDING=false → using random vector for debug only"
        )
        return np.random.rand(1024).tolist()

