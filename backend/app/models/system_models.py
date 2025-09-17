from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, TIMESTAMP, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base

class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(50), default="viewer", comment="用户角色: viewer, editor, reviewer, admin")
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"

class InferenceLog(Base):
    """推理日志表"""
    __tablename__ = "inference_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    query_text = Column(Text, nullable=False, comment="查询文本")
    query_language = Column(String(10), default="zh", comment="查询语言")
    inference_method = Column(String(50), comment="推理方法: rag, rule_based, case_voting")
    result = Column(JSON, comment="推理结果")
    confidence_score = Column(Float, comment="置信度分数")
    success = Column(Boolean, nullable=False, comment="是否成功")
    error_message = Column(Text, comment="错误信息")
    execution_time = Column(Float, comment="执行时间(秒)")
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Relationships
    user = relationship("User")
    
    def __repr__(self):
        return f"<InferenceLog(id={self.id}, method='{self.inference_method}', success={self.success})>"

class Rule(Base):
    """规则表"""
    __tablename__ = "rules"
    
    id = Column(Integer, primary_key=True, index=True)
    rule_name = Column(String(255), nullable=False, comment="规则名称")
    rule_content = Column(JSON, nullable=False, comment="规则内容")
    description = Column(Text, comment="规则描述")
    status = Column(String(50), default="draft", comment="状态: draft, review, approved, published, deprecated")
    priority = Column(Integer, default=100, comment="优先级，数字越小优先级越高")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    version = Column(Integer, default=1, comment="版本号")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    approver = relationship("User", foreign_keys=[approved_by])
    
    def __repr__(self):
        return f"<Rule(id={self.id}, name='{self.rule_name}', status='{self.status}')>"

class DataImportTask(Base):
    """数据导入任务表"""
    __tablename__ = "data_import_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False, comment="文件名")
    file_size = Column(Integer, comment="文件大小(字节)")
    file_type = Column(String(50), comment="文件类型")
    status = Column(String(50), default="pending", comment="状态: pending, processing, completed, failed")
    total_records = Column(Integer, comment="总记录数")
    processed_records = Column(Integer, default=0, comment="已处理记录数")
    success_records = Column(Integer, default=0, comment="成功记录数")
    error_records = Column(Integer, default=0, comment="错误记录数")
    error_details = Column(JSON, comment="错误详情")
    started_at = Column(TIMESTAMP, comment="开始时间")
    completed_at = Column(TIMESTAMP, comment="完成时间")
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Relationships
    user = relationship("User")
    
    def __repr__(self):
        return f"<DataImportTask(id={self.id}, filename='{self.filename}', status='{self.status}')>"

class ExcelEvaluationData(Base):
    """Excel评测数据表"""
    __tablename__ = "excel_evaluation_data"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(50), nullable=False, comment="评测任务ID")
    filename = Column(String(255), nullable=False, comment="Excel文件名")
    question = Column(Text, nullable=False, comment="问题")
    ground_truth = Column(Text, nullable=False, comment="标准答案")
    contexts = Column(JSON, comment="上下文信息")
    answer = Column(Text, comment="模型回答")
    
    # RAGAS评分字段
    faithfulness = Column(Float, comment="忠实度评分")
    answer_relevancy = Column(Float, comment="答案相关性评分")
    context_precision = Column(Float, comment="上下文精确度评分")
    context_recall = Column(Float, comment="上下文召回率评分")
    
    # 评测状态
    status = Column(String(50), default="pending", comment="状态: pending, completed, failed")
    error_message = Column(Text, comment="错误信息")
    
    # 时间戳
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<ExcelEvaluationData(id={self.id}, task_id='{self.task_id}', status='{self.status}')>"
