"""
RAG modular service package

This package contains smaller, focused modules extracted from the
monolithic rag_llm_recommendation_service. Each module is kept
under ~500 lines and can be reused independently by other API
servers if needed.
"""

__all__ = [
    "embeddings",
    "db",
    "prompts",
    "llm_client",
    "parser",
    "reranker",
    "contexts",
    "ragas_eval",
    "pipeline",
    "signals_utils",
]

