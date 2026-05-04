"""app/services/estudiante_service.py"""
import random
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.schemas.schemas import (
    SincronizarRequest,
    SincronizarResponse,
    VincularRequest,
    VincularResponse,
)

settings = get_settings()


class EstudianteService:

    async def vincular(self, db, payload: VincularRequest) -> VincularResponse:
        ahora = datetime.now(timezone.utc)
        codigos = await db.query("codigos_vinculacion", filters={"codigo": payload.codigo_vinculacion})

        if not codigos:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Código de vinculación inválido o expirado.")

        codigo = codigos[0]
        expira_raw = codigo["expira_el"]
        expira = (
            datetime.fromisoformat(expira_raw.replace("Z", "+00:00"))
            if isinstance(expira_raw, str) else expira_raw
        )
        if expira.tzinfo is None:
            expira = expira.replace(tzinfo=timezone.utc)

        if expira < ahora:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Código de vinculación inválido o expirado.")

        estudiantes = await db.query("estudiantes", filters={"uuid_estudiante": payload.uuid_estudiante})

        if estudiantes:
            est = estudiantes[0]
            if est["id_grupo"] == codigo["id_grupo"]:
                if payload.nombre_alumno and payload.nombre_alumno.strip():
                    await db.update(
                        "estudiantes",
                        {"alias_estudiante": payload.nombre_alumno.strip()[:50]},
                        {"uuid_estudiante": payload.uuid_estudiante},
                    )
                return VincularResponse(
                    mensaje="Dispositivo vinculado con éxito.",
                    id_grupo=codigo["id_grupo"],
                )
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="Este dispositivo ya está vinculado a otro grupo.")

        if payload.nombre_alumno and payload.nombre_alumno.strip():
            alias = payload.nombre_alumno.strip()[:50]
        else:
            existing = await db.query("estudiantes", filters={"id_grupo": codigo["id_grupo"]})
            alias = f"Alumno {len(existing) + 1}"

        await db.insert("estudiantes", {
            "uuid_estudiante": payload.uuid_estudiante,
            "id_grupo": codigo["id_grupo"],
            "alias_estudiante": alias,
        })
        return VincularResponse(
            mensaje="Dispositivo vinculado con éxito.",
            id_grupo=codigo["id_grupo"],
        )

    async def sincronizar(self, db, payload: SincronizarRequest) -> SincronizarResponse:
        estudiantes = await db.query("estudiantes", filters={"uuid_estudiante": payload.uuid_estudiante})
        if not estudiantes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="El dispositivo no está vinculado a ningún grupo.")
        monedas_base = estudiantes[0].get("monedas_totales") or 0

        procesados = 0
        duplicados = 0
        monedas_nuevas = 0

        for evento in payload.eventos:
            fd = evento.fecha_dispositivo
            try:
                await db.insert("eventos_aprendizaje", {
                    "id_evento": evento.id_evento,
                    "uuid_estudiante": payload.uuid_estudiante,
                    "id_mision": evento.id_mision,
                    "errores": evento.errores,
                    "segundos_jugados": evento.segundos_jugados,
                    "monedas_ganadas": evento.monedas_ganadas,
                    "fecha_dispositivo": fd.isoformat() if hasattr(fd, "isoformat") else fd,
                })
                procesados += 1
                monedas_nuevas += evento.monedas_ganadas
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (409, 422, 400):
                    duplicados += 1
                else:
                    raise

        if monedas_nuevas > 0:
            await db.update(
                "estudiantes",
                {"monedas_totales": monedas_base + monedas_nuevas},
                {"uuid_estudiante": payload.uuid_estudiante},
            )

        return SincronizarResponse(
            estado="exito",
            eventos_procesados=procesados,
            duplicados_ignorados=duplicados,
        )


def generar_codigo_ludu() -> str:
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    sufijo = "".join(random.choices(chars, k=2))
    return f"LUDU{sufijo}"
