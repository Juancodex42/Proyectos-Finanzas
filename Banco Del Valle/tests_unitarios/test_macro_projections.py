"""
Pruebas Unitarias: Entorno Macroeconómico, Ecuación de Fisher y EMAE/PBI
Valida ponderación REM/consultoras, piso de tasas reales positivas (Fisher),
clasificación de fase de ciclo y contracción de ratios en recesión.
"""

import pytest
from src.domain.macro_projections import (
    calcular_inflacion_esperada_ponderada,
    ajustar_piso_tasa_fisher,
    determinar_fase_ciclo_economico,
    ajustar_ratio_endeudamiento_por_ciclo,
    ajustar_probabilidad_mora_simulada,
)
from src.domain.models import FaseCiclo


def test_inflacion_esperada_ponderada_60_40():
    """Mediana REM al 45% (peso 0.60) y Consultoras al 50% (peso 0.40) promedian 47%."""
    pi_esperada = calcular_inflacion_esperada_ponderada(
        inflacion_rem=0.45,
        inflacion_consultoras=0.50,
        peso_rem=0.60,
    )
    assert pi_esperada == 0.47


def test_ecuacion_fisher_piso_tasa():
    """
    Ecuación de Fisher:
        i = (1 + r) * (1 + pi^e) - 1
    Con rentabilidad real r = 10% (0.10) e inflación esperada pi^e = 45% (0.45):
        i = (1.10 * 1.45) - 1 = 0.595 (59.5% TNA mínima).
    """
    tna_piso = ajustar_piso_tasa_fisher(
        inflacion_esperada_12m=0.45,
        tasa_real_objetivo=0.10,
    )
    assert tna_piso == 0.595


def test_ecuacion_fisher_inflacion_negativa_error():
    """Inflación esperada negativa debe ser rechazada."""
    with pytest.raises(ValueError, match="no puede ser negativa"):
        ajustar_piso_tasa_fisher(-0.05)


def test_determinar_fase_recesion_severa():
    """Caída del PBI > 2% clasifica como RECESION_SEVERA con F_macro = 1.40."""
    fase, f_macro = determinar_fase_ciclo_economico(variacion_pbi_anual=-0.035)
    assert fase == FaseCiclo.RECESION_SEVERA
    assert f_macro == 1.40


def test_determinar_fase_recesion_leve():
    """Caída del PBI entre -0.5% y -2% clasifica como RECESION_LEVE con F_macro = 1.25."""
    fase, f_macro = determinar_fase_ciclo_economico(variacion_pbi_anual=-0.015)
    assert fase == FaseCiclo.RECESION_LEVE
    assert f_macro == 1.25


def test_determinar_fase_estable():
    """Variación del PBI entre -0.5% y +1.0% es neutral (ESTABLE, F_macro = 1.00)."""
    fase, f_macro = determinar_fase_ciclo_economico(variacion_pbi_anual=0.005)
    assert fase == FaseCiclo.ESTABLE
    assert f_macro == 1.00


def test_determinar_fase_expansion():
    """Crecimiento del PBI > +1.0% clasifica como EXPANSION con F_macro < 1.0."""
    fase, f_macro = determinar_fase_ciclo_economico(variacion_pbi_anual=0.025)
    assert fase == FaseCiclo.EXPANSION
    assert f_macro == 0.875


def test_factor_recesion_ajusta_tope_cuota():
    """
    En recesión severa (F_macro = 1.40):
    El ratio máximo cuota/ingreso se contrae del 35% al 25% del sueldo:
        Ratio = 0.35 / 1.40 = 0.25 (25.0%).
    """
    ratio_base = 0.35
    factor_recesion = 1.40
    ratio_contraido = ajustar_ratio_endeudamiento_por_ciclo(ratio_base, factor_recesion)
    assert ratio_contraido == 0.25


def test_ajustar_probabilidad_mora_simulada():
    """En recesión severa, la morosidad base del 5% escala al 7%."""
    mora_base = 0.05
    factor_macro = 1.40
    mora_ajustada = ajustar_probabilidad_mora_simulada(mora_base, factor_macro)
    assert mora_ajustada == 0.07
