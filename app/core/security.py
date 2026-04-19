"""
app/core/security.py
Valida JWTs de Supabase Auth.

Soporta ES256 (P-256), RS256 y HS256 legacy.
JWKS obtenido de {SUPABASE_URL}/auth/v1/keys con apikey header.
Se usa PyJWT + ECAlgorithm/RSAAlgorithm para construir las claves.
"""
from __future__ import annotations

import time
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.algorithms import ECAlgorithm, RSAAlgorithm
from jwt.exceptions import InvalidTokenError

from app.core.config import get_settings

settings = get_settings()
bearer_scheme = HTTPBearer()

_jwks_cache: list[dict] | None = None
_jwks_fetched_at: float = 0.0
_JWKS_TTL = 3600.0  # refrescar cada hora


async def _fetch_jwks() -> list[dict]:
    global _jwks_cache, _jwks_fetched_at
    now = time.monotonic()
    # Solo usa caché si tiene datos y no expiró
    if _jwks_cache and (now - _jwks_fetched_at) < _JWKS_TTL:
        return _jwks_cache
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{settings.SUPABASE_URL}/auth/v1/keys",
                headers={"apikey": settings.SUPABASE_ANON_KEY},
            )
            resp.raise_for_status()
            keys = resp.json().get("keys", [])
            if keys:  # no cachear si llegó vacío
                _jwks_cache = keys
                _jwks_fetched_at = now
    except Exception:
        pass
    return _jwks_cache or []


def _decode_hs256(token: str) -> dict[str, Any] | None:
    if not settings.SUPABASE_JWT_SECRET:
        return None
    try:
        return jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except InvalidTokenError:
        return None


async def _decode_jwks(token: str) -> dict[str, Any] | None:
    keys = await _fetch_jwks()
    if not keys:
        return None
    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
    except InvalidTokenError:
        return None

    for jwk_data in keys:
        # Saltar claves que no coincidan por kid
        if kid and jwk_data.get("kid") != kid:
            continue
        try:
            kty = jwk_data.get("kty", "")
            if kty == "EC":
                public_key = ECAlgorithm.from_jwk(jwk_data)
            elif kty == "RSA":
                public_key = RSAAlgorithm.from_jwk(jwk_data)
            else:
                continue
            return jwt.decode(
                token,
                public_key,
                algorithms=["RS256", "ES256"],
                options={"verify_aud": False},
            )
        except (InvalidTokenError, Exception):
            continue
    return None


async def verify_supabase_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict[str, Any]:
    token = credentials.credentials
    payload = _decode_hs256(token) or await _decode_jwks(token)
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
