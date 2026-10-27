"""
Repositorio Mixin de configuración persistente y almacén clave-valor del bot.
Referencia de diseño: docs/ARQUITECTURA.md
"""
import json
import logging
from datetime import datetime
from typing import Optional, Any
from data.models import BotConfig
from data.schema import _safe_json_list, _parse_float, _parse_int, _parse_db_datetime

logger = logging.getLogger("data.config")


class ConfigRepoMixin:
    """Operaciones de persistencia para la configuración del bot y variables de control."""
    def get_config(self, key: str, default: str = "") -> str:
        with self._lock:
            conn = self.connect()
            row = conn.execute(
                "SELECT value FROM bot_config WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def set_config(self, key: str, value: str):
        self._execute_write(
            "INSERT OR REPLACE INTO bot_config (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, datetime.now().isoformat()),
        )

    def load_bot_config(self) -> BotConfig:
        """Carga la configuración completa del bot desde DB."""
        from config.settings import (
            DEFAULT_MARGIN_MIN, DEFAULT_SELL_MARGIN_MIN, DEFAULT_PRICE_STEP,
            DEFAULT_POLL_INTERVAL, DEFAULT_VOLUME_REF, DEFAULT_BALANCE_ARS,
            FIWIND_RESCUE_MARGIN,
        )
        with self._lock:
            config = BotConfig()
            config.margin_min = _parse_float(self.get_config("margin_min", str(DEFAULT_MARGIN_MIN)), DEFAULT_MARGIN_MIN)
            config.sell_margin_min = _parse_float(self.get_config("sell_margin_min", str(DEFAULT_SELL_MARGIN_MIN)), DEFAULT_SELL_MARGIN_MIN)
            config.price_step = _parse_float(self.get_config("price_step", str(DEFAULT_PRICE_STEP)), DEFAULT_PRICE_STEP)
            config.poll_interval = _parse_int(self.get_config("poll_interval", str(DEFAULT_POLL_INTERVAL)), DEFAULT_POLL_INTERVAL)
            config.volume_ref = _parse_float(self.get_config("volume_ref", str(DEFAULT_VOLUME_REF)), DEFAULT_VOLUME_REF)
            config.rescue_margin = _parse_float(self.get_config("rescue_margin", str(FIWIND_RESCUE_MARGIN)), FIWIND_RESCUE_MARGIN)

            # Sincronización robusta de saldo: balance auditado de liquidity > bot_config > default
            conn = self.connect()
            liq_row = conn.execute(
                "SELECT balance_after FROM liquidity WHERE event_type != 'historical_sync' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            saved_balance_raw = self.get_config("balance_ars", "")
            if liq_row is not None and liq_row["balance_after"] is not None:
                config.balance_ars = float(liq_row["balance_after"])
            elif saved_balance_raw:
                try:
                    config.balance_ars = float(saved_balance_raw)
                except ValueError:
                    config.balance_ars = float(DEFAULT_BALANCE_ARS)
            else:
                config.balance_ars = float(DEFAULT_BALANCE_ARS)

            config.is_paused = self.get_config("is_paused", "0") == "1"

            paused_assets_raw = self.get_config("paused_assets", "")
            config.paused_assets = {x.strip() for x in paused_assets_raw.split(",") if x.strip()} if paused_assets_raw else set()

            paused_ads_raw = self.get_config("paused_ads", "")
            config.paused_ads = {x.strip() for x in paused_ads_raw.split(",") if x.strip()} if paused_ads_raw else set()

            sleep_until_raw = self.get_config("sleep_until", "")
            if sleep_until_raw:
                try:
                    config.sleep_until = datetime.fromisoformat(sleep_until_raw)
                except ValueError:
                    config.sleep_until = None

            return config

    def save_bot_config(self, config: BotConfig):
        """Persiste la configuración del bot en DB."""
        with self._lock:
            self.set_config("margin_min", str(config.margin_min))
            self.set_config("sell_margin_min", str(config.sell_margin_min))
            self.set_config("price_step", str(config.price_step))
            self.set_config("poll_interval", str(config.poll_interval))
            self.set_config("volume_ref", str(config.volume_ref))
            self.set_config("balance_ars", str(config.balance_ars))
            self.set_config("rescue_margin", str(config.rescue_margin))
            self.set_config("is_paused", "1" if config.is_paused else "0")
            paused_assets_clean = [str(x).strip() for x in (config.paused_assets or []) if str(x).strip()]
            paused_ads_clean = [str(x).strip() for x in (config.paused_ads or []) if str(x).strip()]
            self.set_config("paused_assets", ",".join(dict.fromkeys(paused_assets_clean)))
            self.set_config("paused_ads", ",".join(dict.fromkeys(paused_ads_clean)))
            self.set_config(
                "sleep_until",
                config.sleep_until.isoformat() if config.sleep_until else "",
            )


