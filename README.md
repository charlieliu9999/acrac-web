# ACRAC 医疗影像智能推荐系统

ACRAC (American College of Radiology Appropriateness Criteria) 是一个结合向量数据库与大语言模型（LLM）的医疗影像检查推荐平台。系统聚合了 13 个科室、285 个主题、1,391 个临床场景与 15,970 条推荐数据，通过 RAG（Retrieval-Augmented Generation）管线、规则引擎和评测工具，帮助放射科及医学决策人员快速定位最合适的检查方案。

## 核心功能
- **语义向量检索**：基于 pgvector 与 BGE-M3 向量模型，支持对科室、主题、临床场景、检查项目与推荐的综合搜索。
- **RAG+LLM 智能推荐**：`/api/v1/acrac/rag-llm/intelligent-recommendation` 将召回结果送入大模型推理，输出排序推荐、理由及 RAGAS 评测数据。
- **规则引擎管控**：可在前端开启/禁用规则、选择审计模式，并热加载规则包以确保推荐结果符合临床安全要求。
- **工具与监控面板**：提供向量检索调试、重排、LLM 解析、RAGAS 评分与向量库健康检查等能力，协助排查数据或模型问题。
- **前端管理台**：React 18 + Ant Design 实现的数据导入、模型配置、评测、工具箱与数据浏览页面，便于运维与评估。

## 技术架构
- **后端**：FastAPI + SQLAlchemy，PostgreSQL 15 + pgvector 持久化，Redis 作为缓存与 Celery 队列；集成 SiliconFlow 向量与 LLM 接口。
- **前端**：React 18、TypeScript、Vite，Ant Design 组件库；`frontend/src/pages` 下提供 RAG 助手、RAG 评测、规则管理、数据导入等模块。
- **容器与部署**：`docker-compose.yml` 编排 Postgres、Redis、后端、Celery Worker、前端与 Nginx；脚本 `start.sh`、`start-dev.sh` 提供一键化启动体验。

## 目录总览
```
ACRAC-web/
├── backend/                    # FastAPI 服务、脚本与测试
│   ├── app/                    # API、服务层、模型与配置
│   ├── scripts/                # 数据构建、评测与诊断脚本
│   ├── tests/                  # pytest 单元与集成测试套件
│   ├── migrations/ | alembic/  # 数据库迁移
│   └── acrac.env.example       # 环境变量示例
├── frontend/                   # React 管理台
│   ├── src/                    # Pages、API 客户端、配置等
│   └── package.json            # 前端依赖与命令
├── ACR_data/                   # 原始 ACR 数据集
├── docs/                       # 详细设计、部署与开发文档
├── deployment/                 # Docker、Nginx、Postgres 配置
├── start.sh | start-dev.sh     # 启动脚本（Docker / 本地开发）
└── AGENTS.md                   # 贡献者指南
```

## 环境要求
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ 与 pgvector 拓展（脚本默认使用 Docker 服务名 `postgres`）
- Redis 7+（默认使用 Docker 服务名 `redis`）
- Docker 与 Docker Compose（推荐，`start.sh` 会自动编排）
- SiliconFlow / OpenAI API Key（如需运行完整 RAG + LLM 流程）

## 快速开始
### 选择启动方式
根据你的场景选择其一：

1) 一键启动（Docker Compose，推荐部署/联调）
```bash
./start.sh
```
启动后访问：
- 后端 API 与文档：http://localhost:8001/docs
- 前端管理台：http://localhost:5173

启动脚本会自动选择 docker compose 命令（v1/v2 兼容），并做以下校验：
- 若本机 8001/5173 端口被本地 dev 进程占用，会提示改用 `./start-dev.sh` 或释放端口再运行。
- 健康检查确保容器完全就绪后再返回。

2) 本地开发模式（后端/前端热重载）
```bash
./start-dev.sh
```
脚本会仅拉起 Postgres 与 Redis 容器，并在宿主机本地启动后端（8001）与前端（5173）。
为了避免与 Docker 栈冲突，若发现后端容器在运行，脚本会提示先 `./stop.sh` 或改用 `./start.sh`。

> 提示：前端直连本地后端时，请在 `frontend/.env.development` 设置
> `VITE_API_BASE=http://localhost:8001/api/v1`，否则请求会落到 Vite 自身端口。

### 手动步骤（了解原理用）
1. 克隆仓库：
   ```bash
   git clone <repository-url>
   cd ACRAC-web
   ```
2. 配置环境：
   ```bash
   cp backend/acrac.env.example backend/.env
   # 填写 SiliconFlow / 数据库 / OpenAI 等密钥
   ```
3. 启动数据库与缓存：
   ```bash
   docker-compose up -d postgres redis
   ```
4. 初始化后端：
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
5. 构建向量数据库（首次必跑）：
   ```bash
   python scripts/build_acrac_from_csv_siliconflow.py build \
     --csv-file ../ACR_data/ACR_final.csv \
     --api-key $SILICONFLOW_API_KEY
   ```
6. 启动 FastAPI 服务（默认 8000）：
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
7. 启动前端：
   ```bash
   cd ../frontend
   npm install
   npm run dev  # Vite 默认 5173 端口
   ```
   自带 `start-dev.sh` 可一键拉起 Postgres、Redis、后端与前端热更新服务。

### 端口与访问
- Nginx（容器）：http://localhost:5173
- 前端（容器）：由 Nginx 转发到 `frontend:5173`（Dockerfile.dev 已监听 5173）
- 后端（容器）：http://localhost:8001
- 数据库：`postgres:5432`（容器内服务名），宿主映射 `localhost:5432`
- Redis：`redis:6379`（容器内服务名），宿主映射 `localhost:6379`

## API 速览
- `GET /api/v1/acrac/vector/v2/search/comprehensive`：多实体综合检索
- `POST /api/v1/acrac/rag-llm/intelligent-recommendation`：RAG+LLM 推荐与解释
- `GET /api/v1/acrac/rag-llm/rules-config`：查看规则引擎状态（支持 POST 更新）
- `POST /api/v1/acrac/tools/vector/search`：向量调试端点
- `POST /api/v1/acrac/tools/ragas/score`：RAGAS 单次评分
- `GET /api/v1/admin/data/validate`：向量库健康检查
更多端点详见 `docs/ACRAC_V2_API使用指南.md` 与 Swagger 文档。

## 前端管理台功能
- **RAG 助手**：UI 表单触发智能推荐，展示召回、重排、Prompt、规则审计与 RAGAS 评分结果。
- **RAG 评测**：批量评估推荐质量，生成报表。
- **规则管理**：切换规则启用/仅审计，并在线编辑规则包。
- **工具箱**：内置向量搜索调试、LLM 输出解析、RAGAS 评分、向量状态监控等调试工具。
- **数据导入与浏览**：支持上传 Excel/CSV、查看科室/主题/场景/推荐详情。
- **模型配置**：集中管理 SiliconFlow / Reranker / RAG 阈值等配置（读取 `frontend/config.ts` 与后端配置）。

## 测试与质量保障
- 单元与服务层测试：
  ```bash
  cd backend
  pytest tests/unit
  ```
- 端到端 API 回归：
  ```bash
  cd backend/tests
  python run_all_tests.py
  ```
  需确保 Postgres 与 API 服务已运行。脚本将生成 `test_execution.log` 与 `master_test_report_*.{json,html}`。
- 黑盒/数据完整性脚本位于 `backend/scripts`（如 `check_database.py`、`db_audit.py`）。
- 代码规范：执行 `black app scripts tests && flake8 app && mypy app`；前端在提交前至少运行 `npm run build` 确认通过。

## 部署指南
- `start.sh`：重建并启动 docker-compose 中的全部服务（包含 Celery Worker 与 Nginx）。
- `stop.sh`：停止所有容器。
- 生产部署可参考 `DEPLOYMENT_GUIDE.md` 与 `deployment/nginx/`、`deployment/postgres/` 下的样例配置，建议使用独立的 Compose Override 或 K8s。

## 数据与脚本
- 所有 ACR 数据来源于美国放射学会适宜性标准，已存放在 `ACR_data/`。
- 向量构建、补全与诊断脚本位于 `backend/scripts/`，可通过 `python -m` 方式调用。
- RAGAS 批量评测示例在 `backend/scripts/run_ragas_eval_from_excel.py` 与 `frontend/src/pages/RAGEvaluation.tsx`。

## 贡献指南
- 参考 `AGENTS.md` 获取最新版规范（目录结构、命令、代码风格、测试要求、提交/PR 模板等）。
- 工作流：从 `develop` 切出功能分支 → 编写/更新测试 → 遵循中文 Conventional Commit (`feat: ...`, `fix: ...`) → 发起合并请求并附上测试结果与截图。
- 数据库结构变更需同步提交 Alembic 迁移文件，前端 UI 变动请附带截图或录屏。

## 许可证与声明
- 许可证：MIT（详见 `LICENSE`）
- 本系统用于研究与教学，不应直接用于临床诊断决策。
- 若有问题或希望参与共建，请在仓库 Issues 中联系维护团队。
