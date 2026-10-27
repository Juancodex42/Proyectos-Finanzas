"""
Cliente de consulta de precios para Fiwind (vía CriptoYa API pública).
Utilizado para la Estrategia de Rescate P2P -> Fiwind.
"""
import asyncio
import socket
import time
import logging
from typing import Optional, Tuple, Any
import aiohttp

from config.settings import CRIPTOYA_FIWIND_URL, FIWIND_CACHE_SECONDS

logger = logging.getLogger(__name__)


class FiwindClient:
    """Cliente HTTP asíncrono con caché para cotizaciones de Fiwind."""

    def __init__(
        self,
        url: str = CRIPTOYA_FIWIND_URL,
        cache_ttl: int = FIWIND_CACHE_SECONDS,
        max_stale_seconds: int = 300,
        db: Optional[Any] = None,
    ):
        self.url = url
        self.cache_ttl = cache_ttl
        self.max_stale_seconds = max_stale_seconds
        self.db = db
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()
        self._consecutive_net_errors: int = 0
        self._cached_bid: float = 0.0
        self._cached_ask: float = 0.0
        self._last_fetch_time: float = 0.0
        self._last_saved_quote_time: float = 0.0

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
        """Cierra y descarta la sesión HTTP si quedó obsoleta tras un corte de red/DNS."""
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

    async def get_quotes(self) -> Tuple[float, float]:
        """
        Retorna (bid, ask) de Fiwind para USDT/ARS.
        bid = lo que Fiwind te paga en ARS al venderle USDT.
        ask = lo que Fiwind cobra en ARS al comprarle USDT.
        """
        now = time.time()
        if self._cached_bid > 0 and (now - self._last_fetch_time) < self.cache_ttl:
            return self._cached_bid, self._cached_ask

        try:
            session = await self._get_session()
            async with session.get(self.url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                self._consecutive_net_errors = 0
                if response.status == 200:
                    data = await response.json()
                    bid = float(data.get("bid", 0.0))
                    ask = float(data.get("ask", 0.0))
                    if bid > 0 and ask > 0:
                        self._cached_bid = bid
                        self._cached_ask = ask
                        self._last_fetch_time = now
                        logger.debug("Fiwind cotización actualizada: bid=$%.2f, ask=$%.2f", bid, ask)
                        if (
                            self.db
                            and hasattr(self.db, "save_fiwind_quote")
                            and (now - self._last_saved_quote_time) >= 60.0
                        ):
                            try:
                                self.db.save_fiwind_quote(bid, ask)
                                self._last_saved_quote_time = now
                            except Exception as e_save:
                                logger.debug("Error guardando cotización Fiwind en DB: %s", e_save)
                        return bid, ask
                else:
                    logger.warning("Error consultando CriptoYa/Fiwind (status %d)", response.status)
        except Exception as e:
            self._consecutive_net_errors += 1
            logger.warning("Fallo al obtener cotización Fiwind: %s", e)
            if self._consecutive_net_errors >= 2:
                await self._reset_session()

        # Si falla pero hay caché previo reciente (<= max_stale_seconds), retornar lo último conocido
        if self._cached_bid > 0 and (now - self._last_fetch_time) <= self.max_stale_seconds:
            logger.info("Usando cotización en caché reciente de Fiwind (edad: %.1fs)", now - self._last_fetch_time)
            return self._cached_bid, self._cached_ask

        if self._cached_bid > 0:
            logger.error("Caché de Fiwind expirado (>%ds). Sin cotización válida.", self.max_stale_seconds)
        return 0.0, 0.0

    async def get_usdt_bid(self) -> float:
        """Retorna el precio al que Fiwind compra USDT en mano (ARS recibidos)."""
        bid, _ = await self.get_quotes()
        return bid

    async def close(self):
        """Cierra la sesión HTTP."""
        async with self._session_lock:
            if self._session and not self._session.closed:
                await self._session.close()
                self._session = None
