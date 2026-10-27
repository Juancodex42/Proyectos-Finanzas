"""
Paquete de interfaz remota y automatización vía Telegram.
Exporta TradingBotInterface, AutomationManager, handlers y formateadores.
Referencia de diseño: docs/TELEGRAM_INTERFACE.md
"""

from .bot_interface import TradingBotInterface
from .automation import AutomationManager
from .formatters import (
    format_welcome,
    format_help,
    format_status,
    format_stats,
    format_pnl,
    format_positions,
    format_trades,
    format_strategies,
    format_data_collection,
    format_periodic_alert,
    format_backtest_completed,
)
from .handlers import TelegramCommandHandlerMixin

__all__ = [
    'TradingBotInterface',
    'AutomationManager',
    'TelegramCommandHandlerMixin',
    'format_welcome',
    'format_help',
    'format_status',
    'format_stats',
    'format_pnl',
    'format_positions',
    'format_trades',
    'format_strategies',
    'format_data_collection',
    'format_periodic_alert',
    'format_backtest_completed',
]
