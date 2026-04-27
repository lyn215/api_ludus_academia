"""app/schemas/schemas.py"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ── Vinculación de dispositivo ─────────────────────────────────────────────

class VincularRequest(BaseModel):
    uuid_estudiante: str = Field(..., description="UUID generado por la app en el primer inicio")
    codigo_vinculacion: str = Field(..., min_length=6, max_length=6)
    nombre_alumno: str | None = None

    @field_validator("codigo_vinculacion")
    @classmethod
    def codigo_uppercase(cls, v: str) -> str:
        return v.upper().strip()


class VincularResponse(BaseModel):
    mensaje: str
    id_grupo: int


# ── Sincronización de progreso ──────────────────────────────────────────

class EventoAprendizajeIn(BaseModel):
    id_evento: str = Field(..., description="UUID del móvil — garantiza idempotencia")
    id_mision: str = Field(..., max_length=100)
    errores: int = Field(0, ge=0)
    segundos_jugados: int = Field(0, ge=0, le=86400)
    monedas_ganadas: int = Field(0, ge=0)
    fecha_dispositivo: datetime


class SincronizarRequest(BaseModel):
    uuid_estudiante: str
    eventos: list[EventoAprendizajeIn] = Field(..., min_length=1, max_length=100)


class SincronizarResponse(BaseModel):
    estado: Literal["exito"]
    eventos_procesados: int
    duplicados_ignorados: int


# ── Grupos ─────────────────────────────────────────────────────────────────────

class CrearGrupoRequest(BaseModel):
    nombre_grupo: str = Field(..., min_length=1, max_length=100)
    nombre_escuela: str = Field("Escuela 5 de Mayo de 1862", max_length=200)


class GrupoInfo(BaseModel):
    id_grupo: int
    nombre_grupo: str
    nombre_escuela: str
    total_alumnos: int = 0


# ── Perfil del docente ──────────────────────────────────────────────────

class MiPerfilResponse(BaseModel):
    id: int
    correo: str
    nombre_completo: str | None
    fecha_registro: datetime
    grupos: list[GrupoInfo]
    tiene_grupos: bool


# ── Alias del alumno ───────────────────────────────────────────────────────

class ActualizarAliasRequest(BaseModel):
    alias: str = Field(..., min_length=1, max_length=50)


# ── Generación de código de vinculación ───────────────────────────────────────

class GenerarCodigoRequest(BaseModel):
    id_grupo: int
    horas_validez: int = Field(24, ge=1, le=168)


class GenerarCodigoResponse(BaseModel):
    codigo_vinculacion: str
    expira_el: datetime


# ── Analítica de grupo ──────────────────────────────────────────────────────

class MetricaAlumno(BaseModel):
    alias_alumno: str
    uuid_estudiante: str | None = None
    misiones_completas: int
    promedio_errores: float
    monedas_totales: int
    ultima_actividad: datetime


class AnaliticaGrupoResponse(BaseModel):
    id_grupo: int
    nombre_grupo: str
    total_alumnos: int
    metricas: list[MetricaAlumno]
    generado_el: datetime


# ── Health ──────────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    estado: Literal["ok", "degradado"]
    version: str
    entorno: str
