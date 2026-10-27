"""
Safe Database Cleanup Script for Contaminated Auxiliary Records.
Removes spurious ARS rows from Binance P2P injected by historical misclassification of Ripio Trade.
Safely creates a physical backup before any modification and validates atomic invariants.
"""

import os
import sys
import shutil
import sqlite3
import datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(REPO_ROOT, "webapp", "backend")
COMPAT_DIR = os.path.join(BACKEND_DIR, "compat")
for _p in (COMPAT_DIR, BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)
DB_PATH = os.path.join(BACKEND_DIR, "transactions.db")
BACKUP_DIR = os.path.join(REPO_ROOT, "docs", "archive", "backups")


def cleanup_contaminated_auxiliary_records():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found at {DB_PATH}")

    # 1. Physical Snapshot Backup
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"transactions_backup_pre_purge_{timestamp}.db"
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    shutil.copy2(DB_PATH, backup_path)
    print(f"[BACKUP] Backup físico creado exitosamente en: {backup_path}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Pre-audit validation
        cursor.execute("SELECT COUNT(1) FROM transactions WHERE is_certified = 1")
        initial_certified_count = cursor.fetchone()[0]
        if initial_certified_count != 4290:
            raise ValueError(f"Aborting: Expected 4290 certified records, found {initial_certified_count}")

        cursor.execute("SELECT COUNT(1) FROM transactions WHERE is_certified = 0 AND exchange = 'Binance P2P' AND moneda = 'ARS'")
        target_rows_count = cursor.fetchone()[0]
        print(f"[AUDIT] Registros espurios identificados para eliminación: {target_rows_count}")
        if target_rows_count != 1461:
            print(f"[WARNING] Filas espurias difieren de 1461 (encontradas: {target_rows_count})")

        # Atomic Deletion
        cursor.execute("BEGIN TRANSACTION")
        cursor.execute("""
            DELETE FROM transactions
            WHERE is_certified = 0
              AND exchange = 'Binance P2P'
              AND moneda = 'ARS'
        """)
        deleted_count = cursor.rowcount
        print(f"[PURGE] Registros eliminados en transacción: {deleted_count}")

        # Post-audit validation
        cursor.execute("SELECT COUNT(1) FROM transactions WHERE is_certified = 1")
        post_certified_count = cursor.fetchone()[0]
        if post_certified_count != 4290:
            conn.rollback()
            raise RuntimeError(f"INTEGRITY VIOLATION: Certified transactions modified! Rollback executed.")

        cursor.execute("SELECT COUNT(1) FROM transactions WHERE is_certified = 0 AND exchange = 'Binance P2P' AND moneda = 'ARS'")
        remaining_spurious = cursor.fetchone()[0]
        if remaining_spurious != 0:
            conn.rollback()
            raise RuntimeError("INTEGRITY VIOLATION: Spurious records still remain after delete! Rollback executed.")

        cursor.execute("SELECT COUNT(1) FROM transactions")
        total_remaining = cursor.fetchone()[0]
        print(f"[AUDIT] Total de transacciones restantes en base de datos: {total_remaining}")

        conn.commit()
        print("[SUCCESS] Purga ejecutada y confirmada (COMMIT) con éxito absoluto.")
        return {
            'backup_path': backup_path,
            'deleted_count': deleted_count,
            'certified_preserved': post_certified_count,
            'total_remaining': total_remaining
        }

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Error durante la purga: {e}. Se ejecutó ROLLBACK.")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    cleanup_contaminated_auxiliary_records()
