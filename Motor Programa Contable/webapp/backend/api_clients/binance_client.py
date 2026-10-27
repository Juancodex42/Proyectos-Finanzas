import os
import time
import asyncio
import logging
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

from db.connection import get_connection
from services.exchanges_service import get_latest_transaction_timestamp


async def fetch_binance_v2(creds=None, since_ms=None):
    api_key = (creds.get('apiKey') or creds.get('api_key') or os.getenv("BINANCE_API_KEY")) if isinstance(creds, dict) else os.getenv("BINANCE_API_KEY")
    api_secret = (creds.get('secret') or creds.get('api_secret') or os.getenv("BINANCE_API_SECRET")) if isinstance(creds, dict) else os.getenv("BINANCE_API_SECRET")
    
    if not api_key or not api_secret:
        return {"success": False, "error": "Binance API Keys not configured.", "data": []}
        
    exchange = ccxt_async.binance({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
        'options': {
            'adjustForTimeDifference': True,
        }
    })
    
    validated_trades = []
    anomalies = []
    last_error = None
    try:
        default_pairs = [
            'USDT/ARS', 'BTC/ARS', 'ETH/ARS', 'USDC/USDT', 'USDC/ARS', 'BTC/USDT', 'ETH/USDT',
            'BNB/USDT', 'SOL/USDT', 'FDUSD/USDT', 'BUSD/USDT', 'PEPE/USDT', 'LINK/USDT',
            'WLD/USDT', 'SUI/USDT', 'TAO/USDT', 'DOGE/USDT', 'XRP/USDT', 'ADA/USDT', 'AVAX/USDT',
            'NEAR/USDT', 'DOT/USDT', 'RENDER/USDT', 'ARB/USDT', 'OP/USDT', 'FET/USDT', 'DAI/USDT',
            'TRX/USDT', 'MATIC/USDT', 'SHIB/USDT', 'LTC/USDT', 'U/USDT'
        ]
        pairs = get_exchange_pairs('binance', default_pairs)
        for extra_p in ('U/USDT', 'FDUSD/USDT', 'BNB/USDT', 'SOL/USDT', 'PEPE/USDT', 'BUSD/USDT', 'LINK/USDT', 'WLD/USDT', 'SUI/USDT', 'TAO/USDT'):
            if extra_p not in pairs:
                pairs = list(pairs) + [extra_p]
        
        for pair in pairs:
            try:
                crypto = pair.split('/')[0] if '/' in pair else pair
                if since_ms is not None:
                    since = since_ms
                else:
                    checkpoint = get_latest_transaction_timestamp("Binance Spot", crypto, lookback_days=1)
                    since = checkpoint if checkpoint is not None else 1577836800000
                limit = 1000
                while True:
                    trades = await exchange.fetch_my_trades(symbol=pair, since=since, limit=limit)
                    if not trades:
                        break
                    for t in trades:
                        try:
                            models = decompose_api_trade(t, pair, "Binance Spot")
                            validated_trades.extend(models)
                        except ValidationError as ve:
                            anomalies.append({"exchange": "Binance Spot", "row": t, "error": str(ve)})
                            continue
                    since = trades[-1]['timestamp'] + 1
                    if len(trades) < limit:
                        break
            except ccxt_async.AuthenticationError as ae:
                return {"success": False, "error": f"Error de autenticación en Binance: {ae}", "data": [], "anomalies": []}
            except Exception as e:
                last_error = e
                anomalies.append({"exchange": "Binance Spot", "pair": pair, "error": str(e)})
                print(f"Skipping Binance {pair}: {e}")
                
        if not validated_trades and last_error:
            return {"success": False, "error": f"Fallo al consultar pares de Binance. Último error: {last_error}", "data": [], "anomalies": []}
            
        return {"success": True, "error": None, "data": validated_trades, "anomalies": anomalies}
    except Exception as e:
        return {"success": False, "error": f"Binance V2 Sync Error: {str(e)}", "data": [], "anomalies": []}
    finally:
        await exchange.close()


async def fetch_binance_p2p_v2(creds=None, since_ms=None):
    api_key = (creds.get('apiKey') or creds.get('api_key') or os.getenv("BINANCE_API_KEY")) if isinstance(creds, dict) else os.getenv("BINANCE_API_KEY")
    api_secret = (creds.get('secret') or creds.get('api_secret') or os.getenv("BINANCE_API_SECRET")) if isinstance(creds, dict) else os.getenv("BINANCE_API_SECRET")
    if not api_key or not api_secret:
        return {"success": False, "error": "Binance API Keys not configured.", "data": []}
    exchange = ccxt_async.binance({
        'apiKey': api_key, 'secret': api_secret,
        'enableRateLimit': True,
        'options': {
            'adjustForTimeDifference': True,
            'recvWindow': 60000
        }
    })
    validated_trades = []
    anomalies = []
    seen_order_numbers = set()
    last_error = None
    try:
        try:
            await exchange.load_time_difference()
        except Exception as e:
            logging.getLogger(__name__).warning(f"Error sincronizando reloj con Binance P2P: {e}")

        if not hasattr(exchange, 'sapiGetC2cOrderMatchListUserOrderHistory'):
            return {"success": True, "error": None, "data": [], "anomalies": []}
        
        now_ms = int(time.time() * 1000)
        thirty_days_ms = 30 * 24 * 60 * 60 * 1000
        
        # Determine whether this is an initial sync (empty DB) or an incremental sync
        latest_p2p_date = None
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT MAX(fecha) FROM transactions WHERE exchange = 'Binance P2P'")
            row = cur.fetchone()
            if row and row[0]:
                latest_p2p_date = row[0]
        finally:
            conn.close()

        if since_ms is not None:
            diff = max(0, now_ms - since_ms)
            windows_count = max(1, int(diff / thirty_days_ms) + 1)
        elif latest_p2p_date:
            try:
                # Parse latest timestamp and add 7 days lookback margin
                s_date = str(latest_p2p_date).strip().replace('Z', '')
                dt_latest = datetime.fromisoformat(s_date)
                checkpoint_dt = dt_latest - timedelta(days=7)
                diff = max(0, now_ms - int(checkpoint_dt.timestamp() * 1000))
                windows_count = max(1, int(diff / thirty_days_ms) + 1)
            except Exception:
                windows_count = 2
        else:
            # First-time initial sync: calculate dynamically from 2020-01-01 to today
            start_date_p2p = datetime(2020, 1, 1, tzinfo=timezone.utc)
            now_dt = datetime.now(timezone.utc)
            windows_count = int((now_dt - start_date_p2p).days / 30) + 1

        consecutive_empty_windows = 0
        for i in range(windows_count):
            end_ts = now_ms - (i * thirty_days_ms)
            start_ts = now_ms - ((i + 1) * thirty_days_ms)
            window_had_orders = False
            
            for trade_type in ['BUY', 'SELL']:
                page = 1
                while page <= 40:
                    c2c_list = []
                    success = False
                    for attempt in range(5):
                        try:
                            await asyncio.sleep(0.12)
                            res = await exchange.sapiGetC2cOrderMatchListUserOrderHistory({
                                'tradeType': trade_type,
                                'startTimestamp': start_ts,
                                'endTimestamp': end_ts,
                                'page': page,
                                'rows': 100
                            })
                            c2c_list = res.get('data', []) if isinstance(res, dict) else []
                            success = True
                            break
                        except Exception as req_err:
                            err_msg = str(req_err).lower()
                            if any(k in err_msg for k in ['429', '-1003', 'too many', 'limited']):
                                await asyncio.sleep(2.0 * (attempt + 1))
                            else:
                                await asyncio.sleep(0.5)
                            last_error = req_err
                    
                    if not success or not c2c_list:
                        break
                    
                    for o in c2c_list:
                        if o.get('orderStatus') != 'COMPLETED':
                            continue
                        order_num = o.get('orderNumber')
                        if order_num in seen_order_numbers:
                            continue
                        seen_order_numbers.add(order_num)
                        window_had_orders = True
                        try:
                            is_buy = o.get('tradeType', '').upper() == 'BUY'
                            fiat = str(o.get('fiat', o.get('fiatUnit', 'ARS'))).upper().strip()
                            monto = float(o.get('amount', 0))
                            precio = float(o.get('unitPrice', 0))
                            total_fiat = float(o.get('totalPrice', monto * precio))
                            crypto = o.get('asset', 'USDT').upper()
                            tx_date = datetime.fromtimestamp(int(o['createTime']) / 1000.0, tz=timezone.utc).replace(tzinfo=None)
                            pay_method = o.get('payMethodName', '')

                            if fiat in ('ARS', ''):
                                monto_ars = total_fiat
                                cot_ars = precio
                                p2p_comment = f"Order ID: {order_num} | Binance P2P ({pay_method})"
                            else:
                                from parsers.base_parser import get_fiat_usd_rate
                                rate = get_exchange_rate_from_obj(tx_date)
                                fiat_usd = get_fiat_usd_rate(fiat)
                                monto_ars = total_fiat * fiat_usd * rate
                                cot_ars = precio * fiat_usd * rate
                                p2p_comment = f"Order ID: {order_num} | Binance P2P [{fiat}] ({pay_method})"

                            model = TransactionModel(
                                fecha=tx_date,
                                exchange="Binance P2P",
                                tipo_operacion="Compra" if is_buy else "Venta",
                                moneda=crypto,
                                monto_compra_cripto=monto if is_buy else 0.0,
                                monto_venta_cripto=monto if not is_buy else 0.0,
                                cotizacion_compra=cot_ars if is_buy else 0.0,
                                cotizacion_venta=cot_ars if not is_buy else 0.0,
                                monto_ars=monto_ars,
                                comentarios=p2p_comment
                            )
                            validated_trades.append(model)
                        except ValidationError as ve:
                            anomalies.append({"exchange": "Binance P2P", "row": o, "error": str(ve)})
                            continue
                    
                    if len(c2c_list) < 50:
                        break
                    page += 1

            if window_had_orders:
                consecutive_empty_windows = 0
            else:
                consecutive_empty_windows += 1

            # Early stopping on initial sync: once orders have been seen, if we encounter 6 consecutive empty months towards the past, stop
            if latest_p2p_date is None and seen_order_numbers and consecutive_empty_windows >= 6:
                break

        if not validated_trades and last_error:
            err_str = str(last_error).lower()
            if any(term in err_str for term in ['auth', 'key', 'permission', '401', '403', 'signature', 'invalid', '-1022', '-2015', '-2014', '-1021']):
                return {"success": False, "error": f"Error de autenticación o permisos en Binance P2P: {_clean_api_error(str(last_error))}", "data": [], "anomalies": anomalies}

        return {"success": True, "error": None, "data": validated_trades, "anomalies": anomalies}
    except Exception as e:
        return {"success": False, "error": f"Binance P2P Sync Error: {str(e)}", "data": [], "anomalies": []}
    finally:
        await exchange.close()

async def fetch_binance_transfers_v2(creds=None, since_ms=None):
    api_key = (creds.get('apiKey') or creds.get('api_key') or os.getenv("BINANCE_API_KEY")) if isinstance(creds, dict) else os.getenv("BINANCE_API_KEY")
    api_secret = (creds.get('secret') or creds.get('api_secret') or os.getenv("BINANCE_API_SECRET")) if isinstance(creds, dict) else os.getenv("BINANCE_API_SECRET")
    if not api_key or not api_secret:
        return {"success": False, "error": "Binance API Keys not configured.", "data": [], "anomalies": []}
    exchange = ccxt_async.binance({
        'apiKey': api_key, 'secret': api_secret,
        'enableRateLimit': True,
        'options': {'adjustForTimeDifference': True}
    })
    validated_transfers = []
    anomalies = []
    seen_ids = set()
    if since_ms:
        start_dt = datetime.fromtimestamp(since_ms / 1000.0, tz=timezone.utc)
    else:
        conn = get_connection()
        latest_tr = None
        try:
            cur = conn.cursor()
            cur.execute("SELECT MAX(fecha) FROM transactions WHERE exchange = 'Binance Spot' AND tipo_operacion IN ('Ingreso Cripto', 'Retiro Cripto', 'Depósito', 'Retiro')")
            row = cur.fetchone()
            if row and row[0]:
                latest_tr = row[0]
        finally:
            conn.close()
        if latest_tr:
            try:
                s_tr = str(latest_tr).strip().replace('Z', '')
                dt_tr = datetime.fromisoformat(s_tr)
                start_dt = dt_tr - timedelta(days=7)
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=timezone.utc)
            except Exception:
                start_dt = datetime(2022, 1, 1, tzinfo=timezone.utc)
        else:
            start_dt = datetime(2022, 1, 1, tzinfo=timezone.utc)
    windows = generate_time_windows(start_dt, chunk_days=60)
    try:
        for start_ts, end_ts in windows:
            # 1. Depósitos (sapi/v1/capital/deposit/hisrec)
            try:
                params = {'startTime': start_ts, 'endTime': end_ts}
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
                        exchange="Binance Spot",
                        tipo_operacion="Ingreso Cripto",
                        moneda=coin,
                        monto_compra_cripto=amount,
                        monto_venta_cripto=0.0,
                        cotizacion_compra=0.0,
                        cotizacion_venta=0.0,
                        monto_ars=0.0,
                        comentarios=f"Depósito Binance TXID: {tx_id}"
                    )
                    validated_transfers.append(model)
            except Exception as dep_err:
                anomalies.append({"exchange": "Binance Spot", "action": "fetch_deposits", "window": f"{start_ts}-{end_ts}", "error": str(dep_err)})

            # 2. Retiros (sapi/v1/capital/withdraw/history)
            try:
                params = {'startTime': start_ts, 'endTime': end_ts}
                withdrawals = await exchange.fetch_withdrawals(since=start_ts, params=params)
                for w in (withdrawals or []):
                    status = str(w.get('status', '')).lower()
                    if status not in ('ok', 'success', 'completed', '1', 1, '6'):
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
                        exchange="Binance Spot",
                        tipo_operacion="Retiro Cripto",
                        moneda=coin,
                        monto_compra_cripto=0.0,
                        monto_venta_cripto=amount,
                        cotizacion_compra=0.0,
                        cotizacion_venta=0.0,
                        monto_ars=0.0,
                        comentarios=f"Retiro Binance TXID: {tx_id}"
                    )
                    validated_transfers.append(model)
            except Exception as w_err:
                anomalies.append({"exchange": "Binance Spot", "action": "fetch_withdrawals", "window": f"{start_ts}-{end_ts}", "error": str(w_err)})

        return {"success": True, "error": None, "data": validated_transfers, "anomalies": anomalies}
    except Exception as e:
        return {"success": False, "error": f"Binance Transfers Sync Error: {str(e)}", "data": [], "anomalies": anomalies}
    finally:
        await exchange.close()



async def check_api_auth_binance():
    key = os.getenv("BINANCE_API_KEY")
    secret = os.getenv("BINANCE_API_SECRET")
    if _is_placeholder_key(key, secret):
        return {"status": "unconfigured", "msg": "Llaves no ingresadas"}
    try:
        ex = ccxt_async.binance({
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
            logging.getLogger(__name__).warning(f"Error sincronizando reloj con Binance en auth check: {e}")
        await ex.fetch_balance({'type': 'spot'})
        await ex.close()
        return {"status": "online", "msg": "Autenticado OK"}
    except Exception as e:
        try:
            await ex.close()
        except Exception:
            pass
        err_str = str(e).lower()
        if any(term in err_str for term in ['auth', 'key', 'permission', '401', '403', 'signature', 'invalid', '-1022', '-2015', '-2014']) or ('expired' in err_str and 'request' not in err_str):
            return {"status": "expired", "msg": _clean_api_error(str(e))}
        return {"status": "offline", "msg": _clean_api_error(str(e))}
