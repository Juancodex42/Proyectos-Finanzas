"""
Módulo de reposición y reconciliación profunda de anuncios P2P en Binance.
Gestiona el escaneo integral de 42 anuncios de compra (14 activos x 3 grupos),
y el reabastecimiento en caliente de los clusters de anuncios de venta en Binance.
"""
import asyncio
import logging
import math
from typing import Optional, TYPE_CHECKING

from core.sell_advisor import SELL_CLUSTERS_CONFIG
from data.models import MyAd, BotConfig
from config.settings import (
    P2P_ASSETS_ARS, ASSET_DEFAULTS, STABLECOINS, AD_CREATION_COOLDOWN_SECONDS,
    MIN_AD_PRICE_DIFF_RATIO, ASSET_PRECISION, GROUP_MIN_MULTIPLIERS,
    DEFAULT_BUY_AUTO_REPLY, DEFAULT_BUY_REMARKS, ALTCOIN_MIN_MARGIN_PCT,
    AD_STATUS_OFFLINE, AD_STATUS_CLOSED, AD_STATUS_ONLINE,
    SELL_GROUP_FLOORS_ARS, SELL_GROUP_LIMIT_FACTORS, SELL_AD_PRICE_DIFF_ARS,
)

if TYPE_CHECKING:
    from core.ads.manager import AdsManager

logger = logging.getLogger(__name__)


def compute_buy_ad_parameters(
    asset: str, group_num: int, base_price: float, defaults: dict,
) -> tuple[float, float, float, float]:
    """Calcula precio y límites escalonados reglamentarios para evitar colisiones en Binance."""
    group_offset = (group_num - 1) * max(0.01, round(base_price * MIN_AD_PRICE_DIFF_RATIO, 2))
    min_floor = round(base_price * 0.91, 2)
    initial_ad_price = round(max(base_price - group_offset, min_floor), 2)

    prec = ASSET_PRECISION.get(asset, 2)
    step_unit = 1.0 if prec == 0 else round(10 ** (-prec), prec)
    group_delta = max(step_unit, round(defaults["init_amount"] * 0.015, prec))
    raw_init = defaults["init_amount"] + (4 - group_num) * group_delta
    grp_init_amount = round(raw_init, prec) if prec > 0 else int(round(raw_init))
    if asset in STABLECOINS:
        grp_init_amount = max(grp_init_amount, 100.0)

    min_mult = GROUP_MIN_MULTIPLIERS.get(group_num, 1.0)
    grp_min_trans = round(defaults["min_trans"] * min_mult, 0)
    stock_capacity = float(int(grp_init_amount * initial_ad_price))
    grp_max_trans = min(
        round(defaults["max_trans"] * (1.0 - (group_num - 1) * 0.05), 0),
        stock_capacity,
    )
    return initial_ad_price, grp_init_amount, grp_min_trans, grp_max_trans


def compute_sell_trans_limits(
    cap_ars: float, floor_ars: float, min_f: float, max_f: float,
) -> tuple[float, float]:
    """Calcula límites de transacción consistentes para un anuncio de venta."""
    min_trans = float(max(floor_ars, round(cap_ars * min_f, 0)))
    max_trans = float(round(cap_ars * max_f, 0))
    if min_trans >= max_trans:
        min_trans = min(float(floor_ars), round(max_trans * 0.50, 0))
    return min_trans, max_trans


class AdReplenisher:
    """Coordinador de reposición y reconciliación masiva de anuncios P2P."""

    def __init__(self, manager: "AdsManager"):
        self.manager = manager

    async def ensure_ads_for_all_assets(
        self,
        method_groups: dict[int, list[str]],
        pay_id_map: dict[str, int],
        spot_prices: dict[str, float],
        usdt_benchmark: float = 1580.0,
    ) -> list[MyAd]:
        """Garantiza la existencia y correcta configuración de los 42 anuncios."""
        await self.reconcile_all_ads(
            method_groups=method_groups,
            pay_id_map=pay_id_map,
            spot_prices=spot_prices,
            usdt_benchmark=usdt_benchmark,
            set_online=False,
        )
        return self.manager.db.get_my_ads()

    async def reconcile_all_ads(
        self,
        method_groups: dict[int, list[str]],
        pay_id_map: dict[str, int],
        spot_prices: dict[str, float],
        usdt_benchmark: float = 1580.0,
        set_online: bool = False,
        create_missing: bool = True,
        config: Optional[BotConfig] = None,
    ) -> dict:
        """
        Escaneo y reconciliación profunda de anuncios de COMPRA (14 activos x 3 grupos).
        Verifica métodos de pago, recicla sobrantes, crea faltantes y cierra excedentes.
        """
        logger.info("Iniciando reconciliación y escaneo completo de anuncios (14 activos x 3 anuncios)...")
        all_ads = await self.manager.sync_my_ads()
        await self.manager.assign_groups(all_ads, method_groups)

        stats = {
            "total_assets": len(P2P_ASSETS_ARS),
            "verified": 0, "updated": 0, "created": 0,
            "closed_duplicates": 0, "errors": 0, "total_active": 0,
        }

        ads_by_asset: dict[str, list[MyAd]] = {}
        for ad in all_ads:
            ads_by_asset.setdefault(ad.asset, []).append(ad)

        for idx, asset in enumerate(P2P_ASSETS_ARS, start=1):
            logger.info("📦 [%d/%d] Activo: %s — Verificando 3 grupos (G1, G2, G3)", idx, len(P2P_ASSETS_ARS), asset)
            defaults = ASSET_DEFAULTS.get(asset, {"init_amount": 100.0, "min_trans": 10000.0, "max_trans": 500000.0})

            if asset in STABLECOINS:
                base_price = usdt_benchmark
            else:
                spot = spot_prices.get(asset, 0.0)
                if spot <= 0:
                    logger.warning("  ⚠️ Sin precio Spot para %s. Omitiendo reconciliación.", asset)
                    continue
                alt_margin = usdt_benchmark * ALTCOIN_MIN_MARGIN_PCT
                base_price = round(spot * max(usdt_benchmark - alt_margin, 100.0), 2)

            asset_ads = ads_by_asset.get(asset, [])
            group_to_ad: dict[int, MyAd] = {}
            extra_ads, failed_recycle_ads = [], []

            for ad in asset_ads:
                if ad.ad_group in (1, 2, 3) and ad.ad_group not in group_to_ad:
                    group_to_ad[ad.ad_group] = ad
                else:
                    extra_ads.append(ad)

            for group_num in (1, 2, 3):
                expected_methods = method_groups.get(group_num, [])[:5]
                expected_trade_methods = [
                    {"identifier": m, "payId": pay_id_map[m]}
                    for m in expected_methods if m in pay_id_map
                ]
                if not expected_trade_methods:
                    logger.warning("  • Grupo %d: ⚠️ Sin métodos configurados para %s", group_num, asset)
                    continue

                ad = group_to_ad.get(group_num)
                if ad:
                    if set(ad.payment_methods) != set(expected_methods):
                        logger.info("  • Grupo %d: 🔄 Actualizando métodos para %s (%s)...", group_num, asset, ad.adv_no)
                        try:
                            res = await self.manager.client.update_ad(
                                adv_no=ad.adv_no, update_mode="normal", price=ad.current_price,
                                initAmount=ad.init_amount, minSingleTransAmount=ad.min_trans_amount,
                                maxSingleTransAmount=ad.max_trans_amount, tradeMethods=expected_trade_methods,
                            )
                            if res.get("data", False) or res.get("success", False):
                                ad.payment_methods = [m["identifier"] for m in expected_trade_methods]
                                self.manager.db.save_my_ad(ad)
                                stats["updated"] += 1
                                logger.info("  • Grupo %d: ✅ Anuncio %s actualizado", group_num, ad.adv_no)
                            await asyncio.sleep(0.5)
                        except Exception as e:
                            logger.error("  • Grupo %d: ❌ Error actualizando %s: %s", group_num, ad.adv_no, e)
                            stats["errors"] += 1
                    else:
                        logger.info("  • Grupo %d: ✅ Anuncio existente OK: %s (%s)", group_num, ad.adv_no, asset)
                    stats["verified"] += 1

                elif extra_ads:
                    price, init_u, min_t, max_t = compute_buy_ad_parameters(asset, group_num, base_price, defaults)
                    if max_t < min_t:
                        logger.warning("  • Grupo %d: ⏭️ Capacidad insuficiente para reasignar %s G%d. Saltando.", group_num, asset, group_num)
                        continue
                    spare = extra_ads[0]
                    logger.info("  • Grupo %d: ♻️ Reasignando anuncio sobrante %s a %s G%d...", group_num, spare.adv_no, asset, group_num)
                    try:
                        await self.manager.client.update_ad(
                            adv_no=spare.adv_no, update_mode="normal", price=price, initAmount=init_u,
                            minSingleTransAmount=min_t, maxSingleTransAmount=max_t, tradeMethods=expected_trade_methods,
                        )
                        extra_ads.pop(0)
                        spare.ad_group, spare.current_price, spare.init_amount = group_num, price, init_u
                        spare.min_trans_amount, spare.max_trans_amount = min_t, max_t
                        spare.payment_methods = [m["identifier"] for m in expected_trade_methods]
                        self.manager.db.save_my_ad(spare)
                        group_to_ad[group_num] = spare
                        stats["updated"] += 1
                        stats["verified"] += 1
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        failed_recycle_ads.append(extra_ads.pop(0))
                        logger.error("  • Grupo %d: ❌ Error reasignando anuncio %s: %s", group_num, spare.adv_no, e)
                        stats["errors"] += 1

                else:
                    if not create_missing or self.manager.is_83714_active:
                        logger.debug("  • Grupo %d: ℹ️ No existe anuncio para %s G%d (modo pasivo / 83714)", group_num, asset, group_num)
                        continue
                    price, init_u, min_t, max_t = compute_buy_ad_parameters(asset, group_num, base_price, defaults)
                    if max_t < min_t:
                        logger.warning("  • Grupo %d: ⏭️ Capacidad insuficiente para %s G%d. Saltando creación.", group_num, asset, group_num)
                        continue

                    logger.info("  • Grupo %d: ➕ Creando nuevo anuncio para %s ($%.2f)...", group_num, asset, price)
                    adv_no = await self.manager.lifecycle.create_buy_ad(
                        asset=asset, price=price, init_amount=init_u, min_trans_amount=min_t,
                        max_trans_amount=max_t, trade_methods=expected_trade_methods,
                        auto_reply_msg=DEFAULT_BUY_AUTO_REPLY, remarks=DEFAULT_BUY_REMARKS, online_now=False,
                    )
                    if adv_no:
                        new_ad = MyAd(
                            adv_no=adv_no, asset=asset, ad_group=group_num, current_price=price,
                            payment_methods=[m["identifier"] for m in expected_trade_methods],
                            status=AD_STATUS_OFFLINE, init_amount=init_u, min_trans_amount=min_t, max_trans_amount=max_t,
                        )
                        self.manager.db.save_my_ad(new_ad)
                        group_to_ad[group_num] = new_ad
                        stats["created"] += 1
                        stats["verified"] += 1
                    else:
                        stats["errors"] += 1
                        if getattr(self.manager, "_last_83714_error", False):
                            logger.warning("🛑 Circuit breaker 83714 activado: abortando creaciones restantes.")
                            continue
                    await asyncio.sleep(AD_CREATION_COOLDOWN_SECONDS)

            for redundant_ad in extra_ads + failed_recycle_ads:
                logger.warning("  • Limpieza: Cerrando anuncio duplicado %s de %s...", redundant_ad.adv_no, asset)
                try:
                    await self.manager.client.close_ad(redundant_ad.adv_no)
                    self.manager.db.update_ad_status(redundant_ad.adv_no, AD_STATUS_CLOSED)
                    stats["closed_duplicates"] += 1
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error("  • Limpieza: Error cerrando anuncio excedente %s: %s", redundant_ad.adv_no, e)

        refreshed_ads = await self.manager.sync_my_ads()
        await self.manager.assign_groups(refreshed_ads, method_groups)

        if set_online:
            count = await self.manager.lifecycle.resume_all(config=config)
            stats["total_active"] = count
            logger.info("▶️ Reconciliación completada: %d anuncios puestos ONLINE", count)
        else:
            stats["total_active"] = sum(1 for a in refreshed_ads if a.status == AD_STATUS_ONLINE)

        logger.info("Reconciliación finalizada: %s", stats)
        return stats

    async def reconcile_sell_ads(
        self,
        pay_id_map: dict[str, int],
        benchmarks: Optional[dict] = None,
        available_crypto_stock: float = 350.0,
        set_online: bool = False,
    ) -> dict:
        """Reconcilia y recarga en caliente los 3 clusters de anuncios de VENTA USDT."""
        stats = {"verified": 0, "created": 0, "updated": 0, "errors": 0, "clusters": {}}
        existing_sell_ads = await self.manager.sync_my_sell_ads()
        cluster_to_ad = {a.ad_group: a for a in existing_sell_ads if a.ad_group in (1, 2, 3)}

        for cfg in SELL_CLUSTERS_CONFIG:
            c_id = cfg["id"]
            expected_trade_methods = [
                {"identifier": m, "payId": pay_id_map[m]}
                for m in cfg["methods"] if m in pay_id_map
            ][:5]

            ad = cluster_to_ad.get(c_id)
            surplus_val = float(getattr(ad, "surplus_amount", 0.0) or 0.0) if ad else 0.0
            price_ref = float(ad.current_price or 1600.0) if ad else 1600.0
            floor_ars = SELL_GROUP_FLOORS_ARS.get(c_id, 15000.0)
            ad_min_trans = float(getattr(ad, "min_trans_amount", 0.0) or floor_ars) if ad else floor_ars
            avail_floor = math.floor(float(available_crypto_stock) * 100.0) / 100.0

            is_under = ad is not None and (surplus_val < 10.0 or (surplus_val * price_ref < ad_min_trans))
            is_low = ad is not None and (surplus_val < avail_floor - 5.0)
            is_high = ad is not None and (surplus_val > avail_floor + 2.0)

            if ad is not None and avail_floor >= 10.0 and (is_under or is_low or is_high):
                executed = max(float(ad.init_amount or 0.0) - float(ad.surplus_amount or 0.0), 0.0)
                target_init = round(executed + avail_floor, 2)
                min_f, max_f = SELL_GROUP_LIMIT_FACTORS.get(c_id, (0.50, 1.00))
                min_trans, max_trans = compute_sell_trans_limits(avail_floor * price_ref, floor_ars, min_f, max_f)
                logger.info("🔄 Sincronizando stock venta G%d (%s): initAmount -> %.2f USDT", c_id, ad.adv_no, target_init)
                try:
                    ok = await self.manager.mutator.update_sell_ad_params(
                        adv_no=ad.adv_no, init_amount=target_init, surplus_amount=avail_floor,
                        min_trans_amount=min_trans, max_trans_amount=max_trans,
                    )
                    if ok:
                        ad.init_amount, ad.surplus_amount = target_init, avail_floor
                        ad.min_trans_amount, ad.max_trans_amount = min_trans, max_trans
                        self.manager.db.save_my_sell_ad(ad)
                        stats["updated"] += 1
                except Exception as e_up:
                    logger.error("Error recargando anuncio de venta %s: %s", ad.adv_no, e_up)

            if ad:
                stats["verified"] += 1
                stats["clusters"][c_id] = {"adv_no": ad.adv_no, "price": ad.current_price, "status": ad.status, "created": False}
            elif available_crypto_stock >= 100.0 and expected_trade_methods:
                min_f, max_f = SELL_GROUP_LIMIT_FACTORS.get(c_id, (0.45, 0.99))
                approx_price = 1630.0
                if not benchmarks and self.manager.db:
                    benchmarks = self.manager.db.get_latest_benchmarks()
                if benchmarks:
                    bm_vals = [float(getattr(b, "avg_top_n_price", 0.0) or 0.0) for b in benchmarks.values() if getattr(b, "avg_top_n_price", 0.0) > 0]
                    if bm_vals:
                        approx_price = sum(bm_vals) / len(bm_vals)

                cluster_sell_step = max(0.35, float(SELL_AD_PRICE_DIFF_ARS))
                cluster_price = round(approx_price + (c_id - 1) * cluster_sell_step, 2)
                init_u = avail_floor
                min_trans, max_trans = compute_sell_trans_limits(init_u * cluster_price, floor_ars, min_f, max_f)

                new_adv_no = await self.manager.lifecycle.create_sell_ad(
                    price=cluster_price, init_amount=init_u, min_trans_amount=min_trans,
                    max_trans_amount=max_trans, trade_methods=expected_trade_methods, online_now=False,
                )
                if new_adv_no:
                    stats["created"] += 1
                    stats["clusters"][c_id] = {"adv_no": new_adv_no, "price": cluster_price, "status": 3, "created": True}
                else:
                    stats["errors"] += 1
                await asyncio.sleep(AD_CREATION_COOLDOWN_SECONDS)
            else:
                if available_crypto_stock < 100.0:
                    stats.update({"low_balance": True, "available_stock": available_crypto_stock, "min_required": 100.0})
                    logger.info("Cluster %d de venta no creado: saldo (%.2f USDT) < 100.0 USDT.", c_id, available_crypto_stock)

        await self.manager.sync_my_sell_ads()
        return stats
