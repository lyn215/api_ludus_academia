"""
app/core/security.py
Validación del JWT emitido por Supabase Auth.

Soporta dos modos:
  - HS256 con SUPABASE_JWT_SECRET (legacy, proyectos anteriores)
  - RS256 con las JWT Signing Keys de Supabase (proyectos migrados)
    — las claves públicas se obtienen de {SUPABASE_URL}/auth/v1/keys (JWKS)
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


def _fetch_jwks() -> list[dict]:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    try:
        resp = httpx.get(
            f"{settings.SUPABASE_URL}/auth/v1/keys",
            timeout=10,
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


def _try_rs256(token: str) -> dict[str, Any] | None:
    for key in _fetch_jwks():
        try:
            return jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                options={"verify_aud": False},
            )
        except JWTError:
            continue
    return None


def verify_supabase_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict[str, Any]:
    token = credentials.credentials
    payload = _try_hs256(token) or _try_rs256(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión de Supabase inválida o expirada.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def get_supabase_uid(payload: dict = Depends(verify_supabase_token)) -> str:
    uid = payload.get("sub")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin identificador de usuario (sub).",
        )
    return uid


def get_token_email(payload: dict = Depends(verify_supabase_token)) -> str:
    return payload.get("email", "")
