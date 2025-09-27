#!/usr/bin/env python3
"""
测试qwen2.5-32b模型的RAGAS评测结果输出
验证评测系统是否正确工作
"""

import os
import sys
import json
import time
import logging
import requests
from typing import Dict, List, Any
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API配置
API_BASE = "http://127.0.0.1:8000/api/v1"
HEADERS = {"Content-Type": "application/json"}

def check_model_config():
    """检查模型配置"""
    logger.info("=== 检查qwen2.5-32b模型配置 ===")
    
    # 检查环境变量
    env_vars = [
        "SILICONFLOW_LLM_MODEL",
        "RAGAS_DEFAULT_LLM_MODEL", 
        "SILICONFLOW_API_KEY",
        "OPENAI_API_KEY"
    ]
    
    for var in env_vars:
        value = os.getenv(var, "未设置")
        logger.info(f"{var}: {value}")
    
    return True

def test_ragas_health():
    """测试RAGAS健康检查"""
    logger.info("=== 测试RAGAS健康检查 ===")
    
    try:
        response = requests.get(f"{API_BASE}/ragas-standalone/health", headers=HEADERS, timeout=30)
        logger.info(f"健康检查状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"健康检查结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return True
        else:
            logger.error(f"健康检查失败: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"健康检查异常: {e}")
        return False

def create_test_sample():
    """创建测试样本"""
    return {
        "question": "45岁女性，慢性反复头痛3年，无神经系统异常体征。",
        "answer": "建议进行MR颅脑平扫检查，以排除颅内占位性病变。慢性头痛需要影像学评估。",
        "contexts": [
            "慢性头痛的影像学检查指南",
            "MR颅脑检查适应症包括慢性头痛患者",
            "无神经系统体征的头痛患者建议MR检查"
        ],
        "ground_truth": "MR颅脑(平扫)"
    }

def test_single_evaluation():
    """测试单个样本评测"""
    logger.info("=== 测试单个样本RAGAS评测 ===")
    
    # 创建测试数据
    test_sample = create_test_sample()
    logger.info(f"测试样本: {json.dumps(test_sample, indent=2, ensure_ascii=False)}")
    
    # 准备评测请求
    evaluation_request = {
        "test_cases": [test_sample],
        "model_name": "Qwen/Qwen2.5-32B-Instruct",
        "base_url": "https://api.siliconflow.cn/v1",
        "task_name": "qwen2.5-32b模型测试",
        "async_mode": False
    }
    
    try:
        logger.info("发送评测请求...")
        response = requests.post(
            f"{API_BASE}/ragas-standalone/evaluate",
            json={"test_data": [test_sample]},
            headers=HEADERS,
            timeout=120
        )
        
        logger.info(f"评测响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info("=== 评测结果 ===")
            logger.info(json.dumps(result, indent=2, ensure_ascii=False))
            
            # 分析结果
            if result.get("status") == "success" and "results" in result:
                avg_scores = result["results"].get("avg_scores", {})
                individual_scores = result["results"].get("individual_scores", [])
                
                logger.info("=== 平均评分分析 ===")
                for metric, score in avg_scores.items():
                    logger.info(f"{metric}: {score:.4f}")
                
                if individual_scores:
                    logger.info("=== 个体评分分析 ===")
                    for i, scores in enumerate(individual_scores):
                        logger.info(f"样本 {i+1}: {scores}")
                
                # 检查评分合理性
                check_score_validity(avg_scores)
                logger.info("✅ 单个样本评测成功")
                
            return result
        else:
            logger.error(f"评测失败: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"评测异常: {e}")
        return None

def check_score_validity(scores: Dict[str, float]):
    """检查评分的合理性"""
    logger.info("=== 评分合理性检查 ===")
    
    expected_metrics = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    
    for metric in expected_metrics:
        if metric in scores:
            score = scores[metric]
            if 0 <= score <= 1:
                logger.info(f"✅ {metric}: {score:.4f} (正常范围)")
            else:
                logger.warning(f"⚠️ {metric}: {score:.4f} (超出正常范围 [0,1])")
        else:
            logger.error(f"❌ 缺失指标: {metric}")
    
    # 检查是否有异常低分
    low_scores = [metric for metric, score in scores.items() if score < 0.1]
    if low_scores:
        logger.warning(f"⚠️ 异常低分指标: {low_scores}")
    
    # 检查是否有异常高分
    high_scores = [metric for metric, score in scores.items() if score > 0.95]
    if high_scores:
        logger.info(f"✅ 高分指标: {high_scores}")

def test_batch_evaluation():
    """测试批量评测"""
    logger.info("=== 测试批量评测 ===")
    
    # 创建多个测试样本
    test_samples = [
        {
            "question": "45岁女性，慢性反复头痛3年，无神经系统异常体征。",
            "answer": "建议进行MR颅脑平扫检查。",
            "contexts": ["慢性头痛影像学检查指南"],
            "ground_truth": "MR颅脑(平扫)"
        },
        {
            "question": "32岁男性，突发剧烈头痛，疑似蛛网膜下腔出血。",
            "answer": "建议立即进行CT颅脑平扫检查。",
            "contexts": ["急性头痛诊断指南", "蛛网膜下腔出血影像学特征"],
            "ground_truth": "CT颅脑(平扫)"
        }
    ]
    
    evaluation_request = {
        "test_cases": test_samples,
        "model_name": "Qwen/Qwen2.5-32B-Instruct",
        "task_name": "qwen2.5-32b批量测试",
        "async_mode": False
    }
    
    try:
        response = requests.post(
            f"{API_BASE}/ragas-standalone/evaluate",
            json={"test_data": test_samples},
            headers=HEADERS,
            timeout=180
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info("=== 批量评测结果 ===")
            logger.info(json.dumps(result, indent=2, ensure_ascii=False))
            
            if result.get("status") == "success" and "results" in result:
                total_samples = result["results"].get("total_samples", 0)
                avg_scores = result["results"].get("avg_scores", {})
                
                logger.info(f"✅ 批量评测成功，处理了 {total_samples} 个样本")
                
                logger.info("=== 批量评测平均分 ===")
                for metric, score in avg_scores.items():
                    logger.info(f"{metric}: {score:.4f}")
                
                # 检查评分合理性
                check_score_validity(avg_scores)
            
            return result
        else:
            logger.error(f"批量评测失败: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"批量评测异常: {e}")
        return None

def main():
    """主函数"""
    logger.info("开始测试qwen2.5-32b模型的RAGAS评测结果输出")
    
    # 1. 检查模型配置
    check_model_config()
    
    # 2. 测试健康检查
    health_ok = test_ragas_health()
    if not health_ok:
        logger.error("RAGAS健康检查失败，请检查服务状态")
        return
    
    # 3. 测试单个样本评测
    single_result = test_single_evaluation()
    if not single_result:
        logger.error("单个样本评测失败")
        return
    
    # 4. 测试批量评测
    batch_result = test_batch_evaluation()
    if not batch_result:
        logger.error("批量评测失败")
        return
    
    logger.info("=== 测试完成 ===")
    logger.info("qwen2.5-32b模型的RAGAS评测系统工作正常")

if __name__ == "__main__":
    main()