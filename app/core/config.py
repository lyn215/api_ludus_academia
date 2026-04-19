"""
app/core/config.py
Configuración central de LudusAcademia v2.
"""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # SQLite
    DATABASE_PATH: str = "./ludusacademia.db"

    # Supabase Auth
    SUPABASE_URL: str
    SUPABASE_JWT_SECRET: str

    # Comportamiento
    MAX_SYNC_PAYLOAD_KB: int = 50
    INVITE_CODE_EXPIRY_HOURS: int = 24

    # CORS — acepta JSON array o cadena separada por comas
    # Ejemplos válidos:
    #   ALLOWED_ORIGINS=http://localhost:5173,https://mi-app.onrender.com
    #   ALLOWED_ORIGINS=["http://localhost:5173","https://mi-app.onrender.com"]
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v: object) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json
                return json.loads(v)
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def DATABASE_URL(self) -> str:
        return f"sqlite+aiosqlite:///{self.DATABASE_PATH}"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
