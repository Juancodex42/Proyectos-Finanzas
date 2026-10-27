"""
Repositorio de Persistencia para Movimientos de Cuenta y Libro Contable.
Registra transacciones inmutables, alertas AML y exportaciones de extractos.
Referencia de diseño: docs/homebanking_ux_cuentas_sueldo.md
"""

from typing import Any, Dict, List, Optional
import sqlite3

from src.domain.models import MovimientoCuenta, TipoMovimiento


def _row_to_movimiento(row: sqlite3.Row) -> MovimientoCuenta:
    """Convierte un registro sqlite3.Row a la entidad MovimientoCuenta."""
    return MovimientoCuenta(
        id=row["id"],
        cuenta_id=int(row["cuenta_id"]),
        tipo_movimiento=TipoMovimiento(row["tipo_movimiento"]),
        monto=float(row["monto"]),
        saldo_posterior=float(row["saldo_posterior"]),
        fecha_hora=row["fecha_hora"],
        descripcion=row["descripcion"],
        alerta_aml=int(row["alerta_aml"]),
    )


def registrar_movimiento(conn: sqlite3.Connection, movimiento: MovimientoCuenta) -> int:
    """Inserta un movimiento en el libro contable inmutable y retorna su ID."""
    cursor = conn.cursor()
    tipo_val = movimiento.tipo_movimiento.value if isinstance(movimiento.tipo_movimiento, TipoMovimiento) else str(movimiento.tipo_movimiento)
    cursor.execute(
        """
        INSERT INTO movimientos_cuenta (
            cuenta_id, tipo_movimiento, monto, saldo_posterior, fecha_hora, descripcion, alerta_aml
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            movimiento.cuenta_id,
            tipo_val,
            round(movimiento.monto, 2),
            round(movimiento.saldo_posterior, 2),
            movimiento.fecha_hora,
            movimiento.descripcion,
            1 if movimiento.alerta_aml else 0,
        ),
    )
    return cursor.lastrowid  # type: ignore


def obtener_movimientos_por_cuenta(
    conn: sqlite3.Connection, cuenta_id: int, limite: int = 100, offset: int = 0
) -> List[MovimientoCuenta]:
    """Recupera los movimientos de una cuenta ordenados cronológicamente descendente."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM movimientos_cuenta
        WHERE cuenta_id = ?
        ORDER BY fecha_hora DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (cuenta_id, limite, offset),
    )
    return [_row_to_movimiento(row) for row in cursor.fetchall()]


def obtener_movimientos_por_rango_fechas(
    conn: sqlite3.Connection, cuenta_id: int, fecha_desde: str, fecha_hasta: str
) -> List[MovimientoCuenta]:
    """Recupera movimientos de una cuenta filtrados por rango de fechas (ISO YYYY-MM-DD)."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM movimientos_cuenta
        WHERE cuenta_id = ?
          AND substr(fecha_hora, 1, 10) >= ?
          AND substr(fecha_hora, 1, 10) <= ?
        ORDER BY fecha_hora ASC, id ASC
        """,
        (cuenta_id, fecha_desde, fecha_hasta),
    )
    return [_row_to_movimiento(row) for row in cursor.fetchall()]


def obtener_movimientos_con_alerta_aml(conn: sqlite3.Connection, limite: int = 100) -> List[MovimientoCuenta]:
    """Recupera movimientos marcados con sospecha AML/UIF para auditoría de cumplimiento."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM movimientos_cuenta
        WHERE alerta_aml = 1
        ORDER BY fecha_hora DESC
        LIMIT ?
        """,
        (limite,),
    )
    return [_row_to_movimiento(row) for row in cursor.fetchall()]


def listar_todos_movimientos_rango(
    conn: sqlite3.Connection, fecha_desde: str, fecha_hasta: str, limite: int = 500
) -> List[Dict[str, Any]]:
    """Exporta lista consolidada de movimientos bancarios con CBU/Alias para reportes."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT m.id, m.fecha_hora, m.tipo_movimiento, m.monto, m.saldo_posterior,
               m.descripcion, m.alerta_aml, c.cbu, c.alias
        FROM movimientos_cuenta m
        JOIN cuentas_transaccionales c ON m.cuenta_id = c.id
        WHERE substr(m.fecha_hora, 1, 10) >= ?
          AND substr(m.fecha_hora, 1, 10) <= ?
        ORDER BY m.fecha_hora DESC
        LIMIT ?
        """,
        (fecha_desde, fecha_hasta, limite),
    )
    return [dict(row) for row in cursor.fetchall()]
