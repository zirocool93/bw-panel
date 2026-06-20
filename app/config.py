from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Портал трансляций боулинг-клуба"
    environment: str = "local"
    secret_key: str = Field(default="change-me-in-production")
    database_url: str = "postgresql+psycopg://bowling:bowling@postgres:5432/bowling"
    public_base_url: str = "http://localhost"
    nginx_hls_base_url: str = "http://localhost/hls"
    ome_rtmp_base_url: str = "rtmp://localhost:1935/app"
    ome_api_url: str = "http://ovenmediaengine:8081"
    ome_api_access_token: str = ""
    default_archive_depth_days: int = 14
    default_playback_type: str = "hls"
    archive_root: str = "/opt/bowling-portal/media/archive"
    session_cookie_name: str = "bowling_session"
    access_token_ttl_seconds: int = 900


@lru_cache
def get_settings() -> Settings:
    return Settings()
