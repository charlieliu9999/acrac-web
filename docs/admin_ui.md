ACRAC Admin UI

Location: `frontend/admin`

Prereqs
- Node.js 18+

Install & Run
- cd frontend/admin
- npm install
- npm run dev
- Open http://localhost:5173

Configure Backend API
- Admin UI uses `VITE_API_BASE` (see `.env.development`). Default: `http://127.0.0.1:8001`.
- Backend already allows CORS for http://localhost:5173.

Pages
- RAG 助手: Run `/api/v1/acrac/rag-llm/intelligent-recommendation`, see recall/rerank/recs, rules audit, prompt length.
- 规则管理: Load/save rule packs via `/rules-packs`; toggle engine via `/rules-config`.
- 数据浏览: List scenarios/procedures/recommendations via `/acrac/data/*` endpoints.
- 工具箱: Vector search, rerank, LLM parse via `/acrac/tools/*` endpoints.

Notes
- For enforcement, switch off audit-only in the top toggles.
- If vector search returns low similarity, service may run in no-RAG mode; adjust threshold in RAG 助手.

