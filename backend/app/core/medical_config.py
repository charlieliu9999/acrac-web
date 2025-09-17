"""
医疗系统专用配置
"""
from typing import Dict, List, Any
import os

class MedicalConfig:
    """医疗系统配置类"""
    
    # 向量化模型配置
    EMBEDDING_MODELS = {
        "bge-large-zh": {
            "name": "BAAI/bge-large-zh-v1.5",
            "dimension": 1024,
            "description": "BGE-Large-ZH中文优化模型，医疗场景最佳选择",
            "recommended": True
        },
        "bge-base-zh": {
            "name": "BAAI/bge-base-zh-v1.5",
            "dimension": 768,
            "description": "BGE-Base-ZH中文优化模型，平衡性能和速度",
            "recommended": True
        },
        "m3e-base": {
            "name": "moka-ai/m3e-base",
            "dimension": 768,
            "description": "中文优化多语言模型，适合医疗场景",
            "recommended": False
        },
        "text2vec-chinese": {
            "name": "text2vec-chinese",
            "dimension": 768,
            "description": "纯中文优化模型",
            "recommended": False
        },
        "all-MiniLM-L6-v2": {
            "name": "sentence-transformers/all-MiniLM-L6-v2",
            "dimension": 384,
            "description": "轻量级英文模型",
            "recommended": False
        }
    }
    
    # 向量数据库配置
    VECTOR_DATABASES = {
        "qdrant": {
            "name": "Qdrant",
            "description": "专为向量搜索优化，支持中文和医疗场景",
            "recommended": True,
            "features": [
                "高性能向量搜索",
                "支持过滤和混合搜索",
                "易于部署和维护",
                "支持中文和医疗场景"
            ]
        },
        "weaviate": {
            "name": "Weaviate",
            "description": "支持多模态搜索，内置医疗领域优化",
            "recommended": True,
            "features": [
                "多模态搜索支持",
                "内置医疗领域优化",
                "GraphQL查询接口",
                "企业级功能丰富"
            ]
        },
        "milvus": {
            "name": "Milvus",
            "description": "高性能向量数据库，适合大规模数据",
            "recommended": False,
            "features": [
                "高性能向量搜索",
                "支持大规模数据",
                "适合生产环境",
                "需要更多运维工作"
            ]
        },
        "pgvector": {
            "name": "PostgreSQL + pgvector",
            "description": "基于PostgreSQL的向量扩展",
            "recommended": False,
            "features": [
                "与现有数据库集成",
                "支持SQL查询",
                "性能相对较低",
                "适合小规模应用"
            ]
        }
    }
    
    # 医疗术语映射
    MEDICAL_TERMS = {
        "imaging_modalities": {
            "CT": "计算机断层扫描",
            "MRI": "磁共振成像",
            "X光": "X射线摄影",
            "DR": "数字化X射线摄影",
            "超声": "超声波检查",
            "PET": "正电子发射断层扫描",
            "SPECT": "单光子发射计算机断层扫描",
            "DSA": "数字减影血管造影",
            "乳腺钼靶": "乳腺X射线摄影"
        },
        "body_parts": {
            "胸部": "胸部",
            "腹部": "腹部",
            "头部": "头部",
            "四肢": "四肢",
            "脊柱": "脊柱",
            "心脏": "心脏",
            "肺部": "肺部",
            "肝脏": "肝脏",
            "肾脏": "肾脏",
            "胃部": "胃部",
            "肠道": "肠道",
            "骨骼": "骨骼",
            "肌肉": "肌肉",
            "神经": "神经",
            "血管": "血管",
            "淋巴": "淋巴"
        },
        "conditions": {
            "肿瘤": "肿瘤",
            "炎症": "炎症",
            "感染": "感染",
            "损伤": "损伤",
            "病变": "病变",
            "异常": "异常",
            "正常": "正常",
            "阳性": "阳性",
            "阴性": "阴性",
            "急性": "急性",
            "慢性": "慢性",
            "良性": "良性",
            "恶性": "恶性",
            "早期": "早期",
            "晚期": "晚期",
            "轻度": "轻度",
            "中度": "中度",
            "重度": "重度",
            "严重": "严重",
            "轻微": "轻微",
            "明显": "明显",
            "显著": "显著"
        },
        "procedures": {
            "检查": "检查",
            "诊断": "诊断",
            "治疗": "治疗",
            "手术": "手术",
            "介入": "介入治疗",
            "放疗": "放射治疗",
            "化疗": "化学治疗",
            "免疫治疗": "免疫治疗",
            "靶向治疗": "靶向治疗"
        }
    }
    
    # 医疗文本预处理规则
    TEXT_PREPROCESSING = {
        "max_length": 1000,
        "min_length": 5,
        "remove_special_chars": True,
        "normalize_whitespace": True,
        "add_context_prefix": True
    }
    
    # 向量搜索配置
    VECTOR_SEARCH = {
        "default_limit": 10,
        "similarity_threshold": 0.7,
        "max_results": 100,
        "enable_hybrid_search": True,
        "enable_filtering": True
    }
    
    # 医疗领域特定配置
    MEDICAL_DOMAINS = {
        "radiology": {
            "name": "放射学",
            "keywords": ["影像", "扫描", "X光", "CT", "MRI", "超声"],
            "text_type": "imaging"
        },
        "pathology": {
            "name": "病理学",
            "keywords": ["病理", "活检", "细胞", "组织", "诊断"],
            "text_type": "pathology"
        },
        "laboratory": {
            "name": "实验室检查",
            "keywords": ["血液", "尿液", "生化", "免疫", "微生物"],
            "text_type": "laboratory"
        },
        "surgery": {
            "name": "外科学",
            "keywords": ["手术", "外科", "切除", "修复", "重建"],
            "text_type": "surgery"
        },
        "internal_medicine": {
            "name": "内科学",
            "keywords": ["内科", "药物治疗", "慢性病", "心血管", "呼吸"],
            "text_type": "internal"
        }
    }
    
    @classmethod
    def get_recommended_model(cls) -> str:
        """获取推荐的向量化模型"""
        for model_name, config in cls.EMBEDDING_MODELS.items():
            if config.get("recommended", False):
                return model_name
        return "bge-large-zh"
    
    @classmethod
    def get_recommended_database(cls) -> str:
        """获取推荐的向量数据库"""
        for db_name, config in cls.VECTOR_DATABASES.items():
            if config.get("recommended", False):
                return db_name
        return "qdrant"
    
    @classmethod
    def get_medical_terms(cls, category: str = None) -> Dict[str, str]:
        """获取医疗术语映射"""
        if category:
            return cls.MEDICAL_TERMS.get(category, {})
        return cls.MEDICAL_TERMS
    
    @classmethod
    def get_domain_config(cls, domain: str) -> Dict[str, Any]:
        """获取医疗领域配置"""
        return cls.MEDICAL_DOMAINS.get(domain, {})
    
    @classmethod
    def get_text_type_for_domain(cls, domain: str) -> str:
        """根据医疗领域获取文本类型"""
        domain_config = cls.get_domain_config(domain)
        return domain_config.get("text_type", "general")

# 全局配置实例
medical_config = MedicalConfig()
