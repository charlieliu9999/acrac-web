#!/usr/bin/env python3
"""
创建新的数据库表结构
包括EvaluationProject表和为现有表添加project_id字段
"""

import os
import sys
from sqlalchemy import create_engine, text, MetaData, Table, Column, String, DateTime, Boolean, Text, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 直接使用数据库URL，避免复杂配置
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@127.0.0.1:5432/acrac_db")

def create_tables():
    """创建所有表"""
    try:
        logger.info("开始创建数据库表...")
        
        # 创建数据库引擎
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # 创建evaluation_projects表
            logger.info("创建evaluation_projects表...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS evaluation_projects (
                    id SERIAL PRIMARY KEY,
                    project_id VARCHAR(50) UNIQUE NOT NULL,
                    project_name VARCHAR(200) NOT NULL,
                    excel_filename VARCHAR(500),
                    description TEXT,
                    status VARCHAR(20) DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # 检查inference_logs表的project_id字段
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'inference_logs' 
                AND column_name = 'project_id'
            """))
            if not result.fetchone():
                logger.info("添加inference_logs表的project_id字段...")
                conn.execute(text("""
                    ALTER TABLE inference_logs 
                    ADD COLUMN project_id VARCHAR(50) 
                """))
                logger.info("✓ inference_logs表的project_id字段添加成功")
            else:
                logger.info("✓ inference_logs表的project_id字段已存在")
            
            # 检查excel_evaluation_data表的project_id字段
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'excel_evaluation_data' 
                AND column_name = 'project_id'
            """))
            if not result.fetchone():
                logger.info("添加excel_evaluation_data表的project_id字段...")
                conn.execute(text("""
                    ALTER TABLE excel_evaluation_data 
                    ADD COLUMN project_id VARCHAR(50) DEFAULT 'default'
                """))
                logger.info("✓ excel_evaluation_data表的project_id字段添加成功")
            else:
                logger.info("✓ excel_evaluation_data表的project_id字段已存在")
            
            # 提交所有更改
            conn.commit()
            
            # 验证表创建
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'evaluation_projects'
            """))
            if result.fetchone():
                logger.info("✓ evaluation_projects表创建成功")
            else:
                logger.warning("✗ evaluation_projects表未找到")
        
        logger.info("所有数据库表结构更新完成")
        return True
        
    except Exception as e:
        logger.error(f"创建数据库表失败: {e}")
        return False

if __name__ == "__main__":
    success = create_tables()
    if success:
        print("✓ 数据库表创建/更新成功")
        sys.exit(0)
    else:
        print("✗ 数据库表创建/更新失败")
        sys.exit(1)