import io
import csv
import json
import html as html_lib
from datetime import datetime
from flask import Blueprint, jsonify, request, Response
from werkzeug.utils import secure_filename
from engine.exporter import StrategyExporter

export_bp = Blueprint('export', __name__)


@export_bp.route('/api/download/csv', methods=['POST', 'GET'])
def download_csv():
    """
    Exporta las operaciones de trading clásico a un archivo CSV estructurado con las 11 columnas,
    identificando en el nombre del archivo y metadatos: estrategia, activo, temporalidad y rango de fechas.
    """
    try:
        if request.method == 'POST':
            req = request.json or {}
            trades = req.get('trades', [])
            pair = req.get('pair', 'TRADE_HISTORY')
            strategy = req.get('strategy', 'NEXUS_QUANT')
            interval = req.get('interval', '4h')
            start_date_req = req.get('start_date')
            end_date_req = req.get('end_date')
        else:
            trades = []
            pair = request.args.get('pair', 'TRADE_HISTORY')
            strategy = request.args.get('strategy', 'NEXUS_QUANT')
            interval = request.args.get('interval', '4h')
            start_date_req = request.args.get('start_date')
            end_date_req = request.args.get('end_date')

        # Determinar rango de fechas a partir de los trades o parámetros
        timestamps = []
        for t in trades:
            e_time = t.get('entry_time') or t.get('time')
            if e_time:
                try:
                    ts = float(e_time)
                    if ts > 2e9:
                        ts = ts / 1000.0
                    timestamps.append(ts)
                except Exception:
                    pass

        if timestamps:
            min_dt = datetime.utcfromtimestamp(min(timestamps))
            max_dt = datetime.utcfromtimestamp(max(timestamps))
            date_range_str = f"{min_dt.strftime('%Y%m%d')}_{max_dt.strftime('%Y%m%d')}"
            date_label = f"{min_dt.strftime('%Y-%m-%d')} a {max_dt.strftime('%Y-%m-%d')}"
        elif start_date_req and end_date_req:
            date_range_str = f"{str(start_date_req).replace('-', '').replace('/', '')}_{str(end_date_req).replace('-', '').replace('/', '')}"
            date_label = f"{start_date_req} a {end_date_req}"
        else:
            date_range_str = datetime.utcnow().strftime('%Y%m%d')
            date_label = "Periodo_Completo"

        safe_strat = secure_filename(str(strategy).replace(' ', '_')) or "NEXUS"
        safe_pair = secure_filename(str(pair).replace(' ', '_')) or "ASSET"
        safe_interval = secure_filename(str(interval)) or "4h"

        output = io.StringIO()
        writer = csv.writer(output, lineterminator='\n')
        
        # Cabecera institucional de 11 columnas clásicas
        writer.writerow([
            "#", "Fecha_Hora", "Par", "Tipo", "Precio_Entrada",
            "Stop_Loss", "Take_Profit", "Precio_Salida", "Duracion_Velas",
            "R_Multiplo", "PnL_USD", "Causa_Salida", "Comisiones_USD"
        ])

        for idx, t in enumerate(trades, 1):
            e_time = t.get('entry_time') or t.get('time')
            if e_time:
                try:
                    ts = float(e_time)
                    if ts > 2e9:
                        ts = ts / 1000.0
                    time_str = datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    time_str = str(e_time)
            else:
                time_str = f"Trade #{idx}"

            writer.writerow([
                idx,
                time_str,
                t.get('pair', pair),
                t.get('direction', 'LONG'),
                f"{float(t.get('entry_price', 0.0)):.5f}",
                f"{float(t.get('sl_price', 0.0)):.5f}" if t.get('sl_price') else "",
                f"{float(t.get('tp_price', 0.0)):.5f}" if t.get('tp_price') else "",
                f"{float(t.get('exit_price', 0.0)):.5f}",
                t.get('duration', t.get('holding_period', 1)),
                f"{float(t.get('r_multiple', 0.0)):+.2f}R",
                f"{float(t.get('pnl', 0.0)):+.2f}",
                t.get('exit_reason', t.get('result', 'WIN')),
                f"{float(t.get('fee', 0.0)):.4f}"
            ])

        csv_content = output.getvalue()
        output.close()

        filename = f"Nexus_Trades_{safe_strat}_{safe_pair}_{safe_interval}_{date_range_str}.csv"
        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@export_bp.route('/api/download/pdf', methods=['POST', 'GET'])
def download_pdf():
    """
    Genera y descarga un reporte institucional de desempeño cuantitativo en formato HTML imprimible/PDF.
    """
    try:
        req = request.json or {} if request.method == 'POST' else request.args
        summary = req.get('summary', {})
        pair_raw = str(req.get('pair', 'BTCUSDT'))
        interval_raw = str(req.get('interval', '4h'))
        strategy_raw = str(req.get('strategy', 'Nexus Quant Multi-Asset'))
        trades = req.get('trades', [])
        start_date_req = req.get('start_date')
        end_date_req = req.get('end_date')

        # Determinar rango de fechas a partir de los trades o parámetros
        timestamps = []
        for t in trades:
            e_time = t.get('entry_time') or t.get('time')
            if e_time:
                try:
                    ts = float(e_time)
                    if ts > 2e9:
                        ts = ts / 1000.0
                    timestamps.append(ts)
                except Exception:
                    pass

        if timestamps:
            min_dt = datetime.utcfromtimestamp(min(timestamps))
            max_dt = datetime.utcfromtimestamp(max(timestamps))
            date_range_str = f"{min_dt.strftime('%Y%m%d')}_{max_dt.strftime('%Y%m%d')}"
            date_label = f"{min_dt.strftime('%Y-%m-%d')} a {max_dt.strftime('%Y-%m-%d')}"
        elif start_date_req and end_date_req:
            date_range_str = f"{str(start_date_req).replace('-', '').replace('/', '')}_{str(end_date_req).replace('-', '').replace('/', '')}"
            date_label = f"{start_date_req} a {end_date_req}"
        else:
            date_range_str = datetime.utcnow().strftime('%Y%m%d')
            date_label = "Periodo_Completo"

        pair = html_lib.escape(pair_raw)
        interval = html_lib.escape(interval_raw)
        strategy = html_lib.escape(strategy_raw)
        period_display = html_lib.escape(date_label)

        tot_trades = summary.get('total_trades', len(trades))
        wr = summary.get('win_rate', 0.0) * 100.0 if summary.get('win_rate', 0) <= 1.0 else summary.get('win_rate', 0.0)
        pf = summary.get('profit_factor', 1.0)
        net_pnl = summary.get('net_pnl', 0.0)
        ev_r = summary.get('expected_value_r', 0.0)
        max_dd = summary.get('max_drawdown', 0.0) * 100.0 if summary.get('max_drawdown', 0) <= 1.0 else summary.get('max_drawdown', 0.0)

        html_report = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Nexus Quant Terminal - Reporte Institucional</title>
    <style>
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; margin: 40px; background: #0B0E14; color: #E2E8F0; }}
        .header {{ border-bottom: 2px solid #00F5A0; padding-bottom: 16px; margin-bottom: 24px; }}
        h1 {{ margin: 0; color: #00F5A0; font-size: 24px; }}
        .subtitle {{ color: #94A3B8; font-size: 14px; margin-top: 4px; }}
        .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 30px; }}
        .card {{ background: #151A23; border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 16px; }}
        .card-label {{ font-size: 12px; color: #94A3B8; text-transform: uppercase; font-weight: 700; }}
        .card-val {{ font-size: 22px; font-weight: 800; margin-top: 8px; color: #FFFFFF; }}
        .green {{ color: #00F5A0; }}
        .cyan {{ color: #38BDF8; }}
        .table {{ width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 13px; }}
        .table th, .table td {{ padding: 10px 12px; border-bottom: 1px solid rgba(255,255,255,0.06); text-align: left; }}
        .table th {{ background: #151A23; color: #00F5A0; font-weight: 700; }}
        .print-btn {{ background: #00F5A0; color: #0B0E14; border: none; padding: 10px 20px; border-radius: 6px; font-weight: 800; cursor: pointer; }}
        @media print {{ .print-btn {{ display: none; }} body {{ background: #fff; color: #000; }} .card {{ border: 1px solid #ccc; }} }}
    </style>
</head>
<body>
    <div class="header">
        <button class="print-btn" onclick="window.print()" style="float: right;">🖨️ Imprimir / Guardar como PDF</button>
        <h1>NEXUS QUANT TERMINAL</h1>
        <div class="subtitle">Reporte de Desempeño Cuantitativo | Trading Clásico Asimétrico con Triple Barrera</div>
        <div style="font-size: 12px; color: #64748B; margin-top: 8px;">
            Estrategia: <strong>{strategy}</strong> | Activo: <strong>{pair}</strong> ({interval}) | Periodo Auditado: <strong>{period_display}</strong>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <div class="card-label">Profit Factor</div>
            <div class="card-val green">{pf:.2f}</div>
        </div>
        <div class="card">
            <div class="card-label">PnL Neto Total</div>
            <div class="card-val cyan">{net_pnl:+.2f} USD</div>
        </div>
        <div class="card">
            <div class="card-label">Esperanza / Trade</div>
            <div class="card-val green">{ev_r:+.3f} R</div>
        </div>
        <div class="card">
            <div class="card-label">Max Drawdown</div>
            <div class="card-val">{max_dd:.1f}%</div>
        </div>
    </div>

    <h3>Desglose de Operaciones Recientes ({min(len(trades), 100)} trades)</h3>
    <table class="table">
        <thead>
            <tr>
                <th>#</th>
                <th>Tipo</th>
                <th>Entrada</th>
                <th>Stop Loss</th>
                <th>Take Profit</th>
                <th>Salida</th>
                <th>R:R</th>
                <th>PnL ($)</th>
                <th>Causa</th>
            </tr>
        </thead>
        <tbody>"""

        for idx, t in enumerate(trades[:100], 1):
            pnl_val = float(t.get('pnl', 0.0))
            pnl_col = "#00F5A0" if pnl_val >= 0 else "#EF4444"
            direction_esc = html_lib.escape(str(t.get('direction', 'LONG')))
            reason_esc = html_lib.escape(str(t.get('exit_reason', t.get('result', 'WIN'))))
            html_report += f"""
            <tr>
                <td>{idx}</td>
                <td><strong>{direction_esc}</strong></td>
                <td>{float(t.get('entry_price', 0.0)):.4f}</td>
                <td>{float(t.get('sl_price', 0.0)):.4f}</td>
                <td>{float(t.get('tp_price', 0.0)):.4f}</td>
                <td>{float(t.get('exit_price', 0.0)):.4f}</td>
                <td>{float(t.get('r_multiple', 0.0)):+.2f}R</td>
                <td style="color: {pnl_col}; font-weight: 700;">{pnl_val:+.2f}</td>
                <td>{reason_esc}</td>
            </tr>"""

        html_report += """
        </tbody>
    </table>
</body>
</html>"""

        safe_strat = secure_filename(strategy_raw.replace(' ', '_')) or "Strategy"
        safe_pair = secure_filename(pair_raw.replace(' ', '_')) or "Asset"
        safe_interval = secure_filename(interval_raw) or "4h"
        filename = f"Nexus_Report_{safe_strat}_{safe_pair}_{safe_interval}_{date_range_str}.html"
        return Response(
            html_report,
            mimetype="text/html",
            headers={"Content-Disposition": f"inline;filename={filename}"}
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@export_bp.route('/api/export/pinescript', methods=['POST', 'GET'])
def export_pinescript():
    """Exporta la estrategia especificada a código TradingView PineScript v6 (Bot ejecutable o Indicador)."""
    try:
        if request.method == 'POST':
            req = request.json or {}
        else:
            req = request.args
        strategy = req.get('strategy') or req.get('strategy_key') or 'deesr'
        pair_arg = req.get('pair') or 'BTCUSDT'
        interval_arg = req.get('interval') or '4h'
        params = req.get('params', {})
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception:
                params = {}
        
        def _parse_float(val, default):
            try:
                return float(val) if val is not None else default
            except (ValueError, TypeError):
                return default

        def _parse_int(val, default):
            try:
                return int(float(val)) if val is not None else default
            except (ValueError, TypeError):
                return default

        # Opciones de gestión de riesgo y ejecución
        export_mode = req.get('export_mode') or req.get('mode') or params.get('export_mode', 'strategy')
        initial_capital = _parse_float(req.get('initial_capital', params.get('initial_capital')), 1000.0)
        pos_size_usd = _parse_float(req.get('pos_size_usd', req.get('position_size', params.get('pos_size_usd'))), 50.0)
        max_open_trades = _parse_int(req.get('max_open_trades', params.get('max_open_trades')), 1)
        bars_to_hold = _parse_int(req.get('bars_to_hold', req.get('expiry_bars', params.get('bars_to_hold'))), 1)
        commission_pct = _parse_float(req.get('commission_pct', params.get('commission_pct')), 0.05)

        code = StrategyExporter.export_to_pinescript(
            strategy_key=strategy,
            params=params,
            export_mode=export_mode,
            initial_capital=initial_capital,
            pos_size_usd=pos_size_usd,
            max_open_trades=max_open_trades,
            bars_to_hold=bars_to_hold,
            commission_pct=commission_pct
        )
        if request.args.get('download') == 'true':
            safe_name = secure_filename(f"Nexus_{strategy}_{pair_arg}_{interval_arg}_v6") or "Nexus_Strategy_v6"
            return Response(
                code,
                mimetype='text/plain',
                headers={'Content-Disposition': f'attachment;filename={safe_name}.pine'}
            )
        return jsonify({'strategy': strategy, 'pinescript': code, 'version': 6, 'mode': export_mode})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@export_bp.route('/api/export/python', methods=['POST', 'GET'])
def export_python():
    """Exporta la estrategia especificada a un script independiente en Python."""
    try:
        if request.method == 'POST':
            req = request.json or {}
        else:
            req = request.args
        strategy = req.get('strategy') or req.get('strategy_key') or 'deesr'
        params = req.get('params', {})
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception:
                params = {}
        code = StrategyExporter.export_to_python(strategy, params)
        if request.args.get('download') == 'true':
            safe_name = secure_filename(strategy) or "strategy"
            return Response(
                code,
                mimetype='text/x-python',
                headers={'Content-Disposition': f'attachment;filename={safe_name}.py'}
            )
        return jsonify({'strategy': strategy, 'python': code})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@export_bp.route('/api/export/json', methods=['POST', 'GET'])
def export_json():
    """Exporta la definición y parámetros de la estrategia a JSON schema."""
    try:
        if request.method == 'POST':
            req = request.json or {}
        else:
            req = request.args
        strategy = req.get('strategy') or req.get('strategy_key') or 'deesr'
        params = req.get('params', {})
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception:
                params = {}
        data = StrategyExporter.export_to_json(strategy, params)
        return jsonify({'strategy': strategy, 'schema': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
