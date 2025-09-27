#!/usr/bin/env python3
"""验证RAGAS数据库表是否创建成功"""

from app.core.database import engine
from sqlalchemy import text

def verify_ragas_tables():
    """验证RAGAS相关表是否创建成功"""
    try:
        with engine.connect() as conn:
            # 查询所有RAGAS相关表
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema =