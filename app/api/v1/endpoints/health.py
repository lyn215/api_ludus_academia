"""
app/api/v1/endpoints/health.py
"""
import base64
import json

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.schemas import HealthResponse

router = APIRouter(tags=["🩺 Health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse, summary="Estado del servidor")
async def health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return HealthResponse(
        estado="ok" if db_ok else "degradado",
        version="2.1.0",
        entorno=settings.APP_ENV,
    )


@router.get("/debug/jwt", summary="Diagnóstico JWT — eliminar en producción")
async def debug_jwt(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else None

    token_header: dict = {}
    if token:
        try:
            raw = token.split(".")[0]
            padded = raw + "=" * (-len(raw) % 4)
            token_header = json.loads(base64.urlsafe_b64decode(padded))
        except Exception as exc:
            token_header = {"error": str(exc)}

    jwks_url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
    jwks_result: dict = {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                jwks_url,
                headers={"apikey": settings.SUPABASE_ANON_KEY},
            )
            jwks_result = {
                "status": resp.status_code,
                "anon_key_set": bool(settings.SUPABASE_ANON_KEY),
                "keys_count": len(resp.json().get("keys", [])) if resp.is_success else 0,
                "raw": resp.text[:300],
            }
    except Exception as exc:
        jwks_result = {"error": str(exc)}

    return {
        "supabase_url_configured": bool(settings.SUPABASE_URL),
        "jwt_secret_configured": bool(settings.SUPABASE_JWT_SECRET),
        "anon_key_configured": bool(settings.SUPABASE_ANON_KEY),
        "token_present": bool(token),
        "token_header": token_header,
        "jwks_url": jwks_url,
        "jwks_fetch": jwks_result,
    }
