#!/usr/bin/env python3
"""
检查数据库表结构脚本
"""

import os
import json
import psycopg2
from dotenv import load_dotenv

def main():
    """检查数据库表结构"""
    
    # 加载环境变量
    load_dotenv()
    
    # 获取数据库连接参数
    db_params = {
        'host': os.getenv('PGHOST', '127.0.0.1'),
        'port': os.getenv('PGPORT', '5432'),
        'database': os.getenv('PGDATABASE', 'acrac_db'),
        'user': os.getenv('PGUSER', 'postgres'),
        'password': os.getenv('PGPASSWORD', 'password')
    }
    
    try:
        # 连接数据库
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        
        print("=== 检查数据库表结构 ===\n")
        
        # 1. 检查scenario_results表结构
        print("1. scenario_results表结构:")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'scenario_results'
            ORDER BY ordinal_position
        """)
        
        columns = cursor.fetchall()
        if columns:
            for col_name, data_type, nullable, default in columns:
                print(f"   {col_name}: {data_type} (nullable: {nullable}, default: {default})")
        else:
            print("   表不存在或无列信息")
        
        print()
        
        # 2. 检查evaluation_tasks表结构
        print("2. evaluation_tasks表结构:")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'evaluation_tasks'
            ORDER BY ordinal_position
        """)
        
        columns = cursor.fetchall()
        if columns:
            for col_name, data_type, nullable, default in columns:
                print(f"   {col_name}: {data_type} (nullable: {nullable}, default: {default})")
        else:
            print("   表不存在或无列信息")
        
        print()
        
        # 3. 查看scenario_results表的实际数据
        print("3. scenario_results表的数据样本:")
        cursor.execute("""
            SELECT * FROM scenario_results 
            ORDER BY created_at DESC 
            LIMIT 3
        """)
        
        results = cursor.fetchall()
        if results:
            # 获取列名
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns 
                WHERE table_name = 'scenario_results'
                ORDER BY ordinal_position
            """)
            column_names = [row[0] for row in cursor.fetchall()]
            
            for i, result in enumerate(results, 1):
                print(f"   记录 {i}:")
                for j, value in enumerate(result):
                    col_name = column_names[j] if j < len(column_names) else f"col_{j}"
                    if isinstance(value, str) and len(value) > 100:
                        print(f"     {col_name}: {value[:100]}...")
                    else:
                        print(f"     {col_name}: {value}")
                print()
        else:
            print("   无数据")
        
        # 4. 查看是否有包含推理数据的字段
        print("4. 查找可能包含推理数据的字段:")
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns 
            WHERE table_name = 'scenario_results'
            AND (column_name LIKE '%data%' OR column_name LIKE '%result%' OR column_name LIKE '%content%')
            ORDER BY ordinal_position
        """)
        
        data_columns = cursor.fetchall()
        if data_columns:
            for col_name, data_type in data_columns:
                print(f"   {col_name}: {data_type}")
                
                # 查看这个字段的样本数据
                cursor.execute(f"""
                    SELECT {col_name} FROM scenario_results 
                    WHERE {col_name} IS NOT NULL 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """)
                sample = cursor.fetchone()
                if sample and sample[0]:
                    sample_data = sample[0]
                    if isinstance(sample_data, str) and len(sample_data) > 200:
                        print(f"     样本: {sample_data[:200]}...")
                    else:
                        print(f"     样本: {sample_data}")
                print()
        else:
            print("   未找到相关字段")
        
    except Exception as e:
        print(f"检查表结构时出错: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()