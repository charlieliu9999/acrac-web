#!/usr/bin/env python3
"""
使用真实RAG+LLM推理API数据进行RAGAS评测
"""

import os
import sys
import json
import requests
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'real_rag_evaluation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)

# API配置
API_BASE = "http://127.0.0.1:8000/api/v1"
RAG_API_URL = f"{API_BASE}/acrac/rag-llm/intelligent-recommendation"

def load_environment():
    """加载环境变量"""
    env_file = project_root / ".env"
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        logger.info("✅ 环境变量加载完成")
    else:
        logger.warning("⚠️ .env文件不存在")

def call_real_rag_api(clinical_query: str, ground_truth: str = "") -> Dict[str, Any]:
    """调用真实的RAG+LLM推理API"""
    try:
        payload = {
            "clinical_query": clinical_query,
            "include_raw_data": True,
            "debug_mode": True,
            "top_scenarios": 5,
            "top_recommendations_per_scenario": 3,
            "show_reasoning": True,
            "similarity_threshold": 0.6,
            "compute_ragas": False,  # 我们自己计算RAGAS
            "ground_truth": ground_truth
        }
        
        logger.info(f"调用RAG API: {clinical_query[:50]}...")
        response = requests.post(RAG_API_URL, json=payload, timeout=120)
        response.raise_for_status()
        
        result = response.json()
        if result.get("success"):
            logger.info("✅ RAG API调用成功")
            return result
        else:
            logger.error(f"❌ RAG API调用失败: {result.get('message', '未知错误')}")
            return {}
            
    except Exception as e:
        logger.error(f"❌ RAG API调用异常: {e}")
        return {}

def extract_contexts_from_trace(trace_data: Dict[str, Any]) -> List[str]:
    """从trace数据中提取上下文"""
    contexts = []
    
    # 从scenarios中提取
    scenarios = trace_data.get("scenarios", [])
    for scenario in scenarios:
        if isinstance(scenario, dict):
            desc = scenario.get("description_zh", "")
            if desc:
                contexts.append(desc)
    
    # 从scenarios_with_recommendations中提取
    scenarios_with_recs = trace_data.get("scenarios_with_recommendations", [])
    for scenario in scenarios_with_recs:
        if isinstance(scenario, dict):
            desc = scenario.get("description_zh", "")
            if desc and desc not in contexts:
                contexts.append(desc)
    
    return contexts

def convert_to_ragas_format(rag_result: Dict[str, Any], clinical_query: str, ground_truth: str) -> Dict[str, Any]:
    """将RAG API结果转换为RAGAS评测格式"""
    
    # 提取LLM推荐结果作为答案
    llm_recommendations = rag_result.get("llm_recommendations", {})
    recommendations = llm_recommendations.get("recommendations", [])
    
    # 构造答案文本
    answer_parts = []
    if llm_recommendations.get("summary"):
        answer_parts.append(f"推荐总结: {llm_recommendations['summary']}")
    
    for i, rec in enumerate(recommendations[:3], 1):
        rec_text = f"{i}. {rec.get('procedure_name', '未知检查')} (评分: {rec.get('appropriateness_rating', 'N/A')})"
        if rec.get('recommendation_reason'):
            rec_text += f" - {rec['recommendation_reason']}"
        answer_parts.append(rec_text)
    
    answer = "\n".join(answer_parts) if answer_parts else json.dumps(llm_recommendations, ensure_ascii=False)
    
    # 提取上下文
    contexts = []
    
    # 从trace中提取
    trace_data = rag_result.get("trace", {})
    if trace_data:
        contexts.extend(extract_contexts_from_trace(trace_data))
    
    # 从scenarios中提取
    scenarios = rag_result.get("scenarios", [])
    for scenario in scenarios:
        if isinstance(scenario, dict):
            desc = scenario.get("description_zh", "")
            if desc and desc not in contexts:
                contexts.append(desc)
    
    # 如果没有上下文，使用默认值
    if not contexts:
        contexts = ["无可用上下文信息"]
    
    return {
        "question": clinical_query,
        "answer": answer,
        "contexts": contexts,
        "ground_truth": ground_truth
    }

def run_ragas_evaluation(ragas_data: Dict[str, Any]) -> Dict[str, float]:
    """运行RAGAS评测"""
    try:
        # 使用项目中已有的RAGAS评估器
        from app.services.ragas_evaluator import RAGASEvaluator
        
        logger.info("初始化RAGAS评估器...")
        evaluator = RAGASEvaluator()
        
        # 创建测试样本
        test_sample = evaluator.create_test_sample(
            question=ragas_data["question"],
            answer=ragas_data["answer"],
            contexts=ragas_data["contexts"],
            ground_truth=ragas_data["ground_truth"]
        )
        
        # 运行单样本评测
        logger.info("开始RAGAS评测...")
        scores = evaluator.evaluate_single_sample(test_sample)
        
        logger.info("✅ RAGAS评测完成")
        return scores
        
    except ImportError as e:
        logger.warning(f"⚠️ RAGAS库未安装或配置不正确: {e}")
        return {
            "faithfulness": 0.0,
            "answer_relevancy": 0.0,
            "context_precision": 0.0,
            "context_recall": 0.0
        }
    except Exception as e:
        logger.error(f"❌ RAGAS评测失败: {e}")
        return {
            "faithfulness": 0.0,
            "answer_relevancy": 0.0,
            "context_precision": 0.0,
            "context_recall": 0.0
        }

def save_evaluation_result(result: Dict[str, Any], filename: str = None):
    """保存评测结果"""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"real_rag_evaluation_result_{timestamp}.json"
    
    output_path = project_root / "uploads" / "ragas" / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ 评测结果已保存: {output_path}")
    return output_path

def main():
    """主函数"""
    logger.info("🚀 开始真实RAG+LLM数据的RAGAS评测")
    
    # 加载环境变量
    load_environment()
    
    # 使用用户提供的真实数据示例
    test_case = {
        "clinical_query": "50岁女性，3天前开始出现左侧肢体无力，伴新发头痛。",
        "ground_truth": "MR颅脑(平扫+增强)"
    }
    
    logger.info(f"测试用例: {test_case['clinical_query']}")
    logger.info(f"标准答案: {test_case['ground_truth']}")
    
    # 1. 调用真实RAG API
    logger.info("📡 调用真实RAG+LLM推理API...")
    rag_result = call_real_rag_api(
        clinical_query=test_case["clinical_query"],
        ground_truth=test_case["ground_truth"]
    )
    
    if not rag_result:
        logger.error("❌ 无法获取RAG推理结果，退出")
        return
    
    # 2. 转换为RAGAS格式
    logger.info("🔄 转换数据格式...")
    ragas_data = convert_to_ragas_format(
        rag_result=rag_result,
        clinical_query=test_case["clinical_query"],
        ground_truth=test_case["ground_truth"]
    )
    
    logger.info(f"转换后的数据:")
    logger.info(f"  问题: {ragas_data['question'][:100]}...")
    logger.info(f"  答案: {ragas_data['answer'][:100]}...")
    logger.info(f"  上下文数量: {len(ragas_data['contexts'])}")
    logger.info(f"  标准答案: {ragas_data['ground_truth']}")
    
    # 3. 运行RAGAS评测
    logger.info("📊 运行RAGAS评测...")
    ragas_scores = run_ragas_evaluation(ragas_data)
    
    # 4. 构造完整结果
    evaluation_result = {
        "timestamp": datetime.now().isoformat(),
        "test_case": test_case,
        "rag_api_result": {
            "success": rag_result.get("success"),
            "processing_time_ms": rag_result.get("processing_time_ms"),
            "model_used": rag_result.get("model_used"),
            "similarity_threshold": rag_result.get("similarity_threshold"),
            "max_similarity": rag_result.get("max_similarity"),
            "is_low_similarity_mode": rag_result.get("is_low_similarity_mode"),
            "llm_recommendations": rag_result.get("llm_recommendations"),
            "scenarios_count": len(rag_result.get("scenarios", [])),
        },
        "ragas_data": ragas_data,
        "ragas_scores": ragas_scores,
        "evaluation_summary": {
            "avg_score": sum(ragas_scores.values()) / len(ragas_scores) if ragas_scores else 0,
            "best_metric": max(ragas_scores.items(), key=lambda x: x[1]) if ragas_scores else ("none", 0),
            "worst_metric": min(ragas_scores.items(), key=lambda x: x[1]) if ragas_scores else ("none", 0),
        }
    }
    
    # 5. 保存结果
    output_path = save_evaluation_result(evaluation_result)
    
    # 6. 输出总结
    logger.info("📋 评测结果总结:")
    logger.info(f"  Faithfulness: {ragas_scores.get('faithfulness', 0):.3f}")
    logger.info(f"  Answer Relevancy: {ragas_scores.get('answer_relevancy', 0):.3f}")
    logger.info(f"  Context Precision: {ragas_scores.get('context_precision', 0):.3f}")
    logger.info(f"  Context Recall: {ragas_scores.get('context_recall', 0):.3f}")
    logger.info(f"  平均分: {evaluation_result['evaluation_summary']['avg_score']:.3f}")
    
    logger.info("🎉 真实RAG+LLM数据的RAGAS评测完成!")
    return output_path

if __name__ == "__main__":
    main()