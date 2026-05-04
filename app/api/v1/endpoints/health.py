"""app/api/v1/endpoints/health.py"""
from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.db.session import get_supabase
from app.schemas.schemas import HealthResponse

router = APIRouter(tags=["🩺 Health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse, summary="Estado del servidor")
async def health(db=Depends(get_supabase)) -> HealthResponse:
    try:
        await db.query("bancos_preguntas", select="id", filters={"activo": "true"})
        db_ok = True
    except Exception:
        db_ok = False
    return HealthResponse(
        estado="ok" if db_ok else "degradado",
        version="2.1.0",
        entorno=settings.APP_ENV,
    )
