"""
全新的RAGAS评估器 - 基于真实推理数据
专门为ACRAC医学推荐系统设计
"""
import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd
from pathlib import Path

try:
    from ragas.dataset_schema import SingleTurnSample
    from ragas.metrics import Faithfulness, ContextPrecision, ContextRecall
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    RAGAS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"RAGAS相关依赖未安装: {e}")
    RAGAS_AVAILABLE = False

logger = logging.getLogger(__name__)

class ACRACRAGASEvaluator:
    """ACRAC专用RAGAS评估器"""
    
    def __init__(self):
        """初始化评估器"""
        if not RAGAS_AVAILABLE:
            raise ImportError("RAGAS相关依赖未安装")
        
        # 设置事件循环兼容性
        self._setup_event_loop()
        
        # 加载配置
        self._load_config()
        
        # 初始化模型
        self._init_models()
        
        # 初始化指标（只使用稳定的指标）
        self._init_metrics()
        
        logger.info(f"ACRAC RAGAS评估器初始化完成 - LLM: {self.llm_model}")

    def _setup_event_loop(self):
        """设置事件循环兼容性"""
        os.environ['NEST_ASYNCIO_DISABLE'] = '1'
        os.environ['UVLOOP_DISABLE'] = '1'
        try:
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        except Exception as e:
            logger.warning(f"事件循环设置失败: {e}")

    def _load_config(self):
        """加载配置"""
        # 从环境变量加载API配置
        self.api_key = os.getenv("SILICONFLOW_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("未找到API密钥，请设置 SILICONFLOW_API_KEY")
        
        self.base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        self.llm_model = os.getenv("SILICONFLOW_LLM_MODEL", "Qwen/Qwen2.5-32B-Instruct")
        self.embedding_model = os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3")

    def _init_models(self):
        """初始化LLM和嵌入模型"""
        self.llm = ChatOpenAI(
            model=self.llm_model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=0.1,
            timeout=60,
            max_retries=2
        )
        
        self.embeddings = OpenAIEmbeddings(
            model=self.embedding_model,
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=60,
            max_retries=2
        )
        # 统一对外可见的模型名字段（供上层记录/展示）
        self.llm_model_name = self.llm_model
        self.embedding_model_name = self.embedding_model

    def _init_metrics(self):
        """初始化评估指标（只使用稳定的指标）"""
        self.faithfulness = Faithfulness(llm=self.llm)
        self.context_precision = ContextPrecision(llm=self.llm)
        self.context_recall = ContextRecall(llm=self.llm)
        
        # 暂时不使用answer_relevancy，因为它有LLM输出解析问题
        logger.info("初始化3个稳定指标: faithfulness, context_precision, context_recall")

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
            contexts = ["相关医学知识"]  # 默认上下文
        
        return SingleTurnSample(
            user_input=question,
            response=answer,
            retrieved_contexts=contexts,
            reference=ground_truth
        )

    async def evaluate_sample_async(self, data: Dict[str, Any]) -> Dict[str, float]:
        """异步评估单个样本"""
        try:
            sample = self.create_sample(data)
            logger.info(f"评估样本: {sample.user_input[:50]}...")
            
            results = {}
            
            # 评估faithfulness
            try:
                score = await self.faithfulness.single_turn_ascore(sample)
                results['faithfulness'] = float(score) if not pd.isna(score) else 0.0
                logger.info(f"faithfulness: {results['faithfulness']:.4f}")
            except Exception as e:
                logger.error(f"faithfulness评估失败: {e}")
                results['faithfulness'] = 0.0
            
            # 评估context_precision
            try:
                score = await self.context_precision.single_turn_ascore(sample)
                results['context_precision'] = float(score) if not pd.isna(score) else 0.0
                logger.info(f"context_precision: {results['context_precision']:.4f}")
            except Exception as e:
                logger.error(f"context_precision评估失败: {e}")
                results['context_precision'] = 0.0
            
            # 评估context_recall
            try:
                score = await self.context_recall.single_turn_ascore(sample)
                results['context_recall'] = float(score) if not pd.isna(score) else 0.0
                logger.info(f"context_recall: {results['context_recall']:.4f}")
            except Exception as e:
                logger.error(f"context_recall评估失败: {e}")
                results['context_recall'] = 0.0
            
            # 暂时将answer_relevancy设为0，避免解析问题
            results['answer_relevancy'] = 0.0
            
            return results
            
        except Exception as e:
            logger.error(f"样本评估失败: {e}")
            return {
                'faithfulness': 0.0,
                'answer_relevancy': 0.0,
                'context_precision': 0.0,
                'context_recall': 0.0
            }

    def evaluate_sample(self, data: Dict[str, Any]) -> Dict[str, float]:
        """同步评估单个样本"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.evaluate_sample_async(data))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"同步评估失败: {e}")
            return {
                'faithfulness': 0.0,
                'answer_relevancy': 0.0,
                'context_precision': 0.0,
                'context_recall': 0.0
            }

    def evaluate_batch(self, data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量评估"""
        if not data_list:
            return {
                'avg_scores': {'faithfulness': 0.0, 'answer_relevancy': 0.0, 'context_precision': 0.0, 'context_recall': 0.0},
                'individual_scores': [],
                'total_samples': 0
            }
        
        individual_scores = []
        
        for i, data in enumerate(data_list):
            logger.info(f"评估样本 {i+1}/{len(data_list)}")
            scores = self.evaluate_sample(data)
            individual_scores.append(scores)
        
        # 计算平均分
        avg_scores = {}
        for metric in ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall']:
            scores = [s[metric] for s in individual_scores]
            avg_scores[metric] = np.mean(scores) if scores else 0.0
        
        return {
            'avg_scores': avg_scores,
            'individual_scores': individual_scores,
            'total_samples': len(data_list)
        }

    def load_real_data(self, file_path: str) -> List[Dict[str, Any]]:
        """加载真实推理数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"加载了 {len(data)} 条真实推理数据")
            return data
            
        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            return []

    def save_results(self, results: Dict[str, Any], output_path: str):
        """保存评估结果"""
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 添加时间戳和元数据
            results['evaluation_metadata'] = {
                'timestamp': pd.Timestamp.now().isoformat(),
                'evaluator_version': 'ACRAC_RAGAS_V2',
                'llm_model': self.llm_model,
                'embedding_model': self.embedding_model
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            logger.info(f"评估结果已保存到: {output_path}")
            
        except Exception as e:
            logger.error(f"保存结果失败: {e}")


if __name__ == "__main__":
    # 测试新的评估器
    print("🚀 测试ACRAC RAGAS评估器")
    
    # 设置详细日志
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    # 加载环境变量
    env_file = Path(__file__).parent.parent.parent / '.env'
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
    
    try:
        # 创建评估器
        evaluator = ACRACRAGASEvaluator()
        
        # 加载真实数据
        data_file = "correct_ragas_data_20250924_021143.json"
        real_data = evaluator.load_real_data(data_file)
        
        if real_data:
            print(f"📊 开始评估 {len(real_data)} 条真实数据")
            
            # 运行批量评估
            results = evaluator.evaluate_batch(real_data)
            
            # 显示结果
            print(f"\n✅ 评估完成！")
            print(f"平均评分:")
            for metric, score in results['avg_scores'].items():
                status = "✅" if score > 0 else "⚠️"
                print(f"  {status} {metric}: {score:.4f}")
            
            # 保存结果
            output_file = f"acrac_ragas_evaluation_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json"
            evaluator.save_results(results, output_file)
            
            print(f"\n🎯 评估完成，结果已保存到: {output_file}")
        else:
            print("❌ 未找到真实数据")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        logger.error(f"详细错误: {e}", exc_info=True)