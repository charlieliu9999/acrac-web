#!/usr/bin/env python3
"""
独立的 RAGAS 评估脚本
在独立进程中运行，避免事件循环冲突
"""

import sys
import json
import asyncio
import logging
from typing import Dict, List, Any

# 设置事件循环策略
if sys.platform.startswith('darwin'):  # macOS
    try:
        import uvloop
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    except ImportError:
        pass

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_ragas_evaluation(test_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    运行 RAGAS 评估
    """
    try:
        # 导入 RAGAS 相关模块
        from ragas_evaluator import RAGASEvaluator
        
        # 初始化评估器
        evaluator = RAGASEvaluator()
        logger.info("RAGAS 评估器初始化成功")
        
        # 运行评估
        result = evaluator.run_evaluation(test_data)
        logger.info(f"评估完成，综合评分: {result.get('overall_score', 'N/A')}")
        
        return result
        
    except Exception as e:
        logger.error(f"RAGAS 评估失败: {e}")
        return {
            "status": "error",
            "error": str(e),
            "overall_score": 0.0,
            "metrics": {}
        }

def main():
    """
    主函数
    """
    if len(sys.argv) != 2:
        print(json.dumps({
            "status": "error",
            "error": "Usage: python ragas_standalone_script.py <test_data_file>",
            "overall_score": 0.0
        }))
        sys.exit(1)
    
    test_data_file = sys.argv[1]
    
    try:
        # 读取测试数据
        with open(test_data_file, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        
        # 运行评估
        result = run_ragas_evaluation(test_data)
        
        # 输出结果
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
    except Exception as e:
        error_result = {
            "status": "error",
            "error": str(e),
            "overall_score": 0.0
        }
        print(json.dumps(error_result, ensure_ascii=False, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()