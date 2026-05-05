"""app/api/v1/endpoints/bancos.py
Endpoints de bancos de preguntas — usan exclusivamente Supabase HTTP.
"""
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

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
    orden: int | None = None
    feedback_especifico: str | None = None


class PreguntaOut(BaseModel):
    id: str
    texto_pregunta: str
    tipo_pregunta: str
    materia: str
    dificultad: int | None = None
    pista_texto: str | None = None
    explicacion: str | None = None
    media_url: str | None = None
    activo: bool
    opciones: list[OpcionOut] = []


class BancoOut(BaseModel):
    id: str
    nombre: str
    descripcion: str | None = None
    materia: str
    nivel_grado: int | None = None
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
async def listar_bancos(
    db=Depends(get_supabase),
    materia: Optional[str] = Query(None),
    nivel_grado: Optional[int] = Query(None),
    solo_oficiales: bool = Query(False),
) -> list[BancoOut]:
    bancos = await db.query(
        "bancos_preguntas",
        select="id,nombre,descripcion,materia,nivel_grado,activo,version,es_oficial",
        filters={"activo": "true"},
    )
    if materia:
        bancos = [b for b in bancos if b.get("materia") == materia]
    if nivel_grado is not None:
        bancos = [b for b in bancos if b.get("nivel_grado") == nivel_grado]
    if solo_oficiales:
        bancos = [b for b in bancos if b.get("es_oficial")]

    for banco in bancos:
        asignaciones = await db.query(
            "banco_pregunta_asignacion", select="id", filters={"banco_id": banco["id"]}
        )
        banco["total_preguntas"] = len(asignaciones)

    return bancos


@router.get("/{banco_id}", response_model=BancoDetalleOut, summary="Detalle de banco con preguntas")
async def obtener_banco(
    banco_id: UUID,
    db=Depends(get_supabase),
    incluir_opciones: bool = Query(True),
) -> BancoDetalleOut:
    rows = await db.query(
        "bancos_preguntas",
        select="id,nombre,descripcion,materia,nivel_grado,activo,version,es_oficial",
        filters={"id": str(banco_id)},
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banco no encontrado")
    banco = rows[0]

    asignaciones = await db.query(
        "banco_pregunta_asignacion",
        select="pregunta_id,orden_en_banco",
        filters={"banco_id": str(banco_id)},
        order="orden_en_banco",
    )
    pregunta_ids = [a["pregunta_id"] for a in asignaciones]

    preguntas: list[dict] = []
    if pregunta_ids:
        preguntas = await db.query(
            "preguntas",
            select="id,texto_pregunta,tipo_pregunta,materia,dificultad,pista_texto,explicacion,media_url,activo",
            in_filters={"id": pregunta_ids},
            filters={"activo": "true"},
        )
        if incluir_opciones and preguntas:
            opciones = await db.query(
                "opciones_respuesta",
                select="id,pregunta_id,texto_opcion,es_correcta,orden,feedback_especifico",
                in_filters={"pregunta_id": pregunta_ids},
                order="orden",
            )
            by_pregunta: dict[str, list] = {}
            for op in opciones:
                by_pregunta.setdefault(op["pregunta_id"], []).append(op)
            for p in preguntas:
                p["opciones"] = by_pregunta.get(p["id"], [])

    banco["preguntas"] = preguntas
    banco["total_preguntas"] = len(preguntas)
    return banco


@router.get("/{banco_id}/preguntas", response_model=list[PreguntaOut], summary="Preguntas de un banco")
async def listar_preguntas_banco(
    banco_id: UUID,
    db=Depends(get_supabase),
    dificultad: Optional[int] = Query(None, ge=1, le=3),
) -> list[PreguntaOut]:
    asignaciones = await db.query(
        "banco_pregunta_asignacion",
        select="pregunta_id,orden_en_banco",
        filters={"banco_id": str(banco_id)},
        order="orden_en_banco",
    )
    pregunta_ids = [a["pregunta_id"] for a in asignaciones]
    if not pregunta_ids:
        return []

    preguntas = await db.query(
        "preguntas",
        select="id,texto_pregunta,tipo_pregunta,materia,dificultad,pista_texto,explicacion,media_url,activo",
        in_filters={"id": pregunta_ids},
        filters={"activo": "true"},
    )
    if dificultad is not None:
        preguntas = [p for p in preguntas if p.get("dificultad") == dificultad]

    if preguntas:
        opciones = await db.query(
            "opciones_respuesta",
            select="id,pregunta_id,texto_opcion,es_correcta,orden,feedback_especifico",
            in_filters={"pregunta_id": [p["id"] for p in preguntas]},
            order="orden",
        )
        by_pregunta: dict[str, list] = {}
        for op in opciones:
            by_pregunta.setdefault(op["pregunta_id"], []).append(op)
        for p in preguntas:
            p["opciones"] = by_pregunta.get(p["id"], [])

    return preguntas


# Esquema de validación para la entrada de datos
class AsignacionBanco(BaseModel):
    banco_id: str
    grupo_id: str

@router.post("/asignar")
async def asignar_banco(asignacion: AsignacionBanco, db = Depends(get_supabase)):
    try:
        # Primero eliminar cualquier banco existente para el grupo (un solo banco por grupo)
        await db.delete("grupo_banco", {"grupo_id": asignacion.grupo_id})
        # Luego insertar el nuevo banco
        await db.insert("grupo_banco", {
            "banco_id": asignacion.banco_id,
            "grupo_id": asignacion.grupo_id
        })
        return {"mensaje": "Banco asignado correctamente al grupo."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al asignar: {str(e)}")

@router.delete("/asignar/{grupo_id}/{banco_id}")
async def desasignar_banco(grupo_id: str, banco_id: str, db = Depends(get_supabase)):
    try:
        await db.delete("grupo_banco", {
            "banco_id": banco_id,
            "grupo_id": grupo_id
        })
        return {"mensaje": "Banco desasignado correctamente del grupo."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al desasignar: {str(e)}")

@router.get("/asignados/{grupo_id}", response_model=list[str], summary="Bancos asignados a un grupo")
async def obtener_bancos_asignados(grupo_id: str, db = Depends(get_supabase)) -> list[str]:
    """Retorna lista de UUIDs de bancos asignados al grupo especificado."""
    try:
        asignaciones = await db.get_by_match(
            "grupo_banco",
            match={"grupo_id": grupo_id},
            select="banco_id"
        )
        return [asig["banco_id"] for asig in asignaciones]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al obtener bancos asignados: {str(e)}")
