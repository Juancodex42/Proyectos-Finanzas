"""
Suite de pruebas unitarias deterministas y 100% offline para el Bot V2.0.
Valida dominio matemático, estrategias, router, comisiones de backtest y API mocks.
Referencia de diseño: docs/TESTING_GUIDE.md
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import numpy as np
import pandas as pd
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))

from core.config_loader import ConfigLoader
from core.ripio_api import ProfessionalRipioAPI
from core.state_manager import StateManager
from domain.models import (
    TickerSnapshot,
    OrderBookLevel,
    OrderBookSnapshot,
    QuotePair,
    ArbitrageSignal,
    TradeRecord,
    BacktestMetrics,
    RouteOption,
    RouteEvaluation,
)
from domain.quant_math import (
    calculate_z_score,
    calculate_spread_bps,
    half_life,
    test_cointegration,
    inventory_skew,
    reservation_price,
    optimal_spread,
    sharpe_ratio,
    sortino_ratio,
    max_drawdown,
    permutation_test_signals,
)
from analytics.portfolio_manager import AdvancedPortfolioManager
from analytics.backtester import (
    BacktesterEngine,
    WalkForwardAnalyzer,
    MonteCarloSimulator,
    LuckVsSkillDetector,
)
from analytics.data_loader import DataLoader
from strategies.market_making import MarketMakingStrategy
from strategies.statistical_arbitrage import StatisticalArbitrageStrategy
from execution.inter_exchange_router import InterExchangeRouter, RouteType, NetworkType


# =====================================================================
# 1. ESTRUCTURA, LÍMITE DE 500 LÍNEAS Y HEADERS DE TRAZABILIDAD
# =====================================================================

def test_project_structure_and_engineering_guidelines():
    """Verifica existencia de archivos clave, límite < 500 líneas y headers de diseño."""
    required_files = [
        ".env.example",
        "config/trading_config.yaml",
        "src/domain/models.py",
        "src/domain/quant_math.py",
        "src/core/ripio_api.py",
        "src/core/binance_api.py",
        "src/core/state_manager.py",
        "src/core/config_loader.py",
        "src/analytics/backtester.py",
        "src/analytics/data_loader.py",
        "src/analytics/portfolio_manager.py",
        "src/strategies/market_making.py",
        "src/strategies/statistical_arbitrage.py",
        "src/execution/inter_exchange_router.py",
        "BOT_TRADING_RIPIO_V2.bat",
        "main.py",
        "run_backtest.py",
        "collect_data.py",
        "README.md",
    ]
    for rel_path in required_files:
        assert (ROOT_DIR / rel_path).exists(), f"Falta archivo requerido: {rel_path}"

    py_files = [
        p for p in ROOT_DIR.rglob("*.py")
        if ".venv" not in p.parts and "venv" not in p.parts and "__pycache__" not in p.parts
    ]
    assert len(py_files) > 0
    for py_file in py_files:
        lines = py_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 500, f"{py_file.name} supera 500 líneas ({len(lines)})"
        head_text = "\n".join(lines[:10])
        assert "Referencia de diseño:" in head_text, (
            f"{py_file.name} no incluye el header 'Referencia de diseño:'"
        )


def test_config_loader_without_env_file():
    """Verifica que ConfigLoader funcione en modo Demo/Paper sin requerir .env."""
    loader = ConfigLoader(config_dir=str(ROOT_DIR / "config"))
    creds = loader.load_credentials(strict=False)
    assert "TRADING_MODE" in creds
    assert "CAPITAL_INICIAL" in creds

    config = loader.load_config()
    assert "strategies" in config
    assert loader.validate_config() is True
    assert loader.get("fees.maker") < loader.get("fees.taker")
    assert loader.is_strategy_enabled("statistical_arbitrage") is True


# =====================================================================
# 2. MODELOS DE DOMINIO Y MATEMÁTICA CUANTITATIVA PURA
# =====================================================================

def test_domain_models_and_pure_quant_math():
    """Verifica contratos tipados en models.py y funciones puras en quant_math.py."""
    ticker = TickerSnapshot(pair="USDT_ARS", bid=1490.0, ask=1510.0, last=1500.0)
    assert ticker.mid == 1500.0
    assert ticker.spread_abs == 20.0
    assert abs(ticker.spread_bps - 133.3333) < 0.01
    assert ticker["bid"] == 1490.0

    ob = OrderBookSnapshot(
        pair="USDT_ARS",
        bids=[OrderBookLevel(1490.0, 100.0)],
        asks=[OrderBookLevel(1510.0, 100.0)],
    )
    assert len(ob.bids) == 1

    # Z-score y Spread
    series = [1.0, 1.0, 1.0, 1.0, 1.05]
    z = calculate_z_score(series)
    assert z is not None and z > 1.5
    assert abs(calculate_spread_bps(1.015, 1.0) - 150.0) < 1e-6

    # Ornstein-Uhlenbeck half-life y cointegración sobre serie estacionaria AR(1)
    rng = np.random.default_rng(123)
    n = 120
    usdc = np.full(n, 1500.0)
    spread = np.zeros(n)
    for i in range(1, n):
        spread[i] = 0.5 * spread[i - 1] + rng.normal(0, 1.0)
    usdt = usdc + spread

    hl = half_life(spread)
    assert 0.5 <= hl < 10.0
    is_coint, p_val = test_cointegration(usdt, usdc)
    assert is_coint is True
    assert p_val < 0.05

    # Serie no estacionaria (random walk divergente con tendencia)
    rw_usdt = usdc + np.cumsum(np.full(n, 2.0))
    is_coint_rw, _ = test_cointegration(rw_usdt, usdc)
    assert is_coint_rw is False

    # Métricas financieras
    eq = [10000.0, 10200.0, 9690.0, 10500.0]
    dd = max_drawdown(eq)
    assert abs(dd - 5.0) < 1e-5  # De 10200 a 9690 es 5% exacto
    rets = [0.01, 0.015, -0.005, 0.02, 0.01]
    assert sharpe_ratio(rets) > 0
    assert sortino_ratio(rets) > 0


# =====================================================================
# 3. RIPIO API (OFFLINE MOCK): HMAC CON QUERY PARAMS Y LÍMITE HTTP 429
# =====================================================================

def test_ripio_api_hmac_query_params_and_429_max_retries():
    """Verifica firma HMAC con query params en get_ordenes_abiertas y tope de 3 retries en 429."""
    async def _run():
        api = ProfessionalRipioAPI("test_token", "test_secret", retry_delay=0.001)

        # 1. Verificar que get_ordenes_abiertas incluya ?pair=USDT_ARS en la ruta firmada
        signed_paths = []
        orig_get_headers = api.get_headers

        def spy_get_headers(method, path, body=""):
            signed_paths.append(path)
            return orig_get_headers(method, path, body)

        api.get_headers = spy_get_headers

        mock_resp_ok = AsyncMock()
        mock_resp_ok.status = 200
        mock_resp_ok.json = AsyncMock(return_value={"data": {"orders": [{"id": "ord_1"}]}})
        mock_ctx_ok = AsyncMock()
        mock_ctx_ok.__aenter__.return_value = mock_resp_ok

        api.session = MagicMock()
        api.session.get.return_value = mock_ctx_ok

        orders = await api.get_ordenes_abiertas(pair="USDT_ARS")
        assert len(orders) == 1
        assert signed_paths[-1] == "/v4/orders/open?pair=USDT_ARS"

        # 2. Verificar que HTTP 429 corte en max_retries=3 sin recursión infinita
        mock_resp_429 = AsyncMock()
        mock_resp_429.status = 429
        mock_ctx_429 = AsyncMock()
        mock_ctx_429.__aenter__.return_value = mock_resp_429
        api.session.get.return_value = mock_ctx_429

        res_429 = await api.get_ticker("USDT_ARS", max_retries=3)
        assert res_429 is None
        assert api.stats["rate_limit_hits"] >= 4  # 1 inicial + 3 reintentos

    asyncio.run(_run())


# =====================================================================
# 4. STATE MANAGER & PORTFOLIO MANAGER (OFFLINE)
# =====================================================================

def test_state_manager_isolation_and_dual_keys(tmp_path):
    """Verifica aislamiento de disco y sincronización de trades_dia / trades_history."""
    prod_state_path = ROOT_DIR / "data" / "state" / "bot_state.json"
    prod_before = prod_state_path.read_text(encoding="utf-8") if prod_state_path.exists() else None

    sm = StateManager(state_dir=str(tmp_path / "isolated"))
    sm.load_state()
    sm.update_capital(5000.0)
    sm.add_trade("statistical_arbitrage", {"pnl": 25.5, "pair": "USDT_USDC"})
    sm.backup_state()

    assert sm.state["capital"] == 5000.0
    assert len(sm.state["trades_dia"]) == 1
    assert len(sm.state["trades_history"]) == 1
    assert sm.state["trades_dia"][0]["strategy"] == "statistical_arbitrage"
    assert sm.state["trades_dia"][0]["estrategia"] == "statistical_arbitrage"

    if prod_before is not None:
        assert prod_state_path.read_text(encoding="utf-8") == prod_before


def test_portfolio_manager_offline():
    """Verifica cálculo de valor, exposición y límites del PortfolioManager con mocks."""
    async def _run():
        mock_ripio = MagicMock()
        mock_ripio.get_balance = AsyncMock(return_value={
            "USDT": {"available": 500.0, "locked": 0.0},
            "USDC": {"available": 500.0, "locked": 0.0},
            "ARS": {"available": 150000.0, "locked": 0.0},
            "BTC": {"available": 0.0, "locked": 0.0},
            "ETH": {"available": 0.0, "locked": 0.0},
        })
        mock_ripio.get_ticker = AsyncMock(return_value={"bid": 1490.0, "ask": 1500.0, "last": 1500.0})

        config = ConfigLoader(config_dir=str(ROOT_DIR / "config")).load_config()
        pm = AdvancedPortfolioManager(mock_ripio, config)
        assert await pm.actualizar_inventario() is True
        assert await pm.actualizar_precios() is True

        total_usd = pm.calcular_valor_portfolio_usd()
        assert abs(total_usd - 1100.0) < 1e-2  # 500 + 500 + 150000/1500 = 1100 USD
        exp = pm.calcular_exposicion_por_moneda()
        assert abs(sum(exp.values()) - 1.0) < 1e-6
        valido, violaciones = await pm.validar_limites_exposicion()
        assert valido is True and len(violaciones) == 0

    asyncio.run(_run())


# =====================================================================
# 5. MARKET MAKING (AVELLANEDA-STOIKOV) & STATISTICAL ARBITRAGE
# =====================================================================

def test_avellaneda_stoikov_inventory_shift_and_yaml_keys():
    """Verifica sesgo de inventario Avellaneda-Stoikov y compatibilidad de claves YAML."""
    mock_ripio = MagicMock()
    mock_portfolio = MagicMock()
    mock_state = MagicMock()
    mock_state.state = {"capital": 2000.0}

    # Usando claves en español tal como están en config/trading_config.yaml
    config = {
        "strategies": {
            "market_making": {
                "enabled": True,
                "allocation_pct": 0.30,
                "risk_aversion": 0.2,
                "spread_objetivo_pct": 0.004,
                "max_inventario_desbalance_pct": 0.25,
            }
        },
        "fees": {"maker": 0.0013, "taker": 0.0030},
    }
    mm = MarketMakingStrategy(mock_ripio, config, mock_portfolio, mock_state)
    assert abs(mm.gamma - 0.2) < 1e-6
    assert abs(mm.target_spread_bps - 40.0) < 1e-6
    assert abs(mm.max_inventory_usd - 500.0) < 1e-6

    mm.mid_prices.extend([1500.0, 1502.0, 1498.0, 1500.0])

    mm.inventory_value_usd = 0.0
    bid_neutral, ask_neutral = mm.calculate_quote_prices()

    mm.inventory_value_usd = 250.0
    bid_long, ask_long = mm.calculate_quote_prices()

    mm.inventory_value_usd = -250.0
    bid_short, ask_short = mm.calculate_quote_prices()

    assert bid_long < bid_neutral < bid_short
    assert ask_long < ask_neutral < ask_short


def test_statistical_arbitrage_signal_and_trade_recording(tmp_path):
    """Verifica detección de señal, cierre y registro en StateManager de StatArb."""
    async def _run():
        mock_ripio = MagicMock()
        sm = StateManager(state_dir=str(tmp_path / "stat_arb_state"))
        sm.update_capital(10000.0)
        pm = MagicMock()
        config = ConfigLoader(config_dir=str(ROOT_DIR / "config")).load_config()

        sa = StatisticalArbitrageStrategy(mock_ripio, config, pm, sm)
        sa.cointegration_pvalue_max = 0.999
        assert sa.lookback_period == 30

        rng = np.random.default_rng(7)
        for _ in range(35):
            u_c = 1500.0 + rng.normal(0, 0.5)
            u_t = u_c + rng.normal(0, 1.0)
            sa.price_history_usdc.append(u_c)
            sa.price_history_usdt.append(u_t)
            sa.ratio_history.append(u_t / u_c)

        # Inyectar dislocación fuerte (USDT subvaluado -> Z < -2.0)
        sa.price_history_usdc.append(1500.0)
        sa.price_history_usdt.append(1475.0)
        sa.ratio_history.append(1475.0 / 1500.0)

        sig_open = await sa.generate_signal()
        assert sig_open is not None
        assert sig_open["action"] == "open_long_usdt"
        assert await sa.execute_signal(sig_open) is True
        assert sa.current_position == "long_usdt"

        # Normalizar ratio a 1.000 para disparar cierre
        sa.price_history_usdc.append(1500.0)
        sa.price_history_usdt.append(1500.0)
        sa.ratio_history.append(1.0)

        sig_close = await sa.generate_signal()
        assert sig_close is not None and sig_close["action"] == "close"
        assert await sa.execute_signal(sig_close) is True
        assert sa.current_position is None
        assert len(sm.state["trades_history"]) == 1
        assert sm.state["trades_history"][0]["pnl"] > 0

    asyncio.run(_run())


# =====================================================================
# 6. INTER-EXCHANGE ROUTER (PAR INVERSO Y COSTO ÓPTIMO)
# =====================================================================

def test_inter_exchange_router_inverse_pair_and_optimal_route():
    """Verifica inversión 1/ask y 1/bid en par inverso y selección de ruta óptima."""
    async def _run():
        mock_ripio = MagicMock()
        mock_binance = MagicMock()
        config = ConfigLoader(config_dir=str(ROOT_DIR / "config")).load_config()

        # Simular que USDT_USDC no existe, pero USDC_USDT sí existe con bid=0.98, ask=1.00
        async def fake_ticker(pair):
            if pair == "USDT_USDC":
                return None
            if pair == "USDC_USDT":
                return {"bid": 0.98, "ask": 1.00, "last": 0.99}
            return None

        mock_ripio.get_ticker = fake_ticker
        router = InterExchangeRouter(mock_ripio, mock_binance, config)

        spread_info = await router.get_ripio_swap_spread("USDT", "USDC")
        assert spread_info is not None
        assert abs(spread_info["bid"] - 1.0) < 1e-6  # 1 / 1.00
        assert abs(spread_info["ask"] - (1.0 / 0.98)) < 1e-6  # 1 / 0.98 > bid
        assert spread_info["ask"] > spread_info["bid"]

        # Para $1000 USD con ~2% de spread en Ripio ($20 + $3 = $23), Binance TRC20 cuesta $4
        route = await router.calculate_optimal_route("USDT", "USDC", amount_usd=1000.0)
        assert route["route_type"] == RouteType.BINANCE_ROUTE
        assert route["is_profitable"] is True

    asyncio.run(_run())


# =====================================================================
# 7. BACKTESTER: DESCUENTO REAL DE FEES, MTM DRAWDOWN Y LUCK vs SKILL
# =====================================================================

def test_backtester_real_fees_mtm_drawdown_and_luck_vs_skill():
    """Verifica descuento de comisiones, curva Mark-to-Market y permutación de signos."""
    # 1. Si el precio es constante (1500), abrir y cerrar debe descontar fees reales (< capital inicial)
    df_flat = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=5, freq="5min"),
        "close": [1500.0, 1425.0, 1500.0, 1500.0, 1500.0],
    })

    class OneTradeStrategy:
        def __init__(self):
            self.step = 0

        def on_data(self, row):
            self.step += 1
            if self.step == 1:
                return {"action": "open_long", "position_size_usd": 1000.0}
            if self.step == 3:
                return {"action": "close_long", "position_size_usd": 1000.0}
            return None

    engine = BacktesterEngine(
        strategy=OneTradeStrategy(),
        historical_data=df_flat,
        initial_capital=10000.0,
        maker_fee=0.0013,
        taker_fee=0.0030,
        slippage_bps=0.0,
    )
    res = engine.run()

    # Solo 1 trade cerrado (no 2 por contar la apertura)
    assert res["metrics"]["num_trades"] == 1
    assert len(res["trades"]) == 1

    # Comisiones descontadas: 1000 * (0.0013 + 0.0030) = $4.30 USD
    closed_trade = res["trades"][0]
    assert abs(closed_trade["fee_cost"] - 4.30) < 1e-4
    assert abs(closed_trade["pnl"] - (-4.30)) < 1e-4
    assert abs(engine.capital - (10000.0 - 4.30)) < 1e-4

    # En la barra 2 el precio cayó un 5% (de 1500 a 1425 sobre $1000 = -$50 flotante) -> MaxDD > 0
    assert res["metrics"]["max_drawdown_pct"] > 0.45

    # 2. LuckVsSkillDetector: estrategia ganadora consistente vs ruido aleatorio
    winning_trades = [
        {"pnl": 15.0, "gross_pnl": 18.0, "fee_cost": 3.0} for _ in range(40)
    ]
    lvs_skill = LuckVsSkillDetector(trades=winning_trades, num_permutations=500, seed=42).run()
    assert lvs_skill["p_value"] < 0.01
    assert "ALTA CONFIANZA" in lvs_skill["verdict"]

    losing_trades = [
        {"pnl": -3.0, "gross_pnl": 0.0, "fee_cost": 3.0} for _ in range(40)
    ]
    lvs_luck = LuckVsSkillDetector(trades=losing_trades, num_permutations=500, seed=42).run()
    assert lvs_luck["p_value"] > 0.10


def test_data_loader_collector_csv_compatibility(tmp_path):
    """Verifica que DataLoader y BacktesterEngine acepten columnas USDT_ARS_mid de collect_data.py."""
    csv_path = tmp_path / "ripio_2026-01-01.csv"
    df_raw = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=30, freq="5min"),
        "USDT_ARS_bid": np.linspace(1490, 1510, 30),
        "USDT_ARS_ask": np.linspace(1495, 1515, 30),
        "USDT_ARS_mid": np.linspace(1492.5, 1512.5, 30),
        "USDC_ARS_mid": np.full(30, 1500.0),
    })
    df_raw.to_csv(csv_path, index=False)

    loader = DataLoader(data_dir=str(tmp_path))
    loaded = loader.load_csv(csv_path.name)
    assert loaded is not None
    assert "close" in loaded.columns
    is_valid, msg = loader.validate_ohlcv_data(loaded)
    assert is_valid is True, msg
