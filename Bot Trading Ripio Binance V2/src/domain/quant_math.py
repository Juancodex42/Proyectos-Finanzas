"""
Módulo de funciones matemáticas puras del dominio cuantitativo.
Implementa Avellaneda-Stoikov, Ornstein-Uhlenbeck, ADF y métricas de riesgo.
Referencia de diseño: docs/ARQUITECTURA.md
"""

from typing import Dict, List, Optional, Sequence, Tuple
import numpy as np


# =====================================================================
# 1. STATISTICAL ARBITRAGE & ORNSTEIN-UHLENBECK
# =====================================================================

def calculate_z_score(series: Sequence[float]) -> Optional[float]:
    """Calcula el Z-score de la última observación respecto a la ventana histórica."""
    if len(series) < 2:
        return None
    arr = np.asarray(series, dtype=float)
    mean = float(np.mean(arr))
    std = float(np.std(arr))
    if std <= 1e-12:
        return 0.0
    return float((arr[-1] - mean) / std)


def calculate_spread_bps(ratio: float, parity: float = 1.0) -> float:
    """Calcula el desvío absoluto respecto a la paridad en basis points (bps)."""
    if parity <= 0:
        return 0.0
    return float(abs(ratio - parity) / parity * 10000.0)


def half_life(spread: Sequence[float]) -> float:
    """
    Calcula el half-life de reversión a la media (Ornstein-Uhlenbeck).
    Ajusta por OLS: dS_t = alpha + lambda * S_{t-1} + eps_t -> half_life = -ln(2)/lambda.
    """
    arr = np.asarray(spread, dtype=float)
    if len(arr) < 5:
        return float("inf")

    s_lag = arr[:-1]
    delta_s = np.diff(arr)
    var_lag = float(np.var(s_lag))
    if var_lag <= 1e-12:
        return 1.0

    cov = float(np.mean((s_lag - np.mean(s_lag)) * (delta_s - np.mean(delta_s))))
    lam = cov / var_lag

    if lam >= -1e-9:
        return float("inf")

    hl = -np.log(2.0) / lam
    return float(max(hl, 0.5))


def check_cointegration(
    series_x: Sequence[float],
    series_y: Sequence[float],
    pvalue_threshold: float = 0.05
) -> Tuple[bool, float]:
    """
    Verifica estacionariedad del spread mediante regresión Dickey-Fuller / ADF.
    Un spread estacionario exhibe coeficiente autorregresivo phi_1 < 1 (lambda < 0).
    """
    x = np.asarray(series_x, dtype=float)
    y = np.asarray(series_y, dtype=float)
    if len(x) < 20 or len(y) < 20 or len(x) != len(y):
        return False, 1.0

    spread = x - y
    if float(np.std(spread)) <= 1e-12:
        return True, 0.0

    # Intentar test ADF exacto de statsmodels si está instalado
    try:
        from statsmodels.tsa.stattools import adfuller
        adf_result = adfuller(spread, maxlag=1, regression="c", autolag=None)
        p_value = float(adf_result[1])
        t_stat = float(adf_result[0])
        is_stationary = bool(p_value < pvalue_threshold or t_stat < -2.5)
        return is_stationary, p_value
    except Exception:
        pass

    # Fallback determinista: regresión de diferencias dS_t = alpha + lambda * S_{t-1}
    s_lag = spread[:-1] - np.mean(spread[:-1])
    delta_s = np.diff(spread)
    denom = float(np.sum(s_lag ** 2))
    if denom <= 1e-12:
        return False, 1.0

    lam = float(np.sum(s_lag * delta_s) / denom)
    residuals = delta_s - lam * s_lag
    dof = max(len(delta_s) - 2, 1)
    se_lam = float(np.sqrt((np.sum(residuals ** 2) / dof) / denom))
    t_stat = lam / se_lam if se_lam > 1e-12 else 0.0

    # phi_1 = 1 + lam < 1 equivale a lam < 0; aproximación monótona de p-value DF
    if lam >= 0:
        return False, 1.0
    p_value = float(np.clip(np.exp(0.95 * (t_stat + 1.5)), 0.0001, 0.9999))
    return bool(p_value < pvalue_threshold), p_value


test_cointegration = check_cointegration
test_cointegration.__test__ = False


# =====================================================================
# 2. AVELLANEDA-STOIKOV MARKET MAKING
# =====================================================================

def inventory_skew(
    mid_price: float,
    inventory_usd: float,
    max_inventory_usd: float,
    gamma: float,
    sigma: float
) -> float:
    """
    Calcula la penalización de inventario de Avellaneda-Stoikov en moneda cotizada:
    penalty = mid_price * gamma * (q / q_max) * sigma^2.
    """
    if max_inventory_usd <= 0:
        return 0.0
    q_norm = inventory_usd / max_inventory_usd
    penalty_pct = gamma * q_norm * (sigma ** 2)
    return float(penalty_pct * mid_price)


def reservation_price(
    mid_price: float,
    inventory_usd: float,
    max_inventory_usd: float,
    gamma: float,
    sigma: float
) -> float:
    """Calcula el precio de indiferencia o reserva r = s - penalty(q, gamma, sigma)."""
    penalty = inventory_skew(mid_price, inventory_usd, max_inventory_usd, gamma, sigma)
    return float(mid_price - penalty)


def optimal_spread(
    mid_price: float,
    target_spread_bps: float,
    sigma: float,
    maker_fee: float,
    gamma: float = 0.1,
    k: float = 1.5
) -> float:
    """Calcula el spread óptimo ajustado por volatilidad y piso de comisiones."""
    base_spread_ars = (target_spread_bps / 10000.0) * mid_price
    volatility_multiplier = 1.0 + (sigma / 0.5)
    raw_spread = base_spread_ars * volatility_multiplier
    min_spread_ars = (maker_fee * 2.0 + 0.001) * mid_price
    return float(max(raw_spread, min_spread_ars))


# =====================================================================
# 3. PERFORMANCE & RISK METRICS
# =====================================================================

def sharpe_ratio(
    returns: Sequence[float],
    periods_per_year: float = 252.0,
    risk_free_rate: float = 0.0
) -> float:
    """Calcula el ratio de Sharpe anualizado según la frecuencia de las barras."""
    arr = np.asarray(returns, dtype=float)
    if len(arr) < 2:
        return 0.0
    excess = arr - (risk_free_rate / periods_per_year)
    std = float(np.std(excess))
    if std <= 1e-12:
        return 0.0
    return float((np.mean(excess) / std) * np.sqrt(periods_per_year))


def sortino_ratio(
    returns: Sequence[float],
    periods_per_year: float = 252.0,
    target_return: float = 0.0
) -> float:
    """Calcula el ratio de Sortino anualizado penalizando solo volatilidad negativa."""
    arr = np.asarray(returns, dtype=float)
    if len(arr) < 2:
        return 0.0
    downside = arr[arr < target_return] - target_return
    if len(downside) == 0:
        return 0.0
    downside_std = float(np.sqrt(np.mean(downside ** 2)))
    if downside_std <= 1e-12:
        return 0.0
    return float((np.mean(arr) - target_return) / downside_std * np.sqrt(periods_per_year))


def max_drawdown(equity_values: Sequence[float]) -> float:
    """Calcula el Maximum Drawdown porcentual (0 a 100) sobre una curva de capital."""
    arr = np.asarray(equity_values, dtype=float)
    if len(arr) == 0:
        return 0.0
    peaks = np.maximum.accumulate(arr)
    valid = peaks > 0
    if not np.any(valid):
        return 0.0
    drawdowns = np.zeros_like(arr)
    drawdowns[valid] = (peaks[valid] - arr[valid]) / peaks[valid]
    return float(np.max(drawdowns) * 100.0)


def permutation_test_signals(
    gross_pnls: Sequence[float],
    fee_costs: Sequence[float],
    num_permutations: int = 1000,
    seed: Optional[int] = 42
) -> Dict[str, float]:
    """
    Test de permutación de signos de señales (Fama & French / White Reality Check).
    Invierte aleatoriamente la dirección (+1/-1) de los retornos brutos y resta fees,
    contrastando la media neta real contra la hipótesis nula de entradas aleatorias.
    """
    gross = np.asarray(gross_pnls, dtype=float)
    fees = np.asarray(fee_costs, dtype=float)
    n = len(gross)
    if n == 0:
        return {"t_statistic": 0.0, "p_value": 1.0, "real_mean": 0.0, "null_mean": 0.0}

    real_net = gross - fees
    real_mean = float(np.mean(real_net))
    real_std = float(np.std(real_net))
    t_stat = float(real_mean / (real_std / np.sqrt(n))) if real_std > 1e-12 else 0.0

    rng = np.random.default_rng(seed)
    random_signs = rng.choice([-1.0, 1.0], size=(num_permutations, n))
    null_net_matrix = random_signs * np.abs(gross) - fees
    null_means = np.mean(null_net_matrix, axis=1)

    p_value = float(np.mean(null_means >= real_mean))
    return {
        "t_statistic": t_stat,
        "p_value": p_value,
        "real_mean": real_mean,
        "null_mean": float(np.mean(null_means)),
    }
