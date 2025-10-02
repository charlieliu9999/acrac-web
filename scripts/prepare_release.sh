#!/usr/bin/env bash
set -euo pipefail

echo "[release] Clean transient files"
bash scripts/clean_worktree.sh || true

echo "[release] Lint basic repo state"
git status -s || true

echo "[release] Build docker images"
if command -v docker compose >/dev/null 2>&1; then
  docker compose build
else
  docker-compose build
fi

echo "[release] Done. Tag present?"
git describe --tags --abbrev=0 || echo "No tags yet"

