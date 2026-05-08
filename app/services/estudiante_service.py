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
        expira_raw = codigo.get("expires_at")

        expira = (
            datetime.fromisoformat(expira_raw.replace("Z", "+00:00"))
            if isinstance(expira_raw, str) else expira_raw
        )
        if expira.tzinfo is None:
            expira = expira.replace(tzinfo=timezone.utc)

        if expira < ahora:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Código de vinculación inválido o expirado.")

        grupo_id = codigo["grupo_id"]

        grupos = await db.query("grupos", filters={"id": grupo_id})
        if not grupos:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Grupo no encontrado.")
        nombre_grupo = grupos[0]["nombre_grupo"]

        alumnos = await db.query("usuarios", filters={"id": payload.uuid_estudiante})

        if alumnos:
            alumno = alumnos[0]
            if alumno.get("grupo") == nombre_grupo:
                if payload.nombre_alumno and payload.nombre_alumno.strip():
                    await db.patch(
                        "usuarios",
                        {"id": payload.uuid_estudiante},
                        {"nombre_completo": payload.nombre_alumno.strip()[:50]},
                    )
                return VincularResponse(
                    mensaje="Dispositivo vinculado con éxito.",
                    id_grupo=grupo_id,
                )
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="Este dispositivo ya está vinculado a otro grupo.")

        if payload.nombre_alumno and payload.nombre_alumno.strip():
            alias = payload.nombre_alumno.strip()[:50]
        else:
            existing = await db.query("usuarios",
                                      filters={"tipo_usuario": "alumno", "grupo": nombre_grupo})
            alias = f"Alumno {len(existing) + 1}"

        try:
            ts = int(payload.fecha_dispositivo) / 1000
            fecha_reg = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except Exception:
            fecha_reg = datetime.now(timezone.utc).isoformat()

        await db.insert("usuarios", {
            "id":              payload.uuid_estudiante,
            "nombre_completo": alias,
            "tipo_usuario":    "alumno",
            "grupo":           nombre_grupo,
            "grupo_id":        codigo["grupo_id"],
            "activo":          True,
            "fecha_registro":  fecha_reg,
        })
        return VincularResponse(
            mensaje="Dispositivo vinculado con éxito.",
            id_grupo=grupo_id,
        )

    async def sincronizar(self, db, payload: SincronizarRequest) -> SincronizarResponse:
        alumnos = await db.query("usuarios", filters={"id": payload.uuid_estudiante})
        if not alumnos:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="El dispositivo no está vinculado a ningún grupo.")
        puntos_base = alumnos[0].get("puntos_totales") or 0

        procesados = 0
        duplicados = 0
        puntos_nuevos = 0

        for evento in payload.eventos:
            if evento.id_mision == "presencia":
                continue
            fd = evento.fecha_dispositivo
            try:
                await db.insert("intentos_desafios", {
                    "usuario_id": payload.uuid_estudiante,
                    "nodo_id": evento.id_mision,
                    "es_correcta": evento.errores == 0,
                    "tiempo_respuesta": evento.segundos_jugados,
                    "puntos_obtenidos": evento.monedas_ganadas,
                    "fecha_intento": fd.isoformat() if hasattr(fd, "isoformat") else fd,
                    "sincronizado": True,
                })
                procesados += 1
                puntos_nuevos += evento.monedas_ganadas
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (409, 422, 400):
                    duplicados += 1
                else:
                    raise

        if puntos_nuevos > 0:
            await db.patch(
                "usuarios",
                {"id": payload.uuid_estudiante},
                {"puntos_totales": puntos_base + puntos_nuevos},
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
