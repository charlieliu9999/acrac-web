#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查RAGAS相关表的详细结构
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import engine
from sqlalchemy import text, inspect
import json
from datetime import datetime

def check_ragas_tables():
    """检查RAGAS相关表的详细结构"""
    
    ragas_tables = ['evaluation_tasks', 'scenario_results', 'evaluation_metrics']
    table_info = {}
    
    print("=== 检查RAGAS相关表结构 ===")
    
    with engine.connect() as conn:
        inspector = inspect(engine)
        
        for table_name in ragas_tables:
            print(f"\n检查表: {table_name}")
            
            if table_name in inspector.get_table_names():
                print(f"  ✅ 表 {table_name} 存在")
                
                # 获取列信息
                columns = inspector.get_columns(table_name)
                print(f"  列数: {len(columns)}")
                
                column_details = []
                for col in columns:
                    col_info = {
                        'name': col['name'],
                        'type': str(col['type']),
                        'nullable': col['nullable'],
                        'default': str(col['default']) if col['default'] is not None else None
                    }
                    column_details.append(col_info)
                    print(f"    - {col['name']}: {col['type']} (nullable: {col['nullable']})")
                
                # 获取主键信息
                pk_constraint = inspector.get_pk_constraint(table_name)
                print(f"  主键: {pk_constraint['constrained_columns']}")
                
                # 获取外键信息
                fk_constraints = inspector.get_foreign_keys(table_name)
                if fk_constraints:
                    print(f"  外键数: {len(fk_constraints)}")
                    for fk in fk_constraints:
                        print(f"    - {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")
                
                # 获取索引信息
                indexes = inspector.get_indexes(table_name)
                print(f"  索引数: {len(indexes)}")
                for idx in indexes:
                    print(f"    - {idx['name']}: {idx['column_names']} (unique: {idx['unique']})")
                
                # 获取记录数
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                record_count = result.scalar()
                print(f"  记录数: {record_count}")
                
                table_info[table_name] = {
                    'exists': True,
                    'columns': column_details,
                    'primary_key': pk_constraint['constrained_columns'],
                    'foreign_keys': fk_constraints,
                    'indexes': indexes,
                    'record_count': record_count
                }
                
            else:
                print(f"  ❌ 表 {table_name} 不存在")
                table_info[table_name] = {'exists': False}
    
    # 保存检查结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"ragas_tables_check_{timestamp}.json"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(table_info, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n表结构检查报告已保存到: {report_file}")
    print("=== RAGAS表结构检查完成 ===")
    
    return table_info

if __name__ == "__main__":
    check_ragas_tables()