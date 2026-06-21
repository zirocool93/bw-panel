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
    return f" Проверьте RTSP URL: для Hikvision обычно нужен {corrected}"


def check_rtsp_url(rtsp_url: str) -> tuple[bool, str]:
    if not shutil.which("ffprobe"):
        return False, "ffprobe не установлен в контейнере app"
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-rtsp_transport",
                "tcp",
                "-i",
                rtsp_url,
                "-show_entries",
                "stream=index,codec_type,codec_name,width,height",
                "-of",
                "compact=p=0:nk=0",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "таймаут проверки RTSP." + rtsp_url_hint(rtsp_url)
    if result.returncode == 0:
        details = "; ".join(line.strip() for line in result.stdout.splitlines() if line.strip())
        return True, f"online: {details}" if details else "online"
    return False, (result.stderr.strip() or "offline") + rtsp_url_hint(rtsp_url)


def update_camera_status(db: Session, camera: Camera) -> Camera:
    ok, message = check_rtsp_url(camera.rtsp_url)
    camera.last_status = message[:240] if ok else message[:240]
    camera.last_checked_at = datetime.now(UTC)
    db.commit()
    db.refresh(camera)
    return camera
