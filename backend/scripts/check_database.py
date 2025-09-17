#!/usr/bin/env python3
"""
检查数据库中的临床场景和向量数据
"""

import psycopg2
import os
from pgvector.psycopg2 import register_vector

def check_database():
    conn = psycopg2.connect(
        host='localhost',
        port='5432', 
        database='acrac_db',
        user='postgres',
        password='password'
    )
    register_vector(conn)

    with conn.cursor() as cur:
        # 检查临床场景数据
        cur.execute('SELECT COUNT(*) FROM clinical_scenarios')
        scenarios_count = cur.fetchone()[0]
        print(f'临床场景总数: {scenarios_count}')
        
        # 检查临床推荐数据
        cur.execute('SELECT COUNT(*) FROM clinical_recommendations')
        recs_count = cur.fetchone()[0]
        print(f'临床推荐总数: {recs_count}')
        
        # 检查向量数据
        cur.execute('SELECT COUNT(*) FROM clinical_recommendations WHERE embedding IS NOT NULL')
        vec_count = cur.fetchone()[0]
        print(f'有向量的推荐数: {vec_count}')
        
        # 查看几个临床场景样例
        cur.execute('SELECT semantic_id, description_zh FROM clinical_scenarios LIMIT 3')
        scenarios = cur.fetchall()
        print('\n临床场景样例:')
        for s in scenarios:
            print(f'  {s[0]}: {s[1][:50]}...')
            
        # 查看几个临床推荐样例
        cur.execute('''
            SELECT cr.semantic_id, pd.name_zh, pd.modality, cs.description_zh
            FROM clinical_recommendations cr
            JOIN procedure_dictionary pd ON cr.procedure_id = pd.semantic_id
            JOIN clinical_scenarios cs ON cr.scenario_id = cs.semantic_id
            WHERE cr.embedding IS NOT NULL
            LIMIT 3
        ''')
        recs = cur.fetchall()
        print('\n临床推荐样例:')
        for r in recs:
            print(f'  {r[0]}: {r[1]} ({r[2]}) - {r[3][:30]}...')

    conn.close()

if __name__ == "__main__":
    check_database()
