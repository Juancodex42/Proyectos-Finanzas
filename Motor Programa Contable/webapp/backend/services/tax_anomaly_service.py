"""
Tax Anomaly Service (Sentinel)
Audits tax report results for financial invariants, profit margins,
crypto price bounds, and macro certified accounting discrepancies.
"""

from typing import Dict, Any, List
import sqlite3
from db.connection import get_connection


def audit_fiscal_consistency(report: Dict[str, Any], year: int) -> Dict[str, Any]:
    """
    Performs comprehensive sanity checks on a generated tax report for a given fiscal year.
    Returns:
        {
            "is_sound": bool,
            "anomalies": List[Dict[str, Any]],
            "macro_reconciliation": Dict[str, Any]
        }
    """
    anomalies: List[Dict[str, Any]] = []
    
    ventas = float(report.get("total_sells_ars") or report.get("total_ventas") or 0.0)
    compras = float(report.get("total_buys_ars") or report.get("total_compras") or 0.0)
    ganancia_neta = float(report.get("ganancia_neta") or report.get("pnl_ars") or 0.0)
    
    # 1. Arbitrage Margin Guard
    if ventas > 100_000.0:
        margin_pct = (ganancia_neta / ventas) * 100.0
        is_hodl = bool(report.get("is_hodl") or report.get("profile") == "hodl" or report.get("investor_profile") == "hodl")
        # In P2P crypto arbitrage, margin is strictly between 0.1% and 4.0%
        if margin_pct > 12.0:
            severity = "WARNING" if is_hodl else "CRITICAL"
            anomalies.append({
                "code": "EXCESSIVE_PROFIT_MARGIN",
                "severity": severity,
                "message": (
                    f"El margen de ganancia calculado ({margin_pct:.2f}%) excede el rango maximo "
                    f"esperado para arbitraje P2P (0.2% - 4.0%). "
                    + ("Apreciación de capital normal para inversor HODL / largo plazo." if is_hodl else "Posible quiebre de stock o costos en $0. Nota: Si la cuenta opera como inversor de mediano/largo plazo (HODL), márgenes elevados son normales por apreciación de capital.")
                ),
                "margin_pct": round(margin_pct, 2)
            })
        elif margin_pct < -8.0:
            anomalies.append({
                "code": "EXCESSIVE_NEGATIVE_MARGIN",
                "severity": "CRITICAL",
                "message": (
                    f"La perdida calculada ({margin_pct:.2f}%) supera la tolerancia financiera "
                    f"de la actividad. Posible valor numerico corrupto en compras o FIFO desbalanceado."
                ),
                "margin_pct": round(margin_pct, 2)
            })
            
    # 2. Check reconciliation against CPA Certified Totals in DB
    cert_block = report.get("ledger_certified") or report.get("certified") or {}
    if (report.get("is_partially_certified") or not report.get("is_fully_certified", True)) and cert_block:
        c_ventas = float(cert_block.get("total_sells_ars") or cert_block.get("sells_ars") or 0.0)
        c_compras = float(cert_block.get("total_buys_ars") or cert_block.get("buys_ars") or 0.0)
        c_ganancia = float(cert_block.get("ganancia_neta") or cert_block.get("pnl_ars") or 0.0)
        if c_ventas > 0 or c_ganancia != 0:
            recon_ventas, recon_compras, recon_ganancia = c_ventas, c_compras, c_ganancia
        else:
            recon_ventas, recon_compras, recon_ganancia = ventas, compras, ganancia_neta
    else:
        recon_ventas, recon_compras, recon_ganancia = ventas, compras, ganancia_neta

    reconciliation = check_macro_reconciliation(year, recon_ventas, recon_compras, recon_ganancia)
    if reconciliation.get("has_certification"):
        status = reconciliation.get("status")
        if status == "DISCREPANCY":
            anomalies.append({
                "code": "CPA_MACRO_DISCREPANCY",
                "severity": "HIGH",
                "message": (
                    f"Discrepancia detectada con las Certificaciones Oficiales del C.P.N. para el ano {year}. "
                    f"Ganancia calculada: ${recon_ganancia:,.2f} vs Ganancia Certificada: ${reconciliation['certified_pnl']:,.2f} "
                    f"(Diferencia: ${reconciliation['delta_pnl']:,.2f})."
                ),
                "details": reconciliation
            })
        if reconciliation.get("missing_certified_months"):
            missing_m = reconciliation["missing_certified_months"]
            anomalies.append({
                "code": "UNMATCHED_CERTIFIED_MONTHS",
                "severity": "WARNING",
                "message": (
                    f"Se detectaron {len(missing_m)} meses con certificaciones notariales pero sin transacciones cargadas "
                    f"en el sistema ({', '.join(missing_m)}). Si hubo actividad en esos meses, importe los extractos correspondientes."
                ),
                "missing_months": missing_m
            })
            
    # 3. Database Outlier Price Scanner
    outliers = detect_database_outliers(year)
    if outliers:
        anomalies.append({
            "code": "PRICE_OR_QUANTITY_OUTLIERS",
            "severity": "MEDIUM",
            "message": f"Se detectaron {len(outliers)} transacciones con cotizaciones o cantidades fuera de banda.",
            "sample_outliers": outliers[:5]
        })

    # 4. Check for transactions requiring acquisition cost audit
    conn = None
    c = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM transactions WHERE (fecha LIKE ? OR fecha LIKE ?) AND requires_cost_audit = 1", (f"{year}%", f"%/{year}%"))
        row = c.fetchone()
        audit_count = (row[0] or 0) if row else 0
        if audit_count > 0:
            anomalies.append({
                "code": "REQUIRES_COST_AUDIT",
                "severity": "WARNING",
                "message": f"Se detectaron {audit_count} transacciones que requieren auditoría de costo de adquisición para el año {year}.",
                "count": audit_count
            })
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Error checking transactions requiring cost audit: {e}")
    finally:
        if c:
            try:
                c.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    is_sound = not any(a["severity"] in ("CRITICAL", "HIGH") for a in anomalies)
    
    return {
        "is_sound": is_sound,
        "anomalies": anomalies,
        "macro_reconciliation": reconciliation
    }


def check_macro_reconciliation(year: int, ventas: float, compras: float, ganancia_neta: float) -> Dict[str, Any]:
    """
    Compares computed numbers for a year against all CPA certifications covering that year.
    Accurately attributes multi-year certifications to prevent double-counting.
    """
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT id, title, start_date, end_date, certified_sales_ars, certified_buys_ars, certified_pnl_ars, monthly_breakdown_json
            FROM certifications
            WHERE start_date <= ? AND end_date >= ?
        """, (f"{year}-12-31 23:59:59", f"{year}-01-01 00:00:00"))
        certs = c.fetchall()
        c.close()
    finally:
        conn.close()
    
    if not certs:
        return {"has_certification": False, "status": "NO_CERTIFICATION"}
        
    import json
    tot_cert_sales = 0.0
    tot_cert_buys = 0.0
    tot_cert_pnl = 0.0
    missing_certified_months = []
    
    for r in certs:
        c_start, c_end = str(r[2]), str(r[3])
        sales_val = float(r[4] or 0.0)
        buys_val = float(r[5] or 0.0)
        pnl_val = float(r[6] or 0.0)
        breakdown_str = r[7] if len(r) > 7 else None
        
        # If the certification is entirely contained within the target year:
        if c_start.startswith(str(year)) and c_end.startswith(str(year)):
            tot_cert_sales += sales_val
            tot_cert_buys += buys_val
            tot_cert_pnl += pnl_val
        else:
            # Overlapping multi-year certification: check monthly breakdown
            parsed_mb = {}
            if breakdown_str:
                try:
                    parsed_mb = json.loads(breakdown_str)
                except Exception:
                    parsed_mb = {}
            
            year_prefix = f"{year}-"
            matching_months = {k: v for k, v in parsed_mb.items() if str(k).startswith(year_prefix)}
            if matching_months:
                chk_conn = get_connection()
                try:
                    chk_c = chk_conn.cursor()
                    for m_k, m_v in matching_months.items():
                        m_parts = m_k.split('-')
                        m_year, m_mon = m_parts[0], m_parts[1]
                        try:
                            chk_c.execute(
                                "SELECT COUNT(*) FROM transactions WHERE (fecha LIKE ? OR fecha LIKE ?) "
                                "AND (monto_venta_cripto > 0 OR monto_compra_cripto > 0) "
                                "AND (COALESCE(monto_ars, 0) > 0 OR LOWER(COALESCE(tipo_operacion, '')) LIKE '%compra%' "
                                "OR LOWER(COALESCE(tipo_operacion, '')) LIKE '%venta%' OR LOWER(COALESCE(tipo_operacion, '')) LIKE '%buy%' "
                                "OR LOWER(COALESCE(tipo_operacion, '')) LIKE '%sell%' OR LOWER(COALESCE(tipo_operacion, '')) LIKE '%canje%' "
                                "OR LOWER(COALESCE(tipo_operacion, '')) LIKE '%swap%')",
                                (f"{m_k}%", f"%/{m_mon}/{m_year}%")
                            )
                        except sqlite3.OperationalError:
                            chk_c.execute(
                                "SELECT COUNT(*) FROM transactions WHERE (fecha LIKE ? OR fecha LIKE ?) AND (monto_venta_cripto > 0 OR monto_compra_cripto > 0)",
                                (f"{m_k}%", f"%/{m_mon}/{m_year}%")
                            )
                        count_tx = chk_c.fetchone()[0] or 0
                        if count_tx > 0:
                            tot_cert_sales += float(m_v.get("sells", m_v.get("sales", 0.0)) or 0.0)
                            tot_cert_buys += float(m_v.get("buys", 0.0))
                            tot_cert_pnl += float(m_v.get("pnl", 0.0))
                        else:
                            missing_certified_months.append(m_k)
                    chk_c.close()
                finally:
                    chk_conn.close()
            else:
                from datetime import datetime as dt
                try:
                    d_start = dt.strptime(c_start[:10], "%Y-%m-%d")
                    d_end = dt.strptime(c_end[:10], "%Y-%m-%d")
                    total_days = max(1, (d_end - d_start).days + 1)
                    
                    overlap_start = max(d_start, dt(year, 1, 1))
                    overlap_end = min(d_end, dt(year, 12, 31))
                    overlap_days = max(0, (overlap_end - overlap_start).days + 1)
                    
                    chk_conn = get_connection()
                    try:
                        chk_c = chk_conn.cursor()
                        try:
                            chk_c.execute(
                                "SELECT COUNT(*) FROM transactions WHERE fecha >= ? AND fecha <= ? "
                                "AND (monto_venta_cripto > 0 OR monto_compra_cripto > 0) "
                                "AND (COALESCE(monto_ars, 0) > 0 OR LOWER(COALESCE(tipo_operacion, '')) LIKE '%compra%' "
                                "OR LOWER(COALESCE(tipo_operacion, '')) LIKE '%venta%' OR LOWER(COALESCE(tipo_operacion, '')) LIKE '%buy%' "
                                "OR LOWER(COALESCE(tipo_operacion, '')) LIKE '%sell%' OR LOWER(COALESCE(tipo_operacion, '')) LIKE '%canje%' "
                                "OR LOWER(COALESCE(tipo_operacion, '')) LIKE '%swap%')",
                                (overlap_start.strftime("%Y-%m-%d 00:00:00"), overlap_end.strftime("%Y-%m-%d 23:59:59"))
                            )
                        except sqlite3.OperationalError:
                            chk_c.execute(
                                "SELECT COUNT(*) FROM transactions WHERE fecha >= ? AND fecha <= ? AND (monto_venta_cripto > 0 OR monto_compra_cripto > 0)",
                                (overlap_start.strftime("%Y-%m-%d 00:00:00"), overlap_end.strftime("%Y-%m-%d 23:59:59"))
                            )
                        count_tx = chk_c.fetchone()[0] or 0
                        chk_c.close()
                    finally:
                        chk_conn.close()
                    if count_tx > 0:
                        ratio = overlap_days / total_days
                        tot_cert_sales += sales_val * ratio
                        tot_cert_buys += buys_val * ratio
                        tot_cert_pnl += pnl_val * ratio
                    elif overlap_days > 0:
                        missing_certified_months.append(f"{overlap_start.strftime('%Y-%m')}..{overlap_end.strftime('%Y-%m')}")
                except Exception:
                    tot_cert_sales += sales_val
                    tot_cert_buys += buys_val
                    tot_cert_pnl += pnl_val
    
    delta_sales = abs(ventas - tot_cert_sales)
    delta_pnl = abs(ganancia_neta - tot_cert_pnl)
    
    pct_diff = (delta_pnl / abs(tot_cert_pnl) * 100.0) if abs(tot_cert_pnl) > 1e-6 else 0.0
    status = "MATCH" if pct_diff <= 3.0 else "DISCREPANCY"
    
    res = {
        "has_certification": True,
        "status": status,
        "certified_sales": tot_cert_sales,
        "certified_buys": tot_cert_buys,
        "certified_pnl": tot_cert_pnl,
        "delta_sales": delta_sales,
        "delta_pnl": delta_pnl,
        "pct_diff": round(pct_diff, 2),
        "certifications_count": len(certs)
    }
    if missing_certified_months:
        res["missing_certified_months"] = missing_certified_months
    return res


def detect_database_outliers(year: int) -> List[Dict[str, Any]]:
    """Detects rows where USDT price or BTC price is outside plausible market reality."""
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT tx_hash, fecha, moneda, tipo_operacion, cotizacion_compra, cotizacion_venta, monto_ars
            FROM transactions
            WHERE (fecha LIKE ? OR fecha LIKE ?) AND (
                (
                    (monto_compra_cripto > 0 OR LOWER(tipo_operacion) LIKE '%compra%' OR LOWER(tipo_operacion) LIKE '%buy%') AND (
                        (moneda = 'USDT' AND ((cotizacion_compra > 0 AND (cotizacion_compra > 4000.0 OR cotizacion_compra < 20.0)) OR (cotizacion_compra <= 0 AND monto_ars > 0))) OR
                        (moneda = 'BTC' AND ((cotizacion_compra > 0 AND cotizacion_compra < 500000.0) OR (cotizacion_compra <= 0 AND monto_ars > 0)))
                    )
                ) OR (
                    (monto_venta_cripto > 0 OR LOWER(tipo_operacion) LIKE '%venta%' OR LOWER(tipo_operacion) LIKE '%sell%') AND (
                        (moneda = 'USDT' AND ((cotizacion_venta > 0 AND (cotizacion_venta > 4000.0 OR cotizacion_venta < 20.0)) OR (cotizacion_venta <= 0 AND monto_ars > 0))) OR
                        (moneda = 'BTC' AND ((cotizacion_venta > 0 AND cotizacion_venta < 500000.0) OR (cotizacion_venta <= 0 AND monto_ars > 0)))
                    )
                )
            )
            LIMIT 10
        """, (f"{year}%", f"%/{year}%"))
        rows = c.fetchall()
        c.close()
    finally:
        conn.close()
    
    return [
        {
            "tx_hash": r[0], "fecha": r[1], "moneda": r[2], "tipo": r[3],
            "c_compra": r[4], "c_venta": r[5], "monto_ars": r[6]
        } for r in rows
    ]
