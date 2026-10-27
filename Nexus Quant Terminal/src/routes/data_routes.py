import os
import glob
import numpy as np
from flask import Blueprint, jsonify, request, current_app
from config import Config
from strategies import STRATEGIES
from routes.utils import (
    load_csv_data,
    clean_json_data,
    sort_intervals,
    get_data_dir,
)

data_bp = Blueprint('data', __name__)


@data_bp.route('/api/data/pairs', methods=['GET'])
def get_pairs():
    data_dir = get_data_dir()
    available_intervals_cfg = current_app.config.get('AVAILABLE_INTERVALS', ['1d', '4h', '1h', '30m', '15m', '5m', '1m']) if current_app else getattr(Config, 'AVAILABLE_INTERVALS', ['1d', '4h', '1h', '30m', '15m', '5m', '1m'])
    all_intervals = set(available_intervals_cfg)

    if not os.path.exists(data_dir):
        return jsonify({'pairs': [], 'intervals': sort_intervals(list(all_intervals))})

    files = glob.glob(os.path.join(data_dir, '*.csv'))
    pairs = set()

    for f in files:
        basename = os.path.basename(f).replace('.csv', '')
        parts = basename.split('_')
        if len(parts) >= 2:
            pairs.add(parts[0])
            all_intervals.add(parts[1])

    available_pairs_cfg = current_app.config.get('AVAILABLE_PAIRS', []) if current_app else getattr(Config, 'AVAILABLE_PAIRS', [])
    return jsonify({
        'pairs': sorted(list(pairs)) or available_pairs_cfg,
        'intervals': sort_intervals(list(all_intervals))
    })


@data_bp.route('/api/data/candles', methods=['GET'])
def get_candles():
    pair = request.args.get('pair', 'BTCUSDT')
    interval = request.args.get('interval', '1h')
    try:
        limit_param = request.args.get('limit', '1000')
        limit = int(limit_param) if limit_param and limit_param.isdigit() else 5000
    except ValueError:
        limit = 5000

    df = load_csv_data(pair, interval)
    if df is None:
        return jsonify({'error': 'Data not found'}), 404

    df_subset = df.tail(limit) if limit > 0 else df

    v_arr = df_subset['volume'].to_numpy() if 'volume' in df_subset else np.zeros(len(df_subset))
    candles = [
        {
            'time': int(t),
            'open': float(o),
            'high': float(h),
            'low': float(l),
            'close': float(c),
            'volume': float(v)
        }
        for t, o, h, l, c, v in zip(
            df_subset['time'].to_numpy(),
            df_subset['open'].to_numpy(),
            df_subset['high'].to_numpy(),
            df_subset['low'].to_numpy(),
            df_subset['close'].to_numpy(),
            v_arr
        )
    ]

    return jsonify({'candles': candles})


@data_bp.route('/api/strategies', methods=['GET'])
def get_strategies():
    try:
        # Ranking cuantitativo oficial (1 al 13 por robustez y retorno por unidad)
        ranked_keys = [
            ("ema_cross", "1. 🥇 EMA Cross [93.3% Robustez | +9.2% ROI/Camp]"),
            ("volatility_squeeze", "2. 🥈 Volatility Squeeze [80.0% Robustez | +11.6% ROI/Camp]"),
            ("volatility_squeeze_ml", "3. 🥉 Volatility Squeeze MTF ML [73.3% Robustez | +7.0% ROI/Camp]"),
            ("daily_confluence", "4. 🛡️ Confluencia Diaria Multi-Activo [73.3% Robustez | +5.2% ROI]"),
            ("mean_reversion", "5. ⚡ Reversión a la Media Bollinger [60.0% Robustez]"),
            ("bollinger_bounce", "6. 🌊 Rebote Volatilidad Bollinger [57.1% Robustez | +4.8% ROI]"),
            ("mtf_tcve", "7. ⏱️ MTF Trend Volume Exhaustion [46.2% Robustez | +5.4% ROI]"),
            ("genetic_composite", "8. 🧬 Combinada Genética Optimizada [40.0% Robustez]"),
            ("islg_rs", "9. 📈 Barridos de Liquidez Institucional (ISLG) [33.3% Robustez]"),
            ("rsi_extremes", "10. 📊 Extremos RSI Rápido [33.3% Robustez]"),
            ("support_resistance", "11. 🏆 Soporte y Resistencia Cuántico [26.7% Robustez]"),
            ("deesr", "12. 🎯 Doble Envoltura Extrema (DEESR) [26.7% Robustez]"),
            ("climax_reversal", "13. 🔥 Agotamiento Clímax por Rachas [20.0% Robustez]")
        ]

        result = []
        for key, display_label in ranked_keys:
            if key in STRATEGIES:
                instance = STRATEGIES[key]()
                result.append({
                    'name': key,
                    'display_name': display_label,
                    'raw_name': instance.name,
                    'description': instance.description,
                    'params': instance.get_params_schema()
                })
        return jsonify(clean_json_data({'strategies': result}))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
