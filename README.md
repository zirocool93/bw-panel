# Портал трансляций боулинг-клуба

FastAPI-портал для публикации трансляций турниров боулинг-клуба. MVP включает админку, CRUD камер, OBS-входов, турниров и потоков, публичные страницы, HLS-плеер через hls.js, режимы доступа `public`, `token`, `password`, Docker Compose, Nginx, PostgreSQL и заготовку интеграции с OvenMediaEngine.

## Архитектура

Камеры Hikvision или OBS отправляют поток в OvenMediaEngine. Портал хранит метаданные турниров и источников, формирует playback URL, а зрителям отдает страницы с HTML5-плеером. RTSP-адреса камер не выводятся в публичную часть.

## Установка

```bash
cp .env.example .env
docker compose build
docker compose up -d
docker compose exec app alembic upgrade head
docker compose exec app python scripts/create_admin.py
```

После запуска откройте `/admin`. Данные первого администратора берутся из `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`.

## Установка на сервер

```bash
curl -fsSL https://raw.githubusercontent.com/zirocool93/bw-panel/main/install.sh -o install.sh
sudo bash install.sh
```

Скрипт проверяет Ubuntu/Debian, ставит Docker, создает `/opt/bowling-portal`, спрашивает логин, email и пароль первого администратора, поднимает контейнеры, применяет миграции, создает администратора и проверяет контейнер OvenMediaEngine. Для Proxmox LXC обычно нужны включенные `nesting` и `keyctl`.

Для автоматической установки без вопросов можно передать переменные:

```bash
sudo ADMIN_PROMPT=0 ADMIN_USERNAME=admin ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD='strong-password' bash install.sh
```

## OvenMediaEngine

OvenMediaEngine устанавливается как сервис `ovenmediaengine` в `docker-compose.yml`. В админке есть раздел `/admin/ome`, где можно:

- проверить статус OME;
- увидеть RTMP URL для OBS и HLS base URL;
- посмотреть stream key для OBS-входов;
- посмотреть OME stream names для камер;
- проверить playback URL всех трансляций;
- перегенерировать ingest/playback URL после изменения `.env`.

## Обновление

```bash
sudo PROJECT_DIR=/opt/bowling-portal bash update.sh
```

Скрипт выполняет `git pull`, пересобирает контейнеры, применяет миграции и показывает статус сервисов.

## Настройка `.env`

Главные параметры: `SECRET_KEY`, `DATABASE_URL`, `PUBLIC_BASE_URL`, `NGINX_HLS_BASE_URL`, `OME_RTMP_BASE_URL`, `OME_API_URL`, `POSTGRES_PASSWORD`. Секреты нельзя коммитить в репозиторий.

## Рабочий процесс

1. В админке добавьте камеры с RTSP URL. Пароль камеры после сохранения не показывается в форме.
2. Добавьте OBS-вход. Админка покажет server URL и stream key для OBS.
3. Создайте турнир, выберите статус, публичность и режим доступа.
4. В карточке турнира добавьте трансляции: камера, OBS или внешний HLS.
5. Откройте публичную страницу `/tournaments/{slug}`.

## Архив

В MVP создана таблица `archive_recordings` и скрипт `scripts/cleanup_archive.py`. Полноценная запись средствами OME подключается следующим этапом.

## Защита трансляций

`public` открывает страницу всем, `token` генерирует временный токен при выдаче playback URL, `password` требует пароль турнира и сохраняет доступ в сессии. Реальные RTSP URL не попадают в публичные шаблоны.

## Типовые проблемы

- Если HLS не играет, проверьте `NGINX_HLS_BASE_URL`, порт `3333` OME и наличие активного потока.
- Если OBS не подключается, проверьте `OME_RTMP_BASE_URL` и проброс порта `1935`.
- Если проверка камеры пишет про `ffprobe`, убедитесь, что контейнер пересобран с установленным `ffmpeg`.
