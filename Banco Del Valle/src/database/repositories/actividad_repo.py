"""
Repositorio de Persistencia para Actividad Económica y Ciclo de Riesgo (EMAE / PBI).
Permite ajustar políticas de crédito según la fase del ciclo macroeconómico.
Referencia de diseño: docs/proyecciones_macro_actividad_economica.md
"""

from typing import List, Optional
import sqlite3

from src.domain.models import FaseCiclo, ProyeccionActividad


def _row_to_proyeccion(row: sqlite3.Row) -> ProyeccionActividad:
    """Convierte un registro sqlite3.Row a la entidad ProyeccionActividad."""
    return ProyeccionActividad(
        id=row["id"],
        fecha_relevamiento=row["fecha_relevamiento"],
        variacion_pbi_proyectada_anual=float(row["variacion_pbi_proyectada_anual"]),
        emae_ultimo_interanual=float(row["emae_ultimo_interanual"]),
        fase_ciclo=FaseCiclo(row["fase_ciclo"]),
        factor_macro_riesgo=float(row["factor_macro_riesgo"]),
    )


def registrar_proyeccion_actividad(conn: sqlite3.Connection, proyeccion: ProyeccionActividad) -> int:
    """Inserta una medición del ciclo de actividad económica y retorna su ID."""
    cursor = conn.cursor()
    fase_val = proyeccion.fase_ciclo.value if isinstance(proyeccion.fase_ciclo, FaseCiclo) else str(proyeccion.fase_ciclo)
    cursor.execute(
        """
        INSERT INTO proyecciones_actividad_economica (
            fecha_relevamiento, variacion_pbi_proyectada_anual,
            emae_ultimo_interanual, fase_ciclo, factor_macro_riesgo
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            proyeccion.fecha_relevamiento,
            proyeccion.variacion_pbi_proyectada_anual,
            proyeccion.emae_ultimo_interanual,
            fase_val,
            proyeccion.factor_macro_riesgo,
        ),
    )
    return cursor.lastrowid  # type: ignore


def obtener_ultima_proyeccion_actividad(conn: sqlite3.Connection) -> Optional[ProyeccionActividad]:
    """Recupera la última medición disponible de actividad económica (EMAE)."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM proyecciones_actividad_economica ORDER BY fecha_relevamiento DESC, id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    return _row_to_proyeccion(row) if row else None


def obtener_historico_actividad(conn: sqlite3.Connection, limite: int = 12) -> List[ProyeccionActividad]:
    """Retorna la serie cronológica de mediciones de actividad para análisis del ciclo."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM proyecciones_actividad_economica
        ORDER BY fecha_relevamiento DESC, id DESC
        LIMIT ?
        """,
        (limite,),
    )
    rows = cursor.fetchall()
    return [_row_to_proyeccion(r) for r in reversed(rows)]
