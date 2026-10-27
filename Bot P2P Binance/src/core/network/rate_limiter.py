"""
Módulo de Rate Limiting y Control de Cuarentena para Binance SAPI.

Gestiona el presupuesto de peso IP (X-SAPI-USED-IP-WEIGHT-1M),
pausas por exceso de peticiones (HTTP 429), circuit breaker por
cuarentena de IP (HTTP 418) y backoff exponencial con jitter.
"""
import asyncio
import logging
import random
import time
from typing import Mapping, Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Controlador de tasa de peticiones y prevención de bloqueos para Binance SAPI.
    
    Monitorea los encabezados X-SAPI-USED-IP-WEIGHT-1M y Retry-After devueltos por
    la API, gestionando estados de espera antes de cada solicitud y protegiendo
    la IP contra suspensiones transitorias o definitivas.
    """

    def __init__(self, default_weight_limit: int = 1200) -> None:
        self.default_weight_limit = default_weight_limit
        self._rate_limit_remaining: int = default_weight_limit
        self._rate_limit_updated_at: float = 0.0
        self._rate_limited_until: float = 0.0
        self._rate_limit_lock: asyncio.Lock = asyncio.Lock()
        self._ip_banned_until: float = 0.0

    @property
    def rate_limit_remaining(self) -> int:
        """Presupuesto restante estimado de peso IP para la ventana de 1 minuto."""
        return self._rate_limit_remaining

    @property
    def rate_limited_until(self) -> float:
        """Timestamp epoch en segundos hasta el cual rige una pausa por HTTP 429."""
        return self._rate_limited_until

    @property
    def ip_banned_until(self) -> float:
        """Timestamp epoch en segundos hasta el cual rige la cuarentena por HTTP 418."""
        return self._ip_banned_until

    @property
    def is_ip_banned(self) -> bool:
        """Indica si rige actualmente una cuarentena por respuesta HTTP 418."""
        return self._ip_banned_until > time.time()

    @property
    def ip_banned_remaining_seconds(self) -> int:
        """Segundos restantes de cuarentena IP si está activa, o 0."""
        return max(0, int(self._ip_banned_until - time.time()))

    def check_ip_ban(self) -> None:
        """
        Verifica si la IP local está en cuarentena activa tras un HTTP 418.
        
        Raises:
            RuntimeError: Si la IP está en período de cuarentena.
        """
        if self.is_ip_banned:
            remaining_s = self.ip_banned_remaining_seconds
            raise RuntimeError(
                f"IP bloqueada temporalmente por Binance (HTTP 418). "
                f"Cuarentena activa ({remaining_s}s restantes)"
            )

    async def wait_before_request(self) -> None:
        """
        Evalúa el estado del rate limiter y suspende la ejecución si es necesario.
        
        1. Espera activa si rige una ventana de espera por HTTP 429 (_rate_limited_until).
        2. Pausa preventiva de 2s si el peso restante es menor o igual a 10 y no ha vencido el minuto.
        """
        now = time.time()
        if now < self._rate_limited_until:
            await asyncio.sleep(max(0.0, self._rate_limited_until - now))

        async with self._rate_limit_lock:
            if self._rate_limit_remaining <= 10:
                now_check = time.time()
                if self._rate_limit_updated_at > 0 and (now_check - self._rate_limit_updated_at) >= 60.0:
                    self._rate_limit_remaining = self.default_weight_limit
                else:
                    logger.warning(
                        "Rate limit bajo (%d), esperando 2s...",
                        self._rate_limit_remaining,
                    )
                    await asyncio.sleep(2.0)
                    self._rate_limit_remaining = 100

    def update_from_headers(self, headers: Mapping[str, str]) -> Optional[float]:
        """
        Extrae headers de rate limit (X-SAPI-USED-IP-WEIGHT-1M y Retry-After).
        
        Args:
            headers: Diccionario de encabezados HTTP devuelto por Binance.

        Returns:
            Valor numérico en segundos de Retry-After si fue provisto, o None.
        """
        retry_after: Optional[float] = None
        if "Retry-After" in headers:
            try:
                retry_after = float(headers["Retry-After"])
            except (ValueError, TypeError):
                retry_after = None

        if "X-SAPI-USED-IP-WEIGHT-1M" in headers:
            try:
                used = int(headers["X-SAPI-USED-IP-WEIGHT-1M"])
                self._rate_limit_remaining = max(self.default_weight_limit - used, 0)
                self._rate_limit_updated_at = time.time()
            except (ValueError, TypeError):
                pass

        return retry_after

    def handle_429(self, retry_after: Optional[float], attempt: int) -> float:
        """
        Calcula el tiempo de espera ante error HTTP 429 y actualiza la cota temporal.
        
        Args:
            retry_after: Valor informado por Binance en cabecera Retry-After.
            attempt: Número de intento de reintento actual (0-indexed).

        Returns:
            Tiempo total en segundos que la tarea debe esperar (incluyendo jitter).
        """
        raw_wait = retry_after if retry_after is not None else max(15.0 * (attempt + 1), 60.0)
        wait_time = float(raw_wait) + random.uniform(1.0, 3.0)
        self._rate_limited_until = max(self._rate_limited_until, time.time() + wait_time)
        return wait_time

    def handle_418(self, retry_after: Optional[float]) -> float:
        """
        Registra la cuarentena de IP tras recibir un código HTTP 418.
        
        Args:
            retry_after: Valor informado por Binance en cabecera Retry-After.

        Returns:
            Duración en segundos asignada al bloqueo (mínimo 1800s / 30 minutos).
        """
        ban_duration = max(float(retry_after or 0.0), 1800.0)
        self._ip_banned_until = time.time() + ban_duration
        logger.critical(
            "🚫 ALERTA CRÍTICA: IP bloqueada por Binance (HTTP 418). "
            "Activando circuit-breaker de %.0f segundos.",
            ban_duration,
        )
        return ban_duration

    @staticmethod
    def calculate_backoff(attempt: int) -> float:
        """
        Calcula el retraso en segundos para reintentos por error de red o servidor.
        
        Args:
            attempt: Número de reintento (0-indexed).

        Returns:
            Retraso en segundos (2 ** attempt).
        """
        return float(2 ** attempt)
