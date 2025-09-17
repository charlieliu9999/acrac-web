#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import engine
from sqlalchemy import text

def add_missing_column():
    """添加缺失的clinical_scenario_id字段"""
    try:
        with engine.connect() as conn:
            # 添加字段
            conn.execute(text(
                "ALTER TABLE scenario_results ADD COLUMN IF NOT EXISTS clinical_scenario_id INTEGER REFERENCES clinical_scenario_data(id) ON DELETE SET NULL"
            ))
            
            # 添加索引
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_scenario_results_clinical_scenario_id ON scenario_results(clinical_scenario_id)"
            ))
            
            conn.commit()
            print("字段添加成功")
            
    except Exception as e:
        print(f"添加字段失败: {e}")

if __name__ == "__main__":
    add_missing_column()