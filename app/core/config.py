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

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def ensure_supabase_pooler_config(cls, v: str) -> str:
        """
        Asegura configuración correcta para Supabase pooler (pgbouncer).
        - Puerto 6543 para pooler
        - statement_cache_size=0 para evitar prepared statements
        - sslmode=require para conexiones seguras
        """
        if not v or "pooler.supabase.com" not in v:
            # Si no es pooler, convertir a pooler
            if "supabase.com" in v and "pooler" not in v:
                v = v.replace("supabase.com", "pooler.supabase.com")
                # Cambiar puerto a 6543 si no lo es
                if ":5432/" in v:
                    v = v.replace(":5432/", ":6543/")
        
        # Asegurar parámetros de pgbouncer
        if "?" in v:
            # Ya tiene query params, agregar si no existen
            if "statement_cache_size" not in v:
                v += "&statement_cache_size=0"
            if "sslmode" not in v:
                v += "&sslmode=require"
        else:
            # No tiene query params, agregar
            v += "?statement_cache_size=0&sslmode=require"
        
        return v

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
