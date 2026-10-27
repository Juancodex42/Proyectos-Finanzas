"""
Módulo de formateadores y vistas de mensajes para Telegram.
"""
from telegram_bot.formatters.alert_view import (
    escape_md,
    _translate_reason,
    format_reposition_notification,
    format_order_notification,
    format_swap_notification,
    format_rescue_notification,
    format_opportunity_notification,
    format_daily_report,
    format_profit_report,
    format_altcoin_buy_swap_alert,
    format_open_sell_order_notification,
)
from telegram_bot.formatters.dashboard_view import (
    format_status,
    format_benchmark,
    format_reconciliation_report,
    format_live_dashboard,
    format_simulation_report,
    format_sell_advice_report,
    format_sell_decisions_dashboard,
)

__all__ = [
    "escape_md",
    "_translate_reason",
    "format_reposition_notification",
    "format_order_notification",
    "format_swap_notification",
    "format_rescue_notification",
    "format_opportunity_notification",
    "format_daily_report",
    "format_profit_report",
    "format_altcoin_buy_swap_alert",
    "format_open_sell_order_notification",
    "format_status",
    "format_benchmark",
    "format_reconciliation_report",
    "format_live_dashboard",
    "format_simulation_report",
    "format_sell_advice_report",
    "format_sell_decisions_dashboard",
]
