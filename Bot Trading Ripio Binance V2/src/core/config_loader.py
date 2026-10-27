"""
Gestor centralizado de configuración YAML y variables de entorno.
Valida parámetros de riesgo, alocación de estrategias y credenciales de operación.
Referencia de diseño: docs/ARQUITECTURA.md
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict
import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class ConfigLoader:
    """
    Carga y valida la configuración del sistema desde `config/trading_config.yaml` y `.env`.
    Permite operar en modo Demo / Paper sin requerir un archivo `.env` físico.
    """

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "trading_config.yaml"
        load_dotenv()

        self.config: Dict[str, Any] = {}
        self.credentials: Dict[str, Any] = {}

    def load_credentials(self, strict: bool = False) -> Dict[str, Any]:
        """
        Carga credenciales desde variables de entorno.
        Si `strict=False`, asigna placeholders seguros cuando se ejecuta en modo Demo/Test.
        """
        missing = []

        bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
        if bot_token:
            self.credentials["TELEGRAM_BOT_TOKEN"] = bot_token
            self.credentials["BOT_TOKEN"] = bot_token
        else:
            missing.append("TELEGRAM_BOT_TOKEN / BOT_TOKEN")
            self.credentials["TELEGRAM_BOT_TOKEN"] = ""
            self.credentials["BOT_TOKEN"] = "placeholder_bot_token"

        chat_id = os.getenv("TELEGRAM_AUTHORIZED_USERS") or os.getenv("CHAT_ID")
        if chat_id:
            self.credentials["TELEGRAM_AUTHORIZED_USERS"] = chat_id
            self.credentials["CHAT_ID"] = chat_id
        else:
            missing.append("TELEGRAM_AUTHORIZED_USERS / CHAT_ID")
            self.credentials["TELEGRAM_AUTHORIZED_USERS"] = ""
            self.credentials["CHAT_ID"] = "123456789"

        for var in ("RIPIO_API_TOKEN", "RIPIO_SECRET_KEY"):
            value = os.getenv(var)
            if not value:
                missing.append(var)
                self.credentials[var] = f"placeholder_{var.lower()}"
            else:
                self.credentials[var] = value

        if missing and strict:
            raise ValueError(f"❌ Faltan variables en .env: {', '.join(missing)}")
        if missing:
            logger.info(
                f"ℹ️ Variables de entorno ausentes ({', '.join(missing)}); "
                "usando valores de simulación/demo."
            )

        self.credentials["TRADING_MODE"] = os.getenv("TRADING_MODE", "paper_trading")
        self.credentials["CAPITAL_INICIAL"] = float(os.getenv("CAPITAL_INICIAL", "1000"))
        self.credentials["LOG_LEVEL"] = os.getenv("LOG_LEVEL", "INFO")

        return self.credentials

    def load_config(self) -> Dict[str, Any]:
        """Carga y verifica las secciones requeridas de `trading_config.yaml`."""
        if not self.config_file.exists():
            raise FileNotFoundError(f"❌ No se encuentra {self.config_file}")

        with open(self.config_file, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        required_sections = [
            "pairs",
            "fees",
            "execution",
            "portfolio",
            "risk",
            "strategies",
            "validation",
        ]
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"❌ Falta sección '{section}' en config")

        return self.config

    def get(self, key: str, default: Any = None) -> Any:
        """Obtiene un valor de configuración mediante notación de puntos (dot notation)."""
        keys = key.split(".")
        value: Any = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value

    def validate_config(self) -> bool:
        """Valida consistencia de comisiones, drawdown máximo y suma de alocaciones."""
        errors = []
        if self.get("fees.maker", 0.0013) >= self.get("fees.taker", 0.0030):
            errors.append("⚠️ Comisión maker debería ser < taker")

        if self.get("risk.max_drawdown_pct", 1.0) > 0.30:
            errors.append("⚠️ Max drawdown > 30% es muy alto")

        total_allocation = sum([
            self.get("strategies.statistical_arbitrage.allocation_pct", 0.0),
            self.get("strategies.market_making.allocation_pct", 0.0),
            self.get("strategies.triangular_arbitrage.allocation_pct", 0.0),
            self.get("strategies.volatility_harvesting.allocation_pct", 0.0),
        ])
        if abs(total_allocation - 1.0) > 0.01:
            errors.append(f"⚠️ Allocation total = {total_allocation:.2f}, debería ser 1.0")

        if self.get("validation.sharpe_minimo", 0.0) < 1.0:
            errors.append("⚠️ Sharpe mínimo < 1.0 es muy bajo")

        if errors:
            for err in errors:
                logger.warning(f"  {err}")
            return False
        return True

    def get_strategy_config(self, strategy_name: str) -> Dict[str, Any]:
        """Obtiene el bloque de configuración de una estrategia específica."""
        return self.get(f"strategies.{strategy_name}", {})

    def is_strategy_enabled(self, strategy_name: str) -> bool:
        """Indica si una estrategia se encuentra habilitada en el archivo YAML."""
        return bool(self.get(f"strategies.{strategy_name}.enabled", False))

    def get_trading_mode(self) -> str:
        """Retorna el modo de operación configurado."""
        return str(self.credentials.get("TRADING_MODE", "paper_trading"))

    def is_paper_trading(self) -> bool:
        """Verifica si el sistema opera en modo Paper Trading."""
        return self.get_trading_mode() == "paper_trading"

    def is_live_trading(self) -> bool:
        """Verifica si el sistema opera en modo Live Trading."""
        return self.get_trading_mode() == "live_trading"

    def get_all(self) -> Dict[str, Any]:
        """Retorna resumen público de configuración sin exponer claves privadas."""
        return {
            "config": self.config,
            "trading_mode": self.get_trading_mode(),
            "capital_inicial": self.credentials.get("CAPITAL_INICIAL", 1000.0),
        }
