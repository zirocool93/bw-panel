import shutil
import subprocess
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy.orm import Session

from app.models import Camera


def rtsp_url_hint(rtsp_url: str) -> str:
    if "/ISAPI/Streaming/Channels/" not in rtsp_url:
        return ""
    parts = urlsplit(rtsp_url)
    corrected_path = parts.path.replace("/ISAPI/Streaming/Channels/", "/Streaming/Channels/")
    corrected = urlunsplit((parts.scheme, parts.netloc, corrected_path, parts.query, parts.fragment))
    return f" Альтернативный путь для части Hikvision: {corrected}"


def ffprobe_rtsp(rtsp_url: str, rtsp_transport: str) -> tuple[bool, str]:
    command = ["ffprobe", "-v", "error"]
    if rtsp_transport in {"tcp", "udp"}:
        command.extend(["-rtsp_transport", rtsp_transport])
    command.extend(
        [
            "-i",
            rtsp_url,
            "-show_entries",
            "stream=index,codec_type,codec_name,width,height",
            "-of",
            "compact=p=0:nk=0",
        ]
    )
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
    except subprocess.TimeoutExpired:
        return False, f"таймаут проверки RTSP через {rtsp_transport}"
    if result.returncode != 0:
        return False, result.stderr.strip() or f"offline через {rtsp_transport}"

    details = "; ".join(line.strip() for line in result.stdout.splitlines() if line.strip())
    if "codec_type=video" not in result.stdout:
        return False, f"RTSP доступен через {rtsp_transport}, но видеодорожка не найдена: {details}"
    return True, details


def check_rtsp_url(rtsp_url: str, rtsp_transport: str = "automatic") -> tuple[bool, str, str]:
    if not shutil.which("ffprobe"):
        return False, "ffprobe не установлен в контейнере app", rtsp_transport

    transports = [rtsp_transport] if rtsp_transport in {"tcp", "udp"} else ["tcp", "udp", "automatic"]
    errors = []
    for transport in transports:
        ok, message = ffprobe_rtsp(rtsp_url, transport)
        if ok:
            selected = transport if transport in {"tcp", "udp"} else "automatic"
            return True, f"online через {selected}: {message}", selected
        errors.append(f"{transport}: {message}")

    return False, "offline. " + " | ".join(errors) + rtsp_url_hint(rtsp_url), rtsp_transport


def update_camera_status(db: Session, camera: Camera) -> Camera:
    ok, message, detected_transport = check_rtsp_url(camera.rtsp_url, camera.rtsp_transport)
    camera.last_status = message
    if ok and camera.rtsp_transport == "automatic" and detected_transport in {"tcp", "udp"}:
        camera.rtsp_transport = detected_transport
    camera.last_checked_at = datetime.now(UTC)
    db.commit()
    db.refresh(camera)
    return camera
