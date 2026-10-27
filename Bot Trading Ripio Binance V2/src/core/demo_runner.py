"""
Simulador interactivo Zero-API para demostración en vivo del sistema cuantitativo.
Ejecuta cotizaciones, Avellaneda-Stoikov, Arbitraje Estadístico, Router y Backtest sin APIs.
Referencia de diseño: docs/ARQUITECTURA.md
"""

import logging
from datetime import datetime
from types import SimpleNamespace
from typing import Dict, Optional
import numpy as np

from core.config_loader import ConfigLoader
from core.state_manager import StateManager
from analytics.portfolio_manager import AdvancedPortfolioManager
from strategies import StatisticalArbitrageStrategy, MarketMakingStrategy
from execution.inter_exchange_router import InterExchangeRouter, NetworkType
from run_backtest import run_full_analysis

logger = logging.getLogger(__name__)


class SimulatedRipioAPI:
    """Adaptador determinista en memoria que emula Ripio Trade API v4 sin red."""

    def __init__(self):
        self.tickers = {
            "USDT_ARS": {"bid": 1495.50, "ask": 1502.50, "last": 1499.00},
            "USDC_ARS": {"bid": 1465.00, "ask": 1471.00, "last": 1468.00},
            "BTC_USDC": {"bid": 96450.00, "ask": 96650.00, "last": 96550.00},
            "ETH_USDC": {"bid": 3410.00, "ask": 3425.00, "last": 3418.00},
            "USDT_USDC": {"bid": 1.0160, "ask": 1.0240, "last": 1.0200},
        }
        self.total_requests = 0

    async def get_ticker(self, pair: str) -> Optional[Dict]:
        self.total_requests += 1
        base = self.tickers.get(pair)
        if not base:
            return None
        return {**base, "timestamp": datetime.now()}

    async def get_orderbook(self, pair: str, depth: int = 5) -> Optional[Dict]:
        self.total_requests += 1
        t = self.tickers.get(pair)
        if not t:
            return None
        bids = [[t["bid"] - i * 0.5, 500.0 + i * 150.0] for i in range(depth)]
        asks = [[t["ask"] + i * 0.5, 500.0 + i * 150.0] for i in range(depth)]
        return {"bids": bids, "asks": asks, "pair": pair, "timestamp": datetime.now()}

    async def get_balance(self) -> Dict:
        self.total_requests += 1
        return {
            "USDT": {"available": 2500.0, "locked": 0.0, "total": 2500.0},
            "USDC": {"available": 2500.0, "locked": 0.0, "total": 2500.0},
            "ARS": {"available": 750000.0, "locked": 0.0, "total": 750000.0},
            "BTC": {"available": 0.005, "locked": 0.0, "total": 0.005},
            "ETH": {"available": 0.05, "locked": 0.0, "total": 0.05},
        }

    def get_api_status(self) -> Dict:
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.total_requests,
            "failed_requests": 0,
            "rate_limit_hits": 0,
            "success_rate": 1.0,
            "public_available": 95,
            "private_available": 48,
        }


class SimulatedBinanceAPI:
    """Adaptador determinista en memoria que emula Binance API v3 sin red."""

    PRICES = {
        "BTCUSDT": 96500.00,
        "ETHUSDT": 3415.00,
        "USDTARS": 1488.00,
    }

    async def get_price(self, symbol: str) -> Optional[float]:
        return self.PRICES.get(symbol)

    async def get_ticker(self, symbol: str) -> Optional[Dict]:
        p = self.PRICES.get(symbol)
        if not p:
            return None
        return {"bid": p * 0.9998, "ask": p * 1.0002, "last": p}


async def run_zero_api_demo(days: int = 15, capital: float = 10000.0):
    """
    Ejecuta demostración interactiva completa en consola sin requerir `.env` ni APIs.
    """
    print("\n" + "=" * 80)
    print("  BOT TRADING RIPIO-BINANCE V2.0 — DEMO CUANTITATIVA EN VIVO (ZERO-API MODE)")
    print("=" * 80)
    print("  Nota de Alpha Protection: Parametros calibrados con valores sinteticos")
    print("  academicos para demostracion de arquitectura y modelos matematicos.")
    print("=" * 80 + "\n")

    config_loader = ConfigLoader()
    config = config_loader.load_config()
    ripio_sim = SimulatedRipioAPI()
    binance_sim = SimulatedBinanceAPI()

    import tempfile
    temp_state_dir = tempfile.mkdtemp(prefix="bot_demo_state_")
    state_mgr = StateManager(state_dir=temp_state_dir)
    state_mgr.update_capital(capital)
    portfolio = AdvancedPortfolioManager(ripio_sim, config)
    await portfolio.actualizar_inventario()
    await portfolio.actualizar_precios()

    # 1. Cotizaciones en Tiempo Real
    print("[PASO 1/4] COTIZACIONES SIMULADAS EN TIEMPO REAL (RIPIO vs BINANCE)")
    print("-" * 80)
    usdt_t = await ripio_sim.get_ticker("USDT_ARS")
    usdc_t = await ripio_sim.get_ticker("USDC_ARS")
    btc_r = await ripio_sim.get_ticker("BTC_USDC")
    btc_b = await binance_sim.get_price("BTCUSDT")
    usdt_b = await binance_sim.get_price("USDTARS")

    print(f"  • Ripio USDT/ARS   -> Bid: ${usdt_t['bid']:,.2f} | Ask: ${usdt_t['ask']:,.2f} | Mid: ${(usdt_t['bid']+usdt_t['ask'])/2:,.2f}")
    print(f"  • Ripio USDC/ARS   -> Bid: ${usdc_t['bid']:,.2f} | Ask: ${usdc_t['ask']:,.2f} | Mid: ${(usdc_t['bid']+usdc_t['ask'])/2:,.2f}")
    print(f"  • Binance USDT/ARS -> Referencia: ${usdt_b:,.2f} ARS (Spread Inter-Exchange: +{((usdt_t['bid']/usdt_b)-1)*100:.2f}%)")
    print(f"  • BTC/USD          -> Ripio: ${btc_r['ask']:,.2f} USDC | Binance: ${btc_b:,.2f} USDT")
    print(f"  • Valor Portafolio -> ${portfolio.calcular_valor_portfolio_usd():,.2f} USD equivalente\n")

    # 2. Market Making (Avellaneda-Stoikov)
    print("[PASO 2/4] MARKET MAKING DINAMICO — MODELO AVELLANEDA-STOIKOV (2008)")
    print("-" * 80)
    mm = MarketMakingStrategy(ripio_sim, config, portfolio, state_mgr)
    mm.max_inventory_usd = 500.0
    rng = np.random.default_rng(42)
    base_prices = 1500.0 + np.cumsum(rng.normal(0, 1.8, 30))
    for p in base_prices:
        mm.mid_prices.append(float(p))
    mm.mid_prices.append(1500.0)

    print(f"  Precio Mid Actual: $1,500.00 ARS | Volatilidad Anualizada (sigma): {mm.calculate_volatility():.4f}")
    print(f"  Parametro Aversion al Riesgo (gamma): {mm.gamma} | Max Inventory: ${mm.max_inventory_usd:,.2f} USD\n")
    print(f"  {'Escenario Inventario':<26} | {'Precio Reserva (r)':<18} | {'Bid Quote':<14} | {'Ask Quote':<14} | {'Sesgo (Skew)'}")
    print("  " + "-" * 76)

    for label, inv_val in [
        ("Neutral (q = $0 USD)", 0.0),
        ("Long Exceso (q = +$250)", 250.0),
        ("Short Deficit (q = -$250)", -250.0),
    ]:
        mm.inventory_value_usd = inv_val
        q_pair = mm.calculate_quote_details()
        print(
            f"  {label:<26} | ${q_pair.reservation_price:>15,.2f} | "
            f"${q_pair.bid_price:>11,.2f} | ${q_pair.ask_price:>11,.2f} | "
            f"{-q_pair.inventory_penalty:>+7.2f} ARS"
        )
    print()

    # 3. Statistical Arbitrage & Inter-Exchange Router
    print("[PASO 3/4] STATISTICAL ARBITRAGE (ORNSTEIN-UHLENBECK) & INTER-EXCHANGE ROUTER")
    print("-" * 80)
    router = InterExchangeRouter(ripio_sim, binance_sim, config)
    stat_arb = StatisticalArbitrageStrategy(ripio_sim, config, portfolio, state_mgr, router=router)

    # Alimentar serie estacionaria OU con dislocación en el último tick
    ou_usdc = np.full(60, 1470.0) + rng.normal(0, 1.2, 60)
    ou_usdt = ou_usdc + rng.normal(0, 2.0, 60)
    ou_usdt[-1] = ou_usdc[-1] + 28.5  # Shock positivo de USDT sobre USDC (Z > 2.0)

    for u_t, u_c in zip(ou_usdt, ou_usdc):
        stat_arb.price_history_usdt.append(float(u_t))
        stat_arb.price_history_usdc.append(float(u_c))
        stat_arb.ratio_history.append(float(u_t / u_c))

    is_coint, p_val = stat_arb.test_cointegration()
    z_val = stat_arb.calculate_z_score()
    hl_val = stat_arb.calculate_half_life()
    signal = await stat_arb.generate_signal()

    print(f"  • Cointegracion / ADF Stationarity : {'ESTACIONARIO (OK)' if is_coint else 'NO'} (p-value: {p_val:.4f})")
    print(f"  • Ornstein-Uhlenbeck Half-Life     : {hl_val:.2f} periodos")
    print(f"  • Z-Score Actual (USDT/USDC)       : {z_val:+.2f} (Umbral entrada: ±{stat_arb.z_score_entry})")
    if signal:
        print(f"  • Senal Detectada                  : {signal['action'].upper()} (${signal['position_size_usd']:,.2f} USD)")
        print(f"  • Motivo                           : {signal['reason']}")

    trade_amount = 1000.0
    route_eval = await router.calculate_optimal_route("USDT", "USDC", amount_usd=trade_amount)
    trc20_cost = router.calculate_binance_route_cost(trade_amount, "USDT", NetworkType.TRC20)
    bep20_cost = router.calculate_binance_route_cost(trade_amount, "USDT", NetworkType.BEP20)
    erc20_cost = router.calculate_binance_route_cost(trade_amount, "USDT", NetworkType.ERC20)

    print(f"\n  Evaluacion de Ruteo Optimo para Swap de ${trade_amount:,.2f} USD:")
    print(f"    - Swap Directo en Ripio (Spread + 0.30% Taker) : ${route_eval['ripio_direct_cost_usd']:.2f} USD (1 min)")
    print(f"    - Puente Binance via BEP20 (BSC)               : ${bep20_cost['total_cost_usd']:.2f} USD (45 min)")
    print(f"    - Puente Binance via TRC20 (Tron - Preferida)  : ${trc20_cost['total_cost_usd']:.2f} USD (45 min)")
    print(f"    - Puente Binance via ERC20 (Ethereum)          : ${erc20_cost['total_cost_usd']:.2f} USD (45 min)")
    print(f"    => RUTA SELECCIONADA: {route_eval['route_type'].value.upper()} | Rentable: {'SI' if route_eval['is_profitable'] else 'NO'} (Ganancia Est.: ${route_eval['expected_gain_usd']:.2f} USD)\n")

    # 4. Backtest Cuantitativo Completo
    print("[PASO 4/4] MOTOR DE BACKTESTING CUANTITATIVO (WALK-FORWARD + MONTE CARLO + LUCK vs SKILL)")
    print("-" * 80)
    bt_args = SimpleNamespace(
        mode="full",
        strategy="mean_reversion",
        data=None,
        synthetic=True,
        days=days,
        capital=capital,
        lookback=20,
        z_threshold=2.0,
        train_window=10,
        test_window=5,
        num_folds=4,
        simulations=500,
        permutations=500,
        output_dir="reports",
        export=False,
    )
    analysis = await run_full_analysis(bt_args, save_files=False)

    print("\n" + "=" * 80)
    print("  DEMO EN VIVO FINALIZADA CON EXITO — TODOS LOS SISTEMAS OPERATIVOS")
    print("=" * 80 + "\n")
    return analysis
