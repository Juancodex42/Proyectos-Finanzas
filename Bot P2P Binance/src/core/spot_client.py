"""
Cliente para precios spot de Binance (API pública, sin autenticación).
"""
import asyncio
import logging
import socket
from typing import Optional

import aiohttp

from config.settings import BINANCE_API_BASE

logger = logging.getLogger(__name__)


class SpotClient:
    """Obtiene precios spot desde la API pública de Binance."""

    def __init__(self, base_url: str = BINANCE_API_BASE):
        self.base_url = base_url
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()
        self._consecutive_net_errors: int = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        if (
            self._session is None
            or (isinstance(self._session, aiohttp.ClientSession) and self._session.closed)
            or getattr(self._session, "closed", False) is True
        ):
            async with self._session_lock:
                if (
                    self._session is None
                    or (isinstance(self._session, aiohttp.ClientSession) and self._session.closed)
                    or getattr(self._session, "closed", False) is True
                ):
                    timeout = aiohttp.ClientTimeout(total=10, connect=3)
                    connector = aiohttp.TCPConnector(
                        family=socket.AF_INET,
                        ttl_dns_cache=60,
                        enable_cleanup_closed=True,
                    )
                    self._session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self._session

    async def _reset_session(self):
        """Cierra y descarta la sesión HTTP actual si quedó obsoleta tras un corte de red/DNS."""
        async with self._session_lock:
            self._consecutive_net_errors = 0
            if self._session is not None and isinstance(self._session, aiohttp.ClientSession):
                old_session = self._session
                self._session = None
                if not old_session.closed:
                    try:
                        await old_session.close()
                    except Exception:
                        pass
                logger.info("🔄 Sesión HTTP de SpotClient reiniciada para restablecer conexiones limpias.")

    async def get_all_prices(self) -> dict[str, float]:
        """
        Obtiene todos los precios spot.
        GET /api/v3/ticker/price

        Returns:
            Dict con symbol→price, ej: {"BTCUSDT": 100000.0, "ETHUSDT": 3500.0}
        """
        session = await self._get_session()
        url = f"{self.base_url}/ticker/price"

        try:
            async with session.get(url) as response:
                self._consecutive_net_errors = 0
                if response.status != 200:
                    logger.warning("Error consultando precios spot (status %d)", response.status)
                    return {}
                data = await response.json()
        except Exception as e:
            self._consecutive_net_errors += 1
            logger.warning("Excepción consultando precios spot completos: %s", e)
            if self._consecutive_net_errors >= 3:
                await self._reset_session()
            return {}

        if not isinstance(data, list):
            logger.warning("Respuesta inesperada al consultar precios spot: %s", data)
            return {}

        prices = {}
        for item in data:
            if isinstance(item, dict) and "symbol" in item and "price" in item:
                try:
                    prices[item["symbol"]] = float(item["price"])
                except (ValueError, TypeError):
                    continue

        return prices

    async def get_price(self, symbol: str) -> float:
        """
        Obtiene el precio spot de un par específico.

        Args:
            symbol: Par de trading, ej: "BTCUSDT"

        Returns:
            Precio como float
        """
        session = await self._get_session()
        url = f"{self.base_url}/ticker/price"

        try:
            async with session.get(url, params={"symbol": symbol}) as response:
                self._consecutive_net_errors = 0
                if response.status != 200:
                    raise ValueError(f"Error spot para {symbol} (status {response.status})")
                data = await response.json()
        except Exception as e:
            self._consecutive_net_errors += 1
            logger.warning("Error consultando precio spot para %s: %s", symbol, e)
            if self._consecutive_net_errors >= 3:
                await self._reset_session()
            raise

        if not isinstance(data, dict) or "price" not in data:
            raise ValueError(f"Respuesta inesperada para {symbol}: {data}")

        return float(data["price"])

    async def get_usdt_prices(self, assets: list[str]) -> dict[str, float]:
        """
        Obtiene precios en USDT para una lista de activos.

        Args:
            assets: Lista de activos, ej: ["BTC", "ETH", "SOL"]

        Returns:
            Dict con asset→price_usdt, ej: {"BTC": 100000.0, "ETH": 3500.0}
            Para stablecoins (USDT, USDC, etc.), retorna 1.0
        """
        from config.settings import STABLECOINS
        import json

        needed_symbols = [f"{a}USDT" for a in assets if a not in ("USDT", "U")]
        prices_map = {}
        if needed_symbols:
            session = await self._get_session()
            url = f"{self.base_url}/ticker/price"
            try:
                # Binance exige json compacto sin espacios en el query param symbols
                compact_symbols = json.dumps(needed_symbols, separators=(",", ":"))
                async with session.get(url, params={"symbols": compact_symbols}) as response:
                    self._consecutive_net_errors = 0
                    if response.status == 200:
                        data = await response.json()
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and "symbol" in item and "price" in item:
                                    try:
                                        prices_map[item["symbol"]] = float(item["price"])
                                    except (ValueError, TypeError):
                                        continue
                    else:
                        logger.debug("Respuesta %d en consulta spot filtrada, intentando fallback", response.status)
            except Exception as e:
                self._consecutive_net_errors += 1
                logger.debug("Fallo en consulta spot filtrada (%s), usando fallback global", e)
                if self._consecutive_net_errors >= 3:
                    await self._reset_session()

        # Fallback si falló la consulta filtrada
        if needed_symbols and not prices_map:
            try:
                prices_map = await self.get_all_prices()
            except Exception as e:
                logger.warning("Error en fallback global de precios spot: %s", e)
                prices_map = {}

        if needed_symbols and not prices_map:
            return {}

        result = {}
        for asset in assets:
            if asset in STABLECOINS:
                # Stablecoins ≈ 1 USDT
                if asset == "USDT":
                    result[asset] = 1.0
                else:
                    # Buscar par directo, ej USDCUSDT
                    symbol = f"{asset}USDT"
                    result[asset] = prices_map.get(symbol, 1.0)
            else:
                symbol = f"{asset}USDT"
                if symbol in prices_map:
                    result[asset] = prices_map[symbol]
                else:
                    logger.warning("No se encontró precio spot para %s", asset)

        return result

    async def get_24hr_volatilities(self, assets: list[str]) -> dict[str, float]:
        """
        Obtiene la volatilidad porcentual 24h para una lista de activos desde Binance Spot:
        V = (highPrice - lowPrice) / lowPrice.
        Para stablecoins (USDT, USDC, FDUSD, U), retorna 0.0.
        """
        from config.settings import STABLECOINS
        import json

        session = await self._get_session()
        url = f"{self.base_url}/ticker/24hr"
        needed_symbols = [f"{a}USDT" for a in assets if a not in STABLECOINS]

        volatilities: dict[str, float] = {}
        data = None
        try:
            if needed_symbols:
                compact_symbols = json.dumps(needed_symbols, separators=(",", ":"))
                async with session.get(url, params={"symbols": compact_symbols}) as response:
                    self._consecutive_net_errors = 0
                    if response.status == 200:
                        data = await response.json()
                    else:
                        logger.debug("Respuesta %d en 24hr tickers filtrados, intentando fallback global", response.status)
            if data is None:
                async with session.get(url) as response:
                    self._consecutive_net_errors = 0
                    if response.status != 200:
                        logger.warning("Error consultando 24hr tickers (status %d)", response.status)
                        return {a: (0.0 if a in STABLECOINS else 0.03) for a in assets}
                    data = await response.json()
        except Exception as e:
            self._consecutive_net_errors += 1
            logger.warning("Excepción consultando 24hr tickers: %s", e)
            if self._consecutive_net_errors >= 3:
                await self._reset_session()
            return {a: (0.0 if a in STABLECOINS else 0.03) for a in assets}

        if not isinstance(data, list):
            return {a: (0.0 if a in STABLECOINS else 0.03) for a in assets}

        ticker_map = {}
        for item in data:
            sym = item.get("symbol")
            if sym:
                try:
                    high = float(item.get("highPrice", 0))
                    low = float(item.get("lowPrice", 0))
                    if low > 0 and high >= low:
                        ticker_map[sym] = (high - low) / low
                except (ValueError, TypeError):
                    continue

        for asset in assets:
            if asset in STABLECOINS:
                volatilities[asset] = 0.0
            else:
                sym = f"{asset}USDT"
                volatilities[asset] = ticker_map.get(sym, 0.03)

        return volatilities

    async def close(self):
        """Cierra la sesión HTTP."""
        async with self._session_lock:
            if self._session and not self._session.closed:
                await self._session.close()
                self._session = None
