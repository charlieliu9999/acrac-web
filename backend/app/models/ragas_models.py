"""RAGAS评测数据模型"""
from sqlalchemy import Column, Integer, String, Text, Float, JSON, TIMESTAMP, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.core.database import Base

class TaskStatus(str, Enum):
    """评测任务状态枚举"""
    PENDING = "pending"          # 待处理
    PROCESSING = "processing"    # 处理中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"      # 已取消

class EvaluationTask(Base):
    """RAGAS评测任务表"""
    __tablename__ = "evaluation_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(50), unique=True, nullable=False, index=True, comment="任务唯一标识")
    task_name = Column(String(255), nullable=False, comment="任务名称")
    description = Column(Text, comment="任务描述")
    status = Column(String(20), default=TaskStatus.PENDING, comment="任务状态")
    
    # 文件信息
    file_path = Column(String(500), comment="上传文件路径")
    file_name = Column(String(255), comment="原始文件名")
    file_size = Column(Integer, comment="文件大小（字节）")
    
    # 进度信息
    total_scenarios = Column(Integer, default=0, comment="总场景数")
    completed_scenarios = Column(Integer, default=0, comment="已完成场景数")
    failed_scenarios = Column(Integer, default=0, comment="失败场景数")
    progress_percentage = Column(Float, default=0.0, comment="完成百分比")
    
    # 评测配置
    evaluation_config = Column(JSON, comment="评测配置参数")
    
    # 结果统计
    avg_faithfulness = Column(Float, comment="平均忠实度得分")
    avg_answer_relevancy = Column(Float, comment="平均答案相关性得分")
    avg_context_precision = Column(Float, comment="平均上下文精确度得分")
    avg_context_recall = Column(Float, comment="平均上下文召回率得分")
    avg_overall_score = Column(Float, comment="平均总体得分")
    
    # 时间信息
    started_at = Column(TIMESTAMP, comment="开始时间")
    completed_at = Column(TIMESTAMP, comment="完成时间")
    estimated_completion = Column(TIMESTAMP, comment="预计完成时间")
    
    # 错误信息
    error_message = Column(Text, comment="错误信息")
    error_details = Column(JSON, comment="详细错误信息")
    
    # 系统信息
    created_by = Column(String(100), comment="创建者")
    created_at = Column(TIMESTAMP, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # Celery任务信息
    celery_task_id = Column(String(255), comment="Celery任务ID")
    
    # Relationships
    scenario_results = relationship("ScenarioResult", back_populates="task", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<EvaluationTask(task_id='{self.task_id}', status='{self.status}', progress={self.progress_percentage}%)>"
    
    def update_progress(self):
        """更新进度百分比"""
        if self.total_scenarios > 0:
            self.progress_percentage = (self.completed_scenarios / self.total_scenarios) * 100
        else:
            self.progress_percentage = 0.0
    
    def calculate_average_scores(self):
        """计算平均得分"""
        if not self.scenario_results:
            return
        
        completed_results = [r for r in self.scenario_results if r.status == 'completed']
        if not completed_results:
            return
        
        count = len(completed_results)
        self.avg_faithfulness = sum(r.faithfulness_score or 0 for r in completed_results) / count
        self.avg_answer_relevancy = sum(r.answer_relevancy_score or 0 for r in completed_results) / count
        self.avg_context_precision = sum(r.context_precision_score or 0 for r in completed_results) / count
        self.avg_context_recall = sum(r.context_recall_score or 0 for r in completed_results) / count
        self.avg_overall_score = sum(r.overall_score or 0 for r in completed_results) / count

class ScenarioResult(Base):
    """场景评测结果表"""
    __tablename__ = "scenario_results"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    scenario_id = Column(String(50), nullable=False, index=True, comment="场景唯一标识")
    task_id = Column(String(50), ForeignKey("evaluation_tasks.task_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # 关联临床场景数据
    clinical_scenario_id = Column(Integer, ForeignKey("clinical_scenario_data.id", ondelete="SET NULL"), nullable=True, index=True, comment="关联的临床场景数据ID")
    
    # 原始数据（从clinical_scenarios表获取，这里保留副本用于历史记录）
    question_number = Column(String(20), comment="题号")
    clinical_scenario = Column(Text, comment="临床场景描述")
    standard_answer = Column(String(500), comment="标准答案（首选检查项目）")
    
    # RAG-LLM推理结果
    rag_question = Column(Text, comment="RAG系统处理的问题")
    rag_answer = Column(Text, comment="RAG-LLM生成的答案")
    rag_contexts = Column(JSON, comment="RAG检索的上下文列表")
    rag_trace_data = Column(JSON, comment="RAG推理过程追踪数据")
    
    # 数据适配器处理结果
    adapted_data = Column(JSON, comment="适配器转换后的标准格式数据")
    
    # RAGAS评分结果
    faithfulness_score = Column(Float, comment="忠实度得分 (0-1)")
    answer_relevancy_score = Column(Float, comment="答案相关性得分 (0-1)")
    context_precision_score = Column(Float, comment="上下文精确度得分 (0-1)")
    context_recall_score = Column(Float, comment="上下文召回率得分 (0-1)")
    overall_score = Column(Float, comment="总体得分 (0-1)")
    
    # 详细评估信息
    ragas_evaluation_details = Column(JSON, comment="RAGAS详细评估结果")
    evaluation_metadata = Column(JSON, comment="评估元数据")
    
    # 状态信息
    status = Column(String(20), default="pending", comment="处理状态: pending, processing, completed, failed")
    processing_stage = Column(String(50), comment="当前处理阶段: inference, parsing, evaluation")
    
    # 时间信息
    inference_started_at = Column(TIMESTAMP, comment="推理开始时间")
    inference_completed_at = Column(TIMESTAMP, comment="推理完成时间")
    evaluation_started_at = Column(TIMESTAMP, comment="评估开始时间")
    evaluation_completed_at = Column(TIMESTAMP, comment="评估完成时间")
    
    # 性能指标
    inference_duration_ms = Column(Integer, comment="推理耗时（毫秒）")
    evaluation_duration_ms = Column(Integer, comment="评估耗时（毫秒）")
    total_duration_ms = Column(Integer, comment="总耗时（毫秒）")
    
    # 错误信息
    error_message = Column(Text, comment="错误信息")
    error_stage = Column(String(50), comment="出错阶段")
    error_details = Column(JSON, comment="详细错误信息")
    
    # 系统信息
    created_at = Column(TIMESTAMP, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # Celery子任务信息
    inference_task_id = Column(String(255), comment="推理任务ID")
    parsing_task_id = Column(String(255), comment="解析任务ID")
    evaluation_task_id = Column(String(255), comment="评估任务ID")
    
    # Relationships
    task = relationship("EvaluationTask", back_populates="scenario_results")
    clinical_scenario = relationship("ClinicalScenarioData", back_populates="evaluation_results")
    
    def __repr__(self):
        return f"<ScenarioResult(scenario_id='{self.scenario_id}', status='{self.status}', overall_score={self.overall_score})>"
    
    def update_duration(self):
        """更新总耗时"""
        if self.inference_started_at and self.evaluation_completed_at:
            delta = self.evaluation_completed_at - self.inference_started_at
            self.total_duration_ms = int(delta.total_seconds() * 1000)
    
    def is_completed(self) -> bool:
        """检查是否已完成"""
        return self.status == 'completed' and all([
            self.faithfulness_score is not None,
            self.answer_relevancy_score is not None,
            self.context_precision_score is not None,
            self.context_recall_score is not None,
            self.overall_score is not None
        ])

class EvaluationMetrics(Base):
    """评测指标历史记录表"""
    __tablename__ = "evaluation_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(50), ForeignKey("evaluation_tasks.task_id", ondelete="CASCADE"), nullable=False)
    metric_name = Column(String(100), nullable=False, comment="指标名称")
    metric_value = Column(Float, nullable=False, comment="指标值")
    metric_category = Column(String(50), comment="指标类别: ragas, performance, custom")
    
    # 计算信息
    calculation_method = Column(String(100), comment="计算方法")
    sample_size = Column(Integer, comment="样本数量")
    confidence_interval = Column(JSON, comment="置信区间")
    
    # 时间信息
    measured_at = Column(TIMESTAMP, server_default=func.now(), comment="测量时间")
    
    def __repr__(self):
        return f"<EvaluationMetrics(task_id='{self.task_id}', metric='{self.metric_name}', value={self.metric_value})>"

class DataAdapterLog(Base):
    """数据适配器日志表"""
    __tablename__ = "data_adapter_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    scenario_id = Column(String(50), nullable=False, index=True)
    task_id = Column(String(50), ForeignKey("evaluation_tasks.task_id", ondelete="CASCADE"), nullable=False)
    
    # 适配信息
    input_format = Column(String(100), comment="输入数据格式")
    output_format = Column(String(100), comment="输出数据格式")
    adapter_version = Column(String(20), comment="适配器版本")
    
    # 数据内容
    raw_input_data = Column(JSON, comment="原始输入数据")
    transformed_output_data = Column(JSON, comment="转换后输出数据")
    
    # 转换统计
    transformation_rules_applied = Column(JSON, comment="应用的转换规则")
    data_quality_score = Column(Float, comment="数据质量评分")
    
    # 性能信息
    processing_time_ms = Column(Integer, comment="处理耗时（毫秒）")
    
    # 状态信息
    status = Column(String(20), default="success", comment="适配状态: success, warning, error")
    warnings = Column(JSON, comment="警告信息")
    errors = Column(JSON, comment="错误信息")
    
    # 时间信息
    created_at = Column(TIMESTAMP, server_default=func.now(), comment="创建时间")
    
    def __repr__(self):
        return f"<DataAdapterLog(scenario_id='{self.scenario_id}', status='{self.status}', quality_score={self.data_quality_score})>"