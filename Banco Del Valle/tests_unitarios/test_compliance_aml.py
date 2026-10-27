"""
Pruebas Unitarias: Cumplimiento Normativo (AML/KYC) y Soft Delete.
Valida Enfoque Basado en Riesgo (EBR), umbral de 40 SMVM, RFI y bajas seguras.
Referencia de diseño: docs/diagrama_usuarios_empresas_aml_bloqueos.md
"""

from src.domain.compliance_aml import (
    calcular_umbral_smvm_pesos,
    evaluar_transaccion_aml,
    evaluar_protocolo_bloqueo,
    validar_factibilidad_cierre_cuenta,
)
from src.domain.models import EstadoCuenta


def test_calcular_umbral_smvm_pesos():
    """40 Salarios Mínimos a $300.000 fijan un umbral de $12.000.000 ARS."""
    umbral = calcular_umbral_smvm_pesos(valor_smvm=300000.0, multiplicador=40.0)
    assert umbral == 12000000.0


def test_operacion_habitual_sin_alerta():
    """Transferencia equivalente al 50% del sueldo mensual no dispara banderas rojas."""
    resultado = evaluar_transaccion_aml(
        monto_operacion=1500000.0,
        perfil_mensual_estimado=3000000.0,
        valor_smvm=300000.0,
    )
    assert resultado.operacion_admitida is True
    assert resultado.alerta_aml is False
    assert resultado.requiere_rfi is False


def test_disparo_alerta_umbral_smvm_garantista():
    """
    Operación de $15.000.000 (superior al umbral de 40 SMVM = $12M):
    1. Dispara alerta de monitoreo interno (alerta_aml = True).
    2. Emite requerimiento formal de origen de fondos (RFI = True) con 30 días.
    3. GARANTISTA: La cuenta NO se congela intempestivamente (operacion_admitida = True).
    """
    resultado = evaluar_transaccion_aml(
        monto_operacion=15000000.0,
        perfil_mensual_estimado=3000000.0,
        valor_smvm=300000.0,
    )
    assert resultado.operacion_admitida is True
    assert resultado.alerta_aml is True
    assert resultado.supera_umbral_smvm is True
    assert resultado.requiere_rfi is True
    assert resultado.plazo_descargo_dias == 30
    assert "continúa 100% OPERATIVA" in resultado.observaciones


def test_protocolo_bloqueo_dentro_del_plazo():
    """Durante los 30 días de plazo del RFI, la cuenta no sufre inmovilización cautelar."""
    bloquear, estado, _ = evaluar_protocolo_bloqueo(dias_sin_descargo=15)
    assert bloquear is False
    assert estado == EstadoCuenta.ACTIVO


def test_protocolo_bloqueo_vencimiento_plazo_legal():
    """Vencido el plazo garantista (> 30 días) sin descargo, procede la suspensión."""
    bloquear, estado, motivo = evaluar_protocolo_bloqueo(dias_sin_descargo=35)
    assert bloquear is True
    assert estado == EstadoCuenta.SUSPENDIDO_AML
    assert "vencimiento" in motivo.lower()


def test_protocolo_bloqueo_orden_judicial():
    """Notificación de Oficio Judicial ordena inmovilización cautelar inmediata."""
    bloquear, estado, _ = evaluar_protocolo_bloqueo(orden_judicial=True)
    assert bloquear is True
    assert estado == EstadoCuenta.SUSPENDIDO_AML


def test_protocolo_bloqueo_listas_repet():
    """Coincidencia en listas de financiamiento del terrorismo (RePET) suspende la cuenta."""
    bloquear, estado, _ = evaluar_protocolo_bloqueo(listado_repet=True)
    assert bloquear is True
    assert estado == EstadoCuenta.SUSPENDIDO_AML


def test_protocolo_bloqueo_docs_apocrifas():
    """Presentación de comprobantes falsos o apócrifos suspende la cuenta."""
    bloquear, estado, _ = evaluar_protocolo_bloqueo(docs_apocrifas=True)
    assert bloquear is True
    assert estado == EstadoCuenta.SUSPENDIDO_AML


def test_soft_delete_con_deuda_bloqueado():
    """Prohibido dar de baja cuentas con deudas activas de préstamos."""
    autorizado, motivo = validar_factibilidad_cierre_cuenta(
        saldo_disponible=0.0,
        deuda_prestamos=350000.0,
        plazos_fijos_vigentes=0,
    )
    assert autorizado is False
    assert "deuda de préstamos" in motivo


def test_soft_delete_con_saldo_remanente_bloqueado():
    """El cliente debe retirar su dinero antes de solicitar el cierre definitivo."""
    autorizado, motivo = validar_factibilidad_cierre_cuenta(
        saldo_disponible=50000.0,
        deuda_prestamos=0.0,
        plazos_fijos_vigentes=0,
    )
    assert autorizado is False
    assert "retirar o transferir el saldo" in motivo


def test_soft_delete_con_plazo_fijo_activo():
    """No se permite el cierre con certificados de depósito a plazo fijo en curso."""
    autorizado, motivo = validar_factibilidad_cierre_cuenta(
        saldo_disponible=0.0,
        deuda_prestamos=0.0,
        plazos_fijos_vigentes=1,
    )
    assert autorizado is False
    assert "plazo(s) fijo(s)" in motivo


def test_soft_delete_limpio_autorizado():
    """Cumplidas todas las condiciones de liquidación, se autoriza el archivo legal por 10 años."""
    autorizado, motivo = validar_factibilidad_cierre_cuenta(
        saldo_disponible=0.0,
        deuda_prestamos=0.0,
        plazos_fijos_vigentes=0,
    )
    assert autorizado is True
    assert "Cierre de cuenta autorizado" in motivo
