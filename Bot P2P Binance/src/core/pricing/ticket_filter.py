"""
Módulo de filtros por tamaño de ticket y validación mayorista.

Proporciona funciones auxiliares para descartar micro-anuncios en la competencia
y validar capacidades operativas mínimas requeridas según el grupo y capital.
"""
import math
from typing import Optional
from data.models import ExchangeRate


def is_ticket_qualified(
    rate: ExchangeRate,
    target_min: float,
    min_credible_price: float = 0.0,
) -> bool:
    """
    Verifica si una cotización de la competencia cumple con el ticket mínimo
    mayorista y se encuentra dentro de la banda de precio creíble de Binance.

    Args:
        rate: Cotización del competidor.
        target_min: Monto mínimo en ARS que debe cubrir el máximo del competidor.
        min_credible_price: Piso mínimo legal creíble en ARS.

    Returns:
        True si califica como competidor mayorista válido, False en caso contrario.
    """
    return (
        rate.max_single_trans_amount >= target_min
        and rate.price_ars >= min_credible_price
    )


def filter_qualified_competitors(
    rates: list[ExchangeRate],
    target_min: float,
    min_credible_price: float = 0.0,
) -> list[ExchangeRate]:
    """
    Filtra una lista de cotizaciones quedándose únicamente con mayoristas.

    Args:
        rates: Lista de cotizaciones de la competencia.
        target_min: Monto mínimo en ARS para clasificar como mayorista.
        min_credible_price: Piso de precio legal creíble.

    Returns:
        Lista de competidores calificados.
    """
    return [
        r for r in rates
        if is_ticket_qualified(r, target_min=target_min, min_credible_price=min_credible_price)
    ]


def filter_viable_competitors(
    rates: list[ExchangeRate],
    target_min: float,
    min_credible_price: float,
    max_allowed_price: float,
) -> list[ExchangeRate]:
    """
    Filtra competidores mayoristas que operen estrictamente por debajo del techo de margen.

    Args:
        rates: Lista de cotizaciones de competidores.
        target_min: Monto mínimo en ARS del ticket.
        min_credible_price: Piso creíble en ARS.
        max_allowed_price: Techo absoluto de precio permitido.

    Returns:
        Lista de competidores viables por debajo del techo.
    """
    return [
        r for r in rates
        if r.max_single_trans_amount >= target_min
        and min_credible_price <= r.price_ars < max_allowed_price
    ]


def calculate_capital_capacity_ars(crypto_amount: float, price: float) -> float:
    """
    Calcula el volumen nominal en ARS truncado al entero inferior (math.floor).

    Args:
        crypto_amount: Cantidad en criptoactivo.
        price: Precio unitario en ARS.

    Returns:
        Capacidad en ARS.
    """
    if crypto_amount <= 0 or price <= 0:
        return 0.0
    return float(math.floor(crypto_amount * price))


def is_stock_capacity_sufficient(
    surplus_crypto: float,
    price: float,
    min_trans_amount: float,
) -> bool:
    """
    Verifica si el remanente en cripto cubre el límite mínimo de transacción del anuncio.
    Aplica una tolerancia de $1.0 ARS para evitar errores de redondeo en Binance.

    Args:
        surplus_crypto: Saldo de cripto disponible en el anuncio.
        price: Precio de venta/compra en ARS.
        min_trans_amount: Límite mínimo fijado en el anuncio.

    Returns:
        True si cubre la transacción mínima de forma segura.
    """
    if surplus_crypto <= 0 or price <= 0 or min_trans_amount <= 0:
        return False
    surplus_capacity_ars = surplus_crypto * price
    return (surplus_capacity_ars + 1.0) >= min_trans_amount
