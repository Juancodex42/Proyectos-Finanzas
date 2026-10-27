import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import AsyncMock, MagicMock
from data.models import MyAd, RepositionDecision, BotConfig
from telegram_bot.formatters import format_live_dashboard
from telegram_bot.bot import TelegramBot

def test_format_live_dashboard_structure():
    """Verifica que el dashboard formateado contenga activos, TCs implícitos y emojis válidos."""
    ads = [
        MyAd(adv_no="ad_1", asset="USDT", ad_group=1, current_price=1583.02, payment_methods=["MercadoPagoNew"], status=1),
        MyAd(adv_no="ad_2", asset="USDT", ad_group=2, current_price=1583.51, payment_methods=["LemonCash"], status=1),
        MyAd(adv_no="ad_3", asset="USDT", ad_group=3, current_price=1584.02, payment_methods=["NaranjaX"], status=1),
        MyAd(adv_no="ad_4", asset="BTC", ad_group=1, current_price=121242944.81, payment_methods=["MercadoPagoNew"], status=1),
        MyAd(adv_no="ad_5", asset="BTC", ad_group=2, current_price=121242944.81, payment_methods=["LemonCash"], status=1),
        MyAd(adv_no="ad_6", asset="BTC", ad_group=3, current_price=121242944.81, payment_methods=["NaranjaX"], status=1),
    ]
    decisions = {
        "ad_1": RepositionDecision(should_update=True, new_price=1583.02, reason="reposition_first", tc_implicito=1583.02),
        "ad_2": RepositionDecision(should_update=True, new_price=1583.51, reason="reposition_first", tc_implicito=1583.51),
        "ad_3": RepositionDecision(should_update=True, new_price=1584.02, reason="reposition_first", tc_implicito=1584.02),
        "ad_4": RepositionDecision(should_update=True, new_price=121242944.81, reason="reposition_first", tc_implicito=1584.90),
    }
    spot_prices = {"USDT": 1.0, "BTC": 76499.4}
    config = BotConfig(margin_min=13.0, poll_interval=30)
    
    dashboard = format_live_dashboard(
        ads=ads,
        decisions=decisions,
        spot_prices=spot_prices,
        config=config,
        balance=1100000.0,
        available=990000.0,
        cycle_num=10,
    )
    
    assert "MONITOR EN VIVO" in dashboard
    assert "USDT" in dashboard
    assert "BTC" in dashboard
    assert "1,584.90" in dashboard
    assert len(dashboard) < 4096

@pytest.mark.asyncio
async def test_telegram_bot_update_live_dashboard():
    """Verifica que update_live_dashboard intente editar si existe message_id y guarde ID nuevo."""
    mock_db = MagicMock()
    mock_db.get_config.return_value = "12345"
    bot = TelegramBot(db=mock_db)
    bot._app = MagicMock()
    bot._chat_id = "111222"
    
    # Simular edición exitosa
    bot._app.bot.edit_message_text = AsyncMock()
    await bot.update_live_dashboard("Test text")
    bot._app.bot.edit_message_text.assert_awaited_once_with(
        chat_id="111222",
        message_id=12345,
        text="Test text",
        parse_mode="Markdown",
    )


def test_parse_numeric_input():
    """Verifica el parseo flexible de números en formato argentino e internacional."""
    from telegram_bot.bot import parse_numeric_input
    assert parse_numeric_input("500000") == 500000.0
    assert parse_numeric_input("500.000") == 500000.0
    assert parse_numeric_input("500,000") == 500000.0
    assert parse_numeric_input("$ 500.000") == 500000.0
    assert parse_numeric_input("1.500.000,50") == 1500000.5
    assert parse_numeric_input("1,500,000.50") == 1500000.5
    assert parse_numeric_input("10") == 10.0
    assert parse_numeric_input("10.5") == 10.5
    assert parse_numeric_input("10,5") == 10.5
    assert parse_numeric_input("8.5") == 8.5
    assert parse_numeric_input("8,5") == 8.5
    assert parse_numeric_input("invalido") is None
    assert parse_numeric_input("") is None


@pytest.mark.asyncio
async def test_interactive_set_balance():
    """Verifica el flujo interactivo de configurar saldo ARS."""
    mock_db = MagicMock()
    config = BotConfig(balance_ars=100000.0)
    mock_db.load_bot_config.return_value = config
    bot = TelegramBot(db=mock_db)
    bot._admin_ids = {999}
    bot._chat_id = "999"
    
    # 1. Llamar a set_balance sin argumentos (como al tocarlo en la hamburguesa)
    update = MagicMock()
    update.effective_user.id = 999
    update.effective_chat.id = 999
    update.message.reply_text = AsyncMock()
    ctx = MagicMock()
    ctx.args = []
    
    await bot._cmd_set_balance(update, ctx)
    
    # Debe guardar el estado interactivo y preguntar qué saldo tenés
    assert bot._user_state[999] == "set_balance"
    call_args = update.message.reply_text.call_args[0][0]
    assert "Configurar Saldo ARS" in call_args
    assert "¿Qué saldo tenés ahora?" in call_args
    
    # 2. El usuario responde con el monto (ej: 500000)
    msg_update = MagicMock()
    msg_update.effective_user.id = 999
    msg_update.effective_chat.id = 999
    msg_update.message.text = "500000"
    msg_update.message.reply_text = AsyncMock()
    
    await bot._handle_text_button(msg_update, ctx)
    
    # Debe limpiar el estado, guardar en la BD y confirmar
    assert 999 not in bot._user_state
    assert config.balance_ars == 500000.0
    mock_db.save_bot_config.assert_called_with(config)
    confirm_text = msg_update.message.reply_text.call_args[0][0]
    assert "Saldo ARS actualizado" in confirm_text
    assert "500,000" in confirm_text


@pytest.mark.asyncio
async def test_interactive_set_margin():
    """Verifica el flujo interactivo de cambiar margen mínimo."""
    mock_db = MagicMock()
    config = BotConfig(margin_min=10.0)
    mock_db.load_bot_config.return_value = config
    bot = TelegramBot(db=mock_db)
    bot._admin_ids = {888}
    bot._chat_id = "888"
    
    # 1. Llamar a set_margin sin argumentos
    update = MagicMock()
    update.effective_user.id = 888
    update.effective_chat.id = 888
    update.message.reply_text = AsyncMock()
    ctx = MagicMock()
    ctx.args = []
    
    await bot._cmd_set_margin(update, ctx)
    
    assert bot._user_state[888] == "set_margin"
    call_args = update.message.reply_text.call_args[0][0]
    assert "Cambiar Colchón de Compra" in call_args
    assert "¿Cuánto colchón de compra querés?" in call_args
    
    # 2. El usuario responde con "12.5"
    msg_update = MagicMock()
    msg_update.effective_user.id = 888
    msg_update.effective_chat.id = 888
    msg_update.message.text = "12.5"
    msg_update.message.reply_text = AsyncMock()
    
    await bot._handle_text_button(msg_update, ctx)
    
    assert 888 not in bot._user_state
    assert config.margin_min == 12.5
    mock_db.save_bot_config.assert_called_with(config)
    confirm_text = msg_update.message.reply_text.call_args[0][0]
    assert "Colchón de compra actualizado" in confirm_text
    assert "12.5" in confirm_text


@pytest.mark.asyncio
async def test_interactive_set_rescue():
    """Verifica el flujo interactivo de cambiar margen de rescate Fiwind."""
    mock_db = MagicMock()
    config = BotConfig(rescue_margin=10.0)
    mock_db.load_bot_config.return_value = config
    bot = TelegramBot(db=mock_db)
    bot._admin_ids = {777}
    bot._chat_id = "777"
    
    # 1. Llamar a set_rescue sin argumentos
    update = MagicMock()
    update.effective_user.id = 777
    update.effective_chat.id = 777
    update.message.reply_text = AsyncMock()
    ctx = MagicMock()
    ctx.args = []
    
    await bot._cmd_set_rescue(update, ctx)
    
    assert bot._user_state[777] == "set_rescue"
    call_args = update.message.reply_text.call_args[0][0]
    assert "Margen de Rescate Fiwind" in call_args
    assert "¿Cuánto margen de rescate en Fiwind querés?" in call_args
    
    # 2. El usuario responde con "8,5"
    msg_update = MagicMock()
    msg_update.effective_user.id = 777
    msg_update.effective_chat.id = 777
    msg_update.message.text = "8,5"
    msg_update.message.reply_text = AsyncMock()
    
    await bot._handle_text_button(msg_update, ctx)
    
    assert 777 not in bot._user_state
    assert config.rescue_margin == 8.5
    mock_db.save_bot_config.assert_called_with(config)
    confirm_text = msg_update.message.reply_text.call_args[0][0]
    assert "Margen de rescate Fiwind actualizado" in confirm_text
    assert "8.50" in confirm_text


@pytest.mark.asyncio
async def test_interactive_cancellation():
    """Verifica que al escribir 'cancelar' o usar /cancel se aborte el flujo."""
    mock_db = MagicMock()
    config = BotConfig(margin_min=10.0)
    mock_db.load_bot_config.return_value = config
    bot = TelegramBot(db=mock_db)
    bot._admin_ids = {666}
    bot._chat_id = "666"
    
    # Iniciar estado
    bot._user_state[666] = "set_margin"
    
    # Usuario envía "cancelar"
    msg_update = MagicMock()
    msg_update.effective_user.id = 666
    msg_update.effective_chat.id = 666
    msg_update.message.text = "cancelar"
    msg_update.message.reply_text = AsyncMock()
    ctx = MagicMock()
    
    await bot._handle_text_button(msg_update, ctx)
    
    assert 666 not in bot._user_state
    assert config.margin_min == 10.0
    reply = msg_update.message.reply_text.call_args[0][0]
    assert "cancelada" in reply.lower()


@pytest.mark.asyncio
async def test_direct_commands_with_args():
    """Verifica que si el usuario pasa argumentos directamente, se aplique sin preguntar."""
    mock_db = MagicMock()
    config = BotConfig(balance_ars=100000.0, margin_min=10.0, rescue_margin=10.0)
    mock_db.load_bot_config.return_value = config
    bot = TelegramBot(db=mock_db)
    bot._admin_ids = {555}
    bot._chat_id = "555"
    
    update = MagicMock()
    update.effective_user.id = 555
    update.effective_chat.id = 555
    update.message.reply_text = AsyncMock()
    
    # 1. /set_balance 750000
    ctx_bal = MagicMock()
    ctx_bal.args = ["750000"]
    await bot._cmd_set_balance(update, ctx_bal)
    assert config.balance_ars == 750000.0
    assert 555 not in bot._user_state
    
    # 2. /set_margin 15.5
    ctx_margin = MagicMock()
    ctx_margin.args = ["15.5"]
    await bot._cmd_set_margin(update, ctx_margin)
    assert config.margin_min == 15.5
    assert 555 not in bot._user_state
    
    # 3. /set_rescue 9.25
    ctx_rescue = MagicMock()
    ctx_rescue.args = ["9.25"]
    await bot._cmd_set_rescue(update, ctx_rescue)
    assert config.rescue_margin == 9.25
    assert 555 not in bot._user_state


@pytest.mark.asyncio
async def test_callbacks_set_sell_margin_and_buy_margin():
    """Verifica que los callbacks de cambio de colchón de compra y piso de ganancia funcionen sin NameError y guarden estado."""
    mock_db = MagicMock()
    config = BotConfig(margin_min=10.0, sell_margin_min=5.0)
    mock_db.load_bot_config.return_value = config
    mock_db.get_latest_benchmarks.return_value = {}
    bot = TelegramBot(db=mock_db)
    bot._admin_ids = {444}
    bot._chat_id = "444"

    # 1. Callback bot_set_sell_margin
    update_sell = MagicMock()
    update_sell.effective_user.id = 444
    update_sell.effective_chat.id = 444
    update_sell.callback_query.data = "bot_set_sell_margin"
    update_sell.callback_query.answer = AsyncMock()
    update_sell.callback_query.message.reply_text = AsyncMock()
    ctx = MagicMock()

    await bot._handle_callback(update_sell, ctx)

    assert bot._user_state.get(444) == "set_sell_margin"
    update_sell.callback_query.message.reply_text.assert_awaited_once()
    prompt_sent = update_sell.callback_query.message.reply_text.call_args[0][0]
    assert "Piso de Ganancia de Venta" in prompt_sent

    # 2. Callback bot_set_buy_margin
    update_buy = MagicMock()
    update_buy.effective_user.id = 444
    update_buy.effective_chat.id = 444
    update_buy.callback_query.data = "bot_set_buy_margin"
    update_buy.callback_query.answer = AsyncMock()
    update_buy.callback_query.message.reply_text = AsyncMock()

    await bot._handle_callback(update_buy, ctx)

    assert bot._user_state.get(444) == "set_margin"
    update_buy.callback_query.message.reply_text.assert_awaited_once()
    prompt_buy = update_buy.callback_query.message.reply_text.call_args[0][0]
    assert "Colchón de Compra" in prompt_buy

    # 3. Callback refresh_dash
    update_dash = MagicMock()
    update_dash.effective_user.id = 444
    update_dash.effective_chat.id = 444
    update_dash.callback_query.data = "refresh_dash"
    update_dash.callback_query.answer = AsyncMock()
    update_dash.callback_query.edit_message_text = AsyncMock()

    await bot._handle_callback(update_dash, ctx)
    update_dash.callback_query.edit_message_text.assert_awaited_once()
    dash_text = update_dash.callback_query.edit_message_text.call_args[0][0]
    assert "Panel de Control P2P" in dash_text


def test_format_reconciliation_report_low_sell_balance():
    """Verifica que format_reconciliation_report alerte claramente si el saldo es menor a 100 USDT."""
    from telegram_bot.formatters import format_reconciliation_report

    stats = {
        "total_assets": 14,
        "verified": 42,
        "updated": 0,
        "created": 0,
        "closed_duplicates": 0,
        "total_active": 0,
        "sell_verified": 0,
        "sell_created": 0,
        "sell_low_balance": True,
        "sell_available_stock": 18.41,
        "sell_min_required": 100.0,
    }

    report = format_reconciliation_report(stats)
    assert "VENTAS USDT (No creados)" in report
    assert "18.41 USDT" in report
    assert "100 USDT" in report
    assert "Binance exige al menos 100 USDT" in report




