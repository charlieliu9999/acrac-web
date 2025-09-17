"""
嵌入模型和服务配置
"""
import os
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings
from pydantic import Field

class EmbeddingConfig(BaseSettings):
    """嵌入模型和服务配置类"""
    
    # 模型配置
    EMBEDDING_MODEL_TYPE: str = Field(default="bge-m3", description="嵌入模型类型")
    EMBEDDING_MODEL_NAME: str = Field(default="bge-m3:latest", description="模型名称")
    EMBEDDING_DIMENSION: int = Field(default=1024, description="向量维度")
    
    # Ollama 服务配置
    OLLAMA_ENABLED: bool = Field(default=True, description="是否启用Ollama服务")
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434", description="Ollama服务地址")
    OLLAMA_MODEL_NAME: str = Field(default="bge-m3:latest", description="Ollama模型名称")
    OLLAMA_TIMEOUT: int = Field(default=300, description="Ollama请求超时时间(秒)")
    
    # 本地模型配置
    LOCAL_MODEL_ENABLED: bool = Field(default=False, description="是否启用本地模型")
    LOCAL_MODEL_PATH: Optional[str] = Field(default=None, description="本地模型路径")
    
    # 性能配置
    BATCH_SIZE: int = Field(default=32, description="批处理大小")
    MAX_WORKERS: int = Field(default=4, description="最大工作线程数")
    CACHE_ENABLED: bool = Field(default=True, description="是否启用缓存")
    CACHE_TTL: int = Field(default=3600, description="缓存生存时间(秒)")
    
    # 医疗特定配置
    MEDICAL_PREPROCESSING: bool = Field(default=True, description="是否启用医疗文本预处理")
    MEDICAL_TERMS_NORMALIZATION: bool = Field(default=True, description="是否启用医疗术语标准化")
    CONTEXT_PREFIX_ENABLED: bool = Field(default=True, description="是否启用上下文前缀")
    
    model_config = {
        "env_file": ".env",
        "env_prefix": "EMBEDDING_",
        "case_sensitive": False,
        "extra": "ignore"  # 忽略额外的环境变量
    }

# 支持的模型配置
SUPPORTED_MODELS = {
    "bge-m3": {
        "name": "bge-m3:latest",
        "dimension": 1024,
        "description": "BGE-M3多语言模型，支持中英文，医疗场景推荐",
        "ollama_name": "bge-m3:latest",
        "recommended": True
    },
    "nomic-embed-text": {
        "name": "nomic-embed-text:latest",
        "dimension": 768,
        "description": "Nomic Embed Text模型，多语言支持，医疗场景推荐",
        "ollama_name": "nomic-embed-text:latest",
        "recommended": False
    },
    "bge-large-zh": {
        "name": "BAAI/bge-large-zh-v1.5",
        "dimension": 1024,
        "description": "BGE-Large-ZH中文优化模型，医疗场景最佳选择",
        "ollama_name": "bge-large-zh",
        "recommended": False
    },
    "bge-base-zh": {
        "name": "BAAI/bge-base-zh-v1.5",
        "dimension": 768,
        "description": "BGE-Base-ZH中文优化模型，平衡性能和速度",
        "ollama_name": "bge-base-zh",
        "recommended": False
    },
    "m3e-base": {
        "name": "moka-ai/m3e-base",
        "dimension": 768,
        "description": "M3E-Base中文优化模型",
        "ollama_name": "m3e-base",
        "recommended": False
    },
    "text2vec-chinese": {
        "name": "text2vec-chinese",
        "dimension": 768,
        "description": "Text2Vec-Chinese纯中文模型",
        "ollama_name": "text2vec-chinese",
        "recommended": False
    }
}

# 服务类型配置
SERVICE_TYPES = {
    "ollama": {
        "name": "Ollama",
        "description": "本地Ollama服务，支持多种模型",
        "recommended": True,
        "features": [
            "本地部署",
            "支持多种模型",
            "高性能",
            "易于管理"
        ]
    },
    "huggingface": {
        "name": "Hugging Face",
        "description": "Hugging Face Transformers库",
        "recommended": False,
        "features": [
            "在线模型",
            "自动下载",
            "易于使用",
            "需要网络"
        ]
    },
    "local": {
        "name": "本地模型",
        "description": "本地安装的模型文件",
        "recommended": False,
        "features": [
            "完全离线",
            "最高性能",
            "需要存储空间",
            "手动管理"
        ]
    }
}

def get_model_config(model_type: str) -> Dict[str, Any]:
    """获取模型配置"""
    return SUPPORTED_MODELS.get(model_type, SUPPORTED_MODELS["bge-large-zh"])

def get_service_config(service_type: str) -> Dict[str, Any]:
    """获取服务配置"""
    return SERVICE_TYPES.get(service_type, SERVICE_TYPES["ollama"])

def get_recommended_model() -> str:
    """获取推荐的模型"""
    for model_type, config in SUPPORTED_MODELS.items():
        if config.get("recommended", False):
            return model_type
    return "bge-m3"

def get_recommended_service() -> str:
    """获取推荐的服务"""
    for service_type, config in SERVICE_TYPES.items():
        if config.get("recommended", False):
            return service_type
    return "ollama"

# 全局配置实例
embedding_config = EmbeddingConfig()
