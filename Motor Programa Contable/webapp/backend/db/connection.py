import os
import re
import sys
import sqlite3
import logging
import pandas as pd

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'transactions.db')


def get_connection():
    """
    Returns an active SQLite connection with WAL mode and busy timeout configured.
    Respects monkeypatched db_manager.get_connection or db_manager.DB_PATH for tests.
    """
    if 'db_manager' in sys.modules:
        dm = sys.modules['db_manager']
        patched_fn = getattr(dm, 'get_connection', None)
        if patched_fn is not None and patched_fn is not get_connection:
            return patched_fn()
        path_to_use = getattr(dm, 'DB_PATH', DB_PATH) or DB_PATH
    else:
        path_to_use = DB_PATH

    conn = sqlite3.connect(path_to_use, timeout=30.0)
    try:
        conn.execute("PRAGMA busy_timeout = 30000;")
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA cache_size = -64000;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        conn.execute("PRAGMA mmap_size = 268435456;")
    except Exception as e:
        logger.error(f"Error setting SQLite PRAGMAs: {e}")
    return conn


def init_db():
    """
    Initializes the SQLite database tables and runs retroactive migrations:
    - transactions (with certification metadata)
    - tax_settings (with provincial and fallback fields)
    - exchanges_config (with native and custom configurations)
    - certifications (CPA accounting periods)
    """
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT,
                exchange TEXT,
                tipo_operacion TEXT,
                moneda TEXT,
                monto_compra_cripto REAL,
                monto_venta_cripto REAL,
                cotizacion_compra REAL,
                cotizacion_venta REAL,
                monto_ars REAL,
                comentarios TEXT,
                filename TEXT,
                tx_hash TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_certified INTEGER DEFAULT 0,
                certification_id INTEGER DEFAULT NULL,
                source TEXT DEFAULT 'EXCHANGE_API',
                requires_cost_audit INTEGER DEFAULT 0,
                monto_descubierto REAL DEFAULT 0.0
            )
        ''')

        for col, col_def in [
            ("filename", "TEXT"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("is_certified", "INTEGER DEFAULT 0"),
            ("certification_id", "INTEGER DEFAULT NULL"),
            ("source", "TEXT DEFAULT 'EXCHANGE_API'"),
            ("requires_cost_audit", "INTEGER DEFAULT 0"),
            ("monto_descubierto", "REAL DEFAULT 0.0")
        ]:
            try:
                c.execute(f"ALTER TABLE transactions ADD COLUMN {col} {col_def}")
            except sqlite3.OperationalError:
                pass


        c.execute('''
            CREATE TABLE IF NOT EXISTS tax_settings (
                year INTEGER PRIMARY KEY,
                ganancias_deduccion REAL,
                ganancias_alicuota REAL,
                iibb_tramo1_limite REAL,
                iibb_tramo1_alicuota REAL,
                iibb_tramo2_limite REAL,
                iibb_tramo2_alicuota REAL,
                iibb_tramo3_alicuota REAL,
                iibb_base_calculo TEXT
            )
        ''')

        # Ensure all columns exist for tax_settings (dynamic migration)
        try:
            c.execute("ALTER TABLE tax_settings ADD COLUMN iibb_provincia TEXT DEFAULT 'Catamarca'")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE tax_settings ADD COLUMN ganancias_estimadas_fallback_pct REAL DEFAULT 15.0")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE tax_settings ADD COLUMN usd_ars_exchange_rate REAL DEFAULT 1000.0")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE tax_settings ADD COLUMN use_ganancias_fallback INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass

        # Insert default values for 2025 if not existing
        c.execute("SELECT COUNT(*) FROM tax_settings WHERE year=2025")
        if c.fetchone()[0] == 0:
            c.execute('''
                INSERT INTO tax_settings (
                    year, ganancias_deduccion, ganancias_alicuota,
                    iibb_tramo1_limite, iibb_tramo1_alicuota,
                    iibb_tramo2_limite, iibb_tramo2_alicuota,
                    iibb_tramo3_alicuota, iibb_base_calculo,
                    iibb_provincia, ganancias_estimadas_fallback_pct,
                    usd_ars_exchange_rate, use_ganancias_fallback
                ) VALUES (
                    2025,
                    0.0,
                    15.0,
                    3255000000.0,
                    5.0,
                    26970000000.0,
                    6.0,
                    7.0,
                    'diferencial',
                    'Catamarca',
                    15.0,
                    1000.0,
                    1
                )
            ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS exchanges_config (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                status TEXT DEFAULT 'online',
                last_update TEXT DEFAULT '-',
                date_format TEXT DEFAULT '%d/%m/%Y %H:%M:%S',
                mapping_json TEXT DEFAULT '{}',
                api_keys_json TEXT DEFAULT '{}',
                is_active INTEGER DEFAULT 1
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS certifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                issue_date TEXT,
                cpa_name TEXT,
                notes TEXT,
                file_path TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        for col, col_type in [
            ("certified_sales_ars", "REAL DEFAULT 0.0"),
            ("certified_buys_ars", "REAL DEFAULT 0.0"),
            ("certified_pnl_ars", "REAL DEFAULT 0.0"),
            ("reconciliation_status", "TEXT DEFAULT 'UNRECONCILED'"),
            ("monthly_breakdown_json", "TEXT DEFAULT '{}'")
        ]:
            try:
                c.execute(f"ALTER TABLE certifications ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass

        c.execute('''
            CREATE TABLE IF NOT EXISTS bank_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_hash TEXT UNIQUE,
                fecha TEXT NOT NULL,
                banco TEXT NOT NULL,
                tipo_movimiento TEXT NOT NULL,
                monto_ars REAL NOT NULL,
                descripcion TEXT DEFAULT '',
                titular_contraparte TEXT DEFAULT '',
                cuit_contraparte TEXT DEFAULT '',
                categoria TEXT DEFAULT 'PENDIENTE',
                subtipo_cuenta_propia TEXT DEFAULT NULL,
                matched_tx_id TEXT DEFAULT NULL,
                raw_reference TEXT DEFAULT '',
                nota_auditoria TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS operational_settings (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Seed default exchanges if empty or missing
        defaults = [
            ('binance', 'Binance Spot', 'NATIVE_API', 'online', '-', '%Y-%m-%d %H:%M:%S', '{}', '{}', 1),
            ('binance_p2p', 'Binance P2P', 'NATIVE_CSV', 'online', '-', '%Y-%m-%d %H:%M:%S', '{}', '{}', 1),
            ('bitso', 'Bitso Alpha', 'NATIVE_API', 'online', '-', '%d/%m/%Y %H:%M:%S', '{}', '{}', 1),
            ('fiwind', 'Fiwind', 'NATIVE_CSV', 'online', '-', '%d/%m/%Y %H:%M:%S', '{}', '{}', 1),
            ('ripio_trade', 'Ripio Trade', 'NATIVE_CSV', 'online', '-', '%d/%m/%Y %H:%M:%S', '{}', '{}', 1),
            ('ripio_classic', 'Ripio Classic', 'NATIVE_CSV', 'online', '-', '%d/%m/%Y %H:%M:%S', '{}', '{}', 1),
            ('okx', 'OKX', 'NATIVE_API', 'online', '-', '%d/%m/%Y %H:%M:%S', '{}', '{}', 1),
            ('bybit', 'Bybit', 'NATIVE_API', 'online', '-', '%d/%m/%Y %H:%M:%S', '{}', '{}', 1),
            ('bitget', 'Bitget', 'NATIVE_API', 'online', '-', '%d/%m/%Y %H:%M:%S', '{}', '{}', 1),
            ('manual', 'Operaciones Manuales', 'MANUAL', 'online', '-', '%d/%m/%Y %H:%M:%S', '{"fecha":"Fecha","tipo_operacion":"Tipo","moneda":"Moneda","monto_compra_cripto":"Cantidad Compra","monto_venta_cripto":"Cantidad Venta","cotizacion_compra":"Cotizacion Compra","cotizacion_venta":"Cotizacion Venta","monto_ars":"Monto ARS","comentarios":"Notas"}', '{}', 1),
            ('varios', 'Exchanges Manuales / Varios', 'MANUAL', 'online', '-', '%d/%m/%Y %H:%M:%S', '{"fecha":"Fecha","exchange":"Exchange","tipo_operacion":"Tipo","moneda":"Moneda","monto_compra_cripto":"Cantidad Compra","monto_venta_cripto":"Cantidad Venta","cotizacion_compra":"Cotizacion Compra","cotizacion_venta":"Cotizacion Venta","monto_ars":"Monto ARS","comentarios":"Notas"}', '{}', 1),
        ]
        for d in defaults:
            c.execute("INSERT OR IGNORE INTO exchanges_config VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", d)

        # Performance Indexes
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_is_certified ON transactions(is_certified);")
            c.execute("CREATE INDEX IF NOT EXISTS idx_exchange_fecha ON transactions(exchange, fecha);")
            c.execute("CREATE INDEX IF NOT EXISTS idx_tx_fecha ON transactions(fecha);")
            c.execute("CREATE INDEX IF NOT EXISTS idx_tx_moneda_fecha ON transactions(moneda, fecha);")
            c.execute("CREATE INDEX IF NOT EXISTS idx_tipo_operacion ON transactions(tipo_operacion);")
        except Exception as e:
            print(f"Notice creating indexes: {e}")

        # Retroactive migrations (only run once via schema user_version)
        c.execute("PRAGMA user_version;")
        row_ver = c.fetchone()
        user_ver = row_ver[0] if row_ver else 0
        if user_ver < 2:
            migration_failed = False
            # Retroactive date sanitization for existing transactions table with tx_hash recalculation
            try:
                from models.transaction_models import compute_canonical_tx_hash
                c.execute("""
                    SELECT tx_hash, fecha, exchange, tipo_operacion, moneda,
                           monto_compra_cripto, monto_venta_cripto, monto_ars, comentarios
                    FROM transactions
                    WHERE fecha LIKE '%/%'
                """)
                rows_to_fix = c.fetchall()
                if rows_to_fix:
                    for old_hash, raw_f, ex, tipo, mon, mc, mv, mars, coment in rows_to_fix:
                        try:
                            dt = pd.to_datetime(raw_f, dayfirst=True, errors='coerce')
                            if not pd.isna(dt):
                                clean_iso_fecha = dt.strftime('%Y-%m-%d %H:%M:%S')
                                new_hash = compute_canonical_tx_hash(
                                    clean_iso_fecha, ex, tipo, mon,
                                    monto_compra=float(mc or 0), monto_venta=float(mv or 0),
                                    monto_ars=float(mars or 0),
                                    unique_ref=str(coment or '')
                                )
                                if new_hash != old_hash:
                                    c.execute("SELECT COUNT(*) FROM transactions WHERE tx_hash = ?", (new_hash,))
                                    if c.fetchone()[0] > 0:
                                        c.execute("DELETE FROM transactions WHERE tx_hash = ? AND (is_certified IS NULL OR is_certified = 0)", (old_hash,))
                                    else:
                                        c.execute("UPDATE transactions SET fecha = ?, tx_hash = ? WHERE tx_hash = ?", (clean_iso_fecha, new_hash, old_hash))
                                else:
                                    c.execute("UPDATE transactions SET fecha = ? WHERE tx_hash = ?", (clean_iso_fecha, old_hash))
                        except Exception:
                            pass
                    logger.info(f"Sanitized {len(rows_to_fix)} legacy dates to ISO format and recalculated tx_hashes.")
            except Exception as e:
                logger.error(f"Error in date sanitization migration: {e}")
                migration_failed = True

            # Retroactive migration & cleanup for exchange names and empty rows
            try:
                c.execute(
                    "DELETE FROM transactions WHERE (exchange IS NULL OR TRIM(exchange) = '' OR fecha IS NULL OR TRIM(fecha) = '' OR moneda IS NULL OR TRIM(moneda) = '') AND (is_certified IS NULL OR is_certified = 0);"
                )
                c.execute("UPDATE transactions SET exchange = 'Bitso Alpha' WHERE exchange = 'Bitso';")
                c.execute("UPDATE transactions SET exchange = 'Ripio Trade' WHERE exchange = 'Ripio';")
            except Exception as e:
                logger.error(f"Error in exchange migration & cleanup: {e}")
                migration_failed = True

            # Repair and clean certification records
            try:
                from services.certifications_service import cleanup_and_deduplicate_certifications
                cleanup_and_deduplicate_certifications(conn=conn)
            except Exception as e:
                logger.error(f"Error in cleanup_and_deduplicate_certifications: {e}")
                migration_failed = True

            if migration_failed:
                try:
                    conn.rollback()
                except Exception:
                    pass
                logger.error("Retroactive migrations (user_version < 2) failed; rolled back changes and user_version remains unchanged.")
            else:
                c.execute("PRAGMA user_version = 2;")
                conn.commit()
        else:
            conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        conn.close()
