"""
Gestor de conexiones SQLite, transacciones atómicas ACID y semilla de datos.
Provee conexión en modo WAL, integridad referencial y carga inicial de clientes demo.
Referencia de diseño: docs/homebanking_ux_cuentas_sueldo.md
"""

from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Generator, Optional
import os
import bcrypt
import sqlite3

from src.config import (
    DB_PATH,
    SCHEMA_PATH,
    CAPITAL_PATRIMONIO_INICIAL,
    COLCHON_LIQUIDEZ_SEGURIDAD,
    ENCAJE_FLEXIBLE_PCT,
    TNA_FLEXIBLE_BASE,
)


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Crea y retorna una conexión configurada a la base de datos SQLite."""
    target_path = db_path or os.getenv("BANCO_DB_PATH") or DB_PATH
    Path(target_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(target_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


@contextmanager
def transaction(
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str] = None
) -> Generator[sqlite3.Connection, None, None]:
    """Context manager para ejecutar operaciones atómicas ACID con auto-commit/rollback."""
    owns_connection = False
    if conn is None:
        conn = get_db_connection(db_path)
        owns_connection = True

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if owns_connection:
            conn.close()


def _hash_password(raw_password: str) -> str:
    """Genera hash seguro Bcrypt con salt automático."""
    return bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def seed_initial_data(conn: sqlite3.Connection) -> None:
    """Siembra los registros de demostración requeridos por la arquitectura y UX."""
    cursor = conn.cursor()

    # Verificar si Juan José Gonzalez ya fue sembrado
    cursor.execute("SELECT id FROM personas WHERE dni = ?", ("35123456",))
    if cursor.fetchone() is not None:
        return

    today_iso = "2026-10-26"
    now_iso = "2026-10-26 09:00:00"

    # 1. Persona Humana: Juan José Gonzalez (Catamarca)
    cursor.execute(
        """
        INSERT INTO personas (
            dni, nombre_completo, localidad, categoria_laboral,
            antiguedad_laboral_meses, ingreso_mensual_comprobado,
            monto_sueldo_acreditado, dia_cobro_sueldo, estado_cuenta, fecha_alta
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "35123456",
            "Juan José Gonzalez",
            "San Fernando del Valle de Catamarca",
            "EMPLEADO_PRIVADO",
            48,
            3000000.0,
            3000000.0,
            1,
            "ACTIVO",
            today_iso,
        ),
    )
    persona_id = cursor.lastrowid

    # 2. Cuenta Transaccional Sueldo / Flexible de Juan José
    cursor.execute(
        """
        INSERT INTO cuentas_transaccionales (
            persona_id, empresa_id, cbu, alias, saldo_actual,
            tna_rendimiento_diario, es_cuenta_sueldo, permite_extraccion_inmediata, estado
        ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            persona_id,
            "2850001211100012345678",
            "JUAN.BANCO.VALLE",
            3000000.0,
            TNA_FLEXIBLE_BASE,
            1,
            1,
            "ACTIVA",
        ),
    )
    cuenta_juan_id = cursor.lastrowid

    # 3. Primer movimiento: Acreditación de haberes mensual
    cursor.execute(
        """
        INSERT INTO movimientos_cuenta (
            cuenta_id, tipo_movimiento, monto, saldo_posterior, fecha_hora, descripcion, alerta_aml
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cuenta_juan_id,
            "ACREDITACION_SUELDO",
            3000000.0,
            3000000.0,
            now_iso,
            "Acreditación de Sueldo Mensual - Empleador Registrado",
            0,
        ),
    )

    # 4. Historial Veraz / BCRA para Juan José (Score sobresaliente, Situación 1)
    cursor.execute(
        """
        INSERT INTO historial_veraz_externo (
            persona_id, empresa_id, fecha_consulta, score_externo,
            peor_situacion_bcra, monto_deuda_externa_total, cantidad_bancos_acreedores, cheques_rechazados_monto
        ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?)
        """,
        (persona_id, today_iso, 740, 1, 0.0, 1, 0.0),
    )

    # 5. Empresa Demo: Catamarca Minería & Servicios S.A.
    cursor.execute(
        """
        INSERT INTO empresas (
            cuit, razon_social, tipo_societario, rubro_actividad,
            localidad, facturacion_anual_comprobada, requiere_fianza_socios,
            exencion_impositiva, estado_cuenta, fecha_alta
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "30-71234567-8",
            "Catamarca Minería & Servicios S.A.",
            "SA",
            "Servicios Mineros e Industriales",
            "San Fernando del Valle de Catamarca",
            180000000.0,
            0,
            0,
            "ACTIVO",
            today_iso,
        ),
    )
    empresa_id = cursor.lastrowid

    # 6. Cuenta Transaccional Corporativa PyME
    cursor.execute(
        """
        INSERT INTO cuentas_transaccionales (
            persona_id, empresa_id, cbu, alias, saldo_actual,
            tna_rendimiento_diario, es_cuenta_sueldo, permite_extraccion_inmediata, estado
        ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            empresa_id,
            "2850001211100098765432",
            "CATAMARCA.MINERIA",
            15000000.0,
            TNA_FLEXIBLE_BASE,
            0,
            1,
            "ACTIVA",
        ),
    )
    cuenta_empresa_id = cursor.lastrowid

    # Movimiento depósito inicial corporativo
    cursor.execute(
        """
        INSERT INTO movimientos_cuenta (
            cuenta_id, tipo_movimiento, monto, saldo_posterior, fecha_hora, descripcion, alerta_aml
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cuenta_empresa_id,
            "DEPOSITO",
            15000000.0,
            15000000.0,
            now_iso,
            "Depósito Inicial de Capital Operativo Corporativo",
            0,
        ),
    )

    # 7. Credenciales de Acceso (Bcrypt)
    pass_juan_hash = _hash_password("Valle1234!")
    cursor.execute(
        """
        INSERT INTO usuarios_credenciales (
            persona_id, empresa_id, identificador, email, password_hash, rol,
            intentos_fallidos, bloqueado_hasta, ultimo_login, fecha_creacion
        ) VALUES (?, NULL, ?, ?, ?, ?, ?, NULL, NULL, ?)
        """,
        (persona_id, "35123456", "juan.gonzalez@valle.com.ar", pass_juan_hash, "CLIENTE", 0, now_iso),
    )

    pass_admin_hash = _hash_password("Gerencia2026!")
    cursor.execute(
        """
        INSERT INTO usuarios_credenciales (
            persona_id, empresa_id, identificador, email, password_hash, rol,
            intentos_fallidos, bloqueado_hasta, ultimo_login, fecha_creacion
        ) VALUES (NULL, NULL, ?, ?, ?, ?, ?, NULL, NULL, ?)
        """,
        ("99999999", "gerencia@bancodelvalle.com.ar", pass_admin_hash, "GERENTE", 0, now_iso),
    )

    # 8. Proyecciones Macroeconómicas Iniciales
    cursor.execute(
        """
        INSERT INTO proyecciones_inflacion (
            fecha_relevamiento, inflacion_proyectada_12m, fuente, tasa_referencia_politica_monetaria
        ) VALUES (?, ?, ?, ?)
        """,
        (today_iso, 0.45, "REM_BCRA", 0.40),
    )

    cursor.execute(
        """
        INSERT INTO proyecciones_actividad_economica (
            fecha_relevamiento, variacion_pbi_proyectada_anual, emae_ultimo_interanual, fase_ciclo, factor_macro_riesgo
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (today_iso, 0.01, 0.01, "ESTABLE", 1.0),
    )

    # 9. Snapshot Inicial de Balance y Tesorería
    total_flexibles = 3000000.0 + 15000000.0  # $18.000.000
    encaje_flex = total_flexibles * ENCAJE_FLEXIBLE_PCT  # 30% = $5.400.000
    cashflow_seguro = CAPITAL_PATRIMONIO_INICIAL + total_flexibles - encaje_flex - COLCHON_LIQUIDEZ_SEGURIDAD

    cursor.execute(
        """
        INSERT INTO balance_patrimonio_banco (
            fecha_corte, total_depositos_plazo_fijo, total_depositos_flexibles,
            encaje_obligatorio_bcra, capital_propio_patrimonio, total_prestado_activo,
            cashflow_seguro_prestable
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            today_iso,
            0.0,
            total_flexibles,
            round(encaje_flex, 2),
            CAPITAL_PATRIMONIO_INICIAL,
            0.0,
            round(cashflow_seguro, 2),
        ),
    )


def init_db(db_path: Optional[str] = None, seed_demo: bool = True) -> None:
    """Inicializa la base de datos ejecutando el esquema DDL y poblando los datos iniciales."""
    with transaction(db_path=db_path) as conn:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)

        if seed_demo:
            seed_initial_data(conn)


def reset_database(conn: Optional[sqlite3.Connection] = None, db_path: Optional[str] = None) -> None:
    """Restablece la base de datos eliminando operaciones simuladas y resembrando el estado inicial limpio."""
    with transaction(conn=conn, db_path=db_path) as c:
        c.execute("PRAGMA foreign_keys = OFF;")
        tablas = [
            "auditoria_accesos",
            "movimientos_cuenta",
            "cuotas",
            "prestamos",
            "plazos_fijos",
            "historial_veraz_externo",
            "cuentas_transaccionales",
            "usuarios_credenciales",
            "proyecciones_inflacion",
            "proyecciones_actividad_economica",
            "balance_patrimonio_banco",
            "personas",
            "empresas",
        ]
        for t in tablas:
            try:
                c.execute(f"DELETE FROM {t};")
            except sqlite3.OperationalError:
                pass
        try:
            c.execute("DELETE FROM sqlite_sequence;")
        except sqlite3.OperationalError:
            pass
        c.execute("PRAGMA foreign_keys = ON;")
        seed_initial_data(c)

