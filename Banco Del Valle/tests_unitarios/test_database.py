"""
Suite de Pruebas Unitarias e Integración para la Capa de Persistencia SQLite.
Valida DDL, semillas iniciales, repositorios, transacciones ACID y rollback.
Referencia de diseño: docs/diagrama_logica_negocio_banco.md
"""

from datetime import date, datetime
import os
import tempfile
import pytest

from src.database.connection import get_db_connection, init_db, transaction
from src.database.repositories import (
    actividad_repo,
    balance_repo,
    cuenta_repo,
    deposito_repo,
    empresa_repo,
    inflacion_repo,
    movimiento_repo,
    persona_repo,
    prestamo_repo,
    usuario_repo,
)
from src.domain.models import (
    AuditoriaAcceso,
    BalancePatrimonio,
    CategoriaLaboral,
    CuentaTransaccional,
    Cuota,
    Empresa,
    EstadoCuenta,
    EstadoPlazoFijo,
    EstadoPrestamo,
    FaseCiclo,
    HistorialVeraz,
    MovimientoCuenta,
    Persona,
    PlazoFijo,
    Prestamo,
    ProyeccionActividad,
    ProyeccionInflacion,
    RolUsuario,
    TipoMovimiento,
    TipoSocietario,
    UsuarioCredencial,
)


@pytest.fixture
def test_db():
    """Crea una base de datos SQLite temporal aislada para cada prueba."""
    tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = tmp_file.name
    tmp_file.close()

    init_db(db_path=tmp_path, seed_demo=True)
    conn = get_db_connection(tmp_path)

    yield conn, tmp_path

    conn.close()
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)


def test_seed_demo_juan_jose(test_db):
    """Verifica que la siembra inicial crea a Juan José, sus cuentas, saldo de $3M y credenciales."""
    conn, _ = test_db

    persona = persona_repo.obtener_persona_por_dni(conn, "35123456")
    assert persona is not None
    assert persona.nombre_completo == "Juan José Gonzalez"
    assert persona.categoria_laboral == CategoriaLaboral.EMPLEADO_PRIVADO
    assert persona.ingreso_mensual_comprobado == 3000000.0

    cuentas = cuenta_repo.obtener_cuentas_por_persona(conn, persona.id)
    assert len(cuentas) == 1
    assert cuentas[0].alias == "JUAN.BANCO.VALLE"
    assert cuentas[0].saldo_actual == 3000000.0
    assert cuentas[0].es_cuenta_sueldo is True

    usuario = usuario_repo.obtener_usuario_por_identificador(conn, "35123456")
    assert usuario is not None
    assert usuario.rol == RolUsuario.CLIENTE
    assert usuario.email == "juan.gonzalez@valle.com.ar"

    admin = usuario_repo.obtener_usuario_por_identificador(conn, "99999999")
    assert admin is not None
    assert admin.rol == RolUsuario.GERENTE


def test_persona_repo_crud(test_db):
    """Verifica operaciones de creación, búsqueda y actualización de personas."""
    conn, _ = test_db

    nueva = Persona(
        dni="40999888",
        nombre_completo="María Elena Catamarca",
        categoria_laboral=CategoriaLaboral.EMPLEADO_PUBLICO,
        antiguedad_laboral_meses=24,
        ingreso_mensual_comprobado=1800000.0,
        monto_sueldo_acreditado=1800000.0,
    )
    p_id = persona_repo.crear_persona(conn, nueva)
    assert p_id > 0

    recuperada = persona_repo.obtener_persona_por_id(conn, p_id)
    assert recuperada is not None
    assert recuperada.dni == "40999888"
    assert recuperada.categoria_laboral == CategoriaLaboral.EMPLEADO_PUBLICO

    persona_repo.actualizar_estado_persona(conn, p_id, EstadoCuenta.SUSPENDIDO_AML)
    actualizada = persona_repo.obtener_persona_por_id(conn, p_id)
    assert actualizada.estado_cuenta == EstadoCuenta.SUSPENDIDO_AML


def test_empresa_repo_crud(test_db):
    """Verifica operaciones sobre personas jurídicas / PyMEs."""
    conn, _ = test_db

    empresa = Empresa(
        cuit="30-88887777-9",
        razon_social="Agro Valle SRL",
        tipo_societario=TipoSocietario.SRL,
        rubro_actividad="Agroindustria Olivícola",
        facturacion_anual_comprobada=75000000.0,
        requiere_fianza_socios=True,
    )
    e_id = empresa_repo.crear_empresa(conn, empresa)
    assert e_id > 0

    por_cuit = empresa_repo.obtener_empresa_por_cuit(conn, "30-88887777-9")
    assert por_cuit is not None
    assert por_cuit.razon_social == "Agro Valle SRL"
    assert por_cuit.requiere_fianza_socios is True


def test_cuenta_transaccional_y_movimientos(test_db):
    """Verifica actualización de saldos y registro inmutable en movimientos_cuenta."""
    conn, _ = test_db

    cuenta_juan = cuenta_repo.obtener_cuenta_por_alias(conn, "JUAN.BANCO.VALLE")
    assert cuenta_juan is not None

    nuevo_saldo = cuenta_juan.saldo_actual + 500000.0
    cuenta_repo.actualizar_saldo(conn, cuenta_juan.id, nuevo_saldo)

    mov_id = movimiento_repo.registrar_movimiento(
        conn,
        MovimientoCuenta(
            cuenta_id=cuenta_juan.id,
            tipo_movimiento=TipoMovimiento.DEPOSITO,
            monto=500000.0,
            saldo_posterior=nuevo_saldo,
            descripcion="Depósito en ventanilla",
        ),
    )
    assert mov_id > 0

    movs = movimiento_repo.obtener_movimientos_por_cuenta(conn, cuenta_juan.id)
    assert len(movs) >= 2  # El sueldo inicial + este nuevo depósito
    assert movs[0].monto == 500000.0
    assert movs[0].saldo_posterior == 3500000.0


def test_prestamo_frances_y_cuotas(test_db):
    """Verifica creación de contratos de préstamo, inserción de cuotas y consulta de mora."""
    conn, _ = test_db
    persona = persona_repo.obtener_persona_por_dni(conn, "35123456")

    cuotas = [
        Cuota(numero_cuota=1, monto_cuota=112825.41, fecha_vencimiento="2026-11-01"),
        Cuota(numero_cuota=2, monto_cuota=112825.41, fecha_vencimiento="2026-12-01"),
    ]
    prestamo = Prestamo(
        persona_id=persona.id,
        tipo_credito="PERSONAL",
        monto_capital=1000000.0,
        tasa_nominal_anual=0.60,
        cantidad_cuotas=12,
        fecha_otorgamiento="2026-10-01",
        estado=EstadoPrestamo.ACTIVO,
    )

    p_id = prestamo_repo.crear_prestamo(conn, prestamo, cuotas)
    assert p_id > 0

    cuotas_guardadas = prestamo_repo.obtener_cuotas_por_prestamo(conn, p_id)
    assert len(cuotas_guardadas) == 2
    assert cuotas_guardadas[0].monto_cuota == 112825.41

    prestamo_repo.actualizar_cuota(conn, cuotas_guardadas[0].id, fecha_pago="2026-11-01", dias_mora=0, intereses_punitorios=0.0)
    cuotas_actualizadas = prestamo_repo.obtener_cuotas_por_prestamo(conn, p_id)
    assert cuotas_actualizadas[0].fecha_pago == "2026-11-01"


def test_deposito_plazo_fijo(test_db):
    """Verifica imposición a plazo fijo, agregación para encajes y vencimientos."""
    conn, _ = test_db
    persona = persona_repo.obtener_persona_por_dni(conn, "35123456")

    pf = PlazoFijo(
        persona_id=persona.id,
        monto_depositado=2000000.0,
        tasa_nominal_anual=0.38,
        fecha_inicio="2026-10-01",
        fecha_vencimiento="2026-10-31",
        intereses_a_generar=62465.75,
        estado=EstadoPlazoFijo.ACTIVO,
    )
    pf_id = deposito_repo.crear_plazo_fijo(conn, pf)
    assert pf_id > 0

    total_pf = deposito_repo.sumar_total_depositos_plazo_fijo_activos(conn)
    assert total_pf == 2000000.0

    vencidos = deposito_repo.obtener_plazos_fijos_vencidos_a_la_fecha(conn, "2026-11-01")
    assert len(vencidos) == 1
    assert vencidos[0].id == pf_id


def test_balance_snapshots_y_capitalizacion(test_db):
    """Verifica registro y evolución de snapshots diarios de balance."""
    conn, _ = test_db

    ultimo = balance_repo.obtener_ultimo_balance(conn)
    assert ultimo is not None
    assert ultimo.capital_propio_patrimonio == 50000000.0

    nuevo_snap = BalancePatrimonio(
        fecha_corte="2026-10-27",
        total_depositos_plazo_fijo=2000000.0,
        total_depositos_flexibles=18000000.0,
        encaje_obligatorio_bcra=5640000.0,
        capital_propio_patrimonio=50150000.0,
        total_prestado_activo=1000000.0,
        cashflow_seguro_prestable=58510000.0,
    )
    s_id = balance_repo.registrar_snapshot_balance(conn, nuevo_snap)
    assert s_id > 0

    historico = balance_repo.obtener_historico_balances(conn)
    assert len(historico) == 2
    assert historico[-1].capital_propio_patrimonio == 50150000.0


def test_macro_inflacion_y_actividad(test_db):
    """Verifica persistencia y lectura de variables macroeconómicas."""
    conn, _ = test_db

    inf = inflacion_repo.obtener_ultima_proyeccion_inflacion(conn)
    assert inf is not None
    assert inf.inflacion_proyectada_12m == 0.45

    act = actividad_repo.obtener_ultima_proyeccion_actividad(conn)
    assert act is not None
    assert act.fase_ciclo == FaseCiclo.ESTABLE


def test_seguridad_intentos_fallidos_y_bloqueo(test_db):
    """Verifica incremento de intentos erróneos y bloqueo al llegar a 5 intentos."""
    conn, _ = test_db

    user = usuario_repo.obtener_usuario_por_identificador(conn, "35123456")
    assert user is not None
    assert user.intentos_fallidos == 0

    for i in range(1, 6):
        intentos = usuario_repo.registrar_intento_fallido(conn, user.id, max_intentos=5)
        assert intentos == i

    bloqueado = usuario_repo.obtener_usuario_por_id(conn, user.id)
    assert bloqueado.intentos_fallidos == 5
    assert bloqueado.bloqueado_hasta is not None

    usuario_repo.actualizar_login_exitoso(conn, user.id)
    restaurado = usuario_repo.obtener_usuario_por_id(conn, user.id)
    assert restaurado.intentos_fallidos == 0
    assert restaurado.bloqueado_hasta is None


def test_transaction_rollback_en_error(test_db):
    """Verifica que transaction() revierte completamente los cambios si ocurre una excepción."""
    _, tmp_path = test_db

    with pytest.raises(ValueError):
        with transaction(db_path=tmp_path) as conn_tx:
            persona_repo.crear_persona(
                conn_tx,
                Persona(
                    dni="99999991",
                    nombre_completo="Transacción Cancelada",
                    categoria_laboral=CategoriaLaboral.EMPLEADO_PRIVADO,
                ),
            )
            # Forzar falla para comprobar rollback
            raise ValueError("Falla simulada a mitad de transacción")

    conn_check = get_db_connection(tmp_path)
    persona_fallida = persona_repo.obtener_persona_por_dni(conn_check, "99999991")
    assert persona_fallida is None
    conn_check.close()
