import math
import numpy as np


def calculate_wilson_lower_bound(k: int, n: int, confidence: float = 0.95) -> float:
    """
    Calculates the lower bound of the Wilson score confidence interval for a Bernoulli win rate.
    """
    if n <= 0:
        return 0.0
    z = 1.96  # 95% confidence level
    p = k / n
    denom = 1.0 + (z**2) / n
    center = (p + (z**2) / (2 * n)) / denom
    margin = (z * np.sqrt((p * (1.0 - p) / n) + (z**2) / (4 * (n**2)))) / denom
    return float(max(0.0, center - margin))


def binomial_sf(k: int, M: int, p: float) -> float:
    """Calcula la probabilidad de la cola binomial P(X >= M) donde X ~ Binomial(k, p)."""
    if M <= 0:
        return 1.0
    if M > k:
        return 0.0
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    prob = 0.0
    for j in range(M, k + 1):
        prob += math.comb(k, j) * (p ** j) * ((1.0 - p) ** (k - j))
    return max(0.0, min(1.0, float(prob)))


def monte_carlo_vectorized_2d(
    win_rate: float,
    payout: float,
    n_consecutive: int,
    kelly_f: float,
    num_simulations: int = 10000,
    num_cycles: int = 1000
) -> dict:
    """
    Simulacion Monte Carlo 2D Vectorizada (Feature 15).
    Reemplaza bucles anidados de Python por matrices 2D de NumPy.
    Acelera 10,000 simulaciones a sub-milisegundos.
    """
    p_success = win_rate ** n_consecutive
    profit_if_win = ((payout + 1.0) ** n_consecutive) - 1.0

    rand_matrix = np.random.rand(num_simulations, num_cycles)
    win_matrix = rand_matrix < p_success

    multipliers = np.where(win_matrix, 1.0 + kelly_f * profit_if_win, 1.0 - kelly_f)
    multipliers = np.maximum(multipliers, 0.0)

    equity_paths = np.cumprod(multipliers, axis=1)
    
    initial_col = np.ones((num_simulations, 1), dtype=np.float64)
    equity_paths = np.hstack([initial_col, equity_paths])

    peaks = np.maximum.accumulate(equity_paths, axis=1)
    drawdowns = np.where(peaks > 0, (peaks - equity_paths) / peaks, 0.0)
    max_drawdowns = np.max(drawdowns, axis=1)

    final_equities = equity_paths[:, -1]
    ruined = np.any(equity_paths <= 1e-6, axis=1)

    return {
        "final_equity": {
            "mean": float(np.mean(final_equities)),
            "median": float(np.median(final_equities)),
            "p5": float(np.percentile(final_equities, 5)),
            "p95": float(np.percentile(final_equities, 95))
        },
        "ruin_probability": float(np.sum(ruined) / num_simulations),
        "max_drawdowns": {
            "mean": float(np.mean(max_drawdowns)),
            "p95": float(np.percentile(max_drawdowns, 95))
        }
    }
