import sys
import os
import tempfile
import sqlite3

# Add backend and compat to path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'webapp', 'backend'))
COMPAT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'webapp', 'backend', 'compat'))
for _p in (COMPAT_DIR, BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import db_manager
import db.connection
from services.fifo_service import recalculate_fifo_costs_db


def test_fifo_run():
    tmp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp_db_path = tmp_file.name
    tmp_file.close()

    orig_dbm_path = db_manager.DB_PATH
    orig_dbm_get_conn = db_manager.get_connection
    orig_dbc_path = db.connection.DB_PATH
    orig_dbc_get_conn = db.connection.get_connection

    def _tmp_get_connection():
        conn = sqlite3.connect(tmp_db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    db_manager.DB_PATH = tmp_db_path
    db_manager.get_connection = _tmp_get_connection
    db.connection.DB_PATH = tmp_db_path
    db.connection.get_connection = _tmp_get_connection

    try:
        db_manager.init_db()
        db_manager.insert_transactions([
            {
                "Fecha": "2025-06-10 10:00:00",
                "Exchange": "Binance Spot",
                "Tipo de Operación": "Compra",
                "Moneda": "USDT",
                "Monto Compra (Cripto)": 100.0,
                "Monto Venta (Cripto)": 0.0,
                "Cotización Compra": 1000.0,
                "Cotización Venta": 0.0,
                "Monto ARS": 100000.0,
                "Comentarios": "FIFO_TEMP_SEED_BUY",
            },
            {
                "Fecha": "2025-06-11 12:00:00",
                "Exchange": "Binance Spot",
                "Tipo de Operación": "Venta",
                "Moneda": "USDT",
                "Monto Compra (Cripto)": 0.0,
                "Monto Venta (Cripto)": 100.0,
                "Cotización Compra": 0.0,
                "Cotización Venta": 1050.0,
                "Monto ARS": 105000.0,
                "Comentarios": "FIFO_TEMP_SEED_SELL",
            },
        ], trigger_fifo_recalc=False)

        print("Temporary Database path:", db_manager.DB_PATH)

        conn = db_manager.get_connection()
        try:
            c = conn.cursor()

            # 1. Check stats before recalculation
            print("\n--- stats BEFORE recalculation ---")
            c.execute("SELECT COUNT(*) FROM transactions WHERE tipo_operacion='Venta' AND cotizacion_compra > 0")
            ventas_con_costo_before = c.fetchone()[0]
            print(f"Ventas with cotizacion_compra > 0: {ventas_con_costo_before}")

            spread_before = db_manager.get_modal_spread()
            print("get_modal_spread() result:", spread_before)

            # 2. Run FIFO recalculation
            print("\n--- Running recalculate_fifo_costs_db() ---")
            res = recalculate_fifo_costs_db()
            print("Recalculate result:", res)

            # 3. Check stats after recalculation
            print("\n--- stats AFTER recalculation ---")
            c.execute("SELECT COUNT(*) FROM transactions WHERE tipo_operacion='Venta' AND cotizacion_compra > 0")
            ventas_con_costo_after = c.fetchone()[0]
            print(f"Ventas with cotizacion_compra > 0: {ventas_con_costo_after}")
            assert ventas_con_costo_after == 1

            spread_after = db_manager.get_modal_spread()
            print("get_modal_spread() result:", spread_after)

            # Fetch all non-fallback spreads
            c.execute("""
                SELECT cotizacion_compra, cotizacion_venta, moneda, fecha, exchange
                FROM transactions
                WHERE tipo_operacion='Venta' AND cotizacion_compra > 0 AND cotizacion_venta > 0
            """)
            rows = c.fetchall()
            spreads = []
            for row in rows:
                buy_price = float(row[0])
                sell_price = float(row[1])
                spread = ((sell_price / buy_price) - 1.0) * 100.0
                if abs(spread - 17.647) >= 0.1 and -30.0 < spread < 50.0:
                    spreads.append((round(spread, 1), row[2], row[3], row[4]))

            print(f"\nNon-fallback Spreads (Count: {len(spreads)}):")
            for s, coin, date, exch in sorted(spreads, key=lambda x: x[0]):
                print(f"  Spread: {s}%, Coin: {coin}, Date: {date}, Exch: {exch}")
        finally:
            conn.close()
    finally:
        db_manager.DB_PATH = orig_dbm_path
        db_manager.get_connection = orig_dbm_get_conn
        db.connection.DB_PATH = orig_dbc_path
        db.connection.get_connection = orig_dbc_get_conn
        for suffix in ("", "-wal", "-shm"):
            p = tmp_db_path + suffix
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


if __name__ == "__main__":
    test_fifo_run()

