RAG+LLM Service Architecture (Refactor Plan)

Goals
- Keep existing /intelligent-recommendation stable;
- Modularize by responsibility; enable micro endpoints for reuse/testing;
- Add rules layer (already done) without breaking core flow.

Current Modules
- rag_llm_recommendation_service.py: orchestrates end-to-end
- rules_engine.py: optional rule hooks (rerank/post)

New Endpoints
- /api/v1/acrac/tools/rerank: expose rerank as a micro endpoint
- /api/v1/acrac/tools/llm/parse: parse raw LLM text into structured JSON
- /api/v1/acrac/tools/ragas/score: compute RAGAS metrics

Phase Refactor (Non-breaking)
- Phase 1 (done): introduce tools endpoints and rules engine hooks
- Phase 2: split rag_llm_recommendation_service into components under app/services/rag/
  - vector_search.py: DB connection + scenario/procedure retrieval
  - rerank.py: keyword config, target inference, rescoring + silicon reranker integration
  - prompt_builder.py: prompt construction with configurable truncation
  - llm_client.py: call_llm + parsing + schema validation
  - ragas_service.py: context building + RAGAS scoring
  Wiring: keep class facade delegating to components; imports remain inside service to avoid circular deps.
- Phase 3: independent workers (optional)
  - Move heavy/slow ops (RAGAS, external reranker) behind Celery tasks/queues
  - Provide status endpoints and async job IDs

Perf & Safety
- Database access kept in one place; connection errors gracefully degrade to no-RAG
- Configurable truncations to control prompt size; logs with preview/length
- Rules engine in audit-only mode for observation; explicit flag for enforcement

Testing Strategy
- Unit-level: component tests (rerank logic, parser validation)
- API-level: tools endpoints fixtures; snapshot-based expected outputs
- E2E: five-cases tracer + audit compare for data quality before/after

