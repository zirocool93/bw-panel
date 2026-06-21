# Портал трансляций боулинг-клуба

FastAPI-портал для публикации трансляций турниров боулинг-клуба. MVP включает админку, CRUD камер, OBS-входов, турниров и потоков, публичные страницы, HLS-плеер через hls.js, режимы доступа `public`, `token`, `password`, Docker Compose, Nginx, PostgreSQL и интеграцию с MediaMTX.

## Архитектура

MediaMTX тянет RTSP-потоки камер Hikvision по path и принимает RTMP-публикации от OBS. Портал хранит метаданные турниров и источников, формирует playback URL, а зрителям отдает страницы с HTML5-плеером. RTSP-адреса камер не выводятся в публичную часть.

## Установка

```bash
cp .env.example .env
docker compose build
docker compose up -d
docker compose exec app alembic upgrade head
docker compose exec app python -m scripts.create_admin
```

После запуска откройте `/admin`. Данные первого администратора берутся из `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`.

## Установка на сервер

```bash
curl -fsSL https://raw.githubusercontent.com/zirocool93/bw-panel/main/install.sh -o install.sh
sudo bash install.sh
```

Скрипт проверяет Ubuntu/Debian, ставит Docker, создает `/opt/bowling-portal`, спрашивает логин, email и пароль первого администратора, поднимает контейнеры, применяет миграции, создает администратора и проверяет контейнер MediaMTX. Для Proxmox LXC обычно нужны включенные `nesting` и `keyctl`.

Для автоматической установки без вопросов можно передать переменные:

```bash
sudo ADMIN_PROMPT=0 ADMIN_USERNAME=admin ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD='strong-password' bash install.sh
```

## MediaMTX

MediaMTX устанавливается как сервис `mediamtx` в `docker-compose.yml`. В админке есть раздел `/admin/ome`, где можно:

- проверить статус MediaMTX;
- увидеть RTMP URL для OBS и HLS base URL;
- посмотреть stream key для OBS-входов;
- посмотреть MediaMTX paths для камер;
- посмотреть текущий `mediamtx.yml`, активные paths, HLS muxers, RTMP-подключения и RTSP-сессии для диагностики 404;
- проверить playback URL всех трансляций;
- перегенерировать ingest/playback URL после изменения `.env`.

MediaMTX API включен на порту `9997` внутри Docker и привязан к `127.0.0.1` на сервере. Конфиг paths автоматически генерирует сервис `mediamtx-configurator` из камер и OBS-входов в БД. HLS доступен через Nginx по `/hls/{path}/index.m3u8`.

## Логи в админке

Раздел `/admin/logs` показывает хвост логов разрешенных Docker Compose сервисов: `app`, `nginx`, `mediamtx`, `mediamtx-configurator`, `postgres`. Для этого контейнер `app` монтирует Docker socket только на чтение. Доступ к разделу закрыт авторизацией админки.

При установке `install.sh` автоматически заменяет `localhost` в `.env` на IP сервера для `PUBLIC_BASE_URL`, `NGINX_HLS_BASE_URL` и `OME_RTMP_BASE_URL`. Если нужно указать адрес вручную:

```bash
sudo SERVER_IP=10.5.2.43 bash install.sh
```

## Обновление

```bash
sudo PROJECT_DIR=/opt/bowling-portal bash update.sh
```

Скрипт выполняет `git pull`, пересобирает контейнеры, применяет миграции и показывает статус сервисов.

После перехода с OvenMediaEngine на MediaMTX можно выполнить вручную:

```bash
cd /opt/bowling-portal
sudo git pull
sudo docker compose build
sudo docker compose up -d --remove-orphans
```

Старые контейнеры `ovenmediaengine` и `camera-worker` будут удалены как orphan-сервисы.

## Настройка `.env`

Главные параметры: `SECRET_KEY`, `DATABASE_URL`, `PUBLIC_BASE_URL`, `NGINX_HLS_BASE_URL`, `OME_RTMP_BASE_URL`, `OME_API_URL`, `POSTGRES_PASSWORD`. Секреты нельзя коммитить в репозиторий.

## Рабочий процесс

1. В админке добавьте камеры с RTSP URL. Система передает RTSP URL в MediaMTX как есть и подходит для любых камер/регистраторов, которые отдают стандартный RTSP-поток. Для каждой камеры можно выбрать RTSP transport: `Авто (TCP)`, `TCP` или `UDP`. Пароль камеры после сохранения не показывается в форме. Сервис `mediamtx-configurator` автоматически добавит активные камеры в paths MediaMTX.
2. Добавьте OBS-вход. Админка покажет server URL и stream key для OBS.
3. Создайте турнир, выберите статус, публичность и режим доступа.
4. В карточке турнира добавьте трансляции: камера, OBS или внешний HLS.
5. Откройте публичную страницу `/tournaments/{slug}`.

## Архив

В MVP создана таблица `archive_recordings` и скрипт `scripts/cleanup_archive.py`. Полноценная запись средствами OME подключается следующим этапом.

## Защита трансляций

`public` открывает страницу всем, `token` генерирует временный токен при выдаче playback URL, `password` требует пароль турнира и сохраняет доступ в сессии. Реальные RTSP URL не попадают в публичные шаблоны.

## Типовые проблемы

- Если сайт отвечает `502 Bad Gateway`, проверьте приложение:
  `docker compose ps app` и `docker compose logs --tail=200 app`.
- Если HLS не играет, проверьте `NGINX_HLS_BASE_URL`, порт `8888` MediaMTX и наличие активного path в `/admin/ome`.
- Если MediaMTX возвращает `no stream is available on path 'hls/camera_1'`, Nginx передал в MediaMTX лишний префикс `/hls`; обновите конфиг и пересоздайте `nginx`.
- Если камера добавлена, но не играет, откройте `/admin/ome`: `camera_1` должен быть в текущем `mediamtx.yml` и в конфигурации paths API. После нажатия «Проверить playback URL» смотрите `active paths`, `HLS muxers` и логи `mediamtx`.
- Если в диагнозе MediaMTX у path `ready=нет`, `available=нет`, `tracks=0`, MediaMTX не получил видеодорожку от RTSP-камеры. Проверьте RTSP URL из контейнера `app`, логин/пароль, доступность сети до камеры, выбранный RTSP transport и кодек камеры. Для некоторых Hikvision чаще нужен путь `/Streaming/Channels/101`, но система не переписывает URL автоматически и может работать с любым корректным RTSP URL.
- Если OBS не подключается, проверьте `OME_RTMP_BASE_URL` и проброс порта `1935`.
- Если проверка камеры пишет про `ffprobe`, убедитесь, что контейнер пересобран с установленным `ffmpeg`.
