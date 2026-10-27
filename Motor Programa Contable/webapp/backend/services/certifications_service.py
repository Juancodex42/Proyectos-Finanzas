import json
import os
from datetime import datetime, date
import pandas as pd
from db.connection import get_connection
try:
    from models.cpa_seed_data import CPA_MONTHLY_MAP, AUTHENTIC_CERTIFICATIONS
except ImportError:
    from ..models.cpa_seed_data import CPA_MONTHLY_MAP, AUTHENTIC_CERTIFICATIONS


def _normalize_cert_boundary(dt_val, is_end=False):
    """Normalizes certification boundary date strings to standard 'YYYY-MM-DD HH:MM:SS'."""
    if not dt_val:
        return ""
    s = str(dt_val).strip().replace('T', ' ')
    if s.endswith('Z'):
        s = s[:-1]
    if '.' in s:
        s = s.split('.')[0]
    if len(s) == 10:
        s += " 23:59:59" if is_end else " 00:00:00"
    elif len(s) == 16:
        s += ":59" if is_end else ":00"
    elif len(s) > 19:
        s = s[:19]
    return s


def _parse_cert_datetime(raw):
    """Parse a datetime string from certification dates, returning a datetime object."""
    if not raw:
        return None
    s = str(raw).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(s[:len(fmt.replace('%Y','0000').replace('%m','00').replace('%d','00').replace('%H','00').replace('%M','00').replace('%S','00'))], fmt)
        except (ValueError, IndexError):
            continue
    return None


def sync_certified_transactions_status(conn=None):
    """Synchronizes is_certified and certification_id in transactions with active ranges in certifications."""
    should_close = conn is None
    if should_close:
        conn = get_connection()
    c = conn.cursor()
    try:
        # Reset all provisional / uncertified transactions first
        c.execute("UPDATE transactions SET is_certified = 0, certification_id = NULL WHERE source != 'CERTIFICATION' OR source IS NULL")
        certs = c.execute("SELECT id, start_date, end_date FROM certifications ORDER BY start_date ASC").fetchall()
        for idx in range(len(certs)):
            cert_id, s_date, e_date = certs[idx]
            if not s_date or not e_date:
                continue
            s_s, e_s = _normalize_cert_boundary(s_date, is_end=False), _normalize_cert_boundary(e_date, is_end=True)
            if idx + 1 < len(certs) and certs[idx + 1][1]:
                next_s = _normalize_cert_boundary(certs[idx + 1][1], is_end=False)
                if next_s and pd.to_datetime(s_s) < pd.to_datetime(next_s) <= pd.to_datetime(e_s):
                    e_s = (pd.to_datetime(next_s) - pd.Timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M:%S')
            # Protect all transactions (PDF, CSV, API) falling within this authentic certification window
            c.execute(
                "UPDATE transactions SET is_certified = 1, certification_id = ? WHERE fecha >= ? AND fecha <= ?",
                (cert_id, s_s, e_s)
            )
        # Any transaction explicitly tagged as source='CERTIFICATION' remains certified
        c.execute("UPDATE transactions SET is_certified = 1 WHERE source = 'CERTIFICATION'")
        conn.commit()
    except Exception as e:
        if should_close:
            try:
                conn.rollback()
            except Exception:
                pass
        print(f"[SYNC CERT STATUS] Error syncing certification status: {e}")
        if not should_close:
            raise
    finally:
        if should_close:
            conn.close()


def cleanup_and_deduplicate_certifications(conn=None, force=False):
    """Seeds authentic certifications if the table is empty (or force=True) and repairs macro metadata without deleting user certifications."""
    should_close = conn is None
    if should_close:
        conn = get_connection()
    c = conn.cursor()
    try:
        cert_count = c.execute("SELECT COUNT(*) FROM certifications").fetchone()[0]
        if force or cert_count == 0:
            if force:
                c.execute("DELETE FROM certifications")
            for cert in AUTHENTIC_CERTIFICATIONS:
                tpl_status = cert.get("reconciliation_status", "MATCH")
                tpl_s, tpl_b, tpl_p = cert.get("certified_sales_ars", 0.0), cert.get("certified_buys_ars", 0.0), cert.get("certified_pnl_ars", 0.0)
                c.execute(
                    "INSERT INTO certifications (id, title, start_date, end_date, issue_date, cpa_name, notes, file_path, certified_sales_ars, certified_buys_ars, certified_pnl_ars, reconciliation_status, monthly_breakdown_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (cert["id"], cert["title"], cert["start_date"], cert["end_date"], cert["issue_date"], cert["cpa_name"], cert["notes"], cert["file_path"], tpl_s, tpl_b, tpl_p, tpl_status, json.dumps(CPA_MONTHLY_MAP.get(cert["id"], {})))
                )
            print("[CLEANUP CERTS] Cleaned and restored authentic certifications with monthly breakdown.")
        elif cert_count > 0:
            c.execute("DELETE FROM certifications WHERE id NOT IN (SELECT MIN(id) FROM certifications GROUP BY start_date, end_date)")
            for cert in AUTHENTIC_CERTIFICATIONS:
                tpl_status = cert.get("reconciliation_status", "MATCH")
                tpl_s, tpl_b, tpl_p = cert.get("certified_sales_ars", 0.0), cert.get("certified_buys_ars", 0.0), cert.get("certified_pnl_ars", 0.0)
                mb_json = json.dumps(CPA_MONTHLY_MAP.get(cert["id"], {}))
                c.execute(
                    "UPDATE certifications SET cpa_name = COALESCE(NULLIF(cpa_name, ''), ?), "
                    "certified_sales_ars = CASE WHEN certified_sales_ars IS NULL OR certified_sales_ars = 0 THEN ? ELSE certified_sales_ars END, "
                    "certified_buys_ars = CASE WHEN certified_buys_ars IS NULL OR certified_buys_ars = 0 THEN ? ELSE certified_buys_ars END, "
                    "certified_pnl_ars = CASE WHEN certified_pnl_ars IS NULL OR certified_pnl_ars = 0 THEN ? ELSE certified_pnl_ars END, "
                    "reconciliation_status = ?, "
                    "monthly_breakdown_json = COALESCE(NULLIF(monthly_breakdown_json, '{}'), ?) "
                    "WHERE id = ? OR (SUBSTR(start_date, 1, 7) = SUBSTR(?, 1, 7) AND SUBSTR(end_date, 1, 7) = SUBSTR(?, 1, 7))",
                    (cert["cpa_name"], tpl_s, tpl_b, tpl_p, tpl_status, mb_json, cert["id"], cert["start_date"], cert["end_date"])
                )
        fix_corrupted_certifications(conn=conn)
        sync_certified_transactions_status(conn=conn)
        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"[CLEANUP CERTS] Error cleaning up certifications: {e}")
    finally:
        if should_close:
            conn.close()


def fix_corrupted_certifications(conn=None):
    """Sanitizes certification boundary date strings and fixes invalid boundaries where start_date > end_date."""
    should_close = conn is None
    if should_close:
        conn = get_connection()
    c = conn.cursor()
    try:
        for cert_id, title, s_date, e_date in c.execute("SELECT id, title, start_date, end_date FROM certifications").fetchall():
            s_raw = str(s_date).strip().split(' ')[0] if s_date else ""
            e_raw = str(e_date).strip().split(' ')[0] if e_date else ""
            swapped = False
            if s_raw and e_raw and s_raw > e_raw:
                s_raw, e_raw = e_raw, s_raw
                swapped = True
            s_norm = f"{s_raw} 00:00:00" if s_raw else _normalize_cert_boundary(s_date, is_end=False)
            e_norm = f"{e_raw} 23:59:59" if e_raw else _normalize_cert_boundary(e_date, is_end=True)
            s_disp, e_disp = (s_norm.split(' ')[0] if s_norm else ""), (e_norm.split(' ')[0] if e_norm else "")
            auto_title = f"Certificación Contable ({s_disp} al {e_disp})" if (s_disp and e_disp) else title
            title_str = str(title or "").strip()
            title_corrupted = (not title_str or "None" in title_str or swapped or (title_str.startswith("Certificación Contable (") and auto_title != title_str))
            new_title = auto_title if title_corrupted else title
            if s_norm != str(s_date) or e_norm != str(e_date) or title_corrupted:
                c.execute("UPDATE certifications SET start_date = ?, end_date = ?, title = ? WHERE id = ?", (s_norm, e_norm, new_title, cert_id))
                print(f"[REPAIR CERT] Sanitized ID {cert_id}: {s_norm} -> {e_norm}")
        conn.commit()
    except Exception as e:
        print(f"[REPAIR CERT] Error repairing certifications: {e}")
    finally:
        if should_close:
            conn.close()


def get_certifications():
    """Returns all registered certifications and overview status summary."""
    conn = get_connection()
    try:
        rows = conn.cursor().execute("SELECT id, title, start_date, end_date, issue_date, cpa_name, notes, file_path, created_at, certified_sales_ars, certified_buys_ars, certified_pnl_ars, reconciliation_status FROM certifications ORDER BY start_date ASC").fetchall()
    finally:
        conn.close()

    cert_list, latest_end, latest_end_str = [], None, None
    for r in rows:
        cert_list.append({
            "id": r[0], "title": r[1], "start_date": r[2], "end_date": r[3], "issue_date": r[4], "cpa_name": r[5],
            "notes": r[6], "file_path": r[7], "created_at": r[8],
            "certified_sales_ars": float(r[9] or 0.0) if len(r) > 9 else 0.0,
            "certified_buys_ars": float(r[10] or 0.0) if len(r) > 10 else 0.0,
            "certified_pnl_ars": float(r[11] or 0.0) if len(r) > 11 else 0.0,
            "reconciliation_status": r[12] if len(r) > 12 and r[12] else "MATCH"
        })
        if r[3]:
            raw_end = str(r[3]).strip()
            try:
                ed = datetime.strptime(raw_end.split(' ')[0], "%Y-%m-%d").date()
                if latest_end is None or ed >= latest_end:
                    latest_end, latest_end_str = ed, raw_end
            except Exception:
                pass

    today = date.today()
    if latest_end is None:
        status, uncertified_days, latest_end_str = "pending", None, None
    elif latest_end >= today:
        status, uncertified_days = "up_to_date", 0
    else:
        status, uncertified_days = "pending", (today - latest_end).days
    return {
        "certifications": cert_list,
        "summary": {"total_count": len(cert_list), "status": status, "latest_end_date": latest_end_str, "uncertified_days": uncertified_days, "today": today.strftime("%Y-%m-%d")}
    }


def get_last_certification_end_datetime():
    """Returns exact end_date (datetime object) of most recent certification or None."""
    conn = get_connection()
    try:
        row = conn.cursor().execute("SELECT end_date FROM certifications ORDER BY end_date DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    return _parse_cert_datetime(row[0]) if row and row[0] else None


def add_certification(title, start_date, end_date, issue_date=None, cpa_name=None, notes=None, file_path=None, sync_status=True):
    """Adds or updates a CPA certification period and syncs transaction statuses."""
    current_time = datetime.now().strftime('%H:%M:%S')
    start_date = _normalize_cert_boundary(start_date, is_end=False) if start_date else start_date
    end_date = _normalize_cert_boundary(end_date, is_end=True) if end_date else end_date
    if issue_date and len(str(issue_date).strip()) == 10:
        issue_date = str(issue_date).strip() + " " + current_time
    elif not issue_date:
        issue_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_connection()
    try:
        c = conn.cursor()
        if file_path:
            row = c.execute("SELECT id FROM certifications WHERE file_path LIKE ? OR (start_date = ? AND end_date = ?)", (f"%{os.path.basename(file_path)}%", start_date, end_date)).fetchone()
        else:
            row = c.execute("SELECT id FROM certifications WHERE start_date = ? AND end_date = ?", (start_date, end_date)).fetchone()
        existing_id = row[0] if row else None
        if existing_id:
            c.execute("UPDATE certifications SET title = ?, start_date = ?, end_date = ?, issue_date = ?, cpa_name = ?, notes = ?, file_path = COALESCE(?, file_path) WHERE id = ?", (title, start_date, end_date, issue_date, cpa_name, notes, file_path, existing_id))
            cert_id = existing_id
            print(f"[ADD CERT] Updated existing certification ID {cert_id}")
        else:
            c.execute("INSERT INTO certifications (title, start_date, end_date, issue_date, cpa_name, notes, file_path) VALUES (?, ?, ?, ?, ?, ?, ?)", (title, start_date, end_date, issue_date, cpa_name, notes, file_path))
            cert_id = c.lastrowid
            print(f"[ADD CERT] Inserted new certification ID {cert_id}")
        conn.commit()
        try:
            fix_corrupted_certifications(conn=conn)
            if sync_status:
                sync_certified_transactions_status(conn=conn)
            conn.commit()
        except Exception as e:
            print(f"[ADD CERT] Error syncing: {e}")
    finally:
        conn.close()
    try:
        from services.cache_service import invalidate_analytics_cache
        invalidate_analytics_cache()
    except Exception:
        pass
    return cert_id


def get_certification_by_id(cert_id):
    """Retrieves single certification record by ID."""
    conn = get_connection()
    try:
        r = conn.cursor().execute("SELECT id, title, start_date, end_date, issue_date, cpa_name, notes, file_path, created_at FROM certifications WHERE id = ?", (cert_id,)).fetchone()
    finally:
        conn.close()
    return {"id": r[0], "title": r[1], "start_date": r[2], "end_date": r[3], "issue_date": r[4], "cpa_name": r[5], "notes": r[6], "file_path": r[7], "created_at": r[8]} if r else None

def delete_certification(cert_id):
    """Deletes certification record by ID and synchronizes transaction statuses."""
    conn = get_connection()
    try:
        c = conn.cursor()
        row = c.execute("SELECT start_date, end_date FROM certifications WHERE id = ?", (cert_id,)).fetchone()
        s_s = _normalize_cert_boundary(row[0], is_end=False) if row and row[0] else "9999-99-99"
        e_s = _normalize_cert_boundary(row[1], is_end=True) if row and row[1] else "0000-00-00"
        c.execute(
            "UPDATE transactions SET is_certified = 0, certification_id = NULL, source = CASE WHEN source = 'CERTIFICATION' THEN 'MANUAL_RESTORED' ELSE source END WHERE certification_id = ? OR (source = 'CERTIFICATION' AND fecha >= ? AND fecha <= ?)",
            (cert_id, s_s, e_s)
        )
        c.execute("DELETE FROM certifications WHERE id = ?", (cert_id,))
        conn.commit()
    finally:
        conn.close()
    try:
        sync_certified_transactions_status()
    except Exception as e:
        print(f"[DELETE CERT] Error syncing after delete: {e}")
    try:
        from services.cache_service import invalidate_analytics_cache
        invalidate_analytics_cache()
    except Exception:
        pass
    return True

def get_last_cpa_name():
    """Returns the most recently recorded accountant name from previous certifications."""
    conn = get_connection()
    try:
        row = conn.cursor().execute("SELECT cpa_name FROM certifications WHERE cpa_name IS NOT NULL AND cpa_name != '' ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    return row[0] if row else None

def count_provisional_transactions_in_range(start_date, end_date):
    """Counts provisional/uncertified transactions that fall within [start_date, end_date]."""
    s_s, e_s = _normalize_cert_boundary(start_date, is_end=False), _normalize_cert_boundary(end_date, is_end=True)
    conn = get_connection()
    try:
        return conn.cursor().execute("SELECT COUNT(*) FROM transactions WHERE fecha >= ? AND fecha <= ? AND (source != 'CERTIFICATION' OR source IS NULL)", (s_s, e_s)).fetchone()[0]
    finally:
        conn.close()

def apply_certified_period_replacement(cert_id, start_date, end_date, certified_txs):
    """Atomically purges provisional transactions in [start_date, end_date] and inserts canonical certified transactions."""
    s_s, e_s = _normalize_cert_boundary(start_date, is_end=False), _normalize_cert_boundary(end_date, is_end=True)
    conn = get_connection()
    c = conn.cursor()
    try:
        if certified_txs is None or not isinstance(certified_txs, (list, tuple)):
            raise ValueError("certified_txs must be a list of transaction dicts")
        if not certified_txs:
            return {"success": False, "error": "No se recibieron transacciones certificadas para reemplazar el período."}
        purged_count = c.execute("SELECT COUNT(*) FROM transactions WHERE fecha >= ? AND fecha <= ? AND (source != 'CERTIFICATION' OR source IS NULL)", (s_s, e_s)).fetchone()[0]
        c.execute("DELETE FROM transactions WHERE fecha >= ? AND fecha <= ? AND (source != 'CERTIFICATION' OR source IS NULL)", (s_s, e_s))
        c.execute("DELETE FROM transactions WHERE (certification_id = ? OR (source = 'CERTIFICATION' AND fecha >= ? AND fecha <= ?))", (cert_id, s_s, e_s))

        from services.transactions_service import insert_transactions
        inserted_count, _ = insert_transactions(certified_txs, source="CERTIFICATION", trigger_fifo_recalc=False, external_conn=conn)
        c.execute(
            "UPDATE transactions SET is_certified = 1, certification_id = ?, source = 'CERTIFICATION', requires_cost_audit = 0 WHERE fecha >= ? AND fecha <= ? AND (source = 'CERTIFICATION' OR comentarios LIKE '%[CERTIFICADO%')",
            (cert_id, s_s, e_s)
        )
        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"[REPLACE CERT ERROR] Failed transaction replacement: {e}")
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

    warning = None
    try:
        from services.fifo_service import recalculate_fifo_costs_db
        fifo_res = recalculate_fifo_costs_db()
        if isinstance(fifo_res, dict) and fifo_res.get("success") is False:
            warning = "FIFO recalculation failed"
        sync_certified_transactions_status()
        from services.cache_service import invalidate_analytics_cache
        invalidate_analytics_cache()
    except Exception as e:
        warning = "FIFO recalculation failed"
        print(f"[REPLACE CERT] Notice: post-sync cleanup: {e}")
    res = {"success": True, "purged_count": purged_count, "inserted_count": inserted_count}
    if warning:
        res["warning"] = warning
    return res

replace_certified_period_transactions = apply_certified_period_replacement
replace_period_with_certified_data = apply_certified_period_replacement
replace_period_with_certified_batches = apply_certified_period_replacement
