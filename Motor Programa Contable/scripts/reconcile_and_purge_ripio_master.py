import os
import sys
import sqlite3
import shutil
import datetime
import logging

# Ensure backend and compat paths are loaded
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BACKEND_DIR = os.path.join(BASE_DIR, 'webapp', 'backend')
COMPAT_DIR = os.path.join(BACKEND_DIR, 'compat')
sys.path.insert(0, COMPAT_DIR)
sys.path.insert(0, BACKEND_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from parsers.ripio_parser import process_ripio_trade
from models.transaction_models import compute_canonical_tx_hash

DB_PATH = os.path.join(BACKEND_DIR, 'transactions.db')
RIP_MASTER_PATH = os.path.join(BACKEND_DIR, 'uploads', 'Ripio_Trade_Historico_Completo.csv')


def run_reconciliation():
    logger.info("=== STEP 1: Verifying Database Integrity ===")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cert_count = cursor.execute("SELECT COUNT(*) FROM transactions WHERE is_certified = 1").fetchone()[0]
    total_pre = cursor.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    logger.info(f"Total transactions: {total_pre} | Certified transactions: {cert_count}")

    if cert_count != 4290:
        raise RuntimeError(f"ABORT: Certified count is {cert_count}, expected exactly 4290. Refusing to proceed.")

    # Physical snapshot backup
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    archive_dir = os.path.join(BASE_DIR, 'docs', 'archive')
    os.makedirs(archive_dir, exist_ok=True)
    bak_path = os.path.join(archive_dir, f"transactions_backup_step4_{ts}.db")
    shutil.copy2(DB_PATH, bak_path)
    logger.info(f"Snapshot created at {bak_path}")

    logger.info("=== STEP 2: Purging Uncertified Ripio Fragments ===")
    cursor.execute("""
        DELETE FROM transactions 
        WHERE (is_certified = 0 OR is_certified IS NULL) 
          AND (filename LIKE '%Ripio%' OR lower(exchange) LIKE '%ripio%')
    """)
    purged_count = cursor.rowcount
    logger.info(f"Purged {purged_count} uncertified Ripio rows.")

    logger.info("=== STEP 3: Ingesting Ripio_Trade_Historico_Completo.csv ===")
    if not os.path.exists(RIP_MASTER_PATH):
        raise FileNotFoundError(f"Master CSV not found at {RIP_MASTER_PATH}")

    with open(RIP_MASTER_PATH, 'rb') as f:
        parsed_txs, _ = process_ripio_trade(f, 'Ripio_Trade_Historico_Completo.csv')

    logger.info(f"Parsed {len(parsed_txs)} transactions from master CSV.")

    inserted_ripio = 0
    for tx in parsed_txs:
        fecha = str(tx.get('Fecha', ''))
        exchange = 'Ripio Trade'
        tipo_op = str(tx.get('Tipo de Operación', ''))
        moneda = str(tx.get('Moneda', '')).upper()
        m_compra = float(tx.get('Monto Compra (Cripto)', 0.0) or 0.0)
        m_venta = float(tx.get('Monto Venta (Cripto)', 0.0) or 0.0)
        c_compra = float(tx.get('Cotización Compra', 0.0) or 0.0)
        c_venta = float(tx.get('Cotización Venta', 0.0) or 0.0)
        m_ars = float(tx.get('Monto ARS', 0.0) or 0.0)
        comentario = str(tx.get('Comentarios', ''))
        unique_ref = str(tx.get('unique_id', ''))

        tx_hash = compute_canonical_tx_hash(
            fecha, exchange, tipo_op, moneda,
            monto_compra=m_compra, monto_venta=m_venta,
            monto_ars=m_ars, unique_ref=unique_ref
        )

        cursor.execute("""
            INSERT OR IGNORE INTO transactions (
                tx_hash, fecha, exchange, tipo_operacion, moneda,
                monto_compra_cripto, monto_venta_cripto, cotizacion_compra, cotizacion_venta,
                monto_ars, comentarios, filename, is_certified, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tx_hash, fecha, exchange, tipo_op, moneda,
            m_compra, m_venta, c_compra, c_venta,
            m_ars, comentario, 'Ripio_Trade_Historico_Completo.csv',
            0, 'NATIVE_CSV'
        ))
        if cursor.rowcount > 0:
            inserted_ripio += 1

    logger.info(f"Successfully inserted {inserted_ripio} transactions from Ripio Trade master.")

    logger.info("=== STEP 4: Inserting Regularization Deposit Entries ===")
    # 1. Bitso BTC 2020 initial deposit
    btc_tx_hash = compute_canonical_tx_hash(
        '2020-07-01 00:00:00', 'Bitso Alpha', 'Ingreso Cripto', 'BTC',
        monto_compra=0.00695124, monto_venta=0.0, monto_ars=0.0,
        unique_ref='bitso_funding_initial_2020'
    )
    cursor.execute("""
        INSERT OR IGNORE INTO transactions (
            tx_hash, fecha, exchange, tipo_operacion, moneda,
            monto_compra_cripto, monto_venta_cripto, cotizacion_compra, cotizacion_venta,
            monto_ars, comentarios, filename, is_certified, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        btc_tx_hash, '2020-07-01 00:00:00', 'Bitso Alpha', 'Ingreso Cripto', 'BTC',
        0.00695124, 0.0, 0.0, 0.0,
        0.0, 'Depósito Inicial Bitso Funding / Wallet externa pre-operaciones',
        'manual_initial_deposit_btc_2020', 0, 'INITIAL_DEPOSIT'
    ))
    if cursor.rowcount > 0:
        logger.info("Inserted Bitso BTC 2020 initial deposit of 0.00695124 BTC.")

    # 2. Binance Spot SOL 2025 dust / deposit adjustment
    sol_tx_hash = compute_canonical_tx_hash(
        '2025-10-11 15:00:00', 'Binance Spot', 'Ingreso Cripto', 'SOL',
        monto_compra=0.112, monto_venta=0.0, monto_ars=0.0,
        unique_ref='binance_dust_convert_sol_2025'
    )
    cursor.execute("""
        INSERT OR IGNORE INTO transactions (
            tx_hash, fecha, exchange, tipo_operacion, moneda,
            monto_compra_cripto, monto_venta_cripto, cotizacion_compra, cotizacion_venta,
            monto_ars, comentarios, filename, is_certified, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sol_tx_hash, '2025-10-11 15:00:00', 'Binance Spot', 'Ingreso Cripto', 'SOL',
        0.112, 0.0, 0.0, 0.0,
        0.0, 'Depósito / Binance Convert polvo 0.112 SOL',
        'manual_initial_deposit_sol_2025', 0, 'INITIAL_DEPOSIT'
    ))
    if cursor.rowcount > 0:
        logger.info("Inserted Binance Spot SOL 2025 adjustment of 0.112 SOL.")

    conn.commit()

    # Final check
    cert_post = cursor.execute("SELECT COUNT(*) FROM transactions WHERE is_certified = 1").fetchone()[0]
    total_post = cursor.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    conn.close()

    logger.info(f"Post-migration: Total={total_post} | Certified={cert_post}")
    assert cert_post == 4290, f"Error: Certified count changed to {cert_post}"

    logger.info("=== STEP 5: Checking History Gaps with Updated Logic ===")
    from services.gap_service import check_history_gaps
    gaps = check_history_gaps()
    logger.info(f"Total remaining gaps: {len(gaps)}")
    if gaps:
        for g in gaps:
            logger.warning(f"Remaining gap: {g}")
    else:
        logger.info("🎉 SUCCESS! 0 HUECOS TOTALES EN TODA LA HISTORIA!")

    return len(gaps)


if __name__ == '__main__':
    run_reconciliation()
