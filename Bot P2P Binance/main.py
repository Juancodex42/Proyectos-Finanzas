"""
Bot P2P Binance ARS — Punto de entrada de la aplicación.
Ejecuta el motor orquestador BotEngine con manejo de señales de apagado limpio.
Referencia de diseño: docs/ARQUITECTURA.md
"""
import sys
import signal
import asyncio
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Asegurar que src/ esté en el path para imports absolutos
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from core.orchestrator import BotEngine
from data.database import Database
from core.network.binance_api import BinanceClient
from core.spot_client import SpotClient
from core.fiwind_client import FiwindClient
from telegram_bot.bot import TelegramBot

# ── Windows UTF-8 stdout ──────────────────────────────────────────────
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ── Logging ───────────────────────────────────────────────────────────
LOG_FILE_PATH = Path(__file__).resolve().parent / "logs" / "bot.log"
LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            RotatingFileHandler(
                str(LOG_FILE_PATH),
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
                delay=True,
            ),
        ],
    )
for _noisy in ("httpx", "httpcore", "telegram.ext.Updater"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
logger = logging.getLogger("main")


async def main():
    engine = BotEngine()

    def handle_signal(sig_num, frame):
        logger.info("Señal de parada recibida (%s), iniciando apagado ordenado...", sig_num)
        engine.request_stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, handle_signal)
        except Exception:
            pass

    try:
        await engine.run()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Interrupción por teclado detectada")
    finally:
        await engine.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
