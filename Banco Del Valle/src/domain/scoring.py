"""
Módulo de calificación crediticia multi-factor, capacidad de repago y días de mora.
Ejecuta cálculo de punitorios diarios, scoring de individuos/PyMEs y fianza solidaria.
Referencia de diseño: docs/diagrama_logica_negocio_banco.md
"""

from __future__ import annotations
from datetime import date
from typing import Optional, Tuple
from src.domain.models import (
    Persona,
    Empresa,
    HistorialVeraz,
    ResultadoScoring,
    CategoriaLaboral,
    TipoSocietario,
)
from src.domain.interest_rate import calcular_tna_personalizada


# ============================================================================
# 1. CÁLCULO DE DÍAS DE MORA Y PUNITORIOS
# ============================================================================

def calcular_dias_mora_exactos(
    fecha_vencimiento: str,
    fecha_pago: Optional[str],
    fecha_actual: str,
) -> int:
    """
    Calcula los días calendario exactos de atraso de una cuota.
    
    Reglas:
    - Si la cuota ya fue pagada a término o antes (fecha_pago <= fecha_vencimiento) -> 0 días de mora.
    - Si se pagó con atraso (fecha_pago > fecha_vencimiento) -> días transcurridos hasta el pago.
    - Si aún NO se pagó (fecha_pago is None):
      * Si fecha_actual <= fecha_vencimiento -> 0 días de mora (al día).
      * Si fecha_actual > fecha_vencimiento -> días de atraso acumulados hasta hoy.
    """
    f_venc = date.fromisoformat(fecha_vencimiento)

    if fecha_pago:
        f_pago = date.fromisoformat(fecha_pago)
        if f_pago <= f_venc:
            return 0
        return (f_pago - f_venc).days

    f_act = date.fromisoformat(fecha_actual)
    if f_act <= f_venc:
        return 0

    return (f_act - f_venc).days


def calcular_intereses_punitorios(
    monto_cuota: float,
    dias_mora: int,
    tasa_punitoria_diaria: float = 0.001,  # 0.1% diario por mora
) -> float:
    """
    Liquida el recargo pecuniario diario por mora no justificada.
    
    Fórmula: Punitorios = Cuota * Tasa_diaria * Días_mora
    """
    if dias_mora <= 0 or monto_cuota <= 0.0:
        return 0.0

    punitorios = monto_cuota * tasa_punitoria_diaria * dias_mora
    return round(punitorios, 2)


# ============================================================================
# 2. CAPACIDAD DE PAGO Y RATIOS DE ENDEUDAMIENTO
# ============================================================================

def evaluar_capacidad_repago(
    ingreso_mensual: float,
    cuota_propuesta: float,
    ratio_maximo: float = 0.35,
) -> Tuple[bool, float]:
    """
    Verifica si la cuota mensual solicitada es sostenible para el cliente.
    
    Regla normativa:
    - Para personas: cuota <= 35% del ingreso neto (ratio_maximo = 0.35).
    - Para empresas: cuota <= 20% de facturación mensual (ratio_maximo = 0.20).
    
    Retorna: (aprobado: bool, ratio_obtenido: float)
    """
    if ingreso_mensual <= 0.0:
        return False, 1.0

    ratio = round(cuota_propuesta / ingreso_mensual, 4)
    aprobado = ratio <= ratio_maximo
    return aprobado, ratio


# ============================================================================
# 3. MOTOR DE SCORE INTERNO
# ============================================================================

def calcular_score_interno(
    veraz: HistorialVeraz,
    categoria_laboral: Optional[CategoriaLaboral] = None,
    antiguedad_laboral_meses: int = 12,
) -> int:
    """
    Pondera antecedentes crediticios externos y perfil laboral para emitir un score (300 a 950).
    
    Ponderación:
    1. Score externo Veraz (base de partida, ej. 650).
    2. Penalización por Situación BCRA:
       - Sit 1 (Normal): 0 pts.
       - Sit 2 (Atrasos leves): -100 pts.
       - Sit 3 (Problemas severos): -250 pts.
       - Sit >= 4 (Alto riesgo / Irrecuperable): -450 pts.
    3. Penalización por cheques rechazados sin fondos: -150 pts si tiene deuda.
    4. Bonificación por estabilidad:
       - Empleado Público o Jubilado: +60 pts (máxima estabilidad).
       - Empleado Privado con antigüedad >= 24 meses: +30 pts.
       - Empleado Privado con antigüedad < 12 meses: -40 pts.
    """
    score = veraz.score_externo

    # Penalización por situación crediticia BCRA
    if veraz.peor_situacion_bcra == 2:
        score -= 100
    elif veraz.peor_situacion_bcra == 3:
        score -= 250
    elif veraz.peor_situacion_bcra >= 4:
        score -= 450

    # Cheques rechazados
    if veraz.cheques_rechazados_monto > 0:
        score -= 150

    # Bonificación o ajuste laboral
    if categoria_laboral in (CategoriaLaboral.EMPLEADO_PUBLICO, CategoriaLaboral.JUBILADO):
        score += 60
    elif categoria_laboral == CategoriaLaboral.EMPLEADO_PRIVADO:
        if antiguedad_laboral_meses >= 24:
            score += 30
        elif antiguedad_laboral_meses < 12:
            score -= 40
    elif categoria_laboral == CategoriaLaboral.AUTONOMO_MONOTRIBUTO:
        if antiguedad_laboral_meses < 12:
            score -= 30

    # Límites acotados estándar buró
    return max(300, min(950, score))


# ============================================================================
# 4. EVALUACIÓN CREDITICIA COMPLETA (PERSONAS Y EMPRESAS)
# ============================================================================

def evaluar_scoring_persona(
    persona: Persona,
    veraz: HistorialVeraz,
    cuota_propuesta: float,
    tna_base: float = 0.60,
    ratio_maximo: float = 0.35,
) -> ResultadoScoring:
    """
    Dictamina la pre-aprobación o rechazo de un préstamo para Personas Humanas.
    
    Criterios excluyentes de rechazo:
    1. Situación BCRA >= 3 (Deudor con problemas o incobrable).
    2. Score crediticio interno < 450 puntos.
    3. Cuota propuesta supera el ratio máximo del ingreso mensual (35%).
    4. Cuenta bloqueada por AML o en trámite de baja.
    """
    # 1. Validación de estado de cuenta
    if persona.estado_cuenta.value not in ("ACTIVO", "PENDIENTE_DOCS"):
        return ResultadoScoring(
            aprobado=False,
            score_obtenido=300,
            tasa_anual_asignada=tna_base,
            cuota_mensual=cuota_propuesta,
            ratio_cuota_ingreso=1.0,
            requiere_fianza=False,
            motivo_decision=f"Cuenta no apta para crédito: {persona.estado_cuenta.value}.",
        )

    # 2. Validación de situación BCRA
    if veraz.peor_situacion_bcra >= 3:
        return ResultadoScoring(
            aprobado=False,
            score_obtenido=veraz.score_externo,
            tasa_anual_asignada=tna_base,
            cuota_mensual=cuota_propuesta,
            ratio_cuota_ingreso=0.0,
            requiere_fianza=False,
            motivo_decision=f"Rechazado por antecedentes negativos BCRA (Situación {veraz.peor_situacion_bcra}).",
        )

    # 3. Cálculo de Score Interno
    score_final = calcular_score_interno(
        veraz=veraz,
        categoria_laboral=persona.categoria_laboral,
        antiguedad_laboral_meses=persona.antiguedad_laboral_meses,
    )

    if score_final < 450:
        return ResultadoScoring(
            aprobado=False,
            score_obtenido=score_final,
            tasa_anual_asignada=tna_base,
            cuota_mensual=cuota_propuesta,
            ratio_cuota_ingreso=0.0,
            requiere_fianza=False,
            motivo_decision=f"Score crediticio insuficiente ({score_final} < 450 pts mínimos).",
        )

    # 4. Evaluación de Capacidad de Pago (Ratio Cuota/Ingreso)
    capacidad_ok, ratio_calculado = evaluar_capacidad_repago(
        ingreso_mensual=persona.ingreso_mensual_comprobado,
        cuota_propuesta=cuota_propuesta,
        ratio_maximo=ratio_maximo,
    )

    if not capacidad_ok:
        return ResultadoScoring(
            aprobado=False,
            score_obtenido=score_final,
            tasa_anual_asignada=tna_base,
            cuota_mensual=cuota_propuesta,
            ratio_cuota_ingreso=ratio_calculado,
            requiere_fianza=False,
            motivo_decision=(
                f"Cuota propuesta (${cuota_propuesta:,.2f}) excede el tope del "
                f"{int(ratio_maximo*100)}% del ingreso mensual ({ratio_calculado*100:.1f}%)."
            ),
        )

    # 5. Pricing de Tasa según Score y Segmento
    spread_score = 0.0
    if score_final >= 750:
        spread_score = -0.03  # Descuento de tasa para excelentes pagadores
    elif score_final < 550:
        spread_score = 0.05   # Recargo de tasa para perfiles de mayor volatilidad

    tna_asignada = calcular_tna_personalizada(
        tna_base=tna_base,
        spread_scoring=spread_score,
        categoria_laboral=persona.categoria_laboral,
    )

    return ResultadoScoring(
        aprobado=True,
        score_obtenido=score_final,
        tasa_anual_asignada=tna_asignada,
        cuota_mensual=cuota_propuesta,
        ratio_cuota_ingreso=ratio_calculado,
        requiere_fianza=False,
        motivo_decision="Crédito pre-aprobado exitosamente con perfil crediticio solvente.",
    )


def evaluar_scoring_empresa(
    empresa: Empresa,
    veraz: HistorialVeraz,
    cuota_propuesta: float,
    tna_base: float = 0.55,
    ratio_maximo_facturacion: float = 0.20,
) -> ResultadoScoring:
    """
    Dictamina la pre-aprobación o rechazo de crédito comercial / productivo para PyMEs.
    
    Reglas de negocio (project.md Sección 3.A.3):
    1. Facturación mensual = facturacion_anual_comprobada / 12.
    2. Cuota máxima <= 20% de la facturación mensual comprobada.
    3. Fianza solidaria: Exigida para tipos societarios SAS y SRL con fianza de socios.
    4. Cooperativas y Mutuales: Evaluadas con informe de excedentes y exención impositiva.
    """
    if veraz.peor_situacion_bcra >= 3:
        return ResultadoScoring(
            aprobado=False,
            score_obtenido=veraz.score_externo,
            tasa_anual_asignada=tna_base,
            cuota_mensual=cuota_propuesta,
            ratio_cuota_ingreso=0.0,
            requiere_fianza=False,
            motivo_decision=f"Rechazado por antecedentes corporativos negativos BCRA (Situación {veraz.peor_situacion_bcra}).",
        )

    facturacion_mensual = empresa.facturacion_anual_comprobada / 12.0
    capacidad_ok, ratio_calculado = evaluar_capacidad_repago(
        ingreso_mensual=facturacion_mensual,
        cuota_propuesta=cuota_propuesta,
        ratio_maximo=ratio_maximo_facturacion,
    )

    if not capacidad_ok:
        return ResultadoScoring(
            aprobado=False,
            score_obtenido=veraz.score_externo,
            tasa_anual_asignada=tna_base,
            cuota_mensual=cuota_propuesta,
            ratio_cuota_ingreso=ratio_calculado,
            requiere_fianza=False,
            motivo_decision=(
                f"Cuota excede el límite del {int(ratio_maximo_facturacion*100)}% "
                f"de la facturación mensual promedio ({ratio_calculado*100:.1f}%)."
            ),
        )

    # Determinación de requerimiento de fianza solidaria
    requiere_fianza = (
        empresa.requiere_fianza_socios
        or empresa.tipo_societario in (TipoSocietario.SAS, TipoSocietario.SRL)
    )

    tna_asignada = tna_base
    if empresa.tipo_societario in (TipoSocietario.COOPERATIVA, TipoSocietario.MUTUAL):
        tna_asignada = max(0.35, round(tna_base - 0.04, 4))  # Fomento productivo social

    return ResultadoScoring(
        aprobado=True,
        score_obtenido=veraz.score_externo,
        tasa_anual_asignada=tna_asignada,
        cuota_mensual=cuota_propuesta,
        ratio_cuota_ingreso=ratio_calculado,
        requiere_fianza=requiere_fianza,
        motivo_decision=(
            "Crédito PyME aprobado."
            + (" Requiere suscripción de fianza solidaria de los socios." if requiere_fianza else "")
        ),
    )
