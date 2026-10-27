"""
Pruebas Unitarias: Tesorería Bancaria, Encajes BCRA y ALM
Valida cálculo de reserva de efectivo mínimo (30% vs 12%), algoritmo de
Cashflow Seguro Prestable, bloqueo preventivo por iliquidez y reinversión de P&L.
"""

from src.domain.treasury import (
    calcular_capacidad_prestable_bruta,
    calcular_encaje_requerido,
    calcular_cashflow_seguro,
    verificar_disponibilidad_desembolso,
    calcular_margen_financiero_neto,
    capitalizar_utilidades_en_balance,
    proyectar_patrimonio_escenario,
)
from src.domain.models import BalancePatrimonio


def test_encaje_cuentas_flexibles():
    """
    Régimen de Efectivo Mínimo BCRA para depósitos a la vista (30% encaje).
    Para $10.000.000 captados:
    - Reserva obligatoria inmovilizada = $3.000.000
    - Capacidad prestable bruta = $7.000.000
    """
    monto = 10000000.0
    alicuota = 0.30
    reserva, prestable = calcular_capacidad_prestable_bruta(monto, alicuota)
    assert reserva == 3000000.0
    assert prestable == 7000000.0


def test_encaje_plazos_fijos():
    """
    Régimen de Efectivo Mínimo BCRA para plazos fijos a 30 días (12% encaje).
    Para $10.000.000 captados:
    - Reserva obligatoria inmovilizada = $1.200.000
    - Capacidad prestable bruta = $8.800.000
    """
    monto = 10000000.0
    alicuota = 0.12
    reserva, prestable = calcular_capacidad_prestable_bruta(monto, alicuota)
    assert reserva == 1200000.0
    assert prestable == 8800000.0


def test_calcular_encaje_requerido_total():
    """Valida la suma consolidada de reservas obligatorias de la entidad."""
    flexibles = 20000000.0   # Encaje: 6.000.000
    plazos_fijos = 15000000.0 # Encaje: 1.800.000
    r_flex, r_pf, total = calcular_encaje_requerido(flexibles, plazos_fijos)
    assert r_flex == 6000000.0
    assert r_pf == 1800000.0
    assert total == 7800000.0


def test_bloqueo_desembolso_por_iliquidez():
    """
    Caso crítico de prudencia ALM:
    El cliente califica pero el banco solo cuenta con $3.500.000 de Cashflow Seguro.
    Una solicitud por $5.000.000 debe ser pausada / no autorizada.
    """
    # Balance con Cashflow exacto de $3.500.000:
    # 5M flexibles libres de encaje (70% = 3.5M) + 250k capital - 250k colchon = 3.5M
    balance = BalancePatrimonio(
        total_depositos_flexibles=5000000.0,
        total_depositos_plazo_fijo=0.0,
        capital_propio_patrimonio=250000.0,
        total_prestado_activo=0.0,
    )
    cf = calcular_cashflow_seguro(balance)
    assert cf == 3500000.0

    posicion = verificar_disponibilidad_desembolso(
        monto_solicitado=5000000.0,
        balance=balance,
    )
    assert posicion.desembolso_autorizado is False
    assert "supera el Cashflow Seguro" in posicion.mensaje_alerta


def test_autorizacion_desembolso_con_liquidez(balance_bancario_inicial: BalancePatrimonio):
    """Con solvencia de $49.8M, una solicitud de $2.000.000 se aprueba de inmediato."""
    posicion = verificar_disponibilidad_desembolso(
        monto_solicitado=2000000.0,
        balance=balance_bancario_inicial,
    )
    assert posicion.desembolso_autorizado is True
    assert "Liquidez suficiente" in posicion.mensaje_alerta


def test_margen_financiero_neto():
    """Calcula el P&L bancario (Net Interest Income)."""
    bruto, neto = calcular_margen_financiero_neto(
        intereses_cobrados=1000000.0,
        intereses_pagados=400000.0,
        punitorios_cobrados=25000.0,
        incobrables=50000.0,
    )
    assert bruto == 600000.0
    assert neto == 575000.0


def test_capitalizar_utilidades_en_balance(balance_bancario_inicial: BalancePatrimonio):
    """
    Ciclo virtuoso de reinversión:
    Las utilidades netas incrementan el Patrimonio y expanden el Cashflow Prestable.
    """
    patrimonio_antes = balance_bancario_inicial.capital_propio_patrimonio
    ganancia_neta = 2500000.0

    balance_post = capitalizar_utilidades_en_balance(balance_bancario_inicial, ganancia_neta)
    assert balance_post.capital_propio_patrimonio == patrimonio_antes + ganancia_neta
    assert balance_post.cashflow_seguro_prestable > balance_bancario_inicial.cashflow_seguro_prestable


def test_proyeccion_patrimonio_escenarios():
    """Valida que la proyección optimista supere a la base y a la pesimista."""
    patrimonio_inicial = 50000000.0
    meses = 12

    curva_opt = proyectar_patrimonio_escenario(patrimonio_inicial, +0.03, meses)
    curva_base = proyectar_patrimonio_escenario(patrimonio_inicial, +0.005, meses)
    curva_pes = proyectar_patrimonio_escenario(patrimonio_inicial, -0.035, meses)

    assert curva_opt[-1] > curva_base[-1] > curva_pes[-1]
    assert curva_pes[-1] < patrimonio_inicial
