"""
Repositorio de Persistencia para Personas Jurídicas / PyMEs.
Operaciones CRUD y seguimiento de garantías en tabla 'empresas'.
Referencia de diseño: docs/diagrama_usuarios_empresas_aml_bloqueos.md
"""

from typing import List, Optional
import sqlite3

from src.domain.models import Empresa, EstadoCuenta, HistorialVeraz, TipoSocietario


def _row_to_empresa(row: sqlite3.Row) -> Empresa:
    """Convierte un registro sqlite3.Row a la entidad de dominio Empresa."""
    return Empresa(
        id=row["id"],
        cuit=row["cuit"],
        razon_social=row["razon_social"],
        tipo_societario=TipoSocietario(row["tipo_societario"]),
        rubro_actividad=row["rubro_actividad"],
        localidad=row["localidad"],
        facturacion_anual_comprobada=float(row["facturacion_anual_comprobada"]),
        requiere_fianza_socios=bool(row["requiere_fianza_socios"]),
        exencion_impositiva=bool(row["exencion_impositiva"]),
        estado_cuenta=EstadoCuenta(row["estado_cuenta"]),
        fecha_alta=row["fecha_alta"],
    )


def crear_empresa(conn: sqlite3.Connection, empresa: Empresa) -> int:
    """Inserta una nueva Persona Jurídica / PyME y retorna su ID."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO empresas (
            cuit, razon_social, tipo_societario, rubro_actividad,
            localidad, facturacion_anual_comprobada, requiere_fianza_socios,
            exencion_impositiva, estado_cuenta, fecha_alta
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            empresa.cuit,
            empresa.razon_social,
            empresa.tipo_societario.value if isinstance(empresa.tipo_societario, TipoSocietario) else str(empresa.tipo_societario),
            empresa.rubro_actividad,
            empresa.localidad,
            empresa.facturacion_anual_comprobada,
            1 if empresa.requiere_fianza_socios else 0,
            1 if empresa.exencion_impositiva else 0,
            empresa.estado_cuenta.value if isinstance(empresa.estado_cuenta, EstadoCuenta) else str(empresa.estado_cuenta),
            empresa.fecha_alta,
        ),
    )
    return cursor.lastrowid  # type: ignore


def obtener_empresa_por_id(conn: sqlite3.Connection, empresa_id: int) -> Optional[Empresa]:
    """Recupera una empresa por su ID de clave primaria."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM empresas WHERE id = ?", (empresa_id,))
    row = cursor.fetchone()
    return _row_to_empresa(row) if row else None


def obtener_empresa_por_cuit(conn: sqlite3.Connection, cuit: str) -> Optional[Empresa]:
    """Recupera una empresa por su CUIT tributario único."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM empresas WHERE cuit = ?", (cuit,))
    row = cursor.fetchone()
    return _row_to_empresa(row) if row else None


def actualizar_estado_empresa(conn: sqlite3.Connection, empresa_id: int, nuevo_estado: EstadoCuenta) -> None:
    """Actualiza el estado regulatorio AML o comercial de la empresa."""
    estado_val = nuevo_estado.value if isinstance(nuevo_estado, EstadoCuenta) else str(nuevo_estado)
    conn.execute("UPDATE empresas SET estado_cuenta = ? WHERE id = ?", (estado_val, empresa_id))


def actualizar_datos_financieros(
    conn: sqlite3.Connection,
    empresa_id: int,
    facturacion_anual: float,
    requiere_fianza: bool,
    exencion_impositiva: bool,
) -> None:
    """Actualiza la facturación auditada, requisito de fianza solidaria y exención fiscal."""
    conn.execute(
        """
        UPDATE empresas
        SET facturacion_anual_comprobada = ?,
            requiere_fianza_socios = ?,
            exencion_impositiva = ?
        WHERE id = ?
        """,
        (facturacion_anual, 1 if requiere_fianza else 0, 1 if exencion_impositiva else 0, empresa_id),
    )


def listar_empresas(conn: sqlite3.Connection, limite: int = 100, offset: int = 0) -> List[Empresa]:
    """Retorna una lista paginada de empresas registradas."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM empresas ORDER BY id ASC LIMIT ? OFFSET ?", (limite, offset))
    return [_row_to_empresa(row) for row in cursor.fetchall()]


def obtener_historial_veraz_empresa(conn: sqlite3.Connection, empresa_id: int) -> Optional[HistorialVeraz]:
    """Obtiene el último reporte de buró externo para la empresa especificada."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM historial_veraz_externo
        WHERE empresa_id = ?
        ORDER BY id DESC LIMIT 1
        """,
        (empresa_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return HistorialVeraz(
        id=row["id"],
        persona_id=row["persona_id"],
        empresa_id=row["empresa_id"],
        fecha_consulta=row["fecha_consulta"],
        score_externo=int(row["score_externo"]),
        peor_situacion_bcra=int(row["peor_situacion_bcra"]),
        monto_deuda_externa_total=float(row["monto_deuda_externa_total"]),
        cantidad_bancos_acreedores=int(row["cantidad_bancos_acreedores"]),
        cheques_rechazados_monto=float(row["cheques_rechazados_monto"]),
    )
