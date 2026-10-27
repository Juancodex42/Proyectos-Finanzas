"""
Quirurgical Database Healing and Deduplication Script.
1. Removes 6 malformed OKX orders stored in Binance P2P.
2. Re-ingests OKX 2026 fulfilled orders correctly mapped to exchange='OKX'.
3. Deduplicates Bitso triplicates (keeping canonical UTC records with trade ID).
4. Recalculates FIFO.
"""

import os
import sys
import sqlite3
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'webapp', 'backend'))
COMPAT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'webapp', 'backend', 'compat'))
for _p in (COMPAT_DIR, BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from db.connection import get_connection
from models.transaction_models import compute_canonical_tx_hash
from services.fifo_service import recalculate_fifo_costs_db
from services.cache_service import invalidate_analytics_cache


def heal_database():
    conn = get_connection()
    cursor = conn.cursor()

    logger.info("=== STEP 1: Removing 6 malformed OKX orders from Binance P2P ===")
    cursor.execute("""
        DELETE FROM transactions 
        WHERE rowid BETWEEN 15165 AND 15170 
          AND exchange = 'Binance P2P'
          AND (is_certified = 0 OR is_certified IS NULL)
    """)
    deleted_okx_malformed = cursor.rowcount
    logger.info(f"Deleted {deleted_okx_malformed} malformed OKX rows.")

    logger.info("=== STEP 2: Re-ingesting OKX 2026 fulfilled orders correctly ===")
    okx_aux_dir = os.environ.get('AUX_DIR', os.path.join(ROOT_DIR, 'data'))
    okx_csv_path = os.path.join(okx_aux_dir, '20261006_230124_3ef1fe51-0769-456d-8d76-e6341d6d1e0c.csv')
    inserted_okx = 0
    if os.path.exists(okx_csv_path):
        df_okx = pd.read_csv(okx_csv_path)
        fulfilled_2026 = df_okx[(df_okx['Status'] == 'Fulfilled') & (df_okx['Created date'].str.startswith('2026'))]
        for _, row in fulfilled_2026.iterrows():
            order_no = str(row['Order No'])
            order_type = str(row['Order type']).strip().title() # 'Buy' or 'Sell'
            crypto = str(row['Crypto']).strip().upper()
            price = float(row['Price'])
            volume = float(row['Volume'])
            amount = float(row['Amount'])
            created_date = str(row['Created date']).strip()

            is_buy = order_type == 'Buy'
            tipo_op = 'Compra' if is_buy else 'Venta'
            m_compra = volume if is_buy else 0.0
            m_venta = volume if not is_buy else 0.0
            c_compra = price if is_buy else 0.0
            c_venta = price if not is_buy else 0.0
            comentario = f"Order ID: {order_no} | OKX P2P ({row.get('Payment method', '')})"

            tx_hash = compute_canonical_tx_hash(
                created_date, 'OKX', tipo_op, crypto,
                monto_compra=m_compra, monto_venta=m_venta,
                monto_ars=amount, unique_ref=order_no
            )

            cursor.execute("""
                INSERT OR IGNORE INTO transactions (
                    tx_hash, fecha, exchange, tipo_operacion, moneda,
                    monto_compra_cripto, monto_venta_cripto, cotizacion_compra, cotizacion_venta,
                    monto_ars, comentarios, filename, is_certified, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tx_hash, created_date, 'OKX', tipo_op, crypto,
                m_compra, m_venta, c_compra, c_venta,
                amount, comentario, '20261006_230124_3ef1fe51-0769-456d-8d76-e6341d6d1e0c.csv',
                0, 'NATIVE_CSV'
            ))
            if cursor.rowcount > 0:
                inserted_okx += 1
        logger.info(f"Successfully re-ingested {inserted_okx} valid OKX 2026 transactions.")
    else:
        logger.warning(f"OKX CSV not found at {okx_csv_path}")

    logger.info("=== STEP 3: Deduplicating Bitso triplicates ===")
    # Remove the 112 rows with 'Bitso Trade' (which lack IDs and have timezone offsets)
    cursor.execute("""
        DELETE FROM transactions 
        WHERE lower(exchange) LIKE '%bitso%' 
          AND comentarios = 'Bitso Trade'
          AND (is_certified = 0 OR is_certified IS NULL)
    """)
    deleted_bitso_no_id = cursor.rowcount
    logger.info(f"Deleted {deleted_bitso_no_id} Bitso rows with redundant 'Bitso Trade' comment.")

    # Remove the 111 rows with 'Bitso Alpha: ' keeping the canonical 'Bitso ID: ' rows
    cursor.execute("""
        DELETE FROM transactions 
        WHERE lower(exchange) LIKE '%bitso%' 
          AND comentarios LIKE 'Bitso Alpha: %'
          AND (is_certified = 0 OR is_certified IS NULL)
    """)
    deleted_bitso_alpha = cursor.rowcount
    logger.info(f"Deleted {deleted_bitso_alpha} Bitso duplicate rows with 'Bitso Alpha: <ID>'.")

    # Ensure canonical exchange name is 'Bitso Alpha' for remaining Bitso rows
    cursor.execute("""
        UPDATE transactions 
        SET exchange = 'Bitso Alpha' 
        WHERE lower(exchange) LIKE '%bitso%'
          AND (is_certified = 0 OR is_certified IS NULL)
    """)

    conn.commit()

    cursor.execute("SELECT count(*) FROM transactions WHERE lower(exchange) LIKE '%bitso%'")
    remaining_bitso = cursor.fetchone()[0]
    logger.info(f"Remaining legitimate Bitso transactions: {remaining_bitso}")

    cursor.execute("SELECT count(*) FROM transactions WHERE exchange = 'OKX'")
    okx_count = cursor.fetchone()[0]
    logger.info(f"OKX transactions in DB: {okx_count}")

    conn.close()

    logger.info("=== STEP 4: Recalculating FIFO Base Costs ===")
    recalculate_fifo_costs_db()
    invalidate_analytics_cache()
    logger.info("Database healing complete and FIFO recalculated successfully.")


if __name__ == '__main__':
    heal_database()
