# ACRAC 项目目录结构说明（2025 更新）

该文档概览最新的仓库布局，聚焦经常需要关注的目录与文件。所有路径均相对于项目根目录 `ACRAC-web/`。

## 根目录
- `README.md`：总体说明与启动方式
- `docker-compose.yml`、`start.sh`、`start-dev.sh`、`stop.sh`：容器化与本地启动脚本
- `docs/`：产品、部署与评测文档集合
- `backend/`：FastAPI 与数据处理代码
- `frontend/`：React + Vite 管理控制台
- `deployment/`、`config/`、`data/`：部署配置与原始数据
- `logs/`：运行日志（默认空目录，便于挂载）

## backend/
- `app/`
  - `main.py`：FastAPI 入口
  - `api/api_v1/`
    - `api.py`：统一注册全部 v1 路由
    - `endpoints/`：按功能拆分的路由文件（如 `rag_llm_api.py`、`rag_services_api.py`、`production_recommendation_api.py`）
  - `core/`：配置、日志、数据库会话（`config.py`、`database.py`）
  - `models/`：SQLAlchemy 模型定义
  - `schemas/`：Pydantic 请求 / 响应模型
  - `services/`：业务服务层，含 RAG、向量检索、规 则引擎等实现
- `scripts/`：数据构建、评测与排查脚本
- `migrations/`：Alembic 数据库迁移
- `config/`：RAG、关键词等运行时配置 JSON
- `_archive/`、`backup/`：历史备份

## frontend/
- `package.json`：前端依赖与脚本
- `src/`
  - `main.tsx`、`App.tsx`：入口及路由
  - `config.ts`：运行时配置（API base 等）
  - `api/http.ts`：Axios 客户端封装
  - `pages/`：业务页面（如 `RAGAssistant.tsx`、`ProductionRecommendation.tsx`、`RAGASEvalV2.tsx`）
  - `components/`：复用组件
  - `styles.css`：全局样式

## docs/
- `ACRAC_V2_*.md`：历史方案、评测与使用手册
- `RAGAS_*.md`：RAG/RAGAS 相关计划与复盘
- `PRODUCTION_RECOMMENDATION_API.md`：生产推荐 API 与批量上传使用说明（2025 新增）
- `PROJECT_PROGRESS_REPORT.md`、`PROJECT_PROGRESS_LOG.md`：阶段性进展记录

## 其他目录
- `ACR_data/`、`data/`：原始与加工数据
- `standard/`：医疗标准与词表
- `api_detection_tool/`、`scripts/`：辅助工具与脚本（保留供排障）

> 提示：后端 `.env` 配置需要从 `backend/acrac.env.example` 复制，并更新密钥与数据库配置；前端默认通过同源代理访问 `/api`。
