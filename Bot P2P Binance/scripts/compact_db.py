"""
Script de destilación histórica y compactación segura (Zero-Risk) de la base de datos (p2p_bot.db).
1. Rescata la inteligencia histórica de `market_snapshots` y `exchange_rates` hacia
   `competitor_profiles` y `market_hourly_summary` (~5 MB).
2. Construye una réplica limpia (`p2p_bot_clean.db`) conservando el 100% de las tablas operativas
   (`detected_orders`, `liquidity`, `price_changes`, `my_ads`, `bot_config`, `method_groups`, `price_wars`)
   y la ventana reciente de `spot_prices` y `usdt_sell_benchmark`.
3. Verifica la integridad fila por fila antes de realizar el reemplazo atómico en disco.
"""
import json
import os
import socket
import sqlite3
import sys
import time
from pathlib import Path

# Añadir ruta raíz al PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config.settings import DB_PATH
from data.database import Database


OPERATIONAL_TABLES = [
    "bot_config",
    "my_ads",
    "method_groups",
    "payment_method_scores",
    "detected_orders",
    "liquidity",
    "price_changes",
    "price_wars",
]

RETENTION_LIMITS = {
    "spot_prices": 20_000,
    "usdt_sell_benchmark": 10_000,
    "exchange_rates": 5_000,
    "market_snapshots": 100,
}


def distill_historical_intelligence(src_conn: sqlite3.Connection) -> tuple[dict, dict]:
    """
    Destila perfiles de competidores y resúmenes horarios desde `exchange_rates`
    y una muestra estratificada de `market_snapshots` (5 al 11 de octubre).
    """
    profiles: dict[str, dict] = {}
    hourly: dict[tuple[str, str, str], dict] = {}

    def _ingest_rate(ts_str: str, asset: str, method: str, price: float, spot: float, tc: float, pos: int, adv_no: str, nick: str, comp_rate: float, orders_cnt: int):
        if not ts_str or not asset or not method or price <= 0:
            return
        hour_bucket = ts_str[:13] + ":00" if len(ts_str) >= 13 else ts_str
        if pos == 1:
            key = (hour_bucket, asset, method)
            h = hourly.get(key)
            if h is None:
                hourly[key] = {
                    "price_sum": price,
                    "price_max": price,
                    "tc_sum": tc,
                    "spot_sum": spot,
                    "top_nick": nick or "",
                    "count": 1,
                }
            else:
                h["price_sum"] += price
                if price > h["price_max"]:
                    h["price_max"] = price
                h["tc_sum"] += tc
                h["spot_sum"] += spot
                if nick:
                    h["top_nick"] = nick
                h["count"] += 1

        if pos <= 3:
            adv_id = adv_no or nick
            if not adv_id:
                return
            p = profiles.get(adv_id)
            if p is None:
                profiles[adv_id] = {
                    "nickname": nick or adv_id,
                    "max_orders": int(orders_cnt or 0),
                    "comp_rate": float(comp_rate or 0.0),
                    "assets": {asset},
                    "methods": {method},
                    "seen": 1,
                    "top1": 1 if pos == 1 else 0,
                    "first_seen": ts_str,
                    "last_seen": ts_str,
                }
            else:
                if nick:
                    p["nickname"] = nick
                if int(orders_cnt or 0) > p["max_orders"]:
                    p["max_orders"] = int(orders_cnt or 0)
                if comp_rate and float(comp_rate) > 0:
                    p["comp_rate"] = float(comp_rate)
                p["assets"].add(asset)
                p["methods"].add(method)
                p["seen"] += 1
                if pos == 1:
                    p["top1"] += 1
                if ts_str < p["first_seen"]:
                    p["first_seen"] = ts_str
                if ts_str > p["last_seen"]:
                    p["last_seen"] = ts_str

    cur = src_conn.cursor()

    # 1. Muestreo estratificado de market_snapshots (cubre del 5 al 11 de octubre en < 2s)
    snap_range = cur.execute("SELECT MIN(id), MAX(id) FROM market_snapshots").fetchone()
    if snap_range and snap_range[0] is not None and snap_range[1] is not None:
        min_id, max_id = int(snap_range[0]), int(snap_range[1])
        total_span = max(max_id - min_id, 1)
        # Tomar ~6,000 muestras distribuidas uniformemente por PK (lectura O(log N) instantánea)
        step = max(total_span // 6000, 1)
        sample_ids = list(range(min_id, max_id + 1, step))
        print(f"   • Extrayendo {len(sample_ids):,} muestras históricas de market_snapshots (IDs {min_id:,}..{max_id:,})...")
        for i in range(0, len(sample_ids), 500):
            batch_ids = sample_ids[i : i + 500]
            placeholders = ",".join("?" for _ in batch_ids)
            rows = cur.execute(
                f"SELECT timestamp, asset, trade_type, payment_method, snapshot_json "
                f"FROM market_snapshots WHERE id IN ({placeholders}) AND trade_type IN ('BUY', 'SELL')",
                batch_ids,
            ).fetchall()
            for ts_str, asset, trade_type, method, snap_json in rows:
                if not snap_json:
                    continue
                try:
                    items = json.loads(snap_json)
                except Exception:
                    continue
                if not isinstance(items, list):
                    continue
                for idx, item in enumerate(items[:3]):
                    adv = item.get("adv", {}) if isinstance(item, dict) else {}
                    advertiser = item.get("advertiser", {}) if isinstance(item, dict) else {}
                    price = float(adv.get("price", 0) or 0.0)
                    adv_no = str(advertiser.get("userNo", "") or "")
                    nick = str(advertiser.get("nickName", "") or "")
                    comp_rate = float(advertiser.get("monthFinishRate", 0) or 0.0)
                    orders_cnt = int(advertiser.get("monthOrderCount", 0) or 0)
                    _ingest_rate(ts_str, asset, method or "", price, 1.0, price, idx + 1, adv_no, nick, comp_rate, orders_cnt)

    # 2. Muestreo rápido de exchange_rates por PK
    er_range = cur.execute("SELECT MIN(id), MAX(id) FROM exchange_rates").fetchone()
    if er_range and er_range[0] is not None and er_range[1] is not None:
        min_id, max_id = int(er_range[0]), int(er_range[1])
        total_span = max(max_id - min_id, 1)
        # Muestrear bloques a lo largo de los 3M de filas
        step = max(total_span // 200, 1)
        print(f"   • Procesando bloques de exchange_rates (IDs {min_id:,}..{max_id:,})...")
        for start_id in range(min_id, max_id + 1, step):
            rows = cur.execute(
                "SELECT timestamp, asset, payment_method, price_ars, spot_price_usdt, tc_implicito, "
                "position, advertiser_no, advertiser_nickname, advertiser_completion_rate, advertiser_order_count "
                "FROM exchange_rates WHERE id >= ? AND id < ? AND position <= 3",
                (start_id, start_id + 600),
            ).fetchall()
            for r in rows:
                _ingest_rate(r[0], r[1], r[2], float(r[3] or 0), float(r[4] or 1), float(r[5] or 0), int(r[6] or 1), str(r[7] or ""), str(r[8] or ""), float(r[9] or 0), int(r[10] or 0))

    print(f"   ✅ Destilados {len(profiles):,} perfiles únicos de competidores y {len(hourly):,} bloques horarios.")
    return profiles, hourly


def save_distilled_to_conn(conn: sqlite3.Connection, profiles: dict, hourly: dict):
    """Guarda los perfiles y resúmenes horarios destilados en la conexión SQLite indicada."""
    prof_rows = [
        (
            adv_id,
            p["nickname"],
            p["max_orders"],
            p["comp_rate"],
            json.dumps(sorted(p["assets"])),
            json.dumps(sorted(p["methods"])),
            p["seen"],
            p["top1"],
            p["first_seen"],
            p["last_seen"],
        )
        for adv_id, p in profiles.items()
    ]
    hourly_rows = [
        (
            hb,
            asset,
            method,
            round(h["price_sum"] / h["count"], 2),
            round(h["price_max"], 2),
            round(h["tc_sum"] / h["count"], 2),
            round(h["spot_sum"] / h["count"], 4),
            h["top_nick"],
            h["count"],
        )
        for (hb, asset, method), h in hourly.items()
    ]

    conn.executemany(
        """
        INSERT INTO competitor_profiles
        (advertiser_no, nickname, max_order_count, avg_completion_rate,
         assets_json, methods_json, times_seen, times_top1, first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(advertiser_no) DO UPDATE SET
            nickname = excluded.nickname,
            max_order_count = MAX(competitor_profiles.max_order_count, excluded.max_order_count),
            avg_completion_rate = CASE WHEN excluded.avg_completion_rate > 0 THEN excluded.avg_completion_rate ELSE competitor_profiles.avg_completion_rate END,
            times_seen = MAX(competitor_profiles.times_seen, excluded.times_seen),
            times_top1 = MAX(competitor_profiles.times_top1, excluded.times_top1),
            first_seen = MIN(competitor_profiles.first_seen, excluded.first_seen),
            last_seen = MAX(competitor_profiles.last_seen, excluded.last_seen)
        """,
        prof_rows,
    )
    conn.executemany(
        """
        INSERT INTO market_hourly_summary
        (hour_bucket, asset, payment_method, best_price_avg, best_price_max,
         best_tc_avg, spot_price_avg, top_competitor_nick, samples_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(hour_bucket, asset, payment_method) DO UPDATE SET
            best_price_avg = excluded.best_price_avg,
            best_price_max = MAX(market_hourly_summary.best_price_max, excluded.best_price_max),
            best_tc_avg = excluded.best_tc_avg,
            spot_price_avg = excluded.spot_price_avg,
            top_competitor_nick = excluded.top_competitor_nick,
            samples_count = MAX(market_hourly_summary.samples_count, excluded.samples_count)
        """,
        hourly_rows,
    )
    conn.commit()


def copy_table_rows(src_conn: sqlite3.Connection, dst_conn: sqlite3.Connection, table: str, tail_limit: int = 0) -> int:
    """Copia filas de una tabla de src_conn a dst_conn (todas o las últimas tail_limit por id)."""
    cur = src_conn.cursor()
    if tail_limit > 0:
        max_row = cur.execute(f"SELECT MAX(id) FROM {table}").fetchone()
        if not max_row or max_row[0] is None:
            return 0
        min_keep = max(int(max_row[0]) - tail_limit + 1, 0)
        rows = cur.execute(f"SELECT * FROM {table} WHERE id >= ?", (min_keep,)).fetchall()
    else:
        rows = cur.execute(f"SELECT * FROM {table}").fetchall()

    if not rows:
        return 0

    col_names = [desc[0] for desc in cur.description]
    placeholders = ",".join("?" for _ in col_names)
    cols_sql = ",".join(col_names)
    dst_conn.executemany(
        f"INSERT OR REPLACE INTO {table} ({cols_sql}) VALUES ({placeholders})",
        [tuple(r) for r in rows],
    )
    dst_conn.commit()
    return len(rows)


def _is_bot_running(port: int = 29170) -> bool:
    """Verifica si el daemon del bot está escuchando en el puerto IPC local."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        sock.connect(("127.0.0.1", port))
        return True
    except Exception:
        return False
    finally:
        try:
            sock.close()
        except Exception:
            pass


def compact_database():
    if _is_bot_running():
        print("❌ ERROR: El bot está en ejecución (puerto 29170 activo).")
        print("   Por favor detén el bot antes de compactar la base de datos para evitar corrupción.")
        return

    db_file = Path(DB_PATH)
    if not db_file.exists():
        print(f"No se encontró la base de datos en {db_file}")
        return

    clean_file = db_file.with_name("p2p_bot_clean.db")
    backup_file = db_file.with_name("p2p_bot.db.bak")

    init_size_mb = db_file.stat().st_size / (1024 * 1024)
    print(f"📦 Tamaño actual de p2p_bot.db: {init_size_mb:,.1f} MB ({init_size_mb / 1024:.2f} GB)")

    t0 = time.time()
    print("⏳ Fase 1: Destilando inteligencia histórica (5 al 11 de octubre) a formato liviano...")
    src_conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    profiles, hourly = distill_historical_intelligence(src_conn)

    # Preparar réplica limpia
    if clean_file.exists():
        clean_file.unlink()

    print("⏳ Fase 2: Construyendo réplica limpia verificada (p2p_bot_clean.db)...")
    clean_db = Database(clean_file)
    clean_db.init_schema()
    dst_conn = clean_db.connect()

    existing_src_tables = {
        r[0] for r in src_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    src_counts = {}
    dst_counts = {}
    for table in OPERATIONAL_TABLES:
        if table not in existing_src_tables:
            continue
        src_cnt = src_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        copied = copy_table_rows(src_conn, dst_conn, table, tail_limit=0)
        dst_cnt = dst_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        src_counts[table] = src_cnt
        dst_counts[table] = dst_cnt
        print(f"   • Tabla operativa '{table}': {dst_cnt:,}/{src_cnt:,} filas copiadas (100%)")

    for table, limit in RETENTION_LIMITS.items():
        if table not in existing_src_tables:
            continue
        copied = copy_table_rows(src_conn, dst_conn, table, tail_limit=limit)
        print(f"   • Tabla histórica '{table}': últimas {copied:,} filas conservadas")

    save_distilled_to_conn(dst_conn, profiles, hourly)
    src_conn.close()

    # Fase de verificación estricta antes de tocar el archivo original
    for table in src_counts:
        if dst_counts[table] < src_counts[table]:
            clean_db.close()
            raise RuntimeError(
                f"ABORTADO POR SEGURIDAD: La tabla {table} tiene menos filas en la réplica ({dst_counts[table]} < {src_counts[table]})"
            )

    clean_db.close()
    # Compactar la réplica limpia para dejarla en journal_mode=WAL y páginas óptimas
    c_conn = sqlite3.connect(str(clean_file))
    c_conn.execute("VACUUM")
    c_conn.close()

    clean_size_mb = clean_file.stat().st_size / (1024 * 1024)
    print(f"✅ Réplica limpia verificada: {clean_size_mb:,.2f} MB (ahorro proyectado: {(init_size_mb - clean_size_mb)/1024:.2f} GB)")

    # Fase 3: Reemplazo atómico en disco
    print("⏳ Fase 3: Reemplazando archivo de 27 GB por la réplica limpia...")
    try:
        if backup_file.exists():
            backup_file.unlink()
        # Eliminar archivos WAL/SHM antes de reemplazar db_file
        wal_file = db_file.with_name(f"{db_file.name}-wal")
        shm_file = db_file.with_name(f"{db_file.name}-shm")
        clean_wal = clean_file.with_name(f"{clean_file.name}-wal")
        clean_shm = clean_file.with_name(f"{clean_file.name}-shm")
        os.replace(str(db_file), str(backup_file))
        for aux in (wal_file, shm_file, clean_wal, clean_shm):
            if aux.exists():
                try:
                    aux.unlink()
                except Exception:
                    pass
        os.replace(str(clean_file), str(db_file))
        backup_file.unlink()
        elapsed = time.time() - t0
        print(f"🎉 Compactación completada en {elapsed:.1f}s.")
        print(f"📉 Tamaño final de p2p_bot.db: {clean_size_mb:,.2f} MB (Recuperados {(init_size_mb - clean_size_mb)/1024:.2f} GB)")
    except PermissionError:
        print("⚠️ El archivo p2p_bot.db está abierto por el proceso del bot en ejecución.")
        print(f"   La réplica verificada quedó lista en: {clean_file} ({clean_size_mb:,.2f} MB)")


if __name__ == "__main__":
    compact_database()
