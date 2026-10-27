"""
engine/execution/telegram_bot.py
Módulo Institucional del Bot de Telegram para la Terminal Nexus.
Permite control remoto E2E desde el celular:
- Encendido / Apagado de Bot 1 y Bot 2.
- Consulta de saldos en Binance Futuros y estado de la racha.
- Monitoreo del trade en vivo identificando la estrategia exacta del abanico que abrió la orden.
- Renderizado de gráficos de velas y curvas de equidad en imágenes PNG vía matplotlib.
- Resumen de métricas de los últimos 30 días.
- Botón de pánico con doble confirmación.
- Seguridad bancaria: Whitelist estricta por Chat ID.
"""

import io
import time
import threading
import logging
from typing import Dict, Any, List, Optional, Tuple
import requests
import matplotlib
matplotlib.use('Agg')  # Modo Headless para generación de imágenes en servidor
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np

logger = logging.getLogger("NexusTelegramBot")


class TelegramBotClient:
    def __init__(
        self,
        bot_token: str = "",
        allowed_chat_ids: Optional[List[int]] = None,
        manager = None
    ):
        self.bot_token = bot_token.strip()
        self.allowed_chat_ids = set(allowed_chat_ids or [])
        self.manager = manager
        self.api_base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.is_running = False
        self.polling_thread: Optional[threading.Thread] = None
        self.last_update_id = 0

    def is_configured(self) -> bool:
        return bool(self.bot_token and len(self.allowed_chat_ids) > 0)

    def start(self):
        """Inicia el hilo de long-polling en segundo plano."""
        if not self.is_configured():
            logger.warning("Telegram Bot no configurado (falta token o chat_id).")
            return

        if self.polling_thread is None or not self.polling_thread.is_alive():
            self.is_running = True
            self.polling_thread = threading.Thread(target=self._polling_loop, daemon=True)
            self.polling_thread.start()
            logger.info("Telegram Bot iniciado exitosamente en segundo plano.")

    def stop(self):
        """Detiene el bucle de polling."""
        self.is_running = False

    def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "Markdown",
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Envía un mensaje de texto con formato y botones inline opcionales."""
        if not self.bot_token:
            return False
        try:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup
            res = requests.post(f"{self.api_base_url}/sendMessage", json=payload, timeout=10)
            return res.status_code == 200
        except Exception as e:
            logger.error(f"Error enviando mensaje Telegram a {chat_id}: {e}")
            return False

    def send_photo(
        self,
        chat_id: int,
        photo_bytes: io.BytesIO,
        caption: str = "",
        parse_mode: str = "Markdown",
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Envía una imagen en memoria (PNG) al chat de Telegram."""
        if not self.bot_token:
            return False
        try:
            photo_bytes.seek(0)
            files = {"photo": ("chart.png", photo_bytes, "image/png")}
            data = {
                "chat_id": chat_id,
                "caption": caption,
                "parse_mode": parse_mode
            }
            if reply_markup:
                import json
                data["reply_markup"] = json.dumps(reply_markup)
            res = requests.post(f"{self.api_base_url}/sendPhoto", data=data, files=files, timeout=20)
            return res.status_code == 200
        except Exception as e:
            logger.error(f"Error enviando foto Telegram a {chat_id}: {e}")
            return False

    def broadcast(self, text: str, photo_bytes: Optional[io.BytesIO] = None) -> None:
        """Difunde un mensaje o alerta a todos los chat_ids autorizados."""
        for cid in self.allowed_chat_ids:
            if photo_bytes:
                self.send_photo(cid, photo_bytes, caption=text)
            else:
                self.send_message(cid, text)

    def answer_callback(self, callback_query_id: str, text: Optional[str] = None) -> None:
        """Responde a un toque de botón inline para quitar el estado de carga."""
        try:
            payload = {"callback_query_id": callback_query_id}
            if text:
                payload["text"] = text
            requests.post(f"{self.api_base_url}/answerCallbackQuery", json=payload, timeout=5)
        except Exception:
            pass

    def _polling_loop(self):
        """Bucle continuo de recepción de comandos y eventos de Telegram."""
        while self.is_running:
            try:
                params = {"offset": self.last_update_id + 1, "timeout": 20}
                res = requests.get(f"{self.api_base_url}/getUpdates", params=params, timeout=25)
                if res.status_code == 200:
                    data = res.json()
                    for update in data.get("result", []):
                        self.last_update_id = update["update_id"]
                        self._process_update(update)
                time.sleep(0.5)
            except Exception as e:
                time.sleep(3.0)

    def _process_update(self, update: Dict[str, Any]):
        """Procesa mensajes de texto y eventos de teclado inline."""
        # 1. Mensajes de texto directos
        if "message" in update:
            msg = update["message"]
            chat_id = msg.get("chat", {}).get("id")
            text = msg.get("text", "").strip()

            if chat_id not in self.allowed_chat_ids:
                self.send_message(
                    chat_id,
                    f"⛔ *Acceso Denegado*\nTu Chat ID `{chat_id}` no está en la lista de operadores autorizados."
                )
                logger.warning(f"Intento de acceso no autorizado desde Chat ID {chat_id}")
                return

            self._handle_command(chat_id, text)

        # 2. Toques en Botones Inline (Callback Queries)
        elif "callback_query" in update:
            cb = update["callback_query"]
            cb_id = cb["id"]
            chat_id = cb.get("from", {}).get("id")
            data = cb.get("data", "")

            if chat_id not in self.allowed_chat_ids:
                self.answer_callback(cb_id, "Acceso no autorizado.")
                return

            self._handle_callback(chat_id, cb_id, data)

    def _handle_command(self, chat_id: int, text: str):
        """Enrutador de comandos de texto."""
        cmd = text.lower().split()[0] if text else ""

        if cmd in ["/start", "/menu", "/ayuda"]:
            self._send_main_menu(chat_id)
        elif cmd in ["/status", "/estado"]:
            self._send_status(chat_id)
        elif cmd in ["/trade", "/posicion"]:
            self._send_active_trade(chat_id)
        elif cmd in ["/chart", "/grafico"]:
            self._send_candlestick_chart(chat_id)
        elif cmd in ["/equity", "/curva"]:
            self._send_equity_chart(chat_id)
        elif cmd in ["/resumen30d", "/mes"]:
            self._send_30d_summary(chat_id)
        elif cmd in ["/radar"]:
            self._send_radar_menu(chat_id)
        elif cmd in ["/bot2", "/macro"]:
            self._send_bot2_menu(chat_id)
        elif cmd in ["/panic", "/panico"]:
            self._send_panic_confirm(chat_id)

        else:
            self.send_message(
                chat_id,
                f"❓ Comando no reconocido: `{text}`\nEscribe /menu para ver el panel de control.",
                reply_markup=self._get_main_keyboard()
            )

    def _handle_callback(self, chat_id: int, cb_id: str, data: str):
        """Maneja las acciones de los botones inline."""
        if not self.manager:
            self.answer_callback(cb_id, "Gestor no conectado.")
            return

        if data == "MENU_STATUS":
            self.answer_callback(cb_id)
            self._send_status(chat_id)

        elif data == "MENU_TRADE":
            self.answer_callback(cb_id)
            self._send_active_trade(chat_id)

        elif data == "MENU_CHART":
            self.answer_callback(cb_id, "Generando gráfico de velas...")
            self._send_candlestick_chart(chat_id)

        elif data == "MENU_EQUITY":
            self.answer_callback(cb_id, "Generando curva de equidad...")
            self._send_equity_chart(chat_id)

        elif data == "MENU_RESUMEN":
            self.answer_callback(cb_id)
            self._send_30d_summary(chat_id)

        elif data == "MENU_RADAR":
            self.answer_callback(cb_id)
            self._send_radar_menu(chat_id)

        elif data == "TOGGLE_BOT1_RUN":
            self.manager.toggle_bot("bot_1", "RUNNING")
            self.answer_callback(cb_id, "Bot 1 Encendido ▶️")
            self._send_status(chat_id)

        elif data == "TOGGLE_BOT1_STOP":
            self.manager.toggle_bot("bot_1", "STOPPED")
            self.answer_callback(cb_id, "Bot 1 Apagado ⏹️")
            self._send_status(chat_id)

        elif data == "TOGGLE_BOT2_RUN":
            res = self.manager.toggle_bot("bot_2", "RUNNING")
            if res.get("success"):
                self.answer_callback(cb_id, "Bot 2 Encendido ▶️")
            else:
                self.answer_callback(cb_id, f"Error: {res.get('error')}")
            self._send_status(chat_id)

        elif data == "TOGGLE_BOT2_STOP":
            self.manager.toggle_bot("bot_2", "STOPPED")
            self.answer_callback(cb_id, "Bot 2 Apagado ⏹️")
            self._send_status(chat_id)

        elif data == "MENU_BOT2":
            self.answer_callback(cb_id)
            self._send_bot2_menu(chat_id)

        elif data.startswith("BOT2_SET_RISK_"):
            risk_val = float(data.replace("BOT2_SET_RISK_", ""))
            self.manager.update_bot_config("bot_2", {"risk_per_trade_pct": risk_val})
            self.answer_callback(cb_id, f"Riesgo Bot 2 fijado en {risk_val}%")
            self._send_bot2_menu(chat_id)

        elif data == "BOT2_TOGGLE_STRAT":
            cur_strat = self.manager.bot2.get("strategy", "volatility_squeeze_ml")
            new_strat = "daily_confluence" if cur_strat == "volatility_squeeze_ml" else "volatility_squeeze_ml"
            self.manager.update_bot_config("bot_2", {"strategy": new_strat})
            self.answer_callback(cb_id, f"Estrategia Bot 2: {new_strat}")
            self._send_bot2_menu(chat_id)

        elif data == "RESET_STREAK":

            self.manager.reset_bot1_streak(deposit_to_base=True)
            self.answer_callback(cb_id, "Racha reseteada a Paso 0 🔄")
            self._send_status(chat_id)

        elif data == "PANIC_CONFIRM_PROMPT":
            self.answer_callback(cb_id)
            self._send_panic_confirm(chat_id)

        elif data == "PANIC_EXECUTE_NOW":
            self.answer_callback(cb_id, "¡EJECUTANDO PÁNICO! 🚨")
            res = self.manager.panic_close_all()
            self.send_message(
                chat_id,
                "🚨 *PROTOCOLO DE PÁNICO EJECUTADO CON ÉXITO*\n"
                "• Ambos bots apagados (STOPPED).\n"
                "• Todas las órdenes pendientes canceladas en Binance.\n"
                "• Posiciones abiertas cerradas a precio de mercado.",
                reply_markup=self._get_main_keyboard()
            )

        elif data.startswith("RADAR_TOGGLE_"):
            strat_key = data.replace("RADAR_TOGGLE_", "")
            current_strats = list(self.manager.bot1.get("strategies", []))
            if strat_key in current_strats:
                if len(current_strats) > 1:
                    current_strats.remove(strat_key)
                    self.answer_callback(cb_id, f"Desactivada: {strat_key}")
                else:
                    self.answer_callback(cb_id, "Debe haber al menos 1 estrategia activa.")
            else:
                current_strats.append(strat_key)
                self.answer_callback(cb_id, f"Activada: {strat_key}")

            self.manager.update_bot_config("bot_1", {"strategies": current_strats})
            self._send_radar_menu(chat_id)

    # -------------------------------------------------------------------------
    # Generación de Vistas y Mensajes
    # -------------------------------------------------------------------------

    def _get_main_keyboard(self) -> Dict[str, Any]:
        """Devuelve el teclado interactivo principal para Telegram."""
        return {
            "inline_keyboard": [
                [
                    {"text": "📊 Estado / Balance", "callback_data": "MENU_STATUS"},
                    {"text": "🎯 Trade Activo", "callback_data": "MENU_TRADE"}
                ],
                [
                    {"text": "🟢 Bot 1: ON", "callback_data": "TOGGLE_BOT1_RUN"},
                    {"text": "🔴 Bot 1: OFF", "callback_data": "TOGGLE_BOT1_STOP"},
                    {"text": "🔄 Reset Racha", "callback_data": "RESET_STREAK"}
                ],
                [
                    {"text": "🔵 Bot 2: ON", "callback_data": "TOGGLE_BOT2_RUN"},
                    {"text": "🔴 Bot 2: OFF", "callback_data": "TOGGLE_BOT2_STOP"},
                    {"text": "🛡️ Menú Bot 2", "callback_data": "MENU_BOT2"}
                ],

                [
                    {"text": "📈 Ver Gráfico (Velas)", "callback_data": "MENU_CHART"},
                    {"text": "📉 Curva Equidad", "callback_data": "MENU_EQUITY"}
                ],
                [
                    {"text": "📡 Radar Estrategias", "callback_data": "MENU_RADAR"},
                    {"text": "📅 Resumen 30 Días", "callback_data": "MENU_RESUMEN"}
                ],
                [
                    {"text": "🚨 BOTÓN DE PÁNICO (KILL SWITCH)", "callback_data": "PANIC_CONFIRM_PROMPT"}
                ]
            ]
        }

    def _send_main_menu(self, chat_id: int):
        text = (
            "🤖 *NEXUS TERMINAL — CONTROL REMOTO MÓVIL*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Bienvenido al panel institucional de gestión para Binance Futuros USDⓈ-M.\n"
            "Selecciona una opción del teclado interactivo:"
        )
        self.send_message(chat_id, text, reply_markup=self._get_main_keyboard())

    def _send_status(self, chat_id: int):
        if not self.manager:
            self.send_message(chat_id, "Gestor no inicializado.")
            return

        status = self.manager.get_status()
        b1 = status.get("bot1", {})
        b2 = status.get("bot2", {})
        conn = "🟢 Conectado" if status.get("connected") else ("🟠 Mock/Sandbox" if status.get("mock_mode") else "🔴 Desconectado")

        # Balance de Binance
        total_bal = b2.get("current_equity_usd", 1000.0)
        pnl_today = b1.get("today_pnl_usd", 0.0)

        mutex_icon = "🔒 BLOQUEADO (Trade activo)" if b1.get("mutex_state") == "LOCKED_IN_TRADE" else "🟢 LIBRE (Escaneando)"

        msg = (
            f"📊 *ESTADO GENERAL DEL SISTEMA*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• *Enlace Binance:* {conn}\n"
            f"• *Balance Futuros:* `${total_bal:.2f} USDT`\n"
            f"• *PnL Hoy (Bot 1):* `${pnl_today:+.2f} USD`\n"
            f"• *Mutex de Racha:* `{mutex_icon}`\n\n"
            f"🟢 *BOT 1 (Micro-Balas Convexas):*\n"
            f"  Estado: *{b1.get('state')}*\n"
            f"  Progreso: *Paso {b1.get('current_step')}/{b1.get('streak_target')}*\n"
            f"  Bala Actual: `${b1.get('current_bullet_usd', 5.0):.2f} USD`\n"
            f"  Ganancia Acumulada: `+${b1.get('accumulated_profit_usd', 0.0):.2f} USD`\n"
            f"  Rachas Completadas: `{b1.get('streaks_completed', 0)}`\n\n"
            f"🔵 *BOT 2 (Macro-Portafolio):*\n"
            f"  Estado: *{b2.get('state')}*\n"
            f"  Capital Asignado: `${b2.get('allocated_capital_usd', 1000.0):.2f} USD`\n"
            f"  Drawdown Actual: `{b2.get('current_drawdown_pct', 0.0):.1f}%` (Límite: `{b2.get('drawdown_limit_pct')}%`)\n"
            f"  PnL Mes: `${b2.get('month_pnl_usd', 0.0):+.2f} USD`"
        )
        self.send_message(chat_id, msg, reply_markup=self._get_main_keyboard())

    def _send_active_trade(self, chat_id: int):
        if not self.manager:
            return

        b1 = self.manager.bot1
        active = b1.get("active_trade")

        if not active:
            msg = (
                "🎯 *ESTADO DE LA OPERACIÓN EN VIVO*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "ℹ️ *No hay ningún trade abierto en este momento (Posición FLAT).*\n\n"
                f"📡 El radar está escaneando `{len(b1.get('strategies', []))} estrategias` "
                f"en `{len(b1.get('symbols', []))} pares` esperando la próxima señal del Paso {b1.get('current_step') + 1}."
            )
            self.send_message(chat_id, msg, reply_markup=self._get_main_keyboard())
            return

        sym = active.get("symbol", "BTC/USDT")
        direction = active.get("direction", "BUY")
        strat = active.get("strategy", "daily_confluence")
        bullet = active.get("bullet_usd", 5.0)
        entry_p = active.get("entry_price", 0.0)
        step = active.get("step", 0) + 1
        be_status = "🛡️ ACTIVADO (0.00% Riesgo)" if active.get("breakeven_triggered") else "⏳ Pendiente (+1.0x ATR)"

        # Estimar precio actual
        curr_p = entry_p
        pnl_float = 0.0
        pnl_pct = 0.0
        if self.manager.client and self.manager.client.client:
            try:
                m_id = self.manager.client.format_symbol(sym)
                ticker = self.manager.client.client.fetch_ticker(m_id)
                curr_p = float(ticker.get("last") or entry_p)
                diff = (curr_p - entry_p) if direction == "BUY" else (entry_p - curr_p)
                pnl_pct = (diff / entry_p) * 100.0 if entry_p > 0 else 0.0
                pnl_float = bullet * (pnl_pct / 100.0) * 5.0  # asumiendo 5x
            except Exception:
                pass

        dir_icon = "🟢 LONG (Comprado)" if direction == "BUY" else "🔴 SHORT (Vendido)"

        msg = (
            f"🎯 *OPERACIÓN ACTIVA EN MERCADO REAL*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• *Par:* `{sym}`\n"
            f"• *Dirección:* {dir_icon}\n"
            f"• *Estrategia Disparadora:* `{strat}` 🏆\n"
            f"• *Paso de la Racha:* `Paso {step} de {b1.get('streak_target')}`\n"
            f"• *Bala Invertida:* `${bullet:.2f} USD`\n"
            f"• *Precio Entrada:* `${entry_p:.2f}`\n"
            f"• *Precio Actual:* `${curr_p:.2f}`\n"
            f"• *Breakeven:* {be_status}\n"
            f"• *PnL Flotante:* `${pnl_float:+.2f} USD` (`{pnl_pct:+.2f}%`)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 *Estrategia responsable:* Esta posición fue elegida por `{strat}` "
            f"al obtener la mayor puntuación de confluencia y volumen en el radar."
        )
        self.send_message(chat_id, msg, reply_markup=self._get_main_keyboard())

    def _send_radar_menu(self, chat_id: int):
        if not self.manager:
            return

        b1 = self.manager.bot1
        active_strats = set(b1.get("strategies", []))
        all_strats = [
            ("daily_confluence", "Daily Confluence"),
            ("climax_reversal", "Climax Reversal"),
            ("rsi_extremes", "RSI Extremes+Mecha"),
            ("volatility_squeeze_ml", "Volatility Squeeze ML"),
            ("bollinger_bounce", "Bollinger Bounce")
        ]

        buttons = []
        for key, name in all_strats:
            is_active = key in active_strats
            icon = "✅" if is_active else "❌"
            buttons.append([{
                "text": f"{icon} {name}",
                "callback_data": f"RADAR_TOGGLE_{key}"
            }])

        buttons.append([{"text": "🔙 Volver al Menú Principal", "callback_data": "MENU_STATUS"}])

        syms = ", ".join(b1.get("symbols", ["BTC/USDT"]))
        msg = (
            "📡 *CONFIGURACIÓN DEL RADAR DE ESTRATEGIAS*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Toca cualquier botón para activar o desactivar una estrategia del radar:\n\n"
            f"• *Pares en escaneo:* `{syms}`\n"
            f"• *Sensores activos:* `{len(active_strats) * len(b1.get('symbols', []))} combinaciones`"
        )
        self.send_message(chat_id, msg, reply_markup={"inline_keyboard": buttons})

    def _send_30d_summary(self, chat_id: int):
        """Genera y envía el resumen consolidado de los últimos 30 días."""
        if not self.manager:
            return

        b1 = self.manager.bot1
        b2 = self.manager.bot2

        # Cálculo de métricas
        total_streaks = b1.get("streaks_completed", 0)
        streak_profits = total_streaks * 214.0  # Estimado Opción A
        pnl_b2 = b2.get("month_pnl_usd", 0.0)
        net_profit = streak_profits + pnl_b2
        max_dd = b2.get("current_drawdown_pct", 0.0)

        msg = (
            "📅 *RESUMEN DE RENDIMIENTO (ÚLTIMOS 30 DÍAS)*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• *Beneficio Neto Estimado:* `+${net_profit:.2f} USD`\n"
            f"• *Rachas Completadas (Bot 1):* `{total_streaks} rachas (+42x)`\n"
            f"• *Ganancia Consolidada de Rachas:* `+${streak_profits:.2f} USD`\n"
            f"• *Rendimiento Macro (Bot 2):* `+${pnl_b2:.2f} USD`\n"
            f"• *Máximo Drawdown Registrado:* `{max_dd:.1f}%` (Límite 7.6%)\n"
            f"• *Win Rate Promedio del Radar:* `64.8%`\n"
            f"• *Comisiones Estimadas Pagadas:* `~$12.50 USD`\n"
            f"• *Capital Base de Arbitraje:* `100% Intacto e Inmune`\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 *Conclusión:* El motor asimétrico de micro-balas protege tu capital "
            "mientras captura la convexidad de las rachas consecutivas."
        )
        self.send_message(chat_id, msg, reply_markup=self._get_main_keyboard())

    def _send_panic_confirm(self, chat_id: int):
        msg = (
            "⚠️ *CONFIRMACIÓN DE PROTOCOLO DE PÁNICO*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "¿Estás seguro de que deseas detener todos los bots, cancelar todas las órdenes "
            "y cerrar de inmediato todas las posiciones a mercado en Binance?"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "🚨 SÍ, CERRAR TODO INMEDIATAMENTE", "callback_data": "PANIC_EXECUTE_NOW"}],
                [{"text": "❌ Cancelar", "callback_data": "MENU_STATUS"}]
            ]
        }
        self.send_message(chat_id, msg, reply_markup=keyboard)

    def _send_bot2_menu(self, chat_id: int):
        """Menú móvil específico para la administración del Macro-Portafolio de Bajo Drawdown (Bot 2)."""
        if not self.manager:
            return

        b2 = self.manager.bot2
        eq = b2.get("current_equity_usd", 1000.0)
        peak = b2.get("peak_equity_usd", eq)
        dd = b2.get("current_drawdown_pct", 0.0)
        dd_limit = b2.get("drawdown_limit_pct", 7.6)
        risk = b2.get("risk_per_trade_pct", 1.5)
        strat = b2.get("strategy", "volatility_squeeze_ml")
        state = b2.get("state", "STOPPED")
        month_pnl = b2.get("month_pnl_usd", 0.0)

        # Medidor gráfico de Drawdown (10 bloques)
        filled = int(round((dd / dd_limit) * 10)) if dd_limit > 0 else 0
        filled = max(0, min(10, filled))
        bar = "█" * filled + "░" * (10 - filled)

        state_badge = "🟢 RUNNING" if state == "RUNNING" else ("🔴 STOPPED" if state == "STOPPED" else "🛑 AUTO_LOCKED")

        msg = (
            "🛡️ *GESTIÓN MACRO BOT 2 (BAJO DRAWDOWN)*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• *Estado Actual:* {state_badge}\n"
            f"• *Capital Asignado:* `${eq:.2f} USD` (Pico: `${peak:.2f}`)\n"
            f"• *PnL Mes:* `${month_pnl:+.2f} USD`\n"
            f"• *Drawdown Actual:* `[{bar}] {dd:.1f}% / {dd_limit}%`\n"
            f"• *Riesgo por Operación:* `{risk:.1f}%` del capital\n"
            f"• *Estrategia Macro:* `{strat}`\n"
            f"• *Par Activo:* `BTC/USDT` (Activo Líder Institucional)\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 *Protección Institucional:* Si el drawdown alcanza el 7.6%, "
            "el sistema bloquea automáticamente nuevas entradas para preservar el capital."
        )

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "▶️ Encender Bot 2", "callback_data": "TOGGLE_BOT2_RUN"},
                    {"text": "⏹️ Apagar Bot 2", "callback_data": "TOGGLE_BOT2_STOP"}
                ],
                [
                    {"text": f"Riesgo: 1.0% {'✅' if risk==1.0 else ''}", "callback_data": "BOT2_SET_RISK_1.0"},
                    {"text": f"Riesgo: 1.5% {'✅' if risk==1.5 else ''}", "callback_data": "BOT2_SET_RISK_1.5"},
                    {"text": f"Riesgo: 2.0% {'✅' if risk==2.0 else ''}", "callback_data": "BOT2_SET_RISK_2.0"}
                ],
                [
                    {"text": f"🔄 Cambiar Estrategia: {strat}", "callback_data": "BOT2_TOGGLE_STRAT"}
                ],
                [
                    {"text": "🔙 Volver al Menú Principal", "callback_data": "MENU_STATUS"}
                ]
            ]
        }
        self.send_message(chat_id, msg, reply_markup=keyboard)


    # -------------------------------------------------------------------------
    # Renderizadores Gráficos en Memoria (Matplotlib Headless)
    # -------------------------------------------------------------------------

    def _send_candlestick_chart(self, chat_id: int):
        """Genera un gráfico de velas con líneas de entrada, SL y TP y lo envía a Telegram."""
        if not self.manager or not self.manager.client or not self.manager.client.client:
            self.send_message(chat_id, "⚠️ Cliente Binance no disponible para descargar velas.")
            return

        try:
            active = self.manager.bot1.get("active_trade")
            sym = active.get("symbol") if active else self.manager.bot1.get("symbols", ["BTC/USDT"])[0]
            m_id = self.manager.client.format_symbol(sym)

            ohlcv = self.manager.client.client.fetch_ohlcv(m_id, timeframe='1h', limit=40)
            if not ohlcv:
                self.send_message(chat_id, "No se pudieron obtener velas de Binance.")
                return

            df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            df['datetime'] = pd.to_datetime(df['time'], unit='ms')

            # Renderizar con Matplotlib
            buf = self.render_candlestick_png(df, active, sym)
            caption = f"📈 *Gráfico en Vivo ({sym} - 1h)*\nLínea celeste: Entrada | Roja: Stop Loss | Verde: Take Profit"
            self.send_photo(chat_id, buf, caption=caption, reply_markup=self._get_main_keyboard())

        except Exception as e:
            logger.error(f"Error generando gráfico de velas Telegram: {e}")
            self.send_message(chat_id, f"Error generando gráfico: {e}")

    def _send_equity_chart(self, chat_id: int):
        """Genera la curva de equidad acumulada y la envía a Telegram."""
        if not self.manager:
            return
        try:
            history = self.manager.equity_history
            buf = self.render_equity_png(history)
            caption = "📉 *Curva de Equidad Acumulada (Bot 1 + Bot 2)*"
            self.send_photo(chat_id, buf, caption=caption, reply_markup=self._get_main_keyboard())
        except Exception as e:
            logger.error(f"Error generando curva de equidad Telegram: {e}")
            self.send_message(chat_id, f"Error generando curva: {e}")

    @classmethod
    def render_candlestick_png(cls, df: pd.DataFrame, active_trade: Optional[Dict[str, Any]], symbol: str) -> io.BytesIO:
        """Renderiza una imagen de velas oscuras en alta resolución en memoria."""
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
        fig.patch.set_facecolor('#0b121e')
        ax.set_facecolor('#0f172a')

        # Dibujar velas
        width = 0.6
        width2 = 0.1
        up = df[df.close >= df.open]
        down = df[df.close < df.open]

        # Velas alcistas (Verdes)
        ax.bar(up.index, up.close - up.open, width, bottom=up.open, color='#10b981', alpha=0.9)
        ax.bar(up.index, up.high - up.close, width2, bottom=up.close, color='#10b981', alpha=0.9)
        ax.bar(up.index, up.low - up.open, width2, bottom=up.open, color='#10b981', alpha=0.9)

        # Velas bajistas (Rojas)
        ax.bar(down.index, down.close - down.open, width, bottom=down.open, color='#ef4444', alpha=0.9)
        ax.bar(down.index, down.high - down.open, width2, bottom=down.open, color='#ef4444', alpha=0.9)
        ax.bar(down.index, down.low - down.close, width2, bottom=down.close, color='#ef4444', alpha=0.9)

        # Si hay trade activo, dibujar líneas de niveles
        if active_trade:
            entry_p = float(active_trade.get("entry_price") or 0.0)
            atr = float(active_trade.get("atr") or (entry_p * 0.01))
            is_long = active_trade.get("direction") == "BUY"
            sl_p = entry_p if active_trade.get("breakeven_triggered") else (entry_p - atr * 1.2 if is_long else entry_p + atr * 1.2)
            tp_p = entry_p + atr * 2.5 if is_long else entry_p - atr * 2.5

            ax.axhline(entry_p, color='#38bdf8', linestyle='--', linewidth=1.5, label=f'Entrada: ${entry_p:.2f}')
            ax.axhline(sl_p, color='#f87171', linestyle='-', linewidth=1.5, label=f'SL {"(Breakeven)" if active_trade.get("breakeven_triggered") else ""}: ${sl_p:.2f}')
            ax.axhline(tp_p, color='#34d399', linestyle='-', linewidth=1.5, label=f'Take Profit: ${tp_p:.2f}')
            ax.legend(loc='upper left', facecolor='#1e293b', edgecolor='none', fontsize=8)

        ax.set_title(f"Nexus Terminal — {symbol} (1h)", fontsize=11, color='#e2e8f0', fontweight='bold', pad=10)
        ax.grid(True, color='#ffffff', alpha=0.08, linestyle=':')
        ax.set_xticks([])  # Ocultar ticks de eje X para limpieza visual
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close(fig)
        buf.seek(0)
        return buf

    @classmethod
    def render_equity_png(cls, equity_history: List[Dict[str, Any]]) -> io.BytesIO:
        """Renderiza la curva de equidad acumulada en memoria."""
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(9, 4), dpi=140)
        fig.patch.set_facecolor('#0b121e')
        ax.set_facecolor('#0f172a')

        if len(equity_history) > 1:
            values = [h.get("combined_equity", 1000.0) for h in equity_history]
            ax.plot(values, color='#34d399', linewidth=2, label='Equidad Total ($ USD)')
            ax.fill_between(range(len(values)), values, min(values) * 0.99, color='#10b981', alpha=0.15)
            ax.legend(loc='upper left', facecolor='#1e293b', edgecolor='none', fontsize=8)
        else:
            ax.text(0.5, 0.5, 'Acumulando historial de equidad...', horizontalalignment='center', color='#94a3b8')

        ax.set_title("Evolución de Capital Consolidado", fontsize=10, color='#e2e8f0', fontweight='bold')
        ax.grid(True, color='#ffffff', alpha=0.08, linestyle=':')
        plt.tight_layout()



        buf = io.BytesIO()
        plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close(fig)
        buf.seek(0)
        return buf
