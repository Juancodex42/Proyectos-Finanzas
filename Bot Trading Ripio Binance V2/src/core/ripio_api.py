"""
Cliente asíncrono profesional para Ripio Trade API v4 con autenticación HMAC-SHA256.
Implementa rate limiting preventivo, connection pooling y límite de reintentos HTTP 429.
Referencia de diseño: docs/ARQUITECTURA.md
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import aiohttp

logger = logging.getLogger(__name__)


class ProfessionalRipioAPI:
    """
    Cliente profesional para Ripio Trade API v4 con:
    - Rate limiting preventivo por ventana deslizante (public: 100/min, private: 50/min)
    - Autenticación HMAC-SHA256 incluyendo query parameters en la ruta firmada
    - Reintentos acotados (max_retries=3) ante respuestas HTTP 429
    """

    BASE_URL = "https://api.ripiotrade.co"

    RATE_LIMITS = {
        "public": {"requests": 100, "window": 60},
        "private": {"requests": 50, "window": 60},
    }

    def __init__(self, api_token: str, secret_key: str, retry_delay: float = 60.0):
        self.api_token = api_token
        self.secret_key = secret_key
        self.retry_delay = retry_delay

        self.session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None

        self._public_requests = deque(maxlen=100)
        self._private_requests = deque(maxlen=50)
        self._rate_limit_lock = asyncio.Lock()

        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "rate_limit_hits": 0,
            "last_error": None,
        }

    async def init_session(self):
        """Inicializa sesión HTTP con connection pooling."""
        if self.session is None or self.session.closed:
            self._connector = aiohttp.TCPConnector(
                limit=10,
                limit_per_host=5,
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
            )
            self.session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"User-Agent": "RipioBot/2.0"},
            )
            logger.info("✅ Ripio API session initialized")

    async def close_session(self):
        """Cierra sesión HTTP y libera recursos de red."""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("🔒 Ripio API session closed")

    def create_signature(
        self, timestamp: str, method: str, path: str, body: str = ""
    ) -> str:
        """Crea firma HMAC-SHA256 sobre timestamp + method + path (con query) + body."""
        try:
            message = f"{timestamp}{method.upper()}{path}{body}"
            signature = hmac.new(
                self.secret_key.encode("utf-8"),
                message.encode("utf-8"),
                hashlib.sha256,
            ).digest()
            return base64.b64encode(signature).decode("utf-8")
        except Exception as e:
            logger.error(f"❌ Error creando firma: {e}")
            return ""

    def get_headers(self, method: str, path: str, body: str = "") -> dict:
        """Genera cabeceras HTTP autenticadas para endpoints privados."""
        timestamp = str(int(time.time() * 1000))
        signature = self.create_signature(timestamp, method, path, body)
        return {
            "Authorization": self.api_token,
            "Timestamp": timestamp,
            "Signature": signature,
            "Content-Type": "application/json",
        }

    async def _wait_for_rate_limit(self, endpoint_type: str):
        """Espera preventivamente si la cola de peticiones alcanza el límite por minuto."""
        async with self._rate_limit_lock:
            now = datetime.now()
            if endpoint_type == "public":
                requests_queue = self._public_requests
                limit = self.RATE_LIMITS["public"]
            else:
                requests_queue = self._private_requests
                limit = self.RATE_LIMITS["private"]

            window_start = now - timedelta(seconds=limit["window"])
            while requests_queue and requests_queue[0] < window_start:
                requests_queue.popleft()

            if len(requests_queue) >= limit["requests"]:
                oldest_request = requests_queue[0]
                wait_until = oldest_request + timedelta(seconds=limit["window"])
                wait_seconds = (wait_until - now).total_seconds()
                if wait_seconds > 0:
                    self.stats["rate_limit_hits"] += 1
                    logger.warning(
                        f"⏳ Rate limit alcanzado ({endpoint_type}). Esperando {wait_seconds:.1f}s..."
                    )
                    await asyncio.sleep(wait_seconds)

            requests_queue.append(now)
            self.stats["total_requests"] += 1

    async def get_ticker(
        self, pair: str, max_retries: int = 3, _retry_count: int = 0
    ) -> Optional[Dict]:
        """Obtiene ticker (bid/ask/last) de un par con límite de reintentos ante HTTP 429."""
        await self._wait_for_rate_limit("public")
        path = f"/v4/public/tickers/{pair}"

        try:
            async with self.session.get(f"{self.BASE_URL}{path}") as resp:
                if resp.status == 200:
                    js = await resp.json()
                    data = js.get("data", {})
                    if data.get("bid") and data.get("ask"):
                        self.stats["successful_requests"] += 1
                        return {
                            "bid": float(data["bid"]),
                            "ask": float(data["ask"]),
                            "last": float(data.get("last", data["ask"])),
                            "timestamp": datetime.now(),
                        }
                elif resp.status == 429:
                    self.stats["rate_limit_hits"] += 1
                    if _retry_count < max_retries:
                        logger.warning(
                            f"⚠️ 429 Rate Limit en ticker {pair} "
                            f"(reintento {_retry_count + 1}/{max_retries})..."
                        )
                        await asyncio.sleep(self.retry_delay)
                        return await self.get_ticker(
                            pair, max_retries=max_retries, _retry_count=_retry_count + 1
                        )
                    logger.error(f"❌ Max retries ({max_retries}) alcanzado en ticker {pair} (429)")
                    self.stats["failed_requests"] += 1
                else:
                    text = await resp.text()
                    logger.error(f"❌ Error ticker {pair} ({resp.status}): {text[:200]}")
                    self.stats["failed_requests"] += 1

        except Exception as e:
            logger.error(f"❌ Exception ticker {pair}: {e}")
            self.stats["failed_requests"] += 1
            self.stats["last_error"] = str(e)

        return None

    async def get_orderbook(
        self, pair: str, depth: int = 10, max_retries: int = 3, _retry_count: int = 0
    ) -> Optional[Dict]:
        """Obtiene el libro de órdenes (Level-2) de un par con límite de reintentos 429."""
        await self._wait_for_rate_limit("public")
        path = "/v4/public/orders/level-2"
        params = {"pair": pair, "limit": depth}

        try:
            async with self.session.get(f"{self.BASE_URL}{path}", params=params) as resp:
                if resp.status == 200:
                    js = await resp.json()
                    data = js.get("data", {})
                    bids_raw = data.get("bids", [])
                    asks_raw = data.get("asks", [])
                    if not bids_raw and not asks_raw:
                        return None

                    bids = [
                        [float(b.get("price", 0)), float(b.get("amount", 0))]
                        for b in bids_raw[:depth]
                    ]
                    asks = [
                        [float(a.get("price", 0)), float(a.get("amount", 0))]
                        for a in asks_raw[:depth]
                    ]
                    self.stats["successful_requests"] += 1
                    return {
                        "bids": bids,
                        "asks": asks,
                        "timestamp": datetime.now(),
                        "pair": pair,
                    }
                elif resp.status == 429:
                    self.stats["rate_limit_hits"] += 1
                    if _retry_count < max_retries:
                        await asyncio.sleep(self.retry_delay)
                        return await self.get_orderbook(
                            pair, depth=depth, max_retries=max_retries, _retry_count=_retry_count + 1
                        )
                    self.stats["failed_requests"] += 1
                else:
                    text = await resp.text()
                    logger.error(f"❌ Error orderbook {pair} ({resp.status}): {text[:200]}")
                    self.stats["failed_requests"] += 1

        except Exception as e:
            logger.error(f"❌ Exception orderbook {pair}: {e}")
            self.stats["failed_requests"] += 1
            self.stats["last_error"] = str(e)

        return None

    async def get_balance(
        self, max_retries: int = 3, _retry_count: int = 0
    ) -> Optional[Dict]:
        """Obtiene balances disponibles y bloqueados por moneda."""
        await self._wait_for_rate_limit("private")
        path = "/v4/user/balances"
        headers = self.get_headers("GET", path)

        try:
            async with self.session.get(f"{self.BASE_URL}{path}", headers=headers) as resp:
                if resp.status == 200:
                    js = await resp.json()
                    balances = {}
                    for item in js.get("data", []):
                        currency = item.get("currency_code")
                        available = float(item.get("available_amount", 0))
                        locked = float(item.get("locked_amount", 0))
                        balances[currency] = {
                            "available": available,
                            "locked": locked,
                            "total": available + locked,
                        }
                    self.stats["successful_requests"] += 1
                    return balances
                elif resp.status == 429:
                    self.stats["rate_limit_hits"] += 1
                    if _retry_count < max_retries:
                        await asyncio.sleep(self.retry_delay)
                        return await self.get_balance(
                            max_retries=max_retries, _retry_count=_retry_count + 1
                        )
                    self.stats["failed_requests"] += 1
                else:
                    text = await resp.text()
                    logger.error(f"❌ Error balance ({resp.status}): {text[:200]}")
                    self.stats["failed_requests"] += 1

        except Exception as e:
            logger.error(f"❌ Exception balance: {e}")
            self.stats["failed_requests"] += 1
            self.stats["last_error"] = str(e)

        return None

    async def crear_orden(
        self, pair: str, side: str, quantity: float, price: float
    ) -> Optional[str]:
        """Crea una orden limit validando parámetros previos."""
        if quantity <= 0 or price <= 0 or side.lower() not in ("buy", "sell"):
            logger.error(f"❌ Parámetros de orden inválidos: {side} {quantity} @ {price}")
            return None

        await self._wait_for_rate_limit("private")
        path = "/v4/orders"
        body_data = {
            "pair": pair,
            "side": side.upper(),
            "type": "limit",
            "amount": quantity,
            "price": price,
        }
        body = json.dumps(body_data)

        try:
            headers = self.get_headers("POST", path, body=body)
            async with self.session.post(
                f"{self.BASE_URL}{path}", headers=headers, data=body
            ) as resp:
                if resp.status in (200, 201):
                    js = await resp.json()
                    orden_id = js.get("data", {}).get("id")
                    self.stats["successful_requests"] += 1
                    return orden_id

                text = await resp.text()
                logger.error(f"❌ Error creando orden ({resp.status}): {text[:300]}")
                self.stats["failed_requests"] += 1
                try:
                    error_json = json.loads(text)
                    logger.error(f"Detalle: {error_json.get('message', 'Unknown error')}")
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"❌ Exception creando orden: {e}")
            self.stats["failed_requests"] += 1
            self.stats["last_error"] = str(e)

        return None

    async def cancelar_orden(self, orden_id: str) -> bool:
        """Cancela una orden activa por su ID."""
        await self._wait_for_rate_limit("private")
        path = "/v4/orders"
        body = json.dumps({"id": orden_id})

        try:
            headers = self.get_headers("DELETE", path, body=body)
            async with self.session.delete(
                f"{self.BASE_URL}{path}", headers=headers, data=body
            ) as resp:
                if resp.status in (200, 204):
                    self.stats["successful_requests"] += 1
                    return True
                self.stats["failed_requests"] += 1
        except Exception as e:
            logger.error(f"❌ Exception cancelando {orden_id}: {e}")
            self.stats["failed_requests"] += 1
            self.stats["last_error"] = str(e)

        return False

    async def get_orden_status(self, orden_id: str) -> Optional[Dict]:
        """Obtiene el estado de ejecución de una orden específica."""
        await self._wait_for_rate_limit("private")
        path = f"/v4/orders/{orden_id}"

        try:
            headers = self.get_headers("GET", path)
            async with self.session.get(f"{self.BASE_URL}{path}", headers=headers) as resp:
                if resp.status == 200:
                    js = await resp.json()
                    data = js.get("data", {})
                    self.stats["successful_requests"] += 1
                    return {
                        "id": data.get("id"),
                        "status": data.get("status"),
                        "price": float(data.get("price", 0)),
                        "quantity": float(data.get("requested_amount", 0)),
                        "filled_quantity": float(data.get("executed_amount", 0)),
                        "side": data.get("side"),
                        "pair": data.get("pair"),
                    }
                self.stats["failed_requests"] += 1
        except Exception as e:
            logger.error(f"❌ Exception status {orden_id}: {e}")
            self.stats["failed_requests"] += 1
            self.stats["last_error"] = str(e)

        return None

    async def get_ordenes_abiertas(self, pair: Optional[str] = None) -> List[Dict]:
        """Obtiene órdenes abiertas incluyendo los query params en la firma HMAC."""
        await self._wait_for_rate_limit("private")
        path = f"/v4/orders/open?pair={pair}" if pair else "/v4/orders/open"

        try:
            headers = self.get_headers("GET", path)
            url = f"{self.BASE_URL}{path}"
            async with self.session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    js = await resp.json()
                    self.stats["successful_requests"] += 1
                    return js.get("data", {}).get("orders", [])
                self.stats["failed_requests"] += 1
        except Exception as e:
            logger.error(f"❌ Exception órdenes abiertas: {e}")
            self.stats["failed_requests"] += 1
            self.stats["last_error"] = str(e)

        return []

    async def health_check(self) -> bool:
        """Verifica conectividad básica consultando el ticker público USDT_ARS."""
        try:
            ticker = await self.get_ticker("USDT_ARS")
            return ticker is not None
        except Exception:
            return False

    def get_api_status(self) -> Dict:
        """Retorna métricas de uso y disponibilidad del rate limiter."""
        total = self.stats["total_requests"]
        success_rate = self.stats["successful_requests"] / total if total > 0 else 0.0
        return {
            **self.stats,
            "success_rate": success_rate,
            "public_requests_last_minute": len(self._public_requests),
            "private_requests_last_minute": len(self._private_requests),
            "public_available": self.RATE_LIMITS["public"]["requests"] - len(self._public_requests),
            "private_available": self.RATE_LIMITS["private"]["requests"] - len(self._private_requests),
        }
