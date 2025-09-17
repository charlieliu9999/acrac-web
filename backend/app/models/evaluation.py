from sqlalchemy import Column, Integer, String, Text, JSON, Float, DateTime, Boolean
from sqlalchemy.sql import func
from app.core.database import Base


class EvaluationResult(Base):
    """评估结果模型"""
    __tablename__ = "evaluation_results"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, nullable=False, comment="关联的任务ID")
    result_data = Column(JSON, comment="结果数据")
    status = Column(String(50), default="pending", comment="结果状态")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TestData(Base):
    """测试数据模型"""
    __tablename__ = "test_data"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(String(255), nullable=False, index=True, comment="问题ID")
    clinical_query = Column(Text, nullable=False, comment="临床查询")
    ground_truth = Column(Text, nullable=False, comment="标准答案")
    source_file = Column(String(255), comment="来源文件")
    upload_batch = Column(String(255), comment="上传批次")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())