"""
Tests para verificar la lógica de exclusividad de comerciantes y filtros en compras P2P.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import COMPETE_ONLY_MERCHANTS, DEFAULT_BUY_AUTO_REPLY, DEFAULT_BUY_REMARKS
from core.network.binance_api import BinanceClient
from core.market_scanner import MarketScanner
from core.method_selector import MethodSelector


def test_settings_merchant_filter_defaults():
    assert COMPETE_ONLY_MERCHANTS is True
    assert DEFAULT_BUY_AUTO_REPLY == "Buenas, no transfiero a terceros"
    assert DEFAULT_BUY_REMARKS == "Buenas, no transfiero a terceros"


@pytest.mark.asyncio
async def test_create_ad_buy_parameters():
    client = BinanceClient(api_key="dummy", secret_key="dummy")
    client.signed_post = AsyncMock(return_value={"code": "000000", "data": "12345"})

    res = await client.create_ad(
        asset="USDT",
        trade_type="BUY",
        price=1600.0,
        init_amount=100.0,
        min_trans_amount=10000.0,
        max_trans_amount=160000.0,
        trade_methods=[{"identifier": "MercadoPagoNew"}],
    )
    assert res.get("data") == "12345"

    call_args = client.signed_post.call_args
    body = call_args.kwargs["body"]
    assert body["tradeType"] == "BUY"
    assert body["buyerRegDaysLimit"] == 0
    assert body["userAllTradeCountMin"] == 0
    assert body["takerAdditionalKycRequired"] == 0
    assert body["autoReplyMsg"] == DEFAULT_BUY_AUTO_REPLY
    assert body["remarks"] == DEFAULT_BUY_REMARKS
    await client.close()


@pytest.mark.asyncio
async def test_create_ad_sell_parameters():
    client = BinanceClient(api_key="dummy", secret_key="dummy")
    client.signed_post = AsyncMock(return_value={"code": "000000", "data": "67890"})

    res = await client.create_ad(
        asset="USDT",
        trade_type="SELL",
        price=1620.0,
        init_amount=100.0,
        min_trans_amount=10000.0,
        max_trans_amount=162000.0,
        trade_methods=[{"identifier": "MercadoPagoNew"}],
    )
    assert res.get("data") == "67890"

    call_args = client.signed_post.call_args
    body = call_args.kwargs["body"]
    assert body["tradeType"] == "SELL"
    assert body["takerAdditionalKycRequired"] == 0
    assert "titular verificado" in body["autoReplyMsg"]
    await client.close()


@pytest.mark.asyncio
async def test_scan_competitors_uses_merchant_filter():
    mock_client = AsyncMock(spec=BinanceClient)
    mock_client.search_ads.return_value = {
        "code": "000000",
        "data": [
            {
                "adv": {
                    "advNo": "999",
                    "price": "1605.00",
                    "minSingleTransAmount": "10000",
                    "maxSingleTransAmount": "500000",
                },
                "advertiser": {
                    "userNo": "u1",
                    "nickName": "Merchant1",
                    "userType": "merchant",
                    "orderCount": 50,
                    "monthFinishRate": 0.99,
                },
            }
        ],
    }
    scanner = MarketScanner(client=mock_client, spot_client=AsyncMock(), db=AsyncMock())
    rates = await scanner.scan_competitors(
        asset="USDT",
        payment_method="MercadoPagoNew",
        spot_prices={"USDT": 1.0},
    )
    assert len(rates) == 1
    assert rates[0].advertiser_nickname == "Merchant1"

    # Verificar que search_ads se llamó con publisher_type="merchant"
    mock_client.search_ads.assert_called_once()
    call_kwargs = mock_client.search_ads.call_args.kwargs
    assert call_kwargs.get("publisher_type") == "merchant"
    assert call_kwargs.get("trade_type") == "SELL"


@pytest.mark.asyncio
async def test_method_selector_uses_merchant_filter():
    mock_client = AsyncMock(spec=BinanceClient)
    mock_client.search_ads.return_value = {"code": "000000", "data": []}
    selector = MethodSelector(client=mock_client, db=AsyncMock())

    await selector.score_method("MercadoPagoNew", my_adv_nos=set(), volume_ref=500000.0)

    # Debe haber llamado a search_ads dos veces (BUY y SELL), ambas con publisher_type="merchant"
    assert mock_client.search_ads.call_count == 2
    for call in mock_client.search_ads.call_args_list:
        assert call.kwargs.get("publisher_type") == "merchant"
