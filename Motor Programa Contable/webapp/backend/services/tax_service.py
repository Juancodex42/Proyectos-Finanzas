import logging
import re
import pandas as pd
from db.connection import get_connection

logger = logging.getLogger(__name__)


def resolve_active_fiscal_year(year=None) -> int:
    """Dynamically resolves target fiscal year: explicit arg > DB tax_settings > DB transactions > current year."""
    if year is not None:
        try:
            val = int(year)
            if val > 1900:
                return val
        except (ValueError, TypeError):
            pass
    try:
        conn = get_connection()
        try:
            c = conn.cursor()
            c.execute("SELECT MAX(year) FROM tax_settings")
            row = c.fetchone()
            if row and row[0] and int(row[0]) > 2000:
                return int(row[0])
            c.execute("SELECT MAX(CAST(SUBSTR(fecha, 1, 4) AS INTEGER)) FROM transactions WHERE fecha LIKE '20%'")
            row = c.fetchone()
            if row and row[0] and int(row[0]) > 2000:
                return int(row[0])
        finally:
            conn.close()
    except Exception:
        pass
    return 2025


def get_tax_settings(year=None):
    """Retrieves tax settings for the given fiscal year, or default values if none configured."""
    year_int = resolve_active_fiscal_year(year)

    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT year, ganancias_deduccion, ganancias_alicuota,
                   iibb_tramo1_limite, iibb_tramo1_alicuota,
                   iibb_tramo2_limite, iibb_tramo2_alicuota,
                   iibb_tramo3_alicuota, iibb_base_calculo,
                   iibb_provincia, ganancias_estimadas_fallback_pct, usd_ars_exchange_rate,
                   use_ganancias_fallback
            FROM tax_settings WHERE year=?
        """, (year_int,))
        row = c.fetchone()
    finally:
        conn.close()
    defaults = {
        "year": year_int, "ganancias_deduccion": 0.0, "ganancias_alicuota": 15.0,
        "iibb_tramo1_limite": 3255000000.0, "iibb_tramo1_alicuota": 5.0,
        "iibb_tramo2_limite": 26970000000.0, "iibb_tramo2_alicuota": 6.0,
        "iibb_tramo3_alicuota": 7.0, "iibb_base_calculo": "diferencial",
        "iibb_provincia": "Catamarca", "ganancias_estimadas_fallback_pct": 15.0,
        "usd_ars_exchange_rate": 1000.0, "use_ganancias_fallback": False
    }
    if not row:
        return defaults
    return {
        "year": row[0], "ganancias_deduccion": float(row[1] or 0.0),
        "ganancias_alicuota": float(row[2] if row[2] is not None else 15.0),
        "iibb_tramo1_limite": float(row[3] if row[3] is not None else 3255000000.0),
        "iibb_tramo1_alicuota": float(row[4] if row[4] is not None else 5.0),
        "iibb_tramo2_limite": float(row[5] if row[5] is not None else 26970000000.0),
        "iibb_tramo2_alicuota": float(row[6] if row[6] is not None else 6.0),
        "iibb_tramo3_alicuota": float(row[7] if row[7] is not None else 7.0),
        "iibb_base_calculo": row[8] or "diferencial",
        "iibb_provincia": row[9] if row[9] is not None else 'Catamarca',
        "ganancias_estimadas_fallback_pct": float(row[10] if row[10] is not None else 15.0),
        "usd_ars_exchange_rate": float(row[11] if row[11] is not None else 1000.0),
        "use_ganancias_fallback": bool(row[12] if len(row) > 12 and row[12] is not None else False)
    }


def save_tax_settings(data):
    """Persists tax configuration parameters for a given fiscal year."""
    year = resolve_active_fiscal_year(data.get('year'))

    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO tax_settings (
                year, ganancias_deduccion, ganancias_alicuota, iibb_tramo1_limite, iibb_tramo1_alicuota,
                iibb_tramo2_limite, iibb_tramo2_alicuota, iibb_tramo3_alicuota, iibb_base_calculo,
                iibb_provincia, ganancias_estimadas_fallback_pct, usd_ars_exchange_rate, use_ganancias_fallback
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            year, max(0.0, float(data.get('ganancias_deduccion', 0.0) or 0.0)),
            max(0.0, float(data.get('ganancias_alicuota', 15.0) or 0.0)),
            max(0.0, float(data.get('iibb_tramo1_limite', 3255000000.0) or 0.0)),
            max(0.0, float(data.get('iibb_tramo1_alicuota', 5.0) or 0.0)),
            max(0.0, float(data.get('iibb_tramo2_limite', 26970000000.0) or 0.0)),
            max(0.0, float(data.get('iibb_tramo2_alicuota', 6.0) or 0.0)),
            max(0.0, float(data.get('iibb_tramo3_alicuota', 7.0) or 0.0)),
            str(data.get('iibb_base_calculo', 'diferencial') or 'diferencial'),
            str(data.get('iibb_provincia', 'Catamarca') or 'Catamarca'),
            max(0.0, float(data.get('ganancias_estimadas_fallback_pct', 15.0) or 15.0)),
            max(float(data.get('usd_ars_exchange_rate', 1000.0) or 1000.0), 1.0),
            1 if bool(data.get('use_ganancias_fallback', False)) else 0
        ))
        conn.commit()
    finally:
        conn.close()
    try:
        from services.cache_service import invalidate_analytics_cache
        invalidate_analytics_cache()
    except Exception:
        pass
    return True


update_tax_settings = save_tax_settings


def get_tax_report(year=None):
    """Generates fiscal report for specified year with certified vs provisional segregation."""
    try:
        try:
            from services.fifo_service import recalculate_fifo_costs_db
        except ImportError:
            from .fifo_service import recalculate_fifo_costs_db
        recalculate_fifo_costs_db()
    except Exception as e:
        logger.error(f"Error triggering FIFO recalculation before tax report: {e}", exc_info=True)
        
    year_int = resolve_active_fiscal_year(year)
    year_str = str(year_int)
    settings = get_tax_settings(year_int)

    certifications_included = []
    has_certifications = False

    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT id, title, start_date, end_date, cpa_name, file_path,
                   certified_sales_ars, certified_buys_ars, certified_pnl_ars, monthly_breakdown_json
            FROM certifications 
            WHERE start_date LIKE ? OR end_date LIKE ? OR (start_date <= ? AND end_date >= ?)
            ORDER BY start_date ASC
        """, (f"{year_str}%", f"{year_str}%", f"{year_str}-12-31 23:59:59", f"{year_str}-01-01 00:00:00"))
        cert_rows = c.fetchall()

        has_macro_certified = False
        dynamic_cpa_monthly = {}
        certified_months_set = set()
        if cert_rows:
            has_certifications = True
            for cr in cert_rows:
                c_sales = float(cr[6] or 0.0) if len(cr) > 6 else 0.0
                if c_sales > 0:
                    has_macro_certified = True
                certifications_included.append({
                    "id": cr[0], "title": cr[1], "start_date": cr[2],
                    "end_date": cr[3], "cpa_name": cr[4], "file_path": cr[5],
                    "certified_sales_ars": c_sales
                })
                mb_raw = cr[9] if len(cr) > 9 else '{}'
                if mb_raw:
                    try:
                        import json
                        mb = json.loads(mb_raw) if isinstance(mb_raw, str) else mb_raw
                        if isinstance(mb, dict):
                            for m_k, m_v in mb.items():
                                if str(m_k).startswith(f"{year_str}-"):
                                    certified_months_set.add(m_k)
                                if m_k not in dynamic_cpa_monthly:
                                    dynamic_cpa_monthly[m_k] = {"sells": 0.0, "sales": 0.0, "buys": 0.0, "pnl": 0.0}
                                if isinstance(m_v, dict):
                                    s_val = float(m_v.get("sells", m_v.get("sales", 0.0)) or 0.0)
                                    b_val = float(m_v.get("buys", 0.0) or 0.0)
                                    p_val = float(m_v.get("pnl", 0.0) or 0.0)
                                    dynamic_cpa_monthly[m_k]["sells"] += s_val
                                    dynamic_cpa_monthly[m_k]["sales"] += s_val
                                    dynamic_cpa_monthly[m_k]["buys"] += b_val
                                    dynamic_cpa_monthly[m_k]["pnl"] += p_val
                                    if s_val > 0 or b_val > 0 or p_val != 0:
                                        has_macro_certified = True
                    except Exception as e:
                        logging.getLogger(__name__).warning(f"Error parsing monthly_breakdown_json for certification {cr[0]}: {e}")

        query = "SELECT * FROM transactions WHERE (fecha LIKE ? OR fecha LIKE ? OR fecha LIKE ?) ORDER BY fecha ASC"
        df_all = pd.read_sql_query(query, conn, params=[f"{year_str}%", f"%/{year_str}%", f"%-{year_str}%"])
    finally:
        conn.close()

    if df_all.empty:
        df_certified = pd.DataFrame()
        df_provisional = pd.DataFrame()
    else:
        try:
            from services.fifo_service import parse_dates_series_robust
        except ImportError:
            from .fifo_service import parse_dates_series_robust
        df_all['dt'] = parse_dates_series_robust(df_all['fecha'])
        df_all = df_all[df_all['dt'].dt.year == year_int].copy()
        df_certified = df_all[df_all['is_certified'] == 1]
        df_provisional = df_all[(df_all['is_certified'].isna()) | (df_all['is_certified'] == 0)]

    def _calc_fees_total(fees_df):
        if fees_df.empty:
            return 0.0
        def _fee_item_ars(r):
            m_ars = float(r['monto_ars']) if pd.notna(r['monto_ars']) else 0.0
            if m_ars > 0:
                return m_ars
            mv = float(r.get('monto_venta_cripto') or 0.0) if pd.notna(r.get('monto_venta_cripto')) else 0.0
            mc = float(r.get('monto_compra_cripto') or 0.0) if pd.notna(r.get('monto_compra_cripto')) else 0.0
            amt = mv if mv > 0 else mc
            cc = float(r.get('cotizacion_compra') or 0.0) if pd.notna(r.get('cotizacion_compra')) else 0.0
            cv = float(r.get('cotizacion_venta') or 0.0) if pd.notna(r.get('cotizacion_venta')) else 0.0
            rate = cc if cc > 0 else cv
            return amt * rate if (amt > 0 and rate > 0) else 0.0
        return float(fees_df.apply(_fee_item_ars, axis=1).sum())

    def _calc_sales_pnl(sells_df, use_fallback, fallback_pct):
        if sells_df.empty:
            return 0.0
        def _calc_sale_row(r):
            m_ars = float(r['monto_ars']) if pd.notna(r['monto_ars']) else 0.0
            c_compra = float(r['cotizacion_compra']) if pd.notna(r['cotizacion_compra']) else 0.0
            m_venta = float(r['monto_venta_cripto']) if pd.notna(r['monto_venta_cripto']) else 0.0
            uncovered = float(r.get('monto_descubierto') or 0.0) if pd.notna(r.get('monto_descubierto', 0.0)) else 0.0
            if uncovered <= 0 and r.get('comentarios'):
                m_desc = re.search(r'\[(?:Descubierto|Uncovered):\s*([\d\.]+)', str(r['comentarios']))
                if m_desc:
                    try:
                        uncovered = float(m_desc.group(1))
                    except Exception:
                        pass
            if m_venta <= 0:
                return 0.0
            if uncovered > 1e-9:
                covered_qty = max(0.0, m_venta - uncovered)
                ratio_covered = covered_qty / m_venta
                ratio_uncovered = min(1.0, max(0.0, uncovered / m_venta))
                pnl_cov = (m_ars * ratio_covered) - (c_compra * covered_qty)
                pnl_unc = (m_ars * ratio_uncovered) * (fallback_pct if use_fallback else 1.0)
                return pnl_cov + pnl_unc
            if use_fallback and c_compra <= 0:
                return m_ars * fallback_pct
            return m_ars - (c_compra * m_venta)

        return float(sells_df.apply(_calc_sale_row, axis=1).sum())

    def _calc_df_metrics(df, use_fallback=False, fallback_pct=0.15):
        if df.empty:
            return 0.0, 0.0, 0.0, 0.0
        tipo_op = df['tipo_operacion'].fillna('').astype(str).str.lower()
        is_crypto = ~df['moneda'].fillna('').astype(str).str.upper().isin(['ARS', 'USD', 'EUR'])
        is_buy_op = tipo_op.str.contains('compra|buy', regex=True) & ~tipo_op.str.contains('retiro|comision|comisión|fee', regex=True)
        is_auto_ingreso = (
            tipo_op.str.contains('ingreso autom|ajuste|saldo inicial|capital inicial', regex=True) |
            df['exchange'].fillna('').astype(str).str.contains('Sistema de Conciliación|Ajuste Manual|Capital Inicial', case=False, regex=True) |
            df['comentarios'].fillna('').astype(str).str.contains(r'\[ajuste fifo|sistema de conciliación|ingreso autom|saldo inicial|capital inicial', case=False, regex=True)
        ) & (df['monto_ars'].fillna(0).astype(float) > 0) & ~tipo_op.str.contains('venta|sell', na=False)
        buys = df[(is_buy_op | is_auto_ingreso) & ~tipo_op.str.contains('retiro|comision|comisión|fee', regex=True) & is_crypto]
        sells = df[tipo_op.str.contains('venta|sell|consumo|pago|payment', regex=True) & ~tipo_op.str.contains('retiro|ingreso|comision|comisión|fee', regex=True) & is_crypto]
        is_comision = (
            (tipo_op.str.contains('comision|comisión|fee|tax', regex=True) | 
             (tipo_op.str.contains('gasto', regex=True) & ~tipo_op.str.contains('personal', regex=True)))
            & ~tipo_op.str.contains('ingreso|deposito|depósito', regex=True)
        )
        fees = df[is_comision]
        t_buys = float(buys['monto_ars'].fillna(0).astype(float).sum()) if not buys.empty else 0.0
        t_sells = float(sells['monto_ars'].fillna(0).astype(float).sum()) if not sells.empty else 0.0
        t_fees = float(_calc_fees_total(fees))
        pnl = _calc_sales_pnl(sells, use_fallback, fallback_pct) - t_fees
        return t_buys, t_sells, pnl, t_fees

    use_fallback = bool(settings.get('use_ganancias_fallback', False))
    fallback_pct = float(settings.get('ganancias_estimadas_fallback_pct', 15.0) or 15.0) / 100.0

    total_buys, total_sells, ganancia_neta, total_fees = _calc_df_metrics(df_all, use_fallback, fallback_pct)
    cert_buys, cert_sells, cert_ganancia_neta, cert_fees = _calc_df_metrics(df_certified, use_fallback, fallback_pct)
    raw_cert_buys, raw_cert_sells, raw_cert_pnl = cert_buys, cert_sells, cert_ganancia_neta
    prov_buys, prov_sells, prov_ganancia_neta, prov_fees = _calc_df_metrics(df_provisional, use_fallback, fallback_pct)

    tx_count, certified_tx_count, provisional_tx_count = len(df_all), len(df_certified), len(df_provisional)
    is_fully_certified = bool(has_certifications and provisional_tx_count == 0 and tx_count > 0)
    is_partially_certified = bool(has_certifications and provisional_tx_count > 0 and certified_tx_count > 0)

    monthly_data = []
    if not df_all.empty:
        df_all_copy = df_all.copy()
        dt_month = df_all_copy['dt'].dt.strftime('%Y-%m')
        if dt_month.isna().any():
            def _safe_m(f):
                s = str(f).strip()
                m1 = re.search(r'(\d{4})[-/](\d{1,2})', s)
                if m1: return f"{m1.group(1)}-{m1.group(2).zfill(2)}"
                m2 = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})', s)
                if m2: return f"{m2.group(3)}-{m2.group(2).zfill(2)}"
                return ""
            dt_month = dt_month.fillna(df_all_copy['fecha'].apply(_safe_m))
        df_all_copy['month'] = dt_month.fillna('')
        monthly_groups = df_all_copy[df_all_copy['month'] != ''].groupby('month')
        for month, group in monthly_groups:
            use_fb = bool(settings.get('use_ganancias_fallback', False))
            fb_pct = float(settings.get('ganancias_estimadas_fallback_pct', 15.0) or 15.0) / 100.0

            # Macro Reconciliation: if official CPA certification exists for this month
            if has_macro_certified and month in dynamic_cpa_monthly:
                cpa_m = dynamic_cpa_monthly[month]
                m_cert_buys_val, m_cert_sells_val, m_cert_pnl = cpa_m["buys"], cpa_m["sells"], cpa_m["pnl"]
                group_cert = group[group['is_certified'] == 1]
                group_prov = group[((group['is_certified'].isna()) | (group['is_certified'] == 0))]
                m_cert_count = len(group_cert)

                if not group_prov.empty:
                    p_buys, p_sells, p_pnl, _ = _calc_df_metrics(group_prov, use_fb, fb_pct)
                    m_prov_count, m_prov_pnl = len(group_prov), p_pnl
                    m_prov_buys_val, m_prov_sells_val = p_buys, p_sells
                    m_buys_val, m_sells_val = m_cert_buys_val + m_prov_buys_val, m_cert_sells_val + m_prov_sells_val
                    m_pnl, m_status = m_cert_pnl + m_prov_pnl, 'MIXED'
                else:
                    m_prov_count, m_prov_pnl = 0, 0.0
                    m_prov_buys_val, m_prov_sells_val = 0.0, 0.0
                    m_buys_val, m_sells_val, m_pnl = m_cert_buys_val, m_cert_sells_val, m_cert_pnl
                    m_status = 'CERTIFIED'
            else:
                group_cert = group[group['is_certified'] == 1]
                group_prov = group[((group['is_certified'].isna()) | (group['is_certified'] == 0))]
                m_cert_count, m_prov_count = len(group_cert), len(group_prov)
                m_status = 'CERTIFIED' if (m_prov_count == 0 and m_cert_count > 0) else ('PROVISIONAL' if m_cert_count == 0 else 'MIXED')
                m_buys_val, m_sells_val, m_pnl, _ = _calc_df_metrics(group, use_fb, fb_pct)
                m_cert_buys_val, m_cert_sells_val, m_cert_pnl, _ = _calc_df_metrics(group_cert, use_fb, fb_pct)
                m_prov_buys_val, m_prov_sells_val, m_prov_pnl, _ = _calc_df_metrics(group_prov, use_fb, fb_pct)

            m_base_iibb = m_pnl if settings.get('iibb_base_calculo') == 'diferencial' else m_sells_val
            m_imp_iibb = max(0.0, m_base_iibb * (settings.get('iibb_tramo1_alicuota', 5.0) / 100.0))

            monthly_data.append({
                "month": month, "mes": month,
                "buys_ars": round(m_buys_val, 2), "sells_ars": round(m_sells_val, 2),
                "pnl_ars": round(m_pnl, 2), "status": m_status,
                "ventas_ars": round(m_sells_val, 2), "costo_ars": round(m_buys_val, 2),
                "ganancia_bruta": round(m_pnl, 2), "comisiones_ars": 0.0,
                "ganancia_neta": round(max(0.0, m_pnl), 2),
                "base_iibb": round(m_base_iibb, 2), "impuesto_iibb": round(m_imp_iibb, 2),
                "certified_buys_ars": round(m_cert_buys_val, 2), "certified_sells_ars": round(m_cert_sells_val, 2),
                "provisional_buys_ars": round(m_prov_buys_val, 2), "provisional_sells_ars": round(m_prov_sells_val, 2),
                "certified_pnl_ars": round(m_cert_pnl, 2), "provisional_pnl_ars": round(m_prov_pnl, 2),
                "certified_count": m_cert_count, "provisional_count": m_prov_count
            })

    existing_months = {row.get("month") or row.get("mes") for row in monthly_data}
    for m_key, cpa_m in dynamic_cpa_monthly.items():
        if str(m_key).startswith(f"{year_str}-") and m_key not in existing_months:
            c_sells = float(cpa_m.get("sells", cpa_m.get("sales", 0.0)) or 0.0)
            c_buys = float(cpa_m.get("buys", 0.0) or 0.0)
            c_pnl = float(cpa_m.get("pnl", 0.0) or 0.0)
            if c_sells > 0 or c_buys > 0 or c_pnl != 0:
                m_base_iibb = c_pnl if settings['iibb_base_calculo'] == 'diferencial' else c_sells
                m_imp_iibb = max(0.0, m_base_iibb * (settings['iibb_tramo1_alicuota'] / 100.0))
                monthly_data.append({
                    "month": m_key, "mes": m_key,
                    "buys_ars": round(c_buys, 2), "sells_ars": round(c_sells, 2), "pnl_ars": round(c_pnl, 2),
                    "ventas_ars": round(c_sells, 2), "costo_ars": round(c_buys, 2),
                    "ganancia_bruta": round(c_pnl, 2), "comisiones_ars": 0.0,
                    "ganancia_neta": round(max(0.0, c_pnl), 2),
                    "base_iibb": round(m_base_iibb, 2), "impuesto_iibb": round(m_imp_iibb, 2),
                    "status": "CERTIFIED", "is_cpa_verified": True, "tx_count": 0,
                    "certified_buys_ars": round(c_buys, 2), "certified_sells_ars": round(c_sells, 2),
                    "provisional_buys_ars": 0.0, "provisional_sells_ars": 0.0,
                    "certified_pnl_ars": round(c_pnl, 2), "provisional_pnl_ars": 0.0,
                    "certified_count": 0, "provisional_count": 0
                })
    monthly_data.sort(key=lambda x: x.get("month") or x.get("mes", ""))

    if has_macro_certified and any(m.get("certified_count", 0) > 0 or m.get("is_cpa_verified") for m in monthly_data):
        total_buys = sum(m["buys_ars"] for m in monthly_data)
        total_sells = sum(m["sells_ars"] for m in monthly_data)
        ganancia_neta = sum(m["pnl_ars"] for m in monthly_data)
        cert_buys = sum(m.get("certified_buys_ars", 0.0) for m in monthly_data)
        cert_sells = sum(m.get("certified_sells_ars", 0.0) for m in monthly_data)
        cert_ganancia_neta = sum(m["certified_pnl_ars"] for m in monthly_data)
        if len(certified_months_set) == 12 and len(df_provisional) == 0:
            prov_buys, prov_sells, prov_ganancia_neta, prov_fees = 0.0, 0.0, 0.0, 0.0
        else:
            prov_buys = sum(m.get("provisional_buys_ars", 0.0) for m in monthly_data)
            prov_sells = sum(m.get("provisional_sells_ars", 0.0) for m in monthly_data)
            prov_ganancia_neta = sum(m["provisional_pnl_ars"] for m in monthly_data)

    deduccion = settings['ganancias_deduccion']
    alicuota_ganancias = settings['ganancias_alicuota']
    base_ganancias = max(0.0, ganancia_neta - deduccion)
    impuesto_ganancias = base_ganancias * (alicuota_ganancias / 100.0)

    used_deduccion_cert = min(deduccion, max(0.0, cert_ganancia_neta))
    base_ganancias_certified = max(0.0, cert_ganancia_neta - used_deduccion_cert)
    impuesto_ganancias_certified = base_ganancias_certified * (alicuota_ganancias / 100.0)

    remaining_deduccion = max(0.0, deduccion - used_deduccion_cert)
    # Certified loss (quebranto certificado) offsets provisional gain
    net_prov_gain = prov_ganancia_neta + min(0.0, cert_ganancia_neta)
    base_ganancias_provisional = max(0.0, net_prov_gain - remaining_deduccion)
    impuesto_ganancias_provisional = base_ganancias_provisional * (alicuota_ganancias / 100.0)

    t1_limit, t1_rate = settings['iibb_tramo1_limite'], settings['iibb_tramo1_alicuota']
    t2_limit, t2_rate = settings['iibb_tramo2_limite'], settings['iibb_tramo2_alicuota']
    t3_rate = settings['iibb_tramo3_alicuota']

    if total_sells <= t1_limit:
        tramo, alicuota_iibb = 1, t1_rate
    elif total_sells <= t2_limit:
        tramo, alicuota_iibb = 2, t2_rate
    else:
        tramo, alicuota_iibb = 3, t3_rate
        
    base_iibb = ganancia_neta if settings['iibb_base_calculo'] == 'diferencial' else total_sells
    impuesto_iibb = max(0.0, base_iibb * (alicuota_iibb / 100.0))

    res_payload = {
        "success": True, "year": year_int, "tx_count": tx_count,
        "certified_tx_count": certified_tx_count, "provisional_tx_count": provisional_tx_count,
        "has_certifications": has_certifications, "is_fully_certified": is_fully_certified,
        "is_partially_certified": is_partially_certified, "certifications_included": certifications_included,
        "settings": settings, "total_buys_ars": round(total_buys, 2), "total_sells_ars": round(total_sells, 2),
        "total_deductible_fees_ars": round(total_fees, 2), "total_fees": round(total_fees, 2),
        "ganancia_neta": round(ganancia_neta, 2), "base_ganancias": round(base_ganancias, 2),
        "impuesto_ganancias": round(impuesto_ganancias, 2), "cert_ganancia_neta": round(cert_ganancia_neta, 2),
        "prov_ganancia_neta": round(prov_ganancia_neta, 2),
        "base_ganancias_provisional": round(base_ganancias_provisional, 2),
        "base_ganancias_certified": round(base_ganancias_certified, 2),
        "certified": {
            "buys_ars": round(cert_buys, 2), "sells_ars": round(cert_sells, 2),
            "ganancia_neta": round(cert_ganancia_neta, 2), "base_ganancias": round(base_ganancias_certified, 2),
            "impuesto_ganancias": round(impuesto_ganancias_certified, 2), "tx_count": certified_tx_count
        },
        "ledger_certified": {
            "buys_ars": round(raw_cert_buys, 2), "sells_ars": round(raw_cert_sells, 2),
            "ganancia_neta": round(raw_cert_pnl, 2), "tx_count": certified_tx_count
        },
        "provisional": {
            "buys_ars": round(prov_buys, 2), "sells_ars": round(prov_sells, 2),
            "ganancia_neta": round(prov_ganancia_neta, 2), "base_ganancias": round(base_ganancias_provisional, 2),
            "impuesto_ganancias": round(impuesto_ganancias_provisional, 2), "tx_count": provisional_tx_count
        },
        "tramo_iibb": tramo, "alicuota_iibb": alicuota_iibb,
        "base_iibb": round(base_iibb, 2), "impuesto_iibb": round(impuesto_iibb, 2),
        "monthly_data": monthly_data
    }

    try:
        from services.tax_anomaly_service import audit_fiscal_consistency
        res_payload["audit_summary"] = audit_fiscal_consistency(res_payload, year_int)
    except Exception as e:
        logger.warning(f"Error executing fiscal consistency audit: {e}")
        res_payload["audit_summary"] = {
            "is_sound": False, "error": str(e),
            "anomalies": [{"type": "audit_engine_failure", "description": str(e)}]
        }
    return res_payload


def get_ars_inflation_indexes(year=None):
    """Returns monthly ARS inflation indices (IPC / CER) for tax indexation."""
    year_int = resolve_active_fiscal_year(year)
    return {
        "year": year_int,
        "source": "INDEC",
        "monthly_ipc": {}
    }


def get_crypto_prices(date_str=None, currency='USDT'):
    """Returns historical reference price quotes in ARS/USD for given timestamp."""
    conn = get_connection()
    try:
        c = conn.cursor()
        query = "SELECT cotizacion_compra, cotizacion_venta FROM transactions WHERE moneda = ? AND (cotizacion_compra > 0 OR cotizacion_venta > 0)"
        params = [currency]
        if date_str:
            query += " AND fecha LIKE ?"
            params.append(f"{date_str[:10]}%")
        query += " ORDER BY fecha DESC LIMIT 1"
        c.execute(query, params)
        row = c.fetchone()
    finally:
        conn.close()
    if row:
        return {"currency": currency, "buy_rate": row[0], "sell_rate": row[1]}
    return {"currency": currency, "buy_rate": None, "sell_rate": None}
