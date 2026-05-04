"""app/api/v1/endpoints/bancos.py
Endpoints de bancos de preguntas — usan exclusivamente Supabase HTTP.
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from supabase import Client

from app.core.security import verify_supabase_token
from app.db.session import get_supabase

router = APIRouter(
    prefix="/bancos",
    tags=["📚 Bancos de preguntas"],
    dependencies=[Depends(verify_supabase_token)],
)


# ---------------------------------------------------------------------------
# Schemas de respuesta
# ---------------------------------------------------------------------------

class OpcionOut(BaseModel):
    id: str
    texto_opcion: str
    es_correcta: bool
    orden: int | None
    feedback_especifico: str | None


class PreguntaOut(BaseModel):
    id: str
    texto_pregunta: str
    tipo_pregunta: str
    materia: str
    dificultad: int | None
    pista_texto: str | None
    explicacion: str | None
    media_url: str | None
    activo: bool
    opciones: list[OpcionOut] = []


class BancoOut(BaseModel):
    id: str
    nombre: str
    descripcion: str | None
    materia: str
    nivel_grado: int | None
    activo: bool
    version: int
    es_oficial: bool
    total_preguntas: int = 0


class BancoDetalleOut(BancoOut):
    preguntas: list[PreguntaOut] = []


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[BancoOut], summary="Listar bancos activos")
def listar_bancos(
    db: Annotated[Client, Depends(get_supabase)],
    materia: Annotated[str | None, Query(description="Filtrar por materia")] = None,
    nivel_grado: Annotated[int | None, Query(description="Filtrar por nivel/grado")] = None,
    solo_oficiales: Annotated[bool, Query(description="Solo bancos oficiales")] = False,
) -> list[BancoOut]:
    q = db.table("bancos_preguntas").select(
        "id, nombre, descripcion, materia, nivel_grado, activo, version, es_oficial"
    ).eq("activo", True)

    if materia:
        q = q.eq("materia", materia)
    if nivel_grado is not None:
        q = q.eq("nivel_grado", nivel_grado)
    if solo_oficiales:
        q = q.eq("es_oficial", True)

    response = q.execute()
    bancos = response.data

    # Añadir conteo de preguntas por banco
    for banco in bancos:
        conteo = (
            db.table("banco_pregunta_asignacion")
            .select("id", count="exact")
            .eq("banco_id", banco["id"])
            .execute()
        )
        banco["total_preguntas"] = conteo.count or 0

    return bancos


@router.get("/{banco_id}", response_model=BancoDetalleOut, summary="Detalle de banco con preguntas")
def obtener_banco(
    banco_id: UUID,
    db: Annotated[Client, Depends(get_supabase)],
    incluir_opciones: Annotated[bool, Query(description="Incluir opciones de respuesta")] = True,
) -> BancoDetalleOut:
    # Obtener banco
    res_banco = (
        db.table("bancos_preguntas")
        .select("id, nombre, descripcion, materia, nivel_grado, activo, version, es_oficial")
        .eq("id", str(banco_id))
        .single()
        .execute()
    )
    if not res_banco.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banco no encontrado")

    banco = res_banco.data

    # Obtener preguntas asignadas al banco (ordenadas)
    res_asignaciones = (
        db.table("banco_pregunta_asignacion")
        .select("pregunta_id, orden_en_banco")
        .eq("banco_id", str(banco_id))
        .order("orden_en_banco")
        .execute()
    )
    pregunta_ids = [a["pregunta_id"] for a in res_asignaciones.data]

    preguntas: list[dict] = []
    if pregunta_ids:
        res_preguntas = (
            db.table("preguntas")
            .select(
                "id, texto_pregunta, tipo_pregunta, materia, dificultad, "
                "pista_texto, explicacion, media_url, activo"
            )
            .in_("id", pregunta_ids)
            .eq("activo", True)
            .execute()
        )
        preguntas = res_preguntas.data

        if incluir_opciones and preguntas:
            res_opciones = (
                db.table("opciones_respuesta")
                .select("id, pregunta_id, texto_opcion, es_correcta, orden, feedback_especifico")
                .in_("pregunta_id", pregunta_ids)
                .order("orden")
                .execute()
            )
            opciones_por_pregunta: dict[str, list] = {}
            for op in res_opciones.data:
                opciones_por_pregunta.setdefault(op["pregunta_id"], []).append(op)

            for p in preguntas:
                p["opciones"] = opciones_por_pregunta.get(p["id"], [])

    banco["preguntas"] = preguntas
    banco["total_preguntas"] = len(preguntas)
    return banco


@router.get("/{banco_id}/preguntas", response_model=list[PreguntaOut], summary="Preguntas de un banco")
def listar_preguntas_banco(
    banco_id: UUID,
    db: Annotated[Client, Depends(get_supabase)],
    dificultad: Annotated[int | None, Query(ge=1, le=3)] = None,
) -> list[PreguntaOut]:
    res_asignaciones = (
        db.table("banco_pregunta_asignacion")
        .select("pregunta_id, orden_en_banco")
        .eq("banco_id", str(banco_id))
        .order("orden_en_banco")
        .execute()
    )
    pregunta_ids = [a["pregunta_id"] for a in res_asignaciones.data]
    if not pregunta_ids:
        return []

    q = (
        db.table("preguntas")
        .select(
            "id, texto_pregunta, tipo_pregunta, materia, dificultad, "
            "pista_texto, explicacion, media_url, activo"
        )
        .in_("id", pregunta_ids)
        .eq("activo", True)
    )
    if dificultad is not None:
        q = q.eq("dificultad", dificultad)

    preguntas = q.execute().data

    # Opciones para todas las preguntas en una sola query
    if preguntas:
        res_opciones = (
            db.table("opciones_respuesta")
            .select("id, pregunta_id, texto_opcion, es_correcta, orden, feedback_especifico")
            .in_("pregunta_id", [p["id"] for p in preguntas])
            .order("orden")
            .execute()
        )
        opciones_por_pregunta: dict[str, list] = {}
        for op in res_opciones.data:
            opciones_por_pregunta.setdefault(op["pregunta_id"], []).append(op)
        for p in preguntas:
            p["opciones"] = opciones_por_pregunta.get(p["id"], [])

    return preguntas
