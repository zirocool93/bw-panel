from secrets import token_urlsafe
from base64 import b64encode
from urllib.parse import urlparse

import httpx

from app.config import get_settings


class OmeService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_stream_name(self, prefix: str, entity_id: int | None = None) -> str:
        suffix = entity_id if entity_id else token_urlsafe(6)
        return f"{prefix}_{suffix}".replace("-", "_")

    def playback_url(self, app_name: str, stream_name: str, playback_type: str = "hls") -> str:
        suffix = "llhls.m3u8" if playback_type == "ll_hls" else "playlist.m3u8"
        base = self.settings.nginx_hls_base_url.rstrip("/")
        return f"{base}/{app_name}/{stream_name}/{suffix}"

    def obs_ingest_url(self, stream_key: str, protocol: str = "rtmp") -> str:
        if protocol != "rtmp":
            return f"{protocol}://TODO-configure-ingest/{stream_key}"
        return f"{self.settings.ome_rtmp_base_url.rstrip('/')}/{stream_key}"

    def api_headers(self) -> dict[str, str]:
        if not self.settings.ome_api_access_token:
            return {}
        token = b64encode(self.settings.ome_api_access_token.encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {token}"}

    async def check_status(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(f"{self.settings.ome_api_url.rstrip('/')}/v1", headers=self.api_headers())
            if response.status_code in {200, 204, 404}:
                return True, f"API доступен, HTTP {response.status_code}"
            if response.status_code in {401, 403}:
                return False, f"API отвечает, но токен доступа неверный: HTTP {response.status_code}"
            return response.status_code < 500, f"HTTP {response.status_code}"
        except Exception as exc:
            return False, str(exc)

    async def diagnostics(self) -> dict:
        ok, status = await self.check_status()
        public_base = urlparse(self.settings.public_base_url)
        host = public_base.hostname or "localhost"
        external_api_url = f"{public_base.scheme or 'http'}://{host}:8081/v1"
        username = ""
        password_hint = ""
        if ":" in self.settings.ome_api_access_token:
            username, password_hint = self.settings.ome_api_access_token.split(":", 1)
        return {
            "ok": ok,
            "status": status,
            "api_url": self.settings.ome_api_url,
            "external_api_url": external_api_url,
            "api_username": username,
            "api_password_hint": password_hint,
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
