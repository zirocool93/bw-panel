import re
from urllib.parse import urlparse, urlsplit, urlunsplit
from secrets import token_urlsafe
from pathlib import Path

import httpx

from app.config import get_settings


def redact_url_credentials(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return value
    if not parts.scheme or "@" not in parts.netloc:
        return value
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    username = parts.username or ""
    auth = f"{username}:***@" if username else "***@"
    return urlunsplit((parts.scheme, f"{auth}{host}", parts.path, parts.query, parts.fragment))


def redact_sensitive(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key.lower() in {"password", "pass", "rtsp_password"}:
                result[key] = "***"
            elif isinstance(item, str):
                result[key] = redact_url_credentials(item)
            else:
                result[key] = redact_sensitive(item)
        return result
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str):
        return redact_url_credentials(value)
    return value


def redact_config_text(value: str) -> str:
    redacted = re.sub(r"(rtsp://[^:\s/@]+):([^@\s]+)@", r"\1:***@", value)
    return re.sub(r"(pass:\s*).+", r"\1***", redacted)


class OmeService:
    """Compatibility wrapper around the active MediaMTX backend.

    The class name is kept to avoid touching all routers in one migration step.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_stream_name(self, prefix: str, entity_id: int | None = None) -> str:
        suffix = entity_id if entity_id else token_urlsafe(6)
        return f"{prefix}_{suffix}".replace("-", "_")

    def effective_api_url(self) -> str:
        configured = self.settings.ome_api_url.rstrip("/")
        if "ovenmediaengine" in configured or configured.endswith(":8081"):
            return "http://mediamtx:9997"
        return configured

    def effective_hls_base_url(self) -> str:
        configured = self.settings.nginx_hls_base_url.rstrip("/")
        if "localhost" in configured:
            return "/hls"
        return configured

    def effective_rtmp_base_url(self) -> str:
        configured = self.settings.ome_rtmp_base_url.rstrip("/")
        if configured.endswith("/app"):
            configured = configured.removesuffix("/app")
        return configured

    def playback_url(self, app_name: str, stream_name: str, playback_type: str = "hls", base_url: str | None = None) -> str:
        base = (base_url or self.effective_hls_base_url()).rstrip("/")
        return f"{base}/{stream_name}/index.m3u8"

    def browser_playback_url(self, app_name: str, stream_name: str, request_base_url: str) -> str:
        hls_base = f"{request_base_url.rstrip('/')}/hls"
        return self.playback_url(app_name, stream_name, base_url=hls_base)

    def obs_ingest_url(self, stream_key: str, protocol: str = "rtmp") -> str:
        if protocol != "rtmp":
            return f"{protocol}://TODO-configure-ingest/{stream_key}"
        return f"{self.effective_rtmp_base_url()}/{stream_key}"

    async def check_status(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=3, follow_redirects=True) as client:
                response = await client.get(f"{self.effective_api_url()}/v3/config/global/get")
            if response.status_code == 200:
                return True, "MediaMTX API доступен"
            if response.status_code in {401, 403}:
                return False, f"MediaMTX API отвечает HTTP {response.status_code}, но доступ из панели не разрешен"
            return response.status_code < 500, f"MediaMTX API HTTP {response.status_code}"
        except Exception as exc:
            return False, str(exc)

    async def api_json(self, path: str) -> tuple[dict | None, str | None]:
        try:
            async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
                response = await client.get(f"{self.effective_api_url()}{path}")
            if response.status_code >= 400:
                return None, f"HTTP {response.status_code}: {response.text[:500]}"
            return redact_sensitive(response.json()), None
        except Exception as exc:
            return None, str(exc)

    async def config_paths(self) -> tuple[dict | None, str | None]:
        return await self.api_json("/v3/config/paths/list")

    async def active_paths(self) -> tuple[dict | None, str | None]:
        return await self.api_json("/v3/paths/list")

    async def hls_muxers(self) -> tuple[dict | None, str | None]:
        return await self.api_json("/v3/hlsmuxers/list")

    async def rtmp_connections(self) -> tuple[dict | None, str | None]:
        return await self.api_json("/v3/rtmpconns/list")

    async def rtsp_sessions(self) -> tuple[dict | None, str | None]:
        return await self.api_json("/v3/rtspsessions/list")

    def path_diagnostics(self, active_paths: dict | None) -> list[dict]:
        result = []
        for item in (active_paths or {}).get("items", []):
            name = item.get("name") or "unknown"
            ready = bool(item.get("ready"))
            available = bool(item.get("available"))
            tracks = item.get("tracks") or item.get("tracks2") or []
            if ready and tracks:
                status = "Готов к воспроизведению"
                level = "success"
            elif item.get("online") and not tracks:
                status = "Path создан, но MediaMTX не получил видеодорожки с RTSP-источника"
                level = "warning"
            else:
                status = "Path не активен"
                level = "danger"
            result.append(
                {
                    "name": name,
                    "ready": ready,
                    "available": available,
                    "tracks": len(tracks),
                    "status": status,
                    "level": level,
                }
            )
        return result

    def config_text(self) -> tuple[str, str | None]:
        path = Path("/mediamtx-config/mediamtx.yml")
        try:
            return redact_config_text(path.read_text(encoding="utf-8")), None
        except Exception as exc:
            return "", str(exc)

    async def diagnostics(self, request_base_url: str | None = None) -> dict:
        ok, status = await self.check_status()
        public_base = urlparse(request_base_url or self.settings.public_base_url)
        host = public_base.hostname or "localhost"
        scheme = public_base.scheme or "http"
        external_api_url = "http://127.0.0.1:9997 (только на сервере)"
        external_rtmp_url = self.effective_rtmp_base_url()
        if "localhost" in external_rtmp_url:
            external_rtmp_url = f"rtmp://{host}:1935"
        hls_base_url = self.effective_hls_base_url()
        if hls_base_url.startswith("/"):
            hls_base_url = f"{scheme}://{host}{hls_base_url}"
        return {
            "ok": ok,
            "status": status,
            "api_url": self.effective_api_url(),
            "external_api_url": external_api_url,
            "rtmp_url": external_rtmp_url,
            "hls_base_url": hls_base_url,
        }

    async def check_stream(self, playback_url: str | None) -> tuple[bool, str]:
        if not playback_url:
            return False, "URL не задан"
        try:
            async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
                response = await client.get(playback_url)
            final_url = str(response.url)
            body = response.text[:300].strip()
            if response.status_code == 200 and "#EXTM3U" in body:
                return True, f"HTTP 200, HLS playlist получен: {final_url}"
            detail = response.text[:300].strip()
            if final_url != playback_url:
                return False, f"HTTP {response.status_code} после редиректа на {final_url}: {detail}"
            return False, f"HTTP {response.status_code}: {detail}"
        except Exception as exc:
            return False, str(exc)
