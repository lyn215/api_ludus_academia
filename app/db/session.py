"""app/db/session.py"""
import ssl
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool # Importante para evitar doble pooling

from app.core.config import get_settings

settings = get_settings()

# Configuración SSL para despliegue en la nube
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "development",
    # 1. NullPool es vital: delega el pooling totalmente a Supabase
    poolclass=NullPool,
    connect_args={
        "ssl": ssl_context,
        "timeout": 30,
        # 2. Desactivamos caché de sentencias a nivel driver (asyncpg)
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Verifica conectividad al arrancar. Las tablas las gestiona Supabase."""
    try:
        async with engine.begin() as _conn:
            # Ejecutar una query simple para verificar conexión
            await _conn.execute("SELECT 1")
        print("Database connection successful")
    except Exception as e:
        print(f"Database connection error during init: {e}")
        raise


async def get_db() -> AsyncSession:
    """Dependencia FastAPI: inyecta una sesión por request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
