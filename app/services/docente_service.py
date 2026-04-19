"""app/services/docente_service.py"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import CodigoVinculacion, Docente, Estudiante, EventoAprendizaje, Grupo
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


class DocenteService:

    # ── Auto-provisioning ──────────────────────────────────────────────────

    async def obtener_o_crear_docente(
        self,
        db: AsyncSession,
        supabase_uid: str,
        correo: str = "",
    ) -> Docente:
        result = await db.execute(
            select(Docente).where(Docente.supabase_uid == supabase_uid)
        )
        docente = result.scalar_one_or_none()

        if not docente:
            docente = Docente(
                supabase_uid=supabase_uid,
                correo=correo or f"{supabase_uid[:8]}@supabase.local",
            )
            db.add(docente)
            await db.flush()

        return docente

    # ── Perfil y grupos ─────────────────────────────────────────────────────

    async def mi_perfil(
        self, db: AsyncSession, supabase_uid: str, correo: str
    ) -> MiPerfilResponse:
        docente = await self.obtener_o_crear_docente(db, supabase_uid, correo)
        grupos = await self._grupos_con_conteo(db, docente.id)
        return MiPerfilResponse(
            id=docente.id,
            correo=docente.correo,
            nombre_completo=docente.nombre_completo,
            fecha_registro=docente.fecha_registro,
            grupos=grupos,
            tiene_grupos=len(grupos) > 0,
        )

    async def listar_mis_grupos(
        self, db: AsyncSession, supabase_uid: str, correo: str
    ) -> list[GrupoInfo]:
        docente = await self.obtener_o_crear_docente(db, supabase_uid, correo)
        return await self._grupos_con_conteo(db, docente.id)

    async def crear_grupo(
        self,
        db: AsyncSession,
        supabase_uid: str,
        correo: str,
        payload: CrearGrupoRequest,
    ) -> GrupoInfo:
        docente = await self.obtener_o_crear_docente(db, supabase_uid, correo)
        nuevo_grupo = Grupo(
            id_docente=docente.id,
            nombre_grupo=payload.nombre_grupo,
            nombre_escuela=payload.nombre_escuela,
        )
        db.add(nuevo_grupo)
        await db.flush()
        return GrupoInfo(
            id_grupo=nuevo_grupo.id,
            nombre_grupo=nuevo_grupo.nombre_grupo,
            nombre_escuela=nuevo_grupo.nombre_escuela,
            total_alumnos=0,
        )

    # ── Códigos de vinculación ────────────────────────────────────────────────

    async def generar_codigo(
        self,
        db: AsyncSession,
        supabase_uid: str,
        correo: str,
        payload: GenerarCodigoRequest,
    ) -> GenerarCodigoResponse:
        docente = await self.obtener_o_crear_docente(db, supabase_uid, correo)
        grupo = await db.get(Grupo, payload.id_grupo)
        if not grupo or grupo.id_docente != docente.id:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para generar códigos en este grupo.",
            )
        expira = datetime.now(timezone.utc) + timedelta(hours=payload.horas_validez)
        for _ in range(10):
            codigo_str = generar_codigo_ludu()
            if not await db.get(CodigoVinculacion, codigo_str):
                break
        db.add(CodigoVinculacion(
            codigo=codigo_str,
            id_grupo=payload.id_grupo,
            expira_el=expira,
            esta_usado=False,
        ))
        return GenerarCodigoResponse(codigo_vinculacion=codigo_str, expira_el=expira)

    # ── Analítica ───────────────────────────────────────────────────────────────────────

    async def analitica_grupo(
        self,
        db: AsyncSession,
        supabase_uid: str,
        correo: str,
        id_grupo: int,
        metrica: str | None,
    ) -> AnaliticaGrupoResponse:
        docente = await self.obtener_o_crear_docente(db, supabase_uid, correo)
        grupo = await db.get(Grupo, id_grupo)
        if not grupo or grupo.id_docente != docente.id:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para consultar este grupo.",
            )
        result = await db.execute(
            select(Estudiante).where(Estudiante.id_grupo == id_grupo)
        )
        alumnos = result.scalars().all()

        metricas = []
        for alumno in alumnos:
            stats = await db.execute(
                select(
                    func.count(EventoAprendizaje.id_evento).label("total_misiones"),
                    func.coalesce(func.avg(EventoAprendizaje.errores), 0.0).label("prom_errores"),
                    func.max(EventoAprendizaje.fecha_servidor).label("ultima_actividad"),
                ).where(EventoAprendizaje.uuid_estudiante == alumno.uuid_estudiante)
            )
            row = stats.one()
            metricas.append(MetricaAlumno(
                alias_alumno=alumno.alias_estudiante or alumno.uuid_estudiante[:8],
                uuid_estudiante=alumno.uuid_estudiante,
                misiones_completas=row.total_misiones or 0,
                promedio_errores=round(float(row.prom_errores), 2),
                monedas_totales=alumno.monedas_totales,
                ultima_actividad=row.ultima_actividad or _FALLBACK_DT,
            ))

        if metrica == "errores":
            metricas.sort(key=lambda m: m.promedio_errores, reverse=True)
        elif metrica == "progreso":
            metricas.sort(key=lambda m: m.misiones_completas, reverse=True)

        return AnaliticaGrupoResponse(
            id_grupo=id_grupo,
            nombre_grupo=grupo.nombre_grupo,
            total_alumnos=len(metricas),
            metricas=metricas,
            generado_el=datetime.now(timezone.utc),
        )

    # ── Helper privado ──────────────────────────────────────────────────────────────

    async def _grupos_con_conteo(
        self, db: AsyncSession, id_docente: int
    ) -> list[GrupoInfo]:
        result = await db.execute(
            select(Grupo).where(Grupo.id_docente == id_docente)
        )
        grupos = result.scalars().all()
        respuesta = []
        for grupo in grupos:
            total = await db.scalar(
                select(func.count(Estudiante.uuid_estudiante))
                .where(Estudiante.id_grupo == grupo.id)
            ) or 0
            respuesta.append(GrupoInfo(
                id_grupo=grupo.id,
                nombre_grupo=grupo.nombre_grupo,
                nombre_escuela=grupo.nombre_escuela,
                total_alumnos=total,
            ))
        return respuesta
