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
    # 兼容适配：ragas 0.1.9 仍调用 set_run_config，而 LangChain 0.2.x 提供的是 with_config。
    # 提供一个轻量包装，转发 set_run_config -> with_config，避免不必要的依赖升级。
    class ChatOpenAICompat(ChatOpenAI):
        def set_run_config(self, run_config):  # type: ignore[override]
            try:
                # 在 LangChain 0.2.x 中推荐使用 with_config
                return self.with_config(run_config)
            except Exception:
                # 退化为返回自身，保持接口可用
                return self

        # 兼容 RAGAS 0.1.x 在部分路径上传入 PromptValue 的情况
        # LangChain 0.2.x 的 ChatModel.generate 期望的是 List[List[BaseMessage]] 或 ChatPromptValue
        # 如果拿到的是 PromptValue 且无 __len__，将其转换为 messages 列表并包成 batch
        async def generate(self, messages, **kwargs):  # type: ignore[override]
            # 移除 RAGAS 传入但 OpenAI SDK 不支持的参数，避免 Completions.create(is_async=...) 报错
            kwargs.pop('is_async', None)
            try:
                # 将 PromptValue/ChatPromptValue 统一转为消息列表
                if hasattr(messages, "to_messages"):
                    messages = messages.to_messages()
                # 若是单轮消息列表，则包成批量 [[...]]
                if isinstance(messages, list):
                    if not messages or (messages and not isinstance(messages[0], list)):
                        messages = [messages]
                return await super().agenerate(messages, **kwargs)
            except TypeError:
                # 再尝试一次保守转换
                if hasattr(messages, "to_messages"):
                    m = messages.to_messages()
                else:
                    m = messages
                if isinstance(m, list) and (not m or not isinstance(m[0], list)):
                    m = [m]
                return await super().agenerate(m, **kwargs)

        async def agenerate(self, messages, **kwargs):  # explicit async wrapper for safety
            kwargs.pop('is_async', None)
            if hasattr(messages, "to_messages"):
                messages = messages.to_messages()
            if isinstance(messages, list) and (not messages or not isinstance(messages[0], list)):
                messages = [messages]
            return await super().agenerate(messages, **kwargs)
    RAGAS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"RAGAS相关依赖未安装: {e}")
    RAGAS_AVAILABLE = False

logger = logging.getLogger(__name__)

class RAGASEvaluator:
    """RAGAS评估器"""

    def __init__(
        self,
        llm_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ):
        """初始化RAGAS评估器，允许按次选择模型
        llm_model/embedding_model/base_url/api_key 未提供时，从环境变量读取：
        - LLM:   SILICONFLOW_LLM_MODEL or OPENAI_MODEL
        - EMB:   SILICONFLOW_EMBEDDING_MODEL
        - KEY:   OPENAI_API_KEY or SILICONFLOW_API_KEY
        - URL:   OPENAI_BASE_URL or https://api.siliconflow.cn/v1
        """
        if not RAGAS_AVAILABLE:
            raise ImportError("RAGAS相关依赖未安装，请安装ragas、langchain-openai等依赖")

        # API 配置
        # 首选传入的 base_url，其次根据模型名做启发式选择（Ollama 优先），否则回退到环境变量顺序
        _llm = llm_model or os.getenv("SILICONFLOW_LLM_MODEL") or ""
        _emb = embedding_model or os.getenv("SILICONFLOW_EMBEDDING_MODEL") or ""
        prefer_ollama = (":" in str(_llm)) or (":" in str(_emb))
        if base_url:
            self.base_url = base_url
        elif prefer_ollama and os.getenv("OLLAMA_BASE_URL"):
            self.base_url = os.getenv("OLLAMA_BASE_URL")
        else:
            self.base_url = (
                os.getenv("OPENAI_BASE_URL")
                or os.getenv("SILICONFLOW_BASE_URL")
                or os.getenv("OLLAMA_BASE_URL")
                or "https://api.siliconflow.cn/v1"
            )
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("SILICONFLOW_API_KEY")
        # 兼容本地 Ollama（OpenAI 兼容端点通常不需要密钥）
        if not self.api_key:
            base_lower = (self.base_url or "").lower()
            if ("localhost:11434" in base_lower) or ("127.0.0.1:11434" in base_lower) or ("/v1" in base_lower and "ollama" in base_lower):
                # 占位密钥以满足 OpenAI SDK 的参数要求
                self.api_key = "ollama"
            else:
                raise ValueError("未找到API密钥，请设置OPENAI_API_KEY或SILICONFLOW_API_KEY环境变量")

        # 模型名称（允许来自 .env）
        llm_model = llm_model or os.getenv("SILICONFLOW_LLM_MODEL") or "gpt-3.5-turbo"
        embedding_model = embedding_model or os.getenv("SILICONFLOW_EMBEDDING_MODEL") or "BAAI/bge-large-zh-v1.5"

        # 初始化模型
        self.llm = ChatOpenAICompat(
            model=llm_model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self.embeddings = OpenAIEmbeddings(
            model=embedding_model,
            api_key=self.api_key,
            base_url=self.base_url,
        )

        logger.info(f"RAGAS LLM type: {self.llm.__class__.__name__}")

        # 配置RAGAS指标
        faithfulness.llm = self.llm
        answer_relevancy.llm = self.llm
        answer_relevancy.embeddings = self.embeddings
        context_precision.llm = self.llm
        context_recall.llm = self.llm
        context_recall.embeddings = self.embeddings

        self.metrics = [faithfulness, answer_relevancy, context_precision, context_recall]

        logger.info("RAGAS评估器初始化完成")

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
            
            # 提取评分并处理NaN值（兼容 ragas 不同返回结构：标量、列表、ndarray、Series 等）
            def _first(val: Any) -> float:
                try:
                    if isinstance(val, (list, tuple)):
                        val = val[0] if val else float('nan')
                    elif hasattr(val, 'tolist'):
                        arr = val.tolist()
                        val = arr[0] if isinstance(arr, (list, tuple)) and arr else arr
                    elif hasattr(val, 'item'):
                        val = val.item()
                    v = float(val)
                    return 0.0 if (v != v) else v  # NaN -> 0.0
                except Exception:
                    return 0.0

            scores = {
                'faithfulness': _first(result.get('faithfulness')),
                'answer_relevancy': _first(result.get('answer_relevancy')),
                'context_precision': _first(result.get('context_precision')),
                'context_recall': _first(result.get('context_recall')),
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
