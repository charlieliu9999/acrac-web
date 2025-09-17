#!/usr/bin/env python3
"""
Quick check for SiliconFlow reranker availability using BAAI/bge-reranker-v2-m3.

- Loads env from backend/.env if present
- Sends a tiny rerank request and prints scores/order
"""
import os
import json
import sys
from pathlib import Path
import requests

def load_env():
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).resolve().parents[1] / ".env"
        if env_path.exists():
            load_dotenv(str(env_path))
    except Exception:
        pass

def test_rerank():
    api_key = os.getenv("SILICONFLOW_API_KEY")
    base = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    model = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
    if not api_key:
        print("SILICONFLOW_API_KEY not set")
        sys.exit(1)

    query = "妊娠 胸痛 呼吸困难 D-二聚体 肺栓塞"
    docs = [
        "疑似肺栓塞 低或中等验前概率伴D二聚体阳性 初始影像学检查 | 胸外科 | 疑似肺栓塞",
        "成人。长期跛行史。急性发作左下肢疼痛。触诊左股动脉搏动消失 | 介入放射科 | 髂动脉闭塞性疾病",
        "头痛 伴发热或神经功能缺损 初始影像学检查 | 神经内科 | 头痛",
    ]
    payload = {
        "model": model,
        "query": query,
        "documents": docs,
        "top_n": len(docs)
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = f"{base}/rerank"
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
    except Exception as e:
        print("Request error:", e)
        sys.exit(1)

    print("Status:", resp.status_code)
    if resp.status_code != 200:
        print("Body:", resp.text[:500])
        sys.exit(2)

    data = resp.json()
    results = data.get("results") or data.get("data") or []
    if not results:
        print("No results field in response:", json.dumps(data)[:500])
        sys.exit(3)
    # Build (score, doc) pairs
    scored = []
    for r in results:
        idx = r.get("index")
        score = r.get("relevance_score")
        if idx is None or score is None:
            continue
        if 0 <= idx < len(docs):
            scored.append((float(score), docs[idx]))
    scored.sort(reverse=True)
    print("\nRerank results (score, doc):")
    for s, d in scored:
        print(f"  {s:.4f} | {d}")

if __name__ == "__main__":
    load_env()
    test_rerank()

