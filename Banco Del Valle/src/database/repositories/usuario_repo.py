"""
Repositorio de Persistencia para Credenciales de Usuario, RBAC y Auditoría.
Control de intentos fallidos, bloqueos temporales e inicio de sesión seguro.
Referencia de diseño: docs/seguridad_autenticacion_credenciales.md
"""

from datetime import datetime, timedelta
from typing import List, Optional
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
