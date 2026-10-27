import os
from datetime import datetime, timezone, timedelta
import ccxt.async_support as ccxt_async
from pydantic import ValidationError
from models.transaction_models import TransactionModel
from .common import (
    get_exchange_pairs,
    decompose_api_trade,
    convert_cost_to_ars,
    _is_placeholder_key,
    _clean_api_error
)


def _parse_bitso_datetime(created_at) -> datetime:
    """Converts Bitso ISO timestamp (with Z or offset like -03:00) to naive local ART (UTC-3)."""
    if not created_at:
        return datetime.now()
    try:
        dt_parsed = datetime.fromisoformat(str(created_at).strip().replace('Z', '+00:00'))
        if dt_parsed.tzinfo is not None:
            dt_parsed = dt_parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return (dt_parsed - timedelta(hours=3)).replace(tzinfo=None)
    except Exception:
        return datetime.now()


async def fetch_bitso_v2(creds=None, since_ms=None):
    api_key = (creds.get('apiKey') or creds.get('api_key') or os.getenv("BITSO_API_KEY")) if isinstance(creds, dict) else os.getenv("BITSO_API_KEY")
    api_secret = (creds.get('secret') or creds.get('api_secret') or os.getenv("BITSO_API_SECRET")) if isinstance(creds, dict) else os.getenv("BITSO_API_SECRET")
    
    if not api_key or not api_secret:
        return {"success": False, "error": "Bitso API Keys not configured.", "data": []}
        
    exchange = ccxt_async.bitso({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
        'options': {
            'adjustForTimeDifference': True,
        }
    })
    
    validated_trades = []
    anomalies = []
    try:
        pairs = get_exchange_pairs('bitso', ['btc_ars', 'eth_ars', 'usd_ars', 'usdt_ars'])
        for pair in pairs:
            try:
                symbol = pair.lower().replace('/', '_')
                display_symbol = symbol.upper().replace('_', '/')
                limit = 100
                marker = None
                while True:
                    params = {}
                    if marker:
                        params['marker'] = marker
                    trades = await exchange.fetch_my_trades(symbol=symbol, since=since_ms, limit=limit, params=params)
                    if not trades:
                        break
                    for t in trades:
                        try:
                            models = decompose_api_trade(t, display_symbol, "Bitso Alpha")
                            validated_trades.extend(models)
                        except ValidationError as ve:
                            anomalies.append({"exchange": "Bitso Alpha", "row": t, "error": str(ve)})
                            continue
                    new_marker = trades[-1].get('id')
                    if len(trades) < limit or not new_marker or new_marker == marker:
                        break
                    marker = new_marker
            except ccxt_async.AuthenticationError as ae:
                return {"success": False, "error": f"Error de autenticación en Bitso: {ae}", "data": [], "anomalies": []}
            except Exception as e:
                anomalies.append({"exchange": "Bitso Alpha", "pair": pair, "error": str(e)})
                print(f"Skipping Bitso {pair}: {e}")
                 
        # 1. Depósitos (Fundings) con paginación marker
        try:
            marker = None
            limit = 100
            seen_fids = set()
            while True:
                params = {'limit': limit}
                if marker:
                    params['marker'] = marker
                res = await exchange.privateGetFundings(params)
                fundings = res.get('payload', []) if isinstance(res, dict) else []
                if not fundings:
                    break
                for dep in fundings:
                    status = str(dep.get('status', '')).lower()
                    if status not in ('ok', 'success', 'completed', 'complete'):
                        continue
                    amount = float(dep.get('amount') or 0.0)
                    if amount <= 0:
                        continue
                    fid = str(dep.get('fid') or dep.get('id') or '')
                    if fid in seen_fids:
                        continue
                    seen_fids.add(fid)

                    coin = str(dep.get('currency') or dep.get('asset') or '').upper()
                    if coin in ('ARS', 'USD', 'EUR', ''):
                        continue  # Solo transferencias cripto para inventario

                    tx_dt_str = dep.get('created_at')
                    tx_date = _parse_bitso_datetime(tx_dt_str)

                    costo_ars = convert_cost_to_ars(amount, coin, tx_date, amount=amount)
                    cot_ars = costo_ars / amount if amount > 0 else 0.0
                    details = dep.get('details') or {}
                    tx_hash = str(details.get('tx_hash') or fid or '')
                    model = TransactionModel(
                        fecha=tx_date,
                        exchange="Bitso Alpha",
                        tipo_operacion="Ingreso Cripto",
                        moneda=coin,
                        monto_compra_cripto=amount,
                        monto_venta_cripto=0.0,
                        cotizacion_compra=cot_ars,
                        cotizacion_venta=0.0,
                        monto_ars=costo_ars,
                        comentarios=f"Depósito Bitso Funding FID: {fid} | Hash: {tx_hash}",
                        is_utc=False
                    )
                    validated_trades.append(model)

                new_marker = fundings[-1].get('fid')
                if len(fundings) < limit or not new_marker or new_marker == marker:
                    break
                marker = new_marker
        except Exception as dep_err:
            anomalies.append({"exchange": "Bitso Alpha", "action": "privateGetFundings", "error": str(dep_err)})

        # 2. Retiros (Withdrawals) con paginación marker
        try:
            marker = None
            limit = 100
            seen_wids = set()
            while True:
                params = {'limit': limit}
                if marker:
                    params['marker'] = marker
                res = await exchange.privateGetWithdrawals(params)
                withdrawals = res.get('payload', []) if isinstance(res, dict) else []
                if not withdrawals:
                    break
                for w in withdrawals:
                    status = str(w.get('status', '')).lower()
                    if status not in ('ok', 'success', 'completed', 'complete'):
                        continue
                    amount = float(w.get('amount') or 0.0)
                    if amount <= 0:
                        continue
                    wid = str(w.get('wid') or w.get('id') or '')
                    if wid in seen_wids:
                        continue
                    seen_wids.add(wid)

                    coin = str(w.get('currency') or w.get('asset') or '').upper()
                    if coin in ('ARS', 'USD', 'EUR', ''):
                        continue

                    tx_dt_str = w.get('created_at')
                    tx_date = _parse_bitso_datetime(tx_dt_str)

                    costo_ars = convert_cost_to_ars(amount, coin, tx_date, amount=amount)
                    cot_ars = costo_ars / amount if amount > 0 else 0.0
                    details = w.get('details') or {}
                    tx_hash = str(details.get('tx_hash') or details.get('coelsa_id') or wid or '')
                    model = TransactionModel(
                        fecha=tx_date,
                        exchange="Bitso Alpha",
                        tipo_operacion="Retiro Cripto",
                        moneda=coin,
                        monto_compra_cripto=0.0,
                        monto_venta_cripto=amount,
                        cotizacion_compra=0.0,
                        cotizacion_venta=cot_ars,
                        monto_ars=costo_ars,
                        comentarios=f"Retiro Bitso WID: {wid} | Ref: {tx_hash}",
                        is_utc=False
                    )
                    validated_trades.append(model)

                new_marker = withdrawals[-1].get('wid')
                if len(withdrawals) < limit or not new_marker or new_marker == marker:
                    break
                marker = new_marker
        except Exception as w_err:
            anomalies.append({"exchange": "Bitso Alpha", "action": "privateGetWithdrawals", "error": str(w_err)})

        return {"success": True, "error": None, "data": validated_trades, "anomalies": anomalies}
    except Exception as e:
        return {"success": False, "error": f"Bitso V2 Sync Error: {str(e)}", "data": [], "anomalies": anomalies}
    finally:
        await exchange.close()



async def check_api_auth_bitso():
    key = os.getenv("BITSO_API_KEY")
    secret = os.getenv("BITSO_API_SECRET")
    if _is_placeholder_key(key, secret):
        return {"status": "unconfigured", "msg": "Llaves no ingresadas"}
    try:
        ex = ccxt_async.bitso({
            'apiKey': key, 'secret': secret,
            'enableRateLimit': False, 'timeout': 15000,
            'options': {
                'fetchMarkets': False,
                'adjustForTimeDifference': True,
            }
        })
        await ex.fetch_balance()
        await ex.close()
        return {"status": "online", "msg": "Autenticado OK"}
    except Exception as e:
        try:
            await ex.close()
        except Exception:
            pass
        err_str = str(e).lower()
        if any(term in err_str for term in ['auth', 'key', 'permission', '401', '403', 'signature', 'invalid', 'expired']):
            return {"status": "expired", "msg": _clean_api_error(str(e))}
        return {"status": "offline", "msg": _clean_api_error(str(e))}
