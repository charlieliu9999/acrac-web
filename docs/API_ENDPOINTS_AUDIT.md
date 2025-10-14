# ACRAC 系统页面与 API 梳理（2025-10-02）

本文档完成以下内容：
- 页面功能与当前使用的 API 对照表
- 后端 API 服务清单（按模块归类）
- 可合并/重叠 API 分析与合并建议
- 存在问题与修复建议
- 建议的重整后 API 清单（目标形态）
- 清理计划（拟移除/下线的接口集合）

---

## 页面 × API 对照

- RAG 助手（`frontend/src/pages/RAGAssistant.tsx`）
  - 功能：输入临床查询，运行 RAG+LLM 推荐，支持（可选）触发 RAGAS 评估与上传运行日志
  - API：
    - POST `/api/v1/acrac/rag-llm/intelligent-recommendation`
    - POST `/api/v1/acrac/rag-llm/runs/log`
    - POST `/api/v1/ragas/evaluate`（异步任务）
    - GET `/api/v1/ragas/evaluate/{task_id}/status`
    - GET `/api/v1/ragas/evaluate/{task_id}/results`
    - DELETE `/api/v1/ragas/evaluate/{task_id}`

- 规则管理（`frontend/src/pages/RulesManager.tsx`）
  - 功能：查看/编辑规则包、热重载、规则试运行（rerank/post_llm）
  - API：
    - GET `/api/v1/acrac/rag-llm/rules-packs`
    - POST `/api/v1/acrac/rag-llm/rules-packs`
    - POST `/api/v1/acrac/rag-llm/rules-simulate`

- 数据浏览（`frontend/src/pages/DataBrowser.tsx`）
  - 功能：科室 → 主题 → 临床场景 → 推荐与理由 分层浏览
  - API（均来自 data_browse_api）：
    - GET `/api/v1/acrac/data/panels`
    - GET `/api/v1/acrac/data/topics/by-panel?panel_id=...`
    - GET `/api/v1/acrac/data/scenarios/by-topic?topic_id=...`
    - GET `/api/v1/acrac/data/recommendations?scenario_id=...&page=...&size=...`

- 工具箱（`frontend/src/pages/Tools.tsx`）
  - 功能：向量检索、重排、LLM 输出解析、RAGAS 单次评分、数据校验、模型库/配置、CSV 导入
  - API：
    - POST `/api/v1/acrac/tools/vector/search`
    - POST `/api/v1/acrac/tools/rerank`
    - POST `/api/v1/acrac/tools/llm/parse`
    - POST `/api/v1/acrac/tools/ragas/score`
    - GET  `/api/v1/acrac/tools/ragas/schema`
    - GET  `/api/v1/admin/data/validate`
    - GET  `/api/v1/admin/data/models/registry`
    - GET  `/api/v1/admin/data/models/config`
    - POST `/api/v1/admin/data/models/check-model`
    - POST `/api/v1/admin/data/upload`
    - POST `/api/v1/admin/data/import`

- 数据导入（`frontend/src/pages/DataImport.tsx`）
  - 功能：上传 CSV、执行导入/重建、校验与指标、模型库/上下文读取
  - API：
    - POST `/api/v1/admin/data/upload`
    - POST `/api/v1/admin/data/import`
    - GET  `/api/v1/admin/data/models/registry`
    - GET  `/api/v1/admin/data/models/config`
    - POST `/api/v1/admin/data/models/check-model`
    - GET  `/api/v1/admin/data/validate`

- 模型配置（`frontend/src/pages/ModelConfig.tsx`）
  - 功能：读取/保存模型与上下文配置、重载服务、连通性检查、系统状态、（前端存在“提供商连接测试”按钮）
  - API：
    - GET  `/api/v1/admin/data/models/config`
    - POST `/api/v1/admin/data/models/config`
    - POST `/api/v1/admin/data/models/reload`
    - GET  `/api/v1/admin/data/models/registry`
    - GET  `/api/v1/admin/data/models/check`（连通性体检）
    - GET  `/api/v1/admin/data/system/status`
    - 缺失（前端调用但后端无接口）：POST `/api/v1/admin/data/models/test-provider`

- 运行历史（`frontend/src/pages/RunLogs.tsx`）
  - 功能：查看 RAG 推理运行记录，查看详情，批量删除
  - API：
    - GET    `/api/v1/acrac/rag-llm/runs?{page,page_size,status,start,end}`
    - GET    `/api/v1/acrac/rag-llm/runs/{id}`
    - DELETE `/api/v1/acrac/rag-llm/runs`（body: { ids: number[] }）

- RAGAS 评测面板（`frontend/src/pages/RAGASEvalV2.tsx`）
  - 功能：
    1) 阶段一：批量调用推荐并保存运行记录
    2) 阶段二：离线 RAGAS 评测（同步/异步两种实现）
  - API：
    - 阶段一：
      - POST `/api/v1/acrac/excel-evaluation/upload-excel`
      - POST `/api/v1/acrac/rag-llm/intelligent-recommendation`
      - POST `/api/v1/acrac/rag-llm/runs/log`
      - GET  `/api/v1/acrac/rag-llm/runs`、GET `/api/v1/acrac/rag-llm/runs/{id}`
    - 阶段二（两套）：
      - 同步：POST `/api/v1/ragas-standalone/evaluate`
      - 离线：POST `/api/v1/ragas/offline-evaluate`
      - 历史：GET `/api/v1/ragas/history`、GET `/api/v1/ragas/history/{task_id}`

- 其他页面
  - `ModelConfigNew.tsx`, `ModelConfigOptimized.tsx` 文件存在但为空，未被路由使用

---

## 后端 API 清单（按模块/前缀）

- `/api/v1/acrac/data`（`data_browse_api.py`）
  - GET `/panels`，`/topics/by-panel`，`/scenarios/by-topic`
  - GET `/scenarios`（分页检索），`/procedures`，`/recommendations`

- `/api/v1/admin/data`（`admin_data_api.py`）
  - 健康与校验：GET `/system/status`，GET `/validate`
  - 导入：POST `/upload`，POST `/import`
  - 模型配置：
    - GET `/models/config`，POST `/models/config`，POST `/models/reload`
    - GET `/models/check`（连通性体检）
    - GET `/models/registry`，POST `/models/registry`，POST `/models/registry/{kind}`，DELETE `/models/registry/{kind}/{entry_id}`
    - POST `/models/check-model`

- `/api/v1/acrac/tools`（`tools_api.py`）
  - POST `/vector/search`，POST `/rerank`，POST `/llm/parse`
  - POST `/ragas/score`，GET `/ragas/schema`

- `/api/v1/acrac/rag-llm`（`rag_llm_api.py`）
  - 推荐：POST `/intelligent-recommendation`，GET `/intelligent-recommendation-simple`
  - 规则：GET/POST `/rules-config`，GET `/rules-packs`，POST `/rules-packs`，POST `/rules-simulate`
  - 运行记录：POST `/runs/log`，GET `/runs`，GET `/runs/{id}`，DELETE `/runs`
  - 状态：GET `/rag-llm-status`

- `/api/v1/acrac/rag-services`（`rag_services_api.py`）
  - 组件化服务：POST `/embeddings`，`/search-scenarios-by-text`，`/search-scenarios-by-vector`，`/scenario-recommendations`，`/procedure-candidates`，`/rerank`，`/prompt`，`/llm`，`/parse`，`/ragas`，`/pipeline/recommend`

- `/api/v1/ragas`（`ragas_api.py`）
  - 数据：POST `/data/upload`，POST `/data/preprocess`
  - 评估：POST `/evaluate`（异步任务流）、GET `/evaluate/{task_id}/status`，GET `/evaluate/{task_id}/results`，DELETE `/evaluate/{task_id}`
  - 历史：GET `/history`，GET `/history/statistics`，GET `/history/{task_id}`，DELETE `/history/{task_id}`
  - 其他：POST `/offline-evaluate`，POST `/admin/clear-all`

- `/api/v1/ragas-standalone`（`ragas_standalone_api.py`）
  - POST `/evaluate`（同步评测），GET `/health`

- 其他模块（当前前端未使用或使用较少）
  - `/api/v1/acrac`（`acrac_simple.py`）：健康/统计/基础数据/分析类多端点（与 data_browse 功能重叠）
  - `/api/v1/acrac/vector/v2`（`vector_search_api_v2.py`）：全量/分实体向量检索 + 统计
  - `/api/v1/acrac/intelligent`（`intelligent_analysis.py`）：智能临床分析（服务层已被 RAG+LLM 替代）
  - `/api/v1/acrac/methods`（`three_methods_api.py`）：三种方法对比（向量/LLM/RAG）
  - `/api/v1/evaluation`（`evaluation_project_api.py`, `inference_evaluation_api.py`）：评测项目与推理记录到 RAGAS 的转换接口

---

## 可合并/重叠 API 与建议

- 向量检索/重排/解析/RAGAS（重叠）：
  - `tools_api.py` 与 `rag_services_api.py` 提供了高度重叠的能力（`/vector/search`、`/rerank`、`/llm/parse`/`/parse`、RAGAS 评分）。
  - 建议：统一保留 `rag_services_api.py` 作为“组件化 RAG 服务”，逐步将前端 Tools 页迁移到 `/acrac/rag-services/*`，`tools_api.py` 标记为 deprecated 后在一段稳定期后移除。

- 基础数据浏览（重叠）：
  - `acrac_simple.py` 与 `data_browse_api.py` 提供的列表/浏览能力重叠，且实现风格不同（ORM vs. SQL）。
  - 建议：保留 `data_browse_api.py`（当前前端在用），将 `acrac_simple.py` 标记为 deprecated，评估是否还有外部依赖后移除。

- 检索服务接口（重叠）：
  - `vector_search_api_v2.py` 与 `rag_services_api.py`/`tools_api.py` 的检索能力存在交叉。
  - 建议：若无外部依赖，统一到 `rag_services_api.py`，将 `vector_search_api_v2.py` 的优势能力（分实体检索/综合响应）在 `rag_services_api.py` 增设路由后下线 v2 文件。

- RAGAS 评测（重叠）：
  - `ragas_api.py`（异步任务/历史）与 `ragas_standalone_api.py`（同步）并存，且 Tools 页也有“单次得分”接口。
  - 建议：
    - 统一前缀 `/api/v1/ragas`，保留：`/evaluate`（同步/异步通过参数控制）、`/history`、`/offline-evaluate`；
    - 将 `ragas_standalone_api.py` 能力迁回 `ragas_api.py`，对外维持兼容 alias 一段时间。

- 推荐 API（旧）与新 RAG+LLM：
  - `intelligent_analysis.py`、`three_methods_api.py` 与 `rag_llm_api.py` 存在定位重叠。
  - 建议：统一使用 `rag_llm_api.py`，其余置为 deprecated，若无依赖则清理。

---

## 发现的问题（需修复）

- 前端调用但后端缺失：
  - POST `/api/v1/admin/data/models/test-provider`（`frontend/src/pages/ModelConfig.tsx:116` 附近）
  - 建议：在 `admin_data_api.py` 增加该路由，实现对不同 Provider 的连通性探测（可复用现有 `/models/check` 的逻辑）。

- 冗余接口较多：
  - `acrac_simple.py`、`intelligent_analysis.py`、`three_methods_api.py`、`vector_search_api_v2.py`、`ragas_evaluation_api.py`、`evaluation_project_api.py`、`inference_evaluation_api.py` 等与当前 UI 无直接耦合。
  - 建议：分批下线（见下文清理计划）。

- 安全性（提醒）：
  - Admin 端口多数未加鉴权；批量删除、导入、写配置等接口建议加鉴权/审计（不属本次任务范围，留作后续）。

---

## 建议的重整后 API 清单（目标形态）

- 浏览/数据：`/api/v1/acrac/data/*`（保留）
- RAG 推荐（端到端）：`/api/v1/acrac/rag-llm/*`（保留）
- RAG 组件服务（统一）：`/api/v1/acrac/rag-services/*`
  - 搜索、候选、重排、Prompt、LLM、解析、RAGAS、小流水线
  - 前端 Tools 迁移到本组路由，`tools_api.py` 废弃
- Admin：`/api/v1/admin/data/*`（保留 + 补齐 test-provider）
- RAGAS：`/api/v1/ragas/*`（统一同步/异步评测 + 历史 + 离线评测）
- 计划移除：`acrac_simple`、`intelligent_analysis`、`three_methods_api`、`vector_search_api_v2`、`ragas_evaluation_api`、`evaluation_project_api`、`inference_evaluation_api`（见清理计划）

---

## 清理计划（拟移除/下线项）

分两阶段进行，避免回归风险：

1) 标记为 Deprecated，停止前端/脚本引用：
   - `backend/app/api/api_v1/endpoints/acrac_simple.py`
   - `.../intelligent_analysis.py`
   - `.../three_methods_api.py`
   - `.../vector_search_api_v2.py`
   - `.../ragas_evaluation_api.py`（目前路由已注释）
   - `.../evaluation_project_api.py`
   - `.../inference_evaluation_api.py`

2) 观察 1-2 个迭代后移除：
   - 从 `api.py` 移除对应 `include_router`
   - 删除对应端点文件与无用的 service 代码
   - 更新文档与 API 列表，跑一次 CI/集成测试

下线前检查项：
- `rg` 全仓搜索引用，确认无前端/脚本/测试依赖
- 若保留能力，先在 `rag_services_api.py` 增设等价路由并迁移逻辑

---

## 变更建议与下一步

- 优先修复缺失接口：实现 POST `/api/v1/admin/data/models/test-provider`
- 确认合并方向：前端 Tools 迁移到 `/acrac/rag-services/*`
- 确认下线节奏：先从 `acrac_simple.py`、`three_methods_api.py`、`intelligent_analysis.py` 开始
- 维护统一的 API 文档（本文件 + `/docs` 自动化生成可作为后续目标）

附：如需，我可以提交一个小补丁为 `admin_data_api.py` 增加 `test-provider` 端点，并在文档中标记 deprecated 路由，随后按上述计划批量清理。

