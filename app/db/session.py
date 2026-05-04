"""app/db/session.py"""
import ssl
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "development",
    poolclass=NullPool,
    # ESTO ES LO NUEVO Y CRÍTICO:
    # 1. connect_args con valores ENTEROS
    connect_args={
        "ssl": ssl_context,
        "timeout": 30,
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
    # 2. Forzamos a SQLAlchemy a NO cachear nada y a "creer" que ya sabe la versión
    execution_options={
        "compiled_cache": None
    },
)

# 3. Bypass manual del Server Version Info (El culpable del log)
# Esto evita que SQLAlchemy ejecute "select pg_catalog.version()"
engine.dialect._is_postgresql = True
engine.dialect.server_version_info = (15, 0) # Supabase suele usar Postgres 15+

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
    """Verifica conectividad al arrancar sin usar caché de sentencias."""
    from sqlalchemy import text
    try:
        # Usamos un bloque directo para evitar que SQLAlchemy intente 
        # preparar la sentencia en el pool
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.commit()
        print("Database connection successful")
    except Exception as e:
        print(f"Database connection error during init: {e}")
        # No hagas raise aquí inmediatamente para ver si el servidor 
        # puede arrancar de todos modos, o deja el raise si quieres 
        # seguridad total pero asegúrate de que el log se imprima.
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
