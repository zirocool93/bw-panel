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
    transcode = os.getenv("CAMERA_RESTREAM_TRANSCODE", "1") == "1"
    common = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-fflags",
        "+genpts",
        "-use_wallclock_as_timestamps",
        "1",
        "-rtsp_transport",
        "tcp",
        "-i",
        camera.rtsp_url,
        "-map",
        "0:v:0",
    ]
    output = [
        "-f",
        "flv",
        rtmp_url(camera.ome_stream_name or f"camera_{camera.id}"),
    ]
    if not transcode:
        return [
            *common,
            "-an",
            "-c:v",
            "copy",
            "-avoid_negative_ts",
            "make_zero",
            *output,
        ]
    return [
        *common,
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        os.getenv("CAMERA_RESTREAM_X264_PRESET", "veryfast"),
        "-tune",
        "zerolatency",
        "-profile:v",
        "main",
        "-pix_fmt",
        "yuv420p",
        "-vf",
        os.getenv("CAMERA_RESTREAM_VIDEO_FILTER", "scale='min(1920,iw)':-2"),
        "-r",
        os.getenv("CAMERA_RESTREAM_FPS", "20"),
        "-g",
        os.getenv("CAMERA_RESTREAM_GOP", "40"),
        "-keyint_min",
        os.getenv("CAMERA_RESTREAM_GOP", "40"),
        "-sc_threshold",
        "0",
        "-b:v",
        os.getenv("CAMERA_RESTREAM_VIDEO_BITRATE", "4500k"),
        "-maxrate",
        os.getenv("CAMERA_RESTREAM_VIDEO_MAXRATE", "5000k"),
        "-bufsize",
        os.getenv("CAMERA_RESTREAM_VIDEO_BUFSIZE", "9000k"),
        *output,
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
