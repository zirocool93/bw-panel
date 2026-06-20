#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${TARGET_DIR:-/opt/bowling-portal}"
REPO_URL="${REPO_URL:-https://github.com/zirocool93/bw-panel.git}"

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

prompt_admin_credentials() {
  if [ "${ADMIN_PROMPT:-1}" = "0" ]; then
    return
  fi

  if [ -t 0 ]; then
    current_username="$(grep -E '^ADMIN_USERNAME=' .env | cut -d= -f2- || true)"
    current_email="$(grep -E '^ADMIN_EMAIL=' .env | cut -d= -f2- || true)"
    current_password="$(grep -E '^ADMIN_PASSWORD=' .env | cut -d= -f2- || true)"

    read -r -p "Логин первого администратора [${current_username:-admin}]: " admin_username
    read -r -p "Email первого администратора [${current_email:-admin@example.com}]: " admin_email
    read -r -s -p "Пароль первого администратора [оставить текущий из .env]: " admin_password
    echo

    admin_username="${admin_username:-${current_username:-admin}}"
    admin_email="${admin_email:-${current_email:-admin@example.com}}"
    admin_password="${admin_password:-${current_password:-admin12345}}"

    set_env_value ADMIN_USERNAME "$admin_username"
    set_env_value ADMIN_EMAIL "$admin_email"
    set_env_value ADMIN_PASSWORD "$admin_password"
  else
    set_env_value ADMIN_USERNAME "${ADMIN_USERNAME:-admin}"
    set_env_value ADMIN_EMAIL "${ADMIN_EMAIL:-admin@example.com}"
    set_env_value ADMIN_PASSWORD "${ADMIN_PASSWORD:-admin12345}"
  fi
}

check_ome() {
  echo "Проверка OvenMediaEngine..."
  if ! docker compose ps ovenmediaengine | grep -qi "running\|up"; then
    echo "Контейнер OvenMediaEngine не запущен. Проверьте: docker compose logs ovenmediaengine"
    return 1
  fi

  if docker compose exec -T app python - <<'PY'
import asyncio
from app.services.ome import OmeService

async def main():
    ok, status = await OmeService().check_status()
    print(status)
    raise SystemExit(0 if ok else 1)

asyncio.run(main())
PY
  then
    echo "OvenMediaEngine доступен."
  else
    echo "OvenMediaEngine запущен, но API/status endpoint не ответил штатно."
    echo "Это может быть нормально для текущей конфигурации OME; проверьте логи при проблемах с трансляциями."
  fi
}

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
prompt_admin_credentials
mkdir -p media/archive logs
docker compose build
docker compose up -d
docker compose exec -T app alembic upgrade head
docker compose exec -T app python -m scripts.create_admin
check_ome

echo "Публичный сайт: http://$(hostname -I | awk '{print $1}')/"
echo "Админка: http://$(hostname -I | awk '{print $1}')/admin"
