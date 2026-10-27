import os
import time
import hmac
import hashlib
import aiohttp
from datetime import datetime, timezone
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
from .date_chunker import generate_time_windows

from services.exchanges_service import get_latest_transaction_timestamp


async def fetch_ripio_trade_v2(creds=None, since_ms=None):
    api_key = (creds.get('apiKey') or creds.get('api_key') or os.getenv("RIPIO_API_KEY")) if isinstance(creds, dict) else os.getenv("RIPIO_API_KEY")
    api_secret = (creds.get('secret') or creds.get('api_secret') or os.getenv("RIPIO_API_SECRET")) if isinstance(creds, dict) else os.getenv("RIPIO_API_SECRET")
    
    if not api_key or not api_secret:
        return {"success": False, "error": "Ripio Trade API Keys not configured.", "data": []}
        
    base_url = "https://api.ripiotrade.co/v4"
    endpoint = "/user/trades"
    
    validated_trades = []
    anomalies = []
    
    try:
        timestamp = str(int(time.time()))
        api_secret_bytes = api_secret.encode('utf-8')
        message = timestamp + endpoint
        message_bytes = message.encode('utf-8')
        signature = hmac.new(api_secret_bytes, message_bytes, hashlib.sha256).hexdigest()
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'X-Cor-Auth-Timestamp': timestamp,
            'X-Cor-Auth-Signature': signature
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(base_url + endpoint, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    trades = data.get('data', [])
                    for t in trades:
                        try:
                            pair = str(t.get('pair', '')).upper()
                            is_buy = str(t.get('side', '')).lower() == 'buy'
                            parts = pair.replace('_', '/').split('/')
                            base_coin = parts[0] if len(parts) >= 1 else ''
                            quote_coin = parts[1] if len(parts) >= 2 else 'ARS'

                            monto = float(t.get('amount', 0))
                            precio = float(t.get('price', 0))
                            cost = float(t.get('total_value', t.get('cost', monto * precio)))
                            tx_date = datetime.fromisoformat(t['created_at'].replace('Z', '+00:00')).replace(tzinfo=None)

                            if quote_coin == 'ARS':
                                monto_ars = cost
                                cot_ars = precio
                            else:
                                monto_ars = convert_cost_to_ars(cost, pair, tx_date, amount=monto)
                                cot_ars = monto_ars / monto if monto > 0 else 0.0

                            monto_c = monto if is_buy else 0.0
                            monto_v = monto if not is_buy else 0.0
                            tx_id = t.get('id', '')
                            is_swap = quote_coin != 'ARS'
                            base_id = f"{tx_id}_c" if (is_swap and is_buy) else (f"{tx_id}_v" if is_swap else f"{tx_id}")
                            quote_id = f"{tx_id}_v" if is_buy else f"{tx_id}_c"

                            model = TransactionModel(
                                fecha=tx_date,
                                exchange="Ripio Trade",
                                tipo_operacion="Compra" if is_buy else "Venta",
                                moneda=base_coin,
                                monto_compra_cripto=monto_c,
                                monto_venta_cripto=monto_v,
                                cotizacion_compra=cot_ars if is_buy else 0.0,
                                cotizacion_venta=cot_ars if not is_buy else 0.0,
                                monto_ars=monto_ars,
                                comentarios=f"Ripio ID: {base_id}",
                                is_utc=True
                            )
                            validated_trades.append(model)

                            if quote_coin != 'ARS' and cost > 0:
                                cot_q = monto_ars / cost
                                model_quote = TransactionModel(
                                    fecha=tx_date,
                                    exchange="Ripio Trade",
                                    tipo_operacion="Venta" if is_buy else "Compra",
                                    moneda=quote_coin,
                                    monto_compra_cripto=cost if not is_buy else 0.0,
                                    monto_venta_cripto=cost if is_buy else 0.0,
                                    cotizacion_compra=cot_q if not is_buy else 0.0,
                                    cotizacion_venta=cot_q if is_buy else 0.0,
                                    monto_ars=monto_ars,
                                    comentarios=f"[INTERCAMBIO: {quote_coin}->{base_coin}] | Ripio ID: {quote_id}" if is_buy else f"[INTERCAMBIO: {base_coin}->{quote_coin}] | Ripio ID: {quote_id}",
                                    is_utc=True
                                )
                                validated_trades.append(model_quote)
                        except ValidationError as ve:
                            anomalies.append({"exchange": "Ripio Trade", "row": t, "error": str(ve)})
                            continue
                else:
                    return {"success": False, "error": f"Ripio Trade HTTP {response.status}", "data": [], "anomalies": []}
                    
            return {"success": True, "error": None, "data": validated_trades, "anomalies": anomalies}
    except Exception as e:
        return {"success": False, "error": f"Ripio Trade Async Error: {str(e)}", "data": [], "anomalies": []}


async def check_api_auth_ripio():
    res = await fetch_ripio_trade_v2()
    if res.get("success"):
        return {"status": "online", "msg": "Autenticado OK"}
    err = str(res.get("error", ""))
    if "not configured" in err.lower() or "missing" in err.lower():
        return {"status": "unconfigured", "msg": "Llaves no ingresadas"}
    if any(term in err.lower() for term in ['401', '403', 'signature', 'auth', 'expired']):
        return {"status": "expired", "msg": _clean_api_error(err)}
    return {"status": "offline", "msg": _clean_api_error(err)}


async def fetch_okx_v2(creds=None, since_ms=None):
    api_key = (creds.get('apiKey') or creds.get('api_key') or os.getenv("OKX_API_KEY")) if isinstance(creds, dict) else os.getenv("OKX_API_KEY")
    api_secret = (creds.get('secret') or creds.get('api_secret') or os.getenv("OKX_API_SECRET")) if isinstance(creds, dict) else os.getenv("OKX_API_SECRET")
    api_password = (creds.get('password') or creds.get('api_password') or creds.get('passphrase') or os.getenv("OKX_API_PASSWORD")) if isinstance(creds, dict) else os.getenv("OKX_API_PASSWORD")
    if not api_key or not api_secret:
        return {"success": False, "error": "OKX auth missing", "data": []}
    exchange = ccxt_async.okx({
        'apiKey': api_key,
        'secret': api_secret,
        'password': api_password,
        'enableRateLimit': True,
        'options': {
            'adjustForTimeDifference': True,
        }
    })
    
    validated_trades = []
    anomalies = []
    try:
        if hasattr(exchange, 'load_markets'):
            _lm = exchange.load_markets()
            if hasattr(_lm, '__await__'):
                await _lm
        pairs = get_exchange_pairs('okx', ['USDC/USDT', 'BTC/USDT', 'ETH/USDT'])
        for pair in pairs:
            try:
                crypto = pair.split('/')[0] if '/' in pair else pair
                since = since_ms or get_latest_transaction_timestamp("OKX", crypto)
                if since:
                    since += 1
                limit = 100
                while True:
                    trades = await exchange.fetch_my_trades(symbol=pair, since=since, limit=limit)
                    if not trades:
                        break
                    for t in trades:
                        try:
                            models = decompose_api_trade(t, pair, "OKX")
                            validated_trades.extend(models)
                        except ValidationError as ve:
                            anomalies.append({"exchange": "OKX", "row": t, "error": str(ve)})
                            continue
                    since = trades[-1]['timestamp'] + 1
                    if len(trades) < limit:
                        break
            except ccxt_async.AuthenticationError as ae:
                return {"success": False, "error": f"Error de autenticación en OKX: {ae}", "data": [], "anomalies": []}
            except Exception as e:
                anomalies.append({"exchange": "OKX", "pair": pair, "error": str(e)})
                print(f"Skipping OKX {pair}: {e}")
                
        return {"success": True, "error": None, "data": validated_trades, "anomalies": anomalies}
    except Exception as e:
        return {"success": False, "error": str(e), "data": [], "anomalies": []}
    finally:
        await exchange.close()


async def fetch_okx_transfers_v2(creds=None, since_ms=None):
    api_key = (creds.get('apiKey') or creds.get('api_key') or os.getenv("OKX_API_KEY")) if isinstance(creds, dict) else os.getenv("OKX_API_KEY")
    api_secret = (creds.get('secret') or creds.get('api_secret') or os.getenv("OKX_API_SECRET")) if isinstance(creds, dict) else os.getenv("OKX_API_SECRET")
    api_password = (creds.get('password') or creds.get('api_password') or creds.get('passphrase') or os.getenv("OKX_API_PASSWORD")) if isinstance(creds, dict) else os.getenv("OKX_API_PASSWORD")
    if not api_key or not api_secret:
        return {"success": False, "error": "OKX auth missing", "data": [], "anomalies": []}
    exchange = ccxt_async.okx({
        'apiKey': api_key, 'secret': api_secret, 'password': api_password,
        'enableRateLimit': True,
        'options': {'adjustForTimeDifference': True}
    })
    validated_transfers = []
    anomalies = []
    seen_ids = set()
    start_dt = datetime.fromtimestamp(since_ms / 1000.0, tz=timezone.utc) if since_ms else datetime(2024, 1, 1, tzinfo=timezone.utc)
    windows = generate_time_windows(start_dt, chunk_days=30)
    try:
        for start_ts, end_ts in windows:
            # 1. Depósitos OKX
            try:
                params = {'endTime': end_ts, 'until': end_ts}
                deposits = await exchange.fetch_deposits(since=start_ts, params=params)
                for dep in (deposits or []):
                    status = str(dep.get('status', '')).lower()
                    if status not in ('ok', 'success', 'completed', '2', 2):
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
                        exchange="OKX",
                        tipo_operacion="Ingreso Cripto",
                        moneda=coin,
                        monto_compra_cripto=amount,
                        monto_venta_cripto=0.0,
                        cotizacion_compra=0.0,
                        cotizacion_venta=0.0,
                        monto_ars=0.0,
                        comentarios=f"Depósito OKX TXID: {tx_id}"
                    )
                    validated_transfers.append(model)
            except Exception as dep_err:
                anomalies.append({"exchange": "OKX", "action": "fetch_deposits", "window": f"{start_ts}-{end_ts}", "error": str(dep_err)})

            # 2. Retiros OKX
            try:
                params = {'endTime': end_ts, 'until': end_ts}
                withdrawals = await exchange.fetch_withdrawals(since=start_ts, params=params)
                for w in (withdrawals or []):
                    status = str(w.get('status', '')).lower()
                    if status not in ('ok', 'success', 'completed', '2', 2):
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
                        exchange="OKX",
                        tipo_operacion="Retiro Cripto",
                        moneda=coin,
                        monto_compra_cripto=0.0,
                        monto_venta_cripto=amount,
                        cotizacion_compra=0.0,
                        cotizacion_venta=0.0,
                        monto_ars=0.0,
                        comentarios=f"Retiro OKX TXID: {tx_id}"
                    )
                    validated_transfers.append(model)
            except Exception as w_err:
                anomalies.append({"exchange": "OKX", "action": "fetch_withdrawals", "window": f"{start_ts}-{end_ts}", "error": str(w_err)})

        return {"success": True, "error": None, "data": validated_transfers, "anomalies": anomalies}
    except Exception as e:
        return {"success": False, "error": f"OKX Transfers Sync Error: {str(e)}", "data": [], "anomalies": anomalies}
    finally:
        await exchange.close()



async def check_api_auth_okx():
    key = os.getenv("OKX_API_KEY")
    secret = os.getenv("OKX_API_SECRET")
    if _is_placeholder_key(key, secret):
        return {"status": "unconfigured", "msg": "Llaves no ingresadas"}
    try:
        ex = ccxt_async.okx({
            'apiKey': key, 'secret': secret, 'password': os.getenv("OKX_API_PASSWORD"),
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


async def check_api_auth_ccxt_generic(exchange_id):
    if exchange_id in ccxt_async.exchanges:
        key = os.getenv(f"{exchange_id.upper()}_API_KEY")
        secret = os.getenv(f"{exchange_id.upper()}_API_SECRET")
        if not key or not secret or _is_placeholder_key(key, secret):
            return {"status": "unconfigured", "msg": "Llaves no ingresadas"}
        try:
            ex_class = getattr(ccxt_async, exchange_id)
            ex = ex_class({
                'apiKey': key,
                'secret': secret,
                'enableRateLimit': False,
                'timeout': 15000,
                'options': {
                    'fetchMarkets': False,
                    'adjustForTimeDifference': True,
                }
            })
            password = os.getenv(f"{exchange_id.upper()}_API_PASSWORD")
            if password:
                ex.password = password
                
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
    return {"status": "unconfigured", "msg": "Desconocido"}
