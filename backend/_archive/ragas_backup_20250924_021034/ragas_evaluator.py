"""RAGAS评估器服务"""
import os
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datasets import Dataset
import numpy as np
import pandas as pd

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
        
        # 处理 uvloop 兼容性问题
        self._setup_event_loop_compatibility()

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
            or "Qwen/Qwen2.5-32B-Instruct"
        )
        emb_model = (
            eva.get('embedding_model')
            or os.getenv('RAGAS_DEFAULT_EMBEDDING_MODEL')
            or os.getenv('SILICONFLOW_EMBEDDING_MODEL')
            or "BAAI/bge-m3"
        )
        temperature = float(str(eva.get('temperature') if eva.get('temperature') is not None else os.getenv('RAGAS_TEMPERATURE', '0.1')))
        top_p = float(str(eva.get('top_p') if eva.get('top_p') is not None else os.getenv('RAGAS_TOP_P', '0.7')))

        # 初始化模型（不强制 max_tokens，遵循用户"不要限制"要求）
        # 添加超时配置以解决 TimeoutError 问题
        self.llm = ChatOpenAI(
            model=llm_model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=temperature,
            top_p=top_p,
            timeout=60,  # 设置60秒超时
            max_retries=2,  # 最多重试2次
        )
        self.embeddings = OpenAIEmbeddings(
            model=emb_model,
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=60,  # 设置60秒超时
            max_retries=2,  # 最多重试2次
        )
        # 记录模型名，便于在结果中写入评测模型信息
        self.llm_model_name = llm_model
        self.embedding_model_name = emb_model

        # RAGAS 0.3.x 版本不需要手动配置指标的 LLM 和 embeddings
        # 这些会在 evaluate 函数调用时自动配置
        self.metrics = [faithfulness, answer_relevancy, context_precision, context_recall]

        logger.info(f"RAGAS评估器初始化完成（LLM={llm_model}, Embedding={emb_model}）")
    
    def _setup_event_loop_compatibility(self):
        """设置事件循环兼容性，处理 uvloop 与 nest_asyncio 的冲突"""
        try:
            # 检查当前是否在 uvloop 环境中
            loop = asyncio.get_running_loop()
            loop_type = type(loop).__name__
            
            if 'uvloop' in loop_type.lower():
                logger.info(f"检测到 uvloop 环境: {loop_type}")
                # 设置环境变量禁用 nest_asyncio
                os.environ['NEST_ASYNCIO_DISABLE'] = '1'
                
                # 尝试设置默认事件循环策略
                try:
                    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
                    logger.info("已设置默认事件循环策略以兼容 uvloop")
                except Exception as e:
                    logger.warning(f"设置事件循环策略失败: {e}")
                    
        except RuntimeError:
            # 没有运行中的事件循环，这是正常情况
            pass
        except Exception as e:
            logger.warning(f"事件循环兼容性设置失败: {e}")
    
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
        """评估单个样本，带重试机制"""
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                logger.info(f"开始评估单个样本 (尝试 {attempt + 1}/{max_retries}): {sample_data.get('question', 'N/A')[:50]}...")
                
                # 确保 uvloop 兼容性
                self._setup_event_loop_compatibility()
                
                # 验证输入数据
                required_fields = ['question', 'answer', 'contexts', 'ground_truth']
                for field in required_fields:
                    if field not in sample_data:
                        raise ValueError(f"缺少必需字段: {field}")
                
                # 验证数据内容
                if not sample_data['contexts'] or len(sample_data['contexts']) == 0:
                    logger.warning("contexts 为空，添加默认上下文")
                    sample_data['contexts'] = ["相关医学知识"]
                
                # 准备单个样本的数据集
                dataset = self.prepare_ragas_dataset([sample_data])
                logger.info(f"数据集准备完成，包含 {len(dataset)} 个样本")
                
                # 执行评估 - RAGAS 0.3.x 版本
                logger.info("开始执行 RAGAS 评估...")
                result = evaluate(
                    dataset=dataset,
                    metrics=self.metrics,
                    llm=self.llm,
                    embeddings=self.embeddings,
                    raise_exceptions=False  # 避免因单个指标失败而中断整个评估
                )
                logger.info("RAGAS 评估执行完成")
                
                # 提取评分并处理NaN值 - 适配 RAGAS 0.3.x 版本
                scores = {}
                logger.info(f"评估结果类型: {type(result)}")
                
                # RAGAS 0.3.x 版本的结果对象可能有不同的访问方式
                try:
                    # 尝试直接访问结果字典
                    if hasattr(result, 'to_pandas'):
                        df = result.to_pandas()
                        logger.info(f"结果DataFrame列: {df.columns.tolist()}")
                        for metric_name in ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall']:
                            if metric_name in df.columns:
                                raw_score = df[metric_name].iloc[0] if len(df) > 0 else 0.0
                                if pd.isna(raw_score) or np.isnan(raw_score):
                                    logger.warning(f"{metric_name} 评分为 NaN，设置为 0.0")
                                    scores[metric_name] = 0.0
                                else:
                                    scores[metric_name] = float(raw_score)
                                    logger.info(f"{metric_name}: {scores[metric_name]:.4f}")
                            else:
                                logger.warning(f"结果中缺少 {metric_name} 指标")
                                scores[metric_name] = 0.0
                    else:
                        # 备用方法：尝试直接访问属性
                        for metric_name in ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall']:
                            try:
                                if hasattr(result, metric_name):
                                    raw_score = getattr(result, metric_name)
                                    if isinstance(raw_score, (list, tuple)) and len(raw_score) > 0:
                                        raw_score = raw_score[0]
                                    if pd.isna(raw_score) or np.isnan(raw_score):
                                        scores[metric_name] = 0.0
                                    else:
                                        scores[metric_name] = float(raw_score)
                                else:
                                    scores[metric_name] = 0.0
                            except Exception as e:
                                logger.warning(f"提取 {metric_name} 失败: {e}")
                                scores[metric_name] = 0.0
                except Exception as e:
                    logger.error(f"评分提取失败: {e}")
                    # 设置默认分数
                    for metric_name in ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall']:
                        scores[metric_name] = 0.0
                
                # 检查是否有有效分数
                valid_scores = [score for score in scores.values() if score > 0]
                if valid_scores or attempt == max_retries - 1:
                    logger.info(f"单个样本评估完成: {scores}")
                    return scores
                else:
                    logger.warning(f"尝试 {attempt + 1} 所有评分都为0，重试...")
                    continue
                    
            except Exception as e:
                last_error = e
                logger.error(f"尝试 {attempt + 1} 评估失败: {str(e)}")
                if attempt < max_retries - 1:
                    logger.info("等待重试...")
                    import time
                    time.sleep(2)  # 等待2秒后重试
                    continue
        
        # 所有重试都失败，返回默认分数
        logger.error(f"所有重试都失败，最后错误: {last_error}")
        return {
            'faithfulness': 0.0,
            'answer_relevancy': 0.0,
            'context_precision': 0.0,
            'context_recall': 0.0
        }
    
    def evaluate_batch(self, test_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量评估"""
        try:
            # 确保 uvloop 兼容性
            self._setup_event_loop_compatibility()
            
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