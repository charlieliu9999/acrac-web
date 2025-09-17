#!/usr/bin/env python3
"""
临床场景数据模型
用于存储上传的Excel文件中的临床场景数据
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from app.core.database import Base

class ClinicalScenarioData(Base):
    """临床场景数据表
    
    存储从Excel文件解析的临床场景数据，包括：
    - 题号
    - 临床场景描述
    - 首选检查项目（标准答案）
    - 其他相关信息
    """
    __tablename__ = "clinical_scenario_data"
    
    id = Column(Integer, primary_key=True, index=True, comment="主键ID")
    
    # 基本信息
    question_id = Column(String(50), nullable=False, index=True, comment="题号")
    clinical_query = Column(Text, nullable=False, comment="临床场景描述")
    ground_truth = Column(Text, nullable=False, comment="首选检查项目（标准答案）")
    
    # 扩展信息
    category = Column(String(100), nullable=True, comment="分类")
    difficulty = Column(String(20), nullable=True, comment="难度等级")
    keywords = Column(Text, nullable=True, comment="关键词")
    
    # 元数据
    source_file = Column(String(255), nullable=True, comment="来源文件名")
    file_row_number = Column(Integer, nullable=True, comment="文件中的行号")
    upload_batch_id = Column(String(10), nullable=False, index=True, comment="上传批次ID")
    
    # 状态信息
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_validated = Column(Boolean, default=False, comment="是否已验证")
    validation_notes = Column(Text, nullable=True, comment="验证备注")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    
    # 关联关系
    evaluation_results = relationship("ScenarioResult", back_populates="clinical_scenario")
    
    def __repr__(self):
        return f"<ClinicalScenario(id={self.id}, question_id='{self.question_id}', query='{self.clinical_query[:50]}...')>"
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            "id": self.id,
            "question_id": self.question_id,
            "clinical_query": self.clinical_query,
            "ground_truth": self.ground_truth,
            "category": self.category,
            "difficulty": self.difficulty,
            "keywords": self.keywords,
            "source_file": self.source_file,
            "file_row_number": self.file_row_number,
            "upload_batch_id": self.upload_batch_id,
            "is_active": self.is_active,
            "is_validated": self.is_validated,
            "validation_notes": self.validation_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def to_test_case(self):
        """转换为评测用例格式"""
        return {
            "question_id": self.question_id,
            "clinical_query": self.clinical_query,
            "ground_truth": self.ground_truth,
            "metadata": {
                "id": self.id,
                "category": self.category,
                "difficulty": self.difficulty,
                "keywords": self.keywords,
                "source_file": self.source_file
            }
        }

class DataUploadBatch(Base):
    """数据上传批次表
    
    记录每次数据上传的批次信息
    """
    __tablename__ = "data_upload_batches"
    
    id = Column(Integer, primary_key=True, index=True, comment="主键ID")
    
    # 批次信息
    batch_id = Column(String(10), unique=True, nullable=False, index=True, comment="批次ID")
    batch_name = Column(String(255), nullable=False, comment="批次名称")
    description = Column(Text, nullable=True, comment="批次描述")
    
    # 文件信息
    original_filename = Column(String(255), nullable=False, comment="原始文件名")
    file_path = Column(String(500), nullable=True, comment="文件存储路径")
    file_size = Column(Integer, nullable=True, comment="文件大小（字节）")
    file_hash = Column(String(64), nullable=True, comment="文件MD5哈希")
    
    # 处理统计
    total_rows = Column(Integer, default=0, comment="总行数")
    valid_rows = Column(Integer, default=0, comment="有效行数")
    invalid_rows = Column(Integer, default=0, comment="无效行数")
    
    # 处理状态
    status = Column(String(20), default="pending", comment="处理状态：pending/processing/completed/failed")
    error_message = Column(Text, nullable=True, comment="错误信息")
    processing_log = Column(JSON, nullable=True, comment="处理日志")
    
    # 时间戳
    uploaded_at = Column(DateTime, default=datetime.now, comment="上传时间")
    processed_at = Column(DateTime, nullable=True, comment="处理完成时间")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    
    def __repr__(self):
        return f"<DataUploadBatch(id={self.id}, batch_id='{self.batch_id}', filename='{self.original_filename}')>"
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "batch_name": self.batch_name,
            "description": self.description,
            "original_filename": self.original_filename,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "file_hash": self.file_hash,
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "invalid_rows": self.invalid_rows,
            "status": self.status,
            "error_message": self.error_message,
            "processing_log": self.processing_log,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }