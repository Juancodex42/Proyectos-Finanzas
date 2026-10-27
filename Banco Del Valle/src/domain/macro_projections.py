"""
Módulo de sensibilidad macroeconómica, inflación esperada (REM) y actividad (EMAE/PBI).
Aplica la Ecuación de Fisher para tasas reales positivas y el factor cíclico F_macro.
Referencia de diseño: docs/proyecciones_inflacion_consultoras.md
"""

from __future__ import annotations
from typing import Tuple
from src.domain.models import FaseCiclo


# ============================================================================
# 1. INFLACIÓN ESPERADA Y ECUACIÓN DE FISHER
# ============================================================================

def calcular_inflacion_esperada_ponderada(
    inflacion_rem: float,
    inflacion_consultoras: float,
    peso_rem: float = 0.60,
) -> float:
    """
    Combina la mediana oficial del REM (BCRA) con el consenso de consultoras privadas.
    
    Fórmula:
        pi_esperada = (peso_rem * pi_rem) + ((1 - peso_rem) * pi_consultoras)
        
    Ejemplo: REM 45% (0.45) y Consultoras 48% (0.48) con peso 60/40 -> 46.2% (0.462).
    """
    if not (0.0 <= peso_rem <= 1.0):
        raise ValueError(f"El ponderador del REM debe estar entre 0.0 y 1.0: {peso_rem}")
    if inflacion_rem < 0.0 or inflacion_consultoras < 0.0:
        raise ValueError("Las expectativas de inflación no pueden ser negativas.")

    peso_consultoras = 1.0 - peso_rem
    inflacion_ponderada = (inflacion_rem * peso_rem) + (inflacion_consultoras * peso_consultoras)
    return round(inflacion_ponderada, 4)


def ajustar_piso_tasa_fisher(
    inflacion_esperada_12m: float,
    tasa_real_objetivo: float = 0.10,  # 10% rentabilidad real requerida
) -> float:
    """
    Calcula el piso mínimo de Tasa Nominal Anual (TNA) exigible mediante la Ecuación de Fisher.
    
    Fórmula exacta:
        (1 + i) = (1 + r) * (1 + pi^e)
        i = (1 + r) * (1 + pi^e) - 1
        
    Donde:
        r = tasa de interés real requerida (ej. 10% = 0.10)
        pi^e = inflación esperada a 12 meses (ej. 45% = 0.45)
        
    Resultado del ejemplo:
        i = (1 + 0.10) * (1 + 0.45) - 1 = 1.10 * 1.45 - 1 = 0.595 (59.5% TNA mínima).
    """
    if inflacion_esperada_12m < 0.0:
        raise ValueError(f"La inflación esperada no puede ser negativa: {inflacion_esperada_12m}")

    tasa_nominal_minima = ((1.0 + tasa_real_objetivo) * (1.0 + inflacion_esperada_12m)) - 1.0
    return round(tasa_nominal_minima, 4)


# ============================================================================
# 2. ACTIVIDAD ECONÓMICA (EMAE / PBI) Y FACTOR MACRO DE RIESGO
# ============================================================================

def determinar_fase_ciclo_economico(
    variacion_pbi_anual: float,
) -> Tuple[FaseCiclo, float]:
    """
    Clasifica la fase del ciclo macroeconómico según la variación proyectada del PBI/EMAE
    y asigna el factor de riesgo macroeconómico (F_macro).
    
    Escala de ajuste (docs/proyecciones_macro_actividad_economica.md):
    - Recesión Severa (PBI < -2%): F_macro = 1.40 (contracción crediticia máxima).
    - Recesión Leve (-2% <= PBI < -0.5%): F_macro = 1.25.
    - Estable (-0.5% <= PBI <= +1.0%): F_macro = 1.00 (neutral).
    - Expansión (PBI > +1.0%): F_macro = 0.875 (ampliación de capacidad de crédito).
    
    Retorna: (fase_ciclo: FaseCiclo, factor_macro: float)
    """
    if variacion_pbi_anual < -0.02:
        return FaseCiclo.RECESION_SEVERA, 1.40
    elif variacion_pbi_anual < -0.005:
        return FaseCiclo.RECESION_LEVE, 1.25
    elif variacion_pbi_anual <= 0.01:
        return FaseCiclo.ESTABLE, 1.00
    else:
        return FaseCiclo.EXPANSION, 0.875


def ajustar_ratio_endeudamiento_por_ciclo(
    ratio_base: float = 0.35,
    factor_macro: float = 1.0,
) -> float:
    """
    Contrae o expande el ratio máximo de cuota/ingreso permitido según el ciclo económico.
    
    Fórmula:
        Ratio_ajustado = Ratio_base / F_macro
        
    Ejemplo:
        - Ratio base = 35% (0.35)
        - En Recesión Severa (F_macro = 1.40):
          Ratio = 0.35 / 1.40 = 0.25 (25% del sueldo como límite máximo).
          Previene el sobreendeudamiento de las familias ante caída de ingresos reales.
    """
    if factor_macro <= 0.0:
        raise ValueError(f"El factor macro debe ser positivo: {factor_macro}")

    ratio_ajustado = ratio_base / factor_macro
    return round(ratio_ajustado, 4)


def ajustar_probabilidad_mora_simulada(
    mora_base: float,
    factor_macro: float,
) -> float:
    """
    Ajusta la probabilidad estocástica de mora en el motor de simulación acelerada (1s = 1d).
    
    Fórmula:
        Mora_simulada = Mora_base * F_macro
        
    En recesión (F_macro > 1.0), los atrasos y moras se incrementan sistémicamente.
    En expansión (F_macro < 1.0), el cumplimiento de pago mejora.
    """
    if mora_base < 0.0 or factor_macro < 0.0:
        raise ValueError("La mora base y el factor macro deben ser positivos.")

    mora_ajustada = min(1.0, mora_base * factor_macro)
    return round(mora_ajustada, 4)
