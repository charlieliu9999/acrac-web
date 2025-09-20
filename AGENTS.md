# Repository Guidelines

## Project Structure & Module Organization
- Backend (FastAPI) in `backend/app`: routes `api/api_v1/`, services `services/`, models `models/`, schemas `schemas/`, tasks `tasks/`.
- Jobs/scripts in `backend/scripts/`; DB migrations in `backend/migrations/`.
- Frontend (React + Vite) in `frontend/src`: pages `pages/`, HTTP client `api/http.ts`, config `config.ts`.
- Orchestration via `docker-compose.yml`; entry scripts: `start.sh`, `start-dev.sh`, `stop.sh`. Docs in `docs/`.

## Build, Test, and Development Commands
- Full stack: `./start.sh`.
- Manual dev: `docker-compose up -d postgres redis`; `cd backend && uvicorn app.main:app --reload --port 8000`; `cd frontend && npm install && npm run dev` (port 5173).
- Install deps: `pip install -r backend/requirements.txt`; `npm install` (rerun on `package.json` changes).

## Coding Style & Naming Conventions
- Python: Black (88 cols, 4‑space), Flake8, MyPy. Run: `cd backend && black app scripts tests && flake8 app && mypy app`.
- Naming: snake_case modules/functions; PascalCase classes and Pydantic models.
- Frontend: TypeScript strict, 2‑space indent; PascalCase components under `pages/`, camelCase utilities. Put env‑driven bases in `frontend/src/config.ts`.

## Testing Guidelines
- Unit: `cd backend && pytest tests/unit`.
- Integration: `cd backend/tests && python run_all_tests.py` (requires Postgres + FastAPI running).
- Attach `master_test_report*.json` or `test_execution.log` to PRs when behavior changes.

## Commit & Pull Request Guidelines
- Branch from `develop`; open PRs back to `develop`.
- Use Chinese Conventional Commits, e.g., `feat: 新增向量搜索过滤条件`, `fix: 修复RAG评测报错`.
- PRs include: scope, linked issues, migration notes, exact test commands, UI screenshots for `frontend/src/pages` changes, and SQL migrations in `backend/migrations/` for DB updates.

## Security & Configuration Tips
- Copy `backend/acrac.env.example` to `backend/.env`; set required keys (e.g., `SILICONFLOW_API_KEY`). Do not commit secrets.
- Keep Axios base URL aligned in `frontend/src/config.ts` per environment.
- Prefer Docker Compose overrides or files under `deployment/` for shared secrets and environment config.

## Architecture Overview
- FastAPI backend (port 8000), React/Vite frontend (5173), Postgres, and Redis coordinated by Docker Compose. Celery tasks live under `backend/app/tasks/` when used.
