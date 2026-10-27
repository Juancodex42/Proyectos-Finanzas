"""
Módulo de ciclo de vida de anuncios P2P en Binance.
Maneja creación, pausa individual y por lote, reactivación con circuit breaker,
y eliminación definitiva de anuncios de COMPRA y VENTA.
"""
import asyncio
import logging
import time
from typing import Optional, TYPE_CHECKING

from core.network.binance_api import BinanceClientError
from data.models import BotConfig
from config.settings import (
    AD_STATUS_ONLINE, AD_STATUS_OFFLINE, AD_STATUS_CLOSED,
    AD_CREATION_COOLDOWN_SECONDS, DEFAULT_BUY_AUTO_REPLY, DEFAULT_BUY_REMARKS,
)

if TYPE_CHECKING:
    from core.ads.manager import AdsManager

logger = logging.getLogger(__name__)


class AdLifecycle:
    """Controlador del ciclo de vida de anuncios P2P (activación, pausa, cierre, creación)."""

    def __init__(self, manager: "AdsManager"):
        self.manager = manager

    async def pause_ad(self, adv_no: str) -> bool:
        """Pausa un anuncio de compra (lo pone offline)."""
        try:
            res = await self.manager.client.update_ad_status(adv_nos=[adv_no], status=AD_STATUS_OFFLINE)
            if res and (res.get("code") == "000000" or res.get("data") is True or res.get("success") is True):
                self.manager.db.update_ad_status(adv_no, AD_STATUS_OFFLINE)
                logger.info("⏸️ Anuncio pausado: %s", adv_no)
                return True
            logger.error("Respuesta no exitosa al pausar %s: %s", adv_no, res)
            return False
        except Exception as e:
            logger.error("Error pausando %s: %s", adv_no, e)
            return False

    async def pause_sell_ad(self, adv_no: str) -> bool:
        """Pausa un anuncio de venta individual."""
        return await self.pause_ad(adv_no)

    async def _resume_single(self, adv_no: str, is_sell: bool) -> bool:
        """Reactivación de un anuncio individual con circuit breaker y cooldown tras fallo."""
        cooldown_dict = self.manager._resume_sell_cooldowns if is_sell else self.manager._resume_cooldowns
        trade_label = "venta" if is_sell else "compra"

        if getattr(self.manager, "_rate_limit_until", 0.0) > time.time():
            logger.debug("⏳ Saltando reactivación de %s %s por Rate Limit activo", trade_label, adv_no)
            return False
        if cooldown_dict.get(adv_no, 0.0) > time.time():
            logger.debug("⏳ Saltando reactivación de %s %s (en cooldown de reactivación)", trade_label, adv_no)
            return False

        try:
            res = await self.manager.client.update_ad_status(adv_nos=[adv_no], status=AD_STATUS_ONLINE)
            if res and (res.get("code") == "000000" or res.get("data") is True or res.get("success") is True):
                self.manager.db.update_ad_status(adv_no, AD_STATUS_ONLINE)
                cooldown_dict.pop(adv_no, None)
                logger.info("▶️ Anuncio reactivado (%s): %s", trade_label, adv_no)
                return True
            logger.error("Respuesta no exitosa al reactivar %s (%s): %s", adv_no, trade_label, res)
            cooldown_dict[adv_no] = time.time() + 5.0
            return False
        except Exception as e:
            is_429 = "429" in str(e) or "Rate limited" in str(e)
            retry_wait = getattr(e, "retry_after", None)
            wait_time = (float(retry_wait) + 0.5 if retry_wait else 2.5) if is_429 else 5.0
            if is_429:
                self.manager._rate_limit_until = time.time() + wait_time
                logger.warning("🛑 Rate limit (429) al reactivar %s %s (%.1fs).", trade_label, adv_no, wait_time)
            cooldown_dict[adv_no] = time.time() + wait_time
            logger.error("Error reactivando %s (%s): %s", adv_no, trade_label, e)
            return False

    async def resume_ad(self, adv_no: str) -> bool:
        """Reactiva un anuncio de compra (lo pone online) con circuit breaker de rate limit."""
        return await self._resume_single(adv_no, is_sell=False)

    async def resume_sell_ad(self, adv_no: str) -> bool:
        """Reactiva un anuncio de venta individual con verificación de rate limit."""
        return await self._resume_single(adv_no, is_sell=True)

    async def _batch_update_ad_status(
        self, adv_nos: list[str], status: int, is_sell: bool = False, chunk_size: int = 15,
    ) -> int:
        """Operación por lotes unificada para actualización de estado en Binance y SQLite."""
        unique_nos = [no for no in dict.fromkeys(adv_nos) if no]
        if not unique_nos:
            return 0
        total, action = 0, "pausados" if status == AD_STATUS_OFFLINE else "reactivados"
        for i in range(0, len(unique_nos), chunk_size):
            chunk = unique_nos[i:i + chunk_size]
            try:
                res = await self.manager.client.update_ad_status(adv_nos=chunk, status=status)
                if res and (res.get("code") in ("000000", "0", 0) or res.get("data") is True or res.get("success") is True):
                    for no in chunk:
                        self.manager.db.update_ad_status(no, status)
                    total += len(chunk)
                    logger.info("⏸️ Lote de %d anuncios %s en Binance: %s", len(chunk), action, chunk)
                else:
                    if isinstance(res, dict) and any(str(v) in ("429", "187000") for v in res.values()):
                        self.manager._rate_limit_until = time.time() + 30.0
                        if status == AD_STATUS_OFFLINE:
                            for no in chunk:
                                self.manager.db.update_ad_status(no, status)
                        break
                    for no in chunk:
                        if await (self.pause_ad(no) if status == AD_STATUS_OFFLINE else self._resume_single(no, is_sell)):
                            total += 1
                        await asyncio.sleep(0.3)
            except Exception as e:
                if "429" in str(e) or "Rate limited" in str(e):
                    self.manager._rate_limit_until = time.time() + 30.0
                    if status == AD_STATUS_OFFLINE:
                        for no in chunk:
                            self.manager.db.update_ad_status(no, status)
                    break
                for no in chunk:
                    try:
                        if await (self.pause_ad(no) if status == AD_STATUS_OFFLINE else self._resume_single(no, is_sell)):
                            total += 1
                        await asyncio.sleep(0.3)
                    except Exception as e_ind:
                        logger.error("Error individual %s: %s", no, e_ind)
            if i + chunk_size < len(unique_nos):
                await asyncio.sleep(0.3)
        return total

    async def pause_ads_batch(self, adv_nos: list[str], chunk_size: int = 15) -> int:
        """Pausa una lista de anuncios en batch usando POST /sapi/v1/c2c/ads/updateStatus."""
        return await self._batch_update_ad_status(adv_nos, AD_STATUS_OFFLINE, chunk_size=chunk_size)

    async def pause_all(self) -> int:
        """Pausa todos los anuncios (compras y ventas) en lotes de hasta 15. Retorna cantidad pausados."""
        buy = [a.adv_no for a in (self.manager.db.get_my_ads() or []) if a.status == AD_STATUS_ONLINE and a.adv_no]
        raw_sell = self.manager.db.get_my_sell_ads() if hasattr(self.manager.db, "get_my_sell_ads") else []
        sell = [a.adv_no for a in (raw_sell or []) if a.status == AD_STATUS_ONLINE and a.adv_no]
        all_online = list(dict.fromkeys(buy + sell))
        if not all_online:
            return 0
        total = await self.pause_ads_batch(all_online, chunk_size=15)
        logger.info("⏸️ %d anuncios (compras y ventas) pausados en total", total)
        return total

    async def pause_all_sell_ads(self) -> int:
        """Pausa todos los anuncios de venta activos en Binance."""
        sell_ads = self.manager.db.get_my_sell_ads("USDT") if hasattr(self.manager.db, "get_my_sell_ads") else []
        active_ads = [a for a in (sell_ads or []) if a.status == AD_STATUS_ONLINE and a.adv_no]
        if not active_ads:
            return 0
        active_nos = [a.adv_no for a in active_ads]
        res = await self.pause_ads_batch(active_nos, chunk_size=15)
        if res > 0:
            for a in active_ads:
                a.status = AD_STATUS_OFFLINE
        return res

    async def resume_all(
        self,
        config: Optional[BotConfig] = None,
        skip_adv_nos: Optional[set[str]] = None,
    ) -> int:
        """Reactiva todos los anuncios de COMPRA elegibles en lotes de hasta 10."""
        paused_ads, paused_assets = set(config.paused_ads) if config else set(), set(config.paused_assets) if config else set()
        adv_nos = [
            a.adv_no for a in (self.manager.db.get_my_ads() or [])
            if (skip_adv_nos is None or a.adv_no not in skip_adv_nos)
            and a.status == AD_STATUS_OFFLINE and a.adv_no not in paused_ads
            and a.asset not in paused_assets and a.init_amount > 0
        ]
        total = await self._batch_update_ad_status(adv_nos, AD_STATUS_ONLINE, is_sell=False, chunk_size=10)
        logger.info("▶️ %d anuncios de compra reactivados", total)
        return total

    async def resume_all_sell_ads(
        self,
        config: Optional[BotConfig] = None,
        skip_adv_nos: Optional[set[str]] = None,
    ) -> int:
        """Reactiva todos los anuncios de venta (USDT) registrados en la base de datos."""
        raw_sell = self.manager.db.get_my_sell_ads("USDT") if hasattr(self.manager.db, "get_my_sell_ads") else []
        skip_set = (skip_adv_nos or set()) | (set(config.paused_ads) if config else set())
        adv_nos = [a.adv_no for a in (raw_sell or []) if a.status != AD_STATUS_ONLINE and a.adv_no and a.adv_no not in skip_set]
        if not adv_nos:
            logger.info("▶️ resume_all_sell_ads: No hay anuncios de venta pausados para reactivar.")
            return 0
        total = await self._batch_update_ad_status(adv_nos, AD_STATUS_ONLINE, is_sell=True, chunk_size=10)
        if total > 0 and raw_sell:
            for a in raw_sell:
                if a.adv_no in adv_nos:
                    a.status = AD_STATUS_ONLINE
        logger.info("▶️ Se reactivaron %d anuncios de venta en Binance: %s", total, adv_nos)
        return total

    async def pause_by_asset(self, asset: str) -> int:
        """Pausa todos los anuncios de un activo en batch."""
        ads = self.manager.db.get_my_ads(asset=asset)
        to_pause = [ad.adv_no for ad in ads if ad.status == AD_STATUS_ONLINE and ad.adv_no]
        return await self.pause_ads_batch(to_pause) if to_pause else 0

    async def resume_by_asset(self, asset: str) -> int:
        """Reactiva todos los anuncios de un activo."""
        ads = self.manager.db.get_my_ads(asset=asset)
        count = 0
        for ad in ads:
            if ad.status == AD_STATUS_OFFLINE and await self.resume_ad(ad.adv_no):
                count += 1
                await asyncio.sleep(0.5)
        return count

    async def _create_ad_with_retry(
        self,
        asset: str, trade_type: str, price: float, init_amount: float,
        min_trans_amount: float, max_trans_amount: float, trade_methods: list[dict],
        auto_reply_msg: str, remarks: str, online_now: bool, max_attempts: int = 3,
    ) -> Optional[str]:
        """Crea un anuncio en Binance gestionando cooldowns (187000) y circuit breaker (83714)."""
        safe_methods = (trade_methods or [])[:5]
        for attempt in range(max_attempts):
            try:
                res = await self.manager.client.create_ad(
                    asset=asset, trade_type=trade_type, price=price, init_amount=init_amount,
                    min_trans_amount=min_trans_amount, max_trans_amount=max_trans_amount,
                    trade_methods=safe_methods, auto_reply_msg=auto_reply_msg,
                    remarks=remarks, online_now=online_now,
                )
                adv_no = res.get("data", "")
                if adv_no:
                    logger.info("✅ Anuncio %s creado: %s (%s a $%.2f)", trade_type, adv_no, asset, price)
                    return str(adv_no)
                logger.warning("Creación de %s sin advNo en response: %s", trade_type, res)
                return None
            except BinanceClientError as e:
                if "187000" in str(e) and attempt < max_attempts - 1:
                    wait_time = (attempt + 1) * AD_CREATION_COOLDOWN_SECONDS
                    logger.warning("⏳ Cooldown 187000 en %s %s. Esperando %.1fs...", trade_type, asset, wait_time)
                    await asyncio.sleep(wait_time)
                    continue
                if "83714" in str(e):
                    self.manager._last_83714_ts = time.time()
                    self.manager._last_83714_error = True
                    logger.error("🚫 Suspensión 83714 detectada: %s", e)
                else:
                    logger.error("Error creando anuncio de %s %s: %s", trade_type, asset, e)
                return None
            except Exception as e:
                logger.error("Error creando anuncio de %s %s: %s", trade_type, asset, e)
                return None
        return None

    async def create_buy_ad(
        self, asset: str, price: float, init_amount: float, min_trans_amount: float,
        max_trans_amount: float, trade_methods: list[dict],
        auto_reply_msg: str = DEFAULT_BUY_AUTO_REPLY, remarks: str = DEFAULT_BUY_REMARKS,
        online_now: bool = False,
    ) -> Optional[str]:
        """Crea un nuevo anuncio de COMPRA con manejo de reintentos por cooldown."""
        return await self._create_ad_with_retry(
            asset=asset, trade_type="BUY", price=price, init_amount=init_amount,
            min_trans_amount=min_trans_amount, max_trans_amount=max_trans_amount,
            trade_methods=trade_methods, auto_reply_msg=auto_reply_msg,
            remarks=remarks, online_now=online_now, max_attempts=2,
        )

    async def create_sell_ad(
        self, price: float, init_amount: float, min_trans_amount: float,
        max_trans_amount: float, trade_methods: list[dict],
        auto_reply_msg: str = "", remarks: str = "", online_now: bool = False,
    ) -> Optional[str]:
        """Crea un nuevo anuncio de VENTA (USDT) en Binance con hasta 3 reintentos."""
        return await self._create_ad_with_retry(
            asset="USDT", trade_type="SELL", price=price, init_amount=init_amount,
            min_trans_amount=min_trans_amount, max_trans_amount=max_trans_amount,
            trade_methods=trade_methods, auto_reply_msg=auto_reply_msg,
            remarks=remarks, online_now=online_now, max_attempts=3,
        )

    async def _fetch_remote_adv_nos(self, trade_type: str) -> tuple[list[str], bool]:
        """Obtiene números de anuncios remotos de Binance para borrado masivo."""
        nos, page, complete = [], 1, True
        while True:
            try:
                res = await self.manager.client.list_my_ads(trade_type=trade_type, page=page, rows=20)
                data = res.get("data", [])
                if not data:
                    break
                for item in data:
                    if item.get("tradeType", trade_type) == trade_type:
                        adv_no = str(item.get("advNo", ""))
                        if adv_no and adv_no not in nos:
                            nos.append(adv_no)
                if page * 20 >= int(res.get("total", 0) or 0):
                    break
                page += 1
            except Exception as e:
                logger.error("Error consultando anuncios %s (pág %d): %s", trade_type, page, e)
                complete = False
                break
        return nos, complete

    async def _close_ad_list(self, adv_nos: list[str]) -> tuple[int, int, set[str]]:
        """Cierra una lista de anuncios uno a uno en Binance y actualiza DB."""
        deleted, errors, failed = 0, 0, set()
        for adv_no in adv_nos:
            try:
                r = await self.manager.client.close_ad(adv_no)
                is_ok = not (isinstance(r, dict) and r.get("code") not in (None, "000000", 0) and not r.get("success") and not r.get("data"))
                if is_ok:
                    deleted += 1
                    self.manager.db.update_ad_status(adv_no, AD_STATUS_CLOSED)
                    logger.info("  • Anuncio individual %s cerrado", adv_no)
                else:
                    errors += 1
                    failed.add(adv_no)
                    logger.error("❌ Falló cierre de %s: %s", adv_no, r)
            except Exception as e:
                errors += 1
                failed.add(adv_no)
                logger.error("❌ Excepción cerrando anuncio individual %s: %s", adv_no, e)
            await asyncio.sleep(0.25)
        return deleted, errors, failed

    async def delete_all_buy_ads(self) -> dict:
        """Cierra y elimina DEFINITIVAMENTE todos los anuncios de COMPRA en Binance (advStatus=4)."""
        logger.warning("🗑️ Iniciando proceso de eliminación de TODOS los anuncios de COMPRA...")
        remote_nos, complete = await self._fetch_remote_adv_nos("BUY")
        local_nos = [a.adv_no for a in self.manager.db.get_my_ads() if a.adv_no]
        all_nos = list(dict.fromkeys(remote_nos + local_nos))
        if not all_nos:
            if complete:
                self.manager.db.clear_my_ads()
            return {"total_found": 0, "deleted": 0, "errors": 0}
        deleted, errors, failed = await self._close_ad_list(all_nos)
        if errors == 0 and complete:
            self.manager.db.clear_my_ads()
        else:
            self.manager.db.purge_ads_except(failed)
        logger.info("🗑️ Eliminación compra: %d cerrados, %d errores de %d", deleted, errors, len(all_nos))
        return {"total_found": len(all_nos), "deleted": deleted, "errors": errors}

    async def delete_all_sell_ads(self) -> dict:
        """Cierra y elimina DEFINITIVAMENTE todos los anuncios de VENTA en Binance (advStatus=4)."""
        logger.warning("🗑️ Iniciando proceso de eliminación de TODOS los anuncios de VENTA...")
        remote_nos, _ = await self._fetch_remote_adv_nos("SELL")
        raw_sell = self.manager.db.get_my_sell_ads() if hasattr(self.manager.db, "get_my_sell_ads") else []
        all_nos = list(dict.fromkeys([a.adv_no for a in (raw_sell or []) if a.adv_no] + remote_nos))
        if not all_nos:
            return {"total_found": 0, "deleted": 0, "errors": 0}
        deleted, errors, _ = await self._close_ad_list(all_nos)
        self.manager.db.clear_my_sell_ads()
        logger.info("🗑️ Eliminación venta: %d exitosos, %d errores de %d", deleted, errors, len(all_nos))
        return {"total_found": len(all_nos), "deleted": deleted, "errors": errors}

