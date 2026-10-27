"""Endpoints de ejecución de campañas Barbell (Six-Bullets) y planes apalancados clásicos.
Calcula dimensionamiento de posiciones, márgenes y niveles SL/TP basados en volatilidad ATR.
Referencia de diseño: docs/ARQUITECTURA.md"""

import numpy as np
from flask import Blueprint, jsonify, request
from strategies import STRATEGIES
from routes.utils import (
    simulator,
    load_csv_data,
    clean_json_data,
)

plan_bp = Blueprint('plan', __name__)


@plan_bp.route('/api/campaign/six-bullets', methods=['POST'])
def run_six_bullets_campaign():
    """
    Simula la campaña Barbell clásica de 6 balas (100% de la bala en riesgo: 1R = $33.33)
    con meta de duplicación asimétrica en 2 rondas.
    """
    try:
        req = request.json or {}
        pair = req.get('pair', 'BTCUSDT')
        interval = req.get('interval', '1h')
        strategy_name = req.get('strategy', 'islg_rs')
        params = req.get('params', {})
        sl_atr = float(req.get('sl_atr', 1.5))
        tp_atr = float(req.get('tp_atr', 3.0))
        rr_ratio = float(req.get('rr_ratio', 2.0)) if req.get('rr_ratio') else None
        max_holding = int(req.get('max_holding', 20))
        initial_capital = float(req.get('initial_capital', 1000.0))
        bullet_risk = float(req.get('bullet_risk', 33.3333))

        df = load_csv_data(pair, interval)
        if df is None:
            return jsonify({'error': f'Datos no encontrados para {pair} {interval}'}), 404

        if strategy_name not in STRATEGIES:
            strategy_name = 'islg_rs'
        strat = STRATEGIES[strategy_name]()
        sigs = strat.generate_signals(df, params) if params else strat.generate_signals(df)

        sim_res = simulator.run(
            df=df,
            signals=sigs,
            sl_atr=sl_atr,
            tp_atr=tp_atr,
            rr_ratio=rr_ratio,
            max_holding=max_holding,
            bullet_risk=bullet_risk,
            initial_capital=initial_capital,
            mode='BARBELL',
            n_consecutive=3,
            risk_ratio=0.20,
            target_ratio=5.0,
            classic_mode=True
        )

        return jsonify(clean_json_data(sim_res))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@plan_bp.route('/api/classic/leverage-plan', methods=['GET', 'POST'])
def get_classic_leverage_plan():
    """
    Calcula en tiempo real la recomendación de apalancamiento, margen, tamaño nominal
    y parámetros de Stop Loss / Take Profit para duplicar el patrimonio en trading apalancado clásico.
    """
    try:
        from engine.optimizers.classic import ClassicOptimizer
        req = request.get_json(silent=True) or request.args.to_dict() or {}
        
        base_patrimony = float(req.get('base_patrimony', 1000.0))
        monthly_flow = float(req.get('monthly_flow', 200.0))
        pair = req.get('pair', 'BTCUSDT')
        interval = req.get('interval', '4h')
        sl_multiplier = float(req.get('sl_multiplier', 1.5))
        tp_multiplier = float(req.get('tp_multiplier', 3.0))
        direction = req.get('direction', 'LONG')

        # Si no se provee entry_price o atr_val, leer del dataset
        entry_price = float(req.get('entry_price', 0.0))
        atr_val = float(req.get('atr_val', 0.0))

        if entry_price <= 0.0 or atr_val <= 0.0:
            df = load_csv_data(pair, interval)
            if df is not None and len(df) > 15:
                entry_price = float(df['close'].iloc[-1])
                high = df['high'].values
                low = df['low'].values
                close = df['close'].values
                tr = np.maximum(high[1:] - low[1:], np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])))
                atr_val = float(np.mean(tr[-14:]))
            else:
                entry_price = 65000.0 if 'BTC' in pair else (3500.0 if 'ETH' in pair else 100.0)
                atr_val = entry_price * 0.02

        plan = ClassicOptimizer.calculate_leveraged_execution_plan(
            base_patrimony=base_patrimony,
            monthly_flow=monthly_flow,
            entry_price=entry_price,
            atr_val=atr_val,
            sl_multiplier=sl_multiplier,
            tp_multiplier=tp_multiplier,
            direction=direction
        )
        plan['pair'] = pair
        plan['interval'] = interval

        return jsonify(clean_json_data(plan))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
