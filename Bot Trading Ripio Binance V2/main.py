"""
Punto de entrada y orquestador principal del Bot de Trading Cuantitativo V2.0.
Coordina los modos Demo Zero-API, Backtest, Data Collection, Health, Paper y Live.
Referencia de diseño: docs/ARQUITECTURA.md
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.append(str(ROOT_DIR / "src"))

from core.config_loader import ConfigLoader
from core.ripio_api import ProfessionalRipioAPI
from core.binance_api import BinanceAPI
from core.state_manager import StateManager
from analytics.portfolio_manager import AdvancedPortfolioManager
from strategies import StatisticalArbitrageStrategy, MarketMakingStrategy
from execution import InterExchangeRouter
from src.telegram_bot import TradingBotInterface
from src.telegram_bot.automation import AutomationManager

(ROOT_DIR / "data" / "logs").mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(str(ROOT_DIR / "data" / "logs" / "bot.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


class BotV2:
    """Orquestador central del Bot de Trading Cuantitativo V2.0."""

    def __init__(self):
        self.config_loader = None
        self.config = None
        self.credentials = None

        self.ripio_api = None
        self.binance_api = None
        self.state_manager = None
        self.portfolio_manager = None
        self.router = None

        self.stat_arb_strategy = None
        self.market_making_strategy = None
        self.telegram_bot = None
        self.automation_manager = None
        self.running = False

    async def initialize(self, mode_override: str = None, capital_override: float = None):
        """Inicializa configuración, clientes de API, gestores de estado y estrategias."""
        logger.info("=" * 60)
        logger.info("🤖 BOT DE TRADING CUANTITATIVO V2.0")
        logger.info("=" * 60)

        self.config_loader = ConfigLoader()
        is_live = mode_override in ("live", "live_trading")
        self.credentials = self.config_loader.load_credentials(strict=is_live)
        self.config = self.config_loader.load_config()

        if mode_override:
            mode_map = {
                "paper": "paper_trading",
                "paper_trading": "paper_trading",
                "live": "live_trading",
                "live_trading": "live_trading",
            }
            mapped = mode_map.get(mode_override.lower(), mode_override)
            self.credentials["TRADING_MODE"] = mapped
            self.config_loader.credentials["TRADING_MODE"] = mapped

        if capital_override is not None:
            self.credentials["CAPITAL_INICIAL"] = float(capital_override)
            self.config_loader.credentials["CAPITAL_INICIAL"] = float(capital_override)

        self.config_loader.validate_config()

        self.ripio_api = ProfessionalRipioAPI(
            api_token=self.credentials["RIPIO_API_TOKEN"],
            secret_key=self.credentials["RIPIO_SECRET_KEY"],
        )
        await self.ripio_api.init_session()

        self.binance_api = BinanceAPI()
        await self.binance_api.init_session()

        ripio_ok = await self.ripio_api.health_check()
        binance_ok = await self.binance_api.health_check()
        if not ripio_ok:
            raise RuntimeError("❌ Ripio API no responde")
        if not binance_ok:
            logger.warning("⚠️ Binance API no responde (no crítico)")

        self.state_manager = StateManager()
        state = self.state_manager.load_state()
        if state["capital"] == 0:
            self.state_manager.update_capital(self.credentials["CAPITAL_INICIAL"])

        self.portfolio_manager = AdvancedPortfolioManager(self.ripio_api, self.config)
        await self.portfolio_manager.actualizar_inventario()
        await self.portfolio_manager.actualizar_precios()

        self.router = InterExchangeRouter(
            ripio_api=self.ripio_api,
            binance_api=self.binance_api,
            config=self.config,
        )

        self.stat_arb_strategy = StatisticalArbitrageStrategy(
            ripio_api=self.ripio_api,
            config=self.config,
            portfolio_manager=self.portfolio_manager,
            state_manager=self.state_manager,
            router=self.router,
        )
        self.market_making_strategy = MarketMakingStrategy(
            ripio_api=self.ripio_api,
            config=self.config,
            portfolio_manager=self.portfolio_manager,
            state_manager=self.state_manager,
        )

        telegram_token = self.credentials.get("TELEGRAM_BOT_TOKEN")
        telegram_users = self.credentials.get("TELEGRAM_AUTHORIZED_USERS", "").split(",")

        if telegram_token and not telegram_token.startswith("placeholder_"):
            authorized_users = []
            for uid_str in telegram_users:
                uid_str = uid_str.strip()
                if uid_str.isdigit():
                    authorized_users.append(int(uid_str))

            self.telegram_bot = TradingBotInterface(
                telegram_token=telegram_token,
                trading_bot=self,
                authorized_users=authorized_users,
            )
            await self.telegram_bot.initialize()
            self.automation_manager = AutomationManager(
                trading_bot=self,
                telegram_bot=self.telegram_bot,
            )

        self.running = True

    async def shutdown(self):
        """Cierra sesiones HTTP, detiene Telegram y persiste el estado en disco."""
        self.running = False
        if self.telegram_bot:
            await self.telegram_bot.stop()
        if self.state_manager:
            self.state_manager.save_state()
        if self.ripio_api:
            await self.ripio_api.close_session()
        if self.binance_api:
            await self.binance_api.close_session()

    async def reload_config(self):
        """Recarga en caliente la configuración desde YAML y `.env`."""
        self.credentials = self.config_loader.load_credentials()
        self.config = self.config_loader.load_config()
        if self.stat_arb_strategy:
            self.stat_arb_strategy.config = self.config
        if self.market_making_strategy:
            self.market_making_strategy.config = self.config

    async def close_all_positions(self):
        """Cierra todas las posiciones activas y cancela órdenes abiertas."""
        if self.stat_arb_strategy and self.stat_arb_strategy.current_position:
            await self.stat_arb_strategy.execute_signal({"action": "close", "position_size_usd": 0})
        if self.market_making_strategy:
            await self.market_making_strategy.cancel_orders()

    async def run_strategies_loop(self, interval_seconds: int = 60):
        """Ejecuta el ciclo continuo de estrategias en modo Paper o Live."""
        iteration = 0
        while self.running:
            try:
                iteration += 1
                await self.portfolio_manager.actualizar_inventario()
                await self.portfolio_manager.actualizar_precios()

                if self.stat_arb_strategy.enabled:
                    await self.stat_arb_strategy.run_iteration()
                if self.market_making_strategy.enabled:
                    await self.market_making_strategy.run_iteration()

                if iteration % 10 == 0:
                    self.state_manager.save_state()

                await asyncio.sleep(interval_seconds)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"[STRATEGIES] Error in loop: {e}")
                await asyncio.sleep(interval_seconds)


def parse_arguments():
    """Parsea argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="Bot de Trading Cuantitativo V2.0 - Ripio / Binance",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="demo",
        choices=[
            "demo",
            "paper",
            "live",
            "backtest",
            "collect",
            "health",
            "paper_trading",
            "live_trading",
        ],
        help="Modo de ejecución: demo (sin APIs), paper, live, backtest, collect, health",
    )
    parser.add_argument("--capital", type=float, default=10000.0, help="Capital inicial en USD")
    parser.add_argument("--days", type=int, default=30, help="Días para recolección o backtesting")
    parser.add_argument("--interval", type=int, default=60, help="Intervalo en segundos")
    return parser.parse_args()


async def main():
    """Punto de entrada asíncrono según el modo seleccionado."""
    args = parse_arguments()

    if args.mode == "demo":
        from core.demo_runner import run_zero_api_demo
        await run_zero_api_demo(days=min(args.days, 15), capital=args.capital or 10000.0)
        return

    if args.mode == "health":
        bot = BotV2()
        bot.config_loader = ConfigLoader()
        bot.credentials = bot.config_loader.load_credentials()
        bot.config = bot.config_loader.load_config()
        bot.ripio_api = ProfessionalRipioAPI(
            api_token=bot.credentials["RIPIO_API_TOKEN"],
            secret_key=bot.credentials["RIPIO_SECRET_KEY"],
        )
        await bot.ripio_api.init_session()
        ripio_ok = await bot.ripio_api.health_check()
        bot.binance_api = BinanceAPI()
        await bot.binance_api.init_session()
        binance_ok = await bot.binance_api.health_check()
        await bot.ripio_api.close_session()
        await bot.binance_api.close_session()
        print(f"Ripio API: {'OK' if ripio_ok else 'FAIL'} | Binance API: {'OK' if binance_ok else 'WARN'}")
        return

    if args.mode == "collect":
        from collect_data import DataCollector
        cfg_loader = ConfigLoader()
        creds = cfg_loader.load_credentials()
        interval_min = max(1, args.interval // 60) if args.interval else 5
        collector = DataCollector(
            api_token=creds["RIPIO_API_TOKEN"],
            secret_key=creds["RIPIO_SECRET_KEY"],
            output_dir=str(ROOT_DIR / "data" / "historical"),
        )
        await collector.initialize()
        await collector.run(duration_days=args.days, interval_minutes=interval_min)
        return

    if args.mode == "backtest":
        from run_backtest import run_basic_backtest
        bt_args = SimpleNamespace(
            mode="basic",
            strategy="mean_reversion",
            data=None,
            synthetic=True,
            days=args.days,
            capital=args.capital or 10000.0,
            lookback=20,
            z_threshold=2.0,
            train_window=30,
            test_window=7,
            num_folds=4,
            simulations=1000,
            permutations=1000,
            output_dir=str(ROOT_DIR / "reports"),
            export=True,
        )
        await run_basic_backtest(bt_args)
        return

    bot = BotV2()
    try:
        await bot.initialize(mode_override=args.mode, capital_override=args.capital)
        tasks = [asyncio.create_task(bot.run_strategies_loop(interval_seconds=args.interval))]
        if bot.telegram_bot:
            tasks.append(asyncio.create_task(bot.telegram_bot.start()))
        if bot.automation_manager:
            tasks.append(asyncio.create_task(bot.automation_manager.start_automation_loop()))
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        await bot.shutdown()


if __name__ == "__main__":
    (ROOT_DIR / "data" / "logs").mkdir(parents=True, exist_ok=True)
    (ROOT_DIR / "data" / "state").mkdir(parents=True, exist_ok=True)
    (ROOT_DIR / "data" / "historical").mkdir(parents=True, exist_ok=True)
    asyncio.run(main())
