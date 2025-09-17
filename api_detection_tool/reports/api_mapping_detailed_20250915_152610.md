# ACRAC API端点详细功能映射报告

**生成时间**: 2025-09-15T15:26:10.331887

## 📊 检测摘要

- **总API端点数量**: 78
- **前端调用次数**: 72
- **后端调用次数**: 51

## 🔧 系统核心 (系统功能)

**模块描述**: 系统健康检查、根路径
**端点数量**: 2
**已使用端点**: 1
**未使用端点**: 1
**总使用次数**: 123

### ✅ 已使用的端点

#### GET /
**函数名**: root
**描述**: 根路径，返回API信息
**总使用次数**: 123
**前端使用**:
- App (frontend/src/App.tsx:11)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: import { api } from './api/http'...
- App (frontend/src/App.tsx:35)
  - 函数: unknown
  - 类型: axios
  - 上下文: api.get('/api/v1/acrac/rag-llm/rules-config').then(res => {...
- App (frontend/src/App.tsx:35)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: api.get('/api/v1/acrac/rag-llm/rules-config').then(res => {...
- App (frontend/src/App.tsx:43)
  - 函数: updateRules
  - 类型: axios
  - 上下文: const res = await api.post('/api/v1/acrac/rag-llm/rules-config', {...
- App (frontend/src/App.tsx:43)
  - 函数: updateRules
  - 类型: string_literal
  - 上下文: const res = await api.post('/api/v1/acrac/rag-llm/rules-config', {...
- Unknown (frontend/src/pages/DataImport.tsx:3)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: import { api } from '../api/http'...
- Unknown (frontend/src/pages/DataImport.tsx:19)
  - 函数: customRequest
  - 类型: axios
  - 上下文: const r = await api.post('/api/v1/admin/data/upload', form, { headers: { 'Content-Type': 'multipart/...
- Unknown (frontend/src/pages/DataImport.tsx:19)
  - 函数: customRequest
  - 类型: string_literal
  - 上下文: const r = await api.post('/api/v1/admin/data/upload', form, { headers: { 'Content-Type': 'multipart/...
- Unknown (frontend/src/pages/DataImport.tsx:34)
  - 函数: onFinish
  - 类型: axios
  - 上下文: const r = await api.post('/api/v1/admin/data/import', {...
- Unknown (frontend/src/pages/DataImport.tsx:34)
  - 函数: onFinish
  - 类型: string_literal
  - 上下文: const r = await api.post('/api/v1/admin/data/import', {...
- Unknown (frontend/src/pages/DataImport.tsx:53)
  - 函数: handleValidate
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/admin/data/validate')...
- Unknown (frontend/src/pages/DataImport.tsx:53)
  - 函数: handleValidate
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/admin/data/validate')...
- format (frontend/src/pages/RulesManager.tsx:3)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: import { api } from '../api/http'...
- format (frontend/src/pages/RulesManager.tsx:13)
  - 函数: load
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/acrac/rag-llm/rules-packs')...
- format (frontend/src/pages/RulesManager.tsx:13)
  - 函数: load
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/acrac/rag-llm/rules-packs')...
- format (frontend/src/pages/RulesManager.tsx:26)
  - 函数: save
  - 类型: axios
  - 上下文: await api.post('/api/v1/acrac/rag-llm/rules-packs', { content: obj })...
- format (frontend/src/pages/RulesManager.tsx:26)
  - 函数: save
  - 类型: string_literal
  - 上下文: await api.post('/api/v1/acrac/rag-llm/rules-packs', { content: obj })...
- loadExample (frontend/src/pages/Tools.tsx:3)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: import { api } from '../api/http'...
- loadExample (frontend/src/pages/Tools.tsx:45)
  - 函数: doVector
  - 类型: axios
  - 上下文: const r = await api.post('/api/v1/acrac/tools/vector/search', v)...
- loadExample (frontend/src/pages/Tools.tsx:45)
  - 函数: doVector
  - 类型: string_literal
  - 上下文: const r = await api.post('/api/v1/acrac/tools/vector/search', v)...
- loadExample (frontend/src/pages/Tools.tsx:54)
  - 函数: doRerank
  - 类型: axios
  - 上下文: const r = await api.post('/api/v1/acrac/tools/rerank', { query: v.query, scenarios })...
- loadExample (frontend/src/pages/Tools.tsx:54)
  - 函数: doRerank
  - 类型: string_literal
  - 上下文: const r = await api.post('/api/v1/acrac/tools/rerank', { query: v.query, scenarios })...
- loadExample (frontend/src/pages/Tools.tsx:63)
  - 函数: doParse
  - 类型: axios
  - 上下文: const r = await api.post('/api/v1/acrac/tools/llm/parse', { llm_raw: parseText })...
- loadExample (frontend/src/pages/Tools.tsx:63)
  - 函数: doParse
  - 类型: string_literal
  - 上下文: const r = await api.post('/api/v1/acrac/tools/llm/parse', { llm_raw: parseText })...
- loadExample (frontend/src/pages/Tools.tsx:97)
  - 函数: unknown
  - 类型: axios
  - 上下文: const r = await api.post('/api/v1/acrac/tools/ragas/score', payload)...
- loadExample (frontend/src/pages/Tools.tsx:97)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: const r = await api.post('/api/v1/acrac/tools/ragas/score', payload)...
- loadExample (frontend/src/pages/Tools.tsx:106)
  - 函数: loadRagasSchema
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/acrac/tools/ragas/schema')...
- loadExample (frontend/src/pages/Tools.tsx:106)
  - 函数: loadRagasSchema
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/acrac/tools/ragas/schema')...
- loadExample (frontend/src/pages/Tools.tsx:116)
  - 函数: loadVectorStatus
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/admin/data/validate')...
- loadExample (frontend/src/pages/Tools.tsx:116)
  - 函数: loadVectorStatus
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/admin/data/validate')...
- getReason (frontend/src/pages/RAGAssistant.tsx:3)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: import { api } from '../api/http'...
- getReason (frontend/src/pages/RAGAssistant.tsx:26)
  - 函数: onFinish
  - 类型: axios
  - 上下文: const r = await api.post('/api/v1/acrac/rag-llm/intelligent-recommendation', payload)...
- getReason (frontend/src/pages/RAGAssistant.tsx:26)
  - 函数: onFinish
  - 类型: string_literal
  - 上下文: const r = await api.post('/api/v1/acrac/rag-llm/intelligent-recommendation', payload)...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:4)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: import { api } from '../api/http'...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:200)
  - 函数: unknown
  - 类型: axios
  - 上下文: const response = await api.post('/api/v1/acrac/rag/query', {...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:200)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: const response = await api.post('/api/v1/acrac/rag/query', {...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:309)
  - 函数: fetchTestCases
  - 类型: axios
  - 上下文: const response = await api.get('/api/v1/acrac/test-cases')...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:309)
  - 函数: fetchTestCases
  - 类型: string_literal
  - 上下文: const response = await api.get('/api/v1/acrac/test-cases')...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:335)
  - 函数: loadHistoryData
  - 类型: axios
  - 上下文: const response = await api.get('/api/v1/ragas/history', {...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:335)
  - 函数: loadHistoryData
  - 类型: string_literal
  - 上下文: const response = await api.get('/api/v1/ragas/history', {...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:402)
  - 函数: unknown
  - 类型: axios
  - 上下文: const response = await api.post('/api/v1/acrac/excel-evaluation/upload-excel', formData, {...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:402)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: const response = await api.post('/api/v1/acrac/excel-evaluation/upload-excel', formData, {...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:461)
  - 函数: unknown
  - 类型: axios
  - 上下文: const response = await api.post('/api/v1/ragas/evaluate', {...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:461)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: const response = await api.post('/api/v1/ragas/evaluate', {...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:475)
  - 函数: unknown
  - 类型: axios
  - 上下文: const response = await api.post('/api/v1/acrac/excel-evaluation/upload-excel', formData, {...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:475)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: const response = await api.post('/api/v1/acrac/excel-evaluation/upload-excel', formData, {...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:559)
  - 函数: startRagasStatusPolling
  - 类型: axios_template
  - 上下文: const response = await api.get(`/api/v1/ragas/evaluate/${taskId}/status`)...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:575)
  - 函数: unknown
  - 类型: axios_template
  - 上下文: const resultsResponse = await api.get(`/api/v1/ragas/evaluate/${taskId}/results`)...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:615)
  - 函数: stopRagasEvaluation
  - 类型: axios_template
  - 上下文: await api.post(`/api/v1/ragas/evaluate/${ragasTaskId}/stop`)...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:640)
  - 函数: startExcelEvaluation
  - 类型: string_literal
  - 上下文: '/api/v1/acrac/excel-evaluation/start-evaluation',...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:660)
  - 函数: startExcelStatusPolling
  - 类型: axios
  - 上下文: const response = await api.get('/api/v1/acrac/excel-evaluation/evaluation-status')...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:660)
  - 函数: startExcelStatusPolling
  - 类型: string_literal
  - 上下文: const response = await api.get('/api/v1/acrac/excel-evaluation/evaluation-status')...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:685)
  - 函数: stopExcelEvaluation
  - 类型: axios
  - 上下文: await api.post('/api/v1/acrac/excel-evaluation/stop-evaluation')...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:685)
  - 函数: stopExcelEvaluation
  - 类型: string_literal
  - 上下文: await api.post('/api/v1/acrac/excel-evaluation/stop-evaluation')...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:700)
  - 函数: exportExcelResults
  - 类型: axios
  - 上下文: const response = await api.post('/api/v1/acrac/excel-evaluation/export-results')...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:700)
  - 函数: exportExcelResults
  - 类型: string_literal
  - 上下文: const response = await api.post('/api/v1/acrac/excel-evaluation/export-results')...
- Unknown (frontend/src/pages/ModelConfig.tsx:3)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: import { api } from '../api/http'...
- Unknown (frontend/src/pages/ModelConfig.tsx:15)
  - 函数: load
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/admin/data/models/config')...
- Unknown (frontend/src/pages/ModelConfig.tsx:15)
  - 函数: load
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/admin/data/models/config')...
- Unknown (frontend/src/pages/ModelConfig.tsx:35)
  - 函数: save
  - 类型: axios
  - 上下文: const r = await api.post('/api/v1/admin/data/models/config', v)...
- Unknown (frontend/src/pages/ModelConfig.tsx:35)
  - 函数: save
  - 类型: string_literal
  - 上下文: const r = await api.post('/api/v1/admin/data/models/config', v)...
- Unknown (frontend/src/pages/ModelConfig.tsx:51)
  - 函数: reloadSvc
  - 类型: axios
  - 上下文: await api.post('/api/v1/admin/data/models/reload')...
- Unknown (frontend/src/pages/ModelConfig.tsx:51)
  - 函数: reloadSvc
  - 类型: string_literal
  - 上下文: await api.post('/api/v1/admin/data/models/reload')...
- Unknown (frontend/src/pages/DataBrowser.tsx:3)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: import { api } from '../api/http'...
- Unknown (frontend/src/pages/DataBrowser.tsx:19)
  - 函数: loadPanels
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/acrac/data/panels')...
- Unknown (frontend/src/pages/DataBrowser.tsx:19)
  - 函数: loadPanels
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/acrac/data/panels')...
- Unknown (frontend/src/pages/DataBrowser.tsx:27)
  - 函数: loadTopics
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/acrac/data/topics/by-panel', { params: { panel_id: pid }})...
- Unknown (frontend/src/pages/DataBrowser.tsx:27)
  - 函数: loadTopics
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/acrac/data/topics/by-panel', { params: { panel_id: pid }})...
- Unknown (frontend/src/pages/DataBrowser.tsx:35)
  - 函数: loadScenarios
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/acrac/data/scenarios/by-topic', { params: { topic_id: tid }})...
- Unknown (frontend/src/pages/DataBrowser.tsx:35)
  - 函数: loadScenarios
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/acrac/data/scenarios/by-topic', { params: { topic_id: tid }})...
- Unknown (frontend/src/pages/DataBrowser.tsx:43)
  - 函数: loadRecs
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/acrac/data/recommendations', { params: { scenario_id: sid, page: 1,...
- Unknown (frontend/src/pages/DataBrowser.tsx:43)
  - 函数: loadRecs
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/acrac/data/recommendations', { params: { scenario_id: sid, page: 1,...
**后端使用**:
- 未知模块 (backend/demo_excel_evaluation.py:44)
  - 函数: upload_excel_file
  - 类型: string_literal
  - 异步: False
- 未知模块 (backend/demo_excel_evaluation.py:67)
  - 函数: start_evaluation
  - 类型: string_literal
  - 异步: False
- 未知模块 (backend/demo_excel_evaluation.py:90)
  - 函数: check_evaluation_status
  - 类型: string_literal
  - 异步: False
- 未知模块 (backend/demo_excel_evaluation.py:108)
  - 函数: get_evaluation_history
  - 类型: string_literal
  - 异步: False
- 未知模块 (backend/demo_excel_evaluation.py:134)
  - 函数: get_task_results
  - 类型: string_literal
  - 异步: False
- 未知模块 (backend/test_ragas_api.py:41)
  - 函数: unknown
  - 类型: test
  - 异步: False
- 未知模块 (backend/test_ragas_complete.py:15)
  - 函数: unknown
  - 类型: test
  - 异步: False
- 未知模块 (backend/test_ragas_complete.py:123)
  - 函数: test_ragas_evaluation
  - 类型: test
  - 异步: False
- 未知模块 (backend/app/core/config.py:11)
  - 函数: unknown
  - 类型: string_literal
  - 异步: False
- 未知模块 (backend/app/core/config.py:50)
  - 函数: unknown
  - 类型: string_literal
  - 异步: False
- 未知模块 (backend/app/core/config.py:59)
  - 函数: unknown
  - 类型: string_literal
  - 异步: False
- 未知模块 (backend/app/schemas/ragas_schemas.py:94)
  - 函数: unknown
  - 类型: string_literal
  - 异步: False
- RAGAS评测 (backend/app/api/api_v1/endpoints/ragas_api.py:594)
  - 函数: unknown
  - 类型: internal_api
  - 异步: False
- RAGAS评测 (backend/app/api/api_v1/endpoints/ragas_api.py:1164)
  - 函数: run_real_rag_evaluation
  - 类型: internal_api
  - 异步: True
- 数据管理 (backend/app/api/api_v1/endpoints/admin_data_api.py:191)
  - 函数: has
  - 类型: internal_api
  - 异步: False
- RAGAS评估 (backend/app/api/api_v1/endpoints/ragas_evaluation_api.py:52)
  - 函数: unknown
  - 类型: internal_api
  - 异步: False
- RAGAS评估 (backend/app/api/api_v1/endpoints/ragas_evaluation_api.py:70)
  - 函数: setup_models
  - 类型: internal_api
  - 异步: False
- RAGAS评估 (backend/app/api/api_v1/endpoints/ragas_evaluation_api.py:192)
  - 函数: run_evaluation
  - 类型: internal_api
  - 异步: False
- Excel评测 (backend/app/api/api_v1/endpoints/excel_evaluation_api.py:43)
  - 函数: __init__
  - 类型: internal_api
  - 异步: False
- 未知模块 (backend/app/services/vector_search_service.py:33)
  - 函数: __init__
  - 类型: internal_service
  - 异步: False
- 未知模块 (backend/app/services/ragas_evaluator.py:91)
  - 函数: unknown
  - 类型: internal_service
  - 异步: False
- 未知模块 (backend/app/services/rag_llm_recommendation_service_副本.py:45)
  - 函数: embed_with_siliconflow
  - 类型: internal_service
  - 异步: False
- 未知模块 (backend/app/services/rag_llm_recommendation_service_副本.py:45)
  - 函数: embed_with_siliconflow
  - 类型: internal_service
  - 异步: False
- 未知模块 (backend/app/services/rag_llm_recommendation_service_副本.py:68)
  - 函数: __init__
  - 类型: internal_service
  - 异步: False
- 未知模块 (backend/app/services/rag_llm_recommendation_service_副本.py:1011)
  - 函数: _compute_ragas_scores
  - 类型: internal_service
  - 异步: False
- 未知模块 (backend/app/services/rag_llm_recommendation_service_副本.py:1167)
  - 函数: _siliconflow_rerank_scenarios
  - 类型: internal_service
  - 异步: False
- 未知模块 (backend/app/services/intelligent_recommendation_service.py:674)
  - 函数: _generate_query_vector
  - 类型: internal_service
  - 异步: False
- 未知模块 (backend/app/services/ragas_service.py:187)
  - 函数: unknown
  - 类型: internal_service
  - 异步: False
- 未知模块 (backend/app/services/ollama_qwen_service.py:22)
  - 函数: check_availability
  - 类型: internal_service
  - 异步: False
- 未知模块 (backend/app/services/ollama_qwen_service.py:22)
  - 函数: check_availability
  - 类型: internal_service
  - 异步: False
- 未知模块 (backend/app/services/ollama_qwen_service.py:177)
  - 函数: unknown
  - 类型: internal_service
  - 异步: False
- 未知模块 (backend/app/services/ollama_qwen_service.py:341)
  - 函数: install_model
  - 类型: internal_service
  - 异步: False
- 未知模块 (backend/app/services/rag_llm_recommendation_service.py:45)
  - 函数: embed_with_siliconflow
  - 类型: internal_service
  - 异步: False
- 未知模块 (backend/app/services/rag_llm_recommendation_service.py:45)
  - 函数: embed_with_siliconflow
  - 类型: internal_service
  - 异步: False
- 未知模块 (backend/app/services/rag_llm_recommendation_service.py:68)
  - 函数: __init__
  - 类型: internal_service
  - 异步: False
- 未知模块 (backend/app/services/rag_llm_recommendation_service.py:1070)
  - 函数: _compute_ragas_scores
  - 类型: internal_service
  - 异步: False
- 未知模块 (backend/app/services/rag_llm_recommendation_service.py:1192)
  - 函数: unknown
  - 类型: internal_service
  - 异步: False
- 未知模块 (backend/app/services/rag_llm_recommendation_service.py:1378)
  - 函数: _siliconflow_rerank_scenarios
  - 类型: internal_service
  - 异步: False
- 未知模块 (backend/tests/quick_test_demo.py:53)
  - 函数: test_vector_search_comprehensive
  - 类型: test
  - 异步: True
- 未知模块 (backend/tests/quick_test_demo.py:101)
  - 函数: test_database_stats
  - 类型: test
  - 异步: True
- 未知模块 (backend/RAGAS/official_ragas_evaluation.py:66)
  - 函数: setup_models
  - 类型: string_literal
  - 异步: False
- 未知模块 (backend/RAGAS/official_ragas_evaluation.py:74)
  - 函数: setup_models
  - 类型: string_literal
  - 异步: False
- 未知模块 (backend/RAGAS/comprehensive_ragas_demo.py:54)
  - 函数: setup_models
  - 类型: string_literal
  - 异步: False
- 未知模块 (backend/RAGAS/comprehensive_ragas_demo.py:62)
  - 函数: setup_models
  - 类型: string_literal
  - 异步: False
- 未知模块 (backend/RAGAS/trace_five_cases.py:18)
  - 函数: unknown
  - 类型: string_literal
  - 异步: False
- 未知模块 (backend/RAGAS/correct_ragas_solution.py:66)
  - 函数: setup_models
  - 类型: string_literal
  - 异步: False
- 未知模块 (backend/RAGAS/correct_ragas_solution.py:74)
  - 函数: setup_models
  - 类型: string_literal
  - 异步: False
- 未知模块 (backend/scripts/build_acrac_from_csv_siliconflow.py:85)
  - 函数: __init__
  - 类型: string_literal
  - 异步: False
- 未知模块 (backend/scripts/run_ragas_eval_from_excel.py:44)
  - 函数: main
  - 类型: string_literal
  - 异步: True
- 未知模块 (backend/scripts/test_siliconflow_reranker.py:25)
  - 函数: test_rerank
  - 类型: test
  - 异步: False
- 未知模块 (backend/scripts/update_procedure_embeddings.py:10)
  - 函数: unknown
  - 类型: string_literal
  - 异步: False

### ❌ 未使用的端点

- **GET /health** (health_check)
  - 描述: 健康检查端点
  - 文件: backend/app/main.py:69

## 🔧 RAG+LLM智能推荐 (核心功能)

**模块描述**: 基于向量语义搜索和大语言模型的智能医疗检查推荐
**端点数量**: 7
**已使用端点**: 5
**未使用端点**: 2
**总使用次数**: 25

### ✅ 已使用的端点

#### POST /intelligent-recommendation
**函数名**: get_intelligent_recommendation
**描述**: 
**总使用次数**: 9
**前端使用**:
- getReason (frontend/src/pages/RAGAssistant.tsx:26)
  - 函数: onFinish
  - 类型: axios
  - 上下文: const r = await api.post('/api/v1/acrac/rag-llm/intelligent-recommendation', payload)...
- getReason (frontend/src/pages/RAGAssistant.tsx:26)
  - 函数: onFinish
  - 类型: string_literal
  - 上下文: const r = await api.post('/api/v1/acrac/rag-llm/intelligent-recommendation', payload)...
**后端使用**:
- 未知模块 (backend/app/core/config.py:59)
  - 函数: unknown
  - 类型: string_literal
  - 异步: False
- RAGAS评测 (backend/app/api/api_v1/endpoints/ragas_api.py:594)
  - 函数: unknown
  - 类型: internal_api
  - 异步: False
- RAGAS评测 (backend/app/api/api_v1/endpoints/ragas_api.py:1164)
  - 函数: run_real_rag_evaluation
  - 类型: internal_api
  - 异步: True
- Excel评测 (backend/app/api/api_v1/endpoints/excel_evaluation_api.py:43)
  - 函数: __init__
  - 类型: internal_api
  - 异步: False
- 未知模块 (backend/app/services/ragas_service.py:187)
  - 函数: unknown
  - 类型: internal_service
  - 异步: False
- 未知模块 (backend/RAGAS/trace_five_cases.py:18)
  - 函数: unknown
  - 类型: string_literal
  - 异步: False
- 未知模块 (backend/scripts/run_ragas_eval_from_excel.py:44)
  - 函数: main
  - 类型: string_literal
  - 异步: True

#### POST /rules-config
**函数名**: update_rules_config
**描述**: 
**总使用次数**: 4
**前端使用**:
- App (frontend/src/App.tsx:35)
  - 函数: unknown
  - 类型: axios
  - 上下文: api.get('/api/v1/acrac/rag-llm/rules-config').then(res => {...
- App (frontend/src/App.tsx:35)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: api.get('/api/v1/acrac/rag-llm/rules-config').then(res => {...
- App (frontend/src/App.tsx:43)
  - 函数: updateRules
  - 类型: axios
  - 上下文: const res = await api.post('/api/v1/acrac/rag-llm/rules-config', {...
- App (frontend/src/App.tsx:43)
  - 函数: updateRules
  - 类型: string_literal
  - 上下文: const res = await api.post('/api/v1/acrac/rag-llm/rules-config', {...

#### GET /rules-config
**函数名**: get_rules_config
**描述**: 
**总使用次数**: 4
**前端使用**:
- App (frontend/src/App.tsx:35)
  - 函数: unknown
  - 类型: axios
  - 上下文: api.get('/api/v1/acrac/rag-llm/rules-config').then(res => {...
- App (frontend/src/App.tsx:35)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: api.get('/api/v1/acrac/rag-llm/rules-config').then(res => {...
- App (frontend/src/App.tsx:43)
  - 函数: updateRules
  - 类型: axios
  - 上下文: const res = await api.post('/api/v1/acrac/rag-llm/rules-config', {...
- App (frontend/src/App.tsx:43)
  - 函数: updateRules
  - 类型: string_literal
  - 上下文: const res = await api.post('/api/v1/acrac/rag-llm/rules-config', {...

#### GET /rules-packs
**函数名**: get_rules_packs
**描述**: 
**总使用次数**: 4
**前端使用**:
- format (frontend/src/pages/RulesManager.tsx:13)
  - 函数: load
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/acrac/rag-llm/rules-packs')...
- format (frontend/src/pages/RulesManager.tsx:13)
  - 函数: load
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/acrac/rag-llm/rules-packs')...
- format (frontend/src/pages/RulesManager.tsx:26)
  - 函数: save
  - 类型: axios
  - 上下文: await api.post('/api/v1/acrac/rag-llm/rules-packs', { content: obj })...
- format (frontend/src/pages/RulesManager.tsx:26)
  - 函数: save
  - 类型: string_literal
  - 上下文: await api.post('/api/v1/acrac/rag-llm/rules-packs', { content: obj })...

#### POST /rules-packs
**函数名**: set_rules_packs
**描述**: 
**总使用次数**: 4
**前端使用**:
- format (frontend/src/pages/RulesManager.tsx:13)
  - 函数: load
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/acrac/rag-llm/rules-packs')...
- format (frontend/src/pages/RulesManager.tsx:13)
  - 函数: load
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/acrac/rag-llm/rules-packs')...
- format (frontend/src/pages/RulesManager.tsx:26)
  - 函数: save
  - 类型: axios
  - 上下文: await api.post('/api/v1/acrac/rag-llm/rules-packs', { content: obj })...
- format (frontend/src/pages/RulesManager.tsx:26)
  - 函数: save
  - 类型: string_literal
  - 上下文: await api.post('/api/v1/acrac/rag-llm/rules-packs', { content: obj })...

### ❌ 未使用的端点

- **GET /intelligent-recommendation-simple** (get_intelligent_recommendation_simple)
  - 描述: 
  - 文件: backend/app/api/api_v1/endpoints/rag_llm_api.py:201
- **GET /rag-llm-status** (check_rag_llm_status)
  - 描述: 检查RAG+LLM服务状态
  - 文件: backend/app/api/api_v1/endpoints/rag_llm_api.py:231

## 🔧 工具集 (工具功能)

**模块描述**: 重排序、LLM解析、RAGAS评分、向量搜索等工具
**端点数量**: 5
**已使用端点**: 5
**未使用端点**: 0
**总使用次数**: 10

### ✅ 已使用的端点

#### POST /rerank
**函数名**: rerank_scenarios
**描述**: 
**总使用次数**: 2
**前端使用**:
- loadExample (frontend/src/pages/Tools.tsx:54)
  - 函数: doRerank
  - 类型: axios
  - 上下文: const r = await api.post('/api/v1/acrac/tools/rerank', { query: v.query, scenarios })...
- loadExample (frontend/src/pages/Tools.tsx:54)
  - 函数: doRerank
  - 类型: string_literal
  - 上下文: const r = await api.post('/api/v1/acrac/tools/rerank', { query: v.query, scenarios })...

#### POST /llm/parse
**函数名**: llm_parse
**描述**: 
**总使用次数**: 2
**前端使用**:
- loadExample (frontend/src/pages/Tools.tsx:63)
  - 函数: doParse
  - 类型: axios
  - 上下文: const r = await api.post('/api/v1/acrac/tools/llm/parse', { llm_raw: parseText })...
- loadExample (frontend/src/pages/Tools.tsx:63)
  - 函数: doParse
  - 类型: string_literal
  - 上下文: const r = await api.post('/api/v1/acrac/tools/llm/parse', { llm_raw: parseText })...

#### POST /ragas/score
**函数名**: ragas_score
**描述**: 
**总使用次数**: 2
**前端使用**:
- loadExample (frontend/src/pages/Tools.tsx:97)
  - 函数: unknown
  - 类型: axios
  - 上下文: const r = await api.post('/api/v1/acrac/tools/ragas/score', payload)...
- loadExample (frontend/src/pages/Tools.tsx:97)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: const r = await api.post('/api/v1/acrac/tools/ragas/score', payload)...

#### GET /ragas/schema
**函数名**: ragas_schema
**描述**: 
**总使用次数**: 2
**前端使用**:
- loadExample (frontend/src/pages/Tools.tsx:106)
  - 函数: loadRagasSchema
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/acrac/tools/ragas/schema')...
- loadExample (frontend/src/pages/Tools.tsx:106)
  - 函数: loadRagasSchema
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/acrac/tools/ragas/schema')...

#### POST /vector/search
**函数名**: vector_search
**描述**: 
**总使用次数**: 2
**前端使用**:
- loadExample (frontend/src/pages/Tools.tsx:45)
  - 函数: doVector
  - 类型: axios
  - 上下文: const r = await api.post('/api/v1/acrac/tools/vector/search', v)...
- loadExample (frontend/src/pages/Tools.tsx:45)
  - 函数: doVector
  - 类型: string_literal
  - 上下文: const r = await api.post('/api/v1/acrac/tools/vector/search', v)...

## 🔧 ACRAC数据查询 (数据查询)

**模块描述**: 基础数据查询、统计、分析功能
**端点数量**: 13
**已使用端点**: 1
**未使用端点**: 12
**总使用次数**: 2

### ✅ 已使用的端点

#### GET /panels
**函数名**: list_panels
**描述**: 列出所有Panels
**总使用次数**: 2
**前端使用**:
- Unknown (frontend/src/pages/DataBrowser.tsx:19)
  - 函数: loadPanels
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/acrac/data/panels')...
- Unknown (frontend/src/pages/DataBrowser.tsx:19)
  - 函数: loadPanels
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/acrac/data/panels')...

### ❌ 未使用的端点

- **GET /statistics** (get_statistics)
  - 描述: 获取详细统计信息
  - 文件: backend/app/api/api_v1/endpoints/acrac_simple.py:49
- **GET /panels/{semantic_id}/topics** (get_topics_by_panel)
  - 描述: 获取Panel下的所有Topics
  - 文件: backend/app/api/api_v1/endpoints/acrac_simple.py:114
- **GET /topics/{semantic_id}/scenarios** (get_scenarios_by_topic)
  - 描述: 获取Topic下的所有临床场景
  - 文件: backend/app/api/api_v1/endpoints/acrac_simple.py:153
- **GET /procedures** (list_procedures)
  - 描述: 列出检查项目
  - 文件: backend/app/api/api_v1/endpoints/acrac_simple.py:205
- **GET /scenarios/{scenario_id}/recommendations** (get_recommendations_for_scenario)
  - 描述: 获取场景的所有推荐
  - 文件: backend/app/api/api_v1/endpoints/acrac_simple.py:245
- **GET /analytics/modality-distribution** (get_modality_distribution)
  - 描述: 获取检查方式分布
  - 文件: backend/app/api/api_v1/endpoints/acrac_simple.py:301
- **GET /analytics/rating-distribution** (get_rating_distribution)
  - 描述: 获取适宜性评分分布
  - 文件: backend/app/api/api_v1/endpoints/acrac_simple.py:321
- **GET /quick/high-rating-recommendations** (get_high_rating_recommendations)
  - 描述: 获取高评分推荐
  - 文件: backend/app/api/api_v1/endpoints/acrac_simple.py:343
- **GET /quick/procedures-by-modality/{modality}** (get_procedures_by_modality)
  - 描述: 按检查方式获取检查项目
  - 文件: backend/app/api/api_v1/endpoints/acrac_simple.py:394
- **GET /examples/complete-recommendation** (get_complete_recommendation_example)
  - 描述: 获取完整推荐示例
  - 文件: backend/app/api/api_v1/endpoints/acrac_simple.py:427
- **GET /search/procedures** (search_procedures_simple)
  - 描述: 简单的检查项目搜索
  - 文件: backend/app/api/api_v1/endpoints/acrac_simple.py:490
- **GET /search/recommendations** (search_recommendations_simple)
  - 描述: 简单的推荐搜索
  - 文件: backend/app/api/api_v1/endpoints/acrac_simple.py:538

## 🔧 RAGAS评测 (评测功能)

**模块描述**: RAGAS评测任务管理、数据上传、结果查询
**端点数量**: 14
**已使用端点**: 6
**未使用端点**: 8
**总使用次数**: 16

### ✅ 已使用的端点

#### POST /data/upload
**函数名**: upload_file
**描述**: 上传测试数据文件并解析保存到数据库
**总使用次数**: 2
**前端使用**:
- Unknown (frontend/src/pages/DataImport.tsx:19)
  - 函数: customRequest
  - 类型: axios
  - 上下文: const r = await api.post('/api/v1/admin/data/upload', form, { headers: { 'Content-Type': 'multipart/...
- Unknown (frontend/src/pages/DataImport.tsx:19)
  - 函数: customRequest
  - 类型: string_literal
  - 上下文: const r = await api.post('/api/v1/admin/data/upload', form, { headers: { 'Content-Type': 'multipart/...

#### GET /data/scenarios
**函数名**: list_clinical_scenarios
**描述**: 查询数据库中的临床场景数据
**总使用次数**: 2
**前端使用**:
- Unknown (frontend/src/pages/DataBrowser.tsx:35)
  - 函数: loadScenarios
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/acrac/data/scenarios/by-topic', { params: { topic_id: tid }})...
- Unknown (frontend/src/pages/DataBrowser.tsx:35)
  - 函数: loadScenarios
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/acrac/data/scenarios/by-topic', { params: { topic_id: tid }})...

#### POST /evaluate
**函数名**: start_evaluation
**描述**: 启动RAGAS评测任务 - 从数据库选择数据进行评测
**总使用次数**: 6
**前端使用**:
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:461)
  - 函数: unknown
  - 类型: axios
  - 上下文: const response = await api.post('/api/v1/ragas/evaluate', {...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:461)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: const response = await api.post('/api/v1/ragas/evaluate', {...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:559)
  - 函数: startRagasStatusPolling
  - 类型: axios_template
  - 上下文: const response = await api.get(`/api/v1/ragas/evaluate/${taskId}/status`)...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:575)
  - 函数: unknown
  - 类型: axios_template
  - 上下文: const resultsResponse = await api.get(`/api/v1/ragas/evaluate/${taskId}/results`)...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:615)
  - 函数: stopRagasEvaluation
  - 类型: axios_template
  - 上下文: await api.post(`/api/v1/ragas/evaluate/${ragasTaskId}/stop`)...
**后端使用**:
- 未知模块 (backend/test_ragas_api.py:41)
  - 函数: unknown
  - 类型: test
  - 异步: False

#### GET /history
**函数名**: get_evaluation_history
**描述**: 获取评测历史记录列表
**总使用次数**: 4
**前端使用**:
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:335)
  - 函数: loadHistoryData
  - 类型: axios
  - 上下文: const response = await api.get('/api/v1/ragas/history', {...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:335)
  - 函数: loadHistoryData
  - 类型: string_literal
  - 上下文: const response = await api.get('/api/v1/ragas/history', {...
**后端使用**:
- 未知模块 (backend/demo_excel_evaluation.py:108)
  - 函数: get_evaluation_history
  - 类型: string_literal
  - 异步: False
- 未知模块 (backend/demo_excel_evaluation.py:134)
  - 函数: get_task_results
  - 类型: string_literal
  - 异步: False

#### GET /history/{task_id}
**函数名**: get_history_detail
**描述**: 获取历史记录详情
**总使用次数**: 1
**后端使用**:
- 未知模块 (backend/demo_excel_evaluation.py:134)
  - 函数: get_task_results
  - 类型: string_literal
  - 异步: False

#### DELETE /history/{task_id}
**函数名**: delete_history_record
**描述**: 删除历史记录
**总使用次数**: 1
**后端使用**:
- 未知模块 (backend/demo_excel_evaluation.py:134)
  - 函数: get_task_results
  - 类型: string_literal
  - 异步: False

### ❌ 未使用的端点

- **POST /data/preprocess** (preprocess_data)
  - 描述: 预处理上传的数据文件
  - 文件: backend/app/api/api_v1/endpoints/ragas_api.py:299
- **GET /data/files** (list_uploaded_files)
  - 描述: 列出已上传的文件
  - 文件: backend/app/api/api_v1/endpoints/ragas_api.py:344
- **GET /data/batches** (list_upload_batches)
  - 描述: 查询上传批次列表
  - 文件: backend/app/api/api_v1/endpoints/ragas_api.py:421
- **DELETE /data/files/{file_id}** (delete_uploaded_file)
  - 描述: 删除上传的文件
  - 文件: backend/app/api/api_v1/endpoints/ragas_api.py:476
- **GET /evaluate/{task_id}/status** (get_task_status)
  - 描述: 获取评测任务状态
  - 文件: backend/app/api/api_v1/endpoints/ragas_api.py:691
- **GET /evaluate/{task_id}/results** (get_task_results)
  - 描述: 获取评测任务结果
  - 文件: backend/app/api/api_v1/endpoints/ragas_api.py:717
- **DELETE /evaluate/{task_id}** (cancel_task)
  - 描述: 取消评测任务
  - 文件: backend/app/api/api_v1/endpoints/ragas_api.py:805
- **GET /history/statistics** (get_evaluation_statistics)
  - 描述: 获取评测统计信息
  - 文件: backend/app/api/api_v1/endpoints/ragas_api.py:908

## 🔧 三种方法 (推荐方法)

**模块描述**: 向量检索、LLM分析、RAG混合推荐方法
**端点数量**: 4
**已使用端点**: 0
**未使用端点**: 4
**总使用次数**: 0

### ❌ 未使用的端点

- **POST /vector-method** (vector_method_recommendation)
  - 描述: 
  - 文件: backend/app/api/api_v1/endpoints/three_methods_api.py:53
- **POST /llm-method** (llm_method_recommendation)
  - 描述: 
  - 文件: backend/app/api/api_v1/endpoints/three_methods_api.py:118
- **POST /rag-method** (rag_method_recommendation)
  - 描述: 
  - 文件: backend/app/api/api_v1/endpoints/three_methods_api.py:181
- **POST /compare-all-methods** (compare_all_methods)
  - 描述: 
  - 文件: backend/app/api/api_v1/endpoints/three_methods_api.py:244

## 🔧 数据管理 (管理功能)

**模块描述**: 数据上传、导入、验证、模型配置
**端点数量**: 6
**已使用端点**: 6
**未使用端点**: 0
**总使用次数**: 23

### ✅ 已使用的端点

#### GET /validate
**函数名**: validate_data
**描述**: 
**总使用次数**: 4
**前端使用**:
- Unknown (frontend/src/pages/DataImport.tsx:53)
  - 函数: handleValidate
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/admin/data/validate')...
- Unknown (frontend/src/pages/DataImport.tsx:53)
  - 函数: handleValidate
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/admin/data/validate')...
- loadExample (frontend/src/pages/Tools.tsx:116)
  - 函数: loadVectorStatus
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/admin/data/validate')...
- loadExample (frontend/src/pages/Tools.tsx:116)
  - 函数: loadVectorStatus
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/admin/data/validate')...

#### POST /upload
**函数名**: upload_csv
**描述**: 
**总使用次数**: 7
**前端使用**:
- Unknown (frontend/src/pages/DataImport.tsx:19)
  - 函数: customRequest
  - 类型: axios
  - 上下文: const r = await api.post('/api/v1/admin/data/upload', form, { headers: { 'Content-Type': 'multipart/...
- Unknown (frontend/src/pages/DataImport.tsx:19)
  - 函数: customRequest
  - 类型: string_literal
  - 上下文: const r = await api.post('/api/v1/admin/data/upload', form, { headers: { 'Content-Type': 'multipart/...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:402)
  - 函数: unknown
  - 类型: axios
  - 上下文: const response = await api.post('/api/v1/acrac/excel-evaluation/upload-excel', formData, {...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:402)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: const response = await api.post('/api/v1/acrac/excel-evaluation/upload-excel', formData, {...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:475)
  - 函数: unknown
  - 类型: axios
  - 上下文: const response = await api.post('/api/v1/acrac/excel-evaluation/upload-excel', formData, {...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:475)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: const response = await api.post('/api/v1/acrac/excel-evaluation/upload-excel', formData, {...
**后端使用**:
- 未知模块 (backend/demo_excel_evaluation.py:44)
  - 函数: upload_excel_file
  - 类型: string_literal
  - 异步: False

#### POST /import
**函数名**: import_csv
**描述**: 
**总使用次数**: 2
**前端使用**:
- Unknown (frontend/src/pages/DataImport.tsx:34)
  - 函数: onFinish
  - 类型: axios
  - 上下文: const r = await api.post('/api/v1/admin/data/import', {...
- Unknown (frontend/src/pages/DataImport.tsx:34)
  - 函数: onFinish
  - 类型: string_literal
  - 上下文: const r = await api.post('/api/v1/admin/data/import', {...

#### GET /models/config
**函数名**: get_models_config
**描述**: 
**总使用次数**: 4
**前端使用**:
- Unknown (frontend/src/pages/ModelConfig.tsx:15)
  - 函数: load
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/admin/data/models/config')...
- Unknown (frontend/src/pages/ModelConfig.tsx:15)
  - 函数: load
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/admin/data/models/config')...
- Unknown (frontend/src/pages/ModelConfig.tsx:35)
  - 函数: save
  - 类型: axios
  - 上下文: const r = await api.post('/api/v1/admin/data/models/config', v)...
- Unknown (frontend/src/pages/ModelConfig.tsx:35)
  - 函数: save
  - 类型: string_literal
  - 上下文: const r = await api.post('/api/v1/admin/data/models/config', v)...

#### POST /models/config
**函数名**: set_models_config
**描述**: 
**总使用次数**: 4
**前端使用**:
- Unknown (frontend/src/pages/ModelConfig.tsx:15)
  - 函数: load
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/admin/data/models/config')...
- Unknown (frontend/src/pages/ModelConfig.tsx:15)
  - 函数: load
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/admin/data/models/config')...
- Unknown (frontend/src/pages/ModelConfig.tsx:35)
  - 函数: save
  - 类型: axios
  - 上下文: const r = await api.post('/api/v1/admin/data/models/config', v)...
- Unknown (frontend/src/pages/ModelConfig.tsx:35)
  - 函数: save
  - 类型: string_literal
  - 上下文: const r = await api.post('/api/v1/admin/data/models/config', v)...

#### POST /models/reload
**函数名**: reload_rag_service
**描述**: 
**总使用次数**: 2
**前端使用**:
- Unknown (frontend/src/pages/ModelConfig.tsx:51)
  - 函数: reloadSvc
  - 类型: axios
  - 上下文: await api.post('/api/v1/admin/data/models/reload')...
- Unknown (frontend/src/pages/ModelConfig.tsx:51)
  - 函数: reloadSvc
  - 类型: string_literal
  - 上下文: await api.post('/api/v1/admin/data/models/reload')...

## 🔧 RAGAS评估 (评测功能)

**模块描述**: RAGAS评估执行、数据查询
**端点数量**: 4
**已使用端点**: 0
**未使用端点**: 4
**总使用次数**: 0

### ❌ 未使用的端点

- **POST /ragas-evaluate** (evaluate_ragas)
  - 描述: 执行RAGAS评估
  - 文件: backend/app/api/api_v1/endpoints/ragas_evaluation_api.py:421
- **GET /data/query** (query_evaluation_data)
  - 描述: 查询评测数据
  - 文件: backend/app/api/api_v1/endpoints/ragas_evaluation_api.py:475
- **POST /data/select-evaluate** (evaluate_selected_data)
  - 描述: 对选中的数据进行评测
  - 文件: backend/app/api/api_v1/endpoints/ragas_evaluation_api.py:524
- **GET /ragas-health** (ragas_health_check)
  - 描述: 
  - 文件: backend/app/api/api_v1/endpoints/ragas_evaluation_api.py:597

## 🔧 智能分析 (分析功能)

**模块描述**: 临床案例分析、方法比较
**端点数量**: 3
**已使用端点**: 0
**未使用端点**: 3
**总使用次数**: 0

### ❌ 未使用的端点

- **POST /analyze-case** (analyze_clinical_case)
  - 描述: 
  - 文件: backend/app/api/api_v1/endpoints/intelligent_analysis.py:61
- **POST /quick-analysis** (quick_clinical_analysis)
  - 描述: 
  - 文件: backend/app/api/api_v1/endpoints/intelligent_analysis.py:101
- **POST /compare-methods** (compare_recommendation_methods)
  - 描述: 
  - 文件: backend/app/api/api_v1/endpoints/intelligent_analysis.py:156

## 🔧 向量搜索 (搜索功能)

**模块描述**: 综合搜索、分类搜索、统计信息
**端点数量**: 7
**已使用端点**: 2
**未使用端点**: 5
**总使用次数**: 2

### ✅ 已使用的端点

#### POST /search/comprehensive
**函数名**: comprehensive_search
**描述**: 
**总使用次数**: 1
**后端使用**:
- 未知模块 (backend/tests/quick_test_demo.py:53)
  - 函数: test_vector_search_comprehensive
  - 类型: test
  - 异步: True

#### GET /stats
**函数名**: get_database_stats
**描述**: 获取数据库统计信息
**总使用次数**: 1
**后端使用**:
- 未知模块 (backend/tests/quick_test_demo.py:101)
  - 函数: test_database_stats
  - 类型: test
  - 异步: True

### ❌ 未使用的端点

- **POST /search/panels** (search_panels)
  - 描述: 搜索科室
  - 文件: backend/app/api/api_v1/endpoints/vector_search_api_v2.py:190
- **POST /search/topics** (search_topics)
  - 描述: 搜索主题
  - 文件: backend/app/api/api_v1/endpoints/vector_search_api_v2.py:208
- **POST /search/scenarios** (search_scenarios)
  - 描述: 搜索临床场景
  - 文件: backend/app/api/api_v1/endpoints/vector_search_api_v2.py:226
- **POST /search/procedures** (search_procedures)
  - 描述: 搜索检查项目
  - 文件: backend/app/api/api_v1/endpoints/vector_search_api_v2.py:244
- **POST /search/recommendations** (search_recommendations)
  - 描述: 搜索临床推荐
  - 文件: backend/app/api/api_v1/endpoints/vector_search_api_v2.py:262

## 🔧 数据浏览 (数据浏览)

**模块描述**: 分层数据浏览、列表查询
**端点数量**: 4
**已使用端点**: 4
**未使用端点**: 0
**总使用次数**: 8

### ✅ 已使用的端点

#### GET /topics/by-panel
**函数名**: list_topics_by_panel
**描述**: 
**总使用次数**: 2
**前端使用**:
- Unknown (frontend/src/pages/DataBrowser.tsx:27)
  - 函数: loadTopics
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/acrac/data/topics/by-panel', { params: { panel_id: pid }})...
- Unknown (frontend/src/pages/DataBrowser.tsx:27)
  - 函数: loadTopics
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/acrac/data/topics/by-panel', { params: { panel_id: pid }})...

#### GET /scenarios/by-topic
**函数名**: list_scenarios_by_topic
**描述**: 
**总使用次数**: 2
**前端使用**:
- Unknown (frontend/src/pages/DataBrowser.tsx:35)
  - 函数: loadScenarios
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/acrac/data/scenarios/by-topic', { params: { topic_id: tid }})...
- Unknown (frontend/src/pages/DataBrowser.tsx:35)
  - 函数: loadScenarios
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/acrac/data/scenarios/by-topic', { params: { topic_id: tid }})...

#### GET /scenarios
**函数名**: list_scenarios
**描述**: 
**总使用次数**: 2
**前端使用**:
- Unknown (frontend/src/pages/DataBrowser.tsx:35)
  - 函数: loadScenarios
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/acrac/data/scenarios/by-topic', { params: { topic_id: tid }})...
- Unknown (frontend/src/pages/DataBrowser.tsx:35)
  - 函数: loadScenarios
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/acrac/data/scenarios/by-topic', { params: { topic_id: tid }})...

#### GET /recommendations
**函数名**: list_recommendations
**描述**: 
**总使用次数**: 2
**前端使用**:
- Unknown (frontend/src/pages/DataBrowser.tsx:43)
  - 函数: loadRecs
  - 类型: axios
  - 上下文: const r = await api.get('/api/v1/acrac/data/recommendations', { params: { scenario_id: sid, page: 1,...
- Unknown (frontend/src/pages/DataBrowser.tsx:43)
  - 函数: loadRecs
  - 类型: string_literal
  - 上下文: const r = await api.get('/api/v1/acrac/data/recommendations', { params: { scenario_id: sid, page: 1,...

## 🔧 数据统计 (统计功能)

**模块描述**: 数据导入统计信息
**端点数量**: 1
**已使用端点**: 0
**未使用端点**: 1
**总使用次数**: 0

### ❌ 未使用的端点

- **GET /import-stats** (get_import_stats)
  - 描述: 获取数据导入统计信息
  - 文件: backend/app/api/api_v1/endpoints/data_stats.py:8

## 🔧 Excel评测 (评测功能)

**模块描述**: Excel文件上传、批量评测、结果导出
**端点数量**: 8
**已使用端点**: 7
**未使用端点**: 1
**总使用次数**: 17

### ✅ 已使用的端点

#### POST /upload-excel
**函数名**: upload_excel_file
**描述**: 上传Excel文件并解析
**总使用次数**: 5
**前端使用**:
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:402)
  - 函数: unknown
  - 类型: axios
  - 上下文: const response = await api.post('/api/v1/acrac/excel-evaluation/upload-excel', formData, {...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:402)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: const response = await api.post('/api/v1/acrac/excel-evaluation/upload-excel', formData, {...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:475)
  - 函数: unknown
  - 类型: axios
  - 上下文: const response = await api.post('/api/v1/acrac/excel-evaluation/upload-excel', formData, {...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:475)
  - 函数: unknown
  - 类型: string_literal
  - 上下文: const response = await api.post('/api/v1/acrac/excel-evaluation/upload-excel', formData, {...
**后端使用**:
- 未知模块 (backend/demo_excel_evaluation.py:44)
  - 函数: upload_excel_file
  - 类型: string_literal
  - 异步: False

#### POST /start-evaluation
**函数名**: start_evaluation
**描述**: 开始批量评测
**总使用次数**: 2
**前端使用**:
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:640)
  - 函数: startExcelEvaluation
  - 类型: string_literal
  - 上下文: '/api/v1/acrac/excel-evaluation/start-evaluation',...
**后端使用**:
- 未知模块 (backend/demo_excel_evaluation.py:67)
  - 函数: start_evaluation
  - 类型: string_literal
  - 异步: False

#### GET /evaluation-status
**函数名**: get_evaluation_status
**描述**: 获取评测状态
**总使用次数**: 3
**前端使用**:
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:660)
  - 函数: startExcelStatusPolling
  - 类型: axios
  - 上下文: const response = await api.get('/api/v1/acrac/excel-evaluation/evaluation-status')...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:660)
  - 函数: startExcelStatusPolling
  - 类型: string_literal
  - 上下文: const response = await api.get('/api/v1/acrac/excel-evaluation/evaluation-status')...
**后端使用**:
- 未知模块 (backend/demo_excel_evaluation.py:90)
  - 函数: check_evaluation_status
  - 类型: string_literal
  - 异步: False

#### POST /stop-evaluation
**函数名**: stop_evaluation
**描述**: 停止评测
**总使用次数**: 2
**前端使用**:
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:685)
  - 函数: stopExcelEvaluation
  - 类型: axios
  - 上下文: await api.post('/api/v1/acrac/excel-evaluation/stop-evaluation')...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:685)
  - 函数: stopExcelEvaluation
  - 类型: string_literal
  - 上下文: await api.post('/api/v1/acrac/excel-evaluation/stop-evaluation')...

#### POST /export-results
**函数名**: export_results
**描述**: 导出评测结果
**总使用次数**: 2
**前端使用**:
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:700)
  - 函数: exportExcelResults
  - 类型: axios
  - 上下文: const response = await api.post('/api/v1/acrac/excel-evaluation/export-results')...
- getCombinedRagasItems (frontend/src/pages/RAGEvaluation.tsx:700)
  - 函数: exportExcelResults
  - 类型: string_literal
  - 上下文: const response = await api.post('/api/v1/acrac/excel-evaluation/export-results')...

#### GET /evaluation-history
**函数名**: get_evaluation_history
**描述**: 获取Excel评测历史数据
**总使用次数**: 2
**后端使用**:
- 未知模块 (backend/demo_excel_evaluation.py:108)
  - 函数: get_evaluation_history
  - 类型: string_literal
  - 异步: False
- 未知模块 (backend/demo_excel_evaluation.py:134)
  - 函数: get_task_results
  - 类型: string_literal
  - 异步: False

#### GET /evaluation-history/{task_id}
**函数名**: get_evaluation_by_task_id
**描述**: 根据任务ID获取评测数据
**总使用次数**: 1
**后端使用**:
- 未知模块 (backend/demo_excel_evaluation.py:134)
  - 函数: get_task_results
  - 类型: string_literal
  - 异步: False

### ❌ 未使用的端点

- **GET /evaluation-results** (get_evaluation_results)
  - 描述: 获取评测结果
  - 文件: backend/app/api/api_v1/endpoints/excel_evaluation_api.py:365
