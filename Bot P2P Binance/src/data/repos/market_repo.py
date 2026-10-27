"""
Market Snapshots, Exchange Rates, Intel, and Price Wars Repository Mixin.
"""
import json
import logging
from datetime import datetime
from typing import Optional, Any, List, Dict
from data.models import ExchangeRate, PaymentMethodScore
from data.schema import _parse_db_datetime, _safe_json_list

logger = logging.getLogger("data.market")


class MarketRepoMixin:
    """Operaciones de persistencia para snapshots de mercado, rates, intel y price wars."""
    def save_snapshot(
        self, asset: str, trade_type: str, payment_method: str,
        snapshot_json: str, volume_filter: float = 0.0,
    ):
        self._execute_write(
            "INSERT INTO market_snapshots (asset, trade_type, payment_method, volume_filter, snapshot_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (asset, trade_type, payment_method, volume_filter, snapshot_json),
        )

    # ── Exchange Rates ────────────────────────────────────────────────

    def save_exchange_rate(self, er: ExchangeRate):
        self._execute_write(
            "INSERT INTO exchange_rates "
            "(asset, payment_method, price_ars, spot_price_usdt, tc_implicito, "
            "position, advertiser_no, advertiser_nickname, advertiser_completion_rate, advertiser_order_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                er.asset, er.payment_method, er.price_ars, er.spot_price_usdt,
                er.tc_implicito, er.position, er.advertiser_no,
                er.advertiser_nickname, er.advertiser_completion_rate,
                er.advertiser_order_count,
            ),
        )

    def save_exchange_rates_batch(self, rates: list[ExchangeRate]):
        self._execute_write(
            "INSERT INTO exchange_rates "
            "(asset, payment_method, price_ars, spot_price_usdt, tc_implicito, "
            "position, advertiser_no, advertiser_nickname, advertiser_completion_rate, advertiser_order_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            executemany=True,
            many_params=[
                (
                    er.asset, er.payment_method, er.price_ars, er.spot_price_usdt,
                    er.tc_implicito, er.position, er.advertiser_no,
                    er.advertiser_nickname, er.advertiser_completion_rate,
                    er.advertiser_order_count,
                )
                for er in rates
            ],
        )

    def record_compact_market_intel(
        self,
        competitors: dict[tuple[str, str], list[ExchangeRate]],
        spot_prices: dict[str, float],
        now_dt: Optional[datetime] = None,
    ):
        """
        Registra en una sola transacción atómica:
        1) El resumen horario por (hour_bucket, asset, payment_method) en market_hourly_summary.
        2) El perfil consolidado de los competidores top-3 en competitor_profiles.
        Ocupa ~5 MB/año en lugar de 27 GB de blobs crudos.
        """
        if not competitors:
            return
        dt = now_dt or datetime.now()
        hour_bucket = dt.strftime("%Y-%m-%d %H:00")
        now_iso = dt.strftime("%Y-%m-%d %H:%M:%S")

        hourly_params = []
        comp_updates: dict[str, dict] = {}

        for (asset, method), rates in competitors.items():
            if not rates:
                continue
            top = rates[0]
            spot = spot_prices.get(asset, top.spot_price_usdt or 1.0)
            hourly_params.append(
                (
                    hour_bucket,
                    asset,
                    method,
                    float(top.price_ars),
                    float(top.price_ars),
                    float(top.tc_implicito),
                    float(spot),
                    top.advertiser_nickname or "",
                )
            )
            for idx, r in enumerate(rates[:3]):
                adv_id = r.advertiser_no or r.advertiser_nickname
                if not adv_id:
                    continue
                entry = comp_updates.setdefault(
                    adv_id,
                    {
                        "nickname": r.advertiser_nickname or adv_id,
                        "order_count": int(r.advertiser_order_count or 0),
                        "comp_rate": float(r.advertiser_completion_rate or 0.0),
                        "assets": set(),
                        "methods": set(),
                        "seen": 0,
                        "top1": 0,
                    },
                )
                entry["order_count"] = max(entry["order_count"], int(r.advertiser_order_count or 0))
                if r.advertiser_completion_rate:
                    entry["comp_rate"] = float(r.advertiser_completion_rate)
                entry["assets"].add(asset)
                entry["methods"].add(method)
                entry["seen"] += 1
                if idx == 0:
                    entry["top1"] += 1

        with self._lock:
            conn = self.connect()
            try:
                if hourly_params:
                    conn.executemany(
                        """
                        INSERT INTO market_hourly_summary
                        (hour_bucket, asset, payment_method, best_price_avg, best_price_max,
                         best_tc_avg, spot_price_avg, top_competitor_nick, samples_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                        ON CONFLICT(hour_bucket, asset, payment_method) DO UPDATE SET
                            best_price_avg = (market_hourly_summary.best_price_avg * market_hourly_summary.samples_count + excluded.best_price_avg) / (market_hourly_summary.samples_count + 1),
                            best_price_max = MAX(market_hourly_summary.best_price_max, excluded.best_price_max),
                            best_tc_avg = (market_hourly_summary.best_tc_avg * market_hourly_summary.samples_count + excluded.best_tc_avg) / (market_hourly_summary.samples_count + 1),
                            spot_price_avg = (market_hourly_summary.spot_price_avg * market_hourly_summary.samples_count + excluded.spot_price_avg) / (market_hourly_summary.samples_count + 1),
                            top_competitor_nick = excluded.top_competitor_nick,
                            samples_count = market_hourly_summary.samples_count + 1
                        """,
                        hourly_params,
                    )

                for adv_id, info in comp_updates.items():
                    conn.execute(
                        """
                        INSERT INTO competitor_profiles
                        (advertiser_no, nickname, max_order_count, avg_completion_rate,
                         assets_json, methods_json, times_seen, times_top1, first_seen, last_seen)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(advertiser_no) DO UPDATE SET
                            nickname = excluded.nickname,
                            max_order_count = MAX(competitor_profiles.max_order_count, excluded.max_order_count),
                            avg_completion_rate = CASE WHEN excluded.avg_completion_rate > 0 THEN excluded.avg_completion_rate ELSE competitor_profiles.avg_completion_rate END,
                            times_seen = competitor_profiles.times_seen + excluded.times_seen,
                            times_top1 = competitor_profiles.times_top1 + excluded.times_top1,
                            last_seen = excluded.last_seen
                        """,
                        (
                            adv_id,
                            info["nickname"],
                            info["order_count"],
                            info["comp_rate"],
                            json.dumps(sorted(info["assets"])),
                            json.dumps(sorted(info["methods"])),
                            info["seen"],
                            info["top1"],
                            now_iso,
                            now_iso,
                        ),
                    )
                conn.commit()
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                logger.debug("Error guardando inteligencia compacta: %s", e)

    def get_top_competitor_profiles(self, limit: int = 20) -> list[dict]:
        """Retorna los competidores más dominantes ordenados por apariciones en #1."""
        with self._lock:
            conn = self.connect()
            rows = conn.execute(
                "SELECT * FROM competitor_profiles ORDER BY times_top1 DESC, times_seen DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_market_hourly_summary(self, asset: str = "USDT", limit_hours: int = 48) -> list[dict]:
        """Retorna la serie horaria resumida para un activo."""
        with self._lock:
            conn = self.connect()
            rows = conn.execute(
                "SELECT * FROM market_hourly_summary WHERE asset = ? ORDER BY hour_bucket DESC LIMIT ?",
                (asset, limit_hours * 15),
            ).fetchall()
            return [dict(r) for r in rows]


    def save_method_scores(self, scores: list[PaymentMethodScore]):
        self._execute_write(
            "INSERT INTO payment_method_scores "
            "(identifier, pay_id, sellers_count, buyers_count, spread, score, selected, assigned_group) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            executemany=True,
            many_params=[
                (s.identifier, s.pay_id, s.sellers_count, s.buyers_count,
                 s.spread, s.score, s.selected, s.assigned_group)
                for s in scores
            ],
        )

    def get_selected_methods(self) -> list[PaymentMethodScore]:
        with self._lock:
            conn = self.connect()
            rows = conn.execute(
                "SELECT * FROM payment_method_scores "
                "WHERE selected = 1 ORDER BY assigned_group, score DESC"
            ).fetchall()
            return [
                PaymentMethodScore(
                    identifier=r["identifier"], pay_id=r["pay_id"],
                    sellers_count=r["sellers_count"], buyers_count=r["buyers_count"],
                    spread=r["spread"], score=r["score"],
                    selected=bool(r["selected"]), assigned_group=r["assigned_group"],
                )
                for r in rows
            ]


    def save_price_war(
        self, asset: str, payment_method: str, competitor_no: str,
        competitor_nickname: str, escalations: int,
        my_price: float, competitor_price: float,
    ):
        self._execute_write(
            "INSERT INTO price_wars "
            "(started_at, asset, payment_method, competitor_no, competitor_nickname, "
            "escalations, my_price_at_start, competitor_price_at_start) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), asset, payment_method, competitor_no, competitor_nickname,
             escalations, my_price, competitor_price),
        )

    def end_price_war(self, competitor_no: str, asset: str, outcome: str, payment_method: Optional[str] = None):
        if payment_method:
            self._execute_write(
                "UPDATE price_wars SET ended_at = ?, outcome = ? "
                "WHERE competitor_no = ? AND asset = ? AND payment_method = ? AND ended_at IS NULL",
                (datetime.now().isoformat(), outcome, competitor_no, asset, payment_method),
            )
        else:
            self._execute_write(
                "UPDATE price_wars SET ended_at = ?, outcome = ? "
                "WHERE competitor_no = ? AND asset = ? AND ended_at IS NULL",
                (datetime.now().isoformat(), outcome, competitor_no, asset),
            )

    def get_active_price_wars(self) -> list[dict]:
        """Retorna guerras de precios activas (ended_at IS NULL)."""
        with self._lock:
            conn = self.connect()
            rows = conn.execute(
                "SELECT * FROM price_wars WHERE ended_at IS NULL"
            ).fetchall()
            return [dict(r) for r in rows]

    def purge_old_snapshots(self, days: int = 3):
        """Elimina snapshots y registros históricos antiguos para mantener liviana la base de datos."""
        with self._lock:
            conn = self.connect()
            try:
                conn.execute(
                    "DELETE FROM market_snapshots WHERE timestamp < datetime('now', '-' || ? || ' days')",
                    (days,),
                )
                conn.execute(
                    "DELETE FROM exchange_rates WHERE timestamp < datetime('now', '-' || ? || ' days')",
                    (days,),
                )
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise
        logger.info("Purga de snapshots antiguos (>%d días) completada", days)

    # Filas máximas a conservar por tabla de histórico (~3 días de operación a 30s/ciclo)
    RETENTION_ROWS = {
        "market_snapshots": 1_000,
        "exchange_rates": 5_000,
        "spot_prices": 20_000,
        "usdt_sell_benchmark": 10_000,
    }

    def purge_by_retention(self, chunk_size: int = 20_000, max_chunks: int = 10) -> dict:
        """
        Purga liviana por PK (ids crecientes = orden temporal): conserva las últimas N filas
        de cada tabla de histórico. Borra por lotes con commit intermedio para no bloquear
        el loop principal. Retorna {tabla: filas_borradas}.
        """
        with self._lock:
            conn = self.connect()
            deleted: dict[str, int] = {}
            for table, keep in self.RETENTION_ROWS.items():
                try:
                    row = conn.execute(f"SELECT MAX(id) AS mx, MIN(id) AS mn FROM {table}").fetchone()
                    if not row or row["mx"] is None:
                        continue
                    cutoff_id = row["mx"] - keep
                    if cutoff_id <= row["mn"]:
                        continue
                    total = 0
                    lo = row["mn"]
                    for _ in range(max_chunks):
                        if lo > cutoff_id:
                            break
                        hi = min(lo + chunk_size, cutoff_id)
                        cur = conn.execute(
                            f"DELETE FROM {table} WHERE id >= ? AND id <= ?", (lo, hi)
                        )
                        conn.commit()
                        total += cur.rowcount
                        lo = hi + 1
                    if total:
                        deleted[table] = total
                except Exception as e:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    logger.warning("Purga por retención falló en %s: %s", table, e)
            if deleted:
                logger.info("Purga por retención: %s", deleted)
            return deleted

