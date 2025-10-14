#!/usr/bin/env python3
"""
模块化评测引擎接口
提供可扩展的评测引擎架构，支持插件化的评测指标管理
"""
import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union, Protocol, Type
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import numpy as np

try:
    from ragas.dataset_schema import SingleTurnSample
    from ragas.metrics import Faithfulness, ContextPrecision, ContextRecall
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
    rerank_model: Optional[str] = None
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
    custom_metrics: List[str] = field(default_factory=list)


@dataclass
class MetricInfo:
    """评测指标信息"""
    name: str
    description: str
    enabled: bool = True
    weight: float = 1.0
    category: str = "default"
    dependencies: List[str] = field(default_factory=list)


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


class MetricEvaluator(Protocol):
    """评测指标接口协议"""
    
    async def evaluate(self, sample: SingleTurnSample) -> Dict[str, Any]:
        """评测单个样本"""
        ...
    
    def get_metric_info(self) -> MetricInfo:
        """获取指标信息"""
        ...


class BaseEvaluationEngine(ABC):
    """评测引擎基类"""
    
    def __init__(self, model_config: ModelConfig, evaluation_config: EvaluationConfig):
        self.model_config = model_config
        self.evaluation_config = evaluation_config
        self.metrics: Dict[str, MetricEvaluator] = {}
        self._initialized = False
    
    @abstractmethod
    async def initialize(self) -> None:
        """初始化评测引擎"""
        pass
    
    @abstractmethod
    async def evaluate_sample(self, sample: SingleTurnSample) -> Dict[str, float]:
        """评测单个样本"""
        pass
    
    @abstractmethod
    async def evaluate_batch(self, samples: List[SingleTurnSample]) -> List[Dict[str, float]]:
        """批量评测样本"""
        pass
    
    @abstractmethod
    async def get_available_metrics(self) -> List[MetricInfo]:
        """获取可用的评测指标"""
        pass
    
    @abstractmethod
    async def update_config(self, config: EvaluationConfig) -> None:
        """更新评测配置"""
        pass


class ModularEvaluationEngine(BaseEvaluationEngine):
    """模块化评测引擎"""
    
    def __init__(self, model_config: ModelConfig, evaluation_config: EvaluationConfig):
        super().__init__(model_config, evaluation_config)
        self.llm = None
        self.embeddings = None
        self.rerank_model = None
    
    async def initialize(self) -> None:
        """初始化评测引擎"""
        if not RAGAS_AVAILABLE:
            raise ImportError("RAGAS相关依赖未安装")
        
        # 初始化模型
        await self._init_models()
        
        # 初始化评测指标
        await self._init_metrics()
        
        self._initialized = True
        logger.info("模块化评测引擎初始化完成")
    
    async def _init_models(self) -> None:
        """初始化模型"""
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
        
        # 如果有重排序模型，初始化它
        if self.model_config.rerank_model:
            # 这里可以添加重排序模型的初始化逻辑
            logger.info(f"重排序模型配置: {self.model_config.rerank_model}")
    
    async def _init_metrics(self) -> None:
        """初始化评测指标"""
        self.metrics = {}
        
        if self.evaluation_config.enable_faithfulness:
            self.metrics['faithfulness'] = Faithfulness()
        
        if self.evaluation_config.enable_context_precision:
            self.metrics['context_precision'] = ContextPrecision()
        
        if self.evaluation_config.enable_context_recall:
            self.metrics['context_recall'] = ContextRecall()
        
        # 添加自定义指标
        for metric_name in self.evaluation_config.custom_metrics:
            await self._load_custom_metric(metric_name)
    
    async def _load_custom_metric(self, metric_name: str) -> None:
        """加载自定义指标"""
        # 这里可以实现自定义指标的加载逻辑
        logger.info(f"加载自定义指标: {metric_name}")
    
    async def evaluate_sample(self, sample: SingleTurnSample) -> Dict[str, float]:
        """评测单个样本"""
        if not self._initialized:
            await self.initialize()
        
        results = {}
        
        for metric_name, metric_evaluator in self.metrics.items():
            try:
                if hasattr(metric_evaluator, 'ascore'):
                    # 使用 RAGAS 的异步评分方法
                    score = await metric_evaluator.ascore(sample)
                elif hasattr(metric_evaluator, 'score'):
                    # 使用 RAGAS 的同步评分方法
                    score = metric_evaluator.score(sample)
                else:
                    # 自定义评测方法
                    score = await self._evaluate_custom_metric(metric_evaluator, sample)
                
                results[metric_name] = float(score) if score is not None else 0.0
                logger.debug(f"指标 {metric_name} 评测完成: {results[metric_name]}")
                
            except Exception as e:
                logger.error(f"指标 {metric_name} 评测失败: {e}")
                results[metric_name] = 0.0
        
        return results
    
    async def _evaluate_custom_metric(self, metric_evaluator: MetricEvaluator, sample: SingleTurnSample) -> float:
        """评测自定义指标"""
        try:
            result = await metric_evaluator.evaluate(sample)
            return result.get('score', 0.0)
        except Exception as e:
            logger.error(f"自定义指标评测失败: {e}")
            return 0.0
    
    async def evaluate_batch(self, samples: List[SingleTurnSample]) -> List[Dict[str, float]]:
        """批量评测样本"""
        if not self._initialized:
            await self.initialize()
        
        results = []
        for i, sample in enumerate(samples):
            logger.info(f"评测样本 {i+1}/{len(samples)}")
            result = await self.evaluate_sample(sample)
            results.append(result)
        
        return results
    
    async def get_available_metrics(self) -> List[MetricInfo]:
        """获取可用的评测指标"""
        metrics_info = []
        
        # 标准 RAGAS 指标
        standard_metrics = {
            'faithfulness': MetricInfo(
                name='faithfulness',
                description='忠实度：评估答案与给定上下文的事实一致性',
                enabled=self.evaluation_config.enable_faithfulness,
                category='ragas_standard'
            ),
            'context_precision': MetricInfo(
                name='context_precision',
                description='上下文精确度：评估检索到的上下文与问题的相关程度',
                enabled=self.evaluation_config.enable_context_precision,
                category='ragas_standard'
            ),
            'context_recall': MetricInfo(
                name='context_recall',
                description='上下文召回率：评估检索器检索所有必要信息的能力',
                enabled=self.evaluation_config.enable_context_recall,
                category='ragas_standard'
            ),
            'answer_relevancy': MetricInfo(
                name='answer_relevancy',
                description='答案相关性：评估生成的答案与用户问题的相关程度',
                enabled=self.evaluation_config.enable_answer_relevancy,
                category='ragas_standard'
            )
        }
        
        for metric_name, metric_info in standard_metrics.items():
            if metric_name in self.metrics:
                metrics_info.append(metric_info)
        
        # 自定义指标
        for metric_name in self.evaluation_config.custom_metrics:
            custom_metric_info = MetricInfo(
                name=metric_name,
                description=f'自定义指标: {metric_name}',
                enabled=True,
                category='custom'
            )
            metrics_info.append(custom_metric_info)
        
        return metrics_info
    
    async def update_config(self, config: EvaluationConfig) -> None:
        """更新评测配置"""
        self.evaluation_config = config
        
        # 重新初始化指标
        await self._init_metrics()
        
        logger.info("评测配置已更新")
    
    async def add_custom_metric(self, metric_name: str, metric_evaluator: MetricEvaluator) -> None:
        """添加自定义评测指标"""
        self.metrics[metric_name] = metric_evaluator
        if metric_name not in self.evaluation_config.custom_metrics:
            self.evaluation_config.custom_metrics.append(metric_name)
        
        logger.info(f"已添加自定义指标: {metric_name}")
    
    async def remove_metric(self, metric_name: str) -> None:
        """移除评测指标"""
        if metric_name in self.metrics:
            del self.metrics[metric_name]
        
        if metric_name in self.evaluation_config.custom_metrics:
            self.evaluation_config.custom_metrics.remove(metric_name)
        
        logger.info(f"已移除指标: {metric_name}")
    
    async def get_metric_statistics(self, results: List[Dict[str, float]]) -> Dict[str, Dict[str, float]]:
        """获取评测指标统计信息"""
        if not results:
            return {}
        
        statistics = {}
        
        # 获取所有指标名称
        all_metrics = set()
        for result in results:
            all_metrics.update(result.keys())
        
        for metric_name in all_metrics:
            scores = [result.get(metric_name, 0.0) for result in results if metric_name in result]
            
            if scores:
                statistics[metric_name] = {
                    'mean': np.mean(scores),
                    'std': np.std(scores),
                    'min': np.min(scores),
                    'max': np.max(scores),
                    'count': len(scores)
                }
        
        return statistics


class EvaluationEngineFactory:
    """评测引擎工厂类"""
    
    @staticmethod
    def create_engine(engine_type: str, model_config: ModelConfig, 
                     evaluation_config: EvaluationConfig) -> BaseEvaluationEngine:
        """创建评测引擎实例"""
        if engine_type == "modular":
            return ModularEvaluationEngine(model_config, evaluation_config)
        elif engine_type == "enhanced":
            # 导入增强版评估器
            from .enhanced_ragas_evaluator import EnhancedRAGASEvaluator
            return EnhancedRAGASEvaluator(model_config, evaluation_config)
        else:
            raise ValueError(f"不支持的评测引擎类型: {engine_type}")
    
    @staticmethod
    def get_available_engines() -> List[str]:
        """获取可用的评测引擎类型"""
        return ["modular", "enhanced"]


# 兼容性函数
def create_modular_evaluation_engine(model_config: Optional[ModelConfig] = None,
                                   evaluation_config: Optional[EvaluationConfig] = None) -> ModularEvaluationEngine:
    """创建模块化评测引擎实例"""
    if model_config is None:
        # 从环境变量加载默认配置
        api_key = os.getenv("SILICONFLOW_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("未找到API密钥，请设置 SILICONFLOW_API_KEY")
        
        model_config = ModelConfig(
            api_key=api_key,
            base_url=os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
            llm_model=os.getenv("SILICONFLOW_LLM_MODEL", "Qwen/Qwen2.5-32B-Instruct"),
            embedding_model=os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3")
        )
    
    if evaluation_config is None:
        evaluation_config = EvaluationConfig()
    
    return ModularEvaluationEngine(model_config, evaluation_config)


if __name__ == "__main__":
    # 测试模块化评测引擎
    print("🚀 测试模块化评测引擎")
    
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    async def test_engine():
        try:
            # 创建评测引擎
            engine = create_modular_evaluation_engine()
            await engine.initialize()
            print("✅ 模块化评测引擎创建成功")
            
            # 获取可用指标
            metrics = await engine.get_available_metrics()
            print(f"📊 可用指标: {[m.name for m in metrics]}")
            
            # 创建测试样本
            sample = SingleTurnSample(
                user_input="糖尿病患者的饮食管理建议？",
                response="糖尿病患者饮食管理：1. 控制总热量 2. 合理分配三大营养素 3. 定时定量进餐",
                retrieved_contexts=[
                    "糖尿病需要严格的饮食控制",
                    "营养均衡对血糖控制很重要"
                ],
                reference="糖尿病患者应该控制饮食"
            )
            
            # 评测样本
            result = await engine.evaluate_sample(sample)
            print(f"✅ 评测完成: {result}")
            
            # 获取统计信息
            stats = await engine.get_metric_statistics([result])
            print(f"📈 统计信息: {stats}")
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(test_engine())






















