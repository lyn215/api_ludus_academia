"""app/core/config.py"""
from functools import lru_cache
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # En producción (Render), se debe pasar como variable de entorno
    DATABASE_URL: str

    SUPABASE_URL: str
    SUPABASE_JWT_SECRET: str
    SUPABASE_ANON_KEY: str = ""

    MAX_SYNC_PAYLOAD_KB: int = 50
    INVITE_CODE_EXPIRY_HOURS: int = 24

    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]

    # app/core/config.py (Solo la parte del validador)

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def ensure_supabase_pooler_config(cls, v: str) -> str:
        if not v: return v
        if v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        parsed = urlparse(v)
        # Solo cambiamos host y puerto, eliminamos TODA la query string 
        # para que no haya conflictos de tipos (str vs int)
        new_netloc = parsed.netloc
        if "supabase.com" in new_netloc and "pooler" not in new_netloc:
            new_netloc = new_netloc.replace("supabase.com", "pooler.supabase.com")
        if ":5432" in new_netloc:
            new_netloc = new_netloc.replace(":5432", ":6543")
            
        # Devolvemos la URL sin parámetros (?...), los parámetros van en session.py
        return urlunparse(parsed._replace(netloc=new_netloc, query=""))

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
