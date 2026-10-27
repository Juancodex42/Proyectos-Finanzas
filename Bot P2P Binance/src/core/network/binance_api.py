"""
Cliente HTTP autenticado para Binance SAPI (C2C/P2P).
Implementa firma HMAC SHA256 según la documentación sapi-v7.4 y rate limiting modular.
"""
import asyncio
import hashlib
import hmac
import json
import logging
import random
import socket
import time
from typing import Optional
from urllib.parse import urlencode

import aiohttp

from config.settings import (
    BINANCE_API_KEY,
    BINANCE_SECRET_KEY,
    BINANCE_BASE_URL,
    CLIENT_TYPE,
    DEFAULT_BUY_REMARKS,
    DEFAULT_SELL_REMARKS,
    SELL_TAKER_ADDITIONAL_KYC_REQUIRED,
    SELL_BUYER_REG_DAYS_LIMIT,
    SELL_USER_ALL_TRADE_COUNT_MIN,
    SELL_BUYER_BTC_POSITION_LIMIT,
)
from core.network.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class BinanceClientError(Exception):
    """Error genérico del cliente Binance SAPI."""

    def __init__(self, status: int, code: str, message: str, retry_after: Optional[float] = None) -> None:
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after
        super().__init__(f"[{status}] {code}: {message}")


class BinanceApi:
    """
    Cliente HTTP asíncrono para Binance SAPI.
    Todas las requests firmadas usan HMAC SHA256 con recvWindow y sincronización RTT.
    """

    def __init__(
        self,
        api_key: str = BINANCE_API_KEY,
        secret_key: str = BINANCE_SECRET_KEY,
        base_url: str = BINANCE_BASE_URL,
        validate_keys: bool = False,
        rate_limiter: Optional[RateLimiter] = None,
    ) -> None:
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        if validate_keys:
            self.validate_credentials()
        self.rate_limiter = rate_limiter or RateLimiter()
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock: asyncio.Lock = asyncio.Lock()
        self._consecutive_net_errors: int = 0
        self._last_session_reset_ts: float = 0.0
        self._time_offset: int = 0
        self._last_time_sync: float = 0.0
        self._last_time_sync_attempt: float = 0.0
        self._time_sync_lock: asyncio.Lock = asyncio.Lock()

    @property
    def _rate_limit_remaining(self) -> int:
        return self.rate_limiter.rate_limit_remaining

    @_rate_limit_remaining.setter
    def _rate_limit_remaining(self, val: int) -> None:
        self.rate_limiter._rate_limit_remaining = val

    @property
    def _rate_limited_until(self) -> float:
        return self.rate_limiter.rate_limited_until

    @_rate_limited_until.setter
    def _rate_limited_until(self, val: float) -> None:
        self.rate_limiter._rate_limited_until = val

    @property
    def _ip_banned_until(self) -> float:
        return self.rate_limiter.ip_banned_until

    @_ip_banned_until.setter
    def _ip_banned_until(self, val: float) -> None:
        self.rate_limiter._ip_banned_until = val

    def validate_credentials(self) -> None:
        """Verifica que las credenciales de Binance no estén vacías."""
        if not self.api_key or not self.secret_key:
            raise ValueError("CRÍTICO: BINANCE_API_KEY y BINANCE_SECRET_KEY deben estar configuradas en .env")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Crea o reutiliza la sesión HTTP con conector IPv4 y limpieza de sockets."""
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
                    timeout = aiohttp.ClientTimeout(total=15, connect=5)
                    connector = aiohttp.TCPConnector(
                        family=socket.AF_INET,
                        ttl_dns_cache=60,
                        enable_cleanup_closed=True,
                    )
                    self._session = aiohttp.ClientSession(
                        connector=connector,
                        timeout=timeout,
                        headers={
                            "X-MBX-APIKEY": self.api_key,
                            "clientType": CLIENT_TYPE,
                            "Content-Type": "application/json",
                        },
                    )
        return self._session

    async def _reset_session(self) -> None:
        """Cierra y descarta la sesión HTTP actual si quedó obsoleta tras corte de red/DNS."""
        async with self._session_lock:
            self._consecutive_net_errors = 0
            now = time.time()
            if self._last_session_reset_ts > 0 and (now - self._last_session_reset_ts) < 10.0:
                return
            self._last_session_reset_ts = now
            if self._session is not None and isinstance(self._session, aiohttp.ClientSession):
                old_session = self._session
                self._session = None
                if not old_session.closed:
                    try:
                        await old_session.close()
                    except Exception:
                        pass
                logger.info("🔄 Sesión HTTP de Binance reiniciada para restablecer conexiones limpias.")

    async def sync_time(self, force: bool = False) -> int:
        """Sincroniza desfase entre reloj local y Binance compensando latencia RTT."""
        async with self._time_sync_lock:
            now = time.time()
            if not force and self._last_time_sync > 0 and (now - self._last_time_sync <= 3600):
                return self._time_offset
            if not force and self._last_time_sync_attempt > 0 and (now - self._last_time_sync_attempt < 30.0):
                return self._time_offset

            self._last_time_sync_attempt = now
            try:
                session = await self._get_session()
                t0 = int(time.time() * 1000)
                async with session.get("https://api.binance.com/api/v3/time") as resp:
                    if resp.status == 200:
                        self._consecutive_net_errors = 0
                        data = await resp.json()
                        server_time = data.get("serverTime")
                        t1 = int(time.time() * 1000)
                        if server_time:
                            local_mid = (t0 + t1) // 2
                            self._time_offset = int(server_time - local_mid)
                            self._last_time_sync = time.time()
                            logger.info(
                                "⏱️ Sincronización horaria con Binance: offset = %+d ms (RTT: %d ms)",
                                self._time_offset, t1 - t0,
                            )
                            return self._time_offset
            except Exception as e:
                self._consecutive_net_errors += 1
                logger.warning("No se pudo sincronizar hora con Binance (/api/v3/time): %s", e)
                if self._consecutive_net_errors >= 3:
                    await self._reset_session()
        return self._time_offset

    def _get_timestamp(self) -> int:
        return int(time.time() * 1000) + self._time_offset

    def _sign(self, query_string: str) -> str:
        return hmac.new(self.secret_key.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256).hexdigest()

    def _build_signed_params(self, params: dict) -> str:
        params["timestamp"] = self._get_timestamp()
        if "recvWindow" not in params:
            params["recvWindow"] = 60000
        query_string = urlencode(params, doseq=True)
        return f"{query_string}&signature={self._sign(query_string)}"

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        body: Optional[dict] = None,
        signed: bool = True,
        max_retries: int = 3,
    ) -> dict:
        """Realiza una request HTTP con reintentos y rate limiting."""
        params = (params or {}).copy()
        now = time.time()
        if signed and (self._last_time_sync == 0.0 or (now - self._last_time_sync > 3600)) and (now - self._last_time_sync_attempt >= 30.0):
            await self.sync_time()

        if self.rate_limiter.is_ip_banned:
            remaining_s = self.rate_limiter.ip_banned_remaining_seconds
            raise BinanceClientError(418, "IP_BANNED", f"IP bloqueada temporalmente por Binance (HTTP 418). Cuarentena activa ({remaining_s}s restantes)")

        session: Optional[aiohttp.ClientSession] = None
        is_ad_post = (path == "/sapi/v1/c2c/ads/post")
        for attempt in range(max_retries):
            try:
                await self.rate_limiter.wait_before_request()
                session = await self._get_session()
                if signed:
                    call_params = params.copy()
                    url = f"{self.base_url}{path}?{self._build_signed_params(call_params)}"
                else:
                    url = f"{self.base_url}{path}"
                    if params:
                        url = f"{url}?{urlencode(params, doseq=True)}"

                async with session.request(method, url, json=body if body else None) as response:
                    self._consecutive_net_errors = 0
                    return await self._handle_response(response)

            except BinanceClientError as e:
                if str(e.code) == "-1021" or "recvWindow" in str(e.message):
                    logger.warning("Desfase horario detectado (-1021). Re-sincronizando reloj (intento %d/%d)...", attempt + 1, max_retries)
                    await self.sync_time(force=True)
                    await asyncio.sleep(0.5)
                    continue
                elif e.status == 418:
                    self.rate_limiter.handle_418(e.retry_after)
                    raise
                elif e.status == 429:
                    wait_time = self.rate_limiter.handle_429(e.retry_after, attempt)
                    if attempt >= max_retries - 1:
                        raise
                    logger.warning("Rate limited (429), esperando %.1fs según Binance (intento %d/%d)", wait_time, attempt + 1, max_retries)
                    await asyncio.sleep(wait_time)
                elif e.status >= 500:
                    if is_ad_post or attempt >= max_retries - 1:
                        raise
                    wait_time = self.rate_limiter.calculate_backoff(attempt)
                    logger.warning("Server error %d, reintentando en %.0fs...", e.status, wait_time)
                    await asyncio.sleep(wait_time)
                else:
                    raise
            except asyncio.CancelledError:
                curr_task = asyncio.current_task()
                task_cancelling = getattr(curr_task, "cancelling", lambda: 0)() > 0 if curr_task else False
                if not task_cancelling and session is not None and session.closed and attempt < max_retries - 1:
                    logger.warning("Sesión HTTP reciclada durante request en vuelo, reintentando con nueva sesión...")
                    await asyncio.sleep(0.5)
                    continue
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                self._consecutive_net_errors += 1
                if self._consecutive_net_errors >= 3:
                    await self._reset_session()
                if is_ad_post:
                    logger.warning("Fallo de red en %s (%s); sin reintento para evitar duplicados.", path, e)
                    raise BinanceClientError(0, "TIMEOUT_NO_RETRY" if isinstance(e, asyncio.TimeoutError) else "NETWORK_ERROR_NO_RETRY", f"Fallo de red en {path} ({e})")
                if attempt < max_retries - 1:
                    logger.warning("Connection/Timeout error: %s, reintentando...", str(e))
                    await asyncio.sleep(self.rate_limiter.calculate_backoff(attempt))
                else:
                    raise

        raise BinanceClientError(0, "MAX_RETRIES", "Se agotaron los reintentos")

    async def _handle_response(self, response: aiohttp.ClientResponse) -> dict:
        """Procesa la respuesta y extrae rate limit headers."""
        retry_after = self.rate_limiter.update_from_headers(response.headers)
        if response.status == 429:
            raise BinanceClientError(429, "429", "Rate limited by Binance", retry_after=retry_after)
        if response.status == 418:
            raise BinanceClientError(418, "418", "IP auto-banned by Binance (418)", retry_after=retry_after)

        try:
            data = await response.json()
        except Exception:
            text = await response.text()
            raise BinanceClientError(response.status, str(response.status), text[:200])

        if response.status != 200:
            code = data.get("code", str(response.status))
            msg = data.get("message", data.get("msg", "Unknown error"))
            raise BinanceClientError(response.status, str(code), msg)

        if isinstance(data, dict) and "code" in data:
            code_str = str(data.get("code"))
            if code_str not in ("000000", "0") and data.get("success") is not True:
                raise BinanceClientError(response.status, code_str, data.get("message", data.get("msg", "API returned error")))

        return data

    async def signed_get(self, path: str, params: Optional[dict] = None) -> dict:
        return await self._request("GET", path, params=params, signed=True)

    async def signed_post(self, path: str, params: Optional[dict] = None, body: Optional[dict] = None) -> dict:
        return await self._request("POST", path, params=params, body=body, signed=True)

    async def public_get(self, path: str, params: Optional[dict] = None) -> dict:
        return await self._request("GET", path, params=params, signed=False)

    async def search_ads(
        self, asset: str, fiat: str, trade_type: str, pay_types: Optional[list[str]] = None,
        trans_amount: Optional[float] = None, publisher_type: Optional[str] = None, page: int = 1, rows: int = 20,
    ) -> dict:
        body = {"asset": asset, "fiat": fiat, "tradeType": trade_type, "page": page, "rows": rows}
        if pay_types:
            body["payTypes"] = pay_types
        if trans_amount is not None:
            body["transAmount"] = trans_amount
        if publisher_type is not None:
            body["publisherType"] = publisher_type
        return await self.signed_post("/sapi/v1/c2c/ads/search", body=body)

    async def list_my_ads(self, trade_type: str = "BUY", asset: Optional[str] = None, fiat_unit: str = "ARS", page: int = 1, rows: int = 20) -> dict:
        body = {"tradeType": trade_type, "fiatUnit": fiat_unit, "page": page, "rows": rows}
        if asset:
            body["asset"] = asset
        return await self.signed_post("/sapi/v1/c2c/ads/listWithPagination", body=body)

    async def get_ad_detail(self, adv_no: str) -> dict:
        return await self.signed_post("/sapi/v1/c2c/ads/getDetailByNo", params={"adsNo": adv_no})

    async def get_reference_price(self, assets: list[str], fiat_currency: str = "ARS", trade_type: str = "BUY") -> dict:
        body = {"assets": assets, "fiatCurrency": fiat_currency, "tradeType": trade_type}
        return await self.signed_post("/sapi/v1/c2c/ads/getReferencePrice", body=body)

    async def create_ad(
        self, asset: str, trade_type: str, price: float, init_amount: float, min_trans_amount: float, max_trans_amount: float,
        trade_methods: list[dict], fiat_unit: str = "ARS", price_type: int = 1, pay_time_limit: int = 15,
        auto_reply_msg: str = "", remarks: str = "", online_now: bool = True,
    ) -> dict:
        is_buy = str(trade_type).upper() == "BUY"
        default_notice = DEFAULT_BUY_REMARKS if is_buy else DEFAULT_SELL_REMARKS
        body = {
            "classify": "profession", "asset": asset, "tradeType": trade_type, "fiatUnit": fiat_unit,
            "price": price, "priceType": price_type, "initAmount": init_amount,
            "minSingleTransAmount": min_trans_amount, "maxSingleTransAmount": max_trans_amount,
            "buyerKycLimit": 1,
            "buyerRegDaysLimit": 0 if is_buy else SELL_BUYER_REG_DAYS_LIMIT,
            "buyerBtcPositionLimit": 0 if is_buy else SELL_BUYER_BTC_POSITION_LIMIT,
            "userAllTradeCountMin": 0 if is_buy else SELL_USER_ALL_TRADE_COUNT_MIN,
            "takerAdditionalKycRequired": 0 if is_buy else SELL_TAKER_ADDITIONAL_KYC_REQUIRED,
            "tradeMethods": trade_methods, "payTimeLimit": pay_time_limit, "onlineNow": online_now,
            "autoReplyMsg": auto_reply_msg if auto_reply_msg else default_notice,
            "remarks": remarks if remarks else default_notice,
        }
        return await self.signed_post("/sapi/v1/c2c/ads/post", body=body)

    async def update_ad(self, adv_no: str, price: Optional[float] = None, update_mode: str = "quickedit", **kwargs) -> dict:
        body = {"advNo": adv_no, "updateMode": update_mode}
        if price is not None:
            body["price"] = price
        body.update(kwargs)
        return await self.signed_post("/sapi/v1/c2c/ads/update", body=body)

    async def update_ad_status(self, adv_nos: list[str], status: int) -> dict:
        if status == 4 and len(adv_nos) > 1:
            all_ok, any_ok, last_res, details = True, False, None, []
            for no in adv_nos:
                try:
                    res = await self.signed_post("/sapi/v1/c2c/ads/updateStatus", body={"advNos": [no], "advStatus": 4})
                    details.append((no, res))
                    if isinstance(res, dict) and (res.get("data") is True or res.get("success") is True or res.get("code") == "000000"):
                        any_ok, last_res = True, res
                    else:
                        all_ok = False
                except Exception as e:
                    logger.error("Error cerrando anuncio %s en batch: %s", no, e)
                    all_ok = False
                    details.append((no, {"error": str(e)}))
                await asyncio.sleep(0.5)
            if all_ok:
                return {"code": "000000", "data": True, "success": True, "details": details}
            if any_ok:
                base = dict(last_res) if isinstance(last_res, dict) else {"code": "000000", "data": True}
                base.setdefault("code", "000000")
                base.setdefault("data", True)
                base["details"] = details
                return base
            return {"code": "187000", "data": False, "success": False, "details": details}

        body = {"advNos": adv_nos, "advStatus": status}
        return await self.signed_post("/sapi/v1/c2c/ads/updateStatus", body=body)

    async def close_ad(self, adv_no: str) -> dict:
        return await self.update_ad_status(adv_nos=[adv_no], status=4)

    async def list_orders(self, trade_type: Optional[str] = None, order_status_list: Optional[list[int]] = None, page: int = 1, rows: int = 20) -> dict:
        body = {"page": page, "rows": rows}
        if trade_type:
            body["tradeType"] = trade_type
        if order_status_list:
            body["orderStatusList"] = order_status_list
        return await self.signed_post("/sapi/v1/c2c/orderMatch/listOrders", body=body)

    async def get_order_history(self, trade_type: Optional[str] = None, page: int = 1, rows: int = 20) -> dict:
        params = {"page": page, "rows": rows}
        if trade_type:
            params["tradeType"] = trade_type
        return await self.signed_get("/sapi/v1/c2c/orderMatch/listUserOrderHistory", params=params)

    async def get_order_detail(self, order_no: str) -> dict:
        return await self.signed_post("/sapi/v1/c2c/orderMatch/getUserOrderDetail", body={"adOrderNo": order_no})

    async def get_my_payment_methods(self) -> dict:
        return await self.signed_get("/sapi/v1/c2c/paymentMethod/getPayMethodByUserId")

    async def list_all_payment_methods(self) -> dict:
        return await self.signed_post("/sapi/v1/c2c/paymentMethod/listAll")

    async def list_digital_currencies(self) -> dict:
        return await self.signed_post("/sapi/v1/c2c/digitalCurrency/list")

    async def list_fiat_currencies(self) -> dict:
        return await self.signed_post("/sapi/v1/c2c/fiatCurrency/list")

    async def set_online(self) -> dict:
        return await self.signed_post("/sapi/v1/c2c/merchant/getOnline")

    async def set_offline(self) -> dict:
        return await self.signed_post("/sapi/v1/c2c/merchant/getOffline")

    async def get_my_spot_trades(self, symbol: str, limit: int = 10) -> list[dict]:
        res = await self.signed_get("/api/v3/myTrades", params={"symbol": symbol, "limit": limit})
        return res if isinstance(res, list) else []

    async def get_convert_trades(self, start_time: int, end_time: int, limit: int = 10) -> dict:
        return await self.signed_get("/sapi/v1/convert/tradeFlow", params={"startTime": start_time, "endTime": end_time, "limit": limit})

    async def get_funding_asset(self, asset: str = "USDT") -> float:
        try:
            res = await self.signed_post("/sapi/v1/asset/get-funding-asset", body={"asset": asset, "needBtcValuation": "false"})
            if isinstance(res, list):
                for item in res:
                    if item.get("asset") == asset:
                        return float(item.get("free", 0.0) or 0.0)
            return 0.0
        except Exception as e:
            logger.warning("No se pudo obtener saldo de Billetera de Fondos para %s: %s", asset, e)
            return 0.0

    async def close(self) -> None:
        async with self._session_lock:
            if self._session and not self._session.closed:
                res = self._session.close()
                if asyncio.iscoroutine(res):
                    await res
                self._session = None


# Alias canónico
BinanceClient = BinanceApi
