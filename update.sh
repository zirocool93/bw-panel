#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/bowling-portal}"
cd "$PROJECT_DIR"

if [ -d .git ]; then
  git pull --ff-only
fi

[ -f .env ] || cp .env.example .env
docker compose build
docker compose up -d
docker compose exec -T app alembic upgrade head
docker image prune -f
docker compose ps
