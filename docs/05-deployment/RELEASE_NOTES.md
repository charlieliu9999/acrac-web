ACRAC Release v1.1.0

Date: 2025-09-27

Highlights
- Performance: Reduced LLM prompt size and request time via JSON-output + max_tokens and optional reasoning toggles; DB pooling and embedding LRU cache.
- Evaluation: Added A/B script for reasoning on/off with automatic JSON+Markdown report.
- Docker: Unified backend healthcheck to `/health`, added `.dockerignore` for backend/frontend to speed builds; Compose healthchecks preserved.
- Cleanup: Ignored transient result files and large evaluation artifacts in `.gitignore`.

Changes
- Docker
  - backend/Dockerfile: healthcheck uses `/health`.
  - backend/.dockerignore, frontend/.dockerignore: new files to shrink images and speed builds.
- Repo hygiene
  - .gitignore: ignore `ab_test_show_reasoning_*.json`, `ragas_results_*.json`.
  - Docs: `docs/INFERENCE_SWITCHES.md` (switches overview), this release note.
- Backend
  - Version bump to 1.1.0 in `backend/app/core/config.py`.

Upgrade Notes
- Rebuild containers: `docker compose build --no-cache && docker compose up -d`.
- Ensure backend `.env.docker` includes production endpoints and keys; prefer `DOCKER_CONTEXT=true`, `SKIP_LOCAL_DOTENV=true`.

Validation
- Health: `curl http://localhost:8001/health` should return `{status: healthy}`.
- API Docs: http://localhost:8080/docs

Next
- Optional: implement dynamic reasoning strategy behind an env flag; map accuracy to `procedure_dictionary.semantic_id` for robust scoring; add minimal CI workflow.
