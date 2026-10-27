"""
Scanner de mercado P2P.
Escanea competencia de compra, benchmark de USDT venta,
y calcula tipos de cambio implícitos.
"""
import json
import logging
import asyncio
import time
from datetime import datetime
from typing import Optional

from core.network.binance_api import BinanceClient
from core.spot_client import SpotClient
from data.database import Database
from data.models import AdInfo, ExchangeRate, Benchmark
from config.settings import (
    FIAT, TOP_N_BENCHMARK, SEARCH_ROWS, STABLECOINS,
    COMPETITOR_ANOMALY_GAP_PCT, SCANNER_CONCURRENCY,
    MIN_COMPETITOR_COMPLETION_RATE, MIN_COMPETITOR_ORDERS,
    COMPETE_ONLY_MERCHANTS,
)

logger = logging.getLogger(__name__)


class MarketScanner:
    """Escanea el mercado P2P y calcula métricas."""

    def __init__(
        self,
        client: BinanceClient,
        spot_client: SpotClient,
        db: Database,
        save_raw_snapshots: bool = False,
    ):
        self.client = client
        self.spot = spot_client
        self.db = db
        self.save_raw_snapshots = save_raw_snapshots
        self._my_adv_nos: set[str] = set()
        self._last_spot_prices: dict[str, float] = {}
        self._last_valid_competitors: dict[tuple[str, str], tuple[float, list[ExchangeRate]]] = {}
        self._anomaly_log_ts: dict[tuple[str, str, int], float] = {}

    def set_my_adv_nos(self, adv_nos: set[str]):
        """Setea los advNo propios para filtrarlos de las búsquedas."""
        self._my_adv_nos = adv_nos
        logger.info("Filtrando %d anuncios propios de búsquedas", len(adv_nos))

    async def scan_competitors(
        self,
        asset: str,
        payment_method: str,
        spot_prices: dict[str, float],
    ) -> list[ExchangeRate]:
        """
        Escanea compradores competidores para un activo y método de pago.
        Retorna ranking de TC implícito (filtrado de anuncios propios).
        """
        try:
            # En Binance SAPI /c2c/ads/search: tradeType="SELL" busca anuncios donde
            # el taker VENDE crypto, es decir, donde los merchants COMPRAN (competidores).
            publisher_type = "merchant" if COMPETE_ONLY_MERCHANTS else None
            result = await self.client.search_ads(
                asset=asset,
                fiat=FIAT,
                trade_type="SELL",
                pay_types=[payment_method],
                rows=SEARCH_ROWS,
                publisher_type=publisher_type,
            )
        except Exception as e:
            logger.error("Error escaneando competencia %s/%s: %s", asset, payment_method, e)
            cached = self._last_valid_competitors.get((asset, payment_method))
            if cached and (time.time() - cached[0]) <= 90.0:
                return list(cached[1])
            return []

        if not isinstance(result, dict) or "data" not in result:
            cached = self._last_valid_competitors.get((asset, payment_method))
            if cached and (time.time() - cached[0]) <= 90.0:
                return list(cached[1])
            return []

        data = result.get("data", [])
        if not data:
            self._last_valid_competitors[(asset, payment_method)] = (time.time(), [])
            return []

        # Guardar snapshot crudo solo si está habilitado explícitamente (evita inflación de 27 GB en SQLite)
        if self.save_raw_snapshots:
            self.db.save_snapshot(
                asset=asset,
                trade_type="BUY",
                payment_method=payment_method,
                snapshot_json=json.dumps(data, default=str),
            )

        # Parsear y filtrar anuncios propios
        ads = [AdInfo.from_search_response(item) for item in data]
        ads = [a for a in ads if a.adv_no not in self._my_adv_nos]

        # Calcular TC implícito
        spot_price = spot_prices.get(asset, 0)
        if spot_price <= 0:
            logger.warning("Sin precio spot para %s, no se puede calcular TC", asset)
            return []

        rates = []
        for i, ad in enumerate(ads):
            tc = ad.price / spot_price
            rates.append(ExchangeRate(
                asset=asset,
                payment_method=payment_method,
                price_ars=ad.price,
                spot_price_usdt=spot_price,
                tc_implicito=tc,
                position=i + 1,
                advertiser_no=ad.advertiser_no,
                advertiser_nickname=ad.advertiser_nickname,
                advertiser_completion_rate=ad.advertiser_completion_rate,
                advertiser_order_count=ad.advertiser_order_count,
                min_single_trans_amount=ad.min_single_trans_amount,
                max_single_trans_amount=ad.max_single_trans_amount,
                timestamp=datetime.now(),
            ))

        # Guardar en DB solo si el volcado histórico crudo está habilitado
        if rates and self.save_raw_snapshots:
            self.db.save_exchange_rates_batch(rates)

        self._last_valid_competitors[(asset, payment_method)] = (time.time(), list(rates))
        return rates

    async def scan_usdt_benchmark(
        self,
        payment_method: str,
        volume_ref: float,
        publisher_type: Optional[str] = "merchant",
    ) -> Optional[Benchmark]:
        """
        Escanea top N vendedores de USDT para un método de pago y volumen.
        Filtra exclusivamente comerciantes verificados (publisher_type="merchant").
        Retorna el benchmark (promedio de precios top N).
        """
        try:
            # En Binance SAPI /c2c/ads/search: tradeType="BUY" busca anuncios donde
            # el taker COMPRA crypto, es decir, donde los merchants VENDEN (benchmark de venta).
            result = await self.client.search_ads(
                asset="USDT",
                fiat=FIAT,
                trade_type="BUY",
                pay_types=[payment_method],
                trans_amount=volume_ref,
                publisher_type=publisher_type,
                rows=TOP_N_BENCHMARK,
            )
        except Exception as e:
            logger.error("Error escaneando benchmark USDT/%s: %s", payment_method, e)
            return None

        data = result.get("data", [])
        if not data:
            logger.warning("Sin datos de benchmark USDT para %s", payment_method)
            return None

        # Guardar snapshot solo si está habilitado explícitamente
        if self.save_raw_snapshots:
            self.db.save_snapshot(
                asset="USDT",
                trade_type="SELL",
                payment_method=payment_method,
                volume_filter=volume_ref,
                snapshot_json=json.dumps(data, default=str),
            )

        # Parsear precios y excluir anuncios propios para evitar auto-competencia
        ads = [AdInfo.from_search_response(item) for item in data]
        ads = [a for a in ads if a.adv_no not in self._my_adv_nos]
        prices = [a.price for a in ads[:TOP_N_BENCHMARK] if a.price > 0]

        if not prices:
            return None

        # Filtro Anti-Outliers simétrico para evitar distorsiones por vendedores artificialmente caros
        # o precios cebo/scams/fat-finger anormalmente baratos (< 2.5% de la mediana)
        if len(prices) >= 3:
            sorted_prices = sorted(prices)
            median_p = sorted_prices[len(sorted_prices) // 2]
            valid_prices = [p for p in prices if median_p * 0.975 <= p <= median_p * 1.025]
            avg_price = sum(valid_prices) / len(valid_prices) if valid_prices else median_p
        else:
            # Si hay 1 o 2 anuncios (método ilíquido), tomar el precio mínimo (más conservador)
            avg_price = min(prices)

        benchmark = Benchmark(
            payment_method=payment_method,
            avg_top_n_price=avg_price,
            individual_prices=prices,
            volume_filter=volume_ref,
            timestamp=datetime.now(),
        )

        # Guardar en DB
        self.db.save_benchmark(benchmark)

        return benchmark

    async def get_spot_prices(self, assets: list[str]) -> dict[str, float]:
        """Obtiene precios spot y los guarda en DB, con fallback a últimos precios conocidos."""
        try:
            prices = await self.spot.get_usdt_prices(assets)
            if prices:
                self._last_spot_prices.update(prices)
                self.db.save_spot_prices(prices)
            return self._last_spot_prices.copy() if self._last_spot_prices else prices
        except Exception as e:
            logger.warning("Error obteniendo precios spot: %s. Usando últimos precios conocidos.", e)
            return self._last_spot_prices.copy()

    async def scan_full_cycle(
        self,
        assets: list[str],
        method_groups: dict[int, list[str]],
        volume_ref: float,
        max_stock_ars: Optional[float] = None,
    ) -> dict:
        """
        Ejecuta un ciclo completo de escaneo.

        Args:
            assets: Lista de activos a escanear
            method_groups: {1: ["BANK","MP",...], 2: [...], 3: [...]}
            volume_ref: Volumen de referencia para benchmark USDT
            max_stock_ars: Saldo máximo en ARS disponible para limitar benchmark al inventario real

        Returns:
            {
                "spot_prices": {"BTC": 100000, ...},
                "competitors": {(asset, method): [ExchangeRate, ...], ...},
                "benchmarks": {"BANK": Benchmark, "MP": Benchmark, ...},
            }
        """
        # 1. Spot prices
        spot_prices = await self.get_spot_prices(assets)
        logger.info("Spot prices: %s", {k: f"${v:,.2f}" for k, v in spot_prices.items()})

        # 2. Benchmark USDT por método (en paralelo controlado con semáforo)
        all_methods = set()
        method_to_group = {}
        for grp, methods in method_groups.items():
            for m in methods:
                all_methods.update(methods)
                method_to_group[m] = grp

        sem = asyncio.Semaphore(SCANNER_CONCURRENCY)

        async def _fetch_bm(method: str):
            async with sem:
                try:
                    grp = method_to_group.get(method, 1)
                    # Para benchmark de venta mayorista: usar el volumen operativo real (max_stock_ars)
                    # o volume_ref si no se detectó volumen suficiente (> $10.000 ARS)
                    if max_stock_ars and max_stock_ars > 10_000.0:
                        target_vol = max_stock_ars
                    else:
                        target_vol = volume_ref

                    eff_vol = max(10_000.0, target_vol)
                    bm = await self.scan_usdt_benchmark(method, eff_vol, publisher_type="merchant")
                    return method, bm
                except Exception as e:
                    logger.error("Error inesperado en benchmark USDT/%s: %s", method, e)
                    return method, None

        bm_results = await asyncio.gather(*[_fetch_bm(m) for m in all_methods])
        benchmarks: dict[str, Benchmark] = {m: bm for m, bm in bm_results if bm}

        logger.info(
            "Benchmarks USDT (%d/%d): %s",
            len(benchmarks),
            len(all_methods),
            {k: f"${v.avg_top_n_price:,.2f}" for k, v in benchmarks.items()},
        )

        # 3. Competencia de compra por asset × método (en paralelo controlado con semáforo)
        async def _fetch_comp(asset: str, method: str):
            async with sem:
                try:
                    rates = await self.scan_competitors(asset, method, spot_prices)
                    return (asset, method), rates
                except Exception as e:
                    logger.error("Error inesperado en competencia %s/%s: %s", asset, method, e)
                    return (asset, method), []

        comp_tasks = [
            _fetch_comp(asset, method)
            for asset in assets
            for method in all_methods
        ]
        comp_results = await asyncio.gather(*comp_tasks)
        competitors: dict[tuple[str, str], list[ExchangeRate]] = dict(comp_results)

        logger.info(
            "Escaneados %d combinaciones asset×método con concurrencia=%d",
            len(competitors),
            SCANNER_CONCURRENCY,
        )

        # 4. Volatilidades 24h desde Binance Spot
        try:
            volatilities = await self.spot.get_24hr_volatilities(assets)
        except Exception as e:
            logger.warning("Error obteniendo volatilidades spot: %s", e)
            volatilities = {}

        # 5. Guardar resumen analítico compacto cada 5 minutos (~5 MB/año en lugar de 27 GB)
        now_ts = time.time()
        last_intel_ts = getattr(self, "_last_compact_intel_ts", 0.0)
        if now_ts - last_intel_ts >= 300.0 and hasattr(self.db, "record_compact_market_intel"):
            try:
                self.db.record_compact_market_intel(competitors, spot_prices)
                self._last_compact_intel_ts = now_ts
            except Exception as e_intel:
                logger.debug("No se pudo registrar resumen compacto de mercado: %s", e_intel)

        return {
            "spot_prices": spot_prices,
            "competitors": competitors,
            "benchmarks": benchmarks,
            "volatilities": volatilities,
        }

    def get_best_competitor(
        self,
        competitors: list[ExchangeRate],
    ) -> Optional[ExchangeRate]:
        """
        Retorna el mejor competidor de compra (BUY ads: mayor precio ARS).
        Filtra anomalías/outliers dinámicamente según la dispersión y profundidad
        del libro de órdenes (evaluando hasta 5 posiciones):
        - Si hay menos de 3 competidores: no se descarta (muestra insuficiente).
        - Si hay 3 o más competidores: evalúa si la brecha es un salto anómalo
          aislado en comparación con la pendiente natural de las siguientes posiciones.
        - Umbral base: 1.0% para stablecoins, 3.5% para altcoins/criptos volátiles.
        """
        if not competitors:
            return None

        # 1. Filtro de calidad: descartar anunciantes cebo o con baja tasa de finalización
        has_metrics = any(c.advertiser_order_count > 0 or c.advertiser_completion_rate > 0 for c in competitors)
        if has_metrics:
            qualified_comps = [
                c for c in competitors
                if (c.advertiser_order_count >= MIN_COMPETITOR_ORDERS and 
                    c.advertiser_completion_rate >= MIN_COMPETITOR_COMPLETION_RATE)
            ]
            active_comps = qualified_comps
            if not active_comps:
                logger.info("Filtro anti-cebo: ningún competidor cumple requisitos de calidad (órdenes >= %d, tasa >= %.2f)",
                            MIN_COMPETITOR_ORDERS, MIN_COMPETITOR_COMPLETION_RATE)
                return None
        else:
            active_comps = competitors

        if len(active_comps) == 1:
            return active_comps[0]

        sorted_comps = sorted(active_comps, key=lambda x: x.price_ars, reverse=True)

        # Si hay menos de 3 competidores: no se descarta (muestra insuficiente para detectar anomalías de libro)
        if len(sorted_comps) < 3:
            return sorted_comps[0]

        # Para 3 o más competidores: analizar salto contra la dispersión de los siguientes puestos (hasta 5)
        for idx in range(len(sorted_comps) - 1):
            cand = sorted_comps[idx]
            next_cand = sorted_comps[idx + 1]

            if next_cand.price_ars <= 0:
                return cand

            gap_pct = (cand.price_ars - next_cand.price_ars) / next_cand.price_ars

            # Calcular la pendiente normal entre las posiciones siguientes (hasta 4 puestos más)
            subsequent = sorted_comps[idx + 1: idx + 5]
            sub_gaps = []
            for j in range(len(subsequent) - 1):
                p_curr = subsequent[j].price_ars
                p_next = subsequent[j + 1].price_ars
                if p_next > 0:
                    sub_gaps.append((p_curr - p_next) / p_next)

            if sub_gaps:
                normal_slope = max(sum(sub_gaps) / len(sub_gaps), 0.002)
            else:
                normal_slope = 0.005

            # Definir umbral base según tipo de activo
            is_stable = cand.asset in STABLECOINS
            base_threshold = 0.010 if is_stable else 0.035

            # Se considera anomalía si supera el umbral base Y además es un salto desproporcionado (>2.2x)
            # respecto a la pendiente natural del libro de órdenes
            is_anomaly = (gap_pct > base_threshold) and (gap_pct > normal_slope * 2.2)

            if is_anomaly:
                _anom_key = (cand.asset, cand.advertiser_nickname, idx + 1)
                _now_ts = time.time()
                if _now_ts - self._anomaly_log_ts.get(_anom_key, 0.0) >= 600.0:
                    self._anomaly_log_ts[_anom_key] = _now_ts
                    logger.warning(
                        "⚠️ Anomalía detectada en posición #%d (%s: $%.2f). "
                        "Salto de %.2f%% contra siguiente ($%.2f), pendiente promedio del libro: %.2f%%. Descartando outlier.",
                        idx + 1, cand.advertiser_nickname, cand.price_ars,
                        gap_pct * 100, next_cand.price_ars, normal_slope * 100,
                    )
                else:
                    logger.debug(
                        "⚠️ Anomalía detectada en posición #%d (%s: $%.2f). "
                        "Salto de %.2f%% contra siguiente ($%.2f), pendiente promedio del libro: %.2f%%. Descartando outlier.",
                        idx + 1, cand.advertiser_nickname, cand.price_ars,
                        gap_pct * 100, next_cand.price_ars, normal_slope * 100,
                    )
                continue  # Descartar cand y evaluar al siguiente como nuevo mejor competidor
            else:
                return cand

        return sorted_comps[-1]
