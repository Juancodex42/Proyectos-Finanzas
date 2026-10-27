"""
Módulo de auditoría y validación estricta de reglas anti-baneo de Binance P2P.
Verifica que las decisiones de reposicionamiento cumplan las normativas de Binance SAPI v7.4.
Referencia de diseño: docs/REGLAS_ANTIBANEO_P2P.md
"""
import logging
from typing import Optional
from data.models import AntiBanViolation, MyAd, RepositionDecision
from config.settings import (
    MIN_AD_PRICE_DIFF_RATIO,
    GROUP_LIMIT_FACTORS,
    GROUP_INIT_MULTIPLIERS,
    GROUP_MIN_MULTIPLIERS,
    ASSET_DEFAULTS,
    STABLECOINS,
)

logger = logging.getLogger("antiban_validator")


class AntiBanValidator:
    """Inspector centralizado que audita decisiones de reposicionamiento antes de tocar Binance."""

    @classmethod
    def audit_asset_decisions(
        cls,
        asset: str,
        ad_decision_pairs: list[tuple[MyAd, RepositionDecision]],
        spot_price: float,
        price_step: float = 0.01,
        min_diff_ratio: float = MIN_AD_PRICE_DIFF_RATIO,
        fiat_rate: float = 1.0,
    ) -> list[AntiBanViolation]:
        """
        Audita un conjunto de decisiones de un mismo activo (típicamente G1, G2 y G3).
        Retorna la lista de violaciones encontradas. Si está vacía, el conjunto es 100% seguro.
        """
        violations: list[AntiBanViolation] = []

        # Filtrar solo los anuncios que estarán activos (no pausados y online o por actualizarse)
        active_pairs = [
            (ad, dec) for ad, dec in ad_decision_pairs
            if not dec.should_pause and (ad.status == 1 or dec.should_update)
        ]

        if not active_pairs:
            return violations

        # ── REGLA 1: Separación de precios entre grupos (Regla 5.1.3 / Error 187055) ──
        # Ningún par de anuncios del mismo activo puede tener una diferencia menor a min_diff_ratio (0.15%)
        active_prices = []
        for ad, dec in active_pairs:
            p = dec.new_price if (dec.new_price and dec.new_price > 0) else ad.current_price
            if p > 0:
                active_prices.append((ad.ad_group, p))

        # Ordenar por precio para verificar distancias adyacentes
        active_prices.sort(key=lambda x: x[1])
        for i in range(len(active_prices) - 1):
            grp_a, p_a = active_prices[i]
            grp_b, p_b = active_prices[i + 1]
            diff = abs(p_b - p_a)
            base_ref = max(p_a, p_b)
            required_diff = max(price_step, round(base_ref * min_diff_ratio, 2))

            if diff < (required_diff - 1e-4):
                violations.append(
                    AntiBanViolation(
                        rule_id="RULE_5_1_3_SEPARATION",
                        asset=asset,
                        group=grp_b,
                        message=(
                            f"Separación insuficiente entre G{grp_a} (${p_a:,.2f}) y G{grp_b} (${p_b:,.2f}): "
                            f"diferencia de ${diff:,.2f} ARS < requerida de ${required_diff:,.2f} ARS (0.15%). "
                            f"Riesgo de Error 187055 en Binance."
                        ),
                    )
                )

        # ── REGLA 2: Escalonamiento y unicidad de initAmount (Regla 5.1.1) ──────────
        # Binance prohíbe que dos anuncios del mismo par tengan idéntica cantidad inicial
        used_amounts: dict[float, int] = {}
        for ad, dec in active_pairs:
            amt = dec.new_init_amount if (dec.new_init_amount and dec.new_init_amount > 0) else ad.init_amount
            if amt and amt > 0:
                amt_rounded = round(amt, 6)
                if amt_rounded in used_amounts:
                    other_grp = used_amounts[amt_rounded]
                    violations.append(
                        AntiBanViolation(
                            rule_id="RULE_5_1_1_UNIQUE_AMOUNT",
                            asset=asset,
                            group=ad.ad_group,
                            message=(
                                f"Cantidad inicial colisiona con G{other_grp}: {amt_rounded:.6f} {asset}. "
                                f"Binance exige cantidades estrictamente diferentes entre anuncios."
                            ),
                        )
                    )
                else:
                    used_amounts[amt_rounded] = ad.ad_group

        # ── REGLAS 3 y 4: Consistencia de límites y capacidad de cripto ────────────
        for ad, dec in active_pairs:
            p = dec.new_price if (dec.new_price and dec.new_price > 0) else ad.current_price
            amt = dec.new_init_amount if (dec.new_init_amount and dec.new_init_amount > 0) else ad.init_amount
            min_trans = dec.new_min_trans_amount if (dec.new_min_trans_amount and dec.new_min_trans_amount > 0) else ad.min_trans_amount
            max_trans = dec.new_max_trans_amount if (dec.new_max_trans_amount and dec.new_max_trans_amount > 0) else ad.max_trans_amount

            if p <= 0:
                violations.append(
                    AntiBanViolation(
                        rule_id="RULE_INVALID_PRICE",
                        asset=asset,
                        group=ad.ad_group,
                        message=f"Precio inválido o nulo: ${p}",
                    )
                )
                continue

            # I-3: Capacidad de stock en ARS >= maxSingleTransAmount y minSingleTransAmount (Anti-187006 & Anti-187040)
            raw_surplus = getattr(ad, "surplus_amount", None)
            if raw_surplus is not None and ad.init_amount > 0:
                surplus = max(float(raw_surplus), 0.0)
                executed = max(ad.init_amount - surplus, 0.0)
            else:
                surplus = ad.init_amount
                executed = 0.0

            # Regla Anti-187040: Binance prohíbe que new_init_amount sea menor a lo ya ejecutado en la orden
            if dec.new_init_amount is not None and executed > 0 and dec.new_init_amount < (executed - 1e-6):
                violations.append(
                    AntiBanViolation(
                        rule_id="RULE_ANTI_187040_INIT_AMOUNT_LT_EXECUTED",
                        asset=asset,
                        group=ad.ad_group,
                        message=(
                            f"Cantidad inicial ({dec.new_init_amount:.6f} {asset}) es menor a lo ya ejecutado "
                            f"({executed:.6f} {asset}). Causará Error 187040 en Binance."
                        ),
                    )
                )

            effective_tradable_crypto = max(dec.new_init_amount - executed, 0.0) if dec.new_init_amount is not None else surplus
            stock_capacity_ars = effective_tradable_crypto * p

            # Regla Anti-187006: minSingleTransAmount no puede superar el remanente disponible del anuncio
            if min_trans > 0 and effective_tradable_crypto > 0:
                if min_trans > (stock_capacity_ars + 1.0) * 1.005:
                    violations.append(
                        AntiBanViolation(
                            rule_id="RULE_ANTI_187006_MIN_TRANS_GT_CAPACITY",
                            asset=asset,
                            group=ad.ad_group,
                            message=(
                                f"Límite mínimo (${min_trans:,.0f} ARS) excede la capacidad remanente tradable "
                                f"({effective_tradable_crypto:.6f} {asset} * ${p:,.2f} = ${stock_capacity_ars:,.0f} ARS). "
                                f"Causará Error 187006 en Binance."
                            ),
                        )
                    )

            if effective_tradable_crypto > 0 and max_trans > 0:
                # Tolerancia de redondeo de $1 ARS o 0.5%
                if max_trans > (stock_capacity_ars + 1.0) * 1.005:
                    violations.append(
                        AntiBanViolation(
                            rule_id="RULE_MAX_TRANS_CAPACITY",
                            asset=asset,
                            group=ad.ad_group,
                            message=(
                                f"Límite máximo (${max_trans:,.0f} ARS) excede la capacidad del anuncio "
                                f"({effective_tradable_crypto:.4f} {asset} * ${p:,.2f} = ${stock_capacity_ars:,.0f} ARS)."
                            ),
                        )
                    )

            # I-4: Rango válido: minSingleTransAmount < maxSingleTransAmount
            if min_trans > 0 and max_trans > 0 and min_trans > max_trans:
                violations.append(
                    AntiBanViolation(
                        rule_id="RULE_LIMITS_INVERTED",
                        asset=asset,
                        group=ad.ad_group,
                        message=f"Límite mínimo (${min_trans:,.0f}) es mayor al límite máximo (${max_trans:,.0f} ARS).",
                    )
                )

            # I-4 bis: Piso mínimo del activo según configuración y multiplicador de grupo
            defaults = ASSET_DEFAULTS.get(asset, {})
            floor_min = defaults.get("min_trans", 10000.0)
            expected_floor = round(floor_min * GROUP_MIN_MULTIPLIERS.get(ad.ad_group, 1.0), 0)
            if min_trans > 0 and min_trans < expected_floor * 0.99:
                violations.append(
                    AntiBanViolation(
                        rule_id="RULE_BELOW_FLOOR_MIN",
                        asset=asset,
                        group=ad.ad_group,
                        message=f"Límite mínimo (${min_trans:,.0f}) por debajo del piso base configurado (${expected_floor:,.0f} ARS).",
                        severity="WARNING",
                    )
                )

        # ── REGLA 6: Collar de seguridad respecto a Spot (Protección patrimonial) ──
        # La referencia patrimonial en ARS se calcula multiplicando spot (USD) por fiat_rate (ARS/USDT).
        # Si spot_price ya viene convertido a ARS (o fiat_rate == 1.0), se usa directamente spot_price.
        ref_spot_ars = spot_price
        if fiat_rate > 1.0:
            if asset in STABLECOINS:
                ref_spot_ars = fiat_rate
            else:
                ref_spot_ars = spot_price * fiat_rate

        if ref_spot_ars > 50.0:
            for ad, dec in active_pairs:
                p = dec.new_price if (dec.new_price and dec.new_price > 0) else ad.current_price
                if p <= 0:
                    continue
                ratio = p / ref_spot_ars if ref_spot_ars > 0 else 1.0
                if ratio < 0.60 or ratio > 1.40:
                    violations.append(
                        AntiBanViolation(
                            rule_id="RULE_SPOT_COLLAR_EXCEEDED",
                            asset=asset,
                            group=ad.ad_group,
                            message=(
                                f"Precio fuera de collar (${p:,.2f} vs ref ${ref_spot_ars:,.2f}, ratio: {ratio:.2f}). "
                                f"Posible anomalía severa de mercado."
                            ),
                        )
                    )

        return violations

    @classmethod
    def audit_all_cycle_decisions(
        cls,
        ads: list[MyAd],
        decisions: dict[str, RepositionDecision],
        spot_prices: dict[str, float],
        fiat_rate: float = 1.0,
    ) -> dict[str, list[AntiBanViolation]]:
        """
        Audita el ciclo completo agrupando por activo.
        Retorna diccionario {asset: [violaciones]}.
        """
        # Agrupar pares (ad, decision) por activo
        by_asset: dict[str, list[tuple[MyAd, RepositionDecision]]] = {}
        for ad in ads:
            dec = decisions.get(ad.adv_no)
            if not dec:
                continue
            by_asset.setdefault(ad.asset, []).append((ad, dec))

        results: dict[str, list[AntiBanViolation]] = {}
        for asset, pairs in by_asset.items():
            spot = spot_prices.get(asset, 1.0)
            violations = cls.audit_asset_decisions(
                asset=asset,
                ad_decision_pairs=pairs,
                spot_price=spot,
                fiat_rate=fiat_rate,
            )
            if violations:
                results[asset] = violations

        return results
