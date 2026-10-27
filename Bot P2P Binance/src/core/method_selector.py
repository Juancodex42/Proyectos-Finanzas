"""
Selección y agrupamiento dinámico de métodos de pago.
Rankea métodos por score de oportunidad y los agrupa en paquetes de 5
minimizando el sobrepago por diferencia de precio competidor.
"""
import logging
import asyncio
from typing import Optional

from core.network.binance_api import BinanceClient
from data.database import Database
from data.models import AdInfo, PaymentMethodScore
from config.settings import (
    FIAT, MAX_TOTAL_METHODS, MAX_METHODS_PER_AD,
    MAX_ADS_PER_ASSET, SEARCH_ROWS, COMPETE_ONLY_MERCHANTS,
)

logger = logging.getLogger(__name__)


class MethodSelector:
    """Selecciona y agrupa los mejores métodos de pago."""

    def __init__(self, client: BinanceClient, db: Database):
        self.client = client
        self.db = db

    async def get_available_methods(self) -> list[dict]:
        """
        Obtiene todos los métodos de pago del usuario.
        Retorna lista de {"identifier": "BANK", "payId": 123, ...}
        """
        try:
            result = await self.client.get_my_payment_methods()
            data = result.get("data", [])
            logger.info("Métodos de pago del usuario: %d encontrados", len(data))
            return data
        except Exception as e:
            logger.error("Error obteniendo métodos de pago: %s", e)
            return []

    async def score_method(
        self,
        identifier: str,
        my_adv_nos: set[str],
        volume_ref: float,
    ) -> PaymentMethodScore:
        """
        Calcula el score de oportunidad de un método de pago.

        Score = (sellers_count × spread) / max(buyers_count, 1)

        sellers_count = cuántos venden USDT con este método (potenciales clientes)
        buyers_count = cuántos compran con este método (competidores)
        spread = avg_sell_usdt - best_buyer_price (margen disponible)
        """
        score = PaymentMethodScore(identifier=identifier)

        try:
            publisher_type = "merchant" if COMPETE_ONLY_MERCHANTS else None
            # 1. Contar vendedores de USDT (merchants vendiendo, taker tradeType="BUY")
            sell_result = await self.client.search_ads(
                asset="USDT", fiat=FIAT, trade_type="BUY",
                pay_types=[identifier], trans_amount=volume_ref, rows=SEARCH_ROWS,
                publisher_type=publisher_type,
            )
            sell_ads = [AdInfo.from_search_response(item)
                        for item in sell_result.get("data", [])]
            score.sellers_count = len(sell_ads)

            await asyncio.sleep(0.2)

            # 2. Contar compradores competidores (merchants comprando, taker tradeType="SELL")
            buy_result = await self.client.search_ads(
                asset="USDT", fiat=FIAT, trade_type="SELL",
                pay_types=[identifier], rows=SEARCH_ROWS,
                publisher_type=publisher_type,
            )
            buy_ads = [AdInfo.from_search_response(item)
                       for item in buy_result.get("data", [])]
            # Filtrar mis propios anuncios
            buy_ads = [a for a in buy_ads if a.adv_no not in my_adv_nos]
            score.buyers_count = len(buy_ads)

            # 3. Calcular spread (precio venta USDT - precio compra competidor)
            if sell_ads and buy_ads:
                avg_sell = sum(a.price for a in sell_ads[:10]) / min(len(sell_ads), 10)
                best_buy = max(a.price for a in buy_ads)
                score.spread = avg_sell - best_buy
            elif sell_ads:
                # Sin competencia de compra → oportunidad
                avg_sell = sum(a.price for a in sell_ads[:10]) / min(len(sell_ads), 10)
                score.spread = avg_sell * 0.01  # Estimado conservador

            # Score final
            score.score = (
                (score.sellers_count * max(score.spread, 0))
                / max(score.buyers_count, 1)
            )

        except Exception as e:
            logger.error("Error scoring método %s: %s", identifier, e)

        return score

    async def select_and_group(
        self,
        my_adv_nos: set[str],
        volume_ref: float,
        reference_asset: str = "USDT",
    ) -> dict[int, list[str]]:
        """
        Selecciona los mejores métodos y los agrupa en 3 paquetes.

        Returns:
            {1: ["BANK", "MP", ...], 2: [...], 3: [...]}
        """
        # 1. Obtener mis métodos disponibles
        my_methods = await self.get_available_methods()
        if not my_methods:
            logger.error("No se encontraron métodos de pago del usuario")
            return {}

        identifiers = []
        pay_id_map = {}
        for m in my_methods:
            ident = (
                m.get("tradeMethodIdentifier")
                or m.get("identifier")
                or m.get("payType")
                or (m.get("tradeMethod", {}).get("identifier") if isinstance(m.get("tradeMethod"), dict) else "")
            )
            if ident and ident not in identifiers:
                identifiers.append(ident)
                pay_id_map[ident] = m.get("id", m.get("payId", 0))

        logger.info("Scoring %d métodos de pago...", len(identifiers))

        # 2. Calcular score de cada método
        scores: list[PaymentMethodScore] = []
        for ident in identifiers:
            s = await self.score_method(ident, my_adv_nos, volume_ref)
            s.pay_id = pay_id_map.get(ident, 0)
            scores.append(s)
            await asyncio.sleep(0.3)

        # 3. Ordenar por score y seleccionar top N
        scores.sort(key=lambda x: x.score, reverse=True)
        selected = scores[:MAX_TOTAL_METHODS]
        for s in selected:
            s.selected = True

        logger.info(
            "Top %d métodos seleccionados: %s",
            len(selected),
            [(s.identifier, f"score={s.score:.1f}") for s in selected],
        )

        # 4. Agrupar por precio competidor similar
        groups = await self._group_by_competitor_price(
            selected, my_adv_nos, reference_asset
        )

        # 5. Guardar en DB
        self.db.save_method_scores(scores)

        return groups

    async def _group_by_competitor_price(
        self,
        selected_methods: list[PaymentMethodScore],
        my_adv_nos: set[str],
        reference_asset: str,
    ) -> dict[int, list[str]]:
        """
        Agrupa métodos según el precio del mejor competidor de compra.
        Métodos con precios similares van en el mismo grupo.
        """
        # Obtener precio del mejor competidor por método
        method_prices: dict[str, float] = {}
        for s in selected_methods:
            try:
                result = await self.client.search_ads(
                    asset=reference_asset, fiat=FIAT, trade_type="SELL",
                    pay_types=[s.identifier], rows=5,
                )
                ads = [AdInfo.from_search_response(item)
                       for item in result.get("data", [])]
                ads = [a for a in ads if a.adv_no not in my_adv_nos]

                if ads:
                    method_prices[s.identifier] = max(a.price for a in ads)
                else:
                    method_prices[s.identifier] = 0.0

            except Exception as e:
                logger.error("Error obteniendo precio competidor para %s: %s",
                             s.identifier, e)
                method_prices[s.identifier] = 0.0

            await asyncio.sleep(0.2)

        # Ordenar por precio competidor ascendente
        sorted_methods = sorted(
            selected_methods,
            key=lambda s: method_prices.get(s.identifier, 0),
        )

        # Distribuir en grupos de MAX_METHODS_PER_AD
        groups: dict[int, list[str]] = {}
        for i, s in enumerate(sorted_methods):
            group_num = (i // MAX_METHODS_PER_AD) + 1
            if group_num > MAX_ADS_PER_ASSET:
                break
            if group_num not in groups:
                groups[group_num] = []
            groups[group_num].append(s.identifier)
            s.assigned_group = group_num

        for g, methods in groups.items():
            prices = [method_prices.get(m, 0) for m in methods]
            spread = max(prices) - min(prices) if prices else 0
            logger.info(
                "Grupo %d: %s (spread interno: $%.0f)",
                g, methods, spread,
            )

        return groups

    async def regroup_if_needed(
        self,
        current_groups: dict[int, list[str]],
        my_adv_nos: set[str],
        reference_asset: str = "USDT",
        max_spread_threshold: float = 500_000,
    ) -> Optional[dict[int, list[str]]]:
        """
        Evalúa si conviene re-agrupar los métodos.
        Retorna nuevos grupos si el spread interno supera el umbral, None si no.
        """
        # Obtener precio competidor actual por método
        method_prices: dict[str, float] = {}
        all_methods = []
        for methods in current_groups.values():
            all_methods.extend(methods)

        for method in all_methods:
            try:
                result = await self.client.search_ads(
                    asset=reference_asset, fiat=FIAT, trade_type="SELL",
                    pay_types=[method], rows=5,
                )
                ads = [AdInfo.from_search_response(item)
                       for item in result.get("data", [])]
                ads = [a for a in ads if a.adv_no not in my_adv_nos]
                if ads:
                    method_prices[method] = max(a.price for a in ads)
            except Exception:
                pass
            await asyncio.sleep(0.2)

        # Verificar spread interno de cada grupo
        needs_regroup = False
        for group_num, methods in current_groups.items():
            prices = [method_prices.get(m, 0) for m in methods if method_prices.get(m, 0) > 0]
            if prices:
                spread = max(prices) - min(prices)
                if spread > max_spread_threshold:
                    logger.info(
                        "Grupo %d: spread $%.0f supera umbral $%.0f → re-agrupando",
                        group_num, spread, max_spread_threshold,
                    )
                    needs_regroup = True

        if not needs_regroup:
            return None

        # Re-ordenar y re-agrupar
        sorted_methods = sorted(all_methods, key=lambda m: method_prices.get(m, 0))
        new_groups: dict[int, list[str]] = {}
        for i, method in enumerate(sorted_methods):
            group_num = (i // MAX_METHODS_PER_AD) + 1
            if group_num > MAX_ADS_PER_ASSET:
                break
            if group_num not in new_groups:
                new_groups[group_num] = []
            new_groups[group_num].append(method)

        return new_groups
