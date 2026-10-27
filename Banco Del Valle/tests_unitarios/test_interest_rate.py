"""
Pruebas Unitarias: Matemática Financiera, Tasas y Sistema Francés.
Valida cuota constante, amortización, rendimiento diario y plazos fijos.
Referencia de diseño: docs/diagrama_plazos_fijos_flexibles_prestamos.md
"""

import pytest
from src.domain.interest_rate import (
    calcular_tasa_mensual,
    calcular_cuota_frances,
    generar_cronograma_frances,
    calcular_interes_flexible_diario,
    calcular_interes_plazo_fijo,
    liquidar_cancelacion_anticipada_pf,
    calcular_tna_personalizada,
)
from src.domain.models import CategoriaLaboral


def test_tasa_mensual_calculo():
    """Verifica que una TNA de 60% se convierta en una tasa periódica mensual de 5%."""
    tna = 0.60
    i_mensual = calcular_tasa_mensual(tna)
    assert i_mensual == pytest.approx(0.05)


def test_tasa_mensual_negativa_error():
    """Verifica que no se admitan tasas nominales anuales negativas."""
    with pytest.raises(ValueError, match="no puede ser negativa"):
        calcular_tasa_mensual(-0.10)


def test_sistema_frances_cuota_fija():
    """Valida el cálculo de cuota constante para $1.000.000 a 12 meses al 60% TNA."""
    capital = 1000000.0
    tna = 0.60
    cuotas = 12
    cuota = calcular_cuota_frances(capital, tna, cuotas)
    assert cuota == 112825.41


def test_sistema_frances_suma_amortizaciones():
    """
    Propiedad matemática esencial:
    La suma del capital amortizado de todas las cuotas debe ser exactamente
    igual al capital original prestado (tolerancia centesimal de ±0.05).
    """
    capital = 1000000.0
    tna = 0.60
    cuotas = 12
    plan = generar_cronograma_frances(capital, tna, cuotas)

    suma_capital_amortizado = sum(c.capital_amortizado for c in plan.cronograma)
    assert abs(suma_capital_amortizado - capital) <= 0.05
    assert len(plan.cronograma) == 12
    assert plan.cronograma[-1].saldo_capital_restante == 0.0


def test_interes_decreciente_capital_creciente():
    """
    En el Sistema Francés tradicional:
    El componente de interés disminuye mes a mes y el de capital aumenta.
    """
    capital = 1000000.0
    tna = 0.60
    cuotas = 12
    plan = generar_cronograma_frances(capital, tna, cuotas)

    for idx in range(len(plan.cronograma) - 2):
        actual = plan.cronograma[idx]
        siguiente = plan.cronograma[idx + 1]
        assert actual.interes_cuota >= siguiente.interes_cuota
        assert actual.capital_amortizado <= siguiente.capital_amortizado


def test_sistema_frances_tasa_cero():
    """Caso borde: crédito sin interés (TNA = 0) debe dividir el capital exactamente."""
    capital = 600000.0
    cuotas = 6
    cuota = calcular_cuota_frances(capital, tna=0.0, cuotas=cuotas)
    assert cuota == 100000.0

    plan = generar_cronograma_frances(capital, tna=0.0, cuotas=cuotas)
    assert plan.total_intereses == 0.0
    assert sum(c.capital_amortizado for c in plan.cronograma) == capital


def test_interes_flexible_diario_juan_jose():
    """
    Valida el devengamiento centesimal diario para Juan José:
    $3.000.000 al 28.5% TNA -> $3.000.000 * (0.285 / 365) = $2.342,47 por día.
    """
    saldo = 3000000.0
    tna_flex = 0.285
    rendimiento = calcular_interes_flexible_diario(saldo, tna_flex)
    assert rendimiento == 2342.47


def test_interes_flexible_diario_saldo_cero():
    """Saldo cero genera exactamente cero rendimiento."""
    assert calcular_interes_flexible_diario(0.0) == 0.0
    assert calcular_interes_flexible_diario(-1500.0) == 0.0


def test_interes_plazo_fijo_30_dias():
    """Depósito de $1.000.000 a 30 días al 38% TNA."""
    intereses = calcular_interes_plazo_fijo(1000000.0, tna=0.38, dias_plazo=30)
    assert intereses == 31232.88


def test_plazo_fijo_plazo_minimo_bcra_error():
    """El BCRA exige un plazo mínimo de 30 días para plazos fijos en pesos."""
    with pytest.raises(ValueError, match="mínimo regulatorio del BCRA es de 30 días"):
        calcular_interes_plazo_fijo(1000000.0, tna=0.38, dias_plazo=20)


def test_cancelacion_anticipada_plazo_fijo():
    """
    Regla normativa BCRA: rescate anticipado de plazo fijo devuelve
    el 100% del capital inicial y anula los intereses devengados ($0.00).
    """
    capital = 1000000.0
    cap_reintegrado, int_liquidados = liquidar_cancelacion_anticipada_pf(capital)
    assert cap_reintegrado == 1000000.0
    assert int_liquidados == 0.0


def test_pricing_tna_bonificacion_publico():
    """Empleado público o jubilado recibe 3 puntos de bonificación sobre la TNA base."""
    tna_base = 0.60
    tna_publico = calcular_tna_personalizada(
        tna_base=tna_base,
        spread_scoring=0.0,
        categoria_laboral=CategoriaLaboral.EMPLEADO_PUBLICO,
    )
    assert tna_publico == 0.57
