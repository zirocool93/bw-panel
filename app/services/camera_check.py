import shutil
import subprocess
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Camera


def check_rtsp_url(rtsp_url: str) -> tuple[bool, str]:
    if not shutil.which("ffprobe"):
        return False, "ffprobe не установлен; TODO: подключить проверку RTSP в контейнере"
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-rtsp_transport", "tcp", "-i", rtsp_url, "-show_streams"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "таймаут проверки RTSP"
    if result.returncode == 0:
        return True, "online"
    return False, result.stderr.strip() or "offline"


def update_camera_status(db: Session, camera: Camera) -> Camera:
    ok, message = check_rtsp_url(camera.rtsp_url)
    camera.last_status = "online" if ok else message[:60]
    camera.last_checked_at = datetime.now(UTC)
    db.commit()
    db.refresh(camera)
    return camera
