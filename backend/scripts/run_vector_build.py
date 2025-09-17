#!/usr/bin/env python3
"""
ACRAC向量数据库构建运行脚本
简化版本，用于快速测试和部署
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.ACRAC完整数据库向量库构建方案 import CompleteDataBuilder
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """主函数"""
    logger.info("🚀 ACRAC向量数据库构建工具")
    logger.info("=" * 60)
    
    # 数据库配置
    db_config = {
        "host": "localhost",
        "port": "5432", 
        "database": "acrac_db",
        "user": "postgres",
        "password": "password"
    }
    
    # CSV文件路径
    csv_file = "../../ACR_data/ACR_final.csv"
    
    # 检查CSV文件是否存在
    if not os.path.exists(csv_file):
        logger.error(f"❌ CSV文件不存在: {csv_file}")
        logger.info("请确保ACR_final.csv文件在正确位置")
        return 1
    
    # 创建构建器
    builder = CompleteDataBuilder(db_config)
    
    try:
        # 连接数据库
        if not builder.connect():
            logger.error("❌ 无法连接到数据库")
            return 1
        
        # 创建完整架构
        logger.info("📝 步骤1: 创建数据库架构")
        if not builder.create_complete_schema():
            logger.error("❌ 创建数据库架构失败")
            return 1
        
        # 创建基础索引
        logger.info("📝 步骤2: 创建基础索引")
        if not builder.create_basic_indexes():
            logger.error("❌ 创建基础索引失败")
            return 1
        
        # 加载CSV数据
        logger.info("📝 步骤3: 加载CSV数据")
        df = builder.load_csv_data(csv_file)
        if df is None:
            logger.error("❌ 加载CSV数据失败")
            return 1
        
        # 构建完整数据库
        logger.info("📝 步骤4: 构建完整数据库")
        if not builder.build_complete_database(df):
            logger.error("❌ 构建数据库失败")
            return 1
        
        # 验证结果
        logger.info("📝 步骤5: 验证构建结果")
        verification = builder.verify_build()
        
        logger.info("\n🎉 向量数据库构建完成!")
        logger.info("=" * 60)
        logger.info(f"📊 最终统计: {builder.stats}")
        
        # 输出验证信息
        if verification:
            logger.info("\n📋 验证结果:")
            for key, value in verification.items():
                if key.endswith('_count'):
                    logger.info(f"   {key}: {value}")
                elif key.endswith('_coverage'):
                    logger.info(f"   {key}: {value}")
        
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ 构建失败: {e}")
        return 1
    
    finally:
        builder.disconnect()

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
