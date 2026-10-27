"""
Cliente asíncrono para endpoints públicos de Binance API v3.
Obtiene precios de referencia y orderbooks para arbitraje inter-exchange.
Referencia de diseño: docs/ARQUITECTURA.md
"""

import aiohttp
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class BinanceAPI:
    """
    Cliente simple para Binance API (solo endpoints públicos)
    Usado únicamente para precios de referencia
    """

    BASE_URL = "https://api.binance.com"

    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self.session = session
        self._own_session = session is None

    async def init_session(self):
        """Inicializa sesión si no fue provista"""
        if self._own_session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
            logger.info("✅ Binance API session initialized")

    async def close_session(self):
        """Cierra sesión si fue creada por esta clase"""
        if self._own_session and self.session and not self.session.closed:
            await self.session.close()
            logger.info("🔒 Binance API session closed")

    async def get_price(self, symbol: str) -> Optional[float]:
        """
        Obtiene precio ask de un símbolo

        Args:
            symbol: e.g. 'BTCUSDT', 'ETHUSDT', 'USDTARS'

        Returns:
            Precio ask (float) o None si falla
        """
        try:
            url = f"{self.BASE_URL}/api/v3/depth"
            params = {"symbol": symbol, "limit": 5}

            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("asks"):
                        return float(data["asks"][0][0])
                else:
                    text = await resp.text()
                    logger.error(f"❌ Error Binance {symbol} ({resp.status}): {text[:200]}")

        except Exception as e:
            logger.error(f"❌ Exception Binance {symbol}: {e}")

        return None

    async def get_ticker(self, symbol: str) -> Optional[dict]:
        """
        Obtiene ticker completo (bid/ask/last)

        Returns:
            {'bid': float, 'ask': float, 'last': float}
        """
        try:
            url = f"{self.BASE_URL}/api/v3/ticker/bookTicker"
            params = {"symbol": symbol}

            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        'bid': float(data['bidPrice']),
                        'ask': float(data['askPrice']),
                        'last': float(data['askPrice'])  # Approximation
                    }
                else:
                    logger.error(f"❌ Error Binance ticker {symbol} ({resp.status})")

        except Exception as e:
            logger.error(f"❌ Exception Binance ticker {symbol}: {e}")

        return None

    async def health_check(self) -> bool:
        """Verifica que Binance API responde"""
        try:
            price = await self.get_price('BTCUSDT')
            if price and price > 0:
                logger.info("✅ Binance API: Health check OK")
                return True
            else:
                logger.error("❌ Binance API: Health check FAILED")
                return False

        except Exception as e:
            logger.error(f"❌ Binance API: Health check EXCEPTION: {e}")
            return False
