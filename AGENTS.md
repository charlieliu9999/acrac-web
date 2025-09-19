# Repository Guidelines

## Project Structure & Module Organization
Backend lives in `backend/app`: routes in `api/api_v1/`, service logic in `services/`, SQLAlchemy models in `models/`, and Pydantic schemas in `schemas/`. Jobs and data loaders sit in `backend/scripts/`; SQL migrations are tracked in `backend/migrations/`. The React client is in `frontend/src`: screens in `pages/`, HTTP client in `api/http.ts`, and shared config in `config.ts`. Top-level scripts (`start.sh`, `start-dev.sh`, `stop.sh`) coordinate services in `docker-compose.yml`. Project docs are under `docs/`.

## Build, Test, and Development Commands
- Start full stack: `./start.sh`.
- Manual dev: `docker-compose up -d postgres redis`; `cd backend && uvicorn app.main:app --reload --port 8000`; `cd frontend && npm install && npm run dev` (port 5173).
- Dependencies: `pip install -r backend/requirements.txt` and `npm install` (run on `package.json` changes).

## Coding Style & Naming Conventions
- Python: Black (88 cols, 4-space indent), `flake8`, `mypy`. Run: `cd backend && black app scripts tests && flake8 app && mypy app`.
- Naming: `snake_case` modules/functions; `PascalCase` classes and Pydantic models.
- Frontend: TypeScript strict, two-space indent; `PascalCase` components in `pages/`, `camelCase` utilities. Put runtime constants/base URLs in `frontend/src/config.ts`.

## Testing Guidelines
- Unit tests: `cd backend && pytest tests/unit`.
- Integration scenarios: `cd backend/tests && python run_all_tests.py` (ensure Postgres and FastAPI are running). 
- When behavior changes, attach `master_test_report*.json` or `test_execution.log` to your PR.

## Commit & Pull Request Guidelines
- Branch from `develop`; raise PRs back to `develop`.
- Use Chinese Conventional Commits, e.g., `feat: 新增向量搜索过滤条件`, `fix: 修复RAG评测报错`.
- PRs must include scope, linked issues, migration notes, exact test commands, UI screenshots for `frontend/src/pages` changes, and SQL migrations in `backend/migrations/` for DB changes.

## Environment & Secrets
- Copy `backend/acrac.env.example` to `.env` and set keys (e.g., `SILICONFLOW_API_KEY`). Never commit secrets.
- Align the frontend Axios base URL in `frontend/src/config.ts`.
- For shared environments, source secrets via Docker Compose overrides or `deployment/` files—avoid hardcoding.
