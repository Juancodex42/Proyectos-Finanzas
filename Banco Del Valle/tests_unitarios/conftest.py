"""
Fixtures Compartidas de Pytest — Banco del Valle.
Carga datos mock de clientes, empresas, buró Veraz y balances iniciales.
Referencia de diseño: docs/diagrama_logica_negocio_banco.md
"""

import sys
from pathlib import Path
import pytest

# Asegurar que el directorio raíz de 'Scoring calculator' esté en el sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.domain.models import (
    Persona,
    Empresa,
    HistorialVeraz,
    BalancePatrimonio,
    CategoriaLaboral,
    TipoSocietario,
    EstadoCuenta,
)


@pytest.fixture
def persona_juan_jose() -> Persona:
    """Cliente demo estándar con cuenta sueldo y excelente perfil crediticio."""
    return Persona(
        id=1,
        dni="35123456",
        nombre_completo="Juan José Gonzalez",
        localidad="San Fernando del Valle de Catamarca",
        categoria_laboral=CategoriaLaboral.EMPLEADO_PRIVADO,
        antiguedad_laboral_meses=24,
        ingreso_mensual_comprobado=3000000.0,
        monto_sueldo_acreditado=3000000.0,
        dia_cobro_sueldo=1,
        estado_cuenta=EstadoCuenta.ACTIVO,
    )


@pytest.fixture
def persona_empleado_publico() -> Persona:
    """Cliente del sector público con máxima estabilidad laboral."""
    return Persona(
        id=2,
        dni="27351234567",
        nombre_completo="María Elena Valle",
        localidad="San Fernando del Valle de Catamarca",
        categoria_laboral=CategoriaLaboral.EMPLEADO_PUBLICO,
        antiguedad_laboral_meses=48,
        ingreso_mensual_comprobado=2500000.0,
        estado_cuenta=EstadoCuenta.ACTIVO,
    )


@pytest.fixture
def empresa_agrovalle_sas() -> Empresa:
    """Persona jurídica tipo SAS que requiere fianza solidaria de socios."""
    return Empresa(
        id=1,
        cuit="30712345679",
        razon_social="AgroValle SAS",
        tipo_societario=TipoSocietario.SAS,
        rubro_actividad="Producción Agropecuaria y Nogalera",
        localidad="San Fernando del Valle de Catamarca",
        facturacion_anual_comprobada=120000000.0,  # $10M mensual
        requiere_fianza_socios=True,
        exencion_impositiva=False,
        estado_cuenta=EstadoCuenta.ACTIVO,
    )


@pytest.fixture
def empresa_cooperativa() -> Empresa:
    """Entidad de economía social con fomento productivo y exención de ganancias."""
    return Empresa(
        id=2,
        cuit="30654321098",
        razon_social="Cooperativa Olivícola del Valle",
        tipo_societario=TipoSocietario.COOPERATIVA,
        rubro_actividad="Elaboración de Aceite de Oliva",
        localidad="Valle Viejo, Catamarca",
        facturacion_anual_comprobada=96000000.0,  # $8M mensual
        requiere_fianza_socios=False,
        exencion_impositiva=True,
        estado_cuenta=EstadoCuenta.ACTIVO,
    )


@pytest.fixture
def veraz_limpio() -> HistorialVeraz:
    """Buró de crédito favorable en Situación 1 (Normal)."""
    return HistorialVeraz(
        score_externo=720,
        peor_situacion_bcra=1,
        monto_deuda_externa_total=150000.0,
        cantidad_bancos_acreedores=1,
        cheques_rechazados_monto=0.0,
    )


@pytest.fixture
def veraz_moroso() -> HistorialVeraz:
    """Buró de crédito descalificado en Situación 3 (Deudor con problemas)."""
    return HistorialVeraz(
        score_externo=480,
        peor_situacion_bcra=3,
        monto_deuda_externa_total=2500000.0,
        cantidad_bancos_acreedores=4,
        cheques_rechazados_monto=450000.0,
    )


@pytest.fixture
def balance_bancario_inicial() -> BalancePatrimonio:
    """Snapshot inicial representativo de la solvencia de la entidad."""
    return BalancePatrimonio(
        id=1,
        fecha_corte="2026-10-25",
        total_depositos_plazo_fijo=10000000.0,  # 10M en PF
        total_depositos_flexibles=10000000.0,   # 10M en cajas flexibles
        encaje_obligatorio_bcra=4200000.0,       # (10M * 0.30) + (10M * 0.12)
        capital_propio_patrimonio=50000000.0,   # 50M patrimonio
        total_prestado_activo=15000000.0,       # 15M en la calle
        cashflow_seguro_prestable=49800000.0,
    )
