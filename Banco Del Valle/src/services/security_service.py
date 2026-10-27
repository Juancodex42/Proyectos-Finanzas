"""
Servicio de seguridad bancaria, hashing Bcrypt, emisión de tokens JWT y onboarding.
Gestiona el ciclo de vida de credenciales, control RBAC, bloqueo y alta atómica.
Referencia de diseño: docs/seguridad_autenticacion_credenciales.md
"""

from datetime import datetime, timedelta
import random
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
import bcrypt
from jose import JWTError, jwt

from src.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    LOCKOUT_MINUTES,
    MAX_LOGIN_ATTEMPTS,
    TNA_FLEXIBLE_BASE,
)
from src.database.repositories import (
    cuenta_repo,
    empresa_repo,
    movimiento_repo,
    persona_repo,
    usuario_repo,
)
from src.domain.models import (
    AuditoriaAcceso,
    CuentaTransaccional,
    Empresa,
    EstadoCuenta,
    HistorialVeraz,
    MovimientoCuenta,
    Persona,
    RegistroEmpresaDTO,
    RegistroPersonaDTO,
    RespuestaRegistroDTO,
    RolUsuario,
    TipoMovimiento,
    UsuarioCredencial,
)


def hash_password(raw_password: str) -> str:
    """Genera hash Bcrypt seguro con salt de 12 rondas."""
    return bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verificar_password(raw_password: str, hashed_password: str) -> bool:
    """Verifica si la contraseña en texto plano coincide con el hash Bcrypt."""
    try:
        return bcrypt.checkpw(raw_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def crear_token_acceso(
    usuario_id: int,
    identificador: str,
    rol: str,
    email: str = "",
    exp_minutos: int = ACCESS_TOKEN_EXPIRE_MINUTES,
) -> str:
    """Emite un token JWT codificado con claims estándar y tiempo de expiración."""
    expiracion = datetime.utcnow() + timedelta(minutes=exp_minutos)
    payload = {
        "sub": str(usuario_id),
        "identificador": identificador,
        "rol": rol,
        "email": email,
        "exp": expiracion,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decodificar_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodifica y valida la firma y expiración de un token JWT."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def validar_rol(token: str, roles_permitidos: List[str]) -> bool:
    """Comprueba si el rol contenido en el token tiene privilegios autorizados."""
    payload = decodificar_token(token)
    if not payload:
        return False
    rol_token = payload.get("rol", "")
    return rol_token in roles_permitidos


def autenticar_usuario(
    conn: sqlite3.Connection,
    identificador_o_email: str,
    raw_password: str,
    ip_origen: str = "127.0.0.1",
) -> Tuple[Optional[UsuarioCredencial], Optional[str], Optional[str]]:
    """
    Valida credenciales, controla bloqueos por fuerza bruta y emite el token JWT.
    Retorna una tupla: (UsuarioCredencial, token_jwt, mensaje_error).
    """
    ident_limpio = identificador_o_email.strip()
    usuario = usuario_repo.obtener_usuario_por_identificador(conn, ident_limpio)
    if not usuario:
        usuario = usuario_repo.obtener_usuario_por_email(conn, ident_limpio)

    if not usuario:
        return None, None, "Credenciales inválidas. Verifique sus datos."

    # Verificar si el usuario se encuentra bloqueado temporalmente
    if usuario.bloqueado_hasta:
        try:
            bloqueo_dt = datetime.fromisoformat(usuario.bloqueado_hasta)
            if datetime.now() < bloqueo_dt:
                minutos_restantes = max(1, int((bloqueo_dt - datetime.now()).total_seconds() / 60))
                return None, None, f"Cuenta bloqueada temporalmente por reiterados intentos fallidos. Intente nuevamente en {minutos_restantes} minutos."
            else:
                usuario_repo.desbloquear_usuario(conn, usuario.id)
        except Exception:
            pass

    # Verificación de hash Bcrypt
    if not verificar_password(raw_password, usuario.password_hash):
        intentos = usuario_repo.registrar_intento_fallido(
            conn, usuario.id, max_intentos=MAX_LOGIN_ATTEMPTS, minutos_bloqueo=LOCKOUT_MINUTES
        )
        usuario_repo.registrar_auditoria_acceso(
            conn,
            AuditoriaAcceso(
                usuario_id=usuario.id,
                direccion_ip=ip_origen,
                exitoso=0,
                motivo_falla=f"Contraseña incorrecta (Intento {intentos}/{MAX_LOGIN_ATTEMPTS})",
            ),
        )
        if intentos >= MAX_LOGIN_ATTEMPTS:
            return None, None, f"Cuenta bloqueada por {LOCKOUT_MINUTES} minutos debido a {MAX_LOGIN_ATTEMPTS} intentos fallidos."
        return None, None, f"Contraseña incorrecta. Intentos restantes: {MAX_LOGIN_ATTEMPTS - intentos}."

    # Login exitoso
    usuario_repo.actualizar_login_exitoso(conn, usuario.id)
    usuario_repo.registrar_auditoria_acceso(
        conn, AuditoriaAcceso(usuario_id=usuario.id, direccion_ip=ip_origen, exitoso=1, motivo_falla=None)
    )

    rol_str = usuario.rol.value if isinstance(usuario.rol, RolUsuario) else str(usuario.rol)
    token = crear_token_acceso(
        usuario_id=usuario.id, identificador=usuario.identificador, rol=rol_str, email=usuario.email
    )
    return usuario, token, None


def _generar_cbu_aleatorio() -> str:
    """Genera un CBU único de 22 dígitos estandarizado bajo prefijo Banco del Valle (285)."""
    prefijo_banco = "285"
    sucursal = "0001"
    digito_verificador_1 = "2"
    numero_cuenta = "".join([str(random.randint(0, 9)) for _ in range(13)])
    digito_verificador_2 = "8"
    return f"{prefijo_banco}{sucursal}{digito_verificador_1}{numero_cuenta}{digito_verificador_2}"


def _generar_alias_sugerido(nombre: str) -> str:
    """Genera un alias amigable y legible para transferencias bancarias."""
    palabras = re.sub(r"[^A-Za-z0-9\s]", "", nombre).upper().split()
    base = ".".join(palabras[:2]) if len(palabras) >= 2 else (palabras[0] if palabras else "CUENTA")
    aleatorio = random.randint(100, 999)
    return f"{base}.VALLE.{aleatorio}"


def registrar_nueva_persona(
    conn: sqlite3.Connection, dto: RegistroPersonaDTO
) -> RespuestaRegistroDTO:
    """Ejecuta el onboarding atómico de una Persona humana con caja de ahorros y credenciales."""
    dni_limpio = dto.dni.strip().replace(".", "").replace("-", "")
    email_limpio = dto.email.strip().lower()

    if persona_repo.obtener_persona_por_dni(conn, dni_limpio):
        return RespuestaRegistroDTO(
            exito=False,
            mensaje=f"Ya existe una persona registrada con el DNI {dni_limpio}.",
            usuario_id=0,
            identificador="",
            email="",
            rol=RolUsuario.CLIENTE,
            cbu_asignado="",
            alias_asignado="",
            token_acceso="",
        )

    if usuario_repo.obtener_usuario_por_email(conn, email_limpio):
        return RespuestaRegistroDTO(
            exito=False,
            mensaje=f"El correo electrónico {email_limpio} ya está en uso.",
            usuario_id=0,
            identificador="",
            email="",
            rol=RolUsuario.CLIENTE,
            cbu_asignado="",
            alias_asignado="",
            token_acceso="",
        )

    # 1. Crear Persona
    nueva_persona = Persona(
        dni=dni_limpio,
        nombre_completo=dto.nombre_completo.strip(),
        localidad=dto.localidad.strip(),
        categoria_laboral=dto.categoria_laboral,
        antiguedad_laboral_meses=dto.antiguedad_laboral_meses,
        ingreso_mensual_comprobado=dto.ingreso_mensual_estimado,
        monto_sueldo_acreditado=dto.monto_sueldo_acreditado,
        dia_cobro_sueldo=1,
        estado_cuenta=EstadoCuenta.ACTIVO,
    )
    persona_id = persona_repo.crear_persona(conn, nueva_persona)

    # 2. Asignar CBU y Alias bancario
    cbu = _generar_cbu_aleatorio()
    alias = _generar_alias_sugerido(dto.nombre_completo)
    saldo_inicial = dto.monto_sueldo_acreditado if dto.es_cuenta_sueldo else 0.0

    nueva_cuenta = CuentaTransaccional(
        persona_id=persona_id,
        empresa_id=None,
        cbu=cbu,
        alias=alias,
        saldo_actual=saldo_inicial,
        tna_rendimiento_diario=TNA_FLEXIBLE_BASE,
        es_cuenta_sueldo=dto.es_cuenta_sueldo,
        permite_extraccion_inmediata=True,
        estado=EstadoCuenta.ACTIVO,
    )
    cuenta_id = cuenta_repo.crear_cuenta(conn, nueva_cuenta)

    # 3. Registrar movimiento contable si hay acreditación de haberes inicial
    if saldo_inicial > 0:
        movimiento_repo.registrar_movimiento(
            conn,
            MovimientoCuenta(
                cuenta_id=cuenta_id,
                tipo_movimiento=TipoMovimiento.ACREDITACION_SUELDO,
                monto=saldo_inicial,
                saldo_posterior=saldo_inicial,
                descripcion="Acreditación inicial de sueldo tras apertura de cuenta",
            ),
        )

    # 4. Snapshot inicial Buró Veraz (Situación 1 - Normal, Score 680)
    persona_repo.guardar_historial_veraz(
        conn,
        HistorialVeraz(
            persona_id=persona_id,
            empresa_id=None,
            score_externo=680,
            peor_situacion_bcra=1,
            monto_deuda_externa_total=0.0,
            cantidad_bancos_acreedores=1,
            cheques_rechazados_monto=0.0,
        ),
    )

    # 5. Crear Credencial de acceso (Bcrypt)
    pass_hash = hash_password(dto.password)
    usuario_id = usuario_repo.crear_usuario(
        conn,
        UsuarioCredencial(
            persona_id=persona_id,
            empresa_id=None,
            identificador=dni_limpio,
            email=email_limpio,
            password_hash=pass_hash,
            rol=RolUsuario.CLIENTE,
        ),
    )

    token = crear_token_acceso(
        usuario_id=usuario_id, identificador=dni_limpio, rol="CLIENTE", email=email_limpio
    )

    return RespuestaRegistroDTO(
        exito=True,
        mensaje="Cuenta bancaria y credenciales creadas exitosamente.",
        usuario_id=usuario_id,
        identificador=dni_limpio,
        email=email_limpio,
        rol=RolUsuario.CLIENTE,
        cbu_asignado=cbu,
        alias_asignado=alias,
        token_acceso=token,
    )


def registrar_nueva_empresa(
    conn: sqlite3.Connection, dto: RegistroEmpresaDTO
) -> RespuestaRegistroDTO:
    """Ejecuta el onboarding atómico de una Persona Jurídica / PyME con cuenta operativa."""
    cuit_limpio = dto.cuit.strip().replace(" ", "")
    email_limpio = dto.email.strip().lower()

    if empresa_repo.obtener_empresa_por_cuit(conn, cuit_limpio):
        return RespuestaRegistroDTO(
            exito=False,
            mensaje=f"Ya existe una empresa registrada con el CUIT {cuit_limpio}.",
            usuario_id=0,
            identificador="",
            email="",
            rol=RolUsuario.CLIENTE,
            cbu_asignado="",
            alias_asignado="",
            token_acceso="",
        )

    if usuario_repo.obtener_usuario_por_email(conn, email_limpio):
        return RespuestaRegistroDTO(
            exito=False,
            mensaje=f"El correo corporativo {email_limpio} ya está en uso.",
            usuario_id=0,
            identificador="",
            email="",
            rol=RolUsuario.CLIENTE,
            cbu_asignado="",
            alias_asignado="",
            token_acceso="",
        )

    # 1. Crear Empresa
    nueva_empresa = Empresa(
        cuit=cuit_limpio,
        razon_social=dto.razon_social.strip(),
        tipo_societario=dto.tipo_societario,
        rubro_actividad=dto.rubro_actividad.strip(),
        localidad=dto.localidad.strip(),
        facturacion_anual_comprobada=dto.facturacion_anual_estimada,
        requiere_fianza_socios=False,
        exencion_impositiva=dto.exencion_impositiva,
        estado_cuenta=EstadoCuenta.ACTIVO,
    )
    empresa_id = empresa_repo.crear_empresa(conn, nueva_empresa)

    # 2. Asignar CBU y Alias corporativo
    cbu = _generar_cbu_aleatorio()
    alias = _generar_alias_sugerido(dto.razon_social)

    nueva_cuenta = CuentaTransaccional(
        persona_id=None,
        empresa_id=empresa_id,
        cbu=cbu,
        alias=alias,
        saldo_actual=0.0,
        tna_rendimiento_diario=TNA_FLEXIBLE_BASE,
        es_cuenta_sueldo=False,
        permite_extraccion_inmediata=True,
        estado=EstadoCuenta.ACTIVO,
    )
    cuenta_repo.crear_cuenta(conn, nueva_cuenta)

    # 3. Snapshot inicial Buró Veraz Corporativo
    empresa_repo.obtener_historial_veraz_empresa(conn, empresa_id)
    persona_repo.guardar_historial_veraz(
        conn,
        HistorialVeraz(
            persona_id=None,
            empresa_id=empresa_id,
            score_externo=700,
            peor_situacion_bcra=1,
            monto_deuda_externa_total=0.0,
            cantidad_bancos_acreedores=1,
            cheques_rechazados_monto=0.0,
        ),
    )

    # 4. Crear Credenciales de acceso
    pass_hash = hash_password(dto.password)
    usuario_id = usuario_repo.crear_usuario(
        conn,
        UsuarioCredencial(
            persona_id=None,
            empresa_id=empresa_id,
            identificador=cuit_limpio,
            email=email_limpio,
            password_hash=pass_hash,
            rol=RolUsuario.CLIENTE,
        ),
    )

    token = crear_token_acceso(
        usuario_id=usuario_id, identificador=cuit_limpio, rol="CLIENTE", email=email_limpio
    )

    return RespuestaRegistroDTO(
        exito=True,
        mensaje="Empresa y cuenta corriente corporativa registradas con éxito.",
        usuario_id=usuario_id,
        identificador=cuit_limpio,
        email=email_limpio,
        rol=RolUsuario.CLIENTE,
        cbu_asignado=cbu,
        alias_asignado=alias,
        token_acceso=token,
    )
