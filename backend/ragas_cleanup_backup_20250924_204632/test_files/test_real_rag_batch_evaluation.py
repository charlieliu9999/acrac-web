#!/usr/bin/env python3
"""
批量使用真实RAG+LLM推理API数据进行RAGAS评测
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
        logging.FileHandler(f'real_rag_batch_evaluation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
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
            "compute_ragas": False,
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

def run_ragas_evaluation(ragas_data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """运行批量RAGAS评测"""
    try:
        # 使用项目中已有的RAGAS评估器
        from app.services.ragas_evaluator_v2 import ACRACRAGASEvaluator
        
        logger.info("初始化RAGAS评估器...")
        evaluator = ACRACRAGASEvaluator()
        
        # 创建测试样本列表
        test_samples = []
        for ragas_data in ragas_data_list:
            test_sample = {
                "question": ragas_data["question"],
                "answer": ragas_data["answer"],
                "contexts": ragas_data["contexts"],
                "ground_truth": ragas_data["ground_truth"]
            }
            test_samples.append(test_sample)
        
        # 运行批量评测
        logger.info(f"开始批量RAGAS评测，共{len(test_samples)}个样本...")
        results = evaluator.evaluate_batch(test_samples)
        
        logger.info("✅ 批量RAGAS评测完成")
        return results
        
    except ImportError as e:
        logger.warning(f"⚠️ RAGAS库未安装或配置不正确: {e}")
        return {
            "avg_scores": {
                "faithfulness": 0.0,
                "answer_relevancy": 0.0,
                "context_precision": 0.0,
                "context_recall": 0.0
            },
            "individual_scores": [],
            "total_samples": 0,
            "overall_score": 0.0
        }
    except Exception as e:
        logger.error(f"❌ 批量RAGAS评测失败: {e}")
        return {
            "avg_scores": {
                "faithfulness": 0.0,
                "answer_relevancy": 0.0,
                "context_precision": 0.0,
                "context_recall": 0.0
            },
            "individual_scores": [],
            "total_samples": 0,
            "overall_score": 0.0
        }

def save_evaluation_result(result: Dict[str, Any], filename: str = None):
    """保存评测结果"""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"real_rag_batch_evaluation_result_{timestamp}.json"
    
    output_path = project_root / "uploads" / "ragas" / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ 评测结果已保存: {output_path}")
    return output_path

def main():
    """主函数"""
    logger.info("🚀 开始批量真实RAG+LLM数据的RAGAS评测")
    
    # 加载环境变量
    load_environment()
    
    # 定义多个测试用例
    test_cases = [
        {
            "clinical_query": "50岁女性，3天前开始出现左侧肢体无力，伴新发头痛。",
            "ground_truth": "MR颅脑(平扫+增强)"
        },
        {
            "clinical_query": "35岁男性，急性胸痛，疑似心肌梗死。",
            "ground_truth": "CT冠状动脉成像"
        },
        {
            "clinical_query": "60岁女性，慢性咳嗽3个月，伴体重下降。",
            "ground_truth": "CT胸部(平扫+增强)"
        },
        {
            "clinical_query": "25岁女性，急性腹痛，右下腹压痛明显。",
            "ground_truth": "CT腹部(平扫)"
        },
        {
            "clinical_query": "45岁男性，反复头晕，伴听力下降。",
            "ground_truth": "MR内耳(平扫+增强)"
        }
    ]
    
    logger.info(f"测试用例数量: {len(test_cases)}")
    
    # 批量处理测试用例
    all_rag_results = []
    all_ragas_data = []
    
    for i, test_case in enumerate(test_cases, 1):
        logger.info(f"处理第{i}/{len(test_cases)}个测试用例...")
        logger.info(f"临床查询: {test_case['clinical_query']}")
        logger.info(f"标准答案: {test_case['ground_truth']}")
        
        # 1. 调用真实RAG API
        rag_result = call_real_rag_api(
            clinical_query=test_case["clinical_query"],
            ground_truth=test_case["ground_truth"]
        )
        
        if not rag_result:
            logger.warning(f"⚠️ 第{i}个测试用例RAG API调用失败，跳过")
            continue
        
        # 2. 转换为RAGAS格式
        ragas_data = convert_to_ragas_format(
            rag_result=rag_result,
            clinical_query=test_case["clinical_query"],
            ground_truth=test_case["ground_truth"]
        )
        
        all_rag_results.append({
            "test_case": test_case,
            "rag_result": rag_result,
            "ragas_data": ragas_data
        })
        all_ragas_data.append(ragas_data)
        
        logger.info(f"✅ 第{i}个测试用例数据准备完成")
    
    if not all_ragas_data:
        logger.error("❌ 没有成功处理的测试用例，退出")
        return
    
    # 3. 运行批量RAGAS评测
    logger.info("📊 运行批量RAGAS评测...")
    ragas_results = run_ragas_evaluation(all_ragas_data)
    
    # 4. 构造完整结果
    evaluation_result = {
        "timestamp": datetime.now().isoformat(),
        "test_cases_count": len(test_cases),
        "successful_cases_count": len(all_rag_results),
        "test_cases": all_rag_results,
        "ragas_evaluation": ragas_results,
        "summary": {
            "avg_scores": ragas_results.get("avg_scores", {}),
            "overall_score": ragas_results.get("overall_score", 0.0),
            "total_samples": ragas_results.get("total_samples", 0),
            "best_performing_metric": None,
            "worst_performing_metric": None
        }
    }
    
    # 分析最佳和最差指标
    avg_scores = ragas_results.get("avg_scores", {})
    if avg_scores:
        best_metric = max(avg_scores.items(), key=lambda x: x[1])
        worst_metric = min(avg_scores.items(), key=lambda x: x[1])
        evaluation_result["summary"]["best_performing_metric"] = best_metric
        evaluation_result["summary"]["worst_performing_metric"] = worst_metric
    
    # 5. 保存结果
    output_path = save_evaluation_result(evaluation_result)
    
    # 6. 输出总结
    logger.info("📋 批量评测结果总结:")
    logger.info(f"  测试用例总数: {len(test_cases)}")
    logger.info(f"  成功处理数: {len(all_rag_results)}")
    logger.info(f"  平均评分:")
    for metric, score in avg_scores.items():
        logger.info(f"    {metric}: {score:.3f}")
    logger.info(f"  综合评分: {ragas_results.get('overall_score', 0):.3f}")
    
    if evaluation_result["summary"]["best_performing_metric"]:
        best_name, best_score = evaluation_result["summary"]["best_performing_metric"]
        logger.info(f"  最佳指标: {best_name} ({best_score:.3f})")
    
    if evaluation_result["summary"]["worst_performing_metric"]:
        worst_name, worst_score = evaluation_result["summary"]["worst_performing_metric"]
        logger.info(f"  最差指标: {worst_name} ({worst_score:.3f})")
    
    logger.info("🎉 批量真实RAG+LLM数据的RAGAS评测完成!")
    return output_path

if __name__ == "__main__":
    main()