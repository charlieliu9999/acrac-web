#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证RAGAS表结构与模型定义的一致性
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import engine
from app.models.ragas_models import EvaluationTask, ScenarioResult, EvaluationMetrics, DataAdapterLog
from sqlalchemy import inspect, text
import json
from datetime import datetime

def get_model_columns(model_class):
    """获取模型定义的列信息"""
    columns = {}
    for column in model_class.__table__.columns:
        columns[column.name] = {
            'type': str(column.type),
            'nullable': column.nullable,
            'primary_key': column.primary_key,
            'default': str(column.default) if column.default is not None else None,
            'foreign_key': column.foreign_keys is not None and len(column.foreign_keys) > 0
        }
    return columns

def get_db_columns(table_name, inspector):
    """获取数据库中表的列信息"""
    columns = {}
    if table_name in inspector.get_table_names():
        for column in inspector.get_columns(table_name):
            columns[column['name']] = {
                'type': str(column['type']),
                'nullable': column['nullable'],
                'primary_key': False,  # 需要单独检查
                'default': str(column['default']) if column['default'] is not None else None,
                'foreign_key': False  # 需要单独检查
            }
        
        # 检查主键
        pk_constraint = inspector.get_pk_constraint(table_name)
        for pk_col in pk_constraint['constrained_columns']:
            if pk_col in columns:
                columns[pk_col]['primary_key'] = True
        
        # 检查外键
        fk_constraints = inspector.get_foreign_keys(table_name)
        for fk in fk_constraints:
            for fk_col in fk['constrained_columns']:
                if fk_col in columns:
                    columns[fk_col]['foreign_key'] = True
    
    return columns

def compare_table_structure(model_class, table_name, inspector):
    """比较模型定义与数据库表结构"""
    print(f"\n=== 验证表: {table_name} ===")
    
    model_columns = get_model_columns(model_class)
    db_columns = get_db_columns(table_name, inspector)
    
    comparison_result = {
        'table_name': table_name,
        'exists_in_db': table_name in inspector.get_table_names(),
        'model_columns_count': len(model_columns),
        'db_columns_count': len(db_columns),
        'missing_columns': [],
        'extra_columns': [],
        'type_mismatches': [],
        'nullable_mismatches': [],
        'is_consistent': True
    }
    
    if not comparison_result['exists_in_db']:
        print(f"  ❌ 表 {table_name} 在数据库中不存在")
        comparison_result['is_consistent'] = False
        return comparison_result
    
    print(f"  ✅ 表 {table_name} 存在")
    print(f"  模型定义列数: {len(model_columns)}")
    print(f"  数据库列数: {len(db_columns)}")
    
    # 检查缺失的列
    for col_name in model_columns:
        if col_name not in db_columns:
            comparison_result['missing_columns'].append(col_name)
            comparison_result['is_consistent'] = False
            print(f"  ❌ 缺失列: {col_name}")
    
    # 检查多余的列
    for col_name in db_columns:
        if col_name not in model_columns:
            comparison_result['extra_columns'].append(col_name)
            print(f"  ⚠️  多余列: {col_name}")
    
    # 检查列类型和属性
    for col_name in model_columns:
        if col_name in db_columns:
            model_col = model_columns[col_name]
            db_col = db_columns[col_name]
            
            # 简化类型比较（忽略长度等细节）
            model_type_simple = model_col['type'].split('(')[0].upper()
            db_type_simple = db_col['type'].split('(')[0].upper()
            
            # 类型映射
            type_mapping = {
                'VARCHAR': 'TEXT',
                'CHARACTER VARYING': 'TEXT',
                'TIMESTAMP': 'DATETIME',
                'DOUBLE_PRECISION': 'FLOAT',
                'DOUBLE PRECISION': 'FLOAT'
            }
            
            model_type_mapped = type_mapping.get(model_type_simple, model_type_simple)
            db_type_mapped = type_mapping.get(db_type_simple, db_type_simple)
            
            if model_type_mapped != db_type_mapped and not (
                (model_type_mapped in ['TEXT', 'VARCHAR'] and db_type_mapped in ['TEXT', 'VARCHAR']) or
                (model_type_mapped in ['FLOAT', 'DOUBLE_PRECISION'] and db_type_mapped in ['FLOAT', 'DOUBLE_PRECISION'])
            ):
                comparison_result['type_mismatches'].append({
                    'column': col_name,
                    'model_type': model_col['type'],
                    'db_type': db_col['type']
                })
                print(f"  ⚠️  类型不匹配 {col_name}: 模型={model_col['type']}, 数据库={db_col['type']}")
            
            # 检查nullable属性
            if model_col['nullable'] != db_col['nullable']:
                comparison_result['nullable_mismatches'].append({
                    'column': col_name,
                    'model_nullable': model_col['nullable'],
                    'db_nullable': db_col['nullable']
                })
                print(f"  ⚠️  nullable不匹配 {col_name}: 模型={model_col['nullable']}, 数据库={db_col['nullable']}")
    
    if comparison_result['is_consistent']:
        print(f"  ✅ 表结构一致")
    else:
        print(f"  ❌ 表结构不一致")
    
    return comparison_result

def verify_ragas_table_structures():
    """验证所有RAGAS表结构"""
    print("=== RAGAS表结构验证 ===")
    
    # 定义要检查的模型和表
    models_to_check = [
        (EvaluationTask, 'evaluation_tasks'),
        (ScenarioResult, 'scenario_results'),
        (EvaluationMetrics, 'evaluation_metrics'),
        (DataAdapterLog, 'data_adapter_logs')
    ]
    
    inspector = inspect(engine)
    verification_results = []
    
    for model_class, table_name in models_to_check:
        result = compare_table_structure(model_class, table_name, inspector)
        verification_results.append(result)
    
    # 生成汇总报告
    print("\n=== 验证汇总 ===")
    consistent_tables = [r for r in verification_results if r['is_consistent']]
    inconsistent_tables = [r for r in verification_results if not r['is_consistent']]
    
    print(f"总表数: {len(verification_results)}")
    print(f"结构一致: {len(consistent_tables)}")
    print(f"结构不一致: {len(inconsistent_tables)}")
    
    if inconsistent_tables:
        print("\n需要修复的表:")
        for table in inconsistent_tables:
            print(f"  - {table['table_name']}")
            if table['missing_columns']:
                print(f"    缺失列: {', '.join(table['missing_columns'])}")
    
    # 保存验证结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"table_structure_verification_{timestamp}.json"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(verification_results, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n验证报告已保存到: {report_file}")
    print("=== 表结构验证完成 ===")
    
    return verification_results

if __name__ == "__main__":
    verify_ragas_table_structures()