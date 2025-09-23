#!/usr/bin/env python3
"""
RAGAS 子进程评估器
通过子进程调用来避免事件循环冲突
"""

import json
import subprocess
import tempfile
import os
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class RAGASSubprocessEvaluator:
    """
    使用子进程的 RAGAS 评估器
    """
    
    def __init__(self):
        self.script_path = os.path.join(os.path.dirname(__file__), "ragas_standalone_script.py")
        
    def run_evaluation(self, test_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        运行 RAGAS 评估
        """
        try:
            # 创建临时文件保存测试数据
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(test_data, f, ensure_ascii=False, indent=2)
                temp_file = f.name
            
            try:
                # 调用独立的评估脚本
                result = subprocess.run([
                    'python', self.script_path, temp_file
                ], capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0:
                    # 解析结果
                    evaluation_result = json.loads(result.stdout)
                    logger.info(f"RAGAS 评估成功完成")
                    return evaluation_result
                else:
                    error_msg = f"RAGAS 评估失败: {result.stderr}"
                    logger.error(error_msg)
                    return {
                        "status": "error",
                        "error": error_msg,
                        "overall_score": 0.0
                    }
                    
            finally:
                # 清理临时文件
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    
        except subprocess.TimeoutExpired:
            error_msg = "RAGAS 评估超时"
            logger.error(error_msg)
            return {
                "status": "error", 
                "error": error_msg,
                "overall_score": 0.0
            }
        except Exception as e:
            error_msg = f"RAGAS 评估异常: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "error",
                "error": error_msg,
                "overall_score": 0.0
            }
    
    def health_check(self) -> Dict[str, Any]:
        """
        健康检查
        """
        try:
            # 测试子进程是否可用
            result = subprocess.run([
                'python', '-c', 'import ragas; print("RAGAS available")'
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return {
                    "status": "healthy",
                    "message": "RAGAS 子进程评估器正常"
                }
            else:
                return {
                    "status": "unhealthy",
                    "message": f"RAGAS 不可用: {result.stderr}"
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"健康检查失败: {str(e)}"
            }