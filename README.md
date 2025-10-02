# ACRAC 医疗影像智能推荐系统

## 项目简介

ACRAC (American College of Radiology Appropriateness Criteria) 是一个基于向量数据库的医疗影像智能推荐系统，能够根据患者症状、病史和临床特征，智能推荐最适合的影像检查项目。

## 核心特性

- 🧠 **智能向量检索**: 使用SiliconFlow BGE-M3模型进行医学语义理解
- 🏥 **临床场景匹配**: 支持15,970+临床推荐场景的智能匹配
- 🔍 **多模态支持**: 支持CT、MRI、DR、RF、MG等多种检查方式
- ⚡ **实时推荐**: 毫秒级响应速度的智能推荐
- 📊 **数据完整性**: 包含13个科室、285个主题、1,391个临床场景

## 技术架构

### 后端技术栈
- **框架**: FastAPI + SQLAlchemy
- **数据库**: PostgreSQL + pgvector
- **向量模型**: SiliconFlow BGE-M3 (1024维)
- **容器化**: Docker + Docker Compose

> 模块化RAG服务说明：见 docs/RAG_MODULAR_SERVICE.md（向量、召回、重排、提示词、LLM、解析、RAGAS 等可独立服务化的端点与部署方案）。

## 运行配置与优先级

为避免“硬编码/虚假兜底”，系统采用明确的配置优先级与显式失败策略：

- 优先级（高→低）：请求级参数 > 模型上下文（config/model_contexts.json + scenario_overrides）> 环境变量（.env/.env.docker）> 代码默认值。
- 失败策略：当 LLM 无法调用或输出无效 JSON 时，接口返回 `success=false` 与错误信息；不会生成“伪造”的推荐结果。

### 关键环境变量（默认值）

- 向量/数据库：`PG*`、`DATABASE_URL`、`REDIS_URL`
- 模型默认：`SILICONFLOW_BASE_URL`、`SILICONFLOW_LLM_MODEL`、`SILICONFLOW_EMBEDDING_MODEL`（可被上下文覆盖）
- 秘钥：`SILICONFLOW_API_KEY` 或 `OPENAI_API_KEY`（仅放在环境，不进入配置文件）
- RAG 行为：
  - `STRICT_EMBEDDING`（生产建议 true；false 仅用于离线/CI 调试）
  - `RAG_USE_RERANKER`（是否启用重排）与 `RERANK_PROVIDER`（auto/local/siliconflow）
  - `RAG_SCENARIO_RECALL_TOPK`（召回 TopK，用于语义检索，不等于展示数量）
- LLM 控制：`LLM_FORCE_JSON`、`LLM_MAX_TOKENS`（可被上下文或请求覆盖）
- RAGAS 评测：`RAG_API_URL` 默认指向新管线 `/acrac/rag-services/pipeline/recommend`

### 模型上下文（热更新）

- 位置：`config/model_contexts.json`
- 用途：全局/场景级覆盖推理/评测模型、`max_tokens`、`temperature`、`top_p`、禁用思维链等；支持 `scenario_overrides`。
- 修改后无需重启，服务会按 mtime 自动热加载。

### 请求级参数（页面即时控制）

- 入口：`POST /api/v1/acrac/rag-services/pipeline/recommend`
- 常用字段：
  - `top_scenarios`（展示的场景数）
  - `top_recommendations_per_scenario`（每场景带入候选数）
  - `show_reasoning`（是否显示理由）
  - `similarity_threshold`（相似度阈值）
  - `compute_ragas`、`ground_truth`
  - `llm_options`（新增）：可传入 `max_tokens`、`temperature`、`top_p`、`disable_thinking`、`no_thinking_tag` 等临时覆盖，仅对本次请求生效。

## 规则引擎（Rules Engine）

- 默认配置文件：`config/rules_packs.json`（可通过 `RULES_CONFIG_PATH` 覆盖）
- 启用/审计开关：
  - `POST /api/v1/acrac/rag-llm/rules-config` `{enabled, audit_only}`
  - 审计日志随响应返回于 `debug_info.rules_audit.rerank/post`
- 执行点：
  - 重排后（rerank）：支持 boost/filter 等；审计写入 `rules_audit.rerank`
  - 解析后（post）：支持 warn/fix/override；审计写入 `rules_audit.post`

## RAGAS 评测

- 使用内嵌评测（pipeline 中 `compute_ragas=true`）时：
  - 有 `ground_truth`：返回 4 项（faithfulness、answer_relevancy、context_precision、context_recall）
  - 无 `ground_truth`：仅返回与参考答案无关的 2 项（faithfulness、answer_relevancy）
  - 评测结果位于 `result.ragas_scores`（顶层）与 `trace.ragas_scores`（兼容旧 UI）
  - 失败原因见 `result.ragas_error`（或 `trace.ragas_error`）

## 端点（核心）

- 新管线：`POST /api/v1/acrac/rag-services/pipeline/recommend`
  - 支持 `llm_options` 自定义每次请求的 `max_tokens` 等参数
  - 调试输出（`debug_mode=true`）包含：
    - `trace.recall_scenarios`（召回详情）
    - `trace.rerank_scenarios`（重排详情）
    - `trace.llm_raw` / `trace.llm_parsed`（原文与解析）

## 严格失败与无“造假兜底”

- 当 LLM 调用失败或输出无效 JSON 时：
  - 服务返回 `success=false` 与明确 `message`，不生成伪造推荐
  - 解析器仅用于键名与格式修正，不将失败结果伪装为“成功推荐”
  - 在开发/离线场景中可设 `STRICT_EMBEDDING=false` 便于联调，但生产需设为 true


### 前端技术栈
- **框架**: React 18 + TypeScript
- **构建工具**: Vite
- **UI组件**: Ant Design + 自定义组件

## 项目结构

```
ACRAC-web/
├── backend/                    # 后端服务
│   ├── app/                   # 应用核心代码
│   │   ├── api/              # API路由
│   │   ├── core/             # 核心配置
│   │   ├── models/           # 数据模型
│   │   ├── schemas/          # 数据模式
│   │   └── services/         # 业务逻辑
│   ├── scripts/              # 数据库构建脚本
│   │   ├── build_acrac_from_csv_siliconflow.py  # 主构建脚本
│   │   ├── test_clinical_scenarios.py          # 临床场景测试
│   │   └── test_vector_search_simple.py        # 向量搜索测试
│   ├── requirements.txt      # Python依赖
│   └── .env                 # 环境配置
├── frontend/                  # 前端应用
│   ├── src/                  # 源代码
│   │   ├── pages/           # React页面组件
│   │   ├── api/             # API客户端
│   │   └── App.tsx          # 主应用组件
│   └── package.json         # 前端依赖
├── ACR_data/                 # 原始数据
├── docs/                     # 项目文档
├── deployment/               # 部署配置
└── backup/                   # 备份文件
```

## 快速开始

### 环境要求
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ with pgvector
- Docker & Docker Compose

### 1. 克隆项目
```bash
git clone <repository-url>
cd ACRAC-web
```

### 2. 配置环境
```bash
# 复制环境配置文件
cp backend/acrac.env.example backend/.env

# 编辑配置文件，设置SiliconFlow API密钥
vim backend/.env
```

### 3. 启动数据库
```bash
docker-compose up -d postgres
```

### 4. 构建数据库
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 构建向量数据库
python scripts/build_acrac_from_csv_siliconflow.py build --csv-file ../ACR_data/ACR_final.csv
```

### 5. 启动后端服务
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. 启动前端服务
```bash
cd frontend
npm install
npm run dev
```

## API 使用

### 向量搜索API
```bash
# 搜索相关临床场景
curl -X POST "http://localhost:8000/api/v1/vector-search/scenarios" \
  -H "Content-Type: application/json" \
  -d '{"query": "45岁女性，慢性反复头痛3年", "limit": 5}'

# 搜索推荐检查项目
curl -X POST "http://localhost:8000/api/v1/vector-search/recommendations" \
  -H "Content-Type: application/json" \
  -d '{"query": "突发剧烈头痛", "limit": 3}'
```

### 数据统计API
```bash
# 获取数据库统计信息
curl "http://localhost:8000/api/v1/stats/overview"

# 获取向量覆盖率
curl "http://localhost:8000/api/v1/stats/vector-coverage"
```

## 测试

### 运行向量检索测试
```bash
cd backend
python scripts/test_vector_search_simple.py
```

### 运行临床场景测试
```bash
cd backend
python scripts/test_clinical_scenarios.py
```

## 数据说明

### 数据来源
- **ACR数据**: 基于美国放射学会适宜性标准
- **向量模型**: SiliconFlow BGE-M3 (1024维)
- **数据规模**: 15,970+临床推荐记录

### 数据表结构
- `panels`: 科室信息 (13条)
- `topics`: 医学主题 (285条)
- `clinical_scenarios`: 临床场景 (1,391条)
- `procedure_dictionary`: 检查项目 (1,053条)
- `clinical_recommendations`: 临床推荐 (15,970条)

## 部署

### Docker部署
```bash
# 构建并启动所有服务
docker-compose up --build

# 仅启动数据库
docker-compose up -d postgres
```

### 生产环境
```bash
# 构建生产镜像
docker build -t acrac-backend ./backend
docker build -t acrac-frontend ./frontend

# 使用docker-compose.prod.yml
docker-compose -f docker-compose.prod.yml up -d
```

## 开发指南

### 添加新的临床场景
1. 在`ACR_data/`目录添加新的CSV数据
2. 运行构建脚本更新数据库
3. 测试向量检索效果

### 自定义向量模型
1. 修改`SiliconFlowEmbedder`类
2. 更新`requirements.txt`
3. 重新构建数据库

### API扩展
1. 在`app/api/`目录添加新的路由
2. 在`app/services/`实现业务逻辑
3. 更新API文档

## 性能优化

### 向量搜索优化
- 使用IVFFLAT索引提升搜索速度
- 批量处理减少API调用次数
- 缓存常用查询结果

### 数据库优化
- 定期执行VACUUM和ANALYZE
- 监控查询性能
- 调整PostgreSQL参数

## 故障排除

### 常见问题
1. **向量生成失败**: 检查SiliconFlow API密钥
2. **数据库连接失败**: 确认PostgreSQL服务状态
3. **搜索精度低**: 检查向量模型和数据质量

### 日志查看
```bash
# 查看后端日志
tail -f backend/logs/app.log

# 查看数据库日志
docker-compose logs postgres
```

## 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 创建Pull Request

## 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 联系方式

- 项目维护者: [Your Name]
- 邮箱: [your.email@example.com]
- 项目地址: [GitHub Repository URL]

---

**注意**: 本系统仅供医疗研究和教育用途，不应用于实际临床诊断决策。
