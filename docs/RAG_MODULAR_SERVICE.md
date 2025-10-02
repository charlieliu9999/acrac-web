# RAG 模块化服务体系说明

本文档介绍 ACRAC 的 RAG+LLM 智能推荐核心能力的模块化重构方案，包括模块划分、API 设计、部署方式以及可观测性与评测支持。

## 目标

- 将原 `RAGLLMRecommendationService` 超过 2000 行的实现解构为不超过 500 行的独立小模块；
- 保持原有 API 输出/接口兼容（`/acrac/rag-llm/*` 不变）；
- 提供面向多 API Server 的“可独立服务化”的细粒度端点：向量、召回、重排、提示词、LLM、解析、评测；
- 复用配置与上下文管理，支持场景级覆盖与热更新；
- 为后续扩容与伸缩提供清晰的边界。

## 模块与职责

- `app/services/rag/embeddings.py`
  - `embed_with_siliconflow(text, api_key, model, base_url)`：OpenAI 兼容 Embedding 客户端，支持 SiliconFlow/OpenAI/OpenRouter/Ollama。

- `app/services/rag/db.py`
  - 连接池与回退；
  - `search_clinical_scenarios(conn, vector, top_k)` 临床场景向量召回；
  - `get_scenario_with_recommendations(conn, scenario_ids)` 场景级推荐明细；
  - `search_procedure_candidates(conn, vector, top_k)` 候选检查检索。

- `app/services/rag/prompts.py`
  - `prepare_llm_prompt(...)` 构建 RAG/非 RAG 两种提示词。

- `app/services/rag/llm_client.py`
  - `call_llm(prompt, context, force_json=True, ...)` OpenAI 兼容 ChatCompletion；
  - 强制 JSON 输出、禁思维链（可选 stop 标记）、Ollama 兼容、失败降级固定 JSON。

- `app/services/rag/parser.py`
  - `parse_llm_response(text)`：去除代码块、宽松 JSON 纠正、Pydantic 归一化。

- `app/services/rag/reranker.py`
  - `rerank_scenarios(query, scenarios, ...)`：SiliconFlow / 本地 cross-encoder / 关键词 & 评分加权回退。

- `app/services/rag/contexts.py`
  - `Contexts`：从 `config/model_contexts.json` 加载推理/评测上下文，支持场景/主题/科室覆盖与 mtime 热更新；
  - `extract_scope_info(scenarios)`：从召回集提取 scope。

- `app/services/rag/ragas_eval.py`
  - `build_contexts_from_payload(payload)`、`format_answer_for_ragas(parsed)`；
  - `compute_ragas_scores(...)`：进程内评测，自动回退子进程隔离，避免 uvloop 冲突。

- `app/services/rag/pipeline.py`
  - `generate_recommendation(query, deps, ...)`：面向依赖注入的编排器（向量→召回→重排→候选→提示词→LLM→解析→可选 RAGAS）。

- `app/services/rag/facade.py`
  - `RAGLLMRecommendationService` 门面：聚合以上模块，保留原类与方法名，暴露嵌入缓存、上下文解析、数据库访问等。

## API 兼容性

- 原路由 `backend/app/api/api_v1/endpoints/rag_llm_api.py` 保持不变；
- 通过在 `rag_llm_recommendation_service.py` 中安全重绑定，将原类名与全局实例指向门面实现：
  - `RAGLLMRecommendationService`（类名不变）
  - `rag_llm_service`（实例不变）

## 新增模块化 API（多服务可复用）

挂载前缀：`/api/v1/acrac/rag-services`

- `POST /embeddings` → 生成文本向量
  - 入参：`{ text, model?, base_url? }`
  - 出参：`{ vector, dim }`

- `POST /search-scenarios-by-text` → 文本召回场景
  - 入参：`{ query, top_k? }`
  - 出参：场景列表（含 `semantic_id`, `description_zh`, `panel/topic`, `similarity`）

- `POST /search-scenarios-by-vector` → 向量召回场景
  - 入参：`{ vector, top_k? }`
  - 出参：场景列表

- `POST /scenario-recommendations` → 场景推荐明细
  - 入参：`{ scenario_ids: [..] }`
  - 出参：按场景聚合的推荐项（含评分/理由等）

- `POST /procedure-candidates` → 候选检查检索
  - 入参：`{ query? | vector?, top_k? }`
  - 出参：候选检查（`name_zh/modality/similarity`）

- `POST /rerank` → 场景重排
  - 入参：`{ query, scenarios, scenarios_with_recs?, provider? }`
  - 出参：带 `_rerank_score` 的场景列表

- `POST /prompt` → 构建提示词
  - 入参：`{ query, scenarios, scenarios_with_recs, is_low_similarity?, top_scenarios?, top_recs_per_scenario?, show_reasoning?, candidates? }`
  - 出参：`{ prompt, length }`

- `POST /llm` → LLM 推理
  - 入参：`{ prompt, context? }`（支持 `llm_model/base_url/max_tokens/disable_thinking` 等）
  - 出参：`{ content }`（原始模型输出）

- `POST /parse` → 解析 LLM 输出
  - 入参：`{ llm_response }`
  - 出参：`{ recommendations: [...], summary, no_rag?, rag_note? }`

- `POST /ragas` → 计算 RAGAS 指标
  - 入参：`{ user_input, answer, contexts, reference? }`
  - 出参：`{ faithfulness, answer_relevancy, context_precision, context_recall }`

- `POST /pipeline/recommend` → 完整推荐流程（便捷）
  - 与旧 `/acrac/rag-llm/intelligent-recommendation` 等价，便于管线式调用。

示例：

```bash
curl -X POST http://localhost:8000/api/v1/acrac/rag-services/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"text":"突发剧烈头痛"}'

curl -X POST http://localhost:8000/api/v1/acrac/rag-services/search-scenarios-by-text \
  -H 'Content-Type: application/json' \
  -d '{"query":"45岁女性，突发剧烈头痛", "top_k":3}'

curl -X POST http://localhost:8000/api/v1/acrac/rag-services/rerank \
  -H 'Content-Type: application/json' \
  -d '{"query":"突发剧烈头痛","scenarios":[...],"provider":"auto"}'
```

## 多 API Server 部署建议

根据吞吐与成本，可将以下能力拆分为独立服务：

- 向量服务（/embeddings）— 可复用于数据入库/批处理；
- 召回 + 候选（/search-scenarios*, /procedure-candidates）— 与数据库同机部署减少 RTT；
- 重排服务（/rerank）— 可启用本地 cross-encoder 或远端 SF rerank；
- 提示词与 LLM（/prompt, /llm, /parse）— 可单独横向扩缩容；
- 评测服务（/ragas）— 离线评测或按需调用，独立伸缩；
- 编排（/pipeline/recommend）— 组合以上服务，也可内嵌在调用端。

路由层可通过网关（如 Nginx/Traefik）做路径转发；各服务共享配置与鉴权策略。

## 配置与环境变量

- 通用：
  - `SILICONFLOW_API_KEY`、`SILICONFLOW_BASE_URL`
  - `OPENAI_API_KEY`（可选兼容）、`OLLAMA_BASE_URL`（本地推理）
  - `RAG_TOP_SCENARIOS`、`RAG_TOP_RECOMMENDATIONS_PER_SCENARIO`、`RAG_SHOW_REASONING`
  - `RAG_SIMILARITY_THRESHOLD`、`RAG_USE_RERANKER`、`RERANK_PROVIDER`
  - `LLM_FORCE_JSON`、`LLM_MAX_TOKENS`、`LLM_SEED`
  - `PGHOST`、`PGPORT`、`PGDATABASE`、`PGUSER`、`PGPASSWORD`、`PGVECTOR_PROBES`

- 模型上下文：`config/model_contexts.json` 支持：
  - `contexts.inference` / `contexts.evaluation` 默认模型与推理参数；
  - `scenario_overrides` 按 `panel/topic/scenario/custom` 维度覆盖（同名字段覆盖）。

## 可观测性与排错

- 通过 `/acrac/rag-llm/rag-llm-status` 检查服务健康；
- 使用 `debug_mode=true` 获取完整 trace（召回、重排、prompt、LLM原始输出、RAGAS上下文与得分）；
- RAGAS 进程内失败（如 uvloop 冲突）自动回退子进程隔离，日志中可见原因。

## 迁移与兼容

- 原 `RAGLLMRecommendationService` 的导入与实例均可继续使用：
  - `from app.services.rag_llm_recommendation_service import rag_llm_service`
  - 内部已重定向到模块化门面实现；
- 原有单元测试（例如 `tests/unit/test_llm_parser.py`）保持可用。

## 版本化与后续工作

- 将 `rag_services_api.py` 拆分为更细的子路由（如 embeddings_api, recall_api 等），以适配更细粒度的部署；
- 增加鉴权与速率限制；
- 在 `docs/` 增加 OpenAPI 片段或示例集合；
- 为 `contexts` 热更新提供管理端点（GET/POST）。

