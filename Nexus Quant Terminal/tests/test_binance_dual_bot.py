"""
tests/test_binance_dual_bot.py
Tests para el cliente de Binance Futures, el gestor Dual-Bot y sus endpoints.
"""

import unittest
from unittest.mock import MagicMock, patch
from app import app
from engine.execution.binance_client import BinanceFuturesClient
from engine.execution.dual_bot_manager import DualBotManager


class TestBinanceDualBot(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.manager = DualBotManager()
        # Reset state for tests
        self.manager.bot1["state"] = "STOPPED"
        self.manager.bot1["current_step"] = 0
        self.manager.bot1["current_bullet_usd"] = 5.0
        self.manager.bot1["accumulated_profit_usd"] = 0.0
        self.manager.bot2["state"] = "STOPPED"
        self.manager.bot2["current_equity_usd"] = 1000.0
        self.manager.bot2["peak_equity_usd"] = 1000.0
        self.manager.bot2["current_drawdown_pct"] = 0.0

    def test_binance_client_unconfigured(self):
        """Cliente sin credenciales debe reportar desconectado."""
        client = BinanceFuturesClient()
        self.assertFalse(client.connected)
        res = client.test_connection()
        self.assertFalse(res["success"])
        self.assertIn("no configuradas", res["error"])

    @patch("engine.execution.binance_client.ccxt.binance")
    def test_binance_client_configured_mock(self, mock_ccxt):
        """Cliente con credenciales simuladas en ccxt."""
        mock_instance = MagicMock()
        mock_instance.fetch_time.return_value = 1700000000000
        mock_instance.fetch_balance.return_value = {
            'USDT': {'free': 250.0, 'total': 250.0}
        }
        mock_ccxt.return_value = mock_instance

        client = BinanceFuturesClient(api_key="mock_key", api_secret="mock_sec", testnet=True)
        self.assertTrue(client.connected)
        res = client.test_connection()
        self.assertTrue(res["success"])
        self.assertEqual(res["usdt_balance"], 250.0)
        self.assertTrue(res["p2p_isolated"])

    def test_dual_bot_manager_toggle_states(self):
        """Verificar transiciones de estado de Bot 1 y Bot 2."""
        res = self.manager.toggle_bot("bot_1", "RUNNING")
        self.assertTrue(res["success"])
        self.assertEqual(self.manager.bot1["state"], "RUNNING")

        res_p = self.manager.toggle_bot("bot_1", "PAUSED")
        self.assertTrue(res_p["success"])
        self.assertEqual(self.manager.bot1["state"], "PAUSED")

        res_inv = self.manager.toggle_bot("bot_1", "INVALID_STATE")
        self.assertFalse(res_inv["success"])

    def test_bot1_streak_progression_and_compounding(self):
        """Bot 1 avanza en la racha, compone la bala y consolida al completar."""
        b1 = self.manager.bot1
        b1["daily_bullet_usd"] = 5.0
        b1["current_bullet_usd"] = 5.0
        b1["streak_target"] = 3
        b1["rr_ratio"] = 2.5

        # Trade 1: WIN
        self.manager.record_simulated_trade("bot_1", is_win=True, pnl_usd=12.50)
        self.assertEqual(b1["current_step"], 1)
        self.assertAlmostEqual(b1["current_bullet_usd"], 5.0 * 3.5, places=1)  # $17.50

        # Trade 2: WIN
        self.manager.record_simulated_trade("bot_1", is_win=True, pnl_usd=43.75)
        self.assertEqual(b1["current_step"], 2)

        # Trade 3: WIN -> Completa racha!
        self.manager.record_simulated_trade("bot_1", is_win=True, pnl_usd=153.12)
        self.assertEqual(b1["current_step"], 0)  # Resetea racha a 0
        self.assertEqual(b1["streaks_completed"], 1)
        self.assertEqual(b1["current_bullet_usd"], 5.0)  # Vuelve a bala base

    def test_bot1_streak_loss_resets_bullet(self):
        """Bot 1 ante pérdida resetea la racha a 0 y bala a base sin tocar patrimonio."""
        b1 = self.manager.bot1
        b1["current_step"] = 2
        b1["current_bullet_usd"] = 61.25

        # Trade 3: LOSS
        self.manager.record_simulated_trade("bot_1", is_win=False, pnl_usd=0.0)
        self.assertEqual(b1["current_step"], 0)
        self.assertEqual(b1["current_bullet_usd"], 5.0)
        self.assertEqual(b1["accumulated_profit_usd"], 0.0)

    def test_bot2_drawdown_auto_lockdown(self):
        """Bot 2 al superar el límite de Drawdown (7.6%) se bloquea automáticamente."""
        b2 = self.manager.bot2
        b2["state"] = "RUNNING"
        b2["current_equity_usd"] = 1000.0
        b2["peak_equity_usd"] = 1000.0

        # Simular pérdida que lleva a Drawdown del 8.0% (> 7.6%)
        self.manager.record_simulated_trade("bot_2", is_win=False, pnl_usd=-80.0)
        self.assertEqual(b2["current_equity_usd"], 920.0)
        self.assertAlmostEqual(b2["current_drawdown_pct"], 8.0, places=1)
        self.assertEqual(b2["state"], "AUTO_LOCKED")

        # Intentar reactivar debe ser rechazado
        toggle_res = self.manager.toggle_bot("bot_2", "RUNNING")
        self.assertFalse(toggle_res["success"])
        self.assertIn("Drawdown actual", toggle_res["error"])

    def test_panic_close_all(self):
        """Botón de Pánico detiene ambos bots inmediatamente."""
        self.manager.bot1["state"] = "RUNNING"
        self.manager.bot2["state"] = "RUNNING"

        res = self.manager.panic_close_all()
        self.assertTrue(res["success"])
        self.assertEqual(self.manager.bot1["state"], "STOPPED")
        self.assertEqual(self.manager.bot2["state"], "STOPPED")

    def test_api_routes_status_and_toggle(self):
        """Endpoints REST devuelven respuestas válidas y actualizan estado."""
        # 1. GET status
        r = self.app.get('/api/execution/status')
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("bot1", data)
        self.assertIn("bot2", data)
        self.assertIn("equity_history", data)

        # 2. POST toggle-bot
        r_post = self.app.post('/api/execution/toggle-bot', json={
            "bot_id": "bot_1",
            "state": "RUNNING"
        })
        self.assertEqual(r_post.status_code, 200)
        self.assertEqual(r_post.get_json()["state"], "RUNNING")

        # 3. POST panic-close
        r_panic = self.app.post('/api/execution/panic-close')
        self.assertEqual(r_panic.status_code, 200)
        self.assertEqual(self.manager.bot1["state"], "STOPPED")

    @patch("engine.execution.binance_client.ccxt.binance")
    def test_bracket_order_call_maps_to_buy_and_put_maps_to_sell(self, mock_ccxt):
        """Verificar que 'CALL' se traduzca en 'buy' y 'PUT' se traduzca en 'sell'."""
        mock_inst = MagicMock()
        mock_inst.fetch_ticker.return_value = {'last': 65000.0}
        mock_inst.market.return_value = {
            'precision': {'amount': 3, 'price': 1},
            'limits': {'amount': {'min': 0.001}, 'cost': {'min': 5.0}}
        }
        mock_inst.amount_to_precision.side_effect = lambda sym, amt: f"{amt:.3f}"
        mock_inst.price_to_precision.side_effect = lambda sym, p: f"{p:.1f}"
        mock_inst.create_order.return_value = {'id': '12345', 'filled': 0.001}
        mock_ccxt.return_value = mock_inst

        client = BinanceFuturesClient(api_key="k", api_secret="s", testnet=True)

        # 1. Probar CALL -> buy
        res_call = client.place_bracket_order(
            symbol="BTCUSDT",
            direction="CALL",
            budget_usd=10.0,
            sl_price=64000.0,
            tp_price=67500.0,
            leverage=10
        )
        self.assertTrue(res_call["success"])
        self.assertEqual(res_call["side"], "buy")

        # 2. Probar PUT -> sell
        res_put = client.place_bracket_order(
            symbol="BTCUSDT",
            direction="PUT",
            budget_usd=10.0,
            sl_price=66000.0,
            tp_price=62500.0,
            leverage=10
        )
        self.assertTrue(res_put["success"])
        self.assertEqual(res_put["side"], "sell")

    @patch("engine.execution.binance_client.ccxt.binance")
    def test_bracket_rollback_on_sl_failure(self, mock_ccxt):
        """Si la orden de entrada entra pero falla el Stop Loss, debe ejecutarse Rollback de emergencia."""
        mock_inst = MagicMock()
        mock_inst.fetch_ticker.return_value = {'last': 65000.0}
        mock_inst.market.return_value = {
            'precision': {'amount': 3, 'price': 1},
            'limits': {'amount': {'min': 0.001}, 'cost': {'min': 5.0}}
        }
        mock_inst.amount_to_precision.side_effect = lambda sym, amt: f"{amt:.3f}"
        mock_inst.price_to_precision.side_effect = lambda sym, p: f"{p:.1f}"

        # Entrada exitosa, pero el SL lanza excepción
        def create_order_side_effect(symbol, type, side, amount, params):
            if type == 'market' and not params.get('reduceOnly'):
                return {'id': 'entry_order_999', 'filled': 0.001}
            elif type == 'STOP_MARKET':
                raise Exception("Error de red al colocar Stop Loss")
            elif params.get('reduceOnly'):
                return {'id': 'rollback_close_order'}
            return {}

        mock_inst.create_order.side_effect = create_order_side_effect
        mock_ccxt.return_value = mock_inst

        client = BinanceFuturesClient(api_key="k", api_secret="s", testnet=True)
        res = client.place_bracket_order(
            symbol="BTCUSDT",
            direction="CALL",
            budget_usd=10.0,
            sl_price=64000.0,
            tp_price=67500.0,
            leverage=10
        )
        self.assertFalse(res["success"])
        self.assertIn("Posición cerrada por seguridad", res["error"])
        # Verificar que se llamó a cancelar y cerrar a mercado
        mock_inst.cancel_all_orders.assert_called()

    @patch("engine.execution.binance_client.ccxt.binance")
    def test_purge_orphan_orders_when_flat(self, mock_ccxt):
        """Si la posición en el par es 0.0, purge_orphan_orders_if_flat debe cancelar órdenes residuales."""
        mock_inst = MagicMock()
        # Posición 0.0
        mock_inst.fetch_positions.return_value = [
            {'symbol': 'BTC/USDT:USDT', 'info': {'positionAmt': '0.0'}}
        ]
        mock_inst.fetch_open_orders.return_value = [{'id': 'orphan_sl_1'}]
        mock_ccxt.return_value = mock_inst

        client = BinanceFuturesClient(api_key="k", api_secret="s", testnet=True)
        purged = client.purge_orphan_orders_if_flat("BTCUSDT")
        self.assertTrue(purged)
        mock_inst.cancel_all_orders.assert_called_with('BTC/USDT:USDT')

    @patch("engine.execution.binance_client.ccxt.binance")
    def test_kill_switch_respects_signed_position_amount(self, mock_ccxt):
        """Kill switch debe vender si positionAmt > 0 y comprar si positionAmt < 0."""
        mock_inst = MagicMock()
        mock_inst.fetch_positions.return_value = [
            {'symbol': 'BTC/USDT:USDT', 'info': {'positionAmt': '0.005'}},  # Long
            {'symbol': 'ETH/USDT:USDT', 'info': {'positionAmt': '-0.10'}}   # Short
        ]
        mock_inst.amount_to_precision.side_effect = lambda sym, amt: f"{amt}"
        mock_inst.create_order.return_value = {'id': 'close_ok'}
        mock_ccxt.return_value = mock_inst

        client = BinanceFuturesClient(api_key="k", api_secret="s", testnet=True)
        res = client.close_all_positions()
        self.assertTrue(res["success"])
        self.assertEqual(len(res["closed_positions"]), 2)

        calls = mock_inst.create_order.call_args_list
        # Primer llamado para BTC Long debe ser 'sell'
        self.assertEqual(calls[0][1]['side'], 'sell')
        # Segundo llamado para ETH Short debe ser 'buy'
        self.assertEqual(calls[1][1]['side'], 'buy')

    @patch("engine.execution.binance_client.ccxt.binance")
    def test_move_stop_loss_to_breakeven(self, mock_ccxt):
        """Verificar que move_stop_loss_to_breakeven cancele el SL viejo y coloque el nuevo al precio de entrada."""
        mock_inst = MagicMock()
        mock_inst.fetch_open_orders.return_value = [
            {'id': 'old_sl_101', 'type': 'STOP_MARKET', 'side': 'sell', 'amount': 0.005}
        ]
        mock_inst.price_to_precision.side_effect = lambda sym, p: f"{p:.1f}"
        mock_inst.amount_to_precision.side_effect = lambda sym, a: f"{a:.3f}"
        mock_inst.create_order.return_value = {'id': 'new_breakeven_sl_202'}
        mock_ccxt.return_value = mock_inst

        client = BinanceFuturesClient(api_key="k", api_secret="s", testnet=True)
        res = client.move_stop_loss_to_breakeven("BTCUSDT", entry_price=75000.0)

        self.assertTrue(res["success"])
        self.assertEqual(res["breakeven_price"], 75000.0)
        self.assertEqual(res["new_order_id"], "new_breakeven_sl_202")

        # Verificar cancelación del viejo SL
        mock_inst.cancel_order.assert_called_with('old_sl_101', 'BTC/USDT:USDT')
        # Verificar creación del nuevo SL con reduceOnly
        mock_inst.create_order.assert_called_with(
            symbol='BTC/USDT:USDT',
            type='STOP_MARKET',
            side='sell',
            amount=0.005,
            params={'stopPrice': 75000.0, 'reduceOnly': True}
        )


if __name__ == '__main__':
    unittest.main()


