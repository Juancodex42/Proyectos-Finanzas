"""
Repositorio de Persistencia para Personas Humanas y Buró Crediticio.
Operaciones CRUD e integridad sobre tablas 'personas' e 'historial_veraz_externo'.
Referencia de diseño: docs/diagrama_usuarios_empresas_aml_bloqueos.md
"""

from typing import List, Optional
import sqlite3

from src.domain.models import CategoriaLaboral, EstadoCuenta, HistorialVeraz, Persona


def _row_to_persona(row: sqlite3.Row) -> Persona:
    """Convierte un registro sqlite3.Row a la entidad de dominio Persona."""
    return Persona(
        id=row["id"],
        dni=row["dni"],
        nombre_completo=row["nombre_completo"],
        localidad=row["localidad"],
        categoria_laboral=CategoriaLaboral(row["categoria_laboral"]),
        antiguedad_laboral_meses=int(row["antiguedad_laboral_meses"]),
        ingreso_mensual_comprobado=float(row["ingreso_mensual_comprobado"]),
        monto_sueldo_acreditado=float(row["monto_sueldo_acreditado"]),
        dia_cobro_sueldo=int(row["dia_cobro_sueldo"]),
        estado_cuenta=EstadoCuenta(row["estado_cuenta"]),
        fecha_alta=row["fecha_alta"],
    )


def crear_persona(conn: sqlite3.Connection, persona: Persona) -> int:
    """Inserta una nueva Persona humana y retorna su ID asignado."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO personas (
            dni, nombre_completo, localidad, categoria_laboral,
            antiguedad_laboral_meses, ingreso_mensual_comprobado,
            monto_sueldo_acreditado, dia_cobro_sueldo, estado_cuenta, fecha_alta
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            persona.dni,
            persona.nombre_completo,
            persona.localidad,
            persona.categoria_laboral.value if isinstance(persona.categoria_laboral, CategoriaLaboral) else str(persona.categoria_laboral),
            persona.antiguedad_laboral_meses,
            persona.ingreso_mensual_comprobado,
            persona.monto_sueldo_acreditado,
            persona.dia_cobro_sueldo,
            persona.estado_cuenta.value if isinstance(persona.estado_cuenta, EstadoCuenta) else str(persona.estado_cuenta),
            persona.fecha_alta,
        ),
    )
    return cursor.lastrowid  # type: ignore


def obtener_persona_por_id(conn: sqlite3.Connection, persona_id: int) -> Optional[Persona]:
    """Recupera una persona por su ID de clave primaria."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM personas WHERE id = ?", (persona_id,))
    row = cursor.fetchone()
    return _row_to_persona(row) if row else None


def obtener_persona_por_dni(conn: sqlite3.Connection, dni: str) -> Optional[Persona]:
    """Recupera una persona por su documento nacional de identidad único."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM personas WHERE dni = ?", (dni,))
    row = cursor.fetchone()
    return _row_to_persona(row) if row else None


def actualizar_estado_persona(conn: sqlite3.Connection, persona_id: int, nuevo_estado: EstadoCuenta) -> None:
    """Actualiza el estado de la cuenta de una persona (ej. AML, ACTIVO, CERRADO)."""
    estado_val = nuevo_estado.value if isinstance(nuevo_estado, EstadoCuenta) else str(nuevo_estado)
    conn.execute("UPDATE personas SET estado_cuenta = ? WHERE id = ?", (estado_val, persona_id))


def actualizar_datos_laborales(
    conn: sqlite3.Connection,
    persona_id: int,
    categoria: CategoriaLaboral,
    antiguedad: int,
    ingreso: float,
    sueldo_acreditado: Optional[float] = None,
) -> None:
    """Actualiza ingresos, antigüedad y categoría laboral de la persona."""
    cat_val = categoria.value if isinstance(categoria, CategoriaLaboral) else str(categoria)
    if sueldo_acreditado is not None:
        conn.execute(
            """
            UPDATE personas
            SET categoria_laboral = ?, antiguedad_laboral_meses = ?,
                ingreso_mensual_comprobado = ?, monto_sueldo_acreditado = ?
            WHERE id = ?
            """,
            (cat_val, antiguedad, ingreso, sueldo_acreditado, persona_id),
        )
    else:
        conn.execute(
            """
            UPDATE personas
            SET categoria_laboral = ?, antiguedad_laboral_meses = ?, ingreso_mensual_comprobado = ?
            WHERE id = ?
            """,
            (cat_val, antiguedad, ingreso, persona_id),
        )


def listar_personas(conn: sqlite3.Connection, limite: int = 100, offset: int = 0) -> List[Persona]:
    """Retorna una lista paginada de personas registradas."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM personas ORDER BY id ASC LIMIT ? OFFSET ?", (limite, offset))
    return [_row_to_persona(row) for row in cursor.fetchall()]


def guardar_historial_veraz(conn: sqlite3.Connection, historial: HistorialVeraz) -> int:
    """Registra o actualiza el snapshot del buró Veraz/BCRA para una persona o empresa."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO historial_veraz_externo (
            persona_id, empresa_id, fecha_consulta, score_externo,
            peor_situacion_bcra, monto_deuda_externa_total,
            cantidad_bancos_acreedores, cheques_rechazados_monto
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            historial.persona_id,
            historial.empresa_id,
            historial.fecha_consulta,
            historial.score_externo,
            historial.peor_situacion_bcra,
            historial.monto_deuda_externa_total,
            historial.cantidad_bancos_acreedores,
            historial.cheques_rechazados_monto,
        ),
    )
    return cursor.lastrowid  # type: ignore


def obtener_historial_veraz_persona(conn: sqlite3.Connection, persona_id: int) -> Optional[HistorialVeraz]:
    """Obtiene el último registro del buró externo para la persona especificada."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM historial_veraz_externo
        WHERE persona_id = ?
        ORDER BY id DESC LIMIT 1
        """,
        (persona_id,),
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
