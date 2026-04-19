"""
app/core/security.py
Valida JWTs de Supabase Auth.

Soporta tres algoritmos:
  - HS256  legacy secret (proyectos anteriores)
  - RS256  JWT Signing Keys RSA
  - ES256  JWT Signing Keys EC P-256 (proyectos migrados desde ~2024)

Las claves públicas se obtienen vía JWKS:
  {SUPABASE_URL}/auth/v1/keys  (requiere apikey header)
"""
from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()
bearer_scheme = HTTPBearer()

_jwks_cache: list[dict] | None = None


async def _fetch_jwks() -> list[dict]:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{settings.SUPABASE_URL}/auth/v1/keys",
                headers={"apikey": settings.SUPABASE_ANON_KEY},
            )
            resp.raise_for_status()
            _jwks_cache = resp.json().get("keys", [])
    except Exception:
        _jwks_cache = []
    return _jwks_cache


def _try_hs256(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError:
        return None


async def _try_jwks(token: str) -> dict[str, Any] | None:
    for key in await _fetch_jwks():
        try:
            return jwt.decode(
                token,
                key,
                algorithms=["RS256", "ES256"],
                options={"verify_aud": False},
            )
        except JWTError:
            continue
    return None


async def verify_supabase_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict[str, Any]:
    token = credentials.credentials
    payload = _try_hs256(token) or await _try_jwks(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión de Supabase inválida o expirada.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


async def get_supabase_uid(payload: dict = Depends(verify_supabase_token)) -> str:
    uid = payload.get("sub")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin identificador de usuario (sub).",
        )
    return uid


async def get_token_email(payload: dict = Depends(verify_supabase_token)) -> str:
    return payload.get("email", "")
