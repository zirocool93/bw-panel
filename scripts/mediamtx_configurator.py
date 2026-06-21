import logging
import os
import tempfile
import time
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.models import Camera, ObsInput

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("mediamtx_configurator")

CONFIG_PATH = Path(os.getenv("MEDIAMTX_CONFIG_PATH", "/config/mediamtx.yml"))
POLL_SECONDS = int(os.getenv("MEDIAMTX_CONFIG_POLL_SECONDS", "10"))


def yaml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def camera_source_url(camera: Camera) -> str:
    if not camera.rtsp_username:
        return camera.rtsp_url
    parts = urlsplit(camera.rtsp_url)
    if "@" in parts.netloc:
        return camera.rtsp_url
    username = quote(camera.rtsp_username, safe="")
    password = quote(camera.rtsp_password or "", safe="")
    auth = f"{username}:{password}@" if password else f"{username}@"
    return urlunsplit((parts.scheme, f"{auth}{parts.netloc}", parts.path, parts.query, parts.fragment))


def base_config() -> list[str]:
    return [
        "logLevel: info",
        "logDestinations: [stdout]",
        "api: true",
        "apiAddress: :9997",
        "metrics: true",
        "metricsAddress: :9998",
        "rtsp: true",
        "rtspAddress: :8554",
        "rtspTransports: [tcp]",
        "rtmp: true",
        "rtmpAddress: :1935",
        "hls: true",
        "hlsAddress: :8888",
        "hlsAllowOrigins: ['*']",
        "hlsAlwaysRemux: false",
        "hlsVariant: lowLatency",
        "hlsSegmentCount: 7",
        "hlsSegmentDuration: 1s",
        "hlsPartDuration: 200ms",
        "webrtc: false",
        "srt: false",
        "paths:",
        "  all:",
        "    source: publisher",
    ]


def load_paths() -> list[str]:
    with SessionLocal() as db:
        cameras = db.scalars(select(Camera).where(Camera.is_active.is_(True), Camera.ome_stream_name.is_not(None))).all()
        obs_inputs = db.scalars(select(ObsInput).where(ObsInput.is_active.is_(True), ObsInput.ome_stream_name.is_not(None))).all()

        lines = base_config()
        for camera in cameras:
            if not camera.rtsp_url:
                continue
            source = camera_source_url(camera)
            lines.extend(
                [
                    f"  {camera.ome_stream_name}:",
                    f"    source: {yaml_string(source)}",
                    "    sourceOnDemand: true",
                    "    sourceOnDemandStartTimeout: 20s",
                    "    sourceOnDemandCloseAfter: 10s",
                    "    rtspTransport: tcp",
                ]
            )
        for obs_input in obs_inputs:
            lines.extend(
                [
                    f"  {obs_input.ome_stream_name}:",
                    "    source: publisher",
                ]
            )
        return lines


def write_if_changed(content: str) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    old = CONFIG_PATH.read_text(encoding="utf-8") if CONFIG_PATH.exists() else ""
    if old == content:
        return
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=CONFIG_PATH.parent, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    tmp_path.replace(CONFIG_PATH)
    logger.info("Конфигурация MediaMTX обновлена: %s", CONFIG_PATH)


def main() -> None:
    while True:
        try:
            write_if_changed("\n".join(load_paths()) + "\n")
        except SQLAlchemyError as exc:
            logger.warning("БД еще не готова или миграции не применены: %s", exc)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
