"""
Módulo de manejadores de comandos, callbacks y parseo de inputs para Telegram.
Referencia de diseño: docs/ARQUITECTURA.md
"""
from telegram_bot.handlers.callbacks import handle_callback
from telegram_bot.handlers.commands import CommandHandlerMixin
from telegram_bot.handlers.input_parser import parse_numeric_input

__all__ = ["handle_callback", "CommandHandlerMixin", "parse_numeric_input"]
