# ACRAC API端点功能映射表

**生成时间**: 2025-09-15T15:26:10.331887
**总端点数量**: 78
**前端调用次数**: 72
**后端调用次数**: 51

## 系统核心 (系统功能)

**描述**: 系统健康检查、根路径
**端点数量**: 2
**已使用**: 1
**未使用**: 1
**总使用次数**: 123

| 方法 | 路径 | 函数名 | 描述 | 前端使用 | 后端使用 | 总使用 | 状态 |
|------|------|--------|------|----------|----------|--------|------|
| GET | `/` | root | 根路径，返回API信息... | App(string_literal), App(axios), App(string_literal) (+69) | 未知模块(string_literal), 未知模块(string_literal), 未知模块(string_literal) (+48) | 123 | ✅ 已使用 |
| GET | `/health` | health_check | 健康检查端点... | - | - | 0 | ❌ 未使用 |

## RAG+LLM智能推荐 (核心功能)

**描述**: 基于向量语义搜索和大语言模型的智能医疗检查推荐
**端点数量**: 7
**已使用**: 5
**未使用**: 2
**总使用次数**: 25

| 方法 | 路径 | 函数名 | 描述 | 前端使用 | 后端使用 | 总使用 | 状态 |
|------|------|--------|------|----------|----------|--------|------|
| POST | `/intelligent-recommendation` | get_intelligent_recommendation | ... | getReason(axios), getReason(string_literal) | 未知模块(string_literal), RAGAS评测(internal_api), RAGAS评测(internal_api) (+4) | 9 | ✅ 已使用 |
| POST | `/rules-config` | update_rules_config | ... | App(axios), App(string_literal), App(axios) (+1) | - | 4 | ✅ 已使用 |
| GET | `/rules-config` | get_rules_config | ... | App(axios), App(string_literal), App(axios) (+1) | - | 4 | ✅ 已使用 |
| GET | `/rules-packs` | get_rules_packs | ... | format(axios), format(string_literal), format(axios) (+1) | - | 4 | ✅ 已使用 |
| POST | `/rules-packs` | set_rules_packs | ... | format(axios), format(string_literal), format(axios) (+1) | - | 4 | ✅ 已使用 |
| GET | `/intelligent-recommendation-simple` | get_intelligent_recommendation_simple | ... | - | - | 0 | ❌ 未使用 |
| GET | `/rag-llm-status` | check_rag_llm_status | 检查RAG+LLM服务状态... | - | - | 0 | ❌ 未使用 |

## 工具集 (工具功能)

**描述**: 重排序、LLM解析、RAGAS评分、向量搜索等工具
**端点数量**: 5
**已使用**: 5
**未使用**: 0
**总使用次数**: 10

| 方法 | 路径 | 函数名 | 描述 | 前端使用 | 后端使用 | 总使用 | 状态 |
|------|------|--------|------|----------|----------|--------|------|
| POST | `/rerank` | rerank_scenarios | ... | loadExample(axios), loadExample(string_literal) | - | 2 | ✅ 已使用 |
| POST | `/llm/parse` | llm_parse | ... | loadExample(axios), loadExample(string_literal) | - | 2 | ✅ 已使用 |
| POST | `/ragas/score` | ragas_score | ... | loadExample(axios), loadExample(string_literal) | - | 2 | ✅ 已使用 |
| GET | `/ragas/schema` | ragas_schema | ... | loadExample(axios), loadExample(string_literal) | - | 2 | ✅ 已使用 |
| POST | `/vector/search` | vector_search | ... | loadExample(axios), loadExample(string_literal) | - | 2 | ✅ 已使用 |

## ACRAC数据查询 (数据查询)

**描述**: 基础数据查询、统计、分析功能
**端点数量**: 13
**已使用**: 1
**未使用**: 12
**总使用次数**: 2

| 方法 | 路径 | 函数名 | 描述 | 前端使用 | 后端使用 | 总使用 | 状态 |
|------|------|--------|------|----------|----------|--------|------|
| GET | `/statistics` | get_statistics | 获取详细统计信息... | - | - | 0 | ❌ 未使用 |
| GET | `/panels` | list_panels | 列出所有Panels... | Unknown(axios), Unknown(string_literal) | - | 2 | ✅ 已使用 |
| GET | `/panels/{semantic_id}/topics` | get_topics_by_panel | 获取Panel下的所有Topics... | - | - | 0 | ❌ 未使用 |
| GET | `/topics/{semantic_id}/scenarios` | get_scenarios_by_topic | 获取Topic下的所有临床场景... | - | - | 0 | ❌ 未使用 |
| GET | `/procedures` | list_procedures | 列出检查项目... | - | - | 0 | ❌ 未使用 |
| GET | `/scenarios/{scenario_id}/recommendations` | get_recommendations_for_scenario | 获取场景的所有推荐... | - | - | 0 | ❌ 未使用 |
| GET | `/analytics/modality-distribution` | get_modality_distribution | 获取检查方式分布... | - | - | 0 | ❌ 未使用 |
| GET | `/analytics/rating-distribution` | get_rating_distribution | 获取适宜性评分分布... | - | - | 0 | ❌ 未使用 |
| GET | `/quick/high-rating-recommendations` | get_high_rating_recommendations | 获取高评分推荐... | - | - | 0 | ❌ 未使用 |
| GET | `/quick/procedures-by-modality/{modality}` | get_procedures_by_modality | 按检查方式获取检查项目... | - | - | 0 | ❌ 未使用 |
| GET | `/examples/complete-recommendation` | get_complete_recommendation_example | 获取完整推荐示例... | - | - | 0 | ❌ 未使用 |
| GET | `/search/procedures` | search_procedures_simple | 简单的检查项目搜索... | - | - | 0 | ❌ 未使用 |
| GET | `/search/recommendations` | search_recommendations_simple | 简单的推荐搜索... | - | - | 0 | ❌ 未使用 |

## RAGAS评测 (评测功能)

**描述**: RAGAS评测任务管理、数据上传、结果查询
**端点数量**: 14
**已使用**: 6
**未使用**: 8
**总使用次数**: 16

| 方法 | 路径 | 函数名 | 描述 | 前端使用 | 后端使用 | 总使用 | 状态 |
|------|------|--------|------|----------|----------|--------|------|
| POST | `/data/upload` | upload_file | 上传测试数据文件并解析保存到数据库... | Unknown(axios), Unknown(string_literal) | - | 2 | ✅ 已使用 |
| POST | `/data/preprocess` | preprocess_data | 预处理上传的数据文件... | - | - | 0 | ❌ 未使用 |
| GET | `/data/files` | list_uploaded_files | 列出已上传的文件... | - | - | 0 | ❌ 未使用 |
| GET | `/data/scenarios` | list_clinical_scenarios | 查询数据库中的临床场景数据... | Unknown(axios), Unknown(string_literal) | - | 2 | ✅ 已使用 |
| GET | `/data/batches` | list_upload_batches | 查询上传批次列表... | - | - | 0 | ❌ 未使用 |
| DELETE | `/data/files/{file_id}` | delete_uploaded_file | 删除上传的文件... | - | - | 0 | ❌ 未使用 |
| POST | `/evaluate` | start_evaluation | 启动RAGAS评测任务 - 从数据库选择数据进行评测... | getCombinedRagasItems(axios), getCombinedRagasItems(string_literal), getCombinedRagasItems(axios_template) (+2) | 未知模块(test) | 6 | ✅ 已使用 |
| GET | `/evaluate/{task_id}/status` | get_task_status | 获取评测任务状态... | - | - | 0 | ❌ 未使用 |
| GET | `/evaluate/{task_id}/results` | get_task_results | 获取评测任务结果... | - | - | 0 | ❌ 未使用 |
| DELETE | `/evaluate/{task_id}` | cancel_task | 取消评测任务... | - | - | 0 | ❌ 未使用 |
| GET | `/history` | get_evaluation_history | 获取评测历史记录列表... | getCombinedRagasItems(axios), getCombinedRagasItems(string_literal) | 未知模块(string_literal), 未知模块(string_literal) | 4 | ✅ 已使用 |
| GET | `/history/statistics` | get_evaluation_statistics | 获取评测统计信息... | - | - | 0 | ❌ 未使用 |
| GET | `/history/{task_id}` | get_history_detail | 获取历史记录详情... | - | 未知模块(string_literal) | 1 | ✅ 已使用 |
| DELETE | `/history/{task_id}` | delete_history_record | 删除历史记录... | - | 未知模块(string_literal) | 1 | ✅ 已使用 |

## 三种方法 (推荐方法)

**描述**: 向量检索、LLM分析、RAG混合推荐方法
**端点数量**: 4
**已使用**: 0
**未使用**: 4
**总使用次数**: 0

| 方法 | 路径 | 函数名 | 描述 | 前端使用 | 后端使用 | 总使用 | 状态 |
|------|------|--------|------|----------|----------|--------|------|
| POST | `/vector-method` | vector_method_recommendation | ... | - | - | 0 | ❌ 未使用 |
| POST | `/llm-method` | llm_method_recommendation | ... | - | - | 0 | ❌ 未使用 |
| POST | `/rag-method` | rag_method_recommendation | ... | - | - | 0 | ❌ 未使用 |
| POST | `/compare-all-methods` | compare_all_methods | ... | - | - | 0 | ❌ 未使用 |

## 数据管理 (管理功能)

**描述**: 数据上传、导入、验证、模型配置
**端点数量**: 6
**已使用**: 6
**未使用**: 0
**总使用次数**: 23

| 方法 | 路径 | 函数名 | 描述 | 前端使用 | 后端使用 | 总使用 | 状态 |
|------|------|--------|------|----------|----------|--------|------|
| GET | `/validate` | validate_data | ... | Unknown(axios), Unknown(string_literal), loadExample(axios) (+1) | - | 4 | ✅ 已使用 |
| POST | `/upload` | upload_csv | ... | Unknown(axios), Unknown(string_literal), getCombinedRagasItems(axios) (+3) | 未知模块(string_literal) | 7 | ✅ 已使用 |
| POST | `/import` | import_csv | ... | Unknown(axios), Unknown(string_literal) | - | 2 | ✅ 已使用 |
| GET | `/models/config` | get_models_config | ... | Unknown(axios), Unknown(string_literal), Unknown(axios) (+1) | - | 4 | ✅ 已使用 |
| POST | `/models/config` | set_models_config | ... | Unknown(axios), Unknown(string_literal), Unknown(axios) (+1) | - | 4 | ✅ 已使用 |
| POST | `/models/reload` | reload_rag_service | ... | Unknown(axios), Unknown(string_literal) | - | 2 | ✅ 已使用 |

## RAGAS评估 (评测功能)

**描述**: RAGAS评估执行、数据查询
**端点数量**: 4
**已使用**: 0
**未使用**: 4
**总使用次数**: 0

| 方法 | 路径 | 函数名 | 描述 | 前端使用 | 后端使用 | 总使用 | 状态 |
|------|------|--------|------|----------|----------|--------|------|
| POST | `/ragas-evaluate` | evaluate_ragas | 执行RAGAS评估... | - | - | 0 | ❌ 未使用 |
| GET | `/data/query` | query_evaluation_data | 查询评测数据... | - | - | 0 | ❌ 未使用 |
| POST | `/data/select-evaluate` | evaluate_selected_data | 对选中的数据进行评测... | - | - | 0 | ❌ 未使用 |
| GET | `/ragas-health` | ragas_health_check | ... | - | - | 0 | ❌ 未使用 |

## 智能分析 (分析功能)

**描述**: 临床案例分析、方法比较
**端点数量**: 3
**已使用**: 0
**未使用**: 3
**总使用次数**: 0

| 方法 | 路径 | 函数名 | 描述 | 前端使用 | 后端使用 | 总使用 | 状态 |
|------|------|--------|------|----------|----------|--------|------|
| POST | `/analyze-case` | analyze_clinical_case | ... | - | - | 0 | ❌ 未使用 |
| POST | `/quick-analysis` | quick_clinical_analysis | ... | - | - | 0 | ❌ 未使用 |
| POST | `/compare-methods` | compare_recommendation_methods | ... | - | - | 0 | ❌ 未使用 |

## 向量搜索 (搜索功能)

**描述**: 综合搜索、分类搜索、统计信息
**端点数量**: 7
**已使用**: 2
**未使用**: 5
**总使用次数**: 2

| 方法 | 路径 | 函数名 | 描述 | 前端使用 | 后端使用 | 总使用 | 状态 |
|------|------|--------|------|----------|----------|--------|------|
| POST | `/search/comprehensive` | comprehensive_search | ... | - | 未知模块(test) | 1 | ✅ 已使用 |
| POST | `/search/panels` | search_panels | 搜索科室... | - | - | 0 | ❌ 未使用 |
| POST | `/search/topics` | search_topics | 搜索主题... | - | - | 0 | ❌ 未使用 |
| POST | `/search/scenarios` | search_scenarios | 搜索临床场景... | - | - | 0 | ❌ 未使用 |
| POST | `/search/procedures` | search_procedures | 搜索检查项目... | - | - | 0 | ❌ 未使用 |
| POST | `/search/recommendations` | search_recommendations | 搜索临床推荐... | - | - | 0 | ❌ 未使用 |
| GET | `/stats` | get_database_stats | 获取数据库统计信息... | - | 未知模块(test) | 1 | ✅ 已使用 |

## 数据浏览 (数据浏览)

**描述**: 分层数据浏览、列表查询
**端点数量**: 4
**已使用**: 4
**未使用**: 0
**总使用次数**: 8

| 方法 | 路径 | 函数名 | 描述 | 前端使用 | 后端使用 | 总使用 | 状态 |
|------|------|--------|------|----------|----------|--------|------|
| GET | `/topics/by-panel` | list_topics_by_panel | ... | Unknown(axios), Unknown(string_literal) | - | 2 | ✅ 已使用 |
| GET | `/scenarios/by-topic` | list_scenarios_by_topic | ... | Unknown(axios), Unknown(string_literal) | - | 2 | ✅ 已使用 |
| GET | `/scenarios` | list_scenarios | ... | Unknown(axios), Unknown(string_literal) | - | 2 | ✅ 已使用 |
| GET | `/recommendations` | list_recommendations | ... | Unknown(axios), Unknown(string_literal) | - | 2 | ✅ 已使用 |

## 数据统计 (统计功能)

**描述**: 数据导入统计信息
**端点数量**: 1
**已使用**: 0
**未使用**: 1
**总使用次数**: 0

| 方法 | 路径 | 函数名 | 描述 | 前端使用 | 后端使用 | 总使用 | 状态 |
|------|------|--------|------|----------|----------|--------|------|
| GET | `/import-stats` | get_import_stats | 获取数据导入统计信息... | - | - | 0 | ❌ 未使用 |

## Excel评测 (评测功能)

**描述**: Excel文件上传、批量评测、结果导出
**端点数量**: 8
**已使用**: 7
**未使用**: 1
**总使用次数**: 17

| 方法 | 路径 | 函数名 | 描述 | 前端使用 | 后端使用 | 总使用 | 状态 |
|------|------|--------|------|----------|----------|--------|------|
| POST | `/upload-excel` | upload_excel_file | 上传Excel文件并解析... | getCombinedRagasItems(axios), getCombinedRagasItems(string_literal), getCombinedRagasItems(axios) (+1) | 未知模块(string_literal) | 5 | ✅ 已使用 |
| POST | `/start-evaluation` | start_evaluation | 开始批量评测... | getCombinedRagasItems(string_literal) | 未知模块(string_literal) | 2 | ✅ 已使用 |
| GET | `/evaluation-status` | get_evaluation_status | 获取评测状态... | getCombinedRagasItems(axios), getCombinedRagasItems(string_literal) | 未知模块(string_literal) | 3 | ✅ 已使用 |
| POST | `/stop-evaluation` | stop_evaluation | 停止评测... | getCombinedRagasItems(axios), getCombinedRagasItems(string_literal) | - | 2 | ✅ 已使用 |
| GET | `/evaluation-results` | get_evaluation_results | 获取评测结果... | - | - | 0 | ❌ 未使用 |
| POST | `/export-results` | export_results | 导出评测结果... | getCombinedRagasItems(axios), getCombinedRagasItems(string_literal) | - | 2 | ✅ 已使用 |
| GET | `/evaluation-history` | get_evaluation_history | 获取Excel评测历史数据... | - | 未知模块(string_literal), 未知模块(string_literal) | 2 | ✅ 已使用 |
| GET | `/evaluation-history/{task_id}` | get_evaluation_by_task_id | 根据任务ID获取评测数据... | - | 未知模块(string_literal) | 1 | ✅ 已使用 |
