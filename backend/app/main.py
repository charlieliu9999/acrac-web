import asyncio
import sys
import os

# 修复 RAGAS 与 uvloop 的兼容性问题
# 禁用 nest_asyncio 以避免与 uvloop 的冲突
os.environ['NEST_ASYNCIO_DISABLE'] = '1'

# 为了解决 RAGAS 与 uvloop 的兼容性问题，我们不使用 uvloop
# 而是使用默认的 asyncio 事件循环策略
if sys.platform != 'win32':
    # 确保使用默认的事件循环策略，避免 uvloop 相关问题
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import engine
from app.models import Base
from app.api.api_v1.api import api_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up ACRAC API...")
    # Create database tables (best-effort; don't crash if DB not available)
    try:
        # Ensure pgvector extension exists before creating tables
        try:
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
        except Exception as ee:
            logger.warning(f"Skip CREATE EXTENSION vector: {ee}")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created")
    except Exception as e:
        logger.warning(f"Skip DB init (limited mode): {e}")
    yield
    # Shutdown
    logger.info("Shutting down ACRAC API...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="ACRAC数据展示与推理系统API",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Add trusted host middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    """根路径，返回API信息"""
    return {
        "message": f"欢迎使用 {settings.PROJECT_NAME} API",
        "version": settings.VERSION,
        "docs_url": "/docs",
        "api_prefix": settings.API_V1_STR
    }

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "service": "acrac-api"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=5173,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
