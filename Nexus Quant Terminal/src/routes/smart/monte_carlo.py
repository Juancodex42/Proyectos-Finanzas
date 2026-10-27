"""
Monte Carlo simulation endpoints for Nexus Quant Terminal Smart Engine.
Provides discrete and continuous probability path generation, ruin probability
estimations, and quantile volatility cones (P5 - P95).
"""
import traceback
from flask import Blueprint, jsonify, request
from routes.utils import optimizer, clean_json_data

monte_carlo_bp = Blueprint('smart_monte_carlo', __name__)


@monte_carlo_bp.route('/api/montecarlo', methods=['POST'])
@monte_carlo_bp.route('/api/montecarlo-simulation', methods=['POST'])
@monte_carlo_bp.route('/api/smart/montecarlo', methods=['POST'])
def run_montecarlo():
    """Executes continuous Monte Carlo simulation (up to 10,000 paths) with path subsampling."""
    try:
        req = request.json or {}
        win_rate = float(req.get('win_rate', 0.5))
        payout = float(req.get('payout', 0.92))
        n = int(req.get('n', 3))
        kelly_f = float(req.get('kelly_f', 0.1))
        num_simulations = min(int(req.get('num_simulations', 5000)), 10000)
        num_cycles = min(int(req.get('num_cycles', 500)), 2000)

        if not (0.0 <= win_rate <= 1.0):
            return jsonify({'error': 'win_rate debe estar entre 0.0 y 1.0.'}), 400
        if payout < 0.0 or payout > 2.0:
            return jsonify({'error': 'payout debe estar entre 0.0 y 2.0.'}), 400
        if n < 1 or n > 50:
            return jsonify({'error': 'n debe estar entre 1 y 50.'}), 400
        if not (0.0 <= kelly_f <= 1.0):
            return jsonify({'error': 'kelly_f (fracción de apuesta) debe estar entre 0.0 y 1.0.'}), 400

        result = optimizer.monte_carlo(win_rate, payout, n, kelly_f, num_simulations, num_cycles)

        # Subsample paths for JSON (max 50 paths, max 200 points each)
        if 'paths' in result:
            sampled_paths = []
            for path in result['paths'][:50]:
                if len(path) > 200:
                    step = len(path) // 200
                    sampled_paths.append(path[::step])
                else:
                    sampled_paths.append(path)
            result['paths'] = sampled_paths

        return jsonify(clean_json_data(result))

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@monte_carlo_bp.route('/api/montecarlo-discrete', methods=['POST'])
@monte_carlo_bp.route('/api/smart/montecarlo-discrete', methods=['POST'])
def run_montecarlo_discrete():
    """Executes discrete campaign Monte Carlo simulation with Markov streak parameters."""
    try:
        req = request.json or {}
        win_rate = float(req.get('win_rate', 0.55))
        payout = float(req.get('payout', 0.85))
        n_consecutive = int(req.get('n_consecutive', 4))
        bet_fraction = float(req.get('bet_fraction', 0.1))
        risk_capital = float(req.get('risk_capital', 200.0))
        target_capital = float(req.get('target_capital', 1000.0))
        num_simulations = min(int(req.get('num_simulations', 5000)), 10000)
        p_ww = float(req['p_ww']) if req.get('p_ww') is not None else None
        p_wl = float(req['p_wl']) if req.get('p_wl') is not None else None

        if not (0.0 <= win_rate <= 1.0):
            return jsonify({'error': 'win_rate debe estar entre 0.0 y 1.0.'}), 400
        if payout < 0.0 or payout > 2.0:
            return jsonify({'error': 'payout debe estar entre 0.0 y 2.0.'}), 400
        if n_consecutive < 1 or n_consecutive > 50:
            return jsonify({'error': 'n_consecutive debe estar entre 1 y 50.'}), 400
        if not (0.0 <= bet_fraction <= 1.0):
            return jsonify({'error': 'bet_fraction debe estar entre 0.0 y 1.0.'}), 400
        if risk_capital <= 0 or target_capital <= 0:
            return jsonify({'error': 'El capital de riesgo y el capital objetivo deben ser mayores a 0.'}), 400
        if target_capital <= risk_capital:
            return jsonify({'error': 'El capital objetivo debe ser mayor que el capital de riesgo.'}), 400

        result = optimizer.monte_carlo_discrete(
            win_rate=win_rate,
            payout=payout,
            n_consecutive=n_consecutive,
            bet_fraction=bet_fraction,
            risk_capital=risk_capital,
            target_capital=target_capital,
            num_simulations=num_simulations,
            p_ww=p_ww,
            p_wl=p_wl
        )
        return jsonify(clean_json_data(result))

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
