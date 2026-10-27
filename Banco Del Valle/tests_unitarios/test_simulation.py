"""
Banco del Valle — Scoring Calculator & Lending Engine
Suite de Pruebas Unitarias para el Motor de Simulación Temporal.
Valida el Simulation Clock, el cierre diario (Daily Tick) y tráfico sintético.
"""

from datetime import date, timedelta
import os
import tempfile
import pytest

from src.database.connection import get_db_connection, init_db
from src.database.repositories import (
    balance_repo,
    cuenta_repo,
    deposito_repo,
    persona_repo,
    prestamo_repo,
)
from src.domain.models import (
    CategoriaLaboral,
    CuentaTransaccional,
    Cuota,
    EstadoPlazoFijo,
    EstadoPrestamo,
    Persona,
    PlazoFijo,
    Prestamo,
)
from src.simulation.clock import SimulationClock
from src.simulation.daily_tick import ejecutar_cierre_diario
from src.simulation.synthetic_traffic import inyectar_trafico_sintetico


@pytest.fixture
def sim_db():
    """Crea una base de datos temporal para pruebas de simulación."""
    tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = tmp_file.name
    tmp_file.close()

    init_db(db_path=tmp_path, seed_demo=True)
    conn = get_db_connection(tmp_path)

    yield conn, tmp_path

    conn.close()
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)


def test_simulation_clock_controls():
    """Valida avance de días, pausas y configuración de velocidad en el reloj."""
    reloj = SimulationClock(fecha_inicial=date(2026, 10, 1))

    assert reloj.fecha_actual == date(2026, 10, 1)
    assert reloj.en_pausa is True

    # Reanudar y avanzar
    reloj.reanudar()
    assert reloj.en_pausa is False

    nueva_fecha = reloj.avanzar_un_dia()
    assert nueva_fecha == date(2026, 10, 2)
    assert reloj.dias_transcurridos == 1

    fecha_saltada = reloj.avanzar_dias(10)
    assert fecha_saltada == date(2026, 10, 12)
    assert reloj.dias_transcurridos == 11

    reloj.fijar_velocidad(0.5)
    assert reloj.segundos_por_dia == 0.5


def test_daily_tick_rendimiento_flexible_juan_jose(sim_db):
    """Valida que Juan José reciba exactamente $2.342,47 diarios por su saldo de $3M al 28.5%."""
    conn, _ = sim_db

    cuenta_juan = cuenta_repo.obtener_cuenta_por_alias(conn, "JUAN.BANCO.VALLE")
    saldo_anterior = cuenta_juan.saldo_actual  # $3.000.000

    fecha_sim = date(2026, 10, 2)
    tick_res = ejecutar_cierre_diario(conn, fecha_sim)

    assert tick_res.rendimientos_flexibles_acreditados > 0

    cuenta_actualizada = cuenta_repo.obtener_cuenta_por_alias(conn, "JUAN.BANCO.VALLE")
    interes_esperado = round(3000000.0 * 0.285 / 365.0, 2)  # $2.342,47
    assert cuenta_actualizada.saldo_actual == round(saldo_anterior + interes_esperado, 2)


def test_daily_tick_cobro_automatico_cuota(sim_db):
    """Valida que una cuota vencida sea debitada automáticamente si hay saldo suficiente."""
    conn, _ = sim_db
    persona = persona_repo.obtener_persona_por_dni(conn, "35123456")

    # Crear préstamo con cuota que vence hoy
    fecha_hoy = date(2026, 10, 5)
    cuota = Cuota(numero_cuota=1, monto_cuota=100000.0, fecha_vencimiento=fecha_hoy.isoformat())
    p_id = prestamo_repo.crear_prestamo(
        conn,
        Prestamo(
            persona_id=persona.id,
            monto_capital=100000.0,
            tasa_nominal_anual=0.60,
            cantidad_cuotas=1,
            fecha_otorgamiento="2026-09-05",
            estado=EstadoPrestamo.ACTIVO,
        ),
        cronograma=[cuota],
    )

    tick_res = ejecutar_cierre_diario(conn, fecha_hoy)
    assert tick_res.cuotas_cobradas >= 1

    prestamo_actualizado = prestamo_repo.obtener_prestamo_por_id(conn, p_id)
    assert prestamo_actualizado.estado == EstadoPrestamo.CANCELADO

    cuotas_p = prestamo_repo.obtener_cuotas_por_prestamo(conn, p_id)
    assert cuotas_p[0].fecha_pago == fecha_hoy.isoformat()
    assert cuotas_p[0].dias_mora == 0


def test_daily_tick_mora_por_fondos_insuficientes(sim_db):
    """Valida que si una cuota vence y la cuenta no tiene saldo, se aplique mora y punitorios."""
    conn, _ = sim_db

    # Crear persona sin fondos
    persona_sin_fondos = Persona(
        dni="44000111",
        nombre_completo="Deudor Sin Saldo",
        categoria_laboral=CategoriaLaboral.AUTONOMO_MONOTRIBUTO,
        ingreso_mensual_comprobado=500000.0,
        monto_sueldo_acreditado=0.0,
    )
    p_id = persona_repo.crear_persona(conn, persona_sin_fondos)
    cuenta_repo.crear_cuenta(
        conn,
        CuentaTransaccional(
            persona_id=p_id,
            cbu="2850001299999999999991",
            alias="DEUDOR.SIN.SALDO",
            saldo_actual=0.0,  # Sin saldo
        ),
    )

    fecha_vencimiento = date(2026, 10, 1)
    fecha_corte = date(2026, 10, 11)  # 10 días de atraso
    cuota = Cuota(numero_cuota=1, monto_cuota=50000.0, fecha_vencimiento=fecha_vencimiento.isoformat())
    prest_id = prestamo_repo.crear_prestamo(
        conn,
        Prestamo(
            persona_id=p_id,
            monto_capital=50000.0,
            tasa_nominal_anual=0.60,
            cantidad_cuotas=1,
            fecha_otorgamiento="2026-09-01",
            estado=EstadoPrestamo.ACTIVO,
        ),
        cronograma=[cuota],
    )

    tick_res = ejecutar_cierre_diario(conn, fecha_corte)
    assert tick_res.cuotas_en_mora >= 1

    prestamo = prestamo_repo.obtener_prestamo_por_id(conn, prest_id)
    assert prestamo.estado == EstadoPrestamo.EN_MORA

    cuotas = prestamo_repo.obtener_cuotas_por_prestamo(conn, prest_id)
    assert cuotas[0].dias_mora == 10
    assert cuotas[0].intereses_punitorios > 0


def test_daily_tick_liquidacion_plazo_fijo_vencido(sim_db):
    """Valida que un plazo fijo que vence sea liquidado acreditando capital + interés a la cuenta."""
    conn, _ = sim_db
    persona = persona_repo.obtener_persona_por_dni(conn, "35123456")
    cuenta_juan = cuenta_repo.obtener_cuenta_por_alias(conn, "JUAN.BANCO.VALLE")
    saldo_previo = cuenta_juan.saldo_actual

    fecha_vencimiento = date(2026, 10, 31)
    pf_id = deposito_repo.crear_plazo_fijo(
        conn,
        PlazoFijo(
            persona_id=persona.id,
            monto_depositado=1000000.0,
            tasa_nominal_anual=0.38,
            fecha_inicio="2026-10-01",
            fecha_vencimiento=fecha_vencimiento.isoformat(),
            intereses_a_generar=31232.88,
            estado=EstadoPlazoFijo.ACTIVO,
        ),
    )

    tick_res = ejecutar_cierre_diario(conn, fecha_vencimiento)
    assert tick_res.plazos_fijos_liquidados >= 1

    pf_actualizado = deposito_repo.obtener_plazo_fijo_por_id(conn, pf_id)
    assert pf_actualizado.estado == EstadoPlazoFijo.LIQUIDADO

    cuenta_despues = cuenta_repo.obtener_cuenta_por_alias(conn, "JUAN.BANCO.VALLE")
    assert cuenta_despues.saldo_actual > saldo_previo + 1000000.0


def test_daily_tick_recalcula_balance_y_encajes(sim_db):
    """Valida que cada cierre diario emita un snapshot actualizado de solvencia y encajes BCRA."""
    conn, _ = sim_db

    fecha_eval = date(2026, 10, 15)
    tick_res = ejecutar_cierre_diario(conn, fecha_eval)

    assert tick_res.balance_snapshot_id is not None
    ultimo_b = balance_repo.obtener_ultimo_balance(conn)
    assert ultimo_b.fecha_corte == fecha_eval.isoformat()
    assert ultimo_b.encaje_obligatorio_bcra > 0
    assert ultimo_b.cashflow_seguro_prestable > 0


def test_inyectar_trafico_sintetico(sim_db):
    """Valida la inyección de operaciones sintéticas sin generar errores de base de datos."""
    conn, _ = sim_db

    res = inyectar_trafico_sintetico(
        conn,
        fecha_simulada=date(2026, 10, 20),
        prob_deposito=1.0,  # Forzar depósito
        prob_credito=1.0,   # Forzar crédito
        prob_plazo_fijo=1.0 # Forzar plazo fijo
    )
    assert isinstance(res, dict)
    assert res["depositos_generados"] >= 1
    assert res["creditos_otorgados"] >= 1
