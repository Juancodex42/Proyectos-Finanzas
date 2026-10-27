"""
Módulo de matemática financiera, formación de tasas de interés y amortización francesa.
Calcula rendimientos flexibles diarios (28.5% TNA), plazos fijos y cronograma Francés.
Referencia de diseño: docs/diagrama_plazos_fijos_flexibles_prestamos.md
"""

from __future__ import annotations
from typing import Optional, Tuple
from src.domain.models import (
    PlanAmortizacion,
    CuotaDetalleFrances,
    CategoriaLaboral,
)


# ============================================================================
# 1. PRICING Y FORMACIÓN DE TASA NOMINAL ANUAL (TNA)
# ============================================================================

def calcular_tasa_mensual(tna: float) -> float:
    """
    Convierte una Tasa Nominal Anual (TNA) en la tasa periódica efectiva mensual.
    
    Fórmula: i = TNA / 12
    Ejemplo: 0.60 TNA -> 0.05 (5% mensual)
    """
    if tna < 0.0:
        raise ValueError(f"La TNA no puede ser negativa: {tna}")
    return round(tna / 12.0, 8)


def calcular_tna_personalizada(
    tna_base: float,
    spread_scoring: float = 0.0,
    categoria_laboral: Optional[CategoriaLaboral] = None,
    tna_piso: float = 0.40,
) -> float:
    """
    Determina la Tasa Nominal Anual final aplicable a un solicitante de crédito.
    
    Reglas de negocio (project.md Sección 3.A.3):
    - Base: TNA fijada por política macroeconómica / Fisher.
    - Spread: Adicional según score de riesgo del solicitante.
    - Bonificación laboral:
      * Empleado Público o Jubilado: Descuento de 3 puntos porcentuales (-0.03).
      * Empleado Privado: Tasa neutral (sin descuento).
      * Monotributista / Autónomo: Recargo prudencial (+0.02).
    - Límite regulatorio: Nunca puede descender por debajo de tna_piso.
    """
    bonificacion = 0.0
    if categoria_laboral in (CategoriaLaboral.EMPLEADO_PUBLICO, CategoriaLaboral.JUBILADO):
        bonificacion = 0.03
    elif categoria_laboral == CategoriaLaboral.AUTONOMO_MONOTRIBUTO:
        bonificacion = -0.02  # Recargo de riesgo por ingreso variable

    tna_calculada = tna_base + spread_scoring - bonificacion
    tna_final = max(tna_calculada, tna_piso)
    return round(tna_final, 4)


# ============================================================================
# 2. SISTEMA FRANCÉS DE AMORTIZACIÓN (CUOTAS CONSTANTES)
# ============================================================================

def calcular_cuota_frances(capital: float, tna: float, cuotas: int) -> float:
    """
    Calcula el importe de la cuota constante mensual bajo el Sistema Francés.
    
    Fórmula:
        C = K * [ i * (1 + i)^n ] / [ (1 + i)^n - 1 ]
    Donde:
        K = capital inicial
        i = tasa mensual (tna / 12)
        n = cantidad de cuotas
        
    Caso límite: si tna == 0 -> C = K / n.
    """
    if capital <= 0.0:
        raise ValueError(f"El capital debe ser estrictamente positivo: {capital}")
    if cuotas <= 0:
        raise ValueError(f"La cantidad de cuotas debe ser mayor a cero: {cuotas}")

    i = calcular_tasa_mensual(tna)

    if i == 0.0:
        return round(capital / cuotas, 2)

    factor = (1.0 + i) ** cuotas
    cuota = capital * (i * factor) / (factor - 1.0)
    return round(cuota, 2)


def generar_cronograma_frances(capital: float, tna: float, cuotas: int) -> PlanAmortizacion:
    """
    Genera el cuadro de marcha completo de un préstamo bajo Sistema Francés.
    
    Propiedades matemáticas estrictas:
    1. La cuota periódica total es constante (excepto ajuste de centavos final).
    2. En cada período, el interés disminuye (I_t = Saldo_anterior * i).
    3. En cada período, la amortización de capital aumenta (A_t = Cuota - I_t).
    4. La suma de todas las amortizaciones de capital debe ser idéntica al capital inicial.
    5. El saldo final al vencer la última cuota debe ser exactamente 0.00.
    """
    if capital <= 0.0 or cuotas <= 0:
        raise ValueError("Capital y cuotas deben ser valores positivos.")

    i = calcular_tasa_mensual(tna)
    cuota_fija = calcular_cuota_frances(capital, tna, cuotas)

    saldo_restante = float(capital)
    cronograma = []
    total_intereses = 0.0

    for nro in range(1, cuotas + 1):
        # Cálculo del interés del período sobre el saldo deudor remanente
        interes_cuota = round(saldo_restante * i, 2)

        # En la última cuota, se absorbe cualquier residuo de redondeo de centavos
        if nro == cuotas:
            capital_cuota = round(saldo_restante, 2)
            monto_cuota_ajustado = round(capital_cuota + interes_cuota, 2)
            saldo_restante = 0.0
        else:
            capital_cuota = round(cuota_fija - interes_cuota, 2)
            # Salvaguarda: si por redondeo supera el saldo
            if capital_cuota > saldo_restante:
                capital_cuota = round(saldo_restante, 2)
            saldo_restante = round(saldo_restante - capital_cuota, 2)
            monto_cuota_ajustado = cuota_fija

        total_intereses = round(total_intereses + interes_cuota, 2)

        detalle = CuotaDetalleFrances(
            numero_cuota=nro,
            monto_cuota=monto_cuota_ajustado,
            capital_amortizado=capital_cuota,
            interes_cuota=interes_cuota,
            saldo_capital_restante=max(0.0, saldo_restante),
        )
        cronograma.append(detalle)

    return PlanAmortizacion(
        monto_capital=round(capital, 2),
        tna=round(tna, 4),
        cantidad_cuotas=cuotas,
        cuota_constante=cuota_fija,
        total_intereses=total_intereses,
        cronograma=cronograma,
    )


# ============================================================================
# 3. CAPTACIÓN PASIVA Y RENDIMIENTOS (FLEXIBLES Y PLAZOS FIJOS)
# ============================================================================

def calcular_interes_flexible_diario(saldo: float, tna_flexible: float = 0.285) -> float:
    """
    Devenga los intereses diarios de una cuenta transaccional flexible a la vista.
    
    Regla de negocio (docs/homebanking_ux_cuentas_sueldo.md):
        Rendimiento Diario = Saldo * (TNA_flexible / 365)
        
    Ejemplo con Juan José:
        $3.000.000 * (0.285 / 365) = $2.342,4657... -> $2.342,47
    """
    if saldo <= 0.0:
        return 0.0
    if tna_flexible < 0.0:
        raise ValueError("La TNA flexible no puede ser negativa.")

    rendimiento_diario = saldo * (tna_flexible / 365.0)
    return round(rendimiento_diario, 2)


def calcular_interes_plazo_fijo(monto_capital: float, tna: float, dias_plazo: int) -> float:
    """
    Calcula los intereses ganados al vencimiento de un depósito a plazo fijo tradicional.
    
    Fórmula estándar BCRA:
        Interés = Capital * TNA * (Días Plazo / 365)
        
    Ejemplo:
        $1.000.000 al 38% TNA a 30 días:
        $1.000.000 * 0.38 * (30 / 365) = $31.232,88
    """
    if monto_capital <= 0.0:
        raise ValueError("El monto del plazo fijo debe ser positivo.")
    if dias_plazo < 30:
        raise ValueError(f"El plazo mínimo regulatorio del BCRA es de 30 días. Recibido: {dias_plazo}")

    intereses = monto_capital * tna * (dias_plazo / 365.0)
    return round(intereses, 2)


def liquidar_cancelacion_anticipada_pf(monto_capital: float) -> Tuple[float, float]:
    """
    Ejecuta la regla regulatoria de cancelación anticipada de plazo fijo (norma BCRA).
    
    Regla estricta:
    - Se reintegra el 100% del capital inicial al ahorrista.
    - Se anulan la totalidad de los intereses ganados ($0,00).
    
    Retorna: (capital_reintegrado, intereses_liquidados)
    """
    if monto_capital <= 0.0:
        raise ValueError("El capital a rescatar debe ser positivo.")

    capital_reintegrado = round(monto_capital, 2)
    intereses_liquidados = 0.0
    return capital_reintegrado, intereses_liquidados
