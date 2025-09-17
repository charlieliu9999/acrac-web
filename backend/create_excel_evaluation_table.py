#!/usr/bin/env python3
"""
创建Excel评测数据表的迁移脚本
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import engine
from app.models.system_models import ExcelEvaluationData
from sqlalchemy import text

def create_excel_evaluation_table():
    """创建Excel评测数据表"""
    try:
        # 创建表
        ExcelEvaluationData.metadata.create_all(bind=engine)
        print("✅ Excel评测数据表创建成功")
        
        # 验证表是否创建成功
        with engine.connect() as conn:
            result = conn.execute(text("SELECT tablename FROM pg_tables WHERE tablename='excel_evaluation_data'"))
            if result.fetchone():
                print("✅ 表结构验证成功")
            else:
                print("❌ 表创建失败")
                
    except Exception as e:
        print(f"❌ 创建表失败: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("开始创建Excel评测数据表...")
    success = create_excel_evaluation_table()
    if success:
        print("🎉 数据库迁移完成")
    else:
        print("💥 数据库迁移失败")
        sys.exit(1)