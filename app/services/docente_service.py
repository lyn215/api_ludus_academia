"""app/services/docente_service.py"""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.schemas.schemas import (
    AnaliticaGrupoResponse,
    CrearGrupoRequest,
    GenerarCodigoRequest,
    GenerarCodigoResponse,
    GrupoInfo,
    MetricaAlumno,
    MiPerfilResponse,
)
from app.services.estudiante_service import generar_codigo_ludu

settings = get_settings()

_FALLBACK_DT = None


def _is_mision_real(id_mision: str) -> bool:
    return id_mision.startswith("nivel_") or id_mision.startswith("L")


def _id_a_nivel(id_mision: str) -> str:
    if id_mision.startswith("nivel_"):
        return id_mision[:7]
    if len(id_mision) >= 2 and id_mision[0] == "L" and id_mision[1].isdigit():
        return f"nivel_{id_mision[1]}"
    return "otro"


class DocenteService:

    # ── Perfil y grupos ─────────────────────────────────────────────────────

    async def mi_perfil(self, db, supabase_uid: str, correo: str) -> MiPerfilResponse:
        grupos = await self._grupos_con_conteo(db, supabase_uid)
        return MiPerfilResponse(
            id=supabase_uid,
            correo=correo,
            nombre_completo=None,
            fecha_registro=datetime.now(timezone.utc),
            grupos=grupos,
            tiene_grupos=len(grupos) > 0,
        )

    async def listar_mis_grupos(self, db, supabase_uid: str, correo: str) -> list[GrupoInfo]:
        return await self._grupos_con_conteo(db, supabase_uid)

    async def crear_grupo(
        self, db, supabase_uid: str, correo: str, payload: CrearGrupoRequest
    ) -> GrupoInfo:
        data: dict = {
            "docente_id": supabase_uid,
            "nombre_grupo": payload.nombre_grupo,
        }
        if payload.nombre_escuela:
            data["nombre_escuela"] = payload.nombre_escuela
        nuevo = await db.insert("grupos", data)
        return GrupoInfo(
            id=nuevo["id"],
            nombre_grupo=nuevo["nombre_grupo"],
            docente_id=nuevo["docente_id"],
            codigo_acceso=nuevo.get("codigo_acceso"),
            activo=nuevo.get("activo", True),
            created_at=nuevo["created_at"],
            nombre_escuela=nuevo.get("nombre_escuela"),
            total_estudiantes=0,
        )

    # ── Alias del alumno ─────────────────────────────────────────────────────

    async def actualizar_alias(
        self, db, supabase_uid: str, correo: str, uuid_estudiante: str, alias: str
    ) -> dict:
        rows = await db.query("usuarios", filters={"id": uuid_estudiante, "tipo_usuario": "alumno"})
        if not rows:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Alumno no encontrado o sin permisos.")
        alumno = rows[0]
        grupo_nombre = alumno.get("grupo")
        if not grupo_nombre:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Alumno no encontrado o sin permisos.")
        grupos = await db.query("grupos", filters={"nombre_grupo": grupo_nombre})
        if not grupos or grupos[0]["docente_id"] != supabase_uid:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Alumno no encontrado o sin permisos.")
        alias_clean = alias.strip()
        await db.patch("usuarios", {"id": uuid_estudiante}, {"nombre_completo": alias_clean})
        return {"uuid": uuid_estudiante, "alias": alias_clean}

    # ── Códigos de vinculación ────────────────────────────────────────────────

    async def generar_codigo(
        self, db, supabase_uid: str, correo: str, payload: GenerarCodigoRequest
    ) -> GenerarCodigoResponse:
        grupos = await db.query("grupos", filters={"id": payload.id_grupo})
        if not grupos or grupos[0]["docente_id"] != supabase_uid:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="No tienes permisos para generar códigos en este grupo.")
        expira = datetime.now(timezone.utc) + timedelta(hours=payload.horas_validez)
        codigo_str = ""
        for _ in range(10):
            codigo_str = generar_codigo_ludu()
            if not await db.query("codigos_vinculacion", filters={"codigo": codigo_str}):
                break
        await db.insert("codigos_vinculacion", {
            "codigo": codigo_str,
            "grupo_id": payload.id_grupo,
            "expires_at": expira.isoformat(),
            "activo": True,
            "docente_id": supabase_uid,
        })
        return GenerarCodigoResponse(codigo_vinculacion=codigo_str, expires_at=expira)

    # ── Analítica ─────────────────────────────────────────────────────────────

    async def analitica_grupo(
        self, db, supabase_uid: str, correo: str, id_grupo: str, metrica: str | None
    ) -> AnaliticaGrupoResponse:
        grupos = await db.query("grupos", filters={"id": id_grupo})
        if not grupos or grupos[0]["docente_id"] != supabase_uid:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="No tienes permisos para consultar este grupo.")
        grupo = grupos[0]

        nombre_grupo = grupo["nombre_grupo"]
        alumnos = await db.query("usuarios", filters={
            "tipo_usuario": "alumno",
            "grupo_id": id_grupo,
        })
        metricas = []

        for alumno in alumnos:
            uid = alumno["id"]
            all_events = await db.query("intentos_desafios", filters={"usuario_id": uid})

            total_intentos = len(all_events)
            misiones_completas = len(set(e.get("nodo_id") for e in all_events if e.get("nodo_id")))
            errores_count = sum(1 for e in all_events if not e.get("es_correcta", True))
            prom_errores = (
                round(errores_count / total_intentos, 2) if total_intentos > 0 else 0.0
            )

            ultima_actividad = None
            if all_events:
                raw = max(
                    (e["fecha_intento"] for e in all_events if e.get("fecha_intento")),
                    default=None,
                )
                if raw:
                    ultima_actividad = (
                        datetime.fromisoformat(raw.replace("Z", "+00:00"))
                        if isinstance(raw, str) else raw
                    )

            acum: dict[str, int] = {}
            for e in all_events:
                nodo = e.get("nodo_id") or "otro"
                if not e.get("es_correcta", True):
                    acum[nodo] = acum.get(nodo, 0) + 1
            errores_por_nivel = {nodo: float(count) for nodo, count in acum.items()}

            metricas.append(MetricaAlumno(
                alias_alumno=alumno.get("nombre_completo") or uid[:8],
                uuid_estudiante=uid,
                misiones_completas=misiones_completas,
                promedio_errores=prom_errores,
                monedas_totales=alumno.get("puntos_totales", 0),
                ultima_actividad=ultima_actividad or _FALLBACK_DT,
                errores_por_nivel=errores_por_nivel,
            ))

        if metrica == "errores":
            metricas.sort(key=lambda m: m.promedio_errores, reverse=True)
        elif metrica == "progreso":
            metricas.sort(key=lambda m: m.misiones_completas, reverse=True)

        return AnaliticaGrupoResponse(
            id_grupo=id_grupo,
            nombre_grupo=grupo["nombre_grupo"],
            total_alumnos=len(metricas),
            metricas=metricas,
            generado_el=datetime.now(timezone.utc),
        )

    # ── Helper privado ────────────────────────────────────────────────────────

    async def _grupos_con_conteo(self, db, id_docente: str) -> list[GrupoInfo]:
        grupos = await db.query("grupos", filters={"docente_id": id_docente})
        result = []
        for grupo in grupos:
            try:
                estudiantes = await db.query("usuarios", filters={
                    "tipo_usuario": "alumno",
                    "grupo_id": grupo["id"],
                })
                count = len(estudiantes)
            except Exception:
                count = 0
            result.append(GrupoInfo(
                id=grupo["id"],
                nombre_grupo=grupo["nombre_grupo"],
                docente_id=grupo["docente_id"],
                codigo_acceso=grupo.get("codigo_acceso"),
                activo=grupo.get("activo", True),
                created_at=grupo["created_at"],
                nombre_escuela=grupo.get("nombre_escuela"),
                total_estudiantes=count,
            ))
        return result
