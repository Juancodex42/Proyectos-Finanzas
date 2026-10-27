"""
Repositorio de Persistencia para Inflación Esperada y Política Monetaria.
Almacena relevamientos del REM BCRA y consultoras para calibración de tasas.
Referencia de diseño: docs/proyecciones_inflacion_consultoras.md
"""

from typing import List, Optional
import sqlite3

from src.domain.models import ProyeccionInflacion


def _row_to_proyeccion(row: sqlite3.Row) -> ProyeccionInflacion:
    """Convierte un registro sqlite3.Row a la entidad ProyeccionInflacion."""
    return ProyeccionInflacion(
        id=row["id"],
        fecha_relevamiento=row["fecha_relevamiento"],
        inflacion_proyectada_12m=float(row["inflacion_proyectada_12m"]),
        fuente=row["fuente"],
        tasa_referencia_politica_monetaria=float(row["tasa_referencia_politica_monetaria"]),
    )


def registrar_proyeccion_inflacion(conn: sqlite3.Connection, proyeccion: ProyeccionInflacion) -> int:
    """Inserta un relevamiento de expectativas inflacionarias y retorna su ID."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO proyecciones_inflacion (
            fecha_relevamiento, inflacion_proyectada_12m, fuente, tasa_referencia_politica_monetaria
        ) VALUES (?, ?, ?, ?)
        """,
        (
            proyeccion.fecha_relevamiento,
            proyeccion.inflacion_proyectada_12m,
            proyeccion.fuente,
            proyeccion.tasa_referencia_politica_monetaria,
        ),
    )
    return cursor.lastrowid  # type: ignore


def obtener_ultima_proyeccion_inflacion(conn: sqlite3.Connection) -> Optional[ProyeccionInflacion]:
    """Recupera la proyección inflacionaria más reciente vigente."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM proyecciones_inflacion ORDER BY fecha_relevamiento DESC, id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    return _row_to_proyeccion(row) if row else None


def obtener_historico_inflacion(conn: sqlite3.Connection, limite: int = 12) -> List[ProyeccionInflacion]:
    """Retorna la serie histórica de inflación esperada ordenada cronológicamente."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM proyecciones_inflacion
        ORDER BY fecha_relevamiento DESC, id DESC
        LIMIT ?
        """,
        (limite,),
    )
    rows = cursor.fetchall()
    return [_row_to_proyeccion(r) for r in reversed(rows)]
