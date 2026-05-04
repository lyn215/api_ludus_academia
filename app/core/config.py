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
    def ensure_statement_cache_size(cls, v: str) -> str:
        """
        Asegura que statement_cache_size=0 esté en la URL para pgbouncer.
        Si no está presente, lo agrega automáticamente.
        """
        if not v or "statement_cache_size" in v:
            return v
        
        # Parsear la URL
        parsed = urlparse(v)
        
        # Parsear query parameters existentes
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        
        # Agregar statement_cache_size=0
        query_params["statement_cache_size"] = ["0"]
        
        # Reconstruir query string (sin usar '+' para espacios)
        new_query = urlencode(query_params, doseq=True)
        
        # Reconstruir URL
        new_parsed = parsed._replace(query=new_query)
        return urlunparse(new_parsed)

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
