"""
Suite de pruebas unitarias offline para la interfaz de Telegram y AutomationManager.
Verifica política fail-closed de autorización, comandos remotos y backtest real.
Referencia de diseño: docs/TELEGRAM_INTERFACE.md
"""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))

from core.state_manager import StateManager
from src.telegram_bot.bot_interface import TradingBotInterface
from src.telegram_bot.automation import AutomationManager


def _make_update(user_id: int = 123456789):
    """Construye un objeto Update simulado para pruebas offline de handlers."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat.id = user_id
    update.message.reply_text = AsyncMock()
    return update


def test_telegram_authorization_fail_closed():
    """Verifica que sin usuarios autorizados configurados el bot rechace todo acceso (fail-closed)."""
    mock_bot = MagicMock()
    tg_empty = TradingBotInterface(
        telegram_token="fake_token",
        trading_bot=mock_bot,
        authorized_users=[],
    )
    assert tg_empty._check_authorization(123456789) is False

    tg_auth = TradingBotInterface(
        telegram_token="fake_token",
        trading_bot=mock_bot,
        authorized_users=[123456789],
    )
    assert tg_auth._check_authorization(123456789) is True
    assert tg_auth._check_authorization(999999999) is False


def test_telegram_state_keys_and_commands(tmp_path):
    """Verifica lectura de trades_dia/trades_history y ejecución de comandos de Telegram."""
    async def _run():
        sm = StateManager(state_dir=str(tmp_path / "tg_state"))
        sm.update_capital(5000.0)
        sm.add_trade(
            "statistical_arbitrage",
            {"pair": "USDT_USDC", "side": "long_usdt", "amount_usd": 400.0, "pnl": 18.5},
        )
        sm.add_trade(
            "market_making",
            {"pair": "USDT_ARS", "side": "buy", "amount_usd": 200.0, "pnl": 6.5},
        )

        mock_bot = MagicMock()
        mock_bot.running = False
        mock_bot.state_manager = sm
        mock_bot.portfolio_manager.calcular_valor_portfolio_usd.return_value = 5025.0
        mock_bot.stat_arb_strategy = SimpleNamespace(
            enabled=True,
            allocation_pct=0.40,
            z_score_entry=2.0,
            z_score_exit=0.5,
            current_position="long_usdt",
            position_size_usd=400.0,
            position_entry_price=0.985,
            ratio_history=[0.992],
        )
        mock_bot.market_making_strategy = SimpleNamespace(
            enabled=True,
            allocation_pct=0.30,
            target_spread_bps=40.0,
            gamma=0.1,
        )
        mock_bot.run_strategies_loop = AsyncMock()
        mock_bot.close_all_positions = AsyncMock()

        tg = TradingBotInterface(
            telegram_token="fake_token",
            trading_bot=mock_bot,
            authorized_users=[111],
        )
        tg.app = MagicMock()
        tg.app.bot.send_message = AsyncMock()

        # Usuario no autorizado recibe rechazo
        unauth_upd = _make_update(user_id=999)
        await tg.cmd_status(unauth_upd, MagicMock())
        assert "[UNAUTHORIZED]" in unauth_upd.message.reply_text.call_args[0][0]

        # Estadísticas y P&L leen correctamente de StateManager
        stats = await tg._calculate_statistics()
        assert stats["total_trades"] == 2
        assert abs(stats["total_pnl"] - 25.0) < 1e-6

        pnl = await tg._get_pnl_breakdown()
        assert abs(pnl["stat_arb"] - 18.5) < 1e-6
        assert abs(pnl["market_making"] - 6.5) < 1e-6

        # Comandos autorizados
        auth_upd = _make_update(user_id=111)
        ctx = MagicMock()
        ctx.args = ["stat_arb"]

        await tg.cmd_status(auth_upd, ctx)
        await tg.cmd_strategies(auth_upd, ctx)
        strat_reply = auth_upd.message.reply_text.call_args[0][0]
        assert "Statistical Arbitrage" in strat_reply
        assert "2.0" in strat_reply

        await tg.cmd_start_bot(auth_upd, ctx)
        assert mock_bot.running is True

        await tg.cmd_stop_bot(auth_upd, ctx)
        assert mock_bot.running is False
        mock_bot.close_all_positions.assert_awaited_once()

        # Ejecutar backtest real desde handler
        await tg._run_backtest_task_enhanced(chat_id=111)
        tg.app.bot.send_message.assert_awaited()
        bt_text = tg.app.bot.send_message.call_args.kwargs["text"]
        assert "[BACKTEST COMPLETADO]" in bt_text

    asyncio.run(_run())


def test_automation_manager_health_and_real_backtest(tmp_path):
    """Verifica chequeo de umbrales, auto-pausa por drawdown y backtest real en AutomationManager."""
    async def _run():
        sm = StateManager(state_dir=str(tmp_path / "auto_state"))
        sm.update_capital(1000.0)
        # Simular racha negativa que supera el 15% de drawdown crítico
        sm.add_trade("statistical_arbitrage", {"pnl": -180.0})

        mock_bot = MagicMock()
        mock_bot.state_manager = sm
        mock_bot.stat_arb_strategy = SimpleNamespace(enabled=True)
        mock_bot.market_making_strategy = SimpleNamespace(enabled=True)

        mock_tg = MagicMock()
        mock_tg.send_alert = AsyncMock()

        auto = AutomationManager(trading_bot=mock_bot, telegram_bot=mock_tg)
        await auto.daily_health_check()

        # Debe haber pausado automáticamente ambas estrategias por drawdown > 15%
        assert mock_bot.stat_arb_strategy.enabled is False
        assert mock_bot.market_making_strategy.enabled is False

        bt_res = await auto._run_automatic_backtest()
        assert bt_res["status"] == "SUCCESS"
        assert "sharpe_backtest" in bt_res

    asyncio.run(_run())
