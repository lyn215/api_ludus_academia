"""
app/api/v1/endpoints/docentes.py
Endpoints del docente — todos requieren JWT de Supabase.
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from app.core.security import get_supabase_uid, get_token_email, verify_supabase_token
from app.db.session import get_supabase
from app.schemas.schemas import (
    ActualizarAliasRequest,
    AnaliticaGrupoResponse,
    CrearGrupoRequest,
    GenerarCodigoRequest,
    GenerarCodigoResponse,
    GrupoInfo,
    MiPerfilResponse,
)
from app.services.docente_service import DocenteService

router = APIRouter(
    prefix="/docentes",
    tags=["📊 Docentes"],
    dependencies=[Depends(verify_supabase_token)],
)
service = DocenteService()


@router.get("/perfil", response_model=MiPerfilResponse, summary="Mi perfil")
async def mi_perfil(
    db=Depends(get_supabase),
    supabase_uid: Annotated[str, Depends(get_supabase_uid)] = None,
    correo: Annotated[str, Depends(get_token_email)] = None,
) -> MiPerfilResponse:
    return await service.mi_perfil(db, supabase_uid, correo)


@router.get("/grupos", response_model=list[GrupoInfo], summary="Mis grupos")
async def listar_grupos(
    db=Depends(get_supabase),
    supabase_uid: Annotated[str, Depends(get_supabase_uid)] = None,
    correo: Annotated[str, Depends(get_token_email)] = None,
) -> list[GrupoInfo]:
    return await service.listar_mis_grupos(db, supabase_uid, correo)


@router.post(
    "/grupos",
    response_model=GrupoInfo,
    status_code=status.HTTP_201_CREATED,
    summary="Crear grupo",
)
async def crear_grupo(
    payload: CrearGrupoRequest,
    db=Depends(get_supabase),
    supabase_uid: Annotated[str, Depends(get_supabase_uid)] = None,
    correo: Annotated[str, Depends(get_token_email)] = None,
) -> GrupoInfo:
    return await service.crear_grupo(db, supabase_uid, correo, payload)


@router.patch(
    "/alumnos/{uuid_estudiante}/alias",
    summary="Actualizar alias del alumno",
)
async def actualizar_alias(
    uuid_estudiante: str,
    payload: ActualizarAliasRequest,
    db=Depends(get_supabase),
    supabase_uid: Annotated[str, Depends(get_supabase_uid)] = None,
    correo: Annotated[str, Depends(get_token_email)] = None,
) -> dict:
    return await service.actualizar_alias(db, supabase_uid, correo, uuid_estudiante, payload.alias)


@router.post(
    "/codigos",
    response_model=GenerarCodigoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generar código de vinculación",
)
async def generar_codigo(
    payload: GenerarCodigoRequest,
    db=Depends(get_supabase),
    supabase_uid: Annotated[str, Depends(get_supabase_uid)] = None,
    correo: Annotated[str, Depends(get_token_email)] = None,
) -> GenerarCodigoResponse:
    return await service.generar_codigo(db, supabase_uid, correo, payload)


@router.get(
    "/analitica/grupo/{id_grupo}",
    response_model=AnaliticaGrupoResponse,
    summary="Analítica del grupo",
)
async def analitica_grupo(
    id_grupo: str,
    db=Depends(get_supabase),
    supabase_uid: Annotated[str, Depends(get_supabase_uid)] = None,
    correo: Annotated[str, Depends(get_token_email)] = None,
    metrica: Literal["errores", "progreso"] | None = Query(None),
) -> AnaliticaGrupoResponse:
    return await service.analitica_grupo(db, supabase_uid, correo, id_grupo, metrica)


@router.get(
    "/reportes/pdf/{uuid_estudiante}",
    summary="Reporte PDF del alumno",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def reporte_pdf(
    uuid_estudiante: str,
    db=Depends(get_supabase),
    supabase_uid: Annotated[str, Depends(get_supabase_uid)] = None,
    correo: Annotated[str, Depends(get_token_email)] = None,
):
    from app.services.reporte_service import ReporteService

    docente = await service.obtener_o_crear_docente(db, supabase_uid, correo)
    rows = await db.query("estudiantes", filters={"uuid_estudiante": uuid_estudiante})
    if not rows:
        raise HTTPException(status_code=404, detail="Alumno no encontrado.")
    estudiante = rows[0]
    grupos = await db.query("grupos", filters={"id": estudiante["id_grupo"]})
    if not grupos or grupos[0]["docente_id"] != docente["id"]:
        raise HTTPException(status_code=403, detail="No tienes acceso a este alumno.")
    pdf_bytes = await ReporteService().generar_pdf(db, estudiante, grupos[0]["nombre_grupo"])
    alias = estudiante.get("alias_estudiante") or uuid_estudiante[:8]
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=reporte_{alias}.pdf"},
    )
