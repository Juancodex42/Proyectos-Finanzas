import pandas as pd
from db.connection import get_connection


def _clean_df_for_json(df):
    """Converts NaNs to None so jsonify produces valid JSON nulls instead of invalid NaN tokens."""
    if df is None or df.empty:
        return []
    return df.astype(object).where(pd.notnull(df), None).to_dict(orient='records')


def _build_filter_sql(date_start=None, date_end=None, exchanges=None, prefix="WHERE", status_filter=None):
    conditions = []
    params = []
    if date_start and str(date_start).strip():
        conditions.append("fecha >= ?")
        if len(str(date_start)) > 10:
            params.append(str(date_start))
        else:
            params.append(str(date_start)[:10] + " 00:00:00")
    if date_end and str(date_end).strip():
        conditions.append("fecha <= ?")
        if len(str(date_end)) > 10:
            params.append(str(date_end))
        else:
            params.append(str(date_end)[:10] + " 23:59:59")
    if exchanges:
        if isinstance(exchanges, str):
            exchanges = [e.strip() for e in exchanges.split(',') if e.strip()]
        if isinstance(exchanges, list) and len(exchanges) > 0:
            placeholders = ','.join(['?'] * len(exchanges))
            conditions.append(f"exchange IN ({placeholders})")
            params.extend(exchanges)

    if status_filter == 'certified':
        conditions.append("is_certified = 1")
    elif status_filter == 'uncertified':
        conditions.append("(is_certified IS NULL OR is_certified = 0)")

    if conditions:
        return f" {prefix} " + " AND ".join(conditions), params
    return "", []


def get_kpis(date_start=None, date_end=None, exchanges=None, status_filter=None):
    """Calculates high-level KPIs for the overview dashboard, including certified vs provisional breakdown."""
    conn = get_connection()
    try:
        c = conn.cursor()
        vol_base = (
            "COALESCE(source, '') != 'BANK_STATEMENT' "
            "AND UPPER(TRIM(moneda)) NOT IN ('ARS', 'USD', 'EUR', 'NONE', '') "
            "AND LOWER(tipo_operacion) NOT LIKE '%retiro%' "
            "AND LOWER(tipo_operacion) NOT LIKE '%ingreso%' "
            "AND LOWER(tipo_operacion) NOT LIKE '%fee%' "
            "AND LOWER(tipo_operacion) NOT LIKE '%comision%' "
            "AND LOWER(tipo_operacion) NOT LIKE '%comisión%' "
            "AND LOWER(tipo_operacion) NOT LIKE '%bloqueo%' "
            "AND LOWER(tipo_operacion) NOT LIKE '%prestamo%' "
            "AND LOWER(tipo_operacion) NOT LIKE '%préstamo%' "
            "AND LOWER(tipo_operacion) NOT LIKE '%inyecci%' "
            "AND LOWER(tipo_operacion) NOT LIKE '%rendimiento%' "
            "AND LOWER(tipo_operacion) NOT LIKE '%gasto personal%' "
            "AND LOWER(tipo_operacion) NOT LIKE '%pase interno%' "
            "AND (COALESCE(comentarios, '') NOT LIKE '%[INTERCAMBIO:%' OR (LOWER(tipo_operacion) LIKE '%compra%' OR LOWER(tipo_operacion) LIKE '%buy%'))"
        )
        vol_filter, vol_params = _build_filter_sql(date_start, date_end, exchanges, "AND", status_filter)
        c.execute(f"SELECT SUM(monto_ars) FROM transactions WHERE {vol_base}{vol_filter}", vol_params)
        total_volume_ars = c.fetchone()[0] or 0.0

        buys_filter, buys_params = _build_filter_sql(date_start, date_end, exchanges, "AND", status_filter)
        c.execute(f"SELECT SUM(monto_ars) FROM transactions WHERE {vol_base} AND ((LOWER(tipo_operacion) LIKE '%compra%' OR LOWER(tipo_operacion) LIKE '%buy%') OR (monto_compra_cripto > 0 AND monto_ars > 0)){buys_filter}", buys_params)
        total_buys_ars = c.fetchone()[0] or 0.0

        c.execute(f"SELECT SUM(monto_ars) FROM transactions WHERE {vol_base} AND ((LOWER(tipo_operacion) LIKE '%venta%' OR LOWER(tipo_operacion) LIKE '%sell%') OR (monto_venta_cripto > 0 AND monto_ars > 0)){buys_filter}", buys_params)
        total_sells_ars = c.fetchone()[0] or 0.0

        filter_sql, params = _build_filter_sql(date_start, date_end, exchanges, "WHERE", status_filter)
        c.execute(f"SELECT COUNT(*) FROM transactions {filter_sql}", params)
        tx_count = c.fetchone()[0] or 0

        cert_filter, cert_params = _build_filter_sql(date_start, date_end, exchanges, "AND", "certified")
        c.execute(f"SELECT SUM(monto_ars) FROM transactions WHERE {vol_base} AND is_certified=1{cert_filter}", cert_params)
        certified_volume = c.fetchone()[0] or 0.0
        c.execute(f"SELECT COUNT(*) FROM transactions WHERE is_certified=1{cert_filter}", cert_params)
        certified_count = c.fetchone()[0] or 0

        uncert_filter, uncert_params = _build_filter_sql(date_start, date_end, exchanges, "AND", "uncertified")
        c.execute(f"SELECT SUM(monto_ars) FROM transactions WHERE {vol_base} AND (is_certified IS NULL OR is_certified=0){uncert_filter}", uncert_params)
        provisional_volume = c.fetchone()[0] or 0.0
        c.execute(f"SELECT COUNT(*) FROM transactions WHERE (is_certified IS NULL OR is_certified=0){uncert_filter}", uncert_params)
        provisional_count = c.fetchone()[0] or 0

        c.execute("SELECT MAX(end_date) FROM certifications")
        last_cert_end = c.fetchone()[0]
    finally:
        conn.close()

    certified_pct = round((certified_volume / total_volume_ars * 100.0), 1) if total_volume_ars > 0 else 0.0

    return {
        "total_volume_ars": round(total_volume_ars, 2),
        "total_buys_ars": round(total_buys_ars, 2),
        "total_sells_ars": round(total_sells_ars, 2),
        "tx_count": tx_count,
        "certified_volume_ars": round(certified_volume, 2),
        "provisional_volume_ars": round(provisional_volume, 2),
        "certified_count": certified_count,
        "certified_tx_count": certified_count,
        "provisional_count": provisional_count,
        "certified_pct": certified_pct,
        "certified_coverage_pct": round(certified_pct, 1),
        "last_certified_end": last_cert_end
    }


def get_daily_volume(date_start=None, date_end=None, exchanges=None, status_filter=None):
    """Aggregates buy/sell volume by day for charting."""
    vol_base = (
        "COALESCE(source, '') != 'BANK_STATEMENT' "
        "AND UPPER(TRIM(moneda)) NOT IN ('ARS', 'USD', 'EUR', 'NONE', '') "
        "AND LOWER(tipo_operacion) NOT LIKE '%retiro%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%ingreso%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%fee%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%comision%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%comisión%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%bloqueo%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%prestamo%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%préstamo%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%inyecci%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%rendimiento%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%gasto personal%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%pase interno%'"
    )
    filter_sql, params = _build_filter_sql(date_start, date_end, exchanges, "AND", status_filter)
    query = f"""
        SELECT 
            SUBSTR(fecha, 1, 10) as day,
            SUM(CASE WHEN ((LOWER(tipo_operacion) LIKE '%compra%' OR LOWER(tipo_operacion) LIKE '%buy%') OR (monto_compra_cripto > 0 AND monto_ars > 0)) THEN monto_ars ELSE 0 END) as buys,
            SUM(CASE WHEN ((LOWER(tipo_operacion) LIKE '%venta%' OR LOWER(tipo_operacion) LIKE '%sell%') OR (monto_venta_cripto > 0 AND monto_ars > 0)) THEN monto_ars ELSE 0 END) as sells
        FROM transactions
        WHERE {vol_base}{filter_sql}
        GROUP BY day
        ORDER BY day ASC
    """
    conn = get_connection()
    try:
        df = pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()
    return _clean_df_for_json(df)


def get_exchange_distribution(date_start=None, date_end=None, exchanges=None, status_filter=None):
    """Calculates operation volume distribution by exchange."""
    vol_base = (
        "COALESCE(source, '') != 'BANK_STATEMENT' "
        "AND UPPER(TRIM(moneda)) NOT IN ('ARS', 'USD', 'EUR', 'NONE', '') "
        "AND LOWER(tipo_operacion) NOT LIKE '%retiro%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%ingreso%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%fee%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%comision%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%comisión%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%bloqueo%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%prestamo%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%préstamo%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%inyecci%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%rendimiento%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%gasto personal%' "
        "AND LOWER(tipo_operacion) NOT LIKE '%pase interno%' "
        "AND (COALESCE(comentarios, '') NOT LIKE '%[INTERCAMBIO:%' OR (LOWER(tipo_operacion) LIKE '%compra%' OR LOWER(tipo_operacion) LIKE '%buy%'))"
    )
    filter_sql, params = _build_filter_sql(date_start, date_end, exchanges, "AND", status_filter)
    query = f"""
        SELECT 
            exchange as name,
            SUM(monto_ars) as value
        FROM transactions
        WHERE {vol_base}{filter_sql}
        GROUP BY exchange
        ORDER BY value DESC
    """
    conn = get_connection()
    try:
        df = pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()
    return _clean_df_for_json(df)


def _calc_sale_net_flow(r):
    if 'VENTA' not in str(r.get('tipo_operacion', '')).upper():
        return 0.0
    m_ars = float(r.get('monto_ars') or 0.0)
    c_compra = float(r.get('cotizacion_compra') or 0.0)
    m_venta = float(r.get('monto_venta_cripto') or 0.0)
    desc_val = r.get('monto_descubierto', 0.0)
    descubierto = float(desc_val or 0.0) if pd.notna(desc_val) else 0.0
    covered_venta = max(0.0, m_venta - max(0.0, descubierto))
    return m_ars - (c_compra * covered_venta)


def get_equity_curve(date_start=None, date_end=None, exchanges=None, interval='daily', status_filter=None):
    """Calculates cumulative net cashflow / profit equity curve."""
    if date_start is not None and not str(date_start).strip():
        date_start = None
    if date_end is not None and not str(date_end).strip():
        date_end = None

    _excl_ops = ('retiro', 'withdraw', 'envio', 'envío', 'deposito', 'depósito', 'deposit', 'ingreso cripto', 'transferencia')
    initial_equity = 0.0
    conn = get_connection()
    try:
        if date_start:
            s_dt = pd.to_datetime(date_start, errors='coerce')
            if pd.notna(s_dt):
                prior_filter, prior_params = _build_filter_sql(None, (s_dt - pd.Timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M:%S'), exchanges, "WHERE", status_filter)
                prior_query = f"SELECT * FROM transactions {prior_filter}"
                prior_df = pd.read_sql_query(prior_query, conn, params=prior_params)
                if not prior_df.empty:
                    prior_op = prior_df['tipo_operacion'].fillna('').astype(str).str.lower().str.strip()
                    prior_df = prior_df[~prior_op.apply(lambda op: any(k in op for k in _excl_ops))].copy()
                if not prior_df.empty:
                    prior_df['net_flow'] = prior_df.apply(_calc_sale_net_flow, axis=1)
                    initial_equity = prior_df['net_flow'].sum()

        filter_sql, params = _build_filter_sql(date_start, date_end, exchanges, "WHERE", status_filter)
        query = f"SELECT * FROM transactions {filter_sql} ORDER BY fecha ASC"
        df = pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()

    if not df.empty:
        op_lower = df['tipo_operacion'].fillna('').astype(str).str.lower().str.strip()
        df = df[~op_lower.apply(lambda op: any(k in op for k in _excl_ops))].copy()
    if not df.empty:
        from services.fifo_service import parse_dates_series_robust
        df['fecha'] = parse_dates_series_robust(df['fecha'])
        df = df.dropna(subset=['fecha']).copy()
        df['net_flow'] = df.apply(_calc_sale_net_flow, axis=1)
    else:
        df = pd.DataFrame(columns=['fecha', 'net_flow'])

    if date_start and date_end:
        start_dt = pd.to_datetime(date_start, errors='coerce')
        end_dt = pd.to_datetime(date_end, errors='coerce')
        if pd.notna(start_dt) and pd.notna(end_dt):
            dummy_df = pd.DataFrame([
                {'fecha': start_dt, 'net_flow': 0.0},
                {'fecha': end_dt, 'net_flow': 0.0}
            ])
            df = pd.concat([df[['fecha', 'net_flow']], dummy_df], ignore_index=True)

    if df.empty:
        return []

    df = df.sort_values('fecha')
    freq_map = {'daily': 'D', 'weekly': 'W', 'monthly': 'M', 'yearly': 'Y'}
    freq = freq_map.get(interval, 'D')

    grouped = df.set_index('fecha').resample(freq)['net_flow'].sum().reset_index()
    grouped['equity'] = grouped['net_flow'].cumsum() + initial_equity

    if freq == 'h':
        grouped['period'] = grouped['fecha'].dt.strftime('%H:%M')
    elif freq == 'M':
        grouped['period'] = grouped['fecha'].dt.strftime('%Y-%m')
    elif freq == 'Y':
        grouped['period'] = grouped['fecha'].dt.strftime('%Y')
    else:
        grouped['period'] = grouped['fecha'].dt.strftime('%Y-%m-%d')

    result = []
    for _, row in grouped.iterrows():
        result.append({
            "period": row['period'],
            "equity": round(row['equity'], 2),
            "net_flow": round(row['net_flow'], 2)
        })
    return result


def get_modal_spread(date_start=None, date_end=None, exchanges=None, status_filter=None):
    """Calculates the most frequent (modal) percentage spread in trade operations using FIFO costs."""
    if date_start is not None and not str(date_start).strip():
        date_start = None
    if date_end is not None and not str(date_end).strip():
        date_end = None

    filter_sql, params = _build_filter_sql(date_start, date_end, exchanges, "AND", status_filter)
    query = f"SELECT cotizacion_compra, cotizacion_venta FROM transactions WHERE (LOWER(tipo_operacion) LIKE '%venta%' OR LOWER(tipo_operacion) LIKE '%sell%') AND cotizacion_venta > 0 AND cotizacion_compra > 0{filter_sql}"
    conn = get_connection()
    try:
        df_sales = pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()

    if df_sales.empty:
        return {"modal_spread": 0.0, "sample_count": 0}

    spreads = []
    for _, row in df_sales.iterrows():
        buy_price = float(row['cotizacion_compra'])
        sell_price = float(row['cotizacion_venta'])
        if buy_price > 0:
            spread = ((sell_price / buy_price) - 1.0) * 100.0
            if abs(spread - 17.647) < 0.1:
                continue
            if -30.0 < spread < 50.0:
                spreads.append(round(spread, 1))

    if not spreads:
        return {"modal_spread": 0.0, "sample_count": 0}

    df_spreads = pd.Series(spreads)
    mode_val = df_spreads.mode()
    modal_spread = float(mode_val.iloc[0]) if not mode_val.empty else 0.0
    return {"modal_spread": max(0.0, modal_spread), "sample_count": len(spreads)}


def get_processing_history():
    """Returns history of unique exchanges with unified, API-only, and File-only temporal ranges."""
    conn = get_connection()
    query = """
        SELECT exchange,
               MIN(fecha) as first_tx, MAX(fecha) as last_tx, COUNT(*) as count,
               MIN(CASE WHEN source = 'EXCHANGE_API' THEN fecha ELSE NULL END) as api_first_tx,
               MAX(CASE WHEN source = 'EXCHANGE_API' THEN fecha ELSE NULL END) as api_last_tx,
               SUM(CASE WHEN source = 'EXCHANGE_API' THEN 1 ELSE 0 END) as api_count,
               MIN(CASE WHEN source != 'EXCHANGE_API' THEN fecha ELSE NULL END) as file_first_tx,
               MAX(CASE WHEN source != 'EXCHANGE_API' THEN fecha ELSE NULL END) as file_last_tx,
               SUM(CASE WHEN source != 'EXCHANGE_API' THEN 1 ELSE 0 END) as file_count
        FROM transactions 
        GROUP BY exchange
    """
    try:
        df = pd.read_sql_query(query, conn)
        return _clean_df_for_json(df)
    except Exception as e:
        print(f"Error fetching history: {e}")
        return []
    finally:
        conn.close()


def get_uploaded_files_history():
    """Returns discrete uploaded files recorded in transactions with their count and date bounds."""
    conn = get_connection()
    query = """
        SELECT filename, exchange,
               MIN(fecha) as first_tx, MAX(fecha) as last_tx, COUNT(*) as count
        FROM transactions
        WHERE filename IS NOT NULL AND TRIM(filename) != '' AND TRIM(filename) != 'None'
        GROUP BY filename, exchange
        ORDER BY last_tx DESC
    """
    try:
        df = pd.read_sql_query(query, conn)
        return _clean_df_for_json(df)
    except Exception as e:
        print(f"Error fetching uploaded files history: {e}")
        return []
    finally:
        conn.close()


def delete_transactions_by_filename(filename: str) -> int:
    """Deletes transactions originating from a specific uploaded file and recalculates FIFO."""
    if not filename:
        return 0
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM transactions WHERE filename = ? AND (is_certified IS NULL OR is_certified = 0)", (filename,))
        deleted = c.rowcount
        conn.commit()
    finally:
        conn.close()
    if deleted > 0:
        try:
            from services.cache_service import invalidate_analytics_cache
            invalidate_analytics_cache()
            from services.fifo_service import recalculate_fifo_costs_db
            recalculate_fifo_costs_db()
        except Exception as e:
            print(f"Notice after deleting file {filename}: {e}")
    return deleted
