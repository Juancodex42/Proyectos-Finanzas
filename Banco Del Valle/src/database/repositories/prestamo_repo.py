"""
Repositorio de Persistencia para Préstamos Franceses y Cuotas de Amortización.
Gestiona contratos crediticios, cronogramas, mora y liquidaciones.
Referencia de diseño: docs/diagrama_plazos_fijos_flexibles_prestamos.md
"""

from typing import Any, Dict, List, Optional
import sqlite3

from src.domain.models import Cuota, EstadoPrestamo, Prestamo


def _row_to_prestamo(row: sqlite3.Row) -> Prestamo:
    """Convierte un registro sqlite3.Row a la entidad Prestamo."""
    return Prestamo(
        id=row["id"],
        persona_id=row["persona_id"],
        empresa_id=row["empresa_id"],
        tipo_credito=row["tipo_credito"],
        monto_capital=float(row["monto_capital"]),
        tasa_nominal_anual=float(row["tasa_nominal_anual"]),
        cantidad_cuotas=int(row["cantidad_cuotas"]),
        fecha_otorgamiento=row["fecha_otorgamiento"],
        estado=EstadoPrestamo(row["estado"]),
    )


def _row_to_cuota(row: sqlite3.Row) -> Cuota:
    """Convierte un registro sqlite3.Row a la entidad Cuota."""
    return Cuota(
        id=row["id"],
        prestamo_id=int(row["prestamo_id"]),
        numero_cuota=int(row["numero_cuota"]),
        monto_cuota=float(row["monto_cuota"]),
        fecha_vencimiento=row["fecha_vencimiento"],
        fecha_pago=row["fecha_pago"],
        dias_mora=int(row["dias_mora"]),
        intereses_punitorios=float(row["intereses_punitorios"]),
    )


def crear_prestamo(
    conn: sqlite3.Connection,
    prestamo: Prestamo,
    cronograma: Optional[List[Cuota]] = None,
) -> int:
    """Inserta un contrato de préstamo y opcionalmente su cronograma completo de cuotas."""
    cursor = conn.cursor()
    estado_val = prestamo.estado.value if isinstance(prestamo.estado, EstadoPrestamo) else str(prestamo.estado)
    cursor.execute(
        """
        INSERT INTO prestamos (
            persona_id, empresa_id, tipo_credito, monto_capital,
            tasa_nominal_anual, cantidad_cuotas, fecha_otorgamiento, estado
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            prestamo.persona_id,
            prestamo.empresa_id,
            prestamo.tipo_credito,
            round(prestamo.monto_capital, 2),
            prestamo.tasa_nominal_anual,
            prestamo.cantidad_cuotas,
            prestamo.fecha_otorgamiento,
            estado_val,
        ),
    )
    prestamo_id = cursor.lastrowid
    assert prestamo_id is not None

    if cronograma:
        for cuota in cronograma:
            cuota.prestamo_id = prestamo_id
            cursor.execute(
                """
                INSERT INTO cuotas (
                    prestamo_id, numero_cuota, monto_cuota,
                    fecha_vencimiento, fecha_pago, dias_mora, intereses_punitorios
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prestamo_id,
                    cuota.numero_cuota,
                    round(cuota.monto_cuota, 2),
                    cuota.fecha_vencimiento,
                    cuota.fecha_pago,
                    cuota.dias_mora,
                    round(cuota.intereses_punitorios, 2),
                ),
            )

    return prestamo_id


def insertar_cuotas(conn: sqlite3.Connection, cuotas: List[Cuota]) -> None:
    """Inserta en bloque una lista de cuotas asociadas a un préstamo existente."""
    cursor = conn.cursor()
    cursor.executemany(
        """
        INSERT INTO cuotas (
            prestamo_id, numero_cuota, monto_cuota,
            fecha_vencimiento, fecha_pago, dias_mora, intereses_punitorios
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                c.prestamo_id,
                c.numero_cuota,
                round(c.monto_cuota, 2),
                c.fecha_vencimiento,
                c.fecha_pago,
                c.dias_mora,
                round(c.intereses_punitorios, 2),
            )
            for c in cuotas
        ],
    )


def obtener_prestamo_por_id(conn: sqlite3.Connection, prestamo_id: int) -> Optional[Prestamo]:
    """Recupera un préstamo por su ID."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM prestamos WHERE id = ?", (prestamo_id,))
    row = cursor.fetchone()
    return _row_to_prestamo(row) if row else None


def obtener_prestamos_por_persona(conn: sqlite3.Connection, persona_id: int) -> List[Prestamo]:
    """Retorna todos los préstamos contraídos por una persona humana."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM prestamos WHERE persona_id = ? ORDER BY id DESC", (persona_id,))
    return [_row_to_prestamo(row) for row in cursor.fetchall()]


def obtener_prestamos_por_empresa(conn: sqlite3.Connection, empresa_id: int) -> List[Prestamo]:
    """Retorna todos los préstamos otorgados a una empresa."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM prestamos WHERE empresa_id = ? ORDER BY id DESC", (empresa_id,))
    return [_row_to_prestamo(row) for row in cursor.fetchall()]


def obtener_cuotas_por_prestamo(conn: sqlite3.Connection, prestamo_id: int) -> List[Cuota]:
    """Retorna el cronograma completo de cuotas de un préstamo ordenado por número."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cuotas WHERE prestamo_id = ? ORDER BY numero_cuota ASC", (prestamo_id,))
    return [_row_to_cuota(row) for row in cursor.fetchall()]


def obtener_prestamos_activos(conn: sqlite3.Connection) -> List[Prestamo]:
    """Retorna préstamos activos o en mora para procesos de seguimiento y cobro diario."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM prestamos WHERE estado IN ('ACTIVO', 'AL_DIA', 'EN_MORA') ORDER BY id ASC")
    return [_row_to_prestamo(row) for row in cursor.fetchall()]


def actualizar_estado_prestamo(conn: sqlite3.Connection, prestamo_id: int, nuevo_estado: EstadoPrestamo) -> None:
    """Actualiza el estado global del préstamo (AL_DIA, EN_MORA, CANCELADO)."""
    estado_val = nuevo_estado.value if isinstance(nuevo_estado, EstadoPrestamo) else str(nuevo_estado)
    conn.execute("UPDATE prestamos SET estado = ? WHERE id = ?", (estado_val, prestamo_id))


def actualizar_cuota(
    conn: sqlite3.Connection,
    cuota_id: int,
    fecha_pago: Optional[str],
    dias_mora: int,
    intereses_punitorios: float,
) -> None:
    """Actualiza el estado de cobranza, días de atraso e intereses punitorios de una cuota."""
    conn.execute(
        """
        UPDATE cuotas
        SET fecha_pago = ?, dias_mora = ?, intereses_punitorios = ?
        WHERE id = ?
        """,
        (fecha_pago, dias_mora, round(intereses_punitorios, 2), cuota_id),
    )


def obtener_total_prestado_activo(conn: sqlite3.Connection) -> float:
    """Calcula el saldo de capital vivo prestado por el banco (cartera activa)."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COALESCE(SUM(p.monto_capital), 0.0)
        FROM prestamos p
        WHERE p.estado IN ('ACTIVO', 'AL_DIA', 'EN_MORA')
        """
    )
    row = cursor.fetchone()
    return float(row[0]) if row else 0.0


def obtener_cuotas_pendientes_a_la_fecha(conn: sqlite3.Connection, fecha_corte: str) -> List[Cuota]:
    """Retorna cuotas impagas cuya fecha de vencimiento es anterior o igual a fecha_corte."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM cuotas
        WHERE fecha_pago IS NULL AND fecha_vencimiento <= ?
        ORDER BY fecha_vencimiento ASC
        """,
        (fecha_corte,),
    )
    return [_row_to_cuota(row) for row in cursor.fetchall()]


def obtener_prestamos_con_detalle_rango(
    conn: sqlite3.Connection, fecha_desde: str, fecha_hasta: str
) -> List[Dict[str, Any]]:
    """Exporta lista de préstamos con nombre/razón social del titular para auditoría y reportes."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.id, p.monto_capital, p.tasa_nominal_anual, p.cantidad_cuotas,
               p.fecha_otorgamiento, p.estado, p.tipo_credito,
               COALESCE(per.nombre_completo, emp.razon_social) AS titular,
               COALESCE(per.dni, emp.cuit) AS documento_fiscal
        FROM prestamos p
        LEFT JOIN personas per ON p.persona_id = per.id
        LEFT JOIN empresas emp ON p.empresa_id = emp.id
        WHERE p.fecha_otorgamiento >= ? AND p.fecha_otorgamiento <= ?
        ORDER BY p.fecha_otorgamiento DESC
        """,
        (fecha_desde, fecha_hasta),
    )
    return [dict(row) for row in cursor.fetchall()]
