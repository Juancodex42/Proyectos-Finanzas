"""
Repositorio de Persistencia para Plazos Fijos Tradicionales y Cuentas de Ahorro.
Gestiona imposiciones a término, devengamiento, encajes (12%) y liquidaciones.
Referencia de diseño: docs/diagrama_plazos_fijos_flexibles_prestamos.md
"""

from typing import Any, Dict, List, Optional
import sqlite3

from src.domain.models import EstadoPlazoFijo, PlazoFijo


def _row_to_plazo_fijo(row: sqlite3.Row) -> PlazoFijo:
    """Convierte un registro sqlite3.Row a la entidad PlazoFijo."""
    return PlazoFijo(
        id=row["id"],
        persona_id=row["persona_id"],
        empresa_id=row["empresa_id"],
        monto_depositado=float(row["monto_depositado"]),
        tasa_nominal_anual=float(row["tasa_nominal_anual"]),
        fecha_inicio=row["fecha_inicio"],
        fecha_vencimiento=row["fecha_vencimiento"],
        intereses_a_generar=float(row["intereses_a_generar"]),
        estado=EstadoPlazoFijo(row["estado"]),
    )


def crear_plazo_fijo(conn: sqlite3.Connection, plazo_fijo: PlazoFijo) -> int:
    """Inserta una nueva colocación a plazo fijo y retorna su ID."""
    cursor = conn.cursor()
    estado_val = plazo_fijo.estado.value if isinstance(plazo_fijo.estado, EstadoPlazoFijo) else str(plazo_fijo.estado)
    cursor.execute(
        """
        INSERT INTO plazos_fijos (
            persona_id, empresa_id, monto_depositado, tasa_nominal_anual,
            fecha_inicio, fecha_vencimiento, intereses_a_generar, estado
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            plazo_fijo.persona_id,
            plazo_fijo.empresa_id,
            round(plazo_fijo.monto_depositado, 2),
            plazo_fijo.tasa_nominal_anual,
            plazo_fijo.fecha_inicio,
            plazo_fijo.fecha_vencimiento,
            round(plazo_fijo.intereses_a_generar, 2),
            estado_val,
        ),
    )
    return cursor.lastrowid  # type: ignore


def obtener_plazo_fijo_por_id(conn: sqlite3.Connection, pf_id: int) -> Optional[PlazoFijo]:
    """Recupera un certificado de plazo fijo por ID."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM plazos_fijos WHERE id = ?", (pf_id,))
    row = cursor.fetchone()
    return _row_to_plazo_fijo(row) if row else None


def obtener_plazos_fijos_por_persona(conn: sqlite3.Connection, persona_id: int) -> List[PlazoFijo]:
    """Retorna los plazos fijos constituidos por una persona humana."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM plazos_fijos WHERE persona_id = ? ORDER BY id DESC", (persona_id,))
    return [_row_to_plazo_fijo(row) for row in cursor.fetchall()]


def obtener_plazos_fijos_por_empresa(conn: sqlite3.Connection, empresa_id: int) -> List[PlazoFijo]:
    """Retorna los plazos fijos constituidos por una empresa."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM plazos_fijos WHERE empresa_id = ? ORDER BY id DESC", (empresa_id,))
    return [_row_to_plazo_fijo(row) for row in cursor.fetchall()]


def obtener_plazos_fijos_activos(conn: sqlite3.Connection) -> List[PlazoFijo]:
    """Retorna los plazos fijos vigentes para devengamiento y cálculo de pasivos."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM plazos_fijos WHERE estado = 'ACTIVO' ORDER BY fecha_vencimiento ASC")
    return [_row_to_plazo_fijo(row) for row in cursor.fetchall()]


def obtener_plazos_fijos_vencidos_a_la_fecha(conn: sqlite3.Connection, fecha_corte: str) -> List[PlazoFijo]:
    """Retorna plazos fijos activos que alcanzaron su fecha de vencimiento."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM plazos_fijos
        WHERE estado = 'ACTIVO' AND fecha_vencimiento <= ?
        ORDER BY fecha_vencimiento ASC
        """,
        (fecha_corte,),
    )
    return [_row_to_plazo_fijo(row) for row in cursor.fetchall()]


def actualizar_estado_plazo_fijo(
    conn: sqlite3.Connection, pf_id: int, nuevo_estado: EstadoPlazoFijo
) -> None:
    """Actualiza el estado de la colocación (LIQUIDADO, CANCELADO_ANTICIPADO, VENCIDO)."""
    estado_val = nuevo_estado.value if isinstance(nuevo_estado, EstadoPlazoFijo) else str(nuevo_estado)
    conn.execute("UPDATE plazos_fijos SET estado = ? WHERE id = ?", (estado_val, pf_id))


def sumar_total_depositos_plazo_fijo_activos(conn: sqlite3.Connection) -> float:
    """Calcula el pasivo total por depósitos a plazo para cálculo de encaje legal (12%)."""
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(SUM(monto_depositado), 0.0) FROM plazos_fijos WHERE estado = 'ACTIVO'")
    row = cursor.fetchone()
    return float(row[0]) if row else 0.0


def listar_plazos_fijos_rango(
    conn: sqlite3.Connection, fecha_desde: str, fecha_hasta: str
) -> List[Dict[str, Any]]:
    """Exporta lista de plazos fijos constituidos con titular para auditoría y reportes."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT pf.id, pf.monto_depositado, pf.tasa_nominal_anual, pf.fecha_inicio,
               pf.fecha_vencimiento, pf.intereses_a_generar, pf.estado,
               COALESCE(per.nombre_completo, emp.razon_social) AS titular,
               COALESCE(per.dni, emp.cuit) AS documento_fiscal
        FROM plazos_fijos pf
        LEFT JOIN personas per ON pf.persona_id = per.id
        LEFT JOIN empresas emp ON pf.empresa_id = emp.id
        WHERE pf.fecha_inicio >= ? AND pf.fecha_inicio <= ?
        ORDER BY pf.fecha_inicio DESC
        """,
        (fecha_desde, fecha_hasta),
    )
    return [dict(row) for row in cursor.fetchall()]
