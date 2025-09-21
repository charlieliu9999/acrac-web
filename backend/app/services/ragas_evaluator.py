"""RAGAS评估器服务"""
import os
import logging
from typing import Dict, List, Any, Optional
from datasets import Dataset
import numpy as np

try:
    from ragas import evaluate
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall
    )
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    RAGAS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"RAGAS相关依赖未安装: {e}")
    RAGAS_AVAILABLE = False

logger = logging.getLogger(__name__)

class RAGASEvaluator:
    """RAGAS评估器"""
    
    def __init__(self):
        """初始化RAGAS评估器（完全采用可配置的 evaluation 上下文，无硬编码模型）"""
        if not RAGAS_AVAILABLE:
            raise ImportError("RAGAS相关依赖未安装，请安装ragas、langchain-openai等依赖")

        # 读取后端配置文件 backend/config/model_contexts.json
        from pathlib import Path
        import json
        contexts_path = Path(__file__).resolve().parents[2] / "config" / "model_contexts.json"
        contexts = {}
        if contexts_path.exists():
            try:
                contexts = json.loads(contexts_path.read_text(encoding="utf-8")) or {}
            except Exception as e:
                logger.warning(f"读取 model_contexts.json 失败: {e}")
        eva = ((contexts.get('contexts') or {}).get('evaluation')) or {}

        # 从 evaluation 上下文与环境变量解析 LLM/Embedding/base_url 与超参
        # 优先 evaluation 上下文，其次 RAGAS_* 环境变量，最后回退到 SiliconFlow 默认
        self.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("SILICONFLOW_API_KEY")
        self.base_url = (
            eva.get('base_url')
            or os.getenv('RAGAS_DEFAULT_BASE_URL')
            or os.getenv('SILICONFLOW_BASE_URL')
            or "https://api.siliconflow.cn/v1"
        )
        if not self.api_key:
            raise ValueError("未找到API密钥，请设置 SILICONFLOW_API_KEY 或 OPENAI_API_KEY")

        llm_model = (
            eva.get('llm_model')
            or os.getenv('RAGAS_DEFAULT_LLM_MODEL')
            or os.getenv('SILICONFLOW_LLM_MODEL')
            or "Qwen/Qwen3-32B"
        )
        emb_model = (
            eva.get('embedding_model')
            or os.getenv('RAGAS_DEFAULT_EMBEDDING_MODEL')
            or os.getenv('SILICONFLOW_EMBEDDING_MODEL')
            or "BAAI/bge-m3"
        )
        temperature = float(str(eva.get('temperature') if eva.get('temperature') is not None else os.getenv('RAGAS_TEMPERATURE', '0.1')))
        top_p = float(str(eva.get('top_p') if eva.get('top_p') is not None else os.getenv('RAGAS_TOP_P', '0.7')))

        # 初始化模型（不强制 max_tokens，遵循用户“不要限制”要求）
        self.llm = ChatOpenAI(
            model=llm_model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=temperature,
            top_p=top_p,
        )
        self.embeddings = OpenAIEmbeddings(
            model=emb_model,
            api_key=self.api_key,
            base_url=self.base_url
        )
        # 记录模型名，便于在结果中写入评测模型信息
        self.llm_model_name = llm_model
        self.embedding_model_name = emb_model

        # 配置RAGAS指标
        faithfulness.llm = self.llm
        answer_relevancy.llm = self.llm
        answer_relevancy.embeddings = self.embeddings
        context_precision.llm = self.llm
        context_recall.llm = self.llm
        context_recall.embeddings = self.embeddings

        self.metrics = [faithfulness, answer_relevancy, context_precision, context_recall]

        logger.info(f"RAGAS评估器初始化完成（LLM={llm_model}, Embedding={emb_model}）")
    
    def prepare_ragas_dataset(self, test_data: List[Dict[str, Any]]) -> Dataset:
        """准备RAGAS兼容的数据集"""
        try:
            ragas_data = {
                'question': [],
                'answer': [],
                'contexts': [],
                'ground_truth': []
            }
            
            for item in test_data:
                ragas_data['question'].append(item.get('question', ''))
                ragas_data['answer'].append(item.get('answer', ''))
                ragas_data['contexts'].append(item.get('contexts', []))
                ragas_data['ground_truth'].append(item.get('ground_truth', ''))
            
            return Dataset.from_dict(ragas_data)
        except Exception as e:
            logger.error(f"准备RAGAS数据集失败: {e}")
            raise
    
    def evaluate_single_sample(self, sample_data: Dict[str, Any]) -> Dict[str, float]:
        """评估单个样本"""
        try:
            # 准备单个样本的数据集
            dataset = self.prepare_ragas_dataset([sample_data])
            
            # 执行评估
            result = evaluate(
                dataset=dataset,
                metrics=self.metrics,
                llm=self.llm,
                embeddings=self.embeddings
            )
            
            # 提取评分并处理NaN值
            scores = {
                'faithfulness': float(result['faithfulness'][0]) if not np.isnan(result['faithfulness'][0]) else 0.0,
                'answer_relevancy': float(result['answer_relevancy'][0]) if not np.isnan(result['answer_relevancy'][0]) else 0.0,
                'context_precision': float(result['context_precision'][0]) if not np.isnan(result['context_precision'][0]) else 0.0,
                'context_recall': float(result['context_recall'][0]) if not np.isnan(result['context_recall'][0]) else 0.0
            }
            
            logger.info(f"单个样本评估完成: {scores}")
            return scores
            
        except Exception as e:
            logger.error(f"单个样本评估失败: {e}")
            # 返回默认分数
            return {
                'faithfulness': 0.0,
                'answer_relevancy': 0.0,
                'context_precision': 0.0,
                'context_recall': 0.0
            }
    
    def evaluate_batch(self, test_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量评估"""
        try:
            if not test_data:
                return {
                    'avg_scores': {
                        'faithfulness': 0.0,
                        'answer_relevancy': 0.0,
                        'context_precision': 0.0,
                        'context_recall': 0.0
                    },
                    'individual_scores': [],
                    'total_samples': 0
                }
            
            # 准备数据集
            dataset = self.prepare_ragas_dataset(test_data)
            
            # 执行批量评估
            result = evaluate(
                dataset=dataset,
                metrics=self.metrics,
                llm=self.llm,
                embeddings=self.embeddings
            )
            
            # 处理结果
            individual_scores = []
            for i in range(len(test_data)):
                scores = {
                    'faithfulness': float(result['faithfulness'][i]) if not np.isnan(result['faithfulness'][i]) else 0.0,
                    'answer_relevancy': float(result['answer_relevancy'][i]) if not np.isnan(result['answer_relevancy'][i]) else 0.0,
                    'context_precision': float(result['context_precision'][i]) if not np.isnan(result['context_precision'][i]) else 0.0,
                    'context_recall': float(result['context_recall'][i]) if not np.isnan(result['context_recall'][i]) else 0.0
                }
                individual_scores.append(scores)
            
            # 计算平均分
            avg_scores = {
                'faithfulness': np.mean([s['faithfulness'] for s in individual_scores]),
                'answer_relevancy': np.mean([s['answer_relevancy'] for s in individual_scores]),
                'context_precision': np.mean([s['context_precision'] for s in individual_scores]),
                'context_recall': np.mean([s['context_recall'] for s in individual_scores])
            }
            
            logger.info(f"批量评估完成: {len(test_data)}个样本，平均分: {avg_scores}")
            
            return {
                'avg_scores': avg_scores,
                'individual_scores': individual_scores,
                'total_samples': len(test_data)
            }
            
        except Exception as e:
            logger.error(f"批量评估失败: {e}")
            # 返回默认结果
            return {
                'avg_scores': {
                    'faithfulness': 0.0,
                    'answer_relevancy': 0.0,
                    'context_precision': 0.0,
                    'context_recall': 0.0
                },
                'individual_scores': [{
                    'faithfulness': 0.0,
                    'answer_relevancy': 0.0,
                    'context_precision': 0.0,
                    'context_recall': 0.0
                } for _ in test_data],
                'total_samples': len(test_data)
            }
    
    def create_test_sample(self, question: str, answer: str, contexts: List[str], ground_truth: str) -> Dict[str, Any]:
        """创建测试样本"""
        return {
            'question': question,
            'answer': answer,
            'contexts': contexts,
            'ground_truth': ground_truth
        }
    
    def run_evaluation(self, test_samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """运行完整评估"""
        try:
            logger.info(f"开始RAGAS评估，样本数: {len(test_samples)}")
            
            # 执行批量评估
            result = self.evaluate_batch(test_samples)
            
            # 添加综合评分
            avg_scores = result['avg_scores']
            overall_score = np.mean(list(avg_scores.values()))
            result['overall_score'] = float(overall_score)
            
            logger.info(f"RAGAS评估完成，综合评分: {overall_score:.4f}")
            
            return result
            
        except Exception as e:
            logger.error(f"RAGAS评估失败: {e}")
            raise
    
    def save_results(self, results: Dict[str, Any], output_path: str) -> None:
        """保存评估结果"""
        try:
            import json
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"评估结果已保存到: {output_path}")
        except Exception as e:
            logger.error(f"保存结果失败: {e}")
            raise

# 主函数示例
if __name__ == "__main__":
    # 初始化评估器
    evaluator = RAGASEvaluator()
    
    # 创建测试样本
    test_samples = [
        evaluator.create_test_sample(
            question="患者出现胸痛症状，需要进行什么影像学检查？",
            answer="建议进行胸部CT检查以排除肺栓塞等疾病。",
            contexts=["胸痛是常见的临床症状", "CT检查可以有效诊断胸部疾病"],
            ground_truth="胸部CT"
        )
    ]
    
    # 运行评估
    results = evaluator.run_evaluation(test_samples)
    
    # 保存结果
    evaluator.save_results(results, "ragas_evaluation_results.json")
    
    print(f"评估完成，综合评分: {results['overall_score']:.4f}")
    print(f"详细评分: {results['avg_scores']}")