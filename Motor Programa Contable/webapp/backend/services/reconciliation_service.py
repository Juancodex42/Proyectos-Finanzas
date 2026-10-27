"""
Motor de conciliación contable y auditoría forense de ventas fantasma.
Simula el balance temporal y gestiona ajustes sintéticos de cartera.
Referencia de diseño: docs/especificacion_fifo_prioridades.md
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import sys
from db.connection import get_connection, DB_PATH
try:
    import db_manager
except ImportError:
    from services import transactions_service as db_manager

class ReconciliationEngine:
    def __init__(self, db_path=None):
        if db_path is None:
            if 'db_manager' in sys.modules:
                dm = sys.modules['db_manager']
                self.db_path = getattr(dm, 'DB_PATH', DB_PATH)
            else:
                self.db_path = DB_PATH
        else:
            self.db_path = db_path
        
    def _get_connection(self):
        default_path = getattr(sys.modules['db_manager'], 'DB_PATH', DB_PATH) if 'db_manager' in sys.modules else DB_PATH
        if self.db_path and self.db_path != default_path:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout = 30000;")
            conn.execute("PRAGMA journal_mode=WAL;")
            return conn
        return get_connection()
        
    def run_full_audit(self, start_date=None, end_date=None):
        """
        Reconstructs the ledger for all currencies chronologically.
        Simulates the wallet balances mathematically.
        Returns a list of 'Phantom Sales' or negative balance anomalies.
        """
        from services.fifo_service import parse_dates_series_robust
        conn = None
        try:
            conn = self._get_connection()
            query = """
                SELECT tx_hash, fecha, exchange, tipo_operacion, moneda, monto_compra_cripto, monto_venta_cripto, comentarios, is_certified 
                FROM transactions 
                ORDER BY fecha ASC, 
                         CASE 
                            WHEN (LOWER(tipo_operacion) LIKE '%compra%' OR LOWER(tipo_operacion) LIKE '%buy%') AND monto_compra_cripto > 0 THEN 1
                            WHEN (LOWER(tipo_operacion) LIKE '%retiro%' OR LOWER(tipo_operacion) LIKE '%withdraw%' OR LOWER(tipo_operacion) LIKE '%envio%' OR LOWER(tipo_operacion) LIKE '%egreso%') THEN 2
                            WHEN (LOWER(tipo_operacion) LIKE '%ingreso%' OR LOWER(tipo_operacion) LIKE '%deposit%' OR LOWER(tipo_operacion) LIKE '%recep%') THEN 3
                            ELSE 4 
                         END ASC,
                         tx_hash ASC
            """
            df = pd.read_sql_query(query, conn)
            
            # Fetch active certification ranges (start_date, end_date) directly from current DB
            certified_ranges = []
            max_cert_dt = None
            try:
                c_cursor = conn.cursor()
                c_cursor.execute("SELECT start_date, end_date FROM certifications")
                cert_rows = c_cursor.fetchall()
                for s_date, e_date in cert_rows:
                    if not s_date or not e_date:
                        continue
                    s_str = str(s_date).replace('T', ' ').strip()
                    e_str = str(e_date).replace('T', ' ').strip()
                    if len(s_str) == 10:
                        s_str += " 00:00:00"
                    if len(e_str) == 10:
                        e_str += " 23:59:59"
                    parsed_pair = parse_dates_series_robust(pd.Series([s_str, e_str]))
                    s_dt, e_dt = parsed_pair.iloc[0], parsed_pair.iloc[1]
                    if pd.notna(s_dt) and pd.notna(e_dt):
                        certified_ranges.append((s_dt, e_dt))
                if certified_ranges:
                    max_cert_dt = max(e_dt for _, e_dt in certified_ranges)
            except Exception:
                certified_ranges = []
                max_cert_dt = None
        except Exception as e:
            return {"success": False, "error": str(e), "anomalies": []}
        finally:
            if conn is not None:
                conn.close()
            
        if df.empty:
            return {"success": True, "anomalies": [], "final_balances": {}}
            
        anomalies = []
        ledgers = {}
        certified_boundary_passed_by_coin = set()
        
        from domain.operations import get_operation_priority

        def _get_recon_op_priority(row):
            return get_operation_priority(
                row.get('tipo_operacion'),
                row.get('monto_compra_cripto'),
                row.get('monto_venta_cripto')
            )

        df['inflow_priority'] = df.apply(_get_recon_op_priority, axis=1)
        df['dt'] = parse_dates_series_robust(df['fecha'])

        from models.transaction_models import canonicalize_ticker
        from models.operational_models import OPERATIONAL_NON_TAXABLE_TYPES
        op_non_taxable = {t.upper().strip() for t in OPERATIONAL_NON_TAXABLE_TYPES}

        if start_date:
            s_cut = parse_dates_series_robust(pd.Series([str(start_date).strip()])).iloc[0]
            if pd.notna(s_cut):
                # Calculate opening balance by replaying all transactions strictly prior to start_date
                prior_df = df[df['dt'] < s_cut].sort_values(['dt', 'inflow_priority', 'tx_hash'])
                for _, p_row in prior_df.iterrows():
                    p_crypto = canonicalize_ticker(p_row['moneda'])
                    if not p_crypto or p_crypto in ('NONE', 'ARS', 'USD', 'EUR', 'NAN'):
                        continue
                    if p_crypto not in ledgers:
                        ledgers[p_crypto] = 0.0
                    p_op = str(p_row['tipo_operacion']).strip().upper()
                    p_mc = float(p_row.get('monto_compra_cripto') or 0.0)
                    p_mv = float(p_row.get('monto_venta_cripto') or 0.0)
                    p_non_tax = (p_op in op_non_taxable) or any(t in p_op for t in op_non_taxable)
                    p_is_fee = any(k in p_op for k in ('COMISION', 'COMISIÓN', 'FEE', 'TAX', 'GASTO')) and not p_non_tax
                    p_is_out = any(k in p_op for k in ('RETIRO', 'ENVIO', 'ENVÍO', 'WITHDRAW', 'TRANSFER', 'SEND', 'EGRESO', 'SALIDA', 'EXTRACCION', 'EXTRACCIÓN')) and p_mv > 0 and not p_is_fee
                    p_is_buy = (any(k in p_op for k in ('COMPRA', 'INGRESO', 'DEPOSITO', 'DEPÓSITO', 'BUY', 'DEPOSIT', 'AJUSTE', 'RECEIVE', 'RECEPCION', 'RECEPCIÓN', 'ENTRADA', 'ABONO')) or (p_mc > 0 and p_mv == 0)) and not p_is_fee
                    p_is_sell = (any(k in p_op for k in ('VENTA', 'SELL', 'CONSUMO', 'PAGO', 'PAYMENT')) or (p_mv > 0 and p_mc == 0)) and not p_is_out and not p_is_fee and not p_non_tax
                    if p_is_buy:
                        ledgers[p_crypto] += p_mc
                    elif p_is_sell or p_is_out or p_is_fee:
                        ledgers[p_crypto] = max(0.0, ledgers[p_crypto] - p_mv)

                df = df[df['dt'] >= s_cut].copy()
        if end_date:
            e_raw = str(end_date).strip()
            if len(e_raw) == 10:
                e_raw += " 23:59:59"
            e_cut = parse_dates_series_robust(pd.Series([e_raw])).iloc[0]
            if pd.notna(e_cut):
                df = df[df['dt'] <= e_cut].copy()
        if df.empty:
            return {"success": True, "anomalies": [], "final_balances": ledgers}
        df_sorted = df.sort_values(['dt', 'inflow_priority', 'tx_hash'])
        
        for index, row in df_sorted.iterrows():
            crypto = canonicalize_ticker(row['moneda'])
            if not crypto or crypto in ('NONE', 'ARS', 'USD', 'EUR', 'NAN'):
                continue
                
            op_type = str(row['tipo_operacion']).strip().upper()
            monto_compra = float(row['monto_compra_cripto'] or 0.0)
            monto_venta = float(row['monto_venta_cripto'] or 0.0)
            
            if crypto not in ledgers:
                ledgers[crypto] = 0.0
                
            r_dt = row['dt']
            is_certified_tx = (pd.notna(r_dt) and any(s_dt <= r_dt <= e_dt for s_dt, e_dt in certified_ranges)) or (row.get('is_certified') in (1, '1', True))
            if is_certified_tx:
                # Las certificaciones C.P.N. sellaron y dictaminaron el stock histórico; reset deficit
                ledgers[crypto] = max(0.0, ledgers[crypto])

            if max_cert_dt is not None and pd.notna(r_dt) and crypto not in certified_boundary_passed_by_coin and r_dt > max_cert_dt:
                certified_boundary_passed_by_coin.add(crypto)
                ledgers[crypto] = max(0.0, ledgers[crypto])

            is_non_taxable_op = (op_type in op_non_taxable) or any(t in op_type for t in op_non_taxable)
            is_fee = any(k in op_type for k in ('COMISION', 'COMISIÓN', 'FEE', 'TAX', 'GASTO')) and not is_non_taxable_op
            is_transfer_out = any(k in op_type for k in ('RETIRO', 'ENVIO', 'ENVÍO', 'WITHDRAW', 'TRANSFER', 'SEND', 'EGRESO', 'SALIDA', 'EXTRACCION', 'EXTRACCIÓN')) and monto_venta > 0 and not is_fee
            is_buy = (any(k in op_type for k in ('COMPRA', 'INGRESO', 'DEPOSITO', 'DEPÓSITO', 'BUY', 'DEPOSIT', 'AJUSTE', 'RECEIVE', 'RECEPCION', 'RECEPCIÓN', 'ENTRADA', 'ABONO')) or (monto_compra > 0 and monto_venta == 0)) and not is_fee
            is_taxable_sell = (any(k in op_type for k in ('VENTA', 'SELL', 'CONSUMO', 'PAGO', 'PAYMENT')) or (monto_venta > 0 and monto_compra == 0)) and not is_transfer_out and not is_fee and not is_non_taxable_op

            if is_buy:
                ledgers[crypto] += monto_compra
            elif is_taxable_sell:
                epsilon = 1e-9  # Harmonized with check_history_gaps
                amount = monto_venta

                # Check for Phantom Sale
                available = max(0.0, ledgers[crypto])
                if amount - available > epsilon:
                    missing_amount = amount - available
                    if not is_certified_tx:
                        anomalies.append({
                            "crypto": crypto,
                            "currency": crypto,
                            "coin": crypto,
                            "date": row['fecha'],
                            "exchange": row['exchange'],
                            "type": row['tipo_operacion'],
                            "attempted_amount": amount,
                            "current_ledger": available,
                            "missing": missing_amount,
                            "deficit": missing_amount,
                            "source_ref": row['comentarios'],
                            "message": f"Phantom Sale Detected: Venta de {amount} {crypto} pero el saldo histórico registrado era {available} (Falta registrar {missing_amount} {crypto} previos)."
                        })
                ledgers[crypto] = max(0.0, ledgers[crypto] - amount)
            elif is_transfer_out:
                # Deduct balance to prevent phantom inflation from subsequent deposits, but do not flag as taxable anomaly
                ledgers[crypto] = max(0.0, ledgers[crypto] - monto_venta)
            elif is_fee:
                # Crypto fee consumes balance without flagging as phantom sale anomaly
                ledgers[crypto] = max(0.0, ledgers[crypto] - monto_venta)
                
        return {
            "success": True,
            "anomalies": anomalies,
            "final_balances": ledgers
        }

    def run_auto_correction(self):
        """
        Runs the audit and injects 'Ajuste de Conciliación Automática' transactions 
        for any detected phantom sales to balance the ledger.
        """
        audit = self.run_full_audit()
        if not audit.get("success"):
            return audit
            
        anomalies = audit.get("anomalies", [])
        if not anomalies:
            return {"success": True, "message": "No anomalies found. Ledger is perfectly balanced.", "fixed_count": 0, "inserted_corrections": 0}
            
        import hashlib
        from models.transaction_models import TransactionModel
        import db_manager
        
        inserted_total = 0
        fixes = []
        
        for a in anomalies:
            try:
                anomaly_dt = pd.to_datetime(a['date'])
                if hasattr(anomaly_dt, 'to_pydatetime'):
                    anomaly_dt = anomaly_dt.to_pydatetime()
                if anomaly_dt.hour == 0 and anomaly_dt.minute == 0 and anomaly_dt.second == 0:
                    fixed_date = anomaly_dt
                else:
                    fixed_date = anomaly_dt - timedelta(seconds=1)
                
                model = TransactionModel(
                    fecha=fixed_date,
                    exchange="Sistema de Conciliación",
                    tipo_operacion="Ingreso Automático",
                    moneda=a['crypto'],
                    monto_compra_cripto=a['missing'],
                    monto_venta_cripto=0.0,
                    cotizacion_compra=0.0,
                    cotizacion_venta=0.0,
                    monto_ars=0.0,
                    comentarios=f"Ajuste automático para cubrir Phantom Sale referenciada como: {a.get('source_ref', '')}"
                )
                dt_dict = model.to_dict()
                coin_val = a.get('coin') or a.get('crypto') or dt_dict.get('Moneda') or dt_dict.get('moneda') or ''
                amt_val = a.get('amount') if 'amount' in a else (a.get('missing') or dt_dict.get('Monto Compra (Cripto)') or dt_dict.get('monto_compra_cripto'))
                raw_str = f"AUTO_{a.get('date')}_{coin_val}_{amt_val}_{a.get('exchange')}"
                dt_dict['tx_hash'] = hashlib.md5(raw_str.encode('utf-8')).hexdigest()
                fixes.append(dt_dict)
            except Exception as e:
                print(f"Error creating fix for anomaly: {e}")
                
        if fixes:
            if self.db_path:
                orig_path = getattr(db_manager, 'DB_PATH', None)
                try:
                    db_manager.DB_PATH = self.db_path
                    inserted, skipped = db_manager.insert_transactions(fixes)
                finally:
                    if orig_path:
                        db_manager.DB_PATH = orig_path
            else:
                inserted, skipped = db_manager.insert_transactions(fixes)
            inserted_total = inserted
            
        verification = self.run_full_audit()
        
        return {
            "success": True,
            "message": f"Se aplicaron {inserted_total} ajustes automáticos.",
            "fixed_count": inserted_total,
            "inserted_corrections": inserted_total,
            "remaining_anomalies": len(verification.get("anomalies", []))
        }

    def classify_single_anomaly(self, date_str, exchange_str, crypto_str, missing_amount, origin_type):
        """
        Classifies an anomaly by inserting a transaction with the selected origin type.
        origin_type can be: 'Capital Inicial / Años Anteriores', 'Exchange Externo', 'P2P / Efectivo'.
        """
        import hashlib
        from models.transaction_models import TransactionModel
        from parsers.base_parser import get_usd_ars_rate
        from models.transaction_models import get_quote_usd_value

        orig_date = date_str
        if isinstance(orig_date, dict):
            orig_date = orig_date.get('date') or orig_date.get('fecha')

        try:
            import re
            s_dt = str(orig_date).strip()
            if not s_dt or s_dt.lower() in ('none', 'nan', 'nat', ''):
                raise ValueError("Fecha de anomalía inválida")
            use_df = not bool(re.match(r'^\d{4}[-/]', s_dt))
            dt_parsed = pd.to_datetime(s_dt, dayfirst=use_df)
            if pd.isna(dt_parsed):
                raise ValueError("Fecha de anomalía inválida")
            if hasattr(dt_parsed, 'to_pydatetime'):
                dt_parsed = dt_parsed.to_pydatetime()
            if dt_parsed.hour == 0 and dt_parsed.minute == 0 and dt_parsed.second == 0:
                fixed_date = dt_parsed
            else:
                fixed_date = dt_parsed - timedelta(seconds=1)
        except Exception as e:
            if isinstance(e, ValueError) and "Fecha de anomalía inválida" in str(e):
                raise
            raise ValueError(f"Fecha de anomalía inválida: {orig_date}") from e

        missing_flt = float(missing_amount)
        if origin_type and any(k in str(origin_type).lower() for k in ['capital inicial', 'años anteriores', 'anos anteriores']):
            cot_compra = 0.0
            m_ars = 0.0
        else:
            usd_ars_rate = get_usd_ars_rate(fixed_date)
            usd_val = get_quote_usd_value(crypto_str, missing_flt, fecha=fixed_date)
            m_ars = usd_val * usd_ars_rate
            cot_compra = m_ars / missing_flt if missing_flt > 0 else usd_ars_rate

        model = TransactionModel(
            fecha=fixed_date,
            exchange=exchange_str or origin_type or "Ajuste Manual",
            tipo_operacion="Compra",
            moneda=crypto_str,
            monto_compra_cripto=missing_flt,
            monto_venta_cripto=0.0,
            cotizacion_compra=cot_compra,
            cotizacion_venta=0.0,
            monto_ars=m_ars,
            comentarios=f"Ingreso clasificado manualmente como: {origin_type} para subsanar venta del {date_str} en {exchange_str}"
        )
        dt_dict = model.to_dict()
        if self.db_path:
            import db_manager
            orig_path = getattr(db_manager, 'DB_PATH', None)
            try:
                db_manager.DB_PATH = self.db_path
                inserted, skipped = db_manager.insert_transactions([dt_dict])
            finally:
                if orig_path:
                    db_manager.DB_PATH = orig_path
        else:
            inserted, skipped = db_manager.insert_transactions([dt_dict])
        return {"success": True, "inserted": inserted, "message": f"Operación clasificada como '{origin_type}' guardada con éxito."}

    def prune_obsolete_auto_corrections(self, coins=None, auto_re_correct=False, start_date=None, end_date=None):
        """
        Prunes or adjusts synthetic auto-corrections ('Sistema de Conciliación' / 'Ingreso Automático'
        or manual gap resolution placeholders) when real transactions have been retroactively uploaded.
        Auto-correction should not be triggered automatically without explicit confirmation.
        """
        conn = self._get_connection()
        c = conn.cursor()
        try:
            date_clause = ""
            date_params = []
            if start_date and end_date:
                date_clause = " AND fecha >= ? AND fecha <= ?"
                date_params = [str(start_date)[:10] + " 00:00:00", str(end_date)[:10] + " 23:59:59"]

            if coins:
                from models.transaction_models import canonicalize_ticker
                upper_coins = list({canonicalize_ticker(coin) for coin in coins if coin})
                if not upper_coins:
                    return
                placeholders = ','.join(['?'] * len(upper_coins))
                c.execute(f"""
                    SELECT COUNT(*) FROM transactions 
                    WHERE (exchange = 'Sistema de Conciliación' OR tipo_operacion = 'Ingreso Automático'
                           OR comentarios LIKE '%para subsanar venta%')
                      AND (comentarios NOT LIKE '%manualmente%' AND comentarios NOT LIKE '%Manual%'
                           AND exchange != 'Ajuste Manual' AND exchange NOT LIKE '%Manual%')
                      AND (is_certified IS NULL OR is_certified = 0)
                      AND (UPPER(moneda) IN ({placeholders}) OR UPPER(TRIM(REPLACE(REPLACE(moneda, '-TRC20', ''), '_TRX', ''))) IN ({placeholders}))
                      {date_clause}
                """, upper_coins + upper_coins + date_params)
                count = c.fetchone()[0]
                if count == 0:
                    return
                
                c.execute(f"""
                    DELETE FROM transactions 
                    WHERE (exchange = 'Sistema de Conciliación' OR tipo_operacion = 'Ingreso Automático'
                           OR comentarios LIKE '%para subsanar venta%')
                      AND (comentarios NOT LIKE '%manualmente%' AND comentarios NOT LIKE '%Manual%'
                           AND exchange != 'Ajuste Manual' AND exchange NOT LIKE '%Manual%')
                      AND (is_certified IS NULL OR is_certified = 0)
                      AND (UPPER(moneda) IN ({placeholders}) OR UPPER(TRIM(REPLACE(REPLACE(moneda, '-TRC20', ''), '_TRX', ''))) IN ({placeholders}))
                      {date_clause}
                """, upper_coins + upper_coins + date_params)
            else:
                c.execute("""
                    SELECT COUNT(*) FROM transactions 
                    WHERE (exchange = 'Sistema de Conciliación' OR tipo_operacion = 'Ingreso Automático'
                           OR comentarios LIKE '%para subsanar venta%')
                      AND (comentarios NOT LIKE '%manualmente%' AND comentarios NOT LIKE '%Manual%'
                           AND exchange != 'Ajuste Manual' AND exchange NOT LIKE '%Manual%')
                      AND (is_certified IS NULL OR is_certified = 0)
                """)
                count = c.fetchone()[0]
                if count == 0:
                    return
                c.execute("""
                    DELETE FROM transactions 
                    WHERE (exchange = 'Sistema de Conciliación' OR tipo_operacion = 'Ingreso Automático'
                           OR comentarios LIKE '%para subsanar venta%')
                      AND (comentarios NOT LIKE '%manualmente%' AND comentarios NOT LIKE '%Manual%'
                           AND exchange != 'Ajuste Manual' AND exchange NOT LIKE '%Manual%')
                      AND (is_certified IS NULL OR is_certified = 0)
                """)
            conn.commit()
        finally:
            conn.close()

        # Bug 1 fix: Do not manufacture artificial purchases without explicit user confirmation.
        if auto_re_correct:
            self.run_auto_correction()


