"""app/db/session.py"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "development",
    future=True,
    pool_pre_ping=True,
    pool_size=3,  # Reducido para pooler
    max_overflow=2,
    pool_timeout=30,
    pool_recycle=3600,  # Reciclar conexiones cada hora
    connect_args={
        "statement_cache_size": 0,  # Crítico para pgbouncer
        "timeout": 15,
        "server_settings": {
            "jit": "off",  # Desactivar JIT para mejor compatibilidad
        },
    },
    # SQLAlchemy 2.0: desactiva compiled statement cache
    execution_options={"compiled_cache": None},
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


async def get_db() -> AsyncSession:
    """Dependencia FastAPI: inyecta una sesión por request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
