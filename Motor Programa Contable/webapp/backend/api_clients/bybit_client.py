import os
import logging
import ccxt.async_support as ccxt_async
from pydantic import ValidationError
from datetime import datetime, timezone, timedelta
from models.transaction_models import TransactionModel
from .common import (
    get_exchange_pairs,
    decompose_api_trade,
    _is_placeholder_key,
    _clean_api_error
)
from .date_chunker import generate_time_windows

from services.exchanges_service import get_latest_transaction_timestamp


async def fetch_bybit_v2(creds=None, since_ms=None):
    api_key = (creds.get('apiKey') or creds.get('api_key') or os.getenv("BYBIT_API_KEY")) if isinstance(creds, dict) else os.getenv("BYBIT_API_KEY")
    api_secret = (creds.get('secret') or creds.get('api_secret') or os.getenv("BYBIT_API_SECRET")) if isinstance(creds, dict) else os.getenv("BYBIT_API_SECRET")
    if not api_key or not api_secret:
        return {"success": False, "error": "Bybit auth missing", "data": []}
    exchange = ccxt_async.bybit({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
        'options': {
            'adjustForTimeDifference': True,
            'recvWindow': 30000,
        }
    })
    validated_trades = []
    anomalies = []
    last_error = None
    try:
        try:
            await exchange.load_time_difference()
        except Exception as e:
            logging.getLogger(__name__).warning(f"Error sincronizando reloj con Bybit (load_time_difference): {e}")
        if hasattr(exchange, 'load_markets'):
            _lm = exchange.load_markets()
            if hasattr(_lm, '__await__'):
                await _lm
        pairs = get_exchange_pairs('bybit', ['USDC/USDT', 'BTC/USDT', 'ETH/USDT'])
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        seven_days_ms = 7 * 24 * 60 * 60 * 1000
        for pair in pairs:
            try:
                crypto = pair.split('/')[0] if '/' in pair else pair
                since = since_ms or get_latest_transaction_timestamp("Bybit", crypto)
                if not since:
                    since = int((datetime.now(timezone.utc) - timedelta(days=180)).timestamp() * 1000)
                else:
                    since += 1
                cur_start = since
                limit = 100
                while cur_start < now_ms:
                    cur_end = min(cur_start + seven_days_ms, now_ms)
                    params = {'endTime': cur_end}
                    trades = await exchange.fetch_my_trades(symbol=pair, since=cur_start, limit=limit, params=params)
                    if trades:
                        for t in trades:
                            try:
                                models = decompose_api_trade(t, pair, "Bybit")
                                validated_trades.extend(models)
                            except ValidationError as ve:
                                anomalies.append({"exchange": "Bybit", "row": t, "error": str(ve)})
                                continue
                        cur_start = trades[-1]['timestamp'] + 1
                        if len(trades) < limit:
                            cur_start = cur_end
                    else:
                        cur_start = cur_end
            except ccxt_async.AuthenticationError as ae:
                return {"success": False, "error": f"Error de autenticación en Bybit: {ae}", "data": [], "anomalies": []}
            except Exception as e:
                last_error = e
                anomalies.append({"exchange": "Bybit", "pair": pair, "error": str(e)})
                logging.getLogger(__name__).warning(f"Skipping Bybit {pair}: {e}")
                
        if not validated_trades and last_error:
            return {"success": False, "error": f"Fallo al consultar pares de Bybit. Último error: {last_error}", "data": [], "anomalies": []}

        return {"success": True, "error": None, "data": validated_trades, "anomalies": anomalies}
    except Exception as e:
        return {"success": False, "error": str(e), "data": [], "anomalies": []}
    finally:
        await exchange.close()


async def fetch_bybit_transfers_v2(creds=None, since_ms=None):
    api_key = (creds.get('apiKey') or creds.get('api_key') or os.getenv("BYBIT_API_KEY")) if isinstance(creds, dict) else os.getenv("BYBIT_API_KEY")
    api_secret = (creds.get('secret') or creds.get('api_secret') or os.getenv("BYBIT_API_SECRET")) if isinstance(creds, dict) else os.getenv("BYBIT_API_SECRET")
    if not api_key or not api_secret:
        return {"success": False, "error": "Bybit auth missing", "data": [], "anomalies": []}
    exchange = ccxt_async.bybit({
        'apiKey': api_key, 'secret': api_secret,
        'enableRateLimit': True,
        'options': {'adjustForTimeDifference': True, 'recvWindow': 30000}
    })
    validated_transfers = []
    anomalies = []
    seen_ids = set()
    start_dt = datetime.fromtimestamp(since_ms / 1000.0, tz=timezone.utc) if since_ms else datetime(2024, 1, 1, tzinfo=timezone.utc)
    windows = generate_time_windows(start_dt, chunk_days=30)
    try:
        try:
            await exchange.load_time_difference()
        except Exception:
            pass
        for start_ts, end_ts in windows:
            # 1. Depósitos (Bybit V5 Asset API)
            try:
                params = {'endTime': end_ts}
                deposits = await exchange.fetch_deposits(since=start_ts, params=params)
                for dep in (deposits or []):
                    status = str(dep.get('status', '')).lower()
                    if status not in ('ok', 'success', 'completed', '1', 1, '3'):
                        continue
                    amount = float(dep.get('amount') or 0.0)
                    if amount <= 0:
                        continue
                    tx_id = str(dep.get('txid') or dep.get('id') or '')
                    dedup_key = f"dep_{tx_id}_{dep.get('timestamp')}_{amount}"
                    if dedup_key in seen_ids:
                        continue
                    seen_ids.add(dedup_key)

                    coin = str(dep.get('currency') or 'USDT').upper()
                    tx_ts = dep.get('timestamp')
                    tx_date = datetime.fromtimestamp(tx_ts / 1000.0, tz=timezone.utc).replace(tzinfo=None) if tx_ts else datetime.now()
                    model = TransactionModel(
                        fecha=tx_date,
                        exchange="Bybit",
                        tipo_operacion="Ingreso Cripto",
                        moneda=coin,
                        monto_compra_cripto=amount,
                        monto_venta_cripto=0.0,
                        cotizacion_compra=0.0,
                        cotizacion_venta=0.0,
                        monto_ars=0.0,
                        comentarios=f"Depósito Bybit TXID: {tx_id}"
                    )
                    validated_transfers.append(model)
            except Exception as dep_err:
                anomalies.append({"exchange": "Bybit", "action": "fetch_deposits", "window": f"{start_ts}-{end_ts}", "error": str(dep_err)})

            # 2. Retiros (Bybit V5 Asset API)
            try:
                params = {'endTime': end_ts}
                withdrawals = await exchange.fetch_withdrawals(since=start_ts, params=params)
                for w in (withdrawals or []):
                    status = str(w.get('status', '')).lower()
                    if status not in ('ok', 'success', 'completed', '1', 1, 'success'):
                        continue
                    amount = float(w.get('amount') or 0.0)
                    if amount <= 0:
                        continue
                    tx_id = str(w.get('txid') or w.get('id') or '')
                    dedup_key = f"w_{tx_id}_{w.get('timestamp')}_{amount}"
                    if dedup_key in seen_ids:
                        continue
                    seen_ids.add(dedup_key)

                    coin = str(w.get('currency') or 'USDT').upper()
                    tx_ts = w.get('timestamp')
                    tx_date = datetime.fromtimestamp(tx_ts / 1000.0, tz=timezone.utc).replace(tzinfo=None) if tx_ts else datetime.now()
                    model = TransactionModel(
                        fecha=tx_date,
                        exchange="Bybit",
                        tipo_operacion="Retiro Cripto",
                        moneda=coin,
                        monto_compra_cripto=0.0,
                        monto_venta_cripto=amount,
                        cotizacion_compra=0.0,
                        cotizacion_venta=0.0,
                        monto_ars=0.0,
                        comentarios=f"Retiro Bybit TXID: {tx_id}"
                    )
                    validated_transfers.append(model)
            except Exception as w_err:
                anomalies.append({"exchange": "Bybit", "action": "fetch_withdrawals", "window": f"{start_ts}-{end_ts}", "error": str(w_err)})

        return {"success": True, "error": None, "data": validated_transfers, "anomalies": anomalies}
    except Exception as e:
        return {"success": False, "error": f"Bybit Transfers Sync Error: {str(e)}", "data": [], "anomalies": anomalies}
    finally:
        await exchange.close()



async def check_api_auth_bybit():
    key = os.getenv("BYBIT_API_KEY")
    secret = os.getenv("BYBIT_API_SECRET")
    if _is_placeholder_key(key, secret):
        return {"status": "unconfigured", "msg": "Llaves no ingresadas"}
    try:
        ex = ccxt_async.bybit({
            'apiKey': key, 'secret': secret,
            'enableRateLimit': False, 'timeout': 15000,
            'options': {
                'fetchMarkets': False,
                'adjustForTimeDifference': True,
                'recvWindow': 30000,
            }
        })
        try:
            await ex.load_time_difference()
        except Exception as e:
            logging.getLogger(__name__).warning(f"Error sincronizando reloj con Bybit en auth check: {e}")
        await ex.fetch_balance()
        await ex.close()
        return {"status": "online", "msg": "Autenticado OK"}
    except Exception as e:
        try:
            await ex.close()
        except Exception:
            pass
        err_str = str(e).lower()
        if '10002' in err_str or 'request expired' in err_str:
            return {"status": "offline", "msg": "Error 10002 (Desfasaje de hora)"}
        if any(term in err_str for term in ['auth', 'key', 'permission', '401', '403', 'signature', 'invalid']) or ('expired' in err_str and 'request' not in err_str):
            return {"status": "expired", "msg": _clean_api_error(str(e))}
        return {"status": "offline", "msg": _clean_api_error(str(e))}
