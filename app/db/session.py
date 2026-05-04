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
    poolclass=NullPool,
    connect_args={
        "ssl": ssl_context,
        "timeout": 30,
        "statement_cache_size": 0,          # <--- Entero, no string
        "prepared_statement_cache_size": 0, # <--- Entero, no string
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
