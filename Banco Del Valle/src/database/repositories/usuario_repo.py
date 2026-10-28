"""
Repositorio de Persistencia para Credenciales de Usuario, RBAC y Auditoría.
Control de intentos fallidos, bloqueos temporales e inicio de sesión seguro.
Referencia de diseño: docs/seguridad_autenticacion_credenciales.md
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import sqlite3

from src.domain.models import AuditoriaAcceso, RolUsuario, UsuarioCredencial


def _row_to_usuario(row: sqlite3.Row) -> UsuarioCredencial:
    """Convierte un registro sqlite3.Row a la entidad UsuarioCredencial."""
    return UsuarioCredencial(
        id=row["id"],
        persona_id=row["persona_id"],
        empresa_id=row["empresa_id"],
        identificador=row["identificador"],
        email=row["email"],
        password_hash=row["password_hash"],
        rol=RolUsuario(row["rol"]),
        intentos_fallidos=int(row["intentos_fallidos"]),
        bloqueado_hasta=row["bloqueado_hasta"],
        ultimo_login=row["ultimo_login"],
        fecha_creacion=row["fecha_creacion"],
    )


def _row_to_auditoria(row: sqlite3.Row) -> AuditoriaAcceso:
    """Convierte un registro sqlite3.Row a la entidad AuditoriaAcceso."""
    return AuditoriaAcceso(
        id=row["id"],
        usuario_id=row["usuario_id"],
        fecha_hora=row["fecha_hora"],
        direccion_ip=row["direccion_ip"],
        exitoso=int(row["exitoso"]),
        motivo_falla=row["motivo_falla"],
    )


def crear_usuario(conn: sqlite3.Connection, usuario: UsuarioCredencial) -> int:
    """Inserta credenciales de acceso para un usuario del sistema y retorna su ID."""
    cursor = conn.cursor()
    rol_val = usuario.rol.value if isinstance(usuario.rol, RolUsuario) else str(usuario.rol)
    cursor.execute(
        """
        INSERT INTO usuarios_credenciales (
            persona_id, empresa_id, identificador, email,
            password_hash, rol, intentos_fallidos, bloqueado_hasta,
            ultimo_login, fecha_creacion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            usuario.persona_id,
            usuario.empresa_id,
            usuario.identificador.strip(),
            usuario.email.strip().lower(),
            usuario.password_hash,
            rol_val,
            usuario.intentos_fallidos,
            usuario.bloqueado_hasta,
            usuario.ultimo_login,
            usuario.fecha_creacion,
        ),
    )
    return cursor.lastrowid  # type: ignore


def obtener_usuario_por_id(conn: sqlite3.Connection, usuario_id: int) -> Optional[UsuarioCredencial]:
    """Recupera un usuario por su ID primario."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios_credenciales WHERE id = ?", (usuario_id,))
    row = cursor.fetchone()
    return _row_to_usuario(row) if row else None


def obtener_usuario_por_identificador(conn: sqlite3.Connection, identificador: str) -> Optional[UsuarioCredencial]:
    """Recupera un usuario por su identificador único (DNI, CUIT o alias corporativo)."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM usuarios_credenciales WHERE UPPER(identificador) = UPPER(?)",
        (identificador.strip(),),
    )
    row = cursor.fetchone()
    return _row_to_usuario(row) if row else None


def obtener_usuario_por_email(conn: sqlite3.Connection, email: str) -> Optional[UsuarioCredencial]:
    """Recupera un usuario por su correo electrónico único."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM usuarios_credenciales WHERE LOWER(email) = LOWER(?)",
        (email.strip(),),
    )
    row = cursor.fetchone()
    return _row_to_usuario(row) if row else None


def actualizar_login_exitoso(conn: sqlite3.Connection, usuario_id: int) -> None:
    """Reinicia el contador de intentos fallidos y actualiza la fecha del último login."""
    ahora_iso = datetime.now().isoformat()
    conn.execute(
        """
        UPDATE usuarios_credenciales
        SET intentos_fallidos = 0, bloqueado_hasta = NULL, ultimo_login = ?
        WHERE id = ?
        """,
        (ahora_iso, usuario_id),
    )


def registrar_intento_fallido(
    conn: sqlite3.Connection,
    usuario_id: int,
    max_intentos: int = 5,
    minutos_bloqueo: int = 15,
) -> int:
    """Incrementa intentos fallidos; bloquea temporalmente al alcanzar max_intentos."""
    usuario = obtener_usuario_por_id(conn, usuario_id)
    if not usuario:
        return 0

    nuevos_intentos = usuario.intentos_fallidos + 1
    bloqueado_hasta = None

    if nuevos_intentos >= max_intentos:
        bloqueado_hasta = (datetime.now() + timedelta(minutes=minutos_bloqueo)).isoformat()

    conn.execute(
        """
        UPDATE usuarios_credenciales
        SET intentos_fallidos = ?, bloqueado_hasta = ?
        WHERE id = ?
        """,
        (nuevos_intentos, bloqueado_hasta, usuario_id),
    )
    return nuevos_intentos


def desbloquear_usuario(conn: sqlite3.Connection, usuario_id: int) -> None:
    """Desbloquea manualmente a un usuario restableciendo el contador a cero."""
    conn.execute(
        """
        UPDATE usuarios_credenciales
        SET intentos_fallidos = 0, bloqueado_hasta = NULL
        WHERE id = ?
        """,
        (usuario_id,),
    )


def registrar_auditoria_acceso(conn: sqlite3.Connection, auditoria: AuditoriaAcceso) -> int:
    """Inserta una traza de auditoría de inicio de sesión."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO auditoria_accesos (
            usuario_id, fecha_hora, direccion_ip, exitoso, motivo_falla
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            auditoria.usuario_id,
            auditoria.fecha_hora,
            auditoria.direccion_ip,
            1 if auditoria.exitoso else 0,
            auditoria.motivo_falla,
        ),
    )
    return cursor.lastrowid  # type: ignore


def obtener_auditoria_por_usuario(
    conn: sqlite3.Connection, usuario_id: int, limite: int = 50
) -> List[AuditoriaAcceso]:
    """Retorna los registros de auditoría de acceso más recientes de un usuario."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM auditoria_accesos
        WHERE usuario_id = ?
        ORDER BY fecha_hora DESC, id DESC
        LIMIT ?
        """,
        (usuario_id, limite),
    )
    return [_row_to_auditoria(row) for row in cursor.fetchall()]


def _construir_query_base_usuarios() -> str:
    """Retorna la CTE y subconsultas unificadas de clientes (Individuos y Empresas) con cuentas y créditos."""
    return """
    WITH prestamos_agg AS (
        SELECT 
            COALESCE(persona_id, 0) as p_id,
            COALESCE(empresa_id, 0) as e_id,
            COUNT(*) as total_prestamos,
            SUM(CASE WHEN estado IN ('ACTIVO', 'AL_DIA', 'EN_MORA') THEN 1 ELSE 0 END) as prestamos_activos,
            SUM(CASE WHEN estado IN ('ACTIVO', 'AL_DIA', 'EN_MORA') THEN monto_capital ELSE 0.0 END) as deuda_capital_activa,
            GROUP_CONCAT(DISTINCT estado) as estados_prestamos
        FROM prestamos
        GROUP BY p_id, e_id
    ),
    cuentas_agg AS (
        SELECT
            COALESCE(persona_id, 0) as p_id,
            COALESCE(empresa_id, 0) as e_id,
            id as cuenta_id,
            cbu,
            alias,
            saldo_actual,
            estado as estado_cuenta_bancaria,
            es_cuenta_sueldo,
            tna_rendimiento_diario
        FROM cuentas_transaccionales
    )
    SELECT 
        'INDIVIDUO' as tipo_cliente,
        p.id as cliente_id,
        p.dni as identificador_fiscal,
        p.nombre_completo as nombre_titular,
        u.id as usuario_id,
        u.email as email_contacto,
        COALESCE(u.rol, 'CLIENTE') as rol_acceso,
        p.categoria_laboral as subtipo_actividad,
        p.categoria_laboral as tipo_empresa_o_laboral,
        p.estado_cuenta as estado_cliente,
        p.fecha_alta as fecha_registro,
        c.cuenta_id,
        COALESCE(c.cbu, '') as cbu,
        COALESCE(c.alias, '') as alias,
        COALESCE(c.saldo_actual, 0.0) as saldo_cuenta,
        COALESCE(c.es_cuenta_sueldo, 0) as es_cuenta_sueldo,
        COALESCE(pr.prestamos_activos, 0) as prestamos_activos,
        COALESCE(pr.deuda_capital_activa, 0.0) as monto_prestamos,
        COALESCE(pr.estados_prestamos, 'SIN_PRESTAMO') as estados_prestamos
    FROM personas p
    LEFT JOIN usuarios_credenciales u ON u.persona_id = p.id
    LEFT JOIN cuentas_agg c ON c.p_id = p.id
    LEFT JOIN prestamos_agg pr ON pr.p_id = p.id

    UNION ALL

    SELECT 
        'EMPRESA' as tipo_cliente,
        e.id as cliente_id,
        e.cuit as identificador_fiscal,
        e.razon_social as nombre_titular,
        u.id as usuario_id,
        u.email as email_contacto,
        COALESCE(u.rol, 'CLIENTE') as rol_acceso,
        (e.tipo_societario || ' - ' || e.rubro_actividad) as subtipo_actividad,
        e.tipo_societario as tipo_empresa_o_laboral,
        e.estado_cuenta as estado_cliente,
        e.fecha_alta as fecha_registro,
        c.cuenta_id,
        COALESCE(c.cbu, '') as cbu,
        COALESCE(c.alias, '') as alias,
        COALESCE(c.saldo_actual, 0.0) as saldo_cuenta,
        0 as es_cuenta_sueldo,
        COALESCE(pr.prestamos_activos, 0) as prestamos_activos,
        COALESCE(pr.deuda_capital_activa, 0.0) as monto_prestamos,
        COALESCE(pr.estados_prestamos, 'SIN_PRESTAMO') as estados_prestamos
    FROM empresas e
    LEFT JOIN usuarios_credenciales u ON u.empresa_id = e.id
    LEFT JOIN cuentas_agg c ON c.e_id = e.id
    LEFT JOIN prestamos_agg pr ON pr.e_id = e.id
    """


def obtener_lista_usuarios_banco(
    conn: sqlite3.Connection,
    tipo_cliente: Optional[str] = None,
    estado: Optional[str] = None,
    busqueda: Optional[str] = None,
    orden: str = "recientes",
    limite: Optional[int] = 10,
    offset: Optional[int] = 0,
) -> List[Dict[str, Any]]:
    """
    Retorna la lista paginada y filtrada del Padrón Central de Clientes (Individuos y Empresas)
    con sus cuentas transaccionales, saldo, préstamos a su nombre y fecha de registro.
    """
    base_sql = _construir_query_base_usuarios()
    where_clauses = []
    params: List[Any] = []

    if tipo_cliente and tipo_cliente.upper() in ("INDIVIDUO", "EMPRESA"):
        where_clauses.append("tipo_cliente = ?")
        params.append(tipo_cliente.upper())

    if estado and estado.upper() not in ("TODOS", ""):
        where_clauses.append("UPPER(estado_cliente) = ?")
        params.append(estado.upper())

    if busqueda and busqueda.strip():
        term = f"%{busqueda.strip().lower()}%"
        where_clauses.append(
            "(LOWER(nombre_titular) LIKE ? OR LOWER(identificador_fiscal) LIKE ? OR LOWER(email_contacto) LIKE ? OR LOWER(alias) LIKE ? OR cbu LIKE ?)"
        )
        params.extend([term, term, term, term, term])

    where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Ordenamiento
    order_map = {
        "recientes": "ORDER BY fecha_registro DESC, cliente_id DESC",
        "antiguos": "ORDER BY fecha_registro ASC, cliente_id ASC",
        "mayor_saldo": "ORDER BY saldo_cuenta DESC",
        "menor_saldo": "ORDER BY saldo_cuenta ASC",
        "nombre_asc": "ORDER BY nombre_titular ASC",
    }
    order_clause = order_map.get(orden.lower(), "ORDER BY fecha_registro DESC, cliente_id DESC")

    limit_clause = ""
    if limite is not None:
        limit_clause = f"LIMIT {int(limite)} OFFSET {int(offset or 0)}"

    query = f"""
    SELECT * FROM (
        {base_sql}
    )
    {where_str}
    {order_clause}
    {limit_clause}
    """

    cursor = conn.cursor()
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    
    # Mapear a diccionarios
    columnas = [col[0] for col in cursor.description]
    return [dict(zip(columnas, row)) for row in rows]


def contar_usuarios_banco(
    conn: sqlite3.Connection,
    tipo_cliente: Optional[str] = None,
    estado: Optional[str] = None,
    busqueda: Optional[str] = None,
) -> int:
    """Calcula el total de registros coincidentes con los filtros para la paginación."""
    base_sql = _construir_query_base_usuarios()
    where_clauses = []
    params: List[Any] = []

    if tipo_cliente and tipo_cliente.upper() in ("INDIVIDUO", "EMPRESA"):
        where_clauses.append("tipo_cliente = ?")
        params.append(tipo_cliente.upper())

    if estado and estado.upper() not in ("TODOS", ""):
        where_clauses.append("UPPER(estado_cliente) = ?")
        params.append(estado.upper())

    if busqueda and busqueda.strip():
        term = f"%{busqueda.strip().lower()}%"
        where_clauses.append(
            "(LOWER(nombre_titular) LIKE ? OR LOWER(identificador_fiscal) LIKE ? OR LOWER(email_contacto) LIKE ? OR LOWER(alias) LIKE ? OR cbu LIKE ?)"
        )
        params.extend([term, term, term, term, term])

    where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    query = f"""
    SELECT COUNT(*) FROM (
        {base_sql}
    )
    {where_str}
    """

    cursor = conn.cursor()
    cursor.execute(query, tuple(params))
    row = cursor.fetchone()
    return int(row[0]) if row else 0
