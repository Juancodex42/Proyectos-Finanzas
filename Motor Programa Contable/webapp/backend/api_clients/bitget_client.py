import os
from datetime import datetime, timezone, timedelta
import ccxt.async_support as ccxt_async
from pydantic import ValidationError
from models.transaction_models import TransactionModel
from .common import (
    get_exchange_pairs,
    decompose_api_trade,
    get_exchange_rate_from_obj,
    _is_placeholder_key,
    _clean_api_error
)
from .date_chunker import generate_time_windows

from services.exchanges_service import get_latest_transaction_timestamp


async def fetch_bitget_v2(creds=None, since_ms=None):
    api_key = (creds.get('apiKey') or creds.get('api_key') or os.getenv("BITGET_API_KEY")) if isinstance(creds, dict) else os.getenv("BITGET_API_KEY")
    api_secret = (creds.get('secret') or creds.get('api_secret') or os.getenv("BITGET_API_SECRET")) if isinstance(creds, dict) else os.getenv("BITGET_API_SECRET")
    api_password = (creds.get('password') or creds.get('api_password') or creds.get('passphrase') or os.getenv("BITGET_API_PASSWORD")) if isinstance(creds, dict) else os.getenv("BITGET_API_PASSWORD")
    if not api_key or not api_secret:
        return {"success": False, "error": "Bitget auth missing", "data": []}
    exchange = ccxt_async.bitget({
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
        pairs = get_exchange_pairs('bitget', ['USDC/USDT', 'BTC/USDT', 'ETH/USDT', 'SOL/USDT'])
        for pair in pairs:
            try:
                crypto = pair.split('/')[0] if '/' in pair else pair
                since = since_ms or get_latest_transaction_timestamp("Bitget", crypto)
                if since:
                    since += 1
                limit = 100
                while True:
                    trades = await exchange.fetch_my_trades(symbol=pair, since=since, limit=limit)
                    if not trades:
                        break
                    for t in trades:
                        try:
                            models = decompose_api_trade(t, pair, "Bitget")
                            validated_trades.extend(models)
                        except ValidationError as ve:
                            anomalies.append({"exchange": "Bitget", "row": t, "error": str(ve)})
                            continue
                    since = trades[-1]['timestamp'] + 1
                    if len(trades) < limit:
                        break
            except ccxt_async.AuthenticationError as ae:
                return {"success": False, "error": f"Error de autenticación en Bitget: {ae}", "data": [], "anomalies": []}
            except Exception as e:
                anomalies.append({"exchange": "Bitget", "pair": pair, "error": str(e)})
                
        return {"success": True, "error": None, "data": validated_trades, "anomalies": anomalies}
    except Exception as e:
        return {"success": False, "error": str(e), "data": [], "anomalies": []}
    finally:
        await exchange.close()


async def fetch_bitget_p2p_v2(creds=None, since_ms=None):
    api_key = (creds.get('apiKey') or creds.get('api_key') or os.getenv("BITGET_API_KEY")) if isinstance(creds, dict) else os.getenv("BITGET_API_KEY")
    api_secret = (creds.get('secret') or creds.get('api_secret') or os.getenv("BITGET_API_SECRET")) if isinstance(creds, dict) else os.getenv("BITGET_API_SECRET")
    api_password = (creds.get('password') or creds.get('api_password') or creds.get('passphrase') or os.getenv("BITGET_API_PASSWORD")) if isinstance(creds, dict) else os.getenv("BITGET_API_PASSWORD")
    if not api_key or not api_secret:
        return {"success": False, "error": "Bitget auth missing", "data": []}
    exchange = ccxt_async.bitget({
        'apiKey': api_key, 'secret': api_secret, 'password': api_password,
        'enableRateLimit': True,
        'options': {'adjustForTimeDifference': True}
    })
    validated_trades = []
    anomalies = []
    seen_orders = set()
    try:
        fn = getattr(exchange, 'privateP2pGetV2P2pOrderList', None) or getattr(exchange, 'private_p2p_get_v2_p2p_orderlist', None)
        if not fn:
            return {"success": True, "error": None, "data": [], "anomalies": []}
            
        all_orders = []
        # Bitget P2P API strictly enforces <= 7 day windows
        start_dt = datetime.fromtimestamp(since_ms / 1000.0, tz=timezone.utc) if since_ms else datetime(2025, 1, 1, tzinfo=timezone.utc)
        windows = generate_time_windows(start_dt, chunk_days=7)
        for st, et in windows:
            try:
                end_id = None
                for _page in range(10):
                    req_params = {'startTime': str(st), 'endTime': str(et), 'limit': '100'}
                    if end_id:
                        req_params['endId'] = end_id
                    res = await fn(req_params)
                    data_obj = res.get('data', {}) if isinstance(res, dict) else {}
                    p2p_list = data_obj.get('orderList', []) if isinstance(data_obj, dict) else []
                    if not p2p_list:
                        break
                    new_in_page = 0
                    for o in p2p_list:
                        o_id = str(o.get('orderNo') or o.get('orderId') or '')
                        if o_id and o_id not in seen_orders:
                            seen_orders.add(o_id)
                            all_orders.append(o)
                            new_in_page += 1
                    last_id = str(p2p_list[-1].get('orderNo') or p2p_list[-1].get('orderId') or data_obj.get('endId') or '')
                    if len(p2p_list) < 100 or not last_id or last_id == end_id or new_in_page == 0:
                        break
                    end_id = last_id
            except Exception as pe:
                anomalies.append({"exchange": "Bitget P2P", "action": "fetch_p2p_window", "window": f"{st}-{et}", "error": str(pe)})
                continue

        for o in all_orders:
            # Check completed or fulfilled status
            status_clean = str(o.get('status', '')).lower()
            if status_clean and status_clean not in ['completed', 'finish', 'fulfilled', 'success']:
                continue
            try:
                buyer = str(o.get('buyerRealName', '')).strip().lower()
                seller = str(o.get('sellerRealName', '')).strip().lower()
                side = str(o.get('side', '')).strip().lower()
                
                p2p_nick = os.environ.get('BITGET_P2P_NICKNAME', '').strip().lower()
                if p2p_nick:
                    is_buy = (buyer == p2p_nick) or (side in ('buy', 'compra', '1') and seller != p2p_nick)
                else:
                    is_buy = side in ('buy', 'compra', '1')
                
                monto = float(o.get('count', 0))
                precio = float(o.get('price', 0))
                monto_ars = float(o.get('amount', monto * precio))
                crypto = o.get('coin', 'USDT').upper()
                tx_date = datetime.fromtimestamp(int(o['cTime']) / 1000.0, tz=timezone.utc).replace(tzinfo=None)
                pay_method = o.get('paymentInfo', {}).get('paymethodName', '') if isinstance(o.get('paymentInfo'), dict) else ''
                
                fiat_coin = str(o.get('fiatCoin') or o.get('currency') or o.get('fiat') or 'ARS').upper().strip()
                is_ars = any(k in fiat_coin for k in ('ARS', 'PESO', 'PESOS', '$')) or not fiat_coin
                if not is_ars:
                    from parsers.base_parser import get_fiat_usd_rate
                    rate = get_exchange_rate_from_obj(tx_date)
                    fiat_usd = get_fiat_usd_rate(fiat_coin)
                    monto_ars = monto_ars * fiat_usd * rate
                    precio = precio * fiat_usd * rate

                model = TransactionModel(
                    fecha=tx_date,
                    exchange="Bitget P2P",
                    tipo_operacion="Compra" if is_buy else "Venta",
                    moneda=crypto,
                    monto_compra_cripto=monto if is_buy else 0.0,
                    monto_venta_cripto=monto if not is_buy else 0.0,
                    cotizacion_compra=precio if is_buy else 0.0,
                    cotizacion_venta=precio if not is_buy else 0.0,
                    monto_ars=monto_ars,
                    comentarios=f"Bitget P2P [{fiat_coin}] ID: {o.get('orderNo', '')} ({pay_method})" if not is_ars else f"Bitget P2P ID: {o.get('orderNo', '')} ({pay_method})"
                )
                validated_trades.append(model)
            except ValidationError as ve:
                anomalies.append({"exchange": "Bitget P2P", "row": o, "error": str(ve)})
                continue
        return {"success": True, "error": None, "data": validated_trades, "anomalies": anomalies}
    except Exception as e:
        return {"success": False, "error": f"Bitget P2P Sync Error: {str(e)}", "data": [], "anomalies": []}
    finally:
        await exchange.close()

async def fetch_bitget_transfers_v2(creds=None, since_ms=None):
    api_key = (creds.get('apiKey') or creds.get('api_key') or os.getenv("BITGET_API_KEY")) if isinstance(creds, dict) else os.getenv("BITGET_API_KEY")
    api_secret = (creds.get('secret') or creds.get('api_secret') or os.getenv("BITGET_API_SECRET")) if isinstance(creds, dict) else os.getenv("BITGET_API_SECRET")
    api_password = (creds.get('password') or creds.get('api_password') or creds.get('passphrase') or os.getenv("BITGET_API_PASSWORD")) if isinstance(creds, dict) else os.getenv("BITGET_API_PASSWORD")
    if not api_key or not api_secret:
        return {"success": False, "error": "Bitget auth missing", "data": [], "anomalies": []}
    exchange = ccxt_async.bitget({
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
            # 1. Depósitos Bitget V2
            try:
                params = {'endTime': end_ts}
                deposits = await exchange.fetch_deposits(since=start_ts, params=params)
                for dep in (deposits or []):
                    status = str(dep.get('status', '')).lower()
                    if status not in ('ok', 'success', 'completed', '1', 1):
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
                        exchange="Bitget",
                        tipo_operacion="Ingreso Cripto",
                        moneda=coin,
                        monto_compra_cripto=amount,
                        monto_venta_cripto=0.0,
                        cotizacion_compra=0.0,
                        cotizacion_venta=0.0,
                        monto_ars=0.0,
                        comentarios=f"Depósito Bitget TXID: {tx_id}"
                    )
                    validated_transfers.append(model)
            except Exception as dep_err:
                anomalies.append({"exchange": "Bitget", "action": "fetch_deposits", "window": f"{start_ts}-{end_ts}", "error": str(dep_err)})

            # 2. Retiros Bitget V2
            try:
                params = {'endTime': end_ts}
                withdrawals = await exchange.fetch_withdrawals(since=start_ts, params=params)
                for w in (withdrawals or []):
                    status = str(w.get('status', '')).lower()
                    if status not in ('ok', 'success', 'completed', '1', 1):
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
                        exchange="Bitget",
                        tipo_operacion="Retiro Cripto",
                        moneda=coin,
                        monto_compra_cripto=0.0,
                        monto_venta_cripto=amount,
                        cotizacion_compra=0.0,
                        cotizacion_venta=0.0,
                        monto_ars=0.0,
                        comentarios=f"Retiro Bitget TXID: {tx_id}"
                    )
                    validated_transfers.append(model)
            except Exception as w_err:
                anomalies.append({"exchange": "Bitget", "action": "fetch_withdrawals", "window": f"{start_ts}-{end_ts}", "error": str(w_err)})

        return {"success": True, "error": None, "data": validated_transfers, "anomalies": anomalies}
    except Exception as e:
        return {"success": False, "error": f"Bitget Transfers Sync Error: {str(e)}", "data": [], "anomalies": anomalies}
    finally:
        await exchange.close()



async def check_api_auth_bitget():
    key = os.getenv("BITGET_API_KEY")
    secret = os.getenv("BITGET_API_SECRET")
    if _is_placeholder_key(key, secret):
        return {"status": "unconfigured", "msg": "Llaves no ingresadas"}
    try:
        ex = ccxt_async.bitget({
            'apiKey': key, 'secret': secret, 'password': os.getenv("BITGET_API_PASSWORD"),
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
