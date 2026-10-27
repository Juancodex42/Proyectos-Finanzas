"""
Pruebas Unitarias: Calificación Crediticia, Ratios y Días de Mora
Valida cálculo exacto de días de mora, punitorios diarios, límite cuota/ingreso (35%),
scoring multi-factor de individuos y fianza solidaria para PyMEs.
"""

from src.domain.scoring import (
    calcular_dias_mora_exactos,
    calcular_intereses_punitorios,
    evaluar_capacidad_repago,
    calcular_score_interno,
    evaluar_scoring_persona,
    evaluar_scoring_empresa,
)
from src.domain.models import (
    Persona,
    Empresa,
    HistorialVeraz,
    CategoriaLaboral,
    EstadoCuenta,
)


def test_dias_mora_exactos_al_dia():
    """Cuota no vencida debe devolver cero días de mora."""
    dias = calcular_dias_mora_exactos(
        fecha_vencimiento="2026-11-10",
        fecha_pago=None,
        fecha_actual="2026-11-05",
    )
    assert dias == 0
    assert calcular_intereses_punitorios(50000.0, dias) == 0.0


def test_dias_mora_atraso_calculado():
    """Cuota vencida el 10/11 con fecha actual 25/11 acumula exactamente 15 días."""
    dias = calcular_dias_mora_exactos(
        fecha_vencimiento="2026-11-10",
        fecha_pago=None,
        fecha_actual="2026-11-25",
    )
    assert dias == 15
    punitorios = calcular_intereses_punitorios(100000.0, dias, tasa_punitoria_diaria=0.001)
    # 100.000 * 0.001 * 15 = 1.500
    assert punitorios == 1500.0


def test_dias_mora_pago_a_termino():
    """Si la cuota fue pagada en fecha o con anticipación, los días de mora son 0."""
    dias = calcular_dias_mora_exactos(
        fecha_vencimiento="2026-11-10",
        fecha_pago="2026-11-10",
        fecha_actual="2026-11-30",
    )
    assert dias == 0


def test_dias_mora_pago_tardio():
    """Si la cuota venció el 10/11 y se pagó el 18/11, debe registrar 8 días de mora."""
    dias = calcular_dias_mora_exactos(
        fecha_vencimiento="2026-11-10",
        fecha_pago="2026-11-18",
        fecha_actual="2026-11-30",
    )
    assert dias == 8


def test_ratio_endeudamiento_persona_aprobado(persona_juan_jose: Persona):
    """
    Sueldo comprobado = $3.000.000.
    Cuota propuesta = $1.000.000 (33.3% del ingreso).
    Debe aprobarse por estar dentro del tope del 35%.
    """
    aprobado, ratio = evaluar_capacidad_repago(
        ingreso_mensual=persona_juan_jose.ingreso_mensual_comprobado,
        cuota_propuesta=1000000.0,
        ratio_maximo=0.35,
    )
    assert aprobado is True
    assert round(ratio, 3) == 0.333


def test_ratio_endeudamiento_persona_rechazado(persona_juan_jose: Persona):
    """
    Cuota propuesta = $1.200.000 (40.0% del ingreso).
    Debe rechazarse por superar el 35%.
    """
    aprobado, ratio = evaluar_capacidad_repago(
        ingreso_mensual=persona_juan_jose.ingreso_mensual_comprobado,
        cuota_propuesta=1200000.0,
        ratio_maximo=0.35,
    )
    assert aprobado is False
    assert ratio == 0.40


def test_scoring_persona_completo_exitoso(
    persona_juan_jose: Persona,
    veraz_limpio: HistorialVeraz,
):
    """Juan José con excelente veraz y cuota razonable obtiene crédito pre-aprobado."""
    resultado = evaluar_scoring_persona(
        persona=persona_juan_jose,
        veraz=veraz_limpio,
        cuota_propuesta=850000.0,
        tna_base=0.60,
    )
    assert resultado.aprobado is True
    assert resultado.score_obtenido >= 700
    assert resultado.tasa_anual_asignada <= 0.60  # Bonificación de buen score


def test_scoring_persona_rechazo_situacion_bcra_3(
    persona_juan_jose: Persona,
    veraz_moroso: HistorialVeraz,
):
    """Cliente con situación 3 en Veraz debe ser rechazado de forma excluyente."""
    resultado = evaluar_scoring_persona(
        persona=persona_juan_jose,
        veraz=veraz_moroso,
        cuota_propuesta=500000.0,
    )
    assert resultado.aprobado is False
    assert "Situación 3" in resultado.motivo_decision


def test_scoring_persona_rechazo_cuenta_bloqueada(
    persona_juan_jose: Persona,
    veraz_limpio: HistorialVeraz,
):
    """Si la cuenta del cliente está suspendida por AML, no se aprueban nuevos préstamos."""
    persona_juan_jose.estado_cuenta = EstadoCuenta.SUSPENDIDO_AML
    resultado = evaluar_scoring_persona(
        persona=persona_juan_jose,
        veraz=veraz_limpio,
        cuota_propuesta=100000.0,
    )
    assert resultado.aprobado is False
    assert "Cuenta no apta" in resultado.motivo_decision


def test_scoring_empresas_fianza_socios(
    empresa_agrovalle_sas: Empresa,
    veraz_limpio: HistorialVeraz,
):
    """
    Empresa tipo SAS con facturación de $10M mensuales y cuota de $1.5M (15% <= 20%).
    Debe aprobarse pero exigiendo fianza solidaria de los socios.
    """
    resultado = evaluar_scoring_empresa(
        empresa=empresa_agrovalle_sas,
        veraz=veraz_limpio,
        cuota_propuesta=1500000.0,
    )
    assert resultado.aprobado is True
    assert resultado.requiere_fianza is True


def test_scoring_empresas_rechazo_sobreendeudamiento(
    empresa_agrovalle_sas: Empresa,
    veraz_limpio: HistorialVeraz,
):
    """Cuota de $2.5M excede el 20% de la facturación mensual ($10M) -> Rechazo."""
    resultado = evaluar_scoring_empresa(
        empresa=empresa_agrovalle_sas,
        veraz=veraz_limpio,
        cuota_propuesta=2500000.0,  # 25% > 20%
    )
    assert resultado.aprobado is False
    assert "excede el límite del 20%" in resultado.motivo_decision
