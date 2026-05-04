"""
Sistema híbrido de conexión a base de datos.
- SQLAlchemy: Para endpoints existentes (docentes, estudiantes, etc.)
- Supabase HTTP: Para nuevos endpoints de bancos dinámicos
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from supabase import create_client, Client

from app.core.config import get_settings

settings = get_settings()

# =============================================================================
# SISTEMA 1: SQLAlchemy (para endpoints existentes)
# =============================================================================

DATABASE_URL = (
    "postgresql+asyncpg://postgres.bbyhevcprqxntsaknwul:Dez6XRXwOiHFHo7A"
    "@aws-1-us-east-1.pooler.supabase.com:6543/postgres"
)

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.APP_ENV == "development",
    future=True,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
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


async def get_db() -> AsyncSession:
    """Dependencia FastAPI para endpoints que usan SQLAlchemy."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# =============================================================================
# SISTEMA 2: Supabase HTTP (para nuevos endpoints de bancos)
# =============================================================================

supabase: Client = create_client(
    supabase_url=settings.SUPABASE_URL,
    supabase_key=settings.SUPABASE_ANON_KEY,
)


def get_supabase() -> Client:
    """Dependencia FastAPI para endpoints que usan Supabase HTTP.

    Uso:
        @router.get("/bancos")
        def get_bancos(db: Client = Depends(get_supabase)):
            return db.table("bancos_preguntas").select("*").execute().data
    """
    return supabase


# =============================================================================
# Inicialización
# =============================================================================

async def init_db() -> None:
    """Verifica conectividad de ambos sistemas al arrancar."""
    try:
        async with engine.begin() as _conn:
            print("SQLAlchemy connection OK")

        response = supabase.table("bancos_preguntas").select("id").limit(1).execute()
        print(f"Supabase HTTP client OK. Found {len(response.data)} banco(s)")
    except Exception as e:
        print(f"Error initializing database connections: {e}")
        raise
