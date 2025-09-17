#!/usr/bin/env python3
"""
Run RAGAS evaluation without DB using the first 5 rows from backend/test_full_data.xlsx
It calls the real RAG-LLM API defined by RAG_API_URL and prints a compact summary.
"""
import asyncio
import os
import sys
from pathlib import Path

# Ensure backend is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from app.services.ragas_service import run_real_rag_evaluation


def build_cases_from_excel(xlsx_path: Path, limit: int = 5):
    df = pd.read_excel(xlsx_path).head(limit)
    cases = []
    for _, row in df.iterrows():
        cases.append({
            'question_id': str(row.get('题号', '')),
            'clinical_query': str(row.get('临床场景', '')),
            'ground_truth': str(row.get('首选检查项目（标准化）', '')),
        })
    return cases


async def main():
    xlsx = ROOT / 'test_full_data.xlsx'
    if not xlsx.exists():
        print(f'ERROR: Excel file not found: {xlsx}')
        sys.exit(1)

    cases = build_cases_from_excel(xlsx, limit=5)
    if not cases:
        print('ERROR: No cases built from excel')
        sys.exit(1)

    # Show which RAG API we will call
    rag_api = os.getenv('RAG_API_URL', 'http://127.0.0.1:8002/api/v1/acrac/rag-llm/intelligent-recommendation')
    print('RAG_API_URL =', rag_api)

    res = await run_real_rag_evaluation(
        test_cases=cases,
        model_name=os.getenv('SILICONFLOW_LLM_MODEL', 'Qwen/Qwen2.5-32B-Instruct'),
    )

    print('status:', res.get('status'))
    print('total:', res.get('total_cases'), 'completed:', res.get('completed_cases'), 'failed:', res.get('failed_cases'))
    for r in (res.get('results') or [])[:5]:
        print(r.get('question_id'), r.get('success'), r.get('metrics', {}))


if __name__ == '__main__':
    asyncio.run(main())

