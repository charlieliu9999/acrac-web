#!/usr/bin/env python3
import os
import psycopg2
from pathlib import Path

SQL_FILE = Path(__file__).resolve().parents[0] / 'sql' / '20250909_fix_procedure_fields.sql'

def main():
    cfg = {
        'host': os.getenv('PGHOST', 'localhost'),
        'port': int(os.getenv('PGPORT', '5432')),
        'database': os.getenv('PGDATABASE', 'acrac_db'),
        'user': os.getenv('PGUSER', 'postgres'),
        'password': os.getenv('PGPASSWORD', 'password'),
    }
    sql = SQL_FILE.read_text(encoding='utf-8')
    conn = psycopg2.connect(**cfg)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            print('Migration applied successfully.')
    finally:
        conn.close()

if __name__ == '__main__':
    main()

