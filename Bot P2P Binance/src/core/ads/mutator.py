"""
Módulo de mutación y actualización de parámetros de anuncios P2P en Binance.
Actualiza precios, márgenes, límites mínimos y máximos, y montos en línea y base de datos.
"""
import logging
import math
import time
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.ads.manager import AdsManager

logger = logging.getLogger(__name__)


class AdMutator:
    """Manejador de mutaciones de anuncios de COMPRA y VENTA."""

    def __init__(self, manager: "AdsManager"):
        self.manager = manager

    async def update_ad_params(
        self,
        adv_no: str,
        price: Optional[float] = None,
        init_amount: Optional[float] = None,
        min_trans_amount: Optional[float] = None,
        max_trans_amount: Optional[float] = None,
        surplus_amount: Optional[float] = None,
    ) -> bool:
        """
        Actualiza precio, cantidad y/o límites de un anuncio de compra de forma unificada y atómica.
        Funciona tanto si el anuncio está ONLINE como OFFLINE en Binance.
        """
        kwargs = {}
        if price is not None:
            kwargs["price"] = price
        if init_amount is not None:
            kwargs["initAmount"] = init_amount
        if min_trans_amount is not None:
            kwargs["minSingleTransAmount"] = min_trans_amount
        if max_trans_amount is not None:
            kwargs["maxSingleTransAmount"] = max_trans_amount

        # Coherencia atómica: si se envían ambos límites, asegurar min <= max
        if "minSingleTransAmount" in kwargs and "maxSingleTransAmount" in kwargs:
            if kwargs["minSingleTransAmount"] > kwargs["maxSingleTransAmount"]:
                kwargs["minSingleTransAmount"] = kwargs["maxSingleTransAmount"]
                min_trans_amount = kwargs["minSingleTransAmount"]

        if not kwargs:
            return True

        try:
            result = await self.manager.client.update_ad(
                adv_no=adv_no,
                update_mode="quickedit",
                **kwargs,
            )

            success = result.get("data", False) or result.get("success", False)
            if success:
                self.manager.db.update_ad_params_db(
                    adv_no=adv_no,
                    price=price,
                    init_amount=init_amount,
                    min_trans_amount=min_trans_amount,
                    max_trans_amount=max_trans_amount,
                    surplus_amount=surplus_amount,
                )
                logger.info("✅ Anuncio %s actualizado en Binance: %s", adv_no, kwargs)
                return True
            else:
                logger.warning(
                    "⚠️ Update sin éxito para %s: %s (kwargs intentados: %s)",
                    adv_no, result, kwargs,
                )
                return False

        except Exception as e:
            if "83714" in str(e):
                self.manager._last_83714_ts = time.time()
                self.manager._last_83714_error = True
                logger.error(
                    "🚫 Bloqueo 83714 detectado en update_ad_params: %s. Activando circuit breaker general.",
                    e,
                )
            logger.error(
                "❌ Error actualizando parámetros de %s: %s (kwargs intentados: %s)",
                adv_no, e, kwargs,
            )
            return False

    async def update_price(self, adv_no: str, new_price: float) -> bool:
        """
        Actualiza el precio de un anuncio via quickedit.
        Retorna True si se actualizó correctamente.
        """
        return await self.update_ad_params(adv_no=adv_no, price=new_price)

    async def update_ad_limits(
        self,
        adv_no: str,
        min_trans_amount: Optional[float] = None,
        max_trans_amount: Optional[float] = None,
    ) -> bool:
        """Actualiza límites de transacción del anuncio (Edge Case 2)."""
        return await self.update_ad_params(
            adv_no=adv_no,
            min_trans_amount=min_trans_amount,
            max_trans_amount=max_trans_amount,
        )

    async def update_sell_ad_params(
        self,
        adv_no: str,
        price: Optional[float] = None,
        init_amount: Optional[float] = None,
        min_trans_amount: Optional[float] = None,
        max_trans_amount: Optional[float] = None,
        surplus_amount: Optional[float] = None,
    ) -> bool:
        """Actualiza parámetros de un anuncio de venta en Binance y en SQLite."""
        kwargs = {}
        if price is not None:
            kwargs["price"] = price
        if init_amount is not None:
            kwargs["initAmount"] = math.floor(float(init_amount) * 100.0) / 100.0
        if min_trans_amount is not None:
            kwargs["minSingleTransAmount"] = min_trans_amount
        if max_trans_amount is not None:
            kwargs["maxSingleTransAmount"] = max_trans_amount

        if "minSingleTransAmount" in kwargs and "maxSingleTransAmount" in kwargs:
            if kwargs["minSingleTransAmount"] > kwargs["maxSingleTransAmount"]:
                kwargs["minSingleTransAmount"] = kwargs["maxSingleTransAmount"]

        if not kwargs:
            return True

        try:
            result = await self.manager.client.update_ad(
                adv_no=adv_no,
                update_mode="quickedit",
                **kwargs,
            )
            success = result.get("data", False) or result.get("success", False)
            if success:
                sell_ads = self.manager.db.get_my_sell_ads()
                ad = next((a for a in sell_ads if a.adv_no == adv_no), None)
                if ad:
                    if price is not None:
                        ad.current_price = price
                    if init_amount is not None:
                        ad.init_amount = init_amount
                    if surplus_amount is not None:
                        ad.surplus_amount = surplus_amount
                    if min_trans_amount is not None:
                        ad.min_trans_amount = min_trans_amount
                    if max_trans_amount is not None:
                        ad.max_trans_amount = max_trans_amount
                    ad.last_repositioned = datetime.now()
                    self.manager.db.save_my_sell_ad(ad)
                logger.info("✅ Anuncio de venta %s actualizado en Binance: %s", adv_no, kwargs)
                return True
            else:
                logger.warning("Update de venta sin éxito para %s: %s", adv_no, result)
                return False
        except Exception as e:
            logger.error("Error actualizando anuncio de venta %s: %s", adv_no, e)
            return False
