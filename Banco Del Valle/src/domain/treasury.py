"""
Módulo de cálculo de encajes mínimos BCRA, liquidez ALM y margen financiero (P&L).
Aplica el algoritmo de Cashflow Seguro Prestable, reinversión y proyecciones multi-escenario.
Referencia de diseño: docs/normativa_encajes_bcra.md
"""

from __future__ import annotations
from typing import Tuple, List
from src.domain.models import BalancePatrimonio, PosicionLiquidez


# ============================================================================
# 1. RÉGIMEN DE EFECTIVO MÍNIMO (ENCAJES REGULATORIOS BCRA)
# ============================================================================

def calcular_capacidad_prestable_bruta(
    monto_deposito: float,
    alicuota_encaje: float,
) -> Tuple[float, float]:
    """
    Desglosa un depósito captado en reserva obligatoria inmovilizada y capacidad prestable bruta.
    
    Regla normativa BCRA:
    - Reserva obligatoria inmovilizada = Deposito * alicuota_encaje
    - Capacidad prestable bruta = Deposito * (1 - alicuota_encaje)
    
    Retorna: (reserva_inmovilizada, capacidad_prestable_bruta)
    """
    if monto_deposito < 0.0:
        raise ValueError(f"El depósito no puede ser negativo: {monto_deposito}")
    if not (0.0 <= alicuota_encaje <= 1.0):
        raise ValueError(f"La alícuota de encaje debe estar entre 0.0 y 1.0: {alicuota_encaje}")

    reserva = round(monto_deposito * alicuota_encaje, 2)
    prestable = round(monto_deposito - reserva, 2)
    return reserva, prestable


def calcular_encaje_requerido(
    total_flexibles: float,
    total_plazos_fijos: float,
    alicuota_flex: float = 0.30,  # 30% encaje cuenta flexible / vista
    alicuota_pf: float = 0.12,    # 12% encaje plazo fijo tradicional (30-59d)
) -> Tuple[float, float, float]:
    """
    Calcula la posición obligatoria de Efectivo Mínimo total exigida por el BCRA.
    
    Fórmula:
        Encaje Total = (Depósitos Flexibles * 0.30) + (Plazos Fijos * 0.12)
        
    Retorna: (encaje_flexibles, encaje_plazos_fijos, encaje_total_exigido)
    """
    reserva_flex, _ = calcular_capacidad_prestable_bruta(total_flexibles, alicuota_flex)
    reserva_pf, _ = calcular_capacidad_prestable_bruta(total_plazos_fijos, alicuota_pf)
    encaje_total = round(reserva_flex + reserva_pf, 2)
    return reserva_flex, reserva_pf, encaje_total


# ============================================================================
# 2. ALGORITMO DE CASHFLOW SEGURO PRESTABLE (ALM)
# ============================================================================

def calcular_cashflow_seguro(
    balance: BalancePatrimonio,
    colchon_pct: float = 0.05,
    compromisos_30d: float = 0.0,
    alicuota_flex: float = 0.30,
    alicuota_pf: float = 0.12,
) -> float:
    """
    Determina el capital líquido máximo que el banco puede prestar sin incurrir en descalce
    de plazos (maturity mismatch) ni violar los encajes legales del BCRA.
    
    Fórmula matemática ALM (docs/multiplicador_y_cashflow_prestable.md):
        CF_seguro = Flexibles_Libres + PF_Libres + Patrimonio_Propio
                    - Cartera_Activa - Colchón_Precautorio - Compromisos_30d
    Donde:
        - Flexibles_Libres = Depósitos_Flexibles * (1 - 0.30)
        - PF_Libres = Plazos_Fijos * (1 - 0.12)
        - Colchón_Precautorio = Total_Depósitos * colchon_pct (5% a 10%)
    """
    _, libres_flex = calcular_capacidad_prestable_bruta(balance.total_depositos_flexibles, alicuota_flex)
    _, libres_pf = calcular_capacidad_prestable_bruta(balance.total_depositos_plazo_fijo, alicuota_pf)

    total_depositos = balance.total_depositos_flexibles + balance.total_depositos_plazo_fijo
    colchon = round(total_depositos * colchon_pct, 2)

    cf_calculado = (
        libres_flex
        + libres_pf
        + balance.capital_propio_patrimonio
        - balance.total_prestado_activo
        - colchon
        - compromisos_30d
    )

    # El cashflow prestable nunca puede ser menor a 0.0 (en caso de iliquidez transitoria)
    return max(0.0, round(cf_calculado, 2))


def verificar_disponibilidad_desembolso(
    monto_solicitado: float,
    balance: BalancePatrimonio,
    colchon_pct: float = 0.05,
    compromisos_30d: float = 0.0,
) -> PosicionLiquidez:
    """
    Evalúa si la tesorería del banco autoriza el desembolso de un nuevo préstamo.
    
    Regla estricta:
    - Si monto_solicitado <= CF_seguro -> Desembolso habilitado.
    - Si monto_solicitado > CF_seguro -> Desembolso bloqueado para salvaguardar encajes.
    """
    if monto_solicitado <= 0.0:
        raise ValueError("El monto a desembolsar debe ser mayor a cero.")

    _, _, encaje_exigido = calcular_encaje_requerido(
        balance.total_depositos_flexibles,
        balance.total_depositos_plazo_fijo,
    )

    cf_disponible = calcular_cashflow_seguro(
        balance=balance,
        colchon_pct=colchon_pct,
        compromisos_30d=compromisos_30d,
    )

    desembolso_ok = cf_disponible >= monto_solicitado
    mensaje = (
        f"Liquidez suficiente. Cashflow seguro disponible: ${cf_disponible:,.2f}."
        if desembolso_ok
        else (
            f"Desembolso pausado por Tesorería. Monto solicitado (${monto_solicitado:,.2f}) "
            f"supera el Cashflow Seguro Prestable (${cf_disponible:,.2f})."
        )
    )

    # Superávit sobre el encaje obligatorio
    superavit = round(cf_disponible, 2)

    return PosicionLiquidez(
        cumple_encaje_bcra=True,
        encaje_total_exigido=encaje_exigido,
        cashflow_seguro_disponible=cf_disponible,
        superavit_deficit_encaje=superavit,
        desembolso_autorizado=desembolso_ok,
        mensaje_alerta=mensaje,
    )


# ============================================================================
# 3. P&L BANCARIO (MARGEN FINANCIERO NETO Y REINVERSIÓN)
# ============================================================================

def calcular_margen_financiero_neto(
    intereses_cobrados: float,
    intereses_pagados: float,
    punitorios_cobrados: float = 0.0,
    incobrables: float = 0.0,
) -> Tuple[float, float]:
    """
    Calcula el resultado financiero operativo de la entidad (Net Interest Income - NII).
    
    Fórmulas (docs/margen_financiero_y_proyecciones_escenarios.md):
        Margen Bruto = Intereses Cobrados (Préstamos) - Intereses Pagados (PF + Flexibles)
        Resultado Operativo Neto = Margen Bruto + Punitorios - Pérdidas Incobrables
        
    Retorna: (margen_financiero_bruto, resultado_operativo_neto)
    """
    margen_bruto = round(intereses_cobrados - intereses_pagados, 2)
    resultado_neto = round(margen_bruto + punitorios_cobrados - incobrables, 2)
    return margen_bruto, resultado_neto


def capitalizar_utilidades_en_balance(
    balance: BalancePatrimonio,
    resultado_neto_periodo: float,
) -> BalancePatrimonio:
    """
    Ejecuta el ciclo de reinversión inmediata de ganancias del banco.
    
    Regla de negocio:
    1. Las utilidades netas se capitalizan en el Patrimonio Neto (capital_propio_patrimonio).
    2. Expandir directamente el Cashflow Seguro Prestable para el siguiente ciclo.
    """
    nuevo_patrimonio = round(balance.capital_propio_patrimonio + resultado_neto_periodo, 2)

    # Clonar el balance con el patrimonio actualizado
    nuevo_balance = BalancePatrimonio(
        id=balance.id,
        fecha_corte=balance.fecha_corte,
        total_depositos_plazo_fijo=balance.total_depositos_plazo_fijo,
        total_depositos_flexibles=balance.total_depositos_flexibles,
        encaje_obligatorio_bcra=balance.encaje_obligatorio_bcra,
        capital_propio_patrimonio=nuevo_patrimonio,
        total_prestado_activo=balance.total_prestado_activo,
        cashflow_seguro_prestable=0.0,
    )

    # Recalcula automáticamente el cashflow con el nuevo patrimonio propio
    nuevo_balance.cashflow_seguro_prestable = calcular_cashflow_seguro(nuevo_balance)
    return nuevo_balance


# ============================================================================
# 4. PROYECCIONES MULTI-ESCENARIO DE GANANCIAS Y PATRIMONIO
# ============================================================================

def proyectar_patrimonio_escenario(
    patrimonio_inicial: float,
    tasa_crecimiento_anual: float,
    meses: int = 12,
) -> List[float]:
    """
    Proyecta la curva patrimonial mensual bajo un escenario macroeconómico dado.
    
    Parámetros de referencia (docs/margen_financiero_y_proyecciones_escenarios.md):
    - Escenario Optimista (Bull): +3.0% anual (+0.03)
    - Escenario Base (Consenso): +0.5% anual (+0.005)
    - Escenario Pesimista (Stress): -3.5% anual (-0.035)
    
    Retorna la lista de valores patrimoniales proyectados mes a mes (mes 0 a N).
    """
    if meses <= 0:
        return [patrimonio_inicial]

    tasa_mensual = tasa_crecimiento_anual / 12.0
    curva = [round(patrimonio_inicial, 2)]
    valor_actual = patrimonio_inicial

    for _ in range(1, meses + 1):
        valor_actual = valor_actual * (1.0 + tasa_mensual)
        curva.append(round(valor_actual, 2))

    return curva
