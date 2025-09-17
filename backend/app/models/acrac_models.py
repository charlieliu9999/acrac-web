"""
ACRAC数据模型 - 优化后的五表分离架构
"""
from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, TIMESTAMP, Boolean, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.core.database import Base

class Panel(Base):
    """Panel表 - 科室/专科"""
    __tablename__ = "panels"
    
    id = Column(Integer, primary_key=True, index=True)
    semantic_id = Column(String(20), unique=True, nullable=False, comment="语义化ID: P0001, P0002...")
    name_en = Column(String(255), nullable=False, comment="英文名称")
    name_zh = Column(String(255), nullable=False, comment="中文名称")
    description = Column(Text, comment="描述")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_at = Column(TIMESTAMP, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    embedding = Column(Vector(1024), comment="向量嵌入")
    
    # Relationships
    topics = relationship("Topic", back_populates="panel", cascade="all, delete-orphan")
    scenarios = relationship("ClinicalScenario", back_populates="panel", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Panel(semantic_id='{self.semantic_id}', name_zh='{self.name_zh}')>"

class Topic(Base):
    """Topic表 - 临床主题"""
    __tablename__ = "topics"
    
    id = Column(Integer, primary_key=True, index=True)
    semantic_id = Column(String(20), unique=True, nullable=False, comment="语义化ID: T0001, T0002...")
    panel_id = Column(Integer, ForeignKey("panels.id", ondelete="CASCADE"), nullable=False)
    name_en = Column(String(500), nullable=False, comment="英文名称")
    name_zh = Column(String(500), nullable=False, comment="中文名称")
    description = Column(Text, comment="描述")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_at = Column(TIMESTAMP, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    embedding = Column(Vector(1024), comment="层次化向量嵌入")
    
    # Relationships
    panel = relationship("Panel", back_populates="topics")
    scenarios = relationship("ClinicalScenario", back_populates="topic", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Topic(semantic_id='{self.semantic_id}', name_zh='{self.name_zh}')>"

class ClinicalScenario(Base):
    """ClinicalScenario表 - 临床场景"""
    __tablename__ = "clinical_scenarios"
    
    id = Column(Integer, primary_key=True, index=True)
    semantic_id = Column(String(20), unique=True, nullable=False, comment="语义化ID: S0001, S0002...")
    panel_id = Column(Integer, ForeignKey("panels.id", ondelete="CASCADE"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False)
    description_en = Column(Text, nullable=False, comment="英文描述")
    description_zh = Column(Text, nullable=False, comment="中文描述")
    clinical_context = Column(Text, comment="临床上下文")
    patient_population = Column(String(100), comment="患者人群：孕妇、儿童、老年等")
    risk_level = Column(String(50), comment="风险等级：高风险、中风险、低风险")
    age_group = Column(String(50), comment="年龄组：40岁以上、25岁以下等")
    gender = Column(String(20), comment="性别：女性、男性、不限")
    pregnancy_status = Column(String(50), comment="妊娠状态：妊娠期、哺乳期、非妊娠期")
    urgency_level = Column(String(50), comment="紧急程度：急诊、择期")
    symptom_category = Column(String(100), comment="症状分类：疼痛、肿块、出血等")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_at = Column(TIMESTAMP, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    embedding = Column(Vector(1024), comment="层次化向量嵌入")
    
    # Relationships
    panel = relationship("Panel", back_populates="scenarios")
    topic = relationship("Topic", back_populates="scenarios")
    recommendations = relationship("ClinicalRecommendation", back_populates="scenario", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ClinicalScenario(semantic_id='{self.semantic_id}', patient_population='{self.patient_population}')>"

class ProcedureDictionary(Base):
    """ProcedureDictionary表 - 检查项目字典"""
    __tablename__ = "procedure_dictionary"
    
    id = Column(Integer, primary_key=True, index=True)
    semantic_id = Column(String(20), unique=True, nullable=False, comment="语义化ID: PR0001, PR0002...")
    name_en = Column(String(500), nullable=False, comment="英文名称")
    name_zh = Column(String(500), nullable=False, comment="中文名称")
    modality = Column(String(50), comment="检查方式：CT, MRI, US, XR等")
    body_part = Column(String(100), comment="检查部位：头部、胸部、腹部等")
    contrast_used = Column(Boolean, default=False, comment="是否使用对比剂")
    radiation_level = Column(String(50), comment="辐射等级：无、低、中、高")
    exam_duration = Column(Integer, comment="检查时长（分钟）")
    preparation_required = Column(Boolean, default=False, comment="是否需要准备")
    standard_code = Column(String(50), comment="标准编码（医保编码等）")
    icd10_code = Column(String(20), comment="ICD10编码")
    cpt_code = Column(String(20), comment="CPT编码")
    description_en = Column(Text, comment="英文描述")
    description_zh = Column(Text, comment="中文描述")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_at = Column(TIMESTAMP, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    embedding = Column(Vector(1024), comment="独立向量嵌入")
    
    # Relationships
    recommendations = relationship("ClinicalRecommendation", back_populates="procedure", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ProcedureDictionary(semantic_id='{self.semantic_id}', name_zh='{self.name_zh}', modality='{self.modality}')>"

class ClinicalRecommendation(Base):
    """ClinicalRecommendation表 - 临床推荐关系（核心表）"""
    __tablename__ = "clinical_recommendations"
    
    id = Column(Integer, primary_key=True, index=True)
    semantic_id = Column(String(50), unique=True, nullable=False, comment="语义化ID: CR000001, CR000002...")
    scenario_id = Column(String(20), ForeignKey("clinical_scenarios.semantic_id", ondelete="CASCADE"), nullable=False)
    procedure_id = Column(String(20), ForeignKey("procedure_dictionary.semantic_id", ondelete="CASCADE"), nullable=False)
    appropriateness_rating = Column(Integer, comment="适宜性评分 1-9")
    appropriateness_category = Column(String(100), comment="适宜性类别")
    appropriateness_category_zh = Column(String(100), comment="适宜性类别中文")
    reasoning_en = Column(Text, comment="英文推荐理由")
    reasoning_zh = Column(Text, comment="中文推荐理由")
    evidence_level = Column(String(50), comment="证据强度")
    median_rating = Column(Float, comment="中位数评分")
    rating_variance = Column(Float, comment="评分方差")
    consensus_level = Column(String(50), comment="共识水平")
    adult_radiation_dose = Column(String(50), comment="成人辐射剂量")
    pediatric_radiation_dose = Column(String(50), comment="儿童辐射剂量")
    contraindications = Column(Text, comment="禁忌症")
    special_considerations = Column(Text, comment="特殊考虑")
    pregnancy_safety = Column(String(50), comment="妊娠安全性：安全、禁忌、谨慎使用")
    is_generated = Column(Boolean, default=False, comment="是否AI生成")
    confidence_score = Column(Float, default=1.0, comment="置信度评分")
    last_reviewed_date = Column(Date, comment="最后审查日期")
    reviewer_id = Column(Integer, comment="审查者ID")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_at = Column(TIMESTAMP, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    embedding = Column(Vector(1024), comment="完整临床决策向量嵌入")
    
    # Relationships
    scenario = relationship("ClinicalScenario", back_populates="recommendations")
    procedure = relationship("ProcedureDictionary", back_populates="recommendations")
    
    def __repr__(self):
        return f"<ClinicalRecommendation(semantic_id='{self.semantic_id}', rating={self.appropriateness_rating})>"

# 辅助表
class VectorSearchLog(Base):
    """向量搜索日志表"""
    __tablename__ = "vector_search_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    query_text = Column(Text, nullable=False, comment="搜索文本")
    query_type = Column(String(50), comment="查询类型")
    search_vector = Column(Vector(1024), comment="搜索向量")
    results_count = Column(Integer, comment="结果数量")
    search_time_ms = Column(Integer, comment="搜索耗时（毫秒）")
    user_id = Column(Integer, comment="用户ID")
    created_at = Column(TIMESTAMP, server_default=func.now(), comment="创建时间")
    
    def __repr__(self):
        return f"<VectorSearchLog(id={self.id}, query='{self.query_text[:50]}...')>"

class DataUpdateHistory(Base):
    """数据更新历史表"""
    __tablename__ = "data_update_history"
    
    id = Column(Integer, primary_key=True, index=True)
    table_name = Column(String(50), nullable=False, comment="表名")
    record_id = Column(String(50), nullable=False, comment="记录ID")
    operation = Column(String(20), nullable=False, comment="操作类型：INSERT, UPDATE, DELETE")
    old_data = Column(Text, comment="旧数据（JSON格式）")
    new_data = Column(Text, comment="新数据（JSON格式）")
    user_id = Column(Integer, comment="操作用户ID")
    created_at = Column(TIMESTAMP, server_default=func.now(), comment="创建时间")
    
    def __repr__(self):
        return f"<DataUpdateHistory(id={self.id}, table='{self.table_name}', operation='{self.operation}')>"