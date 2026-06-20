import logging
import os
import subprocess
import time

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Camera

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("camera_restream")


def rtmp_url(stream_name: str) -> str:
    base = os.getenv("CAMERA_RESTREAM_RTMP_BASE_URL", "rtmp://ovenmediaengine:1935/app").rstrip("/")
    return f"{base}/{stream_name}"


def build_ffmpeg_command(camera: Camera) -> list[str]:
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-rtsp_transport",
        "tcp",
        "-i",
        camera.rtsp_url,
        "-an",
        "-c:v",
        "copy",
        "-f",
        "flv",
        rtmp_url(camera.ome_stream_name or f"camera_{camera.id}"),
    ]


def load_active_cameras() -> list[Camera]:
    with SessionLocal() as db:
        return list(
            db.scalars(
                select(Camera).where(
                    Camera.is_active.is_(True),
                    Camera.rtsp_url.is_not(None),
                    Camera.ome_stream_name.is_not(None),
                )
            ).all()
        )


def main() -> None:
    poll_seconds = int(os.getenv("CAMERA_RESTREAM_POLL_SECONDS", "10"))
    processes: dict[int, subprocess.Popen] = {}

    while True:
        active_cameras = {camera.id: camera for camera in load_active_cameras()}

        for camera_id, process in list(processes.items()):
            if camera_id not in active_cameras or process.poll() is not None:
                if process.poll() is None:
                    process.terminate()
                processes.pop(camera_id, None)

        for camera_id, camera in active_cameras.items():
            if camera_id in processes:
                continue
            command = build_ffmpeg_command(camera)
            logger.info("Запуск ретрансляции камеры %s в %s", camera.title, rtmp_url(camera.ome_stream_name or ""))
            processes[camera_id] = subprocess.Popen(command)

        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
