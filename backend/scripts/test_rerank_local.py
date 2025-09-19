#!/usr/bin/env python3
"""
Quick test for local reranker (transformers CrossEncoder):

Usage:
  python backend/scripts/test_rerank_local.py "query text" "doc1" "doc2" ...

Env:
  RERANKER_MODEL (default: BAAI/bge-reranker-v2-m3)

Notes:
  - Downloads model on first run to HF cache.
  - Works independently from SiliconFlow/Ollama.
"""
import os
import sys
from typing import List, Dict

def local_rerank(query: str, docs: List[str], model_id: str) -> List[Dict]:
    try:
        from sentence_transformers import CrossEncoder  # type: ignore
        ce = CrossEncoder(model_id)
        pairs = [(query, d) for d in docs]
        scores = ce.predict(pairs)
        out = [{"doc": d, "score": float(s)} for d, s in zip(docs, scores)]
        out.sort(key=lambda x: x["score"], reverse=True)
        return out
    except Exception:
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification  # type: ignore
        tok = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForSequenceClassification.from_pretrained(model_id)
        model.eval()
        out = []
        for d in docs:
            with torch.no_grad():
                inputs = tok(query, d, return_tensors='pt', truncation=True, max_length=512)
                logits = model(**inputs).logits
                s = float(torch.sigmoid(logits.squeeze()).item())
                out.append({"doc": d, "score": s})
        out.sort(key=lambda x: x["score"], reverse=True)
        return out

def main():
    if len(sys.argv) < 3:
        print("Usage: python backend/scripts/test_rerank_local.py 'query' 'doc1' 'doc2' ...")
        sys.exit(1)
    query = sys.argv[1]
    docs = sys.argv[2:]
    model_id = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
    # map possible ollama tag to HF id
    if "/" in model_id and model_id.lower().startswith("dengcao/"):
        model_id = "BAAI/bge-reranker-v2-m3"
    ranked = local_rerank(query, docs, model_id)
    for i, item in enumerate(ranked, 1):
        print(f"{i:02d}. score={item['score']:.4f}  {item['doc']}")

if __name__ == "__main__":
    main()

