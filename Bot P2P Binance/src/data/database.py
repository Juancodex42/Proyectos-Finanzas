"""
Base de datos SQLite para almacenar snapshots, rankings, órdenes y configuración.
Ensambla los repositorios modulares de mercado, anuncios, órdenes y configuración.
"""
import os
import sqlite3
import logging
import threading
from pathlib import Path
from typing import Optional, Any

from config.settings import DB_PATH
from data.schema import (
    SCHEMA, _safe_json_list, _parse_float, _parse_int, _parse_db_datetime,
)
from data.repos import (
    MarketRepoMixin, AdRepoMixin, OrderRepoMixin, ConfigRepoMixin,
)

logger = logging.getLogger(__name__)


class Database(MarketRepoMixin, AdRepoMixin, OrderRepoMixin, ConfigRepoMixin):
    """Gestión de la base de datos SQLite con capacidades modulares multirrepositorio."""
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()
        if self.db_path.name == "p2p_bot.db":
            self._apply_pending_clean_replica_if_any()

    def _apply_pending_clean_replica_if_any(self):
        """Si existe una réplica compactada pendiente (p2p_bot_clean.db), sincroniza deltas operativos y la activa atómicamente."""
        clean_file = self.db_path.with_name("p2p_bot_clean.db")
        if not clean_file.exists() or not self.db_path.exists():
            return
        try:
            src = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            dst = sqlite3.connect(str(clean_file))
            for table in ("bot_config", "my_ads", "payment_method_scores", "detected_orders", "liquidity", "price_changes", "price_wars"):
                try:
                    cur = src.execute(f"SELECT * FROM {table}")
                    rows = cur.fetchall()
                    if rows:
                        cols = [d[0] for d in cur.description]
                        ph = ",".join("?" for _ in cols)
                        dst.executemany(f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({ph})", [tuple(r) for r in rows])
                except Exception:
                    pass
            dst.commit()
            dst.close()
            src.close()

            backup_file = self.db_path.with_name("p2p_bot.db.bak")
            if backup_file.exists():
                backup_file.unlink()
            os.replace(str(self.db_path), str(backup_file))
            os.replace(str(clean_file), str(self.db_path))
            for ext in ("-wal", "-shm"):
                aux = self.db_path.with_name(f"p2p_bot.db{ext}")
                if aux.exists():
                    try:
                        aux.unlink()
                    except Exception:
                        pass
            backup_file.unlink()
            logger.info("🎉 Réplica compactada p2p_bot_clean.db activada atómicamente con éxito.")
        except Exception:
            pass

    def connect(self) -> sqlite3.Connection:
        with self._lock:
            if self._conn is None:
                self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
                self._conn.row_factory = sqlite3.Row
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.execute("PRAGMA foreign_keys=ON")
                self._conn.execute("PRAGMA busy_timeout=5000")
            return self._conn

    def _execute_write(self, sql: str, params: tuple = (), *, executemany: bool = False, many_params: list = None):
        """Ejecuta una escritura con thread lock y rollback automático ante fallos."""
        with self._lock:
            conn = self.connect()
            try:
                if executemany and many_params is not None:
                    cursor = conn.executemany(sql, many_params)
                else:
                    cursor = conn.execute(sql, params)
                conn.commit()
                return cursor
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise

    def init_schema(self):
        """Crea todas las tablas si no existen y migra columnas faltantes."""
        with self._lock:
            conn = self.connect()
            conn.executescript(SCHEMA)
            existing_cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(my_ads)").fetchall()
            }
            for col_name in ("init_amount", "surplus_amount", "min_trans_amount", "max_trans_amount"):
                if col_name not in existing_cols:
                    conn.execute(f"ALTER TABLE my_ads ADD COLUMN {col_name} REAL DEFAULT 0.0")

            existing_order_cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(detected_orders)").fetchall()
            }
            if "fiwind_bid" not in existing_order_cols:
                conn.execute("ALTER TABLE detected_orders ADD COLUMN fiwind_bid REAL DEFAULT NULL")

            conn.commit()
            logger.info("Schema de BD inicializado en %s", self.db_path)

    def vacuum(self):
        """Ejecuta VACUUM sobre la base de datos de forma thread-safe."""
        with self._lock:
            conn = self.connect()
            conn.execute("VACUUM")

    def close(self):
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None


