#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库连接测试脚本
测试PostgreSQL连接状态和pgvector扩展可用性
"""

from app.core.database import engine, test_db_connection
import sqlalchemy as sa

def main():
    print('=== 数据库连接测试 ===')
    try:
        success = test_db_connection()
        print(f'连接状态: {"成功" if success else "失败"}')
        
        if success:
            print('\n=== 检查pgvector扩展 ===')
            with engine.connect() as conn:
                # 检查pgvector扩展
                result = conn.execute(sa.text("SELECT extname FROM pg_extension WHERE extname = 'vector';")).fetchone()
                print(f'pgvector扩展: {"已安装" if result else "未安装"}')
                
                print('\n=== 数据库版本信息 ===')
                version = conn.execute(sa.text('SELECT version();')).fetchone()[0]
                print(f'PostgreSQL版本: {version}')
                
                print('\n=== 检查现有表 ===')
                tables_result = conn.execute(sa.text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name;
                """)).fetchall()
                
                if tables_result:
                    print('现有数据表:')
                    for table in tables_result:
                        print(f'  - {table[0]}')
                else:
                    print('未找到任何数据表')
                    
    except Exception as e:
        print(f'数据库连接测试失败: {str(e)}')
        return False
    
    return success

if __name__ == '__main__':
    main()