import json
import queue
import threading
import time
import numpy as np
from flask import Blueprint, jsonify, request
from strategies import STRATEGIES
from routes.utils import (
    simulator,
    stats_engine,
    load_csv_data,
    clean_json_data,
    is_safe_symbol,
    is_safe_interval,
    sse_response,
)

backtest_bp = Blueprint('backtest', __name__)

@backtest_bp.route('/api/backtest', methods=['POST'])
def run_backtest():
    try:
        req = request.json or {}
        strategy_name = req.get('strategy', '')
        params = req.get('params', {})
        pair = req.get('pair', 'BTCUSDT')
        interval = req.get('interval', '1h')
        if not is_safe_symbol(pair) or not is_safe_interval(interval):
            return jsonify({'error': 'Par o intervalo no válido.'}), 400
        expiry_candles = int(req.get('expiry_candles', 1))
        payout = float(req.get('payout', 0.92))
        
        if expiry_candles < 1:
            return jsonify({'error': 'expiry_candles debe ser mayor o igual a 1.'}), 400
        if payout < 0.0 or payout > 2.0:
            return jsonify({'error': 'payout debe estar entre 0.0 y 2.0.'}), 400
        if strategy_name in ['ema_cross', 'genetic_composite']:
            fast = int(params.get('ema_fast_period' if strategy_name == 'genetic_composite' else 'fast_period', 9))
            slow = int(params.get('ema_slow_period' if strategy_name == 'genetic_composite' else 'slow_period', 21))
            if fast <= 0 or slow <= 0:
                return jsonify({'error': 'Los periodos de las EMAs deben ser mayores a 0.'}), 400
            if fast >= slow:
                return jsonify({'error': 'El periodo de la EMA rápida debe ser menor que el de la lenta.'}), 400

        # Load data
        df = load_csv_data(pair, interval)
        if df is None:
            return jsonify({'error': f'Datos no encontrados para {pair} {interval}'}), 404

        # Get strategy
        if strategy_name not in STRATEGIES:
            return jsonify({'error': f'Estrategia "{strategy_name}" no encontrada. Disponibles: {list(STRATEGIES.keys())}'}), 400

        strategy_class = STRATEGIES[strategy_name]
        strategy = strategy_class()

        # Generate signals
        signals = strategy.generate_signals(df, params)

        mode = req.get('mode', 'SIMPLE')
        n_consecutive = int(req.get('n_consecutive', 5))
        bet_fraction = float(req.get('bet_fraction', 0.1))
        if bet_fraction <= 0.0 or bet_fraction > 1.0:
            return jsonify({'error': 'bet_fraction debe ser un número positivo entre 0.0 y 1.0.'}), 400

        allow_overlapping = bool(req.get('allow_overlapping', False))
        max_concurrent_trades = int(req.get('max_concurrent_trades', 1))
        tie_rule = req.get('tie_rule', 'RETURN_STAKE')

        sl_atr = float(req.get('sl_atr', 1.5)) if req.get('sl_atr') is not None or params.get('sl_atr') is not None else 1.5
        tp_atr = float(req.get('tp_atr', 3.0)) if req.get('tp_atr') is not None or params.get('tp_atr') is not None else 3.0
        rr_ratio = float(req.get('rr_ratio')) if req.get('rr_ratio') is not None else (float(params.get('rr_ratio')) if params.get('rr_ratio') is not None else None)
        max_holding = int(req.get('max_holding', 20)) if req.get('max_holding') is not None else int(req.get('expiry_candles', 20))
        risk_per_bullet = float(req.get('risk_per_bullet', req.get('bullet_risk', 33.3333)))
        fee_pct = float(req.get('fee_pct', 0.0005))
        slippage_pct = float(req.get('slippage_pct', 0.0002))
        classic_mode = bool(req.get('classic_mode', True))

        # Run simulator
        sim_results = simulator.run(
            df, signals,
            expiry_candles=expiry_candles,
            payout=payout,
            initial_capital=1000.0,
            mode=mode,
            n_consecutive=n_consecutive,
            bet_fraction=bet_fraction,
            allow_overlapping=allow_overlapping,
            max_concurrent_trades=max_concurrent_trades,
            tie_rule=tie_rule,
            sl_atr=sl_atr,
            tp_atr=tp_atr,
            rr_ratio=rr_ratio,
            max_holding=max_holding,
            bullet_risk=risk_per_bullet,
            fee_pct=fee_pct,
            slippage_pct=slippage_pct,
            classic_mode=classic_mode
        )

        # Run statistics
        trades = sim_results['trades']
        stats = {}
        if len(trades) > 0:
            stats = stats_engine.analyze(trades, df=df)

        # Build signals list for chart markers with full execution data
        signal_markers = []
        last_exit = 0
        for t in trades:
            e_time = t.get('entry_time', t.get('time', 0))
            x_time = t.get('exit_time', e_time)
            if e_time and e_time >= last_exit:
                e_sec = int(e_time / 1000) if e_time > 2**32 else int(e_time)
                x_sec = int(x_time / 1000) if x_time > 2**32 else int(x_time)
                
                signal_markers.append({
                    'time': e_sec,
                    'direction': t.get('direction', 'LONG'),
                    'entry_price': t.get('entry_price'),
                    'sl_price': t.get('sl_price'),
                    'tp_price': t.get('tp_price'),
                    'exit_price': t.get('exit_price'),
                    'pnl': t.get('pnl', 0.0),
                    'bet_size': t.get('bet_size', 0.0),
                    'result': t.get('result', 'WIN')
                })
                signal_markers.append({
                    'time': x_sec,
                    'direction': 'EXIT',
                    'result': t.get('result', 'WIN'),
                    'trade_direction': t.get('direction', 'LONG'),
                    'entry_price': t.get('entry_price'),
                    'sl_price': t.get('sl_price'),
                    'tp_price': t.get('tp_price'),
                    'exit_price': t.get('exit_price'),
                    'exit_reason': t.get('exit_reason', 'TP' if t.get('result') == 'WIN' else 'SL'),
                    'pnl': t.get('pnl', 0.0),
                    'bet_size': t.get('bet_size', 0.0)
                })
                last_exit = x_time

        # Convert equity curve times to seconds
        equity_curve = []
        for ec in sim_results['equity_curve']:
            t = ec.get('time')
            if t is not None:
                t_val = float(t)
                if t_val > 2**32:
                    t_val = t_val / 1000
                equity_curve.append({'time': int(t_val), 'equity': ec['equity']})

        # Convert trade times to seconds with complete classic fields
        formatted_trades = []
        for trade in trades:
            t = trade.get('time')
            t_val = None
            if t is not None:
                t_val = float(t)
                if t_val > 2**32:
                    t_val = t_val / 1000
                t_val = int(t_val)
            formatted_trades.append({
                'time': t_val,
                'direction': trade.get('direction', 'LONG'),
                'entry_price': trade.get('entry_price'),
                'sl_price': trade.get('sl_price'),
                'tp_price': trade.get('tp_price'),
                'exit_price': trade.get('exit_price'),
                'exit_reason': trade.get('exit_reason', 'TP' if trade.get('result') == 'WIN' else 'SL'),
                'duration': trade.get('duration', trade.get('holding_candles', 1)),
                'holding_candles': trade.get('holding_candles', trade.get('duration', 1)),
                'r_multiple': trade.get('r_multiple', round(trade.get('pnl', 0.0) / max(1.0, trade.get('bet_size', 1.0)), 2)),
                'result': trade.get('result', 'WIN'),
                'pnl': trade.get('pnl', 0.0),
                'bet_size': trade.get('bet_size', trade.get('position_size', 0.0)),
                'position_size': trade.get('position_size', trade.get('bet_size', 0.0)),
                'margin_used': trade.get('margin_used', trade.get('bullet_risk', risk_per_bullet)),
                'leverage': trade.get('leverage', round(float(trade.get('position_size', 0.0)) / max(1.0, float(trade.get('margin_used', risk_per_bullet))), 1)),
                'sl_pct': trade.get('sl_pct', 0.02)
            })

        response = {
            'trades': formatted_trades,
            'equity_curve': equity_curve,
            'stats': stats,
            'signals': signal_markers,
            'summary': sim_results['summary']
        }

        return jsonify(clean_json_data(response))

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@backtest_bp.route('/api/backtest-stream', methods=['GET'])
def run_backtest_stream():
    strategy_name = request.args.get('strategy', '')
    params_str = request.args.get('params', '{}')
    try:
        params = json.loads(params_str)
    except Exception:
        params = {}
    pair = request.args.get('pair', 'BTCUSDT')
    interval = request.args.get('interval', '1h')
    if not is_safe_symbol(pair) or not is_safe_interval(interval):
        return jsonify({'error': 'Par o intervalo no válido.'}), 400
    expiry_candles = int(request.args.get('expiry_candles', 1))
    payout = float(request.args.get('payout', 0.92))
    mode = request.args.get('mode', 'SIMPLE')
    n_consecutive = int(request.args.get('n_consecutive', 5))
    bet_fraction = float(request.args.get('bet_fraction', 0.1))

    sl_atr = float(request.args.get('sl_atr', 1.5)) if request.args.get('sl_atr') is not None or params.get('sl_atr') is not None else 1.5
    tp_atr = float(request.args.get('tp_atr', 3.0)) if request.args.get('tp_atr') is not None or params.get('tp_atr') is not None else 3.0
    rr_ratio = float(request.args.get('rr_ratio')) if request.args.get('rr_ratio') is not None else (float(params.get('rr_ratio')) if params.get('rr_ratio') is not None else None)
    max_holding = int(request.args.get('max_holding', 20)) if request.args.get('max_holding') is not None else int(expiry_candles)
    risk_per_bullet = float(request.args.get('risk_per_bullet', request.args.get('bullet_risk', 33.3333)))
    fee_pct = float(request.args.get('fee_pct', 0.0005))
    slippage_pct = float(request.args.get('slippage_pct', 0.0002))
    classic_mode = bool(request.args.get('classic_mode', 'true').lower() == 'true')
    
    if expiry_candles < 1:
        return jsonify({'error': 'expiry_candles debe ser mayor o igual a 1.'}), 400
    if payout < 0.0 or payout > 2.0:
        return jsonify({'error': 'payout debe estar entre 0.0 y 2.0.'}), 400
    if n_consecutive < 1 or n_consecutive > 50:
        return jsonify({'error': 'n_consecutive debe estar entre 1 y 50.'}), 400
    if not (0.0 <= bet_fraction <= 1.0):
        return jsonify({'error': 'bet_fraction debe estar entre 0.0 y 1.0.'}), 400
    if strategy_name in ['ema_cross', 'genetic_composite']:
        fast = int(params.get('ema_fast_period' if strategy_name == 'genetic_composite' else 'fast_period', 9))
        slow = int(params.get('ema_slow_period' if strategy_name == 'genetic_composite' else 'slow_period', 21))
        if fast <= 0 or slow <= 0:
            return jsonify({'error': 'Los periodos de las EMAs deben ser mayores a 0.'}), 400
        if fast >= slow:
            return jsonify({'error': 'El periodo de la EMA rápida debe ser menor que el de la lenta.'}), 400

    def event_stream():
        try:
            yield f"data: {json.dumps({'type': 'log', 'message': f'Cargando datos para {pair} {interval}...'})}\n\n"
            df = load_csv_data(pair, interval)
            if df is None:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Datos no encontrados para {pair} {interval}'})}\n\n"
                return

            if strategy_name not in STRATEGIES:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Estrategia {strategy_name} no encontrada.'})}\n\n"
                return

            strategy = STRATEGIES[strategy_name]()
            yield f"data: {json.dumps({'type': 'log', 'message': f'Generando señales con {strategy.name}...'})}\n\n"
            signals = strategy.generate_signals(df, params)

            q = queue.Queue()
            start_time = time.time()
            cancel_event = threading.Event()

            def progress_callback(progress_ratio):
                if cancel_event.is_set():
                    raise InterruptedError("Client disconnected")
                elapsed = time.time() - start_time
                eta = (elapsed / progress_ratio) * (1.0 - progress_ratio) if progress_ratio > 0 else 0
                q.put({
                    'type': 'progress',
                    'progress': progress_ratio * 100,
                    'eta': eta,
                    'log': f"Ejecutando backtest: {progress_ratio * 100:.1f}%"
                })

            def worker():
                try:
                    sim_results = simulator.run(
                        df, signals,
                        expiry_candles=expiry_candles,
                        payout=payout,
                        initial_capital=1000.0,
                        mode=mode,
                        n_consecutive=n_consecutive,
                        bet_fraction=bet_fraction,
                        progress_callback=progress_callback,
                        sl_atr=sl_atr,
                        tp_atr=tp_atr,
                        rr_ratio=rr_ratio,
                        max_holding=max_holding,
                        bullet_risk=risk_per_bullet,
                        fee_pct=fee_pct,
                        slippage_pct=slippage_pct,
                        classic_mode=classic_mode
                    )
                    q.put({'type': 'sim_results', 'data': sim_results})
                except InterruptedError:
                    pass
                except Exception as ex:
                    q.put({'type': 'error', 'message': str(ex)})

            threading.Thread(target=worker, daemon=True).start()

            sim_results = None
            try:
                while True:
                    item = q.get()
                    if item['type'] == 'progress':
                        yield f"data: {json.dumps(item)}\n\n"
                    elif item['type'] == 'error':
                        yield f"data: {json.dumps(item)}\n\n"
                        return
                    elif item['type'] == 'sim_results':
                        sim_results = item['data']
                        break
            finally:
                cancel_event.set()

            yield f"data: {json.dumps({'type': 'log', 'message': 'Analizando estadísticas y curvas de capital...'})}\n\n"
            trades = sim_results['trades']
            stats = {}
            if len(trades) > 0:
                stats = stats_engine.analyze(trades, df=df)

            signal_markers = []
            last_exit = 0
            for t in trades:
                e_time = t.get('entry_time', t.get('time', 0))
                x_time = t.get('exit_time', e_time)
                if e_time and e_time >= last_exit:
                    e_sec = int(e_time / 1000) if e_time > 2**32 else int(e_time)
                    x_sec = int(x_time / 1000) if x_time > 2**32 else int(x_time)
                    
                    signal_markers.append({
                        'time': e_sec,
                        'direction': t.get('direction', 'LONG'),
                        'entry_price': t.get('entry_price'),
                        'sl_price': t.get('sl_price'),
                        'tp_price': t.get('tp_price'),
                        'exit_price': t.get('exit_price'),
                        'pnl': t.get('pnl', 0.0),
                        'bet_size': t.get('bet_size', 0.0),
                        'result': t.get('result', 'WIN')
                    })
                    signal_markers.append({
                        'time': x_sec,
                        'direction': 'EXIT',
                        'result': t.get('result', 'WIN'),
                        'trade_direction': t.get('direction', 'LONG'),
                        'entry_price': t.get('entry_price'),
                        'sl_price': t.get('sl_price'),
                        'tp_price': t.get('tp_price'),
                        'exit_price': t.get('exit_price'),
                        'exit_reason': t.get('exit_reason', 'TP' if t.get('result') == 'WIN' else 'SL'),
                        'pnl': t.get('pnl', 0.0),
                        'bet_size': t.get('bet_size', 0.0)
                    })
                    last_exit = x_time

            equity_curve = []
            for ec in sim_results['equity_curve']:
                t = ec.get('time')
                if t is not None:
                    t_val = float(t)
                    if t_val > 2**32:
                        t_val = t_val / 1000
                    equity_curve.append({'time': int(t_val), 'equity': ec['equity']})

            formatted_trades = []
            for trade in trades:
                t = trade.get('time')
                t_val = None
                if t is not None:
                    t_val = float(t)
                    if t_val > 2**32:
                        t_val = t_val / 1000
                    t_val = int(t_val)
                formatted_trades.append({
                    'time': t_val,
                    'direction': trade.get('direction', 'LONG'),
                    'entry_price': trade.get('entry_price'),
                    'sl_price': trade.get('sl_price'),
                    'tp_price': trade.get('tp_price'),
                    'exit_price': trade.get('exit_price'),
                    'exit_reason': trade.get('exit_reason', 'TP' if trade.get('result') == 'WIN' else 'SL'),
                    'duration': trade.get('duration', trade.get('holding_candles', 1)),
                    'holding_candles': trade.get('holding_candles', trade.get('duration', 1)),
                    'r_multiple': trade.get('r_multiple', round(trade.get('pnl', 0.0) / max(1.0, trade.get('bet_size', 1.0)), 2)),
                    'result': trade.get('result', 'WIN'),
                    'pnl': trade.get('pnl', 0.0),
                    'bet_size': trade.get('bet_size', trade.get('position_size', 0.0)),
                    'position_size': trade.get('position_size', trade.get('bet_size', 0.0))
                })

            response = {
                'trades': formatted_trades,
                'equity_curve': equity_curve,
                'stats': stats,
                'signals': signal_markers,
                'summary': sim_results['summary']
            }

            yield f"data: {json.dumps({'type': 'result', 'data': response})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return sse_response(event_stream())
