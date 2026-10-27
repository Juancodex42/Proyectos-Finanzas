"""
Repositorio de Persistencia para Cuentas Transaccionales y Remuneradas.
Administra CBU, Alias, saldos líquidos y cálculo de agregados de encaje.
Referencia de diseño: docs/homebanking_ux_cuentas_sueldo.md
"""

from typing import List, Optional
import sqlite3

from src.domain.models import CuentaTransaccional, EstadoCuenta


def _row_to_cuenta(row: sqlite3.Row) -> CuentaTransaccional:
    """Convierte un registro sqlite3.Row a la entidad CuentaTransaccional."""
    return CuentaTransaccional(
        id=row["id"],
        persona_id=row["persona_id"],
        empresa_id=row["empresa_id"],
        cbu=row["cbu"],
        alias=row["alias"],
        saldo_actual=float(row["saldo_actual"]),
        tna_rendimiento_diario=float(row["tna_rendimiento_diario"]),
        es_cuenta_sueldo=bool(row["es_cuenta_sueldo"]),
        permite_extraccion_inmediata=bool(row["permite_extraccion_inmediata"]),
        estado=EstadoCuenta(row["estado"]),
    )


def crear_cuenta(conn: sqlite3.Connection, cuenta: CuentaTransaccional) -> int:
    """Inserta una nueva cuenta bancaria y retorna su ID."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO cuentas_transaccionales (
            persona_id, empresa_id, cbu, alias, saldo_actual,
            tna_rendimiento_diario, es_cuenta_sueldo, permite_extraccion_inmediata, estado
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cuenta.persona_id,
            cuenta.empresa_id,
            cuenta.cbu,
            cuenta.alias,
            cuenta.saldo_actual,
            cuenta.tna_rendimiento_diario,
            1 if cuenta.es_cuenta_sueldo else 0,
            1 if cuenta.permite_extraccion_inmediata else 0,
            cuenta.estado.value if isinstance(cuenta.estado, EstadoCuenta) else str(cuenta.estado),
        ),
    )
    return cursor.lastrowid  # type: ignore


def obtener_cuenta_por_id(conn: sqlite3.Connection, cuenta_id: int) -> Optional[CuentaTransaccional]:
    """Recupera una cuenta por su clave primaria."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cuentas_transaccionales WHERE id = ?", (cuenta_id,))
    row = cursor.fetchone()
    return _row_to_cuenta(row) if row else None


def obtener_cuenta_por_cbu(conn: sqlite3.Connection, cbu: str) -> Optional[CuentaTransaccional]:
    """Recupera una cuenta por su CBU único de 22 dígitos."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cuentas_transaccionales WHERE cbu = ?", (cbu,))
    row = cursor.fetchone()
    return _row_to_cuenta(row) if row else None


def obtener_cuenta_por_alias(conn: sqlite3.Connection, alias: str) -> Optional[CuentaTransaccional]:
    """Recupera una cuenta por su alias alfanumérico único."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cuentas_transaccionales WHERE UPPER(alias) = UPPER(?)", (alias.strip(),))
    row = cursor.fetchone()
    return _row_to_cuenta(row) if row else None


def obtener_cuentas_por_persona(conn: sqlite3.Connection, persona_id: int) -> List[CuentaTransaccional]:
    """Retorna todas las cuentas asociadas a una persona humana."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cuentas_transaccionales WHERE persona_id = ? ORDER BY id ASC", (persona_id,))
    return [_row_to_cuenta(row) for row in cursor.fetchall()]


def obtener_cuentas_por_empresa(conn: sqlite3.Connection, empresa_id: int) -> List[CuentaTransaccional]:
    """Retorna todas las cuentas asociadas a una empresa."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cuentas_transaccionales WHERE empresa_id = ? ORDER BY id ASC", (empresa_id,))
    return [_row_to_cuenta(row) for row in cursor.fetchall()]


def actualizar_saldo(conn: sqlite3.Connection, cuenta_id: int, nuevo_saldo: float) -> None:
    """Actualiza de forma atómica el saldo contable de una cuenta."""
    conn.execute(
        "UPDATE cuentas_transaccionales SET saldo_actual = ? WHERE id = ?",
        (round(nuevo_saldo, 2), cuenta_id),
    )


def actualizar_estado_cuenta(conn: sqlite3.Connection, cuenta_id: int, nuevo_estado: EstadoCuenta) -> None:
    """Actualiza el estado operativo de la cuenta (ACTIVA, SUSPENDIDO_AML, CERRADA)."""
    estado_val = nuevo_estado.value if isinstance(nuevo_estado, EstadoCuenta) else str(nuevo_estado)
    conn.execute("UPDATE cuentas_transaccionales SET estado = ? WHERE id = ?", (estado_val, cuenta_id))


def actualizar_tna_rendimiento(conn: sqlite3.Connection, cuenta_id: int, nueva_tna: float) -> None:
    """Actualiza la tasa remunerada aplicada al saldo diario flexible."""
    conn.execute(
        "UPDATE cuentas_transaccionales SET tna_rendimiento_diario = ? WHERE id = ?",
        (nueva_tna, cuenta_id),
    )


def sumar_saldos_cuentas_flexibles(conn: sqlite3.Connection) -> float:
    """Calcula la sumatoria total de saldos a la vista para el cálculo del encaje legal (30%)."""
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(SUM(saldo_actual), 0.0) FROM cuentas_transaccionales WHERE estado IN ('ACTIVA', 'ACTIVO')")
    row = cursor.fetchone()
    return float(row[0]) if row else 0.0


def listar_todas_cuentas_activas(conn: sqlite3.Connection) -> List[CuentaTransaccional]:
    """Retorna todas las cuentas transaccionales activas para el proceso de daily tick."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cuentas_transaccionales WHERE estado IN ('ACTIVA', 'ACTIVO') ORDER BY id ASC")
    return [_row_to_cuenta(row) for row in cursor.fetchall()]
