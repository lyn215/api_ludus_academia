"""app/models/bancos.py"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BancoPregunta(Base):
    __tablename__ = "bancos_preguntas"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre              = Column(String(100), nullable=False)
    descripcion         = Column(Text)
    materia             = Column(String(50), nullable=False)
    nivel_grado         = Column(Integer)
    activo              = Column(Boolean, default=True, nullable=False)
    version             = Column(Integer, default=1, nullable=False)
    fecha_creacion      = Column(String, default=_utcnow)   # TIMESTAMP gestionado por Supabase
    fecha_actualizacion = Column(String, default=_utcnow, onupdate=_utcnow)
    creado_por          = Column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    es_oficial          = Column(Boolean, default=False, nullable=False)

    asignaciones = relationship("BancoPreguntaAsignacion", back_populates="banco", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<BancoPregunta id={self.id} nombre={self.nombre!r}>"


class Pregunta(Base):
    __tablename__ = "preguntas"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    texto_pregunta  = Column(Text, nullable=False)
    tipo_pregunta   = Column(String(50), nullable=False)
    materia         = Column(String(50), nullable=False)
    dificultad      = Column(Integer)
    pista_texto     = Column(Text)
    explicacion     = Column(Text)
    media_url       = Column(Text)
    nodo_asociado   = Column(UUID(as_uuid=True), ForeignKey("nodos.id", ondelete="SET NULL"), nullable=True)
    activo          = Column(Boolean, default=True, nullable=False)
    fecha_creacion  = Column(String, default=_utcnow)
    creado_por      = Column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)

    opciones     = relationship("OpcionRespuesta", back_populates="pregunta", cascade="all, delete-orphan")
    asignaciones = relationship("BancoPreguntaAsignacion", back_populates="pregunta")

    def __repr__(self) -> str:
        preview = self.texto_pregunta[:40] if self.texto_pregunta else ""
        return f"<Pregunta id={self.id} texto={preview!r}>"


class OpcionRespuesta(Base):
    __tablename__ = "opciones_respuesta"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pregunta_id         = Column(UUID(as_uuid=True), ForeignKey("preguntas.id", ondelete="CASCADE"), nullable=False)
    texto_opcion        = Column(Text, nullable=False)
    es_correcta         = Column(Boolean, default=False, nullable=False)
    orden               = Column(Integer)
    feedback_especifico = Column(Text)

    pregunta = relationship("Pregunta", back_populates="opciones")

    def __repr__(self) -> str:
        return f"<OpcionRespuesta id={self.id} correcta={self.es_correcta}>"


class BancoPreguntaAsignacion(Base):
    __tablename__ = "banco_pregunta_asignacion"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    banco_id       = Column(UUID(as_uuid=True), ForeignKey("bancos_preguntas.id", ondelete="CASCADE"), nullable=False)
    pregunta_id    = Column(UUID(as_uuid=True), ForeignKey("preguntas.id", ondelete="CASCADE"), nullable=False)
    orden_en_banco = Column(Integer)

    banco    = relationship("BancoPregunta", back_populates="asignaciones")
    pregunta = relationship("Pregunta", back_populates="asignaciones")

    __table_args__ = (
        UniqueConstraint("banco_id", "pregunta_id", name="uq_banco_pregunta"),
    )

    def __repr__(self) -> str:
        return f"<BancoPreguntaAsignacion banco={self.banco_id} pregunta={self.pregunta_id}>"
