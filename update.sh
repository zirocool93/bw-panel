#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/bowling-portal}"
cd "$PROJECT_DIR"

set_env_value() {
  key="$1"
  value="$2"
  tmp_file="$(mktemp)"
  awk -v key="$key" -v value="$value" '
    BEGIN { written = 0 }
    $0 ~ "^" key "=" { print key "=" value; written = 1; next }
    { print }
    END { if (!written) print key "=" value }
  ' .env > "$tmp_file"
  mv "$tmp_file" .env
}

migrate_media_env() {
  server_ip="${SERVER_IP:-$(hostname -I | awk '{print $1}')}"
  [ -n "$server_ip" ] || server_ip="127.0.0.1"

  current_api_url="$(grep -E '^OME_API_URL=' .env | cut -d= -f2- || true)"
  current_rtmp_base="$(grep -E '^OME_RTMP_BASE_URL=' .env | cut -d= -f2- || true)"
  current_hls_base="$(grep -E '^NGINX_HLS_BASE_URL=' .env | cut -d= -f2- || true)"
  current_public_base="$(grep -E '^PUBLIC_BASE_URL=' .env | cut -d= -f2- || true)"

  if [ -z "$current_api_url" ] || echo "$current_api_url" | grep -Eq "ovenmediaengine|:8081"; then
    set_env_value OME_API_URL "http://mediamtx:9997"
  fi
  if [ -z "$current_rtmp_base" ] || echo "$current_rtmp_base" | grep -Eq "localhost|/app$"; then
    set_env_value OME_RTMP_BASE_URL "rtmp://${server_ip}:1935"
  fi
  if [ -z "$current_hls_base" ] || echo "$current_hls_base" | grep -q "localhost"; then
    set_env_value NGINX_HLS_BASE_URL "http://${server_ip}/hls"
  fi
  if [ -z "$current_public_base" ] || echo "$current_public_base" | grep -q "localhost"; then
    set_env_value PUBLIC_BASE_URL "http://${server_ip}"
  fi
}

if [ -d .git ]; then
  git pull --ff-only
fi

[ -f .env ] || cp .env.example .env
migrate_media_env
docker compose build
docker compose up -d --remove-orphans
docker compose restart nginx
docker compose exec -T app alembic upgrade head
docker image prune -f
docker compose ps
