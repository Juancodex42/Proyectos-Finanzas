"""
Módulo de Guardarraíles y Cámara de Seguridad de Venta P2P (SellGuardrails).
Implementa la protección contra pérdidas de capital ("Cero Pérdidas"):
1. Piso de Costo Real (Break-Even WAC + margen mínimo).
2. Oráculo Externo de Cordura (Fiwind Bid cross-check).
3. Frescura y vigencia de datos de mercado (< 90 segundos).
4. Profundidad del libro de órdenes (mínimo de competidores válidos).
5. Límite de exposición por tramos (Tranches).
"""
import logging
from datetime import datetime
from typing import Optional

from config.settings import (
    SELL_MIN_MARGIN_PCT,
    SELL_ORACLE_MAX_DEV_PCT,
    SELL_MAX_STALE_DATA_SECONDS,
    SELL_MAX_USDT_PER_AD,
)

logger = logging.getLogger("sell_guardrails")


class SellGuardrails:
    """Validador estricto de precios y condiciones de venta P2P."""

    @staticmethod
    def validate_break_even(
        price: float,
        wac_cost: float,
        min_margin_pct: float = SELL_MIN_MARGIN_PCT,
        min_margin_ars: float = 0.0,
    ) -> tuple[bool, str]:
        """
        Verifica que el precio propuesto cubra el costo promedio ponderado de compra
        más el margen requerido (porcentaje y/o colchón fijo en ARS configurado por el usuario).
        """
        if price <= 0:
            return False, f"Precio inválido: ${price:,.2f}"

        if wac_cost > 0:
            pct_floor = wac_cost * (1.0 + min_margin_pct)
            ars_floor = wac_cost + min_margin_ars if min_margin_ars > 0 else 0.0
            min_allowed = round(max(pct_floor, ars_floor), 2)
            if price < min_allowed:
                tag = f"colchón (${min_margin_ars:.2f} ARS)" if min_margin_ars > 0 else f"margen ({min_margin_pct*100:.1f}%)"
                return (
                    False,
                    f"Pérdida evitada: precio sugerido (${price:,.2f}) es inferior al costo WAC + {tag} (${min_allowed:,.2f})",
                )

        return True, ""

    @staticmethod
    def validate_oracle_sanity(
        price: float,
        fiwind_bid: float,
        max_dev_pct: float = SELL_ORACLE_MAX_DEV_PCT,
    ) -> tuple[bool, str]:
        """
        Compara el precio P2P contra el bid oficial de Fiwind para evitar
        seguir libros de órdenes manipulados o anomalías externas.
        """
        if fiwind_bid > 0:
            floor_limit = round(fiwind_bid * (1.0 - max_dev_pct), 2)
            if price < floor_limit:
                return (
                    False,
                    f"Anomalía de mercado: precio (${price:,.2f}) desvía >{max_dev_pct*100:.1f}% abajo de Fiwind Bid (${fiwind_bid:,.2f})",
                )

            ceiling_limit = round(fiwind_bid * 1.15, 2)
            if price > ceiling_limit:
                return (
                    False,
                    f"Anomalía de mercado: precio (${price:,.2f}) excede banda creíble de Fiwind (${ceiling_limit:,.2f})",
                )

        return True, ""

    @staticmethod
    def validate_data_freshness(
        timestamp: Optional[datetime],
        max_age_seconds: float = SELL_MAX_STALE_DATA_SECONDS,
    ) -> tuple[bool, str]:
        """
        Asegura que las decisiones se tomen sobre datos frescos de mercado (< 90s).
        """
        if not timestamp:
            return False, "Sin marca de tiempo en datos de mercado"

        age_seconds = (datetime.now() - timestamp).total_seconds()
        # Compensar desfase UTC en timestamps leídos de SQLite sin tzinfo (ej: UTC vs UTC-3)
        if -11000 <= age_seconds <= -10000:
            age_seconds += 10800  # 3 horas de diferencia UTC
        elif -15000 <= age_seconds <= -14000:
            age_seconds += 14400  # 4 horas de diferencia UTC

        if age_seconds > max_age_seconds:
            return False, f"Datos de mercado obsoletos ({age_seconds:.0f}s > {max_age_seconds:.0f}s)"
        if age_seconds < -30:
            return False, f"Inconsistencia temporal o desfase de reloj ({age_seconds:.0f}s)"

        return True, ""

    @staticmethod
    def validate_order_book_depth(
        individual_prices: list[float],
        min_sellers: int = 2,
    ) -> tuple[bool, str]:
        """
        Exige al menos min_sellers anuncios válidos para no anclarse a anomalías de 1 solo competidor.
        """
        valid_prices = [p for p in (individual_prices or []) if p > 0]
        if len(valid_prices) < min_sellers:
            return False, f"Profundidad insuficiente ({len(valid_prices)} vendedor/es < {min_sellers})"

        return True, ""

    @staticmethod
    def validate_tranche_limit(
        amount_crypto: float,
        max_allowed: float = SELL_MAX_USDT_PER_AD,
    ) -> float:
        """
        Recorta la cantidad de cripto a vender al tranche máximo permitido por anuncio.
        """
        if amount_crypto <= 0:
            return 0.0
        return round(min(amount_crypto, max_allowed), 2)

    @classmethod
    def audit_sell_price(
        cls,
        price: float,
        wac_cost: float,
        fiwind_bid: float,
        data_timestamp: Optional[datetime],
        individual_prices: list[float],
        min_margin_pct: float = SELL_MIN_MARGIN_PCT,
        max_dev_pct: float = SELL_ORACLE_MAX_DEV_PCT,
        max_age_seconds: float = SELL_MAX_STALE_DATA_SECONDS,
        min_sellers: int = 2,
        min_margin_ars: float = 0.0,
    ) -> tuple[bool, str]:
        """
        Audita una sugerencia de venta ejecutando todas las pruebas de seguridad.
        Retorna (True, 'OK') o (False, 'Causa del rechazo').
        """
        # 1. Break-Even (Piso de costo + Colchón de Profit)
        ok, reason = cls.validate_break_even(price, wac_cost, min_margin_pct, min_margin_ars=min_margin_ars)
        if not ok:
            return False, reason

        # 2. Oráculo Fiwind
        ok, reason = cls.validate_oracle_sanity(price, fiwind_bid, max_dev_pct)
        if not ok:
            return False, reason

        # 3. Frescura de datos
        ok, reason = cls.validate_data_freshness(data_timestamp, max_age_seconds)
        if not ok:
            return False, reason

        # 4. Profundidad del libro
        ok, reason = cls.validate_order_book_depth(individual_prices, min_sellers)
        if not ok:
            return False, reason

        return True, "Validación de seguridad aprobada"
