"""app/db/session.py"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

# NullPool: SQLAlchemy no mantiene pool propio — pgbouncer hace el pooling.
# statement_cache_size=0: deshabilita prepared statements en asyncpg,
# requerido cuando el backend es pgbouncer en transaction mode.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "development",
    future=True,
    poolclass=NullPool,
    connect_args={
        "statement_cache_size": 0,
        "server_settings": {
            "jit": "off",
            "application_name": "ludusacademia",
        },
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
    async with engine.begin() as _conn:
        pass


async def get_db() -> AsyncSession:
    """Dependencia FastAPI: inyecta una sesión por request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
