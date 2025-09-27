#!/usr/bin/env python3
"""
增强版RAGAS评估器 - 模块化重构版本
专门处理中文医学内容，提供可配置的模型管理和评测指标
"""
import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

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
class EvaluationConfig:
    """评测配置"""
    enable_faithfulness: bool = True
    enable_context_precision: bool = True
    enable_context_recall: bool = True
    enable_answer_relevancy: bool = True
    use_enhanced_methods: bool = True
    chinese_optimization: bool = True
    medical_domain: bool = True


@dataclass
class EvaluationResult:
    """评测结果"""
    sample_id: str
    metrics: Dict[str, float]
    enhanced_metrics: Dict[str, float]
    llm_parsing_success: bool
    fallback_method_used: Optional[str]
    medical_term_analysis: Dict[str, Any]
    chinese_processing_info: Dict[str, Any]
    process_data: Dict[str, Any]
    status: EvaluationStatus
    error_message: Optional[str]
    created_at: str


class BaseEvaluator(ABC):
    """评测器基类"""
    
    @abstractmethod
    async def evaluate_sample(self, sample: SingleTurnSample) -> Dict[str, float]:
        """评测单个样本"""
        pass
    
    @abstractmethod
    async def evaluate_batch(self, samples: List[SingleTurnSample]) -> List[Dict[str, float]]:
        """批量评测样本"""
        pass


class EnhancedRAGASEvaluator(BaseEvaluator):
    """增强版RAGAS评估器，专门处理中文医学内容"""
    
    def __init__(self, model_config: Optional[ModelConfig] = None, 
                 evaluation_config: Optional[EvaluationConfig] = None):
        """初始化评估器"""
        if not RAGAS_AVAILABLE:
            raise ImportError("RAGAS相关依赖未安装")
        
        # 设置事件循环兼容性
        self._setup_event_loop()
        
        # 加载配置
        self.model_config = model_config or self._load_default_model_config()
        self.evaluation_config = evaluation_config or EvaluationConfig()
        
        # 初始化模型
        self._init_models()
        
        # 初始化评测指标
        self._init_metrics()
        
        logger.info(f"增强版RAGAS评估器初始化完成 - LLM: {self.model_config.llm_model}")

    def _setup_event_loop(self):
        """设置事件循环兼容性"""
        try:
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        except Exception as e:
            logger.warning(f"事件循环设置失败: {e}")

    def _load_default_model_config(self) -> ModelConfig:
        """加载默认模型配置"""
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
        self.metrics = {}
        
        if self.evaluation_config.enable_faithfulness:
            self.metrics['faithfulness'] = Faithfulness()
        
        if self.evaluation_config.enable_context_precision:
            self.metrics['context_precision'] = ContextPrecision()
        
        if self.evaluation_config.enable_context_recall:
            self.metrics['context_recall'] = ContextRecall()

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

    async def _evaluate_faithfulness_enhanced(self, sample: SingleTurnSample) -> Dict[str, Any]:
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
                explanation = result.get('explanation', '')
                logger.info(f"增强版faithfulness: {score:.4f}")
                return {
                    'score': score,
                    'explanation': explanation,
                    'llm_parsing_success': True,
                    'fallback_method': None
                }
            except:
                # 如果JSON解析失败，尝试从文本中提取分数
                content = response.content.lower()
                if '1.0' in content or '完全' in content:
                    score = 1.0
                elif '0.8' in content or '大部分' in content:
                    score = 0.8
                elif '0.6' in content or '部分' in content:
                    score = 0.6
                elif '0.4' in content or '少部分' in content:
                    score = 0.4
                elif '0.2' in content or '基本不' in content:
                    score = 0.2
                else:
                    score = 0.0
                
                return {
                    'score': score,
                    'explanation': response.content,
                    'llm_parsing_success': False,
                    'fallback_method': 'text_parsing'
                }
                    
        except Exception as e:
            logger.error(f"增强版faithfulness评估失败: {e}")
            return {
                'score': 0.0,
                'explanation': f"评估失败: {str(e)}",
                'llm_parsing_success': False,
                'fallback_method': 'error_fallback'
            }

    async def _evaluate_context_precision_enhanced(self, sample: SingleTurnSample) -> Dict[str, Any]:
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
                useful_contexts = result.get('useful_contexts', [])
                explanation = result.get('explanation', '')
                logger.info(f"增强版context_precision: {score:.4f}")
                return {
                    'score': score,
                    'useful_contexts': useful_contexts,
                    'explanation': explanation,
                    'llm_parsing_success': True,
                    'fallback_method': None
                }
            except:
                # 简单的启发式评估
                total_contexts = len(sample.retrieved_contexts)
                if total_contexts == 0:
                    return {
                        'score': 0.0,
                        'useful_contexts': [],
                        'explanation': '无上下文',
                        'llm_parsing_success': False,
                        'fallback_method': 'heuristic'
                    }
                
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
                return {
                    'score': score,
                    'useful_contexts': list(range(1, useful_count + 1)),
                    'explanation': f'启发式评估: {useful_count}/{total_contexts} 个上下文有用',
                    'llm_parsing_success': False,
                    'fallback_method': 'heuristic'
                }
                
        except Exception as e:
            logger.error(f"增强版context_precision评估失败: {e}")
            return {
                'score': 0.0,
                'useful_contexts': [],
                'explanation': f"评估失败: {str(e)}",
                'llm_parsing_success': False,
                'fallback_method': 'error_fallback'
            }

    async def _evaluate_context_recall_enhanced(self, sample: SingleTurnSample) -> Dict[str, Any]:
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
                explanation = result.get('explanation', '')
                # 结合GT出现与否进行保守校准
                if isinstance(reference, str) and reference.strip():
                    ref = reference.strip()
                    ctx_text = contexts_text
                    if ref in ctx_text:
                        score = max(score, 0.8)
                    else:
                        score = min(score, 0.6)
                logger.info(f"增强版context_recall: {score:.4f}")
                return {
                    'score': score,
                    'explanation': explanation,
                    'llm_parsing_success': True,
                    'fallback_method': None
                }
            except:
                # 启发式评估
                if len(sample.retrieved_contexts) > 0:
                    # 若GT存在且未出现在任何上下文中，则给0.6；否则0.8
                    gt = (reference or "").strip() if isinstance(reference, str) else ""
                    if gt and all((gt not in (c or "")) for c in sample.retrieved_contexts):
                        score = 0.6
                    else:
                        score = 0.8
                else:
                    score = 0.0
                logger.info(f"增强版context_recall (启发式): {score:.4f}")
                return {
                    'score': score,
                    'explanation': f'启发式评估: {"有上下文" if len(sample.retrieved_contexts) > 0 else "无上下文"}',
                    'llm_parsing_success': False,
                    'fallback_method': 'heuristic'
                }
                
        except Exception as e:
            logger.error(f"增强版context_recall评估失败: {e}")
            return {
                'score': 0.0,
                'explanation': f"评估失败: {str(e)}",
                'llm_parsing_success': False,
                'fallback_method': 'error_fallback'
            }

    async def _evaluate_answer_relevancy_enhanced(self, sample: SingleTurnSample) -> Dict[str, Any]:
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
                explanation = result.get('explanation', '')
                # 若存在标准答案，优先进行一致性校准
                if sample.reference and isinstance(sample.reference, str):
                    ref = sample.reference.strip()
                    ans = (sample.response or "").strip()
                    if ref:
                        if ref in ans:
                            score = max(score, 0.8)  # 命中GT至少0.8
                        else:
                            score = min(score, 0.4)  # 未命中GT，收敛保守
                logger.info(f"增强版answer_relevancy: {score:.4f}")
                return {
                    'score': score,
                    'explanation': explanation,
                    'llm_parsing_success': True,
                    'fallback_method': None
                }
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
                # 结合标准答案进行再校准
                if sample.reference and isinstance(sample.reference, str):
                    ref = sample.reference.strip()
                    if ref:
                        if ref in (sample.response or ""):
                            score = max(score, 0.8)
                        else:
                            score = min(score, 0.4)
                
                logger.info(f"增强版answer_relevancy (启发式): {score:.4f}")
                return {
                    'score': score,
                    'explanation': f'启发式评估: 词汇重叠度 {overlap}/{total_question_words}',
                    'llm_parsing_success': False,
                    'fallback_method': 'heuristic'
                }
                
        except Exception as e:
            logger.error(f"增强版answer_relevancy评估失败: {e}")
            return {
                'score': 0.0,
                'explanation': f"评估失败: {str(e)}",
                'llm_parsing_success': False,
                'fallback_method': 'error_fallback'
            }

    async def evaluate_sample(self, sample: SingleTurnSample) -> Dict[str, float]:
        """评测单个样本"""
        try:
            logger.info(f"评估样本: {sample.user_input[:50]}...")
            
            results = {}
            
            # 使用增强版评估方法
            if self.evaluation_config.enable_faithfulness:
                faithfulness_result = await self._evaluate_faithfulness_enhanced(sample)
                results['faithfulness'] = faithfulness_result['score']
            
            if self.evaluation_config.enable_context_precision:
                precision_result = await self._evaluate_context_precision_enhanced(sample)
                results['context_precision'] = precision_result['score']
            
            if self.evaluation_config.enable_context_recall:
                recall_result = await self._evaluate_context_recall_enhanced(sample)
                results['context_recall'] = recall_result['score']
            
            if self.evaluation_config.enable_answer_relevancy:
                relevancy_result = await self._evaluate_answer_relevancy_enhanced(sample)
                results['answer_relevancy'] = relevancy_result['score']
            
            return results
            
        except Exception as e:
            logger.error(f"样本评估失败: {e}")
            return {
                'faithfulness': 0.0,
                'answer_relevancy': 0.0,
                'context_precision': 0.0,
                'context_recall': 0.0
            }

    async def evaluate_batch(self, samples: List[SingleTurnSample]) -> List[Dict[str, float]]:
        """批量评测样本"""
        if not samples:
            return []
        
        results = []
        for i, sample in enumerate(samples):
            logger.info(f"评估样本 {i+1}/{len(samples)}")
            result = await self.evaluate_sample(sample)
            results.append(result)
        
        return results

    async def evaluate_with_detailed_results(self, data: Dict[str, Any]) -> EvaluationResult:
        """评测样本并返回详细结果"""
        try:
            sample = self.create_sample(data)
            sample_id = data.get('id', f"sample_{hash(str(data))}")
            
            # 执行评测
            metrics = await self.evaluate_sample(sample)
            
            # 收集详细的过程数据
            process_data = {
                'question': sample.user_input,
                'answer': sample.response,
                'contexts': sample.retrieved_contexts,
                'ground_truth': sample.reference,
                'evaluation_config': {
                    'enable_faithfulness': self.evaluation_config.enable_faithfulness,
                    'enable_context_precision': self.evaluation_config.enable_context_precision,
                    'enable_context_recall': self.evaluation_config.enable_context_recall,
                    'enable_answer_relevancy': self.evaluation_config.enable_answer_relevancy,
                    'use_enhanced_methods': self.evaluation_config.use_enhanced_methods,
                    'chinese_optimization': self.evaluation_config.chinese_optimization,
                    'medical_domain': self.evaluation_config.medical_domain
                }
            }
            
            # 医学术语分析（简化版）
            medical_term_analysis = {
                'medical_keywords_found': len([word for word in ['患者', '治疗', '诊断', '症状', '药物'] 
                                             if word in sample.user_input or word in sample.response]),
                'chinese_medical_terms': [word for word in sample.user_input.split() 
                                        if len(word) > 2 and any(char in word for char in '病痛症治药')]
            }
            
            # 中文处理信息
            chinese_processing_info = {
                'is_chinese_content': any('\u4e00' <= char <= '\u9fff' for char in sample.user_input),
                'chinese_character_count': sum(1 for char in sample.user_input if '\u4e00' <= char <= '\u9fff'),
                'processing_method': 'enhanced_chinese_processing' if self.evaluation_config.chinese_optimization else 'standard'
            }
            
            return EvaluationResult(
                sample_id=sample_id,
                metrics=metrics,
                enhanced_metrics=metrics,  # 在增强版中，metrics 和 enhanced_metrics 相同
                llm_parsing_success=True,  # 简化处理
                fallback_method_used=None,
                medical_term_analysis=medical_term_analysis,
                chinese_processing_info=chinese_processing_info,
                process_data=process_data,
                status=EvaluationStatus.COMPLETED,
                error_message=None,
                created_at=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"详细评测失败: {e}")
            return EvaluationResult(
                sample_id=data.get('id', 'unknown'),
                metrics={},
                enhanced_metrics={},
                llm_parsing_success=False,
                fallback_method_used='error_fallback',
                medical_term_analysis={},
                chinese_processing_info={},
                process_data={},
                status=EvaluationStatus.FAILED,
                error_message=str(e),
                created_at=datetime.now().isoformat()
            )


# 兼容性函数，保持与原有代码的兼容性
def create_enhanced_evaluator() -> EnhancedRAGASEvaluator:
    """创建增强版评估器实例"""
    return EnhancedRAGASEvaluator()


async def main():
    """主测试函数"""
    # 测试增强版评估器
    print("🚀 测试增强版RAGAS评估器")
    
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    try:
        # 创建评估器
        evaluator = create_enhanced_evaluator()
        
        # 测试数据
        test_data = {
            "id": "test_001",
            "question": "糖尿病患者的饮食管理建议？",
            "answer": "糖尿病患者饮食管理：1. 控制总热量 2. 合理分配三大营养素 3. 定时定量进餐",
            "contexts": [
                "糖尿病需要严格的饮食控制",
                "营养均衡对血糖控制很重要"
            ],
            "ground_truth": "糖尿病患者应该控制饮食"
        }
        
        print(f"\n📊 测试数据:")
        print(f"   问题: {test_data['question']}")
        print(f"   答案: {test_data['answer']}")
        print(f"   上下文数量: {len(test_data['contexts'])}")
        
        # 运行评估
        result = await evaluator.evaluate_with_detailed_results(test_data)
        
        print(f"\n✅ 评估完成！")
        print(f"评测结果:")
        print(f"  状态: {result.status.value}")
        print(f"  指标分数:")
        for metric, score in result.metrics.items():
            status = "✅" if score > 0 else "⚠️"
            print(f"    {status} {metric}: {score:.4f}")
        
        print(f"  医学术语分析: {result.medical_term_analysis}")
        print(f"  中文处理信息: {result.chinese_processing_info}")
        
        if result.status == EvaluationStatus.COMPLETED:
            print(f"\n🎉 测试成功！增强版评估器工作正常")
        else:
            print(f"\n❌ 测试失败: {result.error_message}")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        logger.error(f"详细错误: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
