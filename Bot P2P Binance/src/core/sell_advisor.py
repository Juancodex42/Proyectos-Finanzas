"""
Módulo de Asesoría de Ventas P2P (SellAdvisor).
Arquitectura de solo lectura que calcula precios óptimos Book-Aware por cluster de métodos.
Referencia de diseño: docs/ARQUITECTURA.md
"""
from datetime import datetime
from typing import Optional

from data.database import Database
from data.models import Benchmark, ClusterAdvice
from config.settings import (
    SELL_PRICING_MODE,
    SELL_MIN_STEP_BEHIND,
    SELL_MAX_SPREAD_FROM_TOP1_PCT,
    SELL_MIN_DELTA_BY_CLUSTER,
)


def calculate_book_aware_sell_price(
    top1: float,
    prices_top10: list[float],
    cluster_id: int,
    default_delta: float,
) -> float:
    """
    Calcula el precio de venta sugerido utilizando la estrategia Book-Aware:
    1. Base: Busca capturar al menos default_delta sobre P1.
    2. Expansión por spread: Si P2 está más despegado (spread amplio en métodos ilíquidos),
       se expande dinámicamente hasta (P2 - 0.01) para capturar todo el margen del libro.
    3. Podio Cap: Si el precio sugerido superaría el Puesto #3 (mercado comprimido),
       se topa en (P3 - 0.01) para garantizar visibilidad en el podio.
    4. Outlier Cap: No superar top1 * (1 + SELL_MAX_SPREAD_FROM_TOP1_PCT) (2.5%).
    """
    if top1 <= 0.0:
        return 0.0

    valid_prices = [p for p in prices_top10 if p > 0]
    if len(valid_prices) >= 3:
        sorted_raw = sorted(valid_prices)
        median_p = sorted_raw[len(sorted_raw) // 2]
        valid_prices = [p for p in valid_prices if p >= median_p * 0.975]

    if valid_prices:
        valid_prices.sort()
        top1 = valid_prices[0]

    base_price = round(top1 + default_delta, 2)

    if SELL_PRICING_MODE == "BOOK_AWARE" and len(valid_prices) >= 2:
        p2 = valid_prices[1]
        dynamic_target = round(p2 - SELL_MIN_STEP_BEHIND, 2)
        # Si P2 permite un precio mayor al base sin salir del puesto 2, capturamos ese spread extra
        suggested_p = max(base_price, dynamic_target)
    else:
        suggested_p = base_price

    # Podio Cap: si hay al menos 3 precios y P3 > P1, no quedar peor que P3
    if len(valid_prices) >= 3 and valid_prices[2] > valid_prices[1]:
        puesto3_p = valid_prices[2]
        if suggested_p >= puesto3_p:
            suggested_p = round(puesto3_p - SELL_MIN_STEP_BEHIND, 2)
    elif len(valid_prices) >= 3 and valid_prices[2] > top1:
        puesto3_p = valid_prices[2]
        if suggested_p > puesto3_p:
            suggested_p = round(puesto3_p, 2)

    # Outlier Cap de seguridad
    max_safe_p = round(top1 * (1.0 + SELL_MAX_SPREAD_FROM_TOP1_PCT), 2)
    suggested_p = min(suggested_p, max_safe_p)

    return suggested_p


def calculate_cluster_cartelera_average(
    cluster_methods: list[str],
    benchmarks: dict[str, Benchmark],
    anchor_method: Optional[str] = None,
    fallback_price: float = 0.0,
) -> tuple[float, float, str, list[float], Optional[datetime]]:
    """
    Calcula el TC promedio real de cartelera (Puesto #1) de los métodos del anuncio:
    1. Obtiene el precio Top 1 real de cartelera para cada método con datos válidos.
    2. Retorna: (promedio_top1, mejor_top1_del_grupo, metodo_lider, lista_top1s, timestamp_mas_reciente)
    """
    valid_top1s: list[tuple[str, float]] = []
    latest_ts: Optional[datetime] = None

    for m in cluster_methods:
        bm = benchmarks.get(m)
        if not bm or not bm.individual_prices:
            continue
        valid_p = [float(p) for p in bm.individual_prices if float(p) > 0]
        if valid_p:
            top1 = min(valid_p)
            valid_top1s.append((m, top1))
            if bm.timestamp and (latest_ts is None or bm.timestamp > latest_ts):
                latest_ts = bm.timestamp

    if not valid_top1s:
        base_p = fallback_price if fallback_price > 0 else 1600.0
        lead = anchor_method or (cluster_methods[0] if cluster_methods else "")
        return round(base_p, 2), round(base_p, 2), lead, [], None

    avg_price = round(sum(p for _, p in valid_top1s) / len(valid_top1s), 2)
    # Priorizar métodos con profundidad suficiente (>= 2 vendedores) para no disparar guardarraíl de liquidez
    liquid_methods = [
        m for m, _ in valid_top1s
        if benchmarks.get(m) and len([p for p in (benchmarks[m].individual_prices or []) if float(p) > 0]) >= 2
    ]
    if anchor_method and anchor_method in liquid_methods:
        leader_method = anchor_method
        best_top1 = next(p for m, p in valid_top1s if m == anchor_method)
    elif liquid_methods:
        leader_method = liquid_methods[0]
        best_top1 = next(p for m, p in valid_top1s if m == leader_method)
    elif anchor_method and any(m == anchor_method for m, _ in valid_top1s):
        leader_method = anchor_method
        best_top1 = next(p for m, p in valid_top1s if m == anchor_method)
    else:
        best_item = min(valid_top1s, key=lambda x: x[1])
        leader_method = best_item[0]
        best_top1 = best_item[1]
    leader_bm = benchmarks.get(leader_method)
    leader_prices = (
        [float(p) for p in leader_bm.individual_prices if float(p) > 0]
        if leader_bm and leader_bm.individual_prices
        else [p for _, p in valid_top1s]
    )
    return avg_price, best_top1, leader_method, leader_prices, latest_ts


def calculate_cluster_multi_method_sell_price(
    cluster_methods: list[str],
    benchmarks: dict[str, Benchmark],
    cluster_id: int,
    default_delta: float,
    anchor_method: str,
    fallback_price: float = 0.0,
) -> tuple[float, float, str, list[float], Optional[datetime]]:
    """
    Calcula el precio de venta óptimo para un cluster evaluando los métodos asignados:
    1. Obtiene precios competitivos Book-Aware para cada método del cluster con datos válidos.
    2. Aplica selección inteligente multi-método: toma el mejor precio competitivo usable
       del grupo mayorista sin arrodillarse ante el método más barato.
    3. Descarta anomalías que excedan el 1.5% del ancla o de la mediana del grupo.

    Retorna: (precio_sugerido, top1_referencia, metodo_lider, prices_top10_lider, timestamp_lider)
    """
    method_targets: dict[str, float] = {}
    method_top1s: dict[str, float] = {}
    method_prices: dict[str, list[float]] = {}
    method_timestamps: dict[str, Optional[datetime]] = {}

    for m in cluster_methods:
        bm = benchmarks.get(m)
        if not bm or not bm.individual_prices:
            continue
        valid_p = [float(p) for p in bm.individual_prices if float(p) > 0]
        if not valid_p:
            continue

        # Filtro anti-outliers (< 2.5% de la mediana)
        if len(valid_p) >= 3:
            sorted_p = sorted(valid_p)
            med = sorted_p[len(sorted_p) // 2]
            valid_p = [p for p in valid_p if p >= med * 0.975]

        if not valid_p:
            continue

        m_top1 = min(valid_p)
        method_top1s[m] = m_top1
        method_prices[m] = valid_p
        method_timestamps[m] = bm.timestamp

        # Objetivo individual por método con Book-Aware
        m_target = calculate_book_aware_sell_price(
            top1=m_top1,
            prices_top10=valid_p,
            cluster_id=cluster_id,
            default_delta=default_delta,
        )
        method_targets[m] = m_target

    if not method_targets:
        base_p = fallback_price if fallback_price > 0 else 1600.0
        return round(base_p + default_delta, 2), 0.0, anchor_method, [], None

    # Priorizar métodos con profundidad suficiente (>= 2 vendedores) para no disparar guardarraíl de liquidez
    liquid_methods = {m: t for m, t in method_targets.items() if len(method_prices[m]) >= 2}
    pool_targets = liquid_methods if liquid_methods else method_targets

    # Referencia del ancla dentro del pool
    anchor_target = pool_targets.get(anchor_method)
    anchor_top1 = method_top1s.get(anchor_method, min(method_top1s.values()))

    # Selección inteligente: tomar el mejor precio competitivo entre los métodos del grupo
    # evitando anomalías que excedan el 1.5% del ancla o de la mediana
    ref_base = anchor_target if anchor_target else (sum(pool_targets.values()) / len(pool_targets))
    usable_targets = {
        m: p for m, p in pool_targets.items()
        if p <= ref_base * 1.015
    }

    if not usable_targets:
        usable_targets = pool_targets

    # El método líder es el que ofrece la mejor cotización competitiva viable
    best_method = max(usable_targets, key=lambda m: usable_targets[m])
    suggested_price = usable_targets[best_method]
    ref_top1 = method_top1s.get(best_method, anchor_top1)
    ref_prices = method_prices.get(best_method, [])
    ref_ts = method_timestamps.get(best_method)

    return suggested_price, ref_top1, best_method, ref_prices, ref_ts


# Configuración canónica de los clusters de venta manual
SELL_CLUSTERS_CONFIG = [
    {
        "id": 1,
        "title": "Billeteras Masivas (Salida Rápida)",
        "methods": ["MercadoPagoNew", "LemonCash", "NaranjaX", "Beloapp", "UalaNew"],
        "anchor_method": "MercadoPagoNew",
        "default_delta": 0.35,
        "suggested_min": 15000.0,
        "speed_label": "⚡ Máxima (5 - 10 min)",
        "notes": "Mercado hiper-comprimido. Mantenerse en podio visible (#2/#3) para rotar inmediato.",
    },
    {
        "id": 2,
        "title": "Bancos Tradicionales (Tickets Altos)",
        "methods": ["SantanderArgentina", "bancogalicia", "BankArgentina", "BancoBrubankNew", "Reba"],
        "anchor_method": "SantanderArgentina",
        "default_delta": 1.80,
        "suggested_min": 80000.0,
        "speed_label": "🔥 Alta en horario bancario (15 - 25 min)",
        "notes": "Ideal para órdenes grandes ($300k - $1M ARS). Evita comisiones y límites de billeteras.",
    },
    {
        "id": 3,
        "title": "Fintechs Secundarias (Margen Premium)",
        "methods": ["personalpay", "Fiwind", "Prex", "bnaplus", "BancoDelSol"],
        "anchor_method": "personalpay",
        "default_delta": 2.20,
        "suggested_min": 30000.0,
        "speed_label": "🚀 Rápida en Fiwind / Buena en Personal Pay",
        "notes": "Los compradores pagan sobreprecio por saldos atrapados o arbitrajes entre apps.",
    },
]


class SellAdvisor:
    """
    Asesor inteligente de precios y organización de métodos para ventas manuales P2P.
    100% de solo lectura: extrae inteligencia de la base de datos local SQLite.
    """

    def __init__(self, db: Database):
        self.db = db

    def get_sell_advice(
        self,
        ticket_ref_crypto: float = 350.0,
        benchmarks: Optional[dict[str, Benchmark]] = None,
    ) -> list[ClusterAdvice]:
        """
        Genera la recomendación en tiempo real para los clusters de venta manual.

        Args:
            ticket_ref_crypto: Monto de venta de referencia para estimar ganancia extra en ARS (ej: 350 USDT).
            benchmarks: Opcional dict de benchmarks vivos en memoria; se fusiona con SQLite como respaldo.

        Returns:
            Lista de ClusterAdvice con precios sugeridos, podio y márgenes extras.
        """
        # Respaldo bidireccional: si benchmarks en memoria está vacío o incompleto, SQLite provee los datos
        db_bms = self.db.get_latest_benchmarks() if self.db else {}
        bms = {**db_bms, **(benchmarks or {})}

        def _is_valid_bm(bm: Optional[Benchmark]) -> bool:
            if not bm:
                return False
            if bm.individual_prices and any(float(p) > 0 for p in bm.individual_prices):
                return True
            return bool(bm.avg_top_n_price and bm.avg_top_n_price > 0)

        # Determinar el precio base de referencia en Mercado Pago (piso del mercado)
        mp_bm = bms.get("MercadoPagoNew")
        base_mp_price = 0.0
        if mp_bm and mp_bm.individual_prices:
            valid_p = [float(p) for p in mp_bm.individual_prices if float(p) > 0]
            if valid_p:
                base_mp_price = valid_p[0]
        if base_mp_price <= 0.0 and mp_bm and mp_bm.avg_top_n_price > 0:
            base_mp_price = float(mp_bm.avg_top_n_price)

        advice_list: list[ClusterAdvice] = []

        for c_cfg in SELL_CLUSTERS_CONFIG:
            c_id = c_cfg["id"]
            title = c_cfg["title"]
            methods = c_cfg["methods"]
            anchor = c_cfg["anchor_method"]
            delta = c_cfg["default_delta"]
            suggested_min = c_cfg["suggested_min"]
            speed = c_cfg["speed_label"]
            notes = c_cfg["notes"]

            suggested_p, top1, leader_m, prices_top10, bm_ts = calculate_cluster_multi_method_sell_price(
                cluster_methods=methods,
                benchmarks=bms,
                cluster_id=c_id,
                default_delta=delta,
                anchor_method=anchor,
                fallback_price=base_mp_price,
            )
            is_valid = top1 > 0
            if base_mp_price <= 0.0:
                base_mp_price = top1

            # Estimar puesto en el ranking con los precios vivos
            if prices_top10:
                pos_count = sum(1 for p in prices_top10 if p <= suggested_p) + 1
                if pos_count > len(prices_top10):
                    estimated_pos = f"Puesto #{pos_count}" if len(prices_top10) < 5 else f"Puesto #{pos_count} (Fuera de top {len(prices_top10)})"
                else:
                    estimated_pos = f"Puesto #{pos_count}"
            else:
                estimated_pos = "Puesto #2 o #3 (Podio)"

            # Calcular ganancia extra vs publicar al precio base de Mercado Pago
            extra_per_usdt = max(round(suggested_p - (base_mp_price + 0.35), 2), 0.0) if c_id > 1 else 0.0
            extra_ticket_ars = round(extra_per_usdt * ticket_ref_crypto, 0)

            # Calcular spread efectivamente aplicado
            actual_spread = round(suggested_p - top1, 2)

            advice = ClusterAdvice(
                cluster_id=c_id,
                title=title,
                methods=methods,
                anchor_method=leader_m,
                top1_price=top1,
                suggested_price=suggested_p,
                spread_added=actual_spread,
                estimated_position=estimated_pos,
                extra_profit_per_usdt=extra_per_usdt,
                estimated_extra_ticket_ars=extra_ticket_ars,
                suggested_min_ars=suggested_min,
                suggested_max_ars=0.0,  # 0.0 representa "Todo el saldo disponible"
                speed_label=speed,
                is_valid_data=is_valid,
                notes=notes,
                data_timestamp=bm_ts,
            )
            advice_list.append(advice)

        return advice_list
