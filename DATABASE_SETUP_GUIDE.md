## ACRAC 开发数据库统一配置指南（方案A）

目标：统一使用 Docker 容器中的 PostgreSQL 作为唯一开发数据库；无论本机直跑还是容器内运行，都连接同一实例，杜绝 “localhost:5432 failed” 之类冲突。

---

### 一、核心理念
- 只保留一份开发数据库：Docker Compose 启动的 `postgres` 容器（端口 5432 暴露到宿主机）
- 连接方式：
  - 容器内（backend、celery）：`host=postgres`（Docker 服务名）
  - 宿主机进程（脚本/本地后端）：`host=127.0.0.1`（映射端口）
- 环境分离但指向同一个数据库：
  - `backend/.env.docker`（容器用）
  - `backend/.env.dev`（宿主机直连用）

> 说明：Pydantic Settings 会读取进程环境变量；`docker-compose` 通过 `env_file` 注入容器环境，宿主机脚本通过 `source backend/.env.dev` 注入环境；两者都优先于代码里的默认值。

---

### 二、环境文件

`backend/.env.docker`（容器内运行）：
```
PGHOST=postgres
PGPORT=5432
PGDATABASE=acrac_db
PGUSER=postgres
PGPASSWORD=password
DATABASE_URL=postgresql://postgres:password@postgres:5432/acrac_db
REDIS_URL=redis://redis:6379/0
RAG_API_URL=http://backend:8000/api/v1/acrac/rag-llm/intelligent-recommendation
SILICONFLOW_API_KEY=
SILICONFLOW_EMBEDDING_MODEL=BAAI/bge-m3
SILICONFLOW_LLM_MODEL=Qwen/Qwen2.5-32B-Instruct
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
```

`backend/.env.dev`（宿主机直跑）：
```
PGHOST=127.0.0.1
PGPORT=5432
PGDATABASE=acrac_db
PGUSER=postgres
PGPASSWORD=password
DATABASE_URL=postgresql://postgres:password@127.0.0.1:5432/acrac_db
REDIS_URL=redis://127.0.0.1:6379/0
RAG_API_URL=http://127.0.0.1:8001/api/v1/acrac/rag-llm/intelligent-recommendation
SILICONFLOW_API_KEY=
SILICONFLOW_EMBEDDING_MODEL=BAAI/bge-m3
SILICONFLOW_LLM_MODEL=Qwen/Qwen2.5-32B-Instruct
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
CELERY_BROKER_URL=redis://127.0.0.1:6379/1
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/2
```

---

### 三、docker-compose 配置
- `backend` 与 `celery_worker` 使用 `env_file: backend/.env.docker`
- PostgreSQL 对宿主机暴露 5432 端口（宿主机脚本可 127.0.0.1:5432 访问）

验证：
```
docker compose up -d postgres redis backend celery_worker
curl -s http://127.0.0.1:8001/api/v1/acrac/health
curl -s http://127.0.0.1:8001/api/v1/admin/data/validate
```

---

### 四、本机直跑后端（可选）
- 目的：在不进入容器的情况下，使用本机 Python/venv 运行 FastAPI，但仍连接 Docker 的 PostgreSQL
- 步骤：
```
# 1) 启动数据库与依赖（单次）
docker compose up -d postgres redis

# 2) 激活虚拟环境并加载 .env.dev
cd backend
source venv/bin/activate
set -a; source .env.dev; set +a

# 3) 启动后端
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```
> 注意：此时 RAG_API_URL、DATABASE_URL 等都来自 `.env.dev`，指向同一个 Docker PostgreSQL。

---

### 五、前端
- 开发模式（Vite）：
```
cd frontend
npm install  # 首次
npm run dev  # http://localhost:5173
```
- 后端 API Base：`frontend/.env` 中配置 `VITE_API_BASE=http://127.0.0.1:8001/api/v1`

---

### 六、常见问题与排查
1) “connection to server at localhost:5432 failed”
- 原因：容器内代码使用 `PGHOST=localhost`（指向容器自身）
- 解决：容器内一律使用 `PGHOST=postgres` 或 `DATABASE_URL` 中 host=postgres

2) “向量状态监控/数据浏览接口失败”
- 调用 `/api/v1/admin/data/validate` 或 `/api/v1/acrac/data/*` 时，后端直接用 psycopg2/sqlalchemy 访问 DB；确保使用了正确 env（容器=`.env.docker`，宿主=`.env.dev`）

3) “容器改了配置不生效”
- 需要 `docker compose up -d backend celery_worker` 或重启容器，让新的 `env_file` 注入

4) “本机直跑后端时连接失败”
- 检查是否已 `set -a; source backend/.env.dev; set +a`
- 检查 Docker 的 `postgres` 容器是否已启动并暴露 5432

---

### 七、快速验证清单
- 容器健康：
```
docker compose ps
curl -s http://127.0.0.1:8001/api/v1/acrac/health
```
- 向量状态：
```
curl -s http://127.0.0.1:8001/api/v1/admin/data/validate
```
- RAG-LLM 推理：
```
curl -s -X POST http://127.0.0.1:8001/api/v1/acrac/rag-llm/intelligent-recommendation \
  -H 'Content-Type: application/json' \
  -d '{"clinical_query":"头痛伴视物模糊","top_scenarios":2,"top_recommendations_per_scenario":2}'
```
- RAGAS（异步）：
```
curl -s -X POST http://127.0.0.1:8001/api/v1/ragas/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"test_cases":[{"question_id":"1","clinical_query":"胸痛3小时","ground_truth":"CT冠状动脉造影"}],"model_name":"gpt-3.5-turbo","base_url":"https://api.siliconflow.cn/v1","async_mode":true}'
```

---

### 八、结论
- 通过 `.env.docker` 与 `.env.dev` 的分离配置，统一连接 Docker PostgreSQL 作为唯一开发数据库
- 容器内使用服务名 `postgres`，宿主机使用 `127.0.0.1`
- 消除了本地与容器之间的 DB 配置冲突，团队可复现且一致

