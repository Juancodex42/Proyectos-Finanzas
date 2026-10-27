"""
Módulo de coordinación central de anuncios P2P en Binance (AdsManager).
Coordina la sincronización de estado, asignación de grupos y delega en mutator,
lifecycle y replenisher.
"""
import logging
import time
from typing import Optional

from core.network.binance_api import BinanceClient
from data.database import Database
from data.models import MyAd, BotConfig
from config.settings import (
    AD_STATUS_CLOSED,
    AD_API_ERROR_COOLDOWN_SECONDS,
    DEFAULT_BUY_AUTO_REPLY,
    DEFAULT_BUY_REMARKS,
)
from core.sell_advisor import SELL_CLUSTERS_CONFIG
from core.ads.mutator import AdMutator
from core.ads.lifecycle import AdLifecycle
from core.ads.replenisher import AdReplenisher

logger = logging.getLogger(__name__)


class AdsManager:
    """Coordinador CRUD de anuncios propios (COMPRA y VENTA)."""

    def __init__(self, client: BinanceClient, db: Database):
        self.client = client
        self.db = db
        self._last_83714_ts: float = 0.0
        self._last_83714_error: bool = False
        self._rate_limit_until: float = 0.0
        self._resume_cooldowns: dict[str, float] = {}
        self._resume_sell_cooldowns: dict[str, float] = {}

        self.mutator = AdMutator(self)
        self.lifecycle = AdLifecycle(self)
        self.replenisher = AdReplenisher(self)

    @property
    def is_83714_active(self) -> bool:
        """Verifica si el circuit breaker por error 83714 está activo."""
        if self._last_83714_ts > 0 and (time.time() - self._last_83714_ts) < AD_API_ERROR_COOLDOWN_SECONDS:
            return True
        if self._last_83714_error:
            self._last_83714_error = False
        return False

    async def sync_my_ads(self) -> list[MyAd]:
        """Sincroniza anuncios de COMPRA desde Binance con SQLite local."""
        all_ads: list[MyAd] = []
        page, fetch_ok, expected_total = 1, True, 0
        existing_map = {a.adv_no: a for a in self.db.get_my_ads()}
        while True:
            try:
                result = await self.client.list_my_ads(trade_type="BUY", page=page, rows=20)
            except Exception as e:
                logger.error("Error listando mis anuncios de compra (page %d): %s", page, e)
                fetch_ok = False
                break

            if not isinstance(result, dict):
                fetch_ok = False
                break

            data = result.get("data", [])
            if not data:
                if page > 1 and expected_total > len(all_ads):
                    logger.warning("Paginación truncada en sync_my_ads (page %d vacía)", page)
                    fetch_ok = False
                break

            for item in data:
                if item.get("advStatus") == AD_STATUS_CLOSED:
                    continue
                methods = [
                    m.get("identifier", m.get("payType", ""))
                    for m in item.get("tradeMethods", [])
                    if m.get("identifier", m.get("payType", ""))
                ]
                adv_no = item.get("advNo", "")
                existing = existing_map.get(adv_no)
                ad = MyAd(
                    adv_no=adv_no,
                    asset=item.get("asset", ""),
                    ad_group=existing.ad_group if existing else 0,
                    current_price=float(item.get("price", 0)),
                    payment_methods=methods,
                    status=item.get("advStatus", 1),
                    init_amount=float(item.get("initAmount", 0) or 0.0),
                    surplus_amount=float(item.get("surplusAmount", 0) or 0.0),
                    min_trans_amount=float(item.get("minSingleTransAmount", 0) or 0.0),
                    max_trans_amount=float(item.get("maxSingleTransAmount", 0) or 0.0),
                    last_repositioned=existing.last_repositioned if existing else None,
                )
                all_ads.append(ad)

            expected_total = int(result.get("total", 0) or 0)
            if page * 20 >= expected_total:
                break
            page += 1

        if fetch_ok and all_ads:
            for ad in all_ads:
                self.db.save_my_ad(ad)
            self.db.purge_ads_except({ad.adv_no for ad in all_ads})
            logger.info("Sincronizados %d anuncios propios de compra", len(all_ads))
            return all_ads
        elif not fetch_ok:
            logger.warning("Fallo de red en sync Binance; preservando BD local")
            return self.db.get_my_ads()
        self.db.clear_my_ads()
        logger.info("Sincronización completada: 0 anuncios de compra.")
        return []

    async def assign_groups(self, ads: list[MyAd], method_groups: dict[int, list[str]]):
        """Asigna grupo a cada anuncio basándose en máxima coincidencia de métodos de pago."""
        for ad in ads:
            best_group, best_overlap = 0, 0
            ad_methods = set(ad.payment_methods)
            for group_num, group_methods in method_groups.items():
                overlap = len(ad_methods.intersection(group_methods))
                if overlap > best_overlap:
                    best_overlap, best_group = overlap, group_num
            if best_group > 0:
                ad.ad_group = best_group
                self.db.save_my_ad(ad)

    async def sync_my_sell_ads(self) -> list[MyAd]:
        """Sincroniza anuncios de VENTA desde Binance y asigna clusters G1, G2, G3."""
        all_ads: list[MyAd] = []
        page, fetch_ok = 1, True
        existing_map = {a.adv_no: a for a in self.db.get_my_sell_ads()}

        while True:
            try:
                result = await self.client.list_my_ads(trade_type="SELL", page=page, rows=20)
            except Exception as e:
                logger.error("Error listando mis anuncios de venta (page %d): %s", page, e)
                fetch_ok = False
                break

            if not isinstance(result, dict):
                fetch_ok = False
                break

            data = result.get("data", [])
            if not data:
                break

            for item in data:
                if item.get("advStatus") == AD_STATUS_CLOSED:
                    continue
                methods = [
                    m.get("identifier", m.get("payType", ""))
                    for m in item.get("tradeMethods", [])
                    if m.get("identifier", m.get("payType", ""))
                ]
                adv_no = item.get("advNo", "")
                existing = existing_map.get(adv_no)
                best_cluster = existing.ad_group if existing and existing.ad_group > 0 else 1
                if not existing or existing.ad_group == 0:
                    best_overlap, ad_set = 0, set(methods)
                    for cfg in SELL_CLUSTERS_CONFIG:
                        overlap = len(ad_set.intersection(cfg["methods"]))
                        if overlap > best_overlap:
                            best_overlap, best_cluster = overlap, cfg["id"]

                ad = MyAd(
                    adv_no=adv_no,
                    asset=item.get("asset", "USDT"),
                    ad_group=best_cluster,
                    current_price=float(item.get("price", 0)),
                    payment_methods=methods,
                    status=item.get("advStatus", 1),
                    init_amount=float(item.get("initAmount", 0) or 0.0),
                    surplus_amount=float(item.get("surplusAmount", 0) or 0.0),
                    min_trans_amount=float(item.get("minSingleTransAmount", 0) or 0.0),
                    max_trans_amount=float(item.get("maxSingleTransAmount", 0) or 0.0),
                    last_repositioned=existing.last_repositioned if existing else None,
                    trade_type="SELL",
                )
                all_ads.append(ad)

            if page * 20 >= int(result.get("total", 0) or 0):
                break
            page += 1

        if fetch_ok and all_ads:
            scores = [
                (len(set(ad.payment_methods).intersection(cfg["methods"])), ad.adv_no, cfg["id"])
                for ad in all_ads for cfg in SELL_CLUSTERS_CONFIG
            ]
            scores.sort(key=lambda x: x[0], reverse=True)
            ad_cluster_map, assigned = {}, set()
            for _, adv_no, c_id in scores:
                if adv_no not in ad_cluster_map and c_id not in assigned:
                    ad_cluster_map[adv_no], _ = c_id, assigned.add(c_id)

            for ad in all_ads:
                if ad.adv_no in ad_cluster_map:
                    ad.ad_group = ad_cluster_map[ad.adv_no]
                else:
                    available = [c["id"] for c in SELL_CLUSTERS_CONFIG if c["id"] not in assigned]
                    if available:
                        ad.ad_group = available[0]
                        assigned.add(available[0])

            for ad in all_ads:
                self.db.save_my_sell_ad(ad)
            self.db.purge_sell_ads_except({ad.adv_no for ad in all_ads})
            logger.info("Sincronizados %d anuncios propios de VENTA", len(all_ads))
            return all_ads
        elif not fetch_ok:
            return self.db.get_my_sell_ads()
        self.db.clear_my_sell_ads()
        return []

    # ── Delegaciones a AdMutator ──────────────────────────────────────────────

    async def update_ad_params(
        self, adv_no: str, price: Optional[float] = None, init_amount: Optional[float] = None,
        min_trans_amount: Optional[float] = None, max_trans_amount: Optional[float] = None,
        surplus_amount: Optional[float] = None,
    ) -> bool:
        """Actualiza parámetros de anuncio de compra."""
        return await self.mutator.update_ad_params(
            adv_no=adv_no, price=price, init_amount=init_amount, min_trans_amount=min_trans_amount,
            max_trans_amount=max_trans_amount, surplus_amount=surplus_amount,
        )

    async def update_price(self, adv_no: str, new_price: float) -> bool:
        """Actualiza precio de un anuncio vía quickedit."""
        return await self.mutator.update_price(adv_no, new_price)

    async def update_ad_limits(
        self, adv_no: str, min_trans_amount: Optional[float] = None,
        max_trans_amount: Optional[float] = None,
    ) -> bool:
        """Actualiza límites de transacción de compra."""
        return await self.mutator.update_ad_limits(adv_no, min_trans_amount, max_trans_amount)

    async def update_sell_ad_params(
        self, adv_no: str, price: Optional[float] = None, init_amount: Optional[float] = None,
        min_trans_amount: Optional[float] = None, max_trans_amount: Optional[float] = None,
        surplus_amount: Optional[float] = None,
    ) -> bool:
        """Actualiza parámetros de un anuncio de venta."""
        return await self.mutator.update_sell_ad_params(
            adv_no=adv_no, price=price, init_amount=init_amount, min_trans_amount=min_trans_amount,
            max_trans_amount=max_trans_amount, surplus_amount=surplus_amount,
        )

    # ── Delegaciones a AdLifecycle ────────────────────────────────────────────

    async def pause_ad(self, adv_no: str) -> bool:
        """Pausa un anuncio de compra."""
        return await self.lifecycle.pause_ad(adv_no)

    async def resume_ad(self, adv_no: str) -> bool:
        """Reactiva un anuncio de compra."""
        return await self.lifecycle.resume_ad(adv_no)

    async def pause_sell_ad(self, adv_no: str) -> bool:
        """Pausa un anuncio de venta individual."""
        return await self.lifecycle.pause_sell_ad(adv_no)

    async def resume_sell_ad(self, adv_no: str) -> bool:
        """Reactiva un anuncio de venta individual."""
        return await self.lifecycle.resume_sell_ad(adv_no)

    async def pause_ads_batch(self, adv_nos: list[str], chunk_size: int = 15) -> int:
        """Pausa anuncios en lote."""
        return await self.lifecycle.pause_ads_batch(adv_nos, chunk_size=chunk_size)

    async def pause_all(self) -> int:
        """Pausa todos los anuncios activos (compra y venta)."""
        return await self.lifecycle.pause_all()

    async def pause_all_sell_ads(self) -> int:
        """Pausa todos los anuncios de venta activos."""
        return await self.lifecycle.pause_all_sell_ads()

    async def resume_all(
        self, config: Optional[BotConfig] = None, skip_adv_nos: Optional[set[str]] = None,
    ) -> int:
        """Reactiva todos los anuncios de compra elegibles."""
        return await self.lifecycle.resume_all(config=config, skip_adv_nos=skip_adv_nos)

    async def resume_all_sell_ads(
        self, config: Optional[BotConfig] = None, skip_adv_nos: Optional[set[str]] = None,
    ) -> int:
        """Reactiva todos los anuncios de venta elegibles."""
        return await self.lifecycle.resume_all_sell_ads(config=config, skip_adv_nos=skip_adv_nos)

    async def pause_by_asset(self, asset: str) -> int:
        """Pausa todos los anuncios de un activo."""
        return await self.lifecycle.pause_by_asset(asset)

    async def resume_by_asset(self, asset: str) -> int:
        """Reactiva todos los anuncios de un activo."""
        return await self.lifecycle.resume_by_asset(asset)

    async def create_buy_ad(
        self, asset: str, price: float, init_amount: float, min_trans_amount: float,
        max_trans_amount: float, trade_methods: list[dict],
        auto_reply_msg: str = DEFAULT_BUY_AUTO_REPLY, remarks: str = DEFAULT_BUY_REMARKS,
        online_now: bool = False,
    ) -> Optional[str]:
        """Crea un anuncio de compra."""
        return await self.lifecycle.create_buy_ad(
            asset=asset, price=price, init_amount=init_amount, min_trans_amount=min_trans_amount,
            max_trans_amount=max_trans_amount, trade_methods=trade_methods,
            auto_reply_msg=auto_reply_msg, remarks=remarks, online_now=online_now,
        )

    async def create_sell_ad(
        self, price: float, init_amount: float, min_trans_amount: float,
        max_trans_amount: float, trade_methods: list[dict],
        auto_reply_msg: str = "", remarks: str = "", online_now: bool = False,
    ) -> Optional[str]:
        """Crea un anuncio de venta."""
        return await self.lifecycle.create_sell_ad(
            price=price, init_amount=init_amount, min_trans_amount=min_trans_amount,
            max_trans_amount=max_trans_amount, trade_methods=trade_methods,
            auto_reply_msg=auto_reply_msg, remarks=remarks, online_now=online_now,
        )

    async def delete_all_buy_ads(self) -> dict:
        """Elimina definitivamente todos los anuncios de compra."""
        return await self.lifecycle.delete_all_buy_ads()

    async def delete_all_sell_ads(self) -> dict:
        """Elimina definitivamente todos los anuncios de venta."""
        return await self.lifecycle.delete_all_sell_ads()

    # ── Delegaciones a AdReplenisher ──────────────────────────────────────────

    async def ensure_ads_for_all_assets(
        self, method_groups: dict[int, list[str]], pay_id_map: dict[str, int],
        spot_prices: dict[str, float], usdt_benchmark: float = 1580.0,
    ) -> list[MyAd]:
        """Garantiza la existencia y correcta configuración de los 42 anuncios."""
        return await self.replenisher.ensure_ads_for_all_assets(
            method_groups=method_groups, pay_id_map=pay_id_map, spot_prices=spot_prices,
            usdt_benchmark=usdt_benchmark,
        )

    async def reconcile_all_ads(
        self, method_groups: dict[int, list[str]], pay_id_map: dict[str, int],
        spot_prices: dict[str, float], usdt_benchmark: float = 1580.0,
        set_online: bool = False, create_missing: bool = True,
        config: Optional[BotConfig] = None,
    ) -> dict:
        """Escaneo y reconciliación profunda de anuncios de COMPRA."""
        return await self.replenisher.reconcile_all_ads(
            method_groups=method_groups, pay_id_map=pay_id_map, spot_prices=spot_prices,
            usdt_benchmark=usdt_benchmark, set_online=set_online, create_missing=create_missing,
            config=config,
        )

    async def reconcile_sell_ads(
        self, pay_id_map: dict[str, int], benchmarks: Optional[dict] = None,
        available_crypto_stock: float = 350.0, set_online: bool = False,
    ) -> dict:
        """Reconciliación y recarga en caliente de los 3 clusters de venta."""
        return await self.replenisher.reconcile_sell_ads(
            pay_id_map=pay_id_map, benchmarks=benchmarks,
            available_crypto_stock=available_crypto_stock, set_online=set_online,
        )
