"""
Esquemas Pydantic de validación de contratos de entrada/salida HTTP REST.
Normaliza payloads del frontend y backend para simuladores, auth y operaciones.
Referencia de diseño: docs/diagrama_logica_negocio_banco.md
"""

import re
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


def normalizar_categoria_laboral(valor: Optional[str]) -> str:
    """Homologa alias de categoría laboral enviados por el frontend al enum de dominio."""
    if not valor:
        return "EMPLEADO_PRIVADO"
    limpio = valor.strip().upper()
    if limpio in ("MONOTRIBUTISTA", "AUTONOMO", "AUTÓNOMO"):
        return "AUTONOMO_MONOTRIBUTO"
    return limpio


class SimularPrestamoRequest(BaseModel):
    monto_capital: float = Field(1500000.0, gt=0)
    cantidad_cuotas: int = Field(24, ge=1, le=72)
    ingreso_mensual: float = Field(3000000.0, gt=0)
    facturacion_anual: Optional[float] = None
    categoria_laboral: str = "EMPLEADO_PRIVADO"
    tipo_societario: Optional[str] = None
    score_externo: int = Field(700, ge=100, le=999)
    peor_situacion_bcra: int = Field(1, ge=1, le=6)
    antiguedad_meses: int = 12
    dni_o_cuit: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def mapear_alias_frontend(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        if "monto_capital" not in d and "monto_solicitado" in d:
            d["monto_capital"] = d["monto_solicitado"]
        if "cantidad_cuotas" not in d and "plazo_meses" in d:
            d["cantidad_cuotas"] = d["plazo_meses"]
        if "ingreso_mensual" not in d:
            if "ingreso_neto_mensual" in d and d["ingreso_neto_mensual"]:
                d["ingreso_mensual"] = d["ingreso_neto_mensual"]
            elif "facturacion_anual" in d and d["facturacion_anual"]:
                d["ingreso_mensual"] = float(d["facturacion_anual"]) / 12.0
        if "antiguedad_meses" not in d and "antiguedad_laboral_meses" in d:
            d["antiguedad_meses"] = d["antiguedad_laboral_meses"]
        d["categoria_laboral"] = normalizar_categoria_laboral(d.get("categoria_laboral"))
        return d


class SimularEmpresaRequest(BaseModel):
    monto_capital: float = Field(5000000.0, gt=0)
    cantidad_cuotas: int = Field(24, ge=1, le=72)
    facturacion_anual: float = Field(60000000.0, gt=0)
    tipo_societario: str = "SRL"
    score_externo: int = Field(700, ge=100, le=999)
    peor_situacion_bcra: int = Field(1, ge=1, le=6)

    @model_validator(mode="before")
    @classmethod
    def mapear_alias_empresa(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        if "monto_capital" not in d and "monto_solicitado" in d:
            d["monto_capital"] = d["monto_solicitado"]
        if "cantidad_cuotas" not in d and "plazo_meses" in d:
            d["cantidad_cuotas"] = d["plazo_meses"]
        return d


class SimularDepositoRequest(BaseModel):
    monto: float = Field(..., gt=0)
    plazo_dias: int = Field(30, ge=30, le=365)


class LoginRequest(BaseModel):
    identificador: str
    password: str

    @field_validator("identificador")
    @classmethod
    def validar_identificador(cls, v: str) -> str:
        limpio = v.strip()
        if not limpio:
            raise ValueError("El identificador (DNI, CUIT o Email) es obligatorio.")
        return limpio

    @field_validator("password")
    @classmethod
    def validar_password_login(cls, v: str) -> str:
        if not v:
            raise ValueError("La contraseña es obligatoria.")
        return v


class RegistroPersonaRequest(BaseModel):
    dni: str
    nombre_completo: str
    email: str
    password: str
    categoria_laboral: str = "EMPLEADO_PRIVADO"
    antiguedad_laboral_meses: int = 12
    ingreso_mensual_estimado: float = 0.0
    es_cuenta_sueldo: bool = False
    monto_sueldo_acreditado: float = 0.0
    localidad: str = "San Fernando del Valle de Catamarca"

    @field_validator("dni")
    @classmethod
    def validar_dni(cls, v: str) -> str:
        limpio = re.sub(r"\D", "", v.strip())
        if len(limpio) < 7 or len(limpio) > 11:
            raise ValueError("El DNI debe contener entre 7 y 8 dígitos numéricos (o 11 dígitos para CUIL).")
        return limpio

    @field_validator("nombre_completo")
    @classmethod
    def validar_nombre_completo(cls, v: str) -> str:
        limpio = v.strip()
        if len(limpio) < 3:
            raise ValueError("El nombre completo debe tener al menos 3 caracteres.")
        return limpio

    @field_validator("email")
    @classmethod
    def validar_email(cls, v: str) -> str:
        limpio = v.strip().lower()
        if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", limpio):
            raise ValueError("El correo electrónico no tiene un formato válido.")
        return limpio

    @field_validator("password")
    @classmethod
    def validar_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("La contraseña debe contener al menos una letra y un número.")
        return v

    @field_validator("antiguedad_laboral_meses")
    @classmethod
    def validar_antiguedad(cls, v: int) -> int:
        if v < 0:
            raise ValueError("La antigüedad laboral no puede ser negativa.")
        return v

    @field_validator("ingreso_mensual_estimado", "monto_sueldo_acreditado")
    @classmethod
    def validar_montos_positivos(cls, v: float) -> float:
        if v < 0:
            raise ValueError("El monto de ingresos o haberes no puede ser negativo.")
        return v

    @model_validator(mode="before")
    @classmethod
    def normalizar_registro_persona(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        if not d.get("ingreso_mensual_estimado") and d.get("ingreso_mensual_comprobado"):
            d["ingreso_mensual_estimado"] = d["ingreso_mensual_comprobado"]
        d["categoria_laboral"] = normalizar_categoria_laboral(d.get("categoria_laboral"))
        return d


class RegistroEmpresaRequest(BaseModel):
    cuit: str
    razon_social: str
    tipo_societario: str = "SRL"
    rubro_actividad: str = "Servicios Generales"
    email: str
    password: str
    facturacion_anual_estimada: float = 0.0
    localidad: str = "San Fernando del Valle de Catamarca"
    exencion_impositiva: bool = False

    @field_validator("cuit")
    @classmethod
    def validar_cuit(cls, v: str) -> str:
        limpio = re.sub(r"\D", "", v.strip())
        if len(limpio) != 11:
            raise ValueError("El CUIT corporativo debe contener exactamente 11 dígitos numéricos.")
        return limpio

    @field_validator("razon_social")
    @classmethod
    def validar_razon_social(cls, v: str) -> str:
        limpio = v.strip()
        if len(limpio) < 3:
            raise ValueError("La razón social debe tener al menos 3 caracteres.")
        return limpio

    @field_validator("email")
    @classmethod
    def validar_email_empresa(cls, v: str) -> str:
        limpio = v.strip().lower()
        if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", limpio):
            raise ValueError("El correo electrónico corporativo no tiene un formato válido.")
        return limpio

    @field_validator("password")
    @classmethod
    def validar_password_empresa(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("La contraseña debe contener al menos una letra y un número.")
        return v

    @field_validator("facturacion_anual_estimada")
    @classmethod
    def validar_facturacion(cls, v: float) -> float:
        if v < 0:
            raise ValueError("La facturación anual no puede ser negativa.")
        return v

    @model_validator(mode="before")
    @classmethod
    def normalizar_registro_empresa(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        if not d.get("facturacion_anual_estimada") and d.get("facturacion_anual_comprobada"):
            d["facturacion_anual_estimada"] = d["facturacion_anual_comprobada"]
        return d


class TransferenciaRequest(BaseModel):
    cbu_o_alias_destino: str
    monto: float = Field(..., gt=0)
    concepto: str = "VARIOS"


class PlazoFijoRequest(BaseModel):
    persona_id: Optional[int] = None
    monto: float = Field(..., gt=0)
    plazo_dias: int = Field(30, ge=30)


class DepositoPruebaRequest(BaseModel):
    cuenta_id: Optional[int] = None
    persona_id: Optional[int] = None
    monto: float = Field(500000.0, gt=0)
    descripcion: str = "Transferencia Inmediata Recibida — COELSA / Transferencias 3.0"


class SolicitudBajaRequest(BaseModel):
    identificador: Optional[str] = None
    motivo: str = "Solicitud voluntaria del cliente conforme Ley 24.240"
    servicio: str = "Cuenta Bancaria y Paquete de Servicios"


class SolicitudArrepentimientoRequest(BaseModel):
    identificador: Optional[str] = None
    producto_id: Optional[int] = None
    tipo_producto: str = "PRESTAMO"  # 'PRESTAMO' o 'PLAZO_FIJO'
    motivo: Optional[str] = "Derecho de revocación dentro de los 10 días hábiles (Ley 24.240 y BCRA)"
