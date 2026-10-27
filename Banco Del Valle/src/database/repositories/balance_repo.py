"""
Repositorio de Persistencia para Balance Contable, Encajes y Patrimonio Neto.
Guarda snapshots diarios de solvencia para KPIs gerenciales y auditoría BCRA.
Referencia de diseño: docs/normativa_encajes_bcra.md
"""

from typing import List, Optional
import sqlite3

from src.domain.models import BalancePatrimonio


def _row_to_balance(row: sqlite3.Row) -> BalancePatrimonio:
    """Convierte un registro sqlite3.Row a la entidad BalancePatrimonio."""
    return BalancePatrimonio(
        id=row["id"],
        fecha_corte=row["fecha_corte"],
        total_depositos_plazo_fijo=float(row["total_depositos_plazo_fijo"]),
        total_depositos_flexibles=float(row["total_depositos_flexibles"]),
        encaje_obligatorio_bcra=float(row["encaje_obligatorio_bcra"]),
        capital_propio_patrimonio=float(row["capital_propio_patrimonio"]),
        total_prestado_activo=float(row["total_prestado_activo"]),
        cashflow_seguro_prestable=float(row["cashflow_seguro_prestable"]),
    )


def registrar_snapshot_balance(conn: sqlite3.Connection, balance: BalancePatrimonio) -> int:
    """Inserta una fotografía diaria del balance bancario y retorna su ID."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO balance_patrimonio_banco (
            fecha_corte, total_depositos_plazo_fijo, total_depositos_flexibles,
            encaje_obligatorio_bcra, capital_propio_patrimonio, total_prestado_activo,
            cashflow_seguro_prestable
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            balance.fecha_corte,
            round(balance.total_depositos_plazo_fijo, 2),
            round(balance.total_depositos_flexibles, 2),
            round(balance.encaje_obligatorio_bcra, 2),
            round(balance.capital_propio_patrimonio, 2),
            round(balance.total_prestado_activo, 2),
            round(balance.cashflow_seguro_prestable, 2),
        ),
    )
    return cursor.lastrowid  # type: ignore


def obtener_ultimo_balance(conn: sqlite3.Connection) -> Optional[BalancePatrimonio]:
    """Recupera el snapshot más reciente del balance patrimonial."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM balance_patrimonio_banco ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    return _row_to_balance(row) if row else None


def obtener_historico_balances(
    conn: sqlite3.Connection,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    limite: int = 365,
) -> List[BalancePatrimonio]:
    """Retorna una serie temporal de balances diarios para gráficas de evolución patrimonial."""
    cursor = conn.cursor()
    if fecha_desde and fecha_hasta:
        cursor.execute(
            """
            SELECT * FROM balance_patrimonio_banco
            WHERE fecha_corte >= ? AND fecha_corte <= ?
            ORDER BY fecha_corte ASC, id ASC
            LIMIT ?
            """,
            (fecha_desde, fecha_hasta, limite),
        )
    else:
        cursor.execute(
            """
            SELECT * FROM balance_patrimonio_banco
            ORDER BY fecha_corte DESC, id DESC
            LIMIT ?
            """,
            (limite,),
        )
        rows = cursor.fetchall()
        return [_row_to_balance(r) for r in reversed(rows)]

    return [_row_to_balance(r) for r in cursor.fetchall()]


def actualizar_capital_propio(conn: sqlite3.Connection, balance_id: int, nuevo_capital: float) -> None:
    """Actualiza el capital propio de un snapshot específico tras capitalización de utilidades."""
    conn.execute(
        "UPDATE balance_patrimonio_banco SET capital_propio_patrimonio = ? WHERE id = ?",
        (round(nuevo_capital, 2), balance_id),
    )
