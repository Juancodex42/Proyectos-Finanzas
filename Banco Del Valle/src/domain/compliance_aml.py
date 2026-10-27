"""
Módulo de cumplimiento normativo UIF, prevención PLA/FT y ciclo de vida de cuentas.
Ejecuta monitoreo por Enfoque Basado en Riesgo (40 SMVM), protocolo RFI y Soft Delete.
Referencia de diseño: docs/compliance_aml_fraude_bajas.md
"""

from __future__ import annotations
from typing import Tuple, Optional
from src.domain.models import EstadoCuenta, ResultadoComplianceAML


# Constante regulatoria de referencia por defecto (Salario Mínimo, Vital y Móvil en Argentina)
SMVM_REFERENCIA_BASE = 300000.0  # $300.000 ARS base para simulador
UMBRAL_SMVM_OFICIAL = 40.0        # 40 SMVM según Resolución UIF N° 78/2025


# ============================================================================
# 1. MONITOREO TRANSACCIONAL Y ENFOQUE BASADO EN RIESGO (EBR)
# ============================================================================

def calcular_umbral_smvm_pesos(
    valor_smvm: float = SMVM_REFERENCIA_BASE,
    multiplicador: float = UMBRAL_SMVM_OFICIAL,
) -> float:
    """
    Calcula el valor en pesos del umbral regulatorio oficial de la UIF.
    
    Ejemplo: 40 SMVM * $300.000 = $12.000.000 ARS.
    """
    if valor_smvm <= 0.0 or multiplicador <= 0.0:
        raise ValueError("El valor del SMVM y el multiplicador deben ser positivos.")
    return round(valor_smvm * multiplicador, 2)


def evaluar_transaccion_aml(
    monto_operacion: float,
    perfil_mensual_estimado: float,
    valor_smvm: float = SMVM_REFERENCIA_BASE,
    umbral_smvm: float = UMBRAL_SMVM_OFICIAL,
) -> ResultadoComplianceAML:
    """
    Analiza una transacción entrante o saliente bajo las directrices de la UIF y BCRA.
    
    Principios rectores (docs/compliance_aml_fraude_bajas.md):
    1. Presunción de licitud de fondos bancarizados.
    2. Prohibición de bloqueos intempestivos: una alerta de monitoreo NUNCA congela la cuenta de inmediato.
    3. Si el monto supera el umbral objetivo (40 SMVM) Y se desvía sustancialmente del perfil histórico:
       - Se dispara alerta interna de monitoreo (alerta_aml = True).
       - Se requiere emisión de RFI (solicitud de justificación de fondos) con 30 días de plazo.
       - La cuenta permanece 100% operativa (operacion_admitida = True).
    """
    if monto_operacion < 0.0:
        raise ValueError("El monto de la operación no puede ser negativo.")

    umbral_pesos = calcular_umbral_smvm_pesos(valor_smvm, umbral_smvm)
    supera_umbral = monto_operacion >= umbral_pesos

    # Desvío significativo: cuando la operación supera 3 veces el perfil habitual y además supera 20 SMVM
    desvio_significativo = (
        perfil_mensual_estimado > 0.0
        and monto_operacion >= (perfil_mensual_estimado * 3.0)
        and monto_operacion >= (umbral_pesos * 0.5)
    )

    dispara_alerta = supera_umbral or desvio_significativo

    if dispara_alerta:
        observacion = (
            f"Alerta de Monitoreo Interno activada. Monto (${monto_operacion:,.2f}) "
            f"supera el umbral oficial de {int(umbral_smvm)} SMVM (${umbral_pesos:,.2f}) "
            "o presenta un desvío significativo del perfil habitual. "
            "Se emite RFI por 30 días hábiles. La cuenta continúa 100% OPERATIVA."
        )
        return ResultadoComplianceAML(
            operacion_admitida=True,
            alerta_aml=True,
            supera_umbral_smvm=supera_umbral,
            monto_operado=round(monto_operacion, 2),
            umbral_referencia=umbral_pesos,
            requiere_rfi=True,
            plazo_descargo_dias=30,
            observaciones=observacion,
        )

    return ResultadoComplianceAML(
        operacion_admitida=True,
        alerta_aml=False,
        supera_umbral_smvm=False,
        monto_operado=round(monto_operacion, 2),
        umbral_referencia=umbral_pesos,
        requiere_rfi=False,
        plazo_descargo_dias=0,
        observaciones="Transacción encuadrada dentro del perfil transaccional habitual.",
    )


# ============================================================================
# 2. PROTOCOLO DE INMOVILIZACIÓN CAUTELAR (CASOS TAXATIVOS)
# ============================================================================

def evaluar_protocolo_bloqueo(
    dias_sin_descargo: int = 0,
    docs_apocrifas: bool = False,
    orden_judicial: bool = False,
    listado_repet: bool = False,
) -> Tuple[bool, EstadoCuenta, str]:
    """
    Determina si corresponde la suspensión cautelar de una cuenta ('SUSPENDIDO_AML').
    
    Regla garantista estricta (docs/diagrama_usuarios_empresas_aml_bloqueos.md):
    El bloqueo preventivo ÚNICAMENTE procede ante 4 causales taxativas:
    1. Vencimiento del plazo de 30 días hábiles sin que el titular presente descargo (dias > 30).
    2. Documentación de origen de fondos comprobadamente falsa o apócrifa.
    3. Notificación de Oficio Judicial dictado por juez competente (embargo preventivo).
    4. Coincidencia confirmada en listas restrictivas de terrorismo (RePET).
    
    Retorna: (debe_bloquear: bool, nuevo_estado: EstadoCuenta, motivo: str)
    """
    if orden_judicial:
        return True, EstadoCuenta.SUSPENDIDO_AML, "Inmovilización cautelar por Oficio Judicial dictado por juez competente."

    if listado_repet:
        return True, EstadoCuenta.SUSPENDIDO_AML, "Bloqueo preventivo obligatorio por inclusión confirmada en RePET (Terrorismo)."

    if docs_apocrifas:
        return True, EstadoCuenta.SUSPENDIDO_AML, "Suspensión de cuenta por presentación de documentación probatoriamente apócrifa o fraudulenta."

    if dias_sin_descargo > 30:
        return (
            True,
            EstadoCuenta.SUSPENDIDO_AML,
            f"Inmovilización preventiva por vencimiento improrrogable del plazo legal ({dias_sin_descargo}d > 30d) sin descargo RFI.",
        )

    # Si no se cumple ninguna de las 4 causales, la cuenta no se bloquea
    return False, EstadoCuenta.ACTIVO, "Cuenta operativa dentro de los plazos reglamentarios."


# ============================================================================
# 3. CICLO DE VIDA Y BAJAS (POLÍTICA DE SOFT DELETE)
# ============================================================================

def validar_factibilidad_cierre_cuenta(
    saldo_disponible: float,
    deuda_prestamos: float,
    plazos_fijos_vigentes: int = 0,
) -> Tuple[bool, str]:
    """
    Valida si un cliente puede solicitar válidamente el cierre de su cuenta.
    
    Reglas de negocio (docs/diagrama_usuarios_empresas_aml_bloqueos.md):
    1. No debe mantener deuda exigible en préstamos activos (deuda_prestamos == 0).
    2. El saldo de su cuenta transaccional debe ser $0.00 (debe transferir o retirar todo antes).
    3. No debe tener certificados de plazo fijo pendientes de vencimiento (plazos_fijos_vigentes == 0).
    
    Retorna: (autorizado: bool, motivo: str)
    """
    if deuda_prestamos > 0.0:
        return (
            False,
            f"No es posible cerrar la cuenta: registra una deuda de préstamos activa por ${deuda_prestamos:,.2f}.",
        )

    if plazos_fijos_vigentes > 0:
        return (
            False,
            f"No es posible cerrar la cuenta: registra {plazos_fijos_vigentes} plazo(s) fijo(s) vigente(s) en curso.",
        )

    if saldo_disponible > 0.0:
        return (
            False,
            f"No es posible cerrar la cuenta: debe retirar o transferir el saldo remanente (${saldo_disponible:,.2f}) previo a la baja.",
        )

    if saldo_disponible < 0.0:
        return (
            False,
            f"No es posible cerrar la cuenta: registra saldo deudor descubierto por ${abs(saldo_disponible):,.2f}.",
        )

    return True, "Cierre de cuenta autorizado. Procediendo al archivo legal por 10 años (Soft Delete)."
