#!/usr/bin/env python3
import os
import sys
import json
import time
import psycopg2
from psycopg2.extras import RealDictCursor
import requests

API_BASE = os.getenv('SILICONFLOW_BASE_URL', 'https://api.siliconflow.cn/v1')
API_KEY = os.getenv('SILICONFLOW_API_KEY')
EMB_MODEL = os.getenv('SILICONFLOW_EMBEDDING_MODEL', 'BAAI/bge-m3')

def embed(text: str) -> list:
    prefers_ollama = ('11434' in (API_BASE or '')) or ('ollama' in (API_BASE or '').lower())
    headers = {"Content-Type": "application/json"}
    if not prefers_ollama:
        if not API_KEY:
            raise RuntimeError('SILICONFLOW_API_KEY not set')
        headers["Authorization"] = f"Bearer {API_KEY}"
    resp = requests.post(
        f"{API_BASE.rstrip('/')}/embeddings",
        headers=headers,
        json={"model": EMB_MODEL, "input": text, "encoding_format": "float"},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data['data'][0]['embedding']

def main():
    cfg = {
        'host': os.getenv('PGHOST', 'localhost'),
        'port': int(os.getenv('PGPORT', '5432')),
        'database': os.getenv('PGDATABASE', 'acrac_db'),
        'user': os.getenv('PGUSER', 'postgres'),
        'password': os.getenv('PGPASSWORD', 'password'),
    }
    conn = psycopg2.connect(**cfg)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT semantic_id, name_zh, name_en, modality, description_zh
                FROM procedure_dictionary
                WHERE is_active = true AND (embedding IS NULL)
                ORDER BY semantic_id
                LIMIT 500
                """
            )
            rows = cur.fetchall()
            print(f"Found {len(rows)} procedures without embeddings")
            for r in rows:
                text = ' / '.join([
                    str(r.get('name_zh') or ''),
                    str(r.get('name_en') or ''),
                    str(r.get('modality') or ''),
                    str(r.get('description_zh') or '')
                ])
                try:
                    vec = embed(text)
                except Exception as e:
                    print(f"Embedding failed for {r['semantic_id']}: {e}")
                    continue
                # Update
                cur2 = conn.cursor()
                cur2.execute(
                    "UPDATE procedure_dictionary SET embedding = %s WHERE semantic_id = %s",
                    (vec, r['semantic_id'])
                )
                conn.commit()
                cur2.close()
                print(f"Updated embedding for {r['semantic_id']}")
                time.sleep(0.2)
    finally:
        conn.close()

if __name__ == '__main__':
    main()
