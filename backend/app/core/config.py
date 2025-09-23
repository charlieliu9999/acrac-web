import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import List, Optional
import os
from pathlib import Path

# Determine whether to load local .env (skip in Docker)
_skip_local = os.getenv("SKIP_LOCAL_DOTENV", "").lower() in ("1", "true", "yes") or \
               os.getenv("DOCKER_CONTEXT", "").lower() in ("1", "true", "yes")
_env_file_path = str(Path(__file__).resolve().parents[2] / ".env") if not _skip_local else None


class Settings(BaseSettings):
    # Project info
    PROJECT_NAME: str = "ACRAC System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database - 连接到Docker容器中的PostgreSQL
    # 修复：优先使用环境变量中的DATABASE_URL，如果没有则使用默认值
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:password@postgres:5432/acrac_db")
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 0
    
    # PostgreSQL 配置
    PGHOST: str = os.getenv("PGHOST", "postgres")  # 修复：使用docker服务名而不是localhost
    PGPORT: str = os.getenv("PGPORT", "5432")
    PGDATABASE: str = os.getenv("PGDATABASE", "acrac_db")
    PGUSER: str = os.getenv("PGUSER", "postgres")
    PGPASSWORD: str = os.getenv("PGPASSWORD", "password")
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")  # 修复：使用docker服务名而不是localhost
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here-please-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"]
    )
    
    @field_validator('BACKEND_CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            # 尝试解析JSON格式
            import json
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
            
            # 处理类似 [url1,url2] 格式的字符串
            if v.startswith('[') and v.endswith(']'):
                # 移除方括号并按逗号分割
                content = v[1:-1]
                return [origin.strip() for origin in content.split(',') if origin.strip()]
            
            # 如果不是特殊格式，按逗号分割
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v
    
    # Celery
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/1")  # 修复：使用docker服务名而不是localhost
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/2")  # 修复：使用docker服务名而不是localhost
    
    # Embedding Model (统一使用嵌入配置)
    EMBEDDING_MODEL_TYPE: str = "bge-m3"
    EMBEDDING_MODEL_NAME: str = "bge-m3:latest"
    EMBEDDING_DIMENSION: int = 1024
    
    # SiliconFlow API Configuration
    # 安全性：不再提供任何默认密钥，必须通过环境变量配置
    SILICONFLOW_API_KEY: str = os.getenv("SILICONFLOW_API_KEY", "")
    SILICONFLOW_EMBEDDING_MODEL: str = os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3")
    SILICONFLOW_LLM_MODEL: str = os.getenv("SILICONFLOW_LLM_MODEL", "Qwen/Qwen2.5-32B-Instruct")
    SILICONFLOW_BASE_URL: str = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    
    # Reranker Configuration
    RERANKER_MODEL: str = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
    
    # OpenAI API Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # RAG API Configuration
    RAG_API_URL: str = os.getenv("RAG_API_URL", "http://127.0.0.1:8002/api/v1/acrac/rag-llm/intelligent-recommendation")

    # RAG 配置
    VECTOR_SIMILARITY_THRESHOLD: float = 0.6
    DEBUG_MODE: bool = True
    
    # 提示词配置参数
    RAG_TOP_SCENARIOS: int = 2
    RAG_TOP_RECOMMENDATIONS_PER_SCENARIO: int = 3
    RAG_SHOW_REASONING: bool = True
    
    # File Upload
    MAX_UPLOAD_SIZE: int = 104857600  # 100MB
    ALLOWED_EXTENSIONS: List[str] = [".xlsx", ".xls", ".csv", ".json"]
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/acrac.log"
    
    # Development
    DEBUG: bool = True
    RELOAD: bool = True

    # Rules Engine (default disabled)
    RULES_ENABLED: bool = False
    RULES_AUDIT_ONLY: bool = True
    RULES_CONFIG_PATH: str = str(Path(__file__).resolve().parents[2] / "config" / "rules_packs.json")
    # Pydantic v2 settings configuration
    # - In Docker, skip loading backend/.env to avoid localhost DSNs
    # - Otherwise, load backend/.env for local dev
    # - Be case sensitive; ignore extra env keys
    model_config = SettingsConfigDict(
        env_file=_env_file_path,
        case_sensitive=True,
        extra="ignore",
    )

# Create settings instance
settings = Settings()

# Ensure log directory exists
log_dir = Path(settings.LOG_FILE).parent
log_dir.mkdir(exist_ok=True)
