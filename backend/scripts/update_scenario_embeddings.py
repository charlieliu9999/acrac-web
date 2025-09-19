#!/usr/bin/env python3
import os
import time
import psycopg2
from psycopg2.extras import RealDictCursor
import requests

API_BASE = os.getenv('SILICONFLOW_BASE_URL', 'https://api.siliconflow.cn/v1')
API_KEY = os.getenv('SILICONFLOW_API_KEY')
EMB_MODEL = os.getenv('SILICONFLOW_EMBEDDING_MODEL', 'BAAI/bge-m3')


def embed(text: str) -> list:
    if not API_KEY:
        raise RuntimeError('SILICONFLOW_API_KEY not set')
    resp = requests.post(
        f"{API_BASE}/embeddings",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
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
                SELECT s.id, s.semantic_id, s.description_zh, COALESCE(s.clinical_context,'') AS ctx,
                       COALESCE(s.patient_population,'') AS pop, COALESCE(s.risk_level,'') AS risk,
                       COALESCE(s.age_group,'') AS age, COALESCE(s.gender,'') AS gender,
                       p.name_zh AS panel_name, t.name_zh AS topic_name
                FROM clinical_scenarios s
                JOIN panels p ON s.panel_id = p.id
                JOIN topics t ON s.topic_id = t.id
                WHERE s.is_active = true AND s.embedding IS NULL
                ORDER BY s.id
                LIMIT 500
                """
            )
            rows = cur.fetchall()
            print(f"Found {len(rows)} scenarios without embeddings")
            for r in rows:
                parts = [
                    f"科室:{r.get('panel_name')}",
                    f"主题:{r.get('topic_name')}",
                    f"临床场景:{r.get('description_zh')}",
                    f"人群:{r.get('pop')}",
                    f"风险:{r.get('risk')}",
                    f"年龄:{r.get('age')}",
                    f"性别:{r.get('gender')}",
                    f"上下文:{r.get('ctx')}",
                ]
                text = ' | '.join([p for p in parts if p and not p.endswith(':')])
                try:
                    vec = embed(text)
                except Exception as e:
                    print(f"Embedding failed for {r['semantic_id']}: {e}")
                    continue
                with conn.cursor() as cur2:
                    cur2.execute(
                        "UPDATE clinical_scenarios SET embedding = %s WHERE id = %s",
                        (vec, r['id'])
                    )
                    conn.commit()
                print(f"Updated scenario embedding for {r['semantic_id']}")
                time.sleep(0.2)
    finally:
        conn.close()


if __name__ == '__main__':
    main()

