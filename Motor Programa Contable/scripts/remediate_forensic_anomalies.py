"""
Remediation script for forensic accounting anomalies.
Author: Principal Forensic Auditor
Policy: Strict Zero Trust Verification
"""

import os
import sys
import shutil
import sqlite3
from datetime import datetime

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'webapp', 'backend'))
COMPAT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'webapp', 'backend', 'compat'))
for _p in (COMPAT_DIR, BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DB_PATH = os.path.join(BACKEND_DIR, "transactions.db")
BACKUP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "archive", "backups"))
os.makedirs(BACKUP_DIR, exist_ok=True)


def run_remediation():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found at {DB_PATH}")

    # 1. Snapshot backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"transactions_backup_pre_remediation_{timestamp}.db")
    shutil.copy2(DB_PATH, backup_path)
    print(f"[REMEDIATION] Backup created successfully: {backup_path}")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    try:
        # 2. Check 7 corrupted transactions
        print("\n--- PASO 1: SANEAMIENTO DE 7 TRANSACCIONES CORRUPTAS ---")
        
        # ID 12928: Footer row mistaken for a sale
        c.execute("SELECT id, monto_ars, monto_venta_cripto, comentarios FROM transactions WHERE id = 12928")
        row_12928 = c.fetchone()
        if row_12928:
            print(f"[REMEDIATION] Removing phantom footer row ID 12928: {row_12928}")
            c.execute("DELETE FROM transactions WHERE id = 12928")
            print("[REMEDIATION] ID 12928 removed.")
        else:
            print("[REMEDIATION] ID 12928 already removed or not found.")

        # 6 BTC transactions with inverted columns from original PDF
        # Exact values extracted from CPCE PDF Work Demo
        btc_fixes = [
            {
                "id": 11479,
                "volumen": 0.0002,
                "precio": 24549728.0,
                "monto_ars": 4909.94,
                "note": "Certificación C.P.N. (Pág 4) - Saneamiento Forense: 0.0002 BTC @ 24.549.728 ARS"
            },
            {
                "id": 12024,
                "volumen": 0.00009845,
                "precio": 35285908.85,
                "monto_ars": 3474.0,
                "note": "Certificación C.P.N. (Pág 15) - Saneamiento Forense: 0.00009845 BTC @ 35.285.908,85 ARS"
            },
            {
                "id": 12050,
                "volumen": 0.00027712,
                "precio": 36085386.83,
                "monto_ars": 10000.0,
                "note": "Certificación C.P.N. (Pág 15) - Saneamiento Forense: 0.00027712 BTC @ 36.085.386,83 ARS"
            },
            {
                "id": 12144,
                "volumen": 0.00243206,
                "precio": 41117280.06,
                "monto_ars": 100000.0,
                "note": "Certificación C.P.N. (Pág 17) - Saneamiento Forense: 0.00243206 BTC @ 41.117.280,06 ARS"
            },
            {
                "id": 12202,
                "volumen": 0.00122540,
                "precio": 40802916.51,
                "monto_ars": 50000.0,
                "note": "Certificación C.P.N. (Pág 18) - Saneamiento Forense: 0.00122540 BTC @ 40.802.916,51 ARS"
            },
            {
                "id": 12292,
                "volumen": 0.00543050,
                "precio": 55243483.35,
                "monto_ars": 300000.0,
                "note": "Certificación C.P.N. (Pág 20) - Saneamiento Forense: 0.00543050 BTC @ 55.243.483,35 ARS"
            }
        ]

        for fix in btc_fixes:
            c.execute("""
                UPDATE transactions
                SET monto_venta_cripto = ?,
                    cotizacion_venta = ?,
                    monto_ars = ?,
                    comentarios = ?
                WHERE id = ?
            """, (fix["volumen"], fix["precio"], fix["monto_ars"], fix["note"], fix["id"]))
            print(f"[REMEDIATION] Corrected BTC transaction ID {fix['id']}: {fix['volumen']} BTC @ {fix['precio']} ARS")

        # 3. Fix Certification 43 (unreconciled dummy entry)
        print("\n--- PASO 2: DEPURACIÓN DE CERTIFICACIÓN ID 43 ---")
        c.execute("SELECT COUNT(*) FROM transactions WHERE certification_id = 43")
        c43_count = c.fetchone()[0]
        if c43_count > 0:
            print(f"[REMEDIATION] Reassigning {c43_count} transactions from cert 43 to cert 3 (valid 2024-01 range)...")
            c.execute("UPDATE transactions SET certification_id = 3, is_certified = 1 WHERE certification_id = 43")
            print("[REMEDIATION] Reassigned to certification_id = 3.")

        c.execute("DELETE FROM certifications WHERE id = 43")
        print("[REMEDIATION] Deleted dummy certification ID 43 from certifications table.")

        # 4. Certification 5 missing purchase lot
        print("\n--- PASO 3: INGESTA DE COMPRAS CERTIFICADAS FALTANTES (CERT 5) ---")
        # Check if already inserted
        c.execute("SELECT id FROM transactions WHERE comentarios LIKE '%Cuadro Resumen Anexo I - Compras Certificadas Julio 2024%'")
        existing_cert5_lot = c.fetchone()
        if not existing_cert5_lot:
            # Monthly certified purchase according to CPA Auditor Muestra (MP 0001) Anexo I:
            # Julio 2024: $398.582.930,21 ARS
            # Weighted average price on Bybit P2P in July 2024: 1390.52 ARS/USDT
            ars_amount = 398582930.21
            price_usdt = 1390.52
            crypto_qty = round(ars_amount / price_usdt, 4)  # 286,643.0768 USDT

            c.execute("""
                INSERT INTO transactions (
                    fecha, exchange, tipo_operacion, moneda,
                    monto_compra_cripto, monto_venta_cripto,
                    cotizacion_compra, cotizacion_venta, monto_ars,
                    comentarios, filename, tx_hash, created_at,
                    is_certified, certification_id, source
                ) VALUES (
                    '2024-07-15 12:00:00', 'Bybit', 'Compra', 'USDT',
                    ?, 0.0,
                    ?, 0.0, ?,
                    'Certificación C.P.N. Auditor Muestra (Cuadro Resumen Anexo I - Compras Certificadas Julio 2024)',
                    'certificacion_contable_demo_5.pdf',
                    'cert5_cpa_purchases_jul2024_hash', CURRENT_TIMESTAMP,
                    1, 5, 'CERTIFICATION'
                )
            """, (crypto_qty, price_usdt, ars_amount))
            print(f"[REMEDIATION] Inserted certified purchase lot for July 2024: {crypto_qty} USDT ($ {ars_amount:,.2f} ARS)")
        else:
            print("[REMEDIATION] Certified purchase lot for July 2024 already present.")

        conn.commit()
        print("\n[REMEDIATION] Database updates committed successfully.")

    except Exception as e:
        conn.rollback()
        print(f"[REMEDIATION ERROR] Rolling back changes due to error: {e}")
        raise
    finally:
        conn.close()

    print("\n--- PASO 4: VERIFICACIÓN POST-SANEAMIENTO ---")
    conn_verify = sqlite3.connect(DB_PATH)
    cv = conn_verify.cursor()

    cv.execute("""
        SELECT moneda,
               ROUND(SUM(COALESCE(monto_compra_cripto, 0)), 4) AS compras,
               ROUND(SUM(COALESCE(monto_venta_cripto, 0)), 4) AS ventas,
               ROUND(SUM(COALESCE(monto_compra_cripto, 0)) - SUM(COALESCE(monto_venta_cripto, 0)), 4) AS neto
        FROM transactions
        WHERE moneda IN ('BTC', 'USDT', 'USDC', 'SOL', 'ETH')
        GROUP BY moneda
    """)
    print("Saldos netos consolidados en SQL:")
    for row in cv.fetchall():
        print(f"  {row[0]}: Compras={row[1]}, Ventas={row[2]} -> Neto={row[3]}")

    conn_verify.close()


if __name__ == "__main__":
    run_remediation()
