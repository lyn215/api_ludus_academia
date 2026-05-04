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

_FALLBACK_DT = datetime(2000, 1, 1, tzinfo=timezone.utc)


def _is_mision_real(id_mision: str) -> bool:
    return id_mision.startswith("nivel_") or id_mision.startswith("L")


def _id_a_nivel(id_mision: str) -> str:
    if id_mision.startswith("nivel_"):
        return id_mision[:7]
    if len(id_mision) >= 2 and id_mision[0] == "L" and id_mision[1].isdigit():
        return f"nivel_{id_mision[1]}"
    return "otro"


class DocenteService:

    # ── Auto-provisioning ──────────────────────────────────────────────────

    async def obtener_o_crear_docente(self, db, supabase_uid: str, correo: str = "") -> dict:
        # El JWT sub coincide con usuarios.id en el patrón estándar de Supabase Auth
        rows = await db.query("usuarios", filters={"id": supabase_uid})
        if rows:
            return rows[0]
        # Fallback: buscar por email
        if correo:
            rows = await db.query("usuarios", filters={"email": correo})
            if rows:
                return rows[0]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario no registrado. Completa el registro antes de usar el dashboard.",
        )

    # ── Perfil y grupos ─────────────────────────────────────────────────────

    async def mi_perfil(self, db, supabase_uid: str, correo: str) -> MiPerfilResponse:
        docente = await self.obtener_o_crear_docente(db, supabase_uid, correo)
        grupos = await self._grupos_con_conteo(db, docente["id"])
        return MiPerfilResponse(
            id=docente["id"],
            correo=docente.get("email", correo),
            nombre_completo=docente.get("nombre_completo"),
            fecha_registro=docente.get("fecha_registro") or datetime.now(timezone.utc),
            grupos=grupos,
            tiene_grupos=len(grupos) > 0,
        )

    async def listar_mis_grupos(self, db, supabase_uid: str, correo: str) -> list[GrupoInfo]:
        docente = await self.obtener_o_crear_docente(db, supabase_uid, correo)
        return await self._grupos_con_conteo(db, docente["id"])

    async def crear_grupo(
        self, db, supabase_uid: str, correo: str, payload: CrearGrupoRequest
    ) -> GrupoInfo:
        docente = await self.obtener_o_crear_docente(db, supabase_uid, correo)
        nuevo = await db.insert("grupos", {
            "docente_id": docente["id"],
            "nombre_grupo": payload.nombre_grupo,
        })
        return GrupoInfo(
            id_grupo=nuevo["id"],
            nombre_grupo=nuevo["nombre_grupo"],
            total_alumnos=0,
        )

    # ── Alias del alumno ─────────────────────────────────────────────────────

    async def actualizar_alias(
        self, db, supabase_uid: str, correo: str, uuid_estudiante: str, alias: str
    ) -> dict:
        docente = await self.obtener_o_crear_docente(db, supabase_uid, correo)
        rows = await db.query("estudiantes", filters={"uuid_estudiante": uuid_estudiante})
        if not rows:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Alumno no encontrado o sin permisos.")
        grupos = await db.query("grupos", filters={"id": rows[0]["id_grupo"]})
        if not grupos or grupos[0]["docente_id"] != docente["id"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Alumno no encontrado o sin permisos.")
        alias_clean = alias.strip()
        await db.update("estudiantes", {"alias_estudiante": alias_clean},
                        {"uuid_estudiante": uuid_estudiante})
        return {"uuid": uuid_estudiante, "alias": alias_clean}

    # ── Códigos de vinculación ────────────────────────────────────────────────

    async def generar_codigo(
        self, db, supabase_uid: str, correo: str, payload: GenerarCodigoRequest
    ) -> GenerarCodigoResponse:
        docente = await self.obtener_o_crear_docente(db, supabase_uid, correo)
        grupos = await db.query("grupos", filters={"id": payload.id_grupo})
        if not grupos or grupos[0]["docente_id"] != docente["id"]:
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
            "id_grupo": payload.id_grupo,
            "expira_el": expira.isoformat(),
            "esta_usado": False,
        })
        return GenerarCodigoResponse(codigo_vinculacion=codigo_str, expira_el=expira)

    # ── Analítica ─────────────────────────────────────────────────────────────

    async def analitica_grupo(
        self, db, supabase_uid: str, correo: str, id_grupo: str, metrica: str | None
    ) -> AnaliticaGrupoResponse:
        docente = await self.obtener_o_crear_docente(db, supabase_uid, correo)
        grupos = await db.query("grupos", filters={"id": id_grupo})
        if not grupos or grupos[0]["docente_id"] != docente["id"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="No tienes permisos para consultar este grupo.")
        grupo = grupos[0]

        alumnos = await db.query("estudiantes", filters={"id_grupo": id_grupo})
        metricas = []

        for alumno in alumnos:
            uid = alumno["uuid_estudiante"]
            all_events = await db.query("eventos_aprendizaje", filters={"uuid_estudiante": uid})
            real_events = [e for e in all_events if _is_mision_real(e["id_mision"])]

            total_misiones = len(real_events)
            prom_errores = (
                round(sum(e.get("errores") or 0 for e in real_events) / total_misiones, 2)
                if total_misiones > 0 else 0.0
            )

            ultima_actividad = None
            if all_events:
                raw = max(
                    (e["fecha_dispositivo"] for e in all_events if e.get("fecha_dispositivo")),
                    default=None,
                )
                if raw:
                    ultima_actividad = (
                        datetime.fromisoformat(raw.replace("Z", "+00:00"))
                        if isinstance(raw, str) else raw
                    )

            acum: dict[str, list[float]] = {}
            for e in real_events:
                nivel = _id_a_nivel(e["id_mision"])
                if nivel != "otro":
                    acum.setdefault(nivel, []).append(float(e.get("errores") or 0))
            errores_por_nivel = {
                nivel: round(sum(vals) / len(vals), 2)
                for nivel, vals in acum.items()
            }

            metricas.append(MetricaAlumno(
                alias_alumno=alumno.get("alias_estudiante") or uid[:8],
                uuid_estudiante=uid,
                misiones_completas=total_misiones,
                promedio_errores=prom_errores,
                monedas_totales=alumno.get("monedas_totales", 0),
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
            estudiantes = await db.query("estudiantes", filters={"id_grupo": grupo["id"]})
            result.append(GrupoInfo(
                id_grupo=grupo["id"],
                nombre_grupo=grupo["nombre_grupo"],
                total_alumnos=len(estudiantes),
            ))
        return result
