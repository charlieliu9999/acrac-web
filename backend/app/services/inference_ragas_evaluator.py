#!/usr/bin/env python3
"""
推理数据 RAGAS 评估器
专门评测检查项目推荐推理数据，使用真实的 RAGAS 评测方案
"""
import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

try:
    from ragas.dataset_schema import SingleTurnSample
    from ragas.metrics import Faithfulness, ContextPrecision, ContextRecall, AnswerRelevancy
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    RAGAS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"RAGAS相关依赖未安装: {e}")
    RAGAS_AVAILABLE = False

logger = logging.getLogger(__name__)


class EvaluationStatus(Enum):
    """评测状态枚举"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ModelConfig:
    """模型配置"""
    llm_model: str = "Qwen/Qwen2.5-32B-Instruct"
    embedding_model: str = "BAAI/bge-m3"
    api_key: str = ""
    base_url: str = "https://api.siliconflow.cn/v1"
    temperature: float = 0.1
    timeout: int = 60
    max_retries: int = 2


@dataclass
class EvaluationResult:
    """评测结果"""
    sample_id: str
    metrics: Dict[str, float]
    status: EvaluationStatus
    error_message: Optional[str] = None
    processing_info: Dict[str, Any] = None
    created_at: str = ""


class InferenceRAGASEvaluator:
    """推理数据 RAGAS 评估器"""
    
    def __init__(self, model_config: Optional[ModelConfig] = None):
        """初始化评估器"""
        if not RAGAS_AVAILABLE:
            raise ImportError("RAGAS相关依赖未安装")
        
        # 设置事件循环兼容性
        self._setup_event_loop()
        
        # 加载配置
        self.model_config = model_config or self._load_default_config()
        
        # 初始化模型
        self._init_models()
        
        # 初始化评测指标
        self._init_metrics()
        
        logger.info(f"推理数据 RAGAS 评估器初始化完成 - LLM: {self.model_config.llm_model}")
    
    def _setup_event_loop(self):
        """设置事件循环兼容性"""
        try:
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        except Exception as e:
            logger.warning(f"事件循环设置失败: {e}")
    
    def _load_default_config(self) -> ModelConfig:
        """加载默认配置"""
        api_key = os.getenv("SILICONFLOW_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("未找到API密钥，请设置 SILICONFLOW_API_KEY")
        
        return ModelConfig(
            api_key=api_key,
            base_url=os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
            llm_model=os.getenv("SILICONFLOW_LLM_MODEL", "Qwen/Qwen2.5-32B-Instruct"),
            embedding_model=os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3")
        )
    
    def _init_models(self):
        """初始化LLM和嵌入模型"""
        self.llm = ChatOpenAI(
            model=self.model_config.llm_model,
            api_key=self.model_config.api_key,
            base_url=self.model_config.base_url,
            temperature=self.model_config.temperature,
            timeout=self.model_config.timeout,
            max_retries=self.model_config.max_retries
        )
        
        self.embeddings = OpenAIEmbeddings(
            model=self.model_config.embedding_model,
            api_key=self.model_config.api_key,
            base_url=self.model_config.base_url,
            timeout=self.model_config.timeout,
            max_retries=self.model_config.max_retries
        )
    
    def _init_metrics(self):
        """初始化评测指标"""
        # 使用默认的 LLM 和 embeddings
        self.metrics = {
            'faithfulness': Faithfulness(),
            'context_precision': ContextPrecision(),
            'context_recall': ContextRecall(),
            'answer_relevancy': AnswerRelevancy()
        }
        
        logger.info(f"初始化评测指标: {list(self.metrics.keys())}")
    
    def create_sample(self, data: Dict[str, Any]) -> SingleTurnSample:
        """创建RAGAS样本对象"""
        question = str(data.get('question', ''))
        answer = str(data.get('answer', ''))
        contexts = data.get('contexts', [])
        ground_truth = str(data.get('ground_truth', ''))
        
        # 确保contexts是字符串列表
        if isinstance(contexts, str):
            contexts = [contexts]
        elif not isinstance(contexts, list):
            contexts = [str(contexts)]
        
        # 过滤空的上下文
        contexts = [ctx for ctx in contexts if ctx and str(ctx).strip()]
        if not contexts:
            contexts = ["相关检查项目知识"]  # 默认上下文
        
        return SingleTurnSample(
            user_input=question,
            response=answer,
            retrieved_contexts=contexts,
            reference=ground_truth
        )
    
    async def evaluate_sample(self, data: Dict[str, Any]) -> EvaluationResult:
        """评测单个样本"""
        try:
            sample = self.create_sample(data)
            sample_id = data.get('id', f"sample_{hash(str(data))}")
            
            logger.info(f"开始评测样本: {sample_id}")
            
            # 使用真实的 RAGAS 评测方法
            results = {}
            
            # 评测忠实度
            try:
                # 使用 RAGAS 的 evaluate 方法
                from ragas import evaluate
                faithfulness_result = await evaluate(
                    [sample],
                    metrics=[self.metrics['faithfulness']]
                )
                logger.info(f"忠实度评测原始结果: {type(faithfulness_result)}, {faithfulness_result}")
                # 从结果中提取分数
                if 'faithfulness' in faithfulness_result:
                    results['faithfulness'] = float(faithfulness_result['faithfulness'][0])
                else:
                    results['faithfulness'] = 0.0
                logger.info(f"忠实度评测完成: {results['faithfulness']:.4f}")
            except Exception as e:
                logger.error(f"忠实度评测失败: {e}")
                results['faithfulness'] = 0.0
            
            # 评测上下文精确度
            try:
                context_precision_result = await evaluate(
                    [sample],
                    metrics=[self.metrics['context_precision']]
                )
                if 'context_precision' in context_precision_result:
                    results['context_precision'] = float(context_precision_result['context_precision'][0])
                else:
                    results['context_precision'] = 0.0
                logger.info(f"上下文精确度评测完成: {results['context_precision']:.4f}")
            except Exception as e:
                logger.error(f"上下文精确度评测失败: {e}")
                results['context_precision'] = 0.0
            
            # 评测上下文召回率
            try:
                context_recall_result = await evaluate(
                    [sample],
                    metrics=[self.metrics['context_recall']]
                )
                if 'context_recall' in context_recall_result:
                    results['context_recall'] = float(context_recall_result['context_recall'][0])
                else:
                    results['context_recall'] = 0.0
                logger.info(f"上下文召回率评测完成: {results['context_recall']:.4f}")
            except Exception as e:
                logger.error(f"上下文召回率评测失败: {e}")
                results['context_recall'] = 0.0
            
            # 评测答案相关性
            try:
                answer_relevancy_result = await evaluate(
                    [sample],
                    metrics=[self.metrics['answer_relevancy']]
                )
                if 'answer_relevancy' in answer_relevancy_result:
                    results['answer_relevancy'] = float(answer_relevancy_result['answer_relevancy'][0])
                else:
                    results['answer_relevancy'] = 0.0
                logger.info(f"答案相关性评测完成: {results['answer_relevancy']:.4f}")
            except Exception as e:
                logger.error(f"答案相关性评测失败: {e}")
                results['answer_relevancy'] = 0.0
            
            # 收集处理信息
            processing_info = {
                'sample_data': data,
                'sample_created': True,
                'metrics_evaluated': list(results.keys()),
                'evaluation_timestamp': datetime.now().isoformat()
            }
            
            return EvaluationResult(
                sample_id=sample_id,
                metrics=results,
                status=EvaluationStatus.COMPLETED,
                processing_info=processing_info,
                created_at=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"样本评测失败: {e}")
            return EvaluationResult(
                sample_id=data.get('id', 'unknown'),
                metrics={},
                status=EvaluationStatus.FAILED,
                error_message=str(e),
                processing_info={'error': str(e)},
                created_at=datetime.now().isoformat()
            )
    
    async def evaluate_batch(self, data_list: List[Dict[str, Any]]) -> List[EvaluationResult]:
        """批量评测"""
        if not data_list:
            return []
        
        results = []
        for i, data in enumerate(data_list):
            logger.info(f"评测样本 {i+1}/{len(data_list)}")
            result = await self.evaluate_sample(data)
            results.append(result)
        
        return results
    
    async def get_evaluation_statistics(self, results: List[EvaluationResult]) -> Dict[str, Any]:
        """获取评测统计信息"""
        if not results:
            return {}
        
        # 过滤成功的评测结果
        successful_results = [r for r in results if r.status == EvaluationStatus.COMPLETED]
        
        if not successful_results:
            return {
                'total_samples': len(results),
                'successful_evaluations': 0,
                'failed_evaluations': len(results),
                'success_rate': 0.0
            }
        
        # 计算各指标的平均分
        metrics_stats = {}
        for metric in ['faithfulness', 'context_precision', 'context_recall', 'answer_relevancy']:
            scores = [r.metrics.get(metric, 0.0) for r in successful_results if metric in r.metrics]
            if scores:
                metrics_stats[metric] = {
                    'mean': sum(scores) / len(scores),
                    'min': min(scores),
                    'max': max(scores),
                    'count': len(scores)
                }
        
        return {
            'total_samples': len(results),
            'successful_evaluations': len(successful_results),
            'failed_evaluations': len(results) - len(successful_results),
            'success_rate': len(successful_results) / len(results),
            'metrics_statistics': metrics_stats
        }


# 兼容性函数
def create_inference_ragas_evaluator(model_config: Optional[ModelConfig] = None) -> InferenceRAGASEvaluator:
    """创建推理数据 RAGAS 评估器实例"""
    return InferenceRAGASEvaluator(model_config)


if __name__ == "__main__":
    # 测试推理数据 RAGAS 评估器
    print("🚀 测试推理数据 RAGAS 评估器")
    
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    async def test_evaluator():
        try:
            # 创建评估器
            evaluator = create_inference_ragas_evaluator()
            print("✅ 推理数据 RAGAS 评估器创建成功")
            
            # 测试数据 - 检查项目推荐推理数据
            test_data = {
                "id": "inference_001",
                "question": "患者出现胸痛症状，需要推荐哪些检查项目？",
                "answer": "建议进行以下检查：1. 心电图 2. 胸部X光 3. 心肌酶谱 4. 血常规",
                "contexts": [
                    "胸痛是常见症状，需要排除心脏疾病",
                    "心电图可以检测心律异常",
                    "胸部X光可以观察肺部情况"
                ],
                "ground_truth": "胸痛患者应进行心电图、胸部X光、心肌酶谱检查"
            }
            
            print(f"\n📊 测试数据:")
            print(f"   问题: {test_data['question']}")
            print(f"   答案: {test_data['answer']}")
            print(f"   上下文数量: {len(test_data['contexts'])}")
            
            # 运行评测
            result = await evaluator.evaluate_sample(test_data)
            
            print(f"\n✅ 评测完成！")
            print(f"评测结果:")
            print(f"  状态: {result.status.value}")
            print(f"  指标分数:")
            
            total_score = 0
            valid_metrics = 0
            for metric, score in result.metrics.items():
                status = "✅" if score > 0 else "⚠️"
                print(f"    {status} {metric}: {score:.4f}")
                if score > 0:
                    total_score += score
                    valid_metrics += 1
            
            if valid_metrics > 0:
                avg_score = total_score / valid_metrics
                print(f"\n📊 平均分: {avg_score:.4f} (有效指标: {valid_metrics}/4)")
                
                if valid_metrics >= 3:
                    print(f"\n🎉 测试成功！推理数据 RAGAS 评估器工作正常")
                else:
                    print(f"\n⚠️  部分指标仍需优化")
            else:
                print(f"\n❌ 所有指标都为0，需要进一步调试")
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            logger.error(f"详细错误: {e}", exc_info=True)
    
    asyncio.run(test_evaluator())
