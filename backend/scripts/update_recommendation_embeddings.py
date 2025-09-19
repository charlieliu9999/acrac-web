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
    if not API_KEY and ('11434' not in (API_BASE or '') and 'ollama' not in (API_BASE or '').lower()):
        raise RuntimeError('SILICONFLOW_API_KEY not set')
    headers = {"Content-Type": "application/json"}
    if API_KEY and ('11434' not in API_BASE and 'ollama' not in API_BASE.lower()):
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
                SELECT cr.id, cr.semantic_id,
                       cr.appropriateness_rating, COALESCE(cr.reasoning_zh,'') AS reason,
                       COALESCE(cr.evidence_level,'') AS ev,
                       s.description_zh AS scenario_desc,
                       COALESCE(s.patient_population,'') AS pop,
                       COALESCE(s.risk_level,'') AS risk,
                       pd.name_zh AS proc_name,
                       COALESCE(pd.modality,'') AS mod,
                       COALESCE(pd.body_part,'') AS bp
                FROM clinical_recommendations cr
                JOIN clinical_scenarios s ON cr.scenario_id = s.semantic_id
                JOIN procedure_dictionary pd ON cr.procedure_id = pd.semantic_id
                WHERE cr.is_active = true AND cr.embedding IS NULL
                ORDER BY cr.id
                LIMIT 500
                """
            )
            rows = cur.fetchall()
            print(f"Found {len(rows)} recommendations without embeddings")
            for r in rows:
                parts = [
                    f"临床场景:{r.get('scenario_desc')}",
                    f"人群:{r.get('pop')}",
                    f"风险:{r.get('risk')}",
                    f"检查项目:{r.get('proc_name')}",
                    f"方式:{r.get('mod')}",
                    f"部位:{r.get('bp')}",
                    f"评分:{r.get('appropriateness_rating')}",
                    f"理由:{r.get('reason')}",
                    f"证据:{r.get('ev')}",
                ]
                text = ' | '.join([p for p in parts if p and not p.endswith(':')])
                try:
                    vec = embed(text)
                except Exception as e:
                    print(f"Embedding failed for {r['semantic_id']}: {e}")
                    continue
                with conn.cursor() as cur2:
                    cur2.execute(
                        "UPDATE clinical_recommendations SET embedding = %s WHERE id = %s",
                        (vec, r['id'])
                    )
                    conn.commit()
                print(f"Updated recommendation embedding for {r['semantic_id']}")
                time.sleep(0.2)
    finally:
        conn.close()


if __name__ == '__main__':
    main()

