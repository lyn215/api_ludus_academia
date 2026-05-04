"""app/core/config.py"""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:Dez6XRXwOiHFHo7A"
        "@db.bbyhevcprqxntsaknwul.supabase.co:5432/postgres"
    )

    SUPABASE_URL: str
    SUPABASE_JWT_SECRET: str
    SUPABASE_ANON_KEY: str = ""

    MAX_SYNC_PAYLOAD_KB: int = 50
    INVITE_CODE_EXPIRY_HOURS: int = 24

    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v: object) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json
                return json.loads(v)
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
