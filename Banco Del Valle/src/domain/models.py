"""
Modelos de datos estandarizados, entidades tipadas y DTOs transversales del banco.
Define dataclasses y enums inmutables para scoring, tesorería, compliance y simulación.
Referencia de diseño: docs/diagrama_logica_negocio_banco.md
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional, List


# ============================================================================
# 1. ENUMS (Valores Fijos y Opciones Tipadas)
# ============================================================================

class RolUsuario(str, Enum):
    """Roles de acceso al sistema para autenticación y RBAC."""
    CLIENTE = "CLIENTE"
    EMPLEADO = "EMPLEADO"
    GERENTE = "GERENTE"


class CategoriaLaboral(str, Enum):
    """Segmentación laboral de individuos para ponderación de scoring."""
    EMPLEADO_PUBLICO = "EMPLEADO_PUBLICO"
    EMPLEADO_PRIVADO = "EMPLEADO_PRIVADO"
    JUBILADO = "JUBILADO"
    AUTONOMO_MONOTRIBUTO = "AUTONOMO_MONOTRIBUTO"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str) and value.strip().upper() in ("MONOTRIBUTISTA", "AUTONOMO", "AUTÓNOMO"):
            return cls.AUTONOMO_MONOTRIBUTO
        return None


class TipoSocietario(str, Enum):
    """Tipos societarios reconocidos para personas jurídicas / PyMEs."""
    SA = "SA"
    SRL = "SRL"
    SAS = "SAS"
    SAU = "SAU"
    COOPERATIVA = "COOPERATIVA"
    MUTUAL = "MUTUAL"
    ONG_FUNDACION = "ONG_FUNDACION"
    FIDEICOMISO = "FIDEICOMISO"


class EstadoCuenta(str, Enum):
    """Ciclo de vida y estados normativos AML/UIF para personas y empresas."""
    ACTIVO = "ACTIVO"
    ACTIVA = "ACTIVA"
    PENDIENTE_DOCS = "PENDIENTE_DOCS"
    SUSPENDIDO_AML = "SUSPENDIDO_AML"
    BAJA_SOLICITADA = "BAJA_SOLICITADA"
    CERRADO = "CERRADO"
    CERRADA = "CERRADA"


class TipoMovimiento(str, Enum):
    """Tipos de transacciones registradas en el libro contable de cuentas."""
    DEPOSITO = "DEPOSITO"
    EXTRACCION = "EXTRACCION"
    TRANSFERENCIA_IN = "TRANSFERENCIA_IN"
    TRANSFERENCIA_OUT = "TRANSFERENCIA_OUT"
    RENDIMIENTO_FLEXIBLE_DIARIO = "RENDIMIENTO_FLEXIBLE_DIARIO"
    COBRO_CUOTA_PRESTAMO = "COBRO_CUOTA_PRESTAMO"
    LIQUIDACION_PLAZO_FIJO = "LIQUIDACION_PLAZO_FIJO"
    ACREDITACION_SUELDO = "ACREDITACION_SUELDO"


class EstadoPrestamo(str, Enum):
    """Estados del ciclo de amortización de un préstamo."""
    ACTIVO = "ACTIVO"
    AL_DIA = "AL_DIA"
    EN_MORA = "EN_MORA"
    CANCELADO = "CANCELADO"
    RECHAZADO = "RECHAZADO"


class EstadoPlazoFijo(str, Enum):
    """Estados de un depósito a plazo tradicional."""
    ACTIVO = "ACTIVO"
    VENCIDO = "VENCIDO"
    LIQUIDADO = "LIQUIDADO"
    CANCELADO_ANTICIPADO = "CANCELADO_ANTICIPADO"


class FaseCiclo(str, Enum):
    """Fases del ciclo macroeconómico según actividad (EMAE / PBI)."""
    EXPANSION = "EXPANSION"
    ESTABLE = "ESTABLE"
    RECESION_LEVE = "RECESION_LEVE"
    RECESION_SEVERA = "RECESION_SEVERA"


class EscenarioMacro(str, Enum):
    """Escenarios proyectivos de ganancias y patrimonio bancario."""
    OPTIMISTA = "OPTIMISTA"
    BASE = "BASE"
    PESIMISTA = "PESIMISTA"


# ============================================================================
# 2. ENTIDADES PRINCIPALES (Persistentes en SQLite)
# ============================================================================

@dataclass
class Persona:
    """Titular particular / Persona humana (Individuos y familias)."""
    id: Optional[int] = None
    dni: str = ""
    nombre_completo: str = ""
    localidad: str = "San Fernando del Valle de Catamarca"
    categoria_laboral: CategoriaLaboral = CategoriaLaboral.EMPLEADO_PRIVADO
    antiguedad_laboral_meses: int = 12
    ingreso_mensual_comprobado: float = 0.0
    monto_sueldo_acreditado: float = 3000000.0
    dia_cobro_sueldo: int = 1
    estado_cuenta: EstadoCuenta = EstadoCuenta.ACTIVO
    fecha_alta: str = field(default_factory=lambda: date.today().isoformat())


@dataclass
class Empresa:
    """Persona jurídica (PyMEs, corporaciones y entidades intermedias)."""
    id: Optional[int] = None
    cuit: str = ""
    razon_social: str = ""
    tipo_societario: TipoSocietario = TipoSocietario.SRL
    rubro_actividad: str = ""
    localidad: str = "San Fernando del Valle de Catamarca"
    facturacion_anual_comprobada: float = 0.0
    requiere_fianza_socios: bool = False
    exencion_impositiva: bool = False
    estado_cuenta: EstadoCuenta = EstadoCuenta.ACTIVO
    fecha_alta: str = field(default_factory=lambda: date.today().isoformat())


@dataclass
class CuentaTransaccional:
    """Caja de Ahorro / Cuenta Corriente remunerada de liquidez inmediata."""
    id: Optional[int] = None
    persona_id: Optional[int] = None
    empresa_id: Optional[int] = None
    cbu: str = ""
    alias: str = ""
    saldo_actual: float = 0.0
    tna_rendimiento_diario: float = 0.285  # 28.5% TNA
    es_cuenta_sueldo: bool = False
    permite_extraccion_inmediata: bool = True
    estado: EstadoCuenta = EstadoCuenta.ACTIVO


@dataclass
class MovimientoCuenta:
    """Registro inmutable de movimientos en cuenta para libro contable y auditoría."""
    id: Optional[int] = None
    cuenta_id: int = 0
    tipo_movimiento: TipoMovimiento = TipoMovimiento.DEPOSITO
    monto: float = 0.0
    saldo_posterior: float = 0.0
    fecha_hora: str = field(default_factory=lambda: datetime.now().isoformat())
    descripcion: str = ""
    alerta_aml: int = 0


@dataclass
class HistorialVeraz:
    """Snapshot de consulta a buró crediticio externo (Veraz / BCRA)."""
    id: Optional[int] = None
    persona_id: Optional[int] = None
    empresa_id: Optional[int] = None
    fecha_consulta: str = field(default_factory=lambda: date.today().isoformat())
    score_externo: int = 650
    peor_situacion_bcra: int = 1  # 1: Normal, hasta 6: Irrecuperable
    monto_deuda_externa_total: float = 0.0
    cantidad_bancos_acreedores: int = 1
    cheques_rechazados_monto: float = 0.0


@dataclass
class Prestamo:
    """Contrato de financiamiento amortizable bajo Sistema Francés."""
    id: Optional[int] = None
    persona_id: Optional[int] = None
    empresa_id: Optional[int] = None
    tipo_credito: str = "PERSONAL"
    monto_capital: float = 0.0
    tasa_nominal_anual: float = 0.60  # 60% TNA
    cantidad_cuotas: int = 12
    fecha_otorgamiento: str = field(default_factory=lambda: date.today().isoformat())
    estado: EstadoPrestamo = EstadoPrestamo.ACTIVO


@dataclass
class Cuota:
    """Detalle de amortización individual cuota por cuota."""
    id: Optional[int] = None
    prestamo_id: int = 0
    numero_cuota: int = 1
    monto_cuota: float = 0.0
    fecha_vencimiento: str = ""
    fecha_pago: Optional[str] = None
    dias_mora: int = 0
    intereses_punitorios: float = 0.0


@dataclass
class PlazoFijo:
    """Depósito a plazo fijo tradicional con devengamiento a término."""
    id: Optional[int] = None
    persona_id: Optional[int] = None
    empresa_id: Optional[int] = None
    monto_depositado: float = 0.0
    tasa_nominal_anual: float = 0.38  # 38% TNA base
    fecha_inicio: str = field(default_factory=lambda: date.today().isoformat())
    fecha_vencimiento: str = ""
    intereses_a_generar: float = 0.0
    estado: EstadoPlazoFijo = EstadoPlazoFijo.ACTIVO


@dataclass
class BalancePatrimonio:
    """Instantánea (Snapshot) diario de solvencia, liquidez y encajes bancarios."""
    id: Optional[int] = None
    fecha_corte: str = field(default_factory=lambda: date.today().isoformat())
    total_depositos_plazo_fijo: float = 0.0
    total_depositos_flexibles: float = 0.0
    encaje_obligatorio_bcra: float = 0.0
    capital_propio_patrimonio: float = 50000000.0
    total_prestado_activo: float = 0.0
    cashflow_seguro_prestable: float = 0.0


@dataclass
class ProyeccionInflacion:
    """Relevamiento macroeconómico de inflación esperada (REM y consultoras)."""
    id: Optional[int] = None
    fecha_relevamiento: str = field(default_factory=lambda: date.today().isoformat())
    inflacion_proyectada_12m: float = 0.45  # 45% anual
    fuente: str = "REM_BCRA"
    tasa_referencia_politica_monetaria: float = 0.40


@dataclass
class ProyeccionActividad:
    """Medición de actividad económica y ciclo crediticio (EMAE / PBI)."""
    id: Optional[int] = None
    fecha_relevamiento: str = field(default_factory=lambda: date.today().isoformat())
    variacion_pbi_proyectada_anual: float = 0.01  # +1%
    emae_ultimo_interanual: float = 0.01
    fase_ciclo: FaseCiclo = FaseCiclo.ESTABLE
    factor_macro_riesgo: float = 1.0


@dataclass
class UsuarioCredencial:
    """Credenciales de acceso con hash Bcrypt y control de acceso (RBAC)."""
    id: Optional[int] = None
    persona_id: Optional[int] = None
    empresa_id: Optional[int] = None
    identificador: str = ""
    email: str = ""
    password_hash: str = ""
    rol: RolUsuario = RolUsuario.CLIENTE
    intentos_fallidos: int = 0
    bloqueado_hasta: Optional[str] = None
    ultimo_login: Optional[str] = None
    fecha_creacion: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AuditoriaAcceso:
    """Registro de accesos e intentos de inicio de sesión."""
    id: Optional[int] = None
    usuario_id: Optional[int] = None
    fecha_hora: str = field(default_factory=lambda: datetime.now().isoformat())
    direccion_ip: str = "127.0.0.1"
    exitoso: int = 1
    motivo_falla: Optional[str] = None


# ============================================================================
# 3. RESULTADOS DE CÁLCULO Y DTOs (Objetos de Memoria)
# ============================================================================

@dataclass
class ResultadoScoring:
    """Dictamen final emitido por el motor de calificación de riesgo crediticio."""
    aprobado: bool
    score_obtenido: int
    tasa_anual_asignada: float
    cuota_mensual: float
    ratio_cuota_ingreso: float
    requiere_fianza: bool = False
    motivo_decision: str = ""


@dataclass
class CuotaDetalleFrances:
    """Detalle de una cuota en la tabla de desarrollo del Sistema Francés."""
    numero_cuota: int
    monto_cuota: float
    capital_amortizado: float
    interes_cuota: float
    saldo_capital_restante: float


@dataclass
class PlanAmortizacion:
    """Cronograma completo generado para un préstamo."""
    monto_capital: float
    tna: float
    cantidad_cuotas: int
    cuota_constante: float
    total_intereses: float
    cronograma: List[CuotaDetalleFrances] = field(default_factory=list)


@dataclass
class PosicionLiquidez:
    """Diagnóstico emitido por Tesorería para autorizar o pausar un desembolso."""
    cumple_encaje_bcra: bool
    encaje_total_exigido: float
    cashflow_seguro_disponible: float
    superavit_deficit_encaje: float
    desembolso_autorizado: bool
    mensaje_alerta: str = ""


@dataclass
class ResultadoComplianceAML:
    """Evaluación de una transacción bajo el Enfoque Basado en Riesgo (EBR)."""
    operacion_admitida: bool
    alerta_aml: bool
    supera_umbral_smvm: bool
    monto_operado: float
    umbral_referencia: float
    requiere_rfi: bool = False
    plazo_descargo_dias: int = 30
    observaciones: str = ""


@dataclass
class ResultadoDailyTick:
    """Resumen de eventos ejecutados durante el cierre diario (1s = 1d)."""
    fecha_simulada: str
    rendimientos_flexibles_acreditados: float = 0.0
    cuotas_cobradas: int = 0
    cuotas_en_mora: int = 0
    plazos_fijos_liquidados: int = 0
    sueldos_acreditados: int = 0
    balance_snapshot_id: Optional[int] = None


@dataclass
class RegistroPersonaDTO:
    """Datos recibidos del frontend para dar de alta una Persona Humana."""
    dni: str
    nombre_completo: str
    email: str
    password: str
    categoria_laboral: CategoriaLaboral
    antiguedad_laboral_meses: int
    ingreso_mensual_estimado: float
    localidad: str = "San Fernando del Valle de Catamarca"
    es_cuenta_sueldo: bool = False
    monto_sueldo_acreditado: float = 0.0


@dataclass
class RegistroEmpresaDTO:
    """Datos recibidos del frontend para dar de alta una Persona Jurídica / PyME."""
    cuit: str
    razon_social: str
    tipo_societario: TipoSocietario
    rubro_actividad: str
    email: str
    password: str
    facturacion_anual_estimada: float
    localidad: str = "San Fernando del Valle de Catamarca"
    exencion_impositiva: bool = False


@dataclass
class RespuestaRegistroDTO:
    """Respuesta emitida tras el alta exitosa de cuenta y coordenadas bancarias."""
    exito: bool
    mensaje: str
    usuario_id: int
    identificador: str
    email: str
    rol: RolUsuario
    cbu_asignado: str
    alias_asignado: str
    token_acceso: str
