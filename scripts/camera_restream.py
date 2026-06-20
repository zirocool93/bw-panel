import logging
import os
import subprocess
import time

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.models import Camera, SystemSetting

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("camera_restream")


DEFAULT_RESTREAM_SETTINGS = {
    "camera_restream_transcode": os.getenv("CAMERA_RESTREAM_TRANSCODE", "0"),
    "camera_restream_video_filter": os.getenv("CAMERA_RESTREAM_VIDEO_FILTER", "scale='min(1920,iw)':-2"),
    "camera_restream_video_bitrate": os.getenv("CAMERA_RESTREAM_VIDEO_BITRATE", "4500k"),
    "camera_restream_video_maxrate": os.getenv("CAMERA_RESTREAM_VIDEO_MAXRATE", "5000k"),
    "camera_restream_video_bufsize": os.getenv("CAMERA_RESTREAM_VIDEO_BUFSIZE", "9000k"),
    "camera_restream_fps": os.getenv("CAMERA_RESTREAM_FPS", "20"),
    "camera_restream_gop": os.getenv("CAMERA_RESTREAM_GOP", "40"),
    "camera_restream_x264_preset": os.getenv("CAMERA_RESTREAM_X264_PRESET", "veryfast"),
}


def as_enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "вкл"}


def rtmp_url(stream_name: str) -> str:
    base = os.getenv("CAMERA_RESTREAM_RTMP_BASE_URL", "rtmp://ovenmediaengine:1935/app").rstrip("/")
    return f"{base}/{stream_name}"


def build_ffmpeg_command(camera: Camera, settings: dict[str, str]) -> list[str]:
    transcode = as_enabled(settings.get("camera_restream_transcode"))
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
        settings["camera_restream_x264_preset"],
        "-tune",
        "zerolatency",
        "-profile:v",
        "main",
        "-pix_fmt",
        "yuv420p",
        "-vf",
        settings["camera_restream_video_filter"],
        "-r",
        settings["camera_restream_fps"],
        "-g",
        settings["camera_restream_gop"],
        "-keyint_min",
        settings["camera_restream_gop"],
        "-sc_threshold",
        "0",
        "-b:v",
        settings["camera_restream_video_bitrate"],
        "-maxrate",
        settings["camera_restream_video_maxrate"],
        "-bufsize",
        settings["camera_restream_video_bufsize"],
        *output,
    ]


def load_worker_state() -> tuple[list[Camera], dict[str, str]]:
    with SessionLocal() as db:
        cameras = list(
            db.scalars(
                select(Camera).where(
                    Camera.is_active.is_(True),
                    Camera.rtsp_url.is_not(None),
                    Camera.ome_stream_name.is_not(None),
                )
            ).all()
        )
        settings = DEFAULT_RESTREAM_SETTINGS.copy()
        for item in db.scalars(select(SystemSetting).where(SystemSetting.key.in_(settings.keys()))):
            if item.value not in {None, ""}:
                settings[item.key] = item.value
        return cameras, settings


def main() -> None:
    poll_seconds = int(os.getenv("CAMERA_RESTREAM_POLL_SECONDS", "10"))
    processes: dict[int, subprocess.Popen] = {}
    process_signatures: dict[int, tuple[str, ...]] = {}

    while True:
        try:
            cameras, settings = load_worker_state()
        except SQLAlchemyError as exc:
            logger.warning("БД еще не готова или миграции не применены: %s", exc)
            time.sleep(poll_seconds)
            continue

        active_cameras = {camera.id: camera for camera in cameras}

        for camera_id, process in list(processes.items()):
            if camera_id not in active_cameras or process.poll() is not None:
                if process.poll() is None:
                    process.terminate()
                processes.pop(camera_id, None)
                process_signatures.pop(camera_id, None)

        for camera_id, camera in active_cameras.items():
            command = build_ffmpeg_command(camera, settings)
            signature = tuple(command)
            if camera_id in processes and process_signatures.get(camera_id) == signature:
                continue
            if camera_id in processes:
                logger.info("Перезапуск ретрансляции камеры %s из-за изменения настроек", camera.title)
                processes[camera_id].terminate()
                processes.pop(camera_id, None)
            logger.info(
                "Запуск ретрансляции камеры %s в %s, перекодирование=%s",
                camera.title,
                rtmp_url(camera.ome_stream_name or ""),
                "вкл" if as_enabled(settings.get("camera_restream_transcode")) else "выкл",
            )
            processes[camera_id] = subprocess.Popen(command)
            process_signatures[camera_id] = signature

        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
