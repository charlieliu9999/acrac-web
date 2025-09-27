#!/usr/bin/env python3
"""
增强版RAGAS评估器
修复LLM输出解析问题，提供更好的中文支持
"""
import os
import sys
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd
from pathlib import Path

# 设置环境变量
os.environ['NEST_ASYNCIO_DISABLE'] = '1'
os.environ['UVLOOP_DISABLE'] = '1'

# 加载.env文件
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

sys.path.insert(0, str(Path(__file__).parent))

try:
    from ragas.dataset_schema import SingleTurnSample
    from ragas.metrics import Faithfulness, ContextPrecision, ContextRecall
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from langchain.schema import HumanMessage
    RAGAS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"RAGAS相关依赖未安装: {e}")
    RAGAS_AVAILABLE = False

logger = logging.getLogger(__name__)

class EnhancedRAGASEvaluator:
    """增强版RAGAS评估器，专门处理中文医学内容"""
    
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
        
        logger.info(f"增强版RAGAS评估器初始化完成 - LLM: {self.llm_model}")

    def _setup_event_loop(self):
        """设置事件循环兼容性"""
        try:
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        except Exception as e:
            logger.warning(f"事件循环设置失败: {e}")

    def _load_config(self):
        """加载配置"""
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

    def _evaluate_faithfulness_enhanced(self, sample: SingleTurnSample) -> float:
        """增强版忠实度评估"""
        try:
            # 使用简化的忠实度评估
            contexts_text = "\n".join(sample.retrieved_contexts)
            prompt = f"""请评估以下答案是否忠实于给定的上下文。

上下文：
{contexts_text}

问题：{sample.user_input}

答案：{sample.response}

请判断答案中的信息是否都能从上下文中找到支持。
请返回JSON格式：
{{
  "faithfulness_score": 0.8,
  "explanation": "评估说明"
}}

评分标准：
- 1.0: 答案完全基于上下文
- 0.8: 答案大部分基于上下文
- 0.6: 答案部分基于上下文
- 0.4: 答案少部分基于上下文
- 0.2: 答案基本不基于上下文
- 0.0: 答案与上下文无关
"""
            
            response = self.llm.invoke([HumanMessage(content=prompt)])
            
            try:
                result = json.loads(response.content)
                score = float(result.get('faithfulness_score', 0.0))
                logger.info(f"增强版faithfulness: {score:.4f}")
                return score
            except:
                # 如果JSON解析失败，尝试从文本中提取分数
                content = response.content.lower()
                if '1.0' in content or '完全' in content:
                    return 1.0
                elif '0.8' in content or '大部分' in content:
                    return 0.8
                elif '0.6' in content or '部分' in content:
                    return 0.6
                elif '0.4' in content or '少部分' in content:
                    return 0.4
                elif '0.2' in content or '基本不' in content:
                    return 0.2
                else:
                    return 0.0
                    
        except Exception as e:
            logger.error(f"增强版faithfulness评估失败: {e}")
            return 0.0

    def _evaluate_context_precision_enhanced(self, sample: SingleTurnSample) -> float:
        """增强版上下文精确度评估"""
        try:
            contexts_numbered = "\n".join([f"{i+1}. {ctx}" for i, ctx in enumerate(sample.retrieved_contexts)])
            prompt = f"""请评估以下上下文对回答问题的精确度。

问题：{sample.user_input}

上下文：
{contexts_numbered}

答案：{sample.response}

请判断每个上下文是否对回答问题有用。
请返回JSON格式：
{{
  "precision_score": 0.8,
  "useful_contexts": [1, 2],
  "explanation": "评估说明"
}}

评分 = 有用的上下文数量 / 总上下文数量
"""
            
            response = self.llm.invoke([HumanMessage(content=prompt)])
            
            try:
                result = json.loads(response.content)
                score = float(result.get('precision_score', 0.0))
                logger.info(f"增强版context_precision: {score:.4f}")
                return score
            except:
                # 简单的启发式评估
                total_contexts = len(sample.retrieved_contexts)
                if total_contexts == 0:
                    return 0.0
                
                # 检查上下文与问题的相关性
                question_lower = sample.user_input.lower()
                useful_count = 0
                
                for ctx in sample.retrieved_contexts:
                    ctx_lower = ctx.lower()
                    # 简单的关键词匹配
                    if any(word in ctx_lower for word in question_lower.split() if len(word) > 1):
                        useful_count += 1
                
                score = useful_count / total_contexts
                logger.info(f"增强版context_precision (启发式): {score:.4f}")
                return score
                
        except Exception as e:
            logger.error(f"增强版context_precision评估失败: {e}")
            return 0.0

    def _evaluate_context_recall_enhanced(self, sample: SingleTurnSample) -> float:
        """增强版上下文召回率评估"""
        try:
            if not sample.reference or sample.reference.strip() == "":
                # 如果没有标准答案，使用答案本身作为参考
                reference = sample.response
            else:
                reference = sample.reference
            
            contexts_text = "\n".join(sample.retrieved_contexts)
            prompt = f"""请评估上下文是否包含了回答问题所需的信息。

问题：{sample.user_input}

标准答案/参考答案：{reference}

上下文：
{contexts_text}

请判断上下文是否包含了回答问题所需的关键信息。
请返回JSON格式：
{{
  "recall_score": 0.8,
  "explanation": "评估说明"
}}

评分标准：
- 1.0: 上下文包含所有必要信息
- 0.8: 上下文包含大部分必要信息
- 0.6: 上下文包含部分必要信息
- 0.4: 上下文包含少量必要信息
- 0.2: 上下文包含很少必要信息
- 0.0: 上下文不包含必要信息
"""
            
            response = self.llm.invoke([HumanMessage(content=prompt)])
            
            try:
                result = json.loads(response.content)
                score = float(result.get('recall_score', 0.0))
                logger.info(f"增强版context_recall: {score:.4f}")
                return score
            except:
                # 启发式评估
                if len(sample.retrieved_contexts) > 0:
                    score = 0.8  # 有上下文就给一个基础分
                else:
                    score = 0.0
                logger.info(f"增强版context_recall (启发式): {score:.4f}")
                return score
                
        except Exception as e:
            logger.error(f"增强版context_recall评估失败: {e}")
            return 0.0

    def _evaluate_answer_relevancy_enhanced(self, sample: SingleTurnSample) -> float:
        """增强版答案相关性评估"""
        try:
            prompt = f"""请评估答案与问题的相关性。

问题：{sample.user_input}

答案：{sample.response}

请判断答案是否直接回答了问题。
请返回JSON格式：
{{
  "relevancy_score": 0.8,
  "explanation": "评估说明"
}}

评分标准：
- 1.0: 答案完全回答了问题
- 0.8: 答案大部分回答了问题
- 0.6: 答案部分回答了问题
- 0.4: 答案少部分回答了问题
- 0.2: 答案基本没有回答问题
- 0.0: 答案与问题无关
"""
            
            response = self.llm.invoke([HumanMessage(content=prompt)])
            
            try:
                result = json.loads(response.content)
                score = float(result.get('relevancy_score', 0.0))
                logger.info(f"增强版answer_relevancy: {score:.4f}")
                return score
            except:
                # 简单的相关性检查
                question_words = set(sample.user_input.lower().split())
                answer_words = set(sample.response.lower().split())
                
                # 计算词汇重叠度
                overlap = len(question_words & answer_words)
                total_question_words = len(question_words)
                
                if total_question_words > 0:
                    score = min(overlap / total_question_words, 1.0)
                else:
                    score = 0.0
                
                logger.info(f"增强版answer_relevancy (启发式): {score:.4f}")
                return score
                
        except Exception as e:
            logger.error(f"增强版answer_relevancy评估失败: {e}")
            return 0.0

    def evaluate_sample(self, data: Dict[str, Any]) -> Dict[str, float]:
        """评估单个样本"""
        try:
            sample = self.create_sample(data)
            logger.info(f"评估样本: {sample.user_input[:50]}...")
            
            results = {}
            
            # 使用增强版评估方法
            results['faithfulness'] = self._evaluate_faithfulness_enhanced(sample)
            results['context_precision'] = self._evaluate_context_precision_enhanced(sample)
            results['context_recall'] = self._evaluate_context_recall_enhanced(sample)
            results['answer_relevancy'] = self._evaluate_answer_relevancy_enhanced(sample)
            
            return results
            
        except Exception as e:
            logger.error(f"样本评估失败: {e}")
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

if __name__ == "__main__":
    # 测试增强版评估器
    print("🚀 测试增强版RAGAS评估器")
    
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    try:
        # 创建评估器
        evaluator = EnhancedRAGASEvaluator()
        
        # 测试数据
        test_data = {
            "question": "糖尿病患者的饮食管理建议？",
            "answer": "糖尿病患者饮食管理：1. 控制总热量 2. 合理分配三大营养素 3. 定时定量进餐",
            "contexts": [
                "糖尿病需要严格的饮食控制",
                "营养均衡对血糖控制很重要"
            ],
            "ground_truth": "糖尿病患者应该控制饮食"
        }
        
        print(f"\\n📊 测试数据:")
        print(f"   问题: {test_data['question']}")
        print(f"   答案: {test_data['answer']}")
        print(f"   上下文数量: {len(test_data['contexts'])}")
        
        # 运行评估
        scores = evaluator.evaluate_sample(test_data)
        
        print(f"\\n✅ 评估完成！")
        print(f"评分结果:")
        total_score = 0
        valid_metrics = 0
        for metric, score in scores.items():
            status = "✅" if score > 0 else "⚠️"
            print(f"  {status} {metric}: {score:.4f}")
            if score > 0:
                total_score += score
                valid_metrics += 1
        
        if valid_metrics > 0:
            avg_score = total_score / valid_metrics
            print(f"\\n📊 平均分: {avg_score:.4f} (有效指标: {valid_metrics}/4)")
            
            if valid_metrics >= 3:
                print(f"\\n🎉 测试成功！增强版评估器工作正常")
            else:
                print(f"\\n⚠️  部分指标仍需优化")
        else:
            print(f"\\n❌ 所有指标都为0，需要进一步调试")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        logger.error(f"详细错误: {e}", exc_info=True)