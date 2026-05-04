"""app/api/v1/endpoints/bancos.py"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.session import get_supabase

router = APIRouter()


@router.get("/")
async def listar_bancos(
    materia: Optional[str] = Query(None),
    nivel_grado: Optional[int] = Query(None),
    db=Depends(get_supabase),
):
    try:
        data = await db.query(
            "bancos_preguntas",
            select="*",
            filters={"activo": "true"} if not materia else None,
        )
        if materia:
            data = [b for b in data if b.get("materia") == materia]
        if nivel_grado:
            data = [b for b in data if b.get("nivel_grado") == nivel_grado]
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{banco_id}")
async def detalle_banco(banco_id: str, db=Depends(get_supabase)):
    try:
        bancos = await db.query("bancos_preguntas", select="*", filters={"id": banco_id})
        if not bancos:
            raise HTTPException(status_code=404, detail="Banco no encontrado")
        banco = bancos[0]
        preguntas = await db.query(
            "preguntas",
            select="*,opciones_respuesta(*)",
            filters={"banco_id": banco_id},
        )
        banco["preguntas"] = preguntas
        return banco
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{banco_id}/preguntas")
async def preguntas_del_banco(
    banco_id: str,
    dificultad: Optional[int] = Query(None),
    db=Depends(get_supabase),
):
    try:
        preguntas = await db.query(
            "preguntas",
            select="*,opciones_respuesta(*)",
            filters={"banco_id": banco_id},
        )
        if dificultad:
            preguntas = [p for p in preguntas if p.get("dificultad") == dificultad]
        return preguntas
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
