"""
P2P Buy and Sell Ads, Benchmarks, and Price Changes Repository Mixin.
"""
import json
import logging
from datetime import datetime
from typing import Optional, Any, List, Dict, Set
from data.models import MyAd, Benchmark, PriceChange
from data.schema import (
    _safe_json_list, _parse_float, _parse_int, _parse_db_datetime,
)

logger = logging.getLogger("data.ads")


class AdRepoMixin:
    """Operaciones de persistencia para anuncios de compra, venta, benchmarks y cambios de precio."""
    def save_benchmark(self, bm: Benchmark):
        ts_str = (
            bm.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            if bm.timestamp
            else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        self._execute_write(
            "INSERT INTO usdt_sell_benchmark "
            "(timestamp, payment_method, volume_filter, avg_top10_price, individual_prices_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                ts_str, bm.payment_method, bm.volume_filter, bm.avg_top_n_price,
                json.dumps(bm.individual_prices),
            ),
        )

    def get_latest_benchmark(self, payment_method: str) -> Optional[Benchmark]:
        with self._lock:
            conn = self.connect()
            row = conn.execute(
                "SELECT * FROM usdt_sell_benchmark WHERE payment_method = ? "
                "ORDER BY timestamp DESC LIMIT 1",
                (payment_method,),
            ).fetchone()
            if not row:
                return None
            return Benchmark(
                payment_method=row["payment_method"],
                avg_top_n_price=row["avg_top10_price"],
                individual_prices=_safe_json_list(row["individual_prices_json"]),
                volume_filter=row["volume_filter"],
                timestamp=_parse_db_datetime(row["timestamp"]) if "timestamp" in row.keys() else None,
            )

    def get_latest_benchmarks(self) -> dict[str, Benchmark]:
        """Retorna el último benchmark registrado para cada método de pago."""
        with self._lock:
            conn = self.connect()
            rows = conn.execute(
                """
                SELECT b.* FROM usdt_sell_benchmark b
                INNER JOIN (
                    SELECT payment_method, MAX(timestamp) as max_ts
                    FROM usdt_sell_benchmark
                    GROUP BY payment_method
                ) latest ON b.payment_method = latest.payment_method AND b.timestamp = latest.max_ts
                """
            ).fetchall()
            result = {}
            for row in rows:
                bm = Benchmark(
                    payment_method=row["payment_method"],
                    avg_top_n_price=row["avg_top10_price"],
                    individual_prices=_safe_json_list(row["individual_prices_json"]),
                    volume_filter=row["volume_filter"],
                    timestamp=_parse_db_datetime(row["timestamp"]) if "timestamp" in row.keys() else None,
                )
                result[row["payment_method"]] = bm
            return result


    # ── My Ads ────────────────────────────────────────────────────────

    def save_my_ad(self, ad: MyAd):
        last_rep_str = (
            ad.last_repositioned.isoformat()
            if isinstance(ad.last_repositioned, datetime)
            else ad.last_repositioned
        )
        self._execute_write(
            "INSERT OR REPLACE INTO my_ads "
            "(adv_no, asset, ad_group, current_price, payment_methods_json, status, "
            "init_amount, surplus_amount, min_trans_amount, max_trans_amount, last_repositioned) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ad.adv_no, ad.asset, ad.ad_group, ad.current_price,
                json.dumps(ad.payment_methods), ad.status,
                float(getattr(ad, "init_amount", 0.0) or 0.0),
                float(getattr(ad, "surplus_amount", 0.0) or 0.0),
                float(getattr(ad, "min_trans_amount", 0.0) or 0.0),
                float(getattr(ad, "max_trans_amount", 0.0) or 0.0),
                last_rep_str,
            ),
        )

    def get_my_ads(self, asset: Optional[str] = None) -> list[MyAd]:
        with self._lock:
            conn = self.connect()
            if asset:
                rows = conn.execute(
                    "SELECT * FROM my_ads WHERE asset = ? ORDER BY ad_group", (asset,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM my_ads ORDER BY asset, ad_group"
                ).fetchall()

            def _parse_dt(val: Any) -> Optional[datetime]:
                if isinstance(val, datetime):
                    return val
                if isinstance(val, str) and val.strip():
                    try:
                        return datetime.fromisoformat(val)
                    except Exception:
                        return None
                return None

            return [
                MyAd(
                    adv_no=r["adv_no"], asset=r["asset"], ad_group=r["ad_group"],
                    current_price=r["current_price"],
                    payment_methods=_safe_json_list(r["payment_methods_json"]),
                    status=r["status"],
                    init_amount=float(r["init_amount"] or 0.0) if "init_amount" in r.keys() else 0.0,
                    surplus_amount=float(r["surplus_amount"] or 0.0) if "surplus_amount" in r.keys() else 0.0,
                    min_trans_amount=float(r["min_trans_amount"] or 0.0) if "min_trans_amount" in r.keys() else 0.0,
                    max_trans_amount=float(r["max_trans_amount"] or 0.0) if "max_trans_amount" in r.keys() else 0.0,
                    last_repositioned=_parse_dt(r["last_repositioned"]),
                )
                for r in rows
            ]

    def get_all_my_ads(self, asset: Optional[str] = None) -> list[MyAd]:
        """Alias de get_my_ads."""
        return self.get_my_ads(asset=asset)

    # ── My Sell Ads ───────────────────────────────────────────────────

    def save_my_sell_ad(self, ad: MyAd):
        last_rep_str = (
            ad.last_repositioned.isoformat()
            if isinstance(ad.last_repositioned, datetime)
            else ad.last_repositioned
        )
        self._execute_write(
            "INSERT OR REPLACE INTO my_sell_ads "
            "(adv_no, asset, ad_group, current_price, payment_methods_json, status, "
            "init_amount, surplus_amount, min_trans_amount, max_trans_amount, last_repositioned) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ad.adv_no, ad.asset, ad.ad_group, ad.current_price,
                json.dumps(ad.payment_methods), ad.status,
                float(getattr(ad, "init_amount", 0.0) or 0.0),
                float(getattr(ad, "surplus_amount", 0.0) or 0.0),
                float(getattr(ad, "min_trans_amount", 0.0) or 0.0),
                float(getattr(ad, "max_trans_amount", 0.0) or 0.0),
                last_rep_str,
            ),
        )

    def get_my_sell_ads(self, asset: Optional[str] = None) -> list[MyAd]:
        with self._lock:
            conn = self.connect()
            if asset:
                rows = conn.execute(
                    "SELECT * FROM my_sell_ads WHERE asset = ? ORDER BY ad_group", (asset,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM my_sell_ads ORDER BY asset, ad_group"
                ).fetchall()

            def _parse_dt(val: Any) -> Optional[datetime]:
                if isinstance(val, datetime):
                    return val
                if isinstance(val, str) and val.strip():
                    try:
                        return datetime.fromisoformat(val)
                    except Exception:
                        return None
                return None

            return [
                MyAd(
                    adv_no=r["adv_no"], asset=r["asset"], ad_group=r["ad_group"],
                    current_price=r["current_price"],
                    payment_methods=_safe_json_list(r["payment_methods_json"]),
                    status=r["status"],
                    init_amount=float(r["init_amount"] or 0.0) if "init_amount" in r.keys() else 0.0,
                    surplus_amount=float(r["surplus_amount"] or 0.0) if "surplus_amount" in r.keys() else 0.0,
                    min_trans_amount=float(r["min_trans_amount"] or 0.0) if "min_trans_amount" in r.keys() else 0.0,
                    max_trans_amount=float(r["max_trans_amount"] or 0.0) if "max_trans_amount" in r.keys() else 0.0,
                    last_repositioned=_parse_dt(r["last_repositioned"]),
                    trade_type="SELL",
                )
                for r in rows
            ]

    def purge_sell_ads_except(self, keep_adv_nos: set[str]) -> int:
        if not keep_adv_nos:
            logger.warning("purge_sell_ads_except llamado con conjunto vacío; omisión preventiva.")
            return 0
        placeholders = ",".join("?" for _ in keep_adv_nos)
        cursor = self._execute_write(
            f"DELETE FROM my_sell_ads WHERE adv_no NOT IN ({placeholders})",
            tuple(keep_adv_nos),
        )
        return cursor.rowcount

    def clear_my_sell_ads(self) -> int:
        cursor = self._execute_write("DELETE FROM my_sell_ads")
        logger.info("Base de datos: se vació la tabla my_sell_ads (%d registros eliminados)", cursor.rowcount)
        return cursor.rowcount

    def get_all_my_sell_adv_nos(self) -> set[str]:
        with self._lock:
            conn = self.connect()
            rows = conn.execute("SELECT adv_no FROM my_sell_ads").fetchall()
            return {r["adv_no"] for r in rows}


    def get_all_my_adv_nos(self) -> set[str]:
        with self._lock:
            conn = self.connect()
            rows = conn.execute("SELECT adv_no FROM my_ads").fetchall()
            return {r["adv_no"] for r in rows}

    def purge_ads_except(self, keep_adv_nos: set[str]) -> int:
        """Elimina de my_ads cualquier anuncio que no esté en keep_adv_nos (ej: anuncios viejos o de venta)."""
        if not keep_adv_nos:
            logger.warning("purge_ads_except llamado con conjunto vacío; omisión preventiva de DELETE para evitar borrado total.")
            return 0
        placeholders = ",".join("?" for _ in keep_adv_nos)
        cursor = self._execute_write(
            f"DELETE FROM my_ads WHERE adv_no NOT IN ({placeholders})",
            tuple(keep_adv_nos),
        )
        return cursor.rowcount

    def clear_my_ads(self) -> int:
        """Elimina todos los registros de la tabla my_ads."""
        cursor = self._execute_write("DELETE FROM my_ads")
        logger.info("Base de datos: se vació la tabla my_ads (%d registros eliminados)", cursor.rowcount)
        return cursor.rowcount

    def update_ad_price(self, adv_no: str, new_price: float):
        self._execute_write(
            "UPDATE my_ads SET current_price = ?, last_repositioned = ? WHERE adv_no = ?",
            (new_price, datetime.now().isoformat(), adv_no),
        )

    def update_ad_params_db(
        self,
        adv_no: str,
        price: Optional[float] = None,
        init_amount: Optional[float] = None,
        min_trans_amount: Optional[float] = None,
        max_trans_amount: Optional[float] = None,
        surplus_amount: Optional[float] = None,
    ):
        """Actualiza precio, cantidad, remanente y/o límites en la tabla my_ads de SQLite."""
        sets = ["last_repositioned = ?"]
        vals: list = [datetime.now().isoformat()]
        if price is not None:
            sets.append("current_price = ?")
            vals.append(float(price))
        if init_amount is not None:
            sets.append("init_amount = ?")
            vals.append(float(init_amount))
        if min_trans_amount is not None:
            sets.append("min_trans_amount = ?")
            vals.append(float(min_trans_amount))
        if max_trans_amount is not None:
            sets.append("max_trans_amount = ?")
            vals.append(float(max_trans_amount))
        if surplus_amount is not None:
            sets.append("surplus_amount = ?")
            vals.append(float(surplus_amount))
        vals.append(adv_no)
        self._execute_write(
            f"UPDATE my_ads SET {', '.join(sets)} WHERE adv_no = ?",
            tuple(vals),
        )

    def decrement_ad_surplus(self, adv_no: str, amount_crypto: float) -> Optional[float]:
        """Descuenta inmediatamente amount_crypto del surplus_amount de un anuncio en SQLite (my_ads o my_sell_ads)."""
        with self._lock:
            conn = self.connect()
            try:
                row = conn.execute("SELECT surplus_amount, init_amount FROM my_ads WHERE adv_no = ?", (adv_no,)).fetchone()
                if row:
                    surplus_val = row["surplus_amount"]
                    curr = float(surplus_val if surplus_val is not None else (row["init_amount"] or 0.0))
                    new_val = max(curr - amount_crypto, 0.0)
                    conn.execute("UPDATE my_ads SET surplus_amount = ? WHERE adv_no = ?", (new_val, adv_no))
                    conn.commit()
                    return new_val

                row_sell = conn.execute("SELECT surplus_amount, init_amount FROM my_sell_ads WHERE adv_no = ?", (adv_no,)).fetchone()
                if row_sell:
                    surplus_val = row_sell["surplus_amount"]
                    curr = float(surplus_val if surplus_val is not None else (row_sell["init_amount"] or 0.0))
                    new_val = max(curr - amount_crypto, 0.0)
                    conn.execute("UPDATE my_sell_ads SET surplus_amount = ? WHERE adv_no = ?", (new_val, adv_no))
                    conn.commit()
                    return new_val
            except Exception as e:
                logger.warning("Error al descontar surplus_amount para adv_no %s: %s", adv_no, e)
            return None

    def update_ad_status(self, adv_no: str, status: int):
        self._execute_write(
            "UPDATE my_ads SET status = ? WHERE adv_no = ?", (status, adv_no)
        )
        self._execute_write(
            "UPDATE my_sell_ads SET status = ? WHERE adv_no = ?", (status, adv_no)
        )

    # ── Price Changes ─────────────────────────────────────────────────

    def save_price_change(self, pc: PriceChange):
        self._execute_write(
            "INSERT INTO price_changes "
            "(adv_no, asset, ad_group, old_price, new_price, reason, "
            "competitor_best_price, competitor_no, tc_implicito, "
            "benchmark_by_method_json, margin_worst, liquidity_ars) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                pc.adv_no, pc.asset, pc.ad_group, pc.old_price, pc.new_price,
                pc.reason, pc.competitor_best_price, pc.competitor_no,
                pc.tc_implicito, json.dumps(pc.benchmark_by_method),
                pc.margin_worst, pc.liquidity_ars,
            ),
        )

    def get_recent_price_changes(self, limit: int = 20) -> list[dict]:
        with self._lock:
            conn = self.connect()
            rows = conn.execute(
                "SELECT * FROM price_changes ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]


