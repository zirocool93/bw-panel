#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${TARGET_DIR:-/opt/bowling-portal}"
REPO_URL="${REPO_URL:-https://github.com/zirocool93/bw-panel.git}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Запустите установку от root: sudo bash install.sh"
  exit 1
fi

if ! grep -qiE "ubuntu|debian" /etc/os-release; then
  echo "Поддерживаются Ubuntu/Debian. Для Proxmox LXC включите nesting и keyctl."
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  apt-get update
  apt-get install -y git
fi

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ca-certificates curl gnupg git
  install -m 0755 -d /etc/apt/keyrings
  . /etc/os-release
  docker_os="$ID"
  curl -fsSL "https://download.docker.com/linux/${docker_os}/gpg" | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${docker_os} ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

if [ -d "$TARGET_DIR/.git" ]; then
  cd "$TARGET_DIR"
  git pull --ff-only
elif [ -n "$(find "$TARGET_DIR" -mindepth 1 -maxdepth 1 2>/dev/null || true)" ]; then
  echo "Директория $TARGET_DIR уже существует и не является git-репозиторием."
  echo "Очистите ее или задайте другой TARGET_DIR."
  exit 1
elif [ -n "$REPO_URL" ]; then
  mkdir -p "$(dirname "$TARGET_DIR")"
  git clone "$REPO_URL" "$TARGET_DIR"
else
  mkdir -p "$TARGET_DIR"
  cp -a . "$TARGET_DIR"
  cd "$TARGET_DIR"
fi

cd "$TARGET_DIR"
[ -f .env ] || cp .env.example .env
mkdir -p media/archive logs
docker compose build
docker compose up -d
docker compose exec -T app alembic upgrade head
docker compose exec -T app python scripts/create_admin.py

echo "Публичный сайт: http://$(hostname -I | awk '{print $1}')/"
echo "Админка: http://$(hostname -I | awk '{print $1}')/admin"
