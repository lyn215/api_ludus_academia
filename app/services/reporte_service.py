"""app/services/reporte_service.py"""
import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Estudiante, EventoAprendizaje
from app.services.docente_service import _MISION_REAL, _id_a_nivel

# ── Constantes pedagógicas ─────────────────────────────────────────────────

NOMBRES_NIVEL = {
    "nivel_0": "Tutorial — El Claro del Despertar",
    "nivel_1": "Nivel 1 — Praderas de la Adición",
    "nivel_2": "Nivel 2 — Minas de la Multiplicación",
    "nivel_3": "Nivel 3 — Templo de los Triángulos",
    "nivel_4": "Nivel 4 — Valle del Cronos",
    "nivel_5": "Nivel 5 — Cascada de las Fracciones",
}

_VERDE = colors.HexColor("#315C4D")
_CREMA = colors.HexColor("#F5F1E3")


def _interpretar_nivel(prom: float) -> tuple[str, str]:
    if prom <= 1.0:
        return (
            "✓ Dominio satisfactorio",
            "El alumno demuestra comprensión sólida de este tema.",
        )
    elif prom <= 3.0:
        return (
            "△ Área de oportunidad",
            "Se recomienda practicar ejercicios adicionales "
            "para consolidar el aprendizaje.",
        )
    else:
        return (
            "✗ Requiere atención",
            "Se recomienda reforzar este tema con el docente "
            "antes de avanzar al siguiente nivel.",
        )


def _nivel_avance(misiones: int) -> str:
    if misiones >= 36:
        return "Avanzado"
    elif misiones >= 15:
        return "En progreso"
    else:
        return "Inicial"


def _observacion_general(misiones: int) -> str:
    if misiones >= 36:
        return (
            "El alumno muestra un avance destacado en el programa. "
            "Se recomienda continuar con el ritmo actual y explorar "
            "los niveles de mayor complejidad."
        )
    elif misiones >= 15:
        return (
            "El alumno se encuentra en progreso dentro del programa. "
            "Continuar fomentando la práctica regular para consolidar "
            "las áreas con mayor número de errores."
        )
    else:
        return (
            "El alumno se encuentra en etapa inicial del programa. "
            "Se recomienda acompañar las primeras sesiones para "
            "familiarizarse con la mecánica del juego y los contenidos."
        )


class ReporteService:

    async def generar_pdf(
        self, db: AsyncSession, estudiante: Estudiante, nombre_grupo: str
    ) -> bytes:
        uid = estudiante.uuid_estudiante

        # Misiones reales: count + promedio errores (excluye eventos técnicos)
        stats = await db.execute(
            select(
                func.count(EventoAprendizaje.id_evento).label("total"),
                func.coalesce(func.avg(EventoAprendizaje.errores), 0.0).label("prom_errores"),
            ).where(
                EventoAprendizaje.uuid_estudiante == uid,
                _MISION_REAL,
            )
        )
        row = stats.one()
        misiones = row.total or 0
        prom_errores = round(float(row.prom_errores), 2)

        # Última actividad por fecha_dispositivo (todos los eventos)
        ultima_actividad = await db.scalar(
            select(func.max(EventoAprendizaje.fecha_dispositivo))
            .where(EventoAprendizaje.uuid_estudiante == uid)
        )

        # Desglose de errores por nivel temático
        desglose = await db.execute(
            select(
                EventoAprendizaje.id_mision,
                func.coalesce(func.avg(EventoAprendizaje.errores), 0.0).label("prom"),
            )
            .where(
                EventoAprendizaje.uuid_estudiante == uid,
                _MISION_REAL,
            )
            .group_by(EventoAprendizaje.id_mision)
        )
        acum: dict[str, list[float]] = {}
        for fila in desglose.all():
            nivel = _id_a_nivel(fila.id_mision)
            if nivel == "otro":
                continue
            acum.setdefault(nivel, []).append(float(fila.prom))
        errores_por_nivel = {
            nivel: round(sum(vals) / len(vals), 2)
            for nivel, vals in acum.items()
        }

        # ── Alias y fechas ─────────────────────────────────────────────────
        alias = estudiante.alias_estudiante or uid[:8]
        fecha_generacion = datetime.now(timezone.utc).strftime("%d/%m/%Y")
        ua_str = (
            ultima_actividad.strftime("%d/%m/%Y %H:%M")
            if ultima_actividad
            else "Sin actividad registrada"
        )

        # ── ReportLab ──────────────────────────────────────────────────────
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=letter,
            rightMargin=inch, leftMargin=inch,
            topMargin=inch, bottomMargin=inch,
        )
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "LTitle", parent=styles["Normal"],
            fontName="Helvetica-Bold", fontSize=16,
            textColor=_VERDE, spaceAfter=4,
        )
        subtitle_style = ParagraphStyle(
            "LSubtitle", parent=styles["Normal"],
            fontSize=12, spaceAfter=12,
        )
        section_style = ParagraphStyle(
            "LSection", parent=styles["Normal"],
            fontName="Helvetica-Bold", fontSize=11,
            textColor=_VERDE, spaceBefore=14, spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "LBody", parent=styles["Normal"],
            fontSize=9, spaceAfter=4,
        )
        bold_body_style = ParagraphStyle(
            "LBoldBody", parent=styles["Normal"],
            fontName="Helvetica-Bold", fontSize=9, spaceAfter=2,
        )
        footer_style = ParagraphStyle(
            "LFooter", parent=styles["Normal"],
            fontSize=7, textColor=colors.grey, alignment=1, spaceAfter=2,
        )

        _header_ts = TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), _VERDE),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ])

        story = []

        # ── SECCIÓN 1 — Encabezado ─────────────────────────────────────────
        story.append(Paragraph("LudusAcademia+", title_style))
        story.append(Paragraph("Reporte de Desempeño Académico Individual", subtitle_style))
        story.append(Spacer(1, 0.15 * inch))

        info_table = Table(
            [
                ["Alumno", alias],
                ["Grupo", nombre_grupo],
                ["Fecha de generación", fecha_generacion],
                ["Última actividad", ua_str],
            ],
            colWidths=[2.2 * inch, 4.0 * inch],
        )
        info_table.setStyle(_header_ts)
        story.append(info_table)

        # ── SECCIÓN 2 — Resumen ejecutivo ──────────────────────────────────
        story.append(Paragraph("Resumen Ejecutivo", section_style))

        resumen_table = Table(
            [
                ["Misiones completadas", f"{misiones} de 6"],
                ["Promedio general errores", f"{prom_errores:.2f}"],
                ["Monedas recolectadas", str(estudiante.monedas_totales)],
                ["Nivel de avance", _nivel_avance(misiones)],
            ],
            colWidths=[2.2 * inch, 4.0 * inch],
        )
        resumen_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _CREMA),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ]))
        story.append(resumen_table)

        # ── SECCIÓN 3 — Desempeño por área temática ───────────────────────
        story.append(Paragraph("Desempeño por Área Temática", section_style))

        _sep = HRFlowable(
            width="100%", thickness=0.5,
            color=colors.HexColor("#CCCCCC"),
            spaceBefore=4, spaceAfter=4,
        )
        for i, (clave, nombre) in enumerate(NOMBRES_NIVEL.items()):
            if i > 0:
                story.append(_sep)
            story.append(Paragraph(nombre, bold_body_style))
            if clave in errores_por_nivel:
                prom = errores_por_nivel[clave]
                etiqueta, interpretacion = _interpretar_nivel(prom)
                story.append(Paragraph(f"Promedio de errores: {prom:.2f}", body_style))
                story.append(Paragraph(f"<b>{etiqueta}</b> — {interpretacion}", body_style))
            else:
                story.append(Paragraph("Sin actividad registrada en este tema.", body_style))

        # ── SECCIÓN 4 — Observaciones generales ───────────────────────────
        story.append(Paragraph("Observaciones Generales", section_style))
        story.append(Paragraph(_observacion_general(misiones), body_style))

        # ── SECCIÓN 5 — Pie de página ──────────────────────────────────────
        story.append(Spacer(1, 0.3 * inch))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        story.append(Spacer(1, 0.08 * inch))
        story.append(Paragraph(
            "Generado por LudusAcademia+ — Herramienta de apoyo pedagógico",
            footer_style,
        ))
        story.append(Paragraph(
            "Este reporte es confidencial y para uso exclusivo del docente.",
            footer_style,
        ))
        story.append(Paragraph(
            "Escuela Primaria 5 de Mayo de 1862 — Huauchinango, Puebla",
            footer_style,
        ))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
