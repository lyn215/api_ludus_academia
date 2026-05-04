"""app/db/session.py"""
from supabase import create_client, Client

from app.core.config import get_settings

settings = get_settings()

supabase: Client = create_client(
    supabase_url=settings.SUPABASE_URL,
    supabase_key=settings.SUPABASE_ANON_KEY,
)


async def init_db() -> None:
    """Verifica conectividad HTTP con Supabase al arrancar."""
    try:
        response = supabase.table("bancos_preguntas").select("id").limit(1).execute()
        print(f"Supabase HTTP client initialized. Found {len(response.data)} banco(s)")
    except Exception as e:
        print(f"Error initializing Supabase client: {e}")
        raise


def get_supabase() -> Client:
    """Dependencia FastAPI: inyecta el cliente Supabase en endpoints.

    Uso:
        @router.get("/bancos")
        def get_bancos(db: Client = Depends(get_supabase)):
            return db.table("bancos_preguntas").select("*").execute().data
    """
    return supabase


async def get_db() -> Client:
    """Alias de get_supabase para compatibilidad durante la migración."""
    return get_supabase()
