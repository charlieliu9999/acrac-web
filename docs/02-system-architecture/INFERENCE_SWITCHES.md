ACRAC RAG+LLM 推理与评测开关说明

本文档概述智能推荐服务的调用方式、关键开关与参数含义、默认值建议及其性能/效果影响。用于快速定位可调入口、理解不同开关的取舍，以及配套的批量评测工具。

一、主要入口与调用关系
- 推理服务类：`backend/app/services/rag_llm_recommendation_service.py:1`
  - 主入口：`generate_intelligent_recommendation(...)` 用于执行完整的检索→重排→提示→LLM→解析→可选RAGAS。
  - 提示构造：`prepare_llm_prompt(...)` 控制是否在提示中携带每条推荐的“推荐理由”。
  - 关键阶段：
    1) 向量召回 `search_clinical_scenarios(...)`
    2) 取回召回场景的推荐详情 `get_scenario_with_recommendations(...)`
    3) 重排 `
       - _rerank_scenarios(...)`（词/面板/主题加权 + reranker 模型）
       - 运行前可触发动态“跳过重排”策略（高置信Top1时加速）
       - 可选：规则引擎 rerank 审计/加权 `rules_engine.apply_rerank(...)`
    4) 构造提示 `prepare_llm_prompt(...)`（是否携带“推荐理由”受 `show_reasoning` 控制）
    5) LLM 生成与解析 `call_llm(...)` + `parse_llm_response(...)`
    6) 可选：规则引擎 post 审计/修订 `rules_engine.apply_post(...)`
    7) 可选：RAGAS 评分 `_compute_ragas_scores(...)`

- 推理 API 端点：`backend/app/api/api_v1/endpoints/rag_llm_api.py:1`
  - `POST /intelligent-recommendation` 对应上面的服务入口，并支持透传调参（见下文“请求级开关”）。

- Excel 批量评测 API：`backend/app/api/api_v1/endpoints/excel_evaluation_api.py:1`
  - 支持上传 Excel、后台批量跑真实推理（可导出结果），内部按服务入口调用。

- A/B 测试脚本：`backend/scripts/ab_test_show_reasoning.py:1`
  - 对比“带理由 vs 不带理由”的性能与命中率；可选启用 RAGAS。

二、请求级开关（API 或服务入参）
- `top_scenarios`：提示中展示的场景数量。默认取 `RAG_TOP_SCENARIOS`（一般为 2）。
- `top_recommendations_per_scenario`：每个场景展示的推荐数量。默认取 `RAG_TOP_RECOMMENDATIONS_PER_SCENARIO`（一般为 3）。
- `show_reasoning`：提示中是否携带“推荐理由”。默认取 `RAG_SHOW_REASONING`（建议默认 false）。
- `similarity_threshold`：低相似度阈值，低于阈值走无RAG精简路径。默认取 `VECTOR_SIMILARITY_THRESHOLD`（一般 0.6）。
- `debug_mode`：输出 trace 与提示长度信息，便于性能分析与问题定位（会有少量开销）。
- `compute_ragas` + `ground_truth`：是否在服务内同步计算 RAGAS，以及传入的标准答案（可选）。

三、服务级/环境级开关（.env）
性能/吞吐相关
- `DB_POOL_MIN`/`DB_POOL_MAX`：PG 连接池大小（默认 1/10）。
- `PGVECTOR_PROBES`：IVFFLAT 检索 probes，越大召回率越高、延迟越大（默认 20，建议 8~20 做权衡）。
- `RAG_SCENE_RECALL_TOPK`：向量召回的场景数量（默认 8）。
- `RAG_RECS_FETCH_TOPK`：对召回场景取推荐详情的数量上限（默认 5），降低 DB I/O。
- `RAG_USE_RERANKER`：是否启用 reranker（默认 true）。
- `RERANK_PROVIDER`：`auto|siliconflow|ollama|local`（默认 auto）。
- `RERANKER_MODEL`：重排模型名（默认 `BAAI/bge-reranker-v2-m3`）。
- `RAG_USE_DYNAMIC_RERANK`：是否动态跳过 rerank（Top1 高置信且与 Top2 差距明显时，默认 true）。
- `EMBED_CACHE_SIZE`：进程内嵌入LRU缓存大小（默认 256）。

提示/LLM相关
- `RAG_TOP_SCENARIOS`、`RAG_TOP_RECOMMENDATIONS_PER_SCENARIO`：参见请求级同名参数默认来源。
- `RAG_SHOW_REASONING`：默认是否携带推荐理由（建议 false）。
- `LLM_FORCE_JSON`：强制 JSON 输出（兼容的 OpenAI 代理支持，默认 true）。
- `LLM_MAX_TOKENS`：限制 LLM 输出长度，避免过度生成（默认 512）。
- `LLM_SEED`：固定随机性，便于 A/B 稳态复现（可选）。

模型与端点
- `SILICONFLOW_API_KEY`、`SILICONFLOW_BASE_URL`：OpenAI 兼容端点。
- `SILICONFLOW_LLM_MODEL`、`SILICONFLOW_EMBEDDING_MODEL`：服务默认的推理/嵌入模型。

四、规则引擎与“动态理由”的关系
- 规则引擎（`rules_engine`）
  - 作用：在 rerank 与 post 两个阶段提供审计/加权/修订能力。
  - 开关：`/rules-config` API 或环境中的 `enabled/audit_only`，参考 `backend/app/api/api_v1/endpoints/rag_llm_api.py:1`。
  - 不直接决定“是否在提示里携带理由”。
- 动态“理由”机制
  - 作用：仅影响提示工程（输入侧），根据场景灵活附加简短要点以提升判别信息密度并控制长度。
  - 触发建议：低相似度/无RAG、评分并列、命中高风险信号等。
  - 可选整合：若希望统一治理，可让规则引擎在审计日志中打标，提示层读取标记决定是否附理由。

五、Excel 批量评测
- API：`backend/app/api/api_v1/endpoints/excel_evaluation_api.py:1`
- 连接复用与并发：内部使用 `requests.Session` 与线程池；并发度可用 `EVAL_CONCURRENCY`（默认 3）。
- 导出：`/export-results` 导出 Excel；`/evaluation-history` 查询历史。

六、A/B 测试脚本用法
- 路径：`backend/scripts/ab_test_show_reasoning.py:1`
- 示例：
  - 仅性能与命中率：
    `python backend/scripts/ab_test_show_reasoning.py --excel ACR_data/影像测试样例-0318-1.xlsx --limit 50 --top-scenarios 2 --top-recs 3 --sim-threshold 0.6`
  - 含 RAGAS（更慢/有成本）：
    `python backend/scripts/ab_test_show_reasoning.py --excel ... --limit 50 --with-ragas`
- 输出：根目录 JSON 汇总 + 追加到 `docs/AB_TEST_SHOW_REASONING_REPORT.md` 的报告节。

七、默认值建议（性能与准确性权衡）
- `RAG_TOP_SCENARIOS=2`、`RAG_TOP_RECOMMENDATIONS_PER_SCENARIO=3`、`RAG_SHOW_REASONING=false`
- `RAG_SCENE_RECALL_TOPK=6~8`、`PGVECTOR_PROBES=10~20`
- `RAG_USE_RERANKER=true` + `RAG_USE_DYNAMIC_RERANK=true`
- `LLM_FORCE_JSON=true`、`LLM_MAX_TOKENS=512`

八、常见问题
- JSON 解析不稳：已内置容错解析；若服务端支持，可保持 `LLM_FORCE_JSON=true` 提高稳定性。
- 命中率评估偏低：建议将 Ground Truth 与模型输出都映射到 `procedure_dictionary.semantic_id` 再比较；当前 A/B 使用名称规范化匹配，可能低估真实命中。
- RAGAS 与命中率的关系：RAGAS衡量文本忠实度/相关性，与“命中标准化首选项目”不同，互补使用更全面。

