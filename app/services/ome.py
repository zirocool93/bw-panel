from urllib.parse import urlparse
from secrets import token_urlsafe

import httpx

from app.config import get_settings


class OmeService:
    """Compatibility wrapper around the active MediaMTX backend.

    The class name is kept to avoid touching all routers in one migration step.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_stream_name(self, prefix: str, entity_id: int | None = None) -> str:
        suffix = entity_id if entity_id else token_urlsafe(6)
        return f"{prefix}_{suffix}".replace("-", "_")

    def playback_url(self, app_name: str, stream_name: str, playback_type: str = "hls", base_url: str | None = None) -> str:
        base = (base_url or self.settings.nginx_hls_base_url).rstrip("/")
        return f"{base}/{stream_name}/index.m3u8"

    def browser_playback_url(self, app_name: str, stream_name: str, request_base_url: str) -> str:
        hls_base = f"{request_base_url.rstrip('/')}/hls"
        return self.playback_url(app_name, stream_name, base_url=hls_base)

    def obs_ingest_url(self, stream_key: str, protocol: str = "rtmp") -> str:
        if protocol != "rtmp":
            return f"{protocol}://TODO-configure-ingest/{stream_key}"
        return f"{self.settings.ome_rtmp_base_url.rstrip('/')}/{stream_key}"

    async def check_status(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(f"{self.settings.ome_api_url.rstrip('/')}/v3/config/global/get")
            if response.status_code in {200, 401, 403, 404}:
                return True, f"MediaMTX API доступен, HTTP {response.status_code}"
            return response.status_code < 500, f"HTTP {response.status_code}"
        except Exception as exc:
            return False, str(exc)

    async def diagnostics(self) -> dict:
        ok, status = await self.check_status()
        public_base = urlparse(self.settings.public_base_url)
        host = public_base.hostname or "localhost"
        external_api_url = f"{public_base.scheme or 'http'}://{host}:9997"
        return {
            "ok": ok,
            "status": status,
            "api_url": self.settings.ome_api_url,
            "external_api_url": external_api_url,
            "rtmp_url": self.settings.ome_rtmp_base_url,
            "hls_base_url": self.settings.nginx_hls_base_url,
        }

    async def check_stream(self, playback_url: str | None) -> tuple[bool, str]:
        if not playback_url:
            return False, "URL не задан"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(playback_url)
            return response.status_code < 400, f"HTTP {response.status_code}"
        except Exception as exc:
            return False, str(exc)
