#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据完整性验证脚本
检查现有数据库表和数据的完整性，生成详细报告
"""

from app.core.database import engine
import sqlalchemy as sa
from datetime import datetime
import json

def check_table_integrity():
    """检查所有表的完整性"""
    integrity_report = {
        'timestamp': datetime.now().isoformat(),
        'database_info': {},
        'tables': {},
        'summary': {}
    }
    
    try:
        with engine.connect() as conn:
            # 获取数据库基本信息
            version = conn.execute(sa.text('SELECT version();')).fetchone()[0]
            integrity_report['database_info']['version'] = version
            
            # 获取所有表信息
            tables_query = sa.text("""
                SELECT 
                    t.table_name,
                    t.table_type,
                    pg_size_pretty(pg_total_relation_size(c.oid)) as size
                FROM information_schema.tables t
                LEFT JOIN pg_class c ON c.relname = t.table_name
                WHERE t.table_schema = 'public'
                ORDER BY t.table_name;
            """)
            
            tables_result = conn.execute(tables_query).fetchall()
            
            total_tables = 0
            total_records = 0
            
            for table_info in tables_result:
                table_name = table_info[0]
                table_type = table_info[1]
                table_size = table_info[2] if table_info[2] else 'N/A'
                
                print(f"\n=== 检查表: {table_name} ===")
                
                # 获取表的记录数
                count_query = sa.text(f"SELECT COUNT(*) FROM {table_name};")
                record_count = conn.execute(count_query).fetchone()[0]
                
                # 获取表结构信息
                columns_query = sa.text("""
                    SELECT 
                        column_name,
                        data_type,
                        is_nullable,
                        column_default
                    FROM information_schema.columns 
                    WHERE table_name = :table_name 
                    AND table_schema = 'public'
                    ORDER BY ordinal_position;
                """)
                
                columns_result = conn.execute(columns_query, {'table_name': table_name}).fetchall()
                
                # 检查主键和索引
                indexes_query = sa.text("""
                    SELECT 
                        i.relname as index_name,
                        a.attname as column_name,
                        ix.indisprimary as is_primary,
                        ix.indisunique as is_unique
                    FROM pg_class t
                    JOIN pg_index ix ON t.oid = ix.indrelid
                    JOIN pg_class i ON i.oid = ix.indexrelid
                    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
                    WHERE t.relname = :table_name
                    ORDER BY i.relname, a.attname;
                """)
                
                indexes_result = conn.execute(indexes_query, {'table_name': table_name}).fetchall()
                
                # 存储表信息
                table_data = {
                    'type': table_type,
                    'size': table_size,
                    'record_count': record_count,
                    'columns': [
                        {
                            'name': col[0],
                            'type': col[1],
                            'nullable': col[2] == 'YES',
                            'default': col[3]
                        } for col in columns_result
                    ],
                    'indexes': [
                        {
                            'name': idx[0],
                            'column': idx[1],
                            'is_primary': idx[2],
                            'is_unique': idx[3]
                        } for idx in indexes_result
                    ]
                }
                
                integrity_report['tables'][table_name] = table_data
                total_tables += 1
                total_records += record_count
                
                print(f"  记录数: {record_count}")
                print(f"  表大小: {table_size}")
                print(f"  列数: {len(columns_result)}")
                print(f"  索引数: {len(indexes_result)}")
                
                # 检查是否有空值在非空列中
                null_checks = []
                for col in columns_result:
                    if col[2] == 'NO':  # NOT NULL column
                        null_check_query = sa.text(f"SELECT COUNT(*) FROM {table_name} WHERE {col[0]} IS NULL;")
                        null_count = conn.execute(null_check_query).fetchone()[0]
                        if null_count > 0:
                            null_checks.append(f"{col[0]}: {null_count} null values")
                
                if null_checks:
                    print(f"  ⚠️  数据完整性问题: {', '.join(null_checks)}")
                    table_data['integrity_issues'] = null_checks
                else:
                    print("  ✅ 数据完整性检查通过")
            
            # 生成汇总信息
            integrity_report['summary'] = {
                'total_tables': total_tables,
                'total_records': total_records,
                'ragas_tables_found': {
                    'evaluation_tasks': 'evaluation_tasks' in [t[0] for t in tables_result],
                    'scenario_results': 'scenario_results' in [t[0] for t in tables_result],
                    'evaluation_metrics': 'evaluation_metrics' in [t[0] for t in tables_result]
                }
            }
            
            print(f"\n=== 数据完整性检查汇总 ===")
            print(f"总表数: {total_tables}")
            print(f"总记录数: {total_records}")
            print(f"RAGAS相关表状态:")
            for table, exists in integrity_report['summary']['ragas_tables_found'].items():
                status = "✅ 已存在" if exists else "❌ 不存在"
                print(f"  {table}: {status}")
            
            return integrity_report
            
    except Exception as e:
        print(f"数据完整性检查失败: {str(e)}")
        integrity_report['error'] = str(e)
        return integrity_report

def save_integrity_report(report):
    """保存完整性报告到文件"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"data_integrity_report_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n完整性报告已保存到: {filename}")
    return filename

def main():
    print('=== 数据库完整性验证开始 ===')
    report = check_table_integrity()
    report_file = save_integrity_report(report)
    print('=== 数据库完整性验证完成 ===')
    return report

if __name__ == '__main__':
    main()