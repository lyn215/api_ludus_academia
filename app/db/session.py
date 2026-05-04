"""app/db/session.py"""
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine, AsyncEngine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()


@event.listens_for(AsyncEngine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """
    Asegura statement_cache_size=0 para pgbouncer en cada conexión.
    Se ejecuta después de que asyncpg se conecta.
    """
    if hasattr(dbapi_conn, 'set_statement_cache_size'):
        try:
            dbapi_conn.set_statement_cache_size(0)
        except Exception as e:
            print(f"Warning: Could not set statement_cache_size: {e}")


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "development",
    future=True,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args={
        "statement_cache_size": 0,
        "timeout": 10,
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
            pass
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
