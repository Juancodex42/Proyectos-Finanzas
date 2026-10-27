"""
Script de Stress Test y Simulación Anti-Baneo Realista.
Somete a los algoritmos de Repositioner, WarDetector y MarketScanner a 6 escenarios hostiles extremos:
1. Guerra de precios relámpago (Blitzkrieg pricing).
2. Pinza de colisión milimétrica (Triple Competitor Tie).
3. Flash Crash de Spot (-25% en 1 ciclo).
4. Competidor señuelo / Troll Outlier (+80% de sobreprecio).
5. Asfixia progresiva de liquidez ($1M -> $4K ARS).
6. Micro-oscilación pasiva de Spot (Anti-Error 83714).

Ejecución:
    python scripts/stress_test_antiblocking.py [--iterations N] [--verbose]
"""
import sys
import os
import time
import argparse
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Agregar raíz del proyecto al sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import (
    PAYMENT_METHOD_GROUPS,
    MIN_AD_PRICE_DIFF_RATIO,
    GROUP_INIT_MULTIPLIERS,
    GROUP_LIMIT_FACTORS,
    ASSET_DEFAULTS,
    STABLECOINS,
)
from data.models import (
    MyAd,
    ExchangeRate,
    Benchmark,
    BotConfig,
    RepositionDecision,
)
from core.pricing.buy_repositioner import Repositioner
from core.war_detector import WarDetector
from core.market_scanner import MarketScanner
from core.liquidity.liquidity_manager import LiquidityTracker
from core.antiban_validator import AntiBanValidator, AntiBanViolation


class MockAdsManager:
    """Mock de AdsManager que registra llamadas de actualización sin tocar Binance."""

    def __init__(self):
        self.update_calls = []
        self.is_83714_active = False

    async def update_ad_params(
        self,
        adv_no,
        price=None,
        init_amount=None,
        min_trans_amount=None,
        max_trans_amount=None,
        surplus_amount=None,
    ):
        self.update_calls.append({
            "adv_no": adv_no,
            "price": price,
            "init_amount": init_amount,
            "min_trans_amount": min_trans_amount,
            "max_trans_amount": max_trans_amount,
            "surplus_amount": surplus_amount,
        })
        return True

    async def pause_ad(self, adv_no):
        return True

    async def resume_ad(self, adv_no):
        return True


def create_test_ads(asset: str = "USDT") -> list[MyAd]:
    """Crea 3 anuncios de prueba (G1, G2, G3) para un activo."""
    defaults = ASSET_DEFAULTS.get(asset, {"min_trans": 10000.0, "max_trans": 500000.0, "init_amount": 100.0})
    return [
        MyAd(
            adv_no=f"{asset.lower()}_ad_g1",
            asset=asset,
            ad_group=1,
            current_price=1400.0,
            payment_methods=["MercadoPagoNew"],
            status=1,
            init_amount=defaults["init_amount"] * 1.0,
            surplus_amount=defaults["init_amount"] * 1.0,
            min_trans_amount=defaults["min_trans"] * 1.0,
            max_trans_amount=defaults["max_trans"] * 0.99,
        ),
        MyAd(
            adv_no=f"{asset.lower()}_ad_g2",
            asset=asset,
            ad_group=2,
            current_price=1397.0,
            payment_methods=["SantanderArgentina"],
            status=1,
            init_amount=defaults["init_amount"] * 0.95,
            surplus_amount=defaults["init_amount"] * 0.95,
            min_trans_amount=defaults["min_trans"] * 1.15,
            max_trans_amount=defaults["max_trans"] * 0.98,
        ),
        MyAd(
            adv_no=f"{asset.lower()}_ad_g3",
            asset=asset,
            ad_group=3,
            current_price=1394.0,
            payment_methods=["Prex"],
            status=1,
            init_amount=defaults["init_amount"] * 0.90,
            surplus_amount=defaults["init_amount"] * 0.90,
            min_trans_amount=defaults["min_trans"] * 1.30,
            max_trans_amount=defaults["max_trans"] * 0.97,
        ),
    ]


def make_comp(
    asset: str,
    method: str,
    price_ars: float,
    min_trans: float = 10000.0,
    max_trans: float = 300000.0,
    adv_no: str = "comp_1",
    position: int = 1,
    orders_count: int = 50,
    completion_rate: float = 0.95,
) -> ExchangeRate:
    return ExchangeRate(
        asset=asset,
        payment_method=method,
        price_ars=price_ars,
        spot_price_usdt=1.0,
        tc_implicito=price_ars,
        position=position,
        advertiser_no=adv_no,
        advertiser_nickname="TestTrader",
        advertiser_completion_rate=completion_rate,
        advertiser_order_count=orders_count,
        min_single_trans_amount=min_trans,
        max_single_trans_amount=max_trans,
        timestamp=datetime.now(),
    )


def make_bm(method: str, price: float = 1450.0) -> Benchmark:
    return Benchmark(
        payment_method=method,
        avg_top_n_price=price,
        individual_prices=[price],
        volume_filter=200000.0,
        timestamp=datetime.now(),
    )


async def run_scenario_1_blitzkrieg_war(verbose: bool = False) -> dict:
    """
    Escenario 1: Guerra de precios relámpago.
    Un competidor agresivo sube su precio en pasos de $2.00 cada pocos segundos (8 escaladas).
    Verifica que WarDetector contenga la guerra en la 3ra subida y que el bot no se sobrecaliente.
    """
    mock_db = MagicMock()
    mock_db.get_active_wars = MagicMock(return_value={})
    mock_db.save_war = MagicMock()
    mock_db.clear_war = MagicMock()
    mock_db.save_price_change = MagicMock()

    war_detector = WarDetector(mock_db)
    ads_manager = MockAdsManager()
    mock_liquidity = MagicMock()
    mock_liquidity.available_balance = 500000.0
    mock_liquidity.balance = 500000.0
    scanner = MarketScanner(client=MagicMock(), spot_client=MagicMock(), db=mock_db)

    repo = Repositioner(
        ads_manager=ads_manager,
        scanner=scanner,
        liquidity=mock_liquidity,
        war_detector=war_detector,
        db=mock_db,
    )

    config = BotConfig(price_step=0.01, margin_min=10.0, volume_ref=200000.0)
    ads = create_test_ads("USDT")
    ad = ads[0]  # G1 MercadoPagoNew

    benchmarks = {"MercadoPagoNew": make_bm("MercadoPagoNew", 1450.0)}
    spot_prices = {"USDT": 1.0}

    war_triggered_at = None
    decisions_history = []

    base_price = 1400.0
    for step in range(1, 9):
        comp_price = base_price + (step * 2.0)
        competitors = {
            ("USDT", "MercadoPagoNew"): [
                make_comp("USDT", "MercadoPagoNew", comp_price, adv_no="hostile_comp_1")
            ]
        }

        decision = await repo.evaluate_ad(
            ad=ad,
            competitors=competitors,
            benchmarks=benchmarks,
            spot_prices=spot_prices,
            config=config,
        )
        decisions_history.append((step, comp_price, decision))

        # Simular que el bot actualizó su precio
        if decision.should_update and decision.new_price > 0:
            ad.current_price = decision.new_price

        is_war = war_detector.is_in_war("USDT", "MercadoPagoNew")
        if is_war and war_triggered_at is None:
            war_triggered_at = step

    success = (war_triggered_at in [3, 4])
    if verbose:
        print(f"  [Escenario 1] Guerra detectada en el paso: {war_triggered_at} (Esperado: 3 o 4)")
        for step, c_price, dec in decisions_history:
            status = "FRENADO_GUERRA" if dec.reason == "war_detected" else ("SUBE" if dec.should_update else "PAUSA/NOOP")
            print(f"    Paso {step}: Comp=${c_price:.2f} -> Bot=${dec.new_price:.2f} | Razón: {dec.reason} [{status}]")

    return {
        "name": "Blitzkrieg Price War",
        "passed": success,
        "escalations_to_contain": war_triggered_at,
        "violations": [],
    }


async def run_scenario_2_precision_squeeze(verbose: bool = False) -> dict:
    """
    Escenario 2: Pinza de colisión milimétrica.
    Competidores en G1, G2 y G3 convergen exactamente en el mismo precio ($1,410.00).
    Verifica que el algoritmo anti-colisión fuerce una separación mínima de >= 0.15% entre grupos.
    """
    mock_db = MagicMock()
    mock_db.save_price_change = MagicMock()
    war_detector = MagicMock()
    war_detector.is_in_war = MagicMock(return_value=False)
    war_detector.check_escalation = MagicMock(return_value=False)
    ads_manager = MockAdsManager()
    mock_liquidity = MagicMock()
    mock_liquidity.available_balance = 500000.0
    mock_liquidity.balance = 500000.0
    scanner = MarketScanner(client=MagicMock(), spot_client=MagicMock(), db=mock_db)

    repo = Repositioner(
        ads_manager=ads_manager,
        scanner=scanner,
        liquidity=mock_liquidity,
        war_detector=war_detector,
        db=mock_db,
    )

    config = BotConfig(price_step=0.01, margin_min=10.0, volume_ref=200000.0)
    ads = create_test_ads("USDT")

    # Mismo precio para los 3 métodos representativos
    tied_price = 1410.00
    competitors = {
        ("USDT", "MercadoPagoNew"): [make_comp("USDT", "MercadoPagoNew", tied_price, adv_no="c1")],
        ("USDT", "SantanderArgentina"): [make_comp("USDT", "SantanderArgentina", tied_price, adv_no="c2")],
        ("USDT", "Prex"): [make_comp("USDT", "Prex", tied_price, adv_no="c3")],
    }
    benchmarks = {
        "MercadoPagoNew": make_bm("MercadoPagoNew", 1450.0),
        "SantanderArgentina": make_bm("SantanderArgentina", 1450.0),
        "Prex": make_bm("Prex", 1450.0),
    }

    # Evaluar individualmente
    evaluated_pairs = []
    for ad in ads:
        d = await repo.evaluate_ad(ad, competitors, benchmarks, {"USDT": 1.0}, config)
        evaluated_pairs.append((ad, d))

    # Resolver colisiones
    resolved_pairs = repo.resolve_asset_price_collisions(
        asset="USDT",
        evaluated=evaluated_pairs,
        config=config,
        all_asset_ads=ads,
    )

    # Auditar con AntiBanValidator
    violations = AntiBanValidator.audit_asset_decisions("USDT", resolved_pairs, spot_price=1.0)

    p1 = resolved_pairs[0][1].new_price
    p2 = resolved_pairs[1][1].new_price
    p3 = resolved_pairs[2][1].new_price

    passed = (len(violations) == 0) and (p1 > p2 > p3)
    diff_1_2 = abs(p1 - p2)
    diff_2_3 = abs(p2 - p3)

    if verbose:
        print(f"  [Escenario 2] Precios post-colisión: G1=${p1:.2f}, G2=${p2:.2f}, G3=${p3:.2f}")
        print(f"    Separación G1-G2: ${diff_1_2:.2f} ARS | G2-G3: ${diff_2_3:.2f} ARS (Min requerido: ${tied_price * MIN_AD_PRICE_DIFF_RATIO:.2f})")
        if violations:
            for v in violations:
                print(f"    ❌ Violación: {v}")

    return {
        "name": "Precision Squeeze Anti-Collision",
        "passed": passed,
        "violations": violations,
        "separation_g1_g2": diff_1_2,
        "separation_g2_g3": diff_2_3,
    }


async def run_scenario_3_flash_crash(verbose: bool = False) -> dict:
    """
    Escenario 3: Flash Crash de Spot (-25% en 1 ciclo).
    El precio spot de BTC cae de $65,000 a $48,750 mientras los competidores en el libro P2P
    aún mantienen precios altos de compra.
    Verifica que el bot no pague de más y respete el techo de margen.
    """
    mock_db = MagicMock()
    war_detector = MagicMock()
    war_detector.is_in_war = MagicMock(return_value=False)
    war_detector.check_escalation = MagicMock(return_value=False)
    ads_manager = MockAdsManager()
    mock_liquidity = MagicMock()
    mock_liquidity.available_balance = 2000000.0
    scanner = MarketScanner(client=MagicMock(), spot_client=MagicMock(), db=mock_db)

    repo = Repositioner(
        ads_manager=ads_manager,
        scanner=scanner,
        liquidity=mock_liquidity,
        war_detector=war_detector,
        db=mock_db,
    )

    config = BotConfig(price_step=1.0, margin_min=15.0, volume_ref=200000.0)
    ads = create_test_ads("BTC")
    ad = ads[0]

    # Competidores comprando a precio previo al crash ($65,000 * 1400 = $91,000,000 ARS)
    old_btc_ars = 91_000_000.0
    competitors = {
        ("BTC", "MercadoPagoNew"): [make_comp("BTC", "MercadoPagoNew", old_btc_ars, adv_no="comp_slow")]
    }
    benchmarks = {"MercadoPagoNew": make_bm("MercadoPagoNew", 1420.0)}

    # Spot cae 25%: nuevo precio spot = $48,750 USDT
    crashed_spot = {"BTC": 48_750.0, "USDT": 1.0}

    decision = await repo.evaluate_ad(ad, competitors, benchmarks, crashed_spot, config)

    # El nuevo precio calculado del bot debe estar estrictamente limitado por el nuevo valor de mercado:
    # Máximo precio pagable ≈ crashed_spot * (benchmark - margin) = 48,750 * (1420 - 15) = $68,493,750 ARS
    max_safe_price = 48_750.0 * (1420.0 - config.margin_min)
    passed = decision.new_price <= max_safe_price

    if verbose:
        print(f"  [Escenario 3] Flash Crash Spot BTC (-25%):")
        print(f"    Competidor dormido P2P: ${old_btc_ars:,.0f} ARS")
        print(f"    Precio seguro máximo:   ${max_safe_price:,.0f} ARS")
        print(f"    Precio decidido bot:    ${decision.new_price:,.0f} ARS | Razón: {decision.reason}")

    return {
        "name": "Spot Flash Crash Protection",
        "passed": passed,
        "bot_price": decision.new_price,
        "max_safe_price": max_safe_price,
        "violations": [],
    }


def run_scenario_4_troll_outlier(verbose: bool = False) -> dict:
    """
    Escenario 4: Competidor Señuelo / Troll Outlier (+80%).
    Un anunciante coloca un precio absurdo de $2,600 ARS por USDT (83% sobre mercado).
    Verifica que el detector de anomalías de MarketScanner lo descarte.
    """
    scanner = MarketScanner(client=MagicMock(), spot_client=MagicMock(), db=MagicMock())

    competitors = [
        make_comp("USDT", "MercadoPagoNew", 2600.00, adv_no="troll", orders_count=50, completion_rate=0.95),
        make_comp("USDT", "MercadoPagoNew", 1425.00, adv_no="legit_1", orders_count=80, completion_rate=0.98),
        make_comp("USDT", "MercadoPagoNew", 1424.50, adv_no="legit_2", orders_count=120, completion_rate=0.99),
        make_comp("USDT", "MercadoPagoNew", 1423.00, adv_no="legit_3", orders_count=200, completion_rate=0.97),
    ]

    best = scanner.get_best_competitor(competitors)
    passed = (best is not None) and (best.advertiser_no == "legit_1") and (best.price_ars == 1425.00)

    if verbose:
        selected_no = best.advertiser_no if best else "None"
        selected_p = best.price_ars if best else 0.0
        print(f"  [Escenario 4] Anuncio Troll ($2600) vs Legit ($1425): Seleccionado {selected_no} (${selected_p:.2f})")

    return {
        "name": "Troll Outlier Rejection",
        "passed": passed,
        "selected_competitor": best.advertiser_no if best else None,
        "violations": [],
    }


async def run_scenario_5_liquidity_asphyxiation(verbose: bool = False) -> dict:
    """
    Escenario 5: Asfixia progresiva de liquidez.
    El balance cae de $1,000,000 -> $50,000 -> $12,500 -> $4,000 ARS.
    Verifica que los grupos se pausen ordenadamente sin violar límites de Binance.
    """
    mock_db = MagicMock()
    war_detector = MagicMock()
    war_detector.is_in_war = MagicMock(return_value=False)
    war_detector.check_escalation = MagicMock(return_value=False)
    ads_manager = MockAdsManager()

    mock_liquidity = MagicMock()
    scanner = MarketScanner(client=MagicMock(), spot_client=MagicMock(), db=mock_db)

    repo = Repositioner(
        ads_manager=ads_manager,
        scanner=scanner,
        liquidity=mock_liquidity,
        war_detector=war_detector,
        db=mock_db,
    )

    config = BotConfig(price_step=0.01, margin_min=10.0, volume_ref=200000.0)
    ads = create_test_ads("USDT")

    competitors = {
        ("USDT", "MercadoPagoNew"): [make_comp("USDT", "MercadoPagoNew", 1410.0, adv_no="c1")],
        ("USDT", "SantanderArgentina"): [make_comp("USDT", "SantanderArgentina", 1405.0, adv_no="c2")],
        ("USDT", "Prex"): [make_comp("USDT", "Prex", 1400.0, adv_no="c3")],
    }
    benchmarks = {
        "MercadoPagoNew": make_bm("MercadoPagoNew", 1450.0),
        "SantanderArgentina": make_bm("SantanderArgentina", 1450.0),
        "Prex": make_bm("Prex", 1450.0),
    }

    balances_test = [
        (1_000_000.0, [False, False, False]),  # Todos activos (liquidez plena)
        (50_000.0,    [False, False, False]),  # Todos activos (límites adaptados)
        (13_000.0,    [False, False, True]),   # G3 pausado ($13k * 0.97 = $12,610 < piso G3 de $13k)
        (11_000.0,    [False, True, True]),    # G2 y G3 pausados ($11k * 0.98 = $10,780 < piso G2 de $11.5k), solo G1 activo
        (4_000.0,     [True, True, True]),     # Todos pausados ($4k < piso G1 de $10k)
    ]

    all_passed = True
    all_violations = []

    for bal, expected_pauses in balances_test:
        mock_liquidity.available_balance = bal
        mock_liquidity.balance = bal

        decisions = []
        for i, ad in enumerate(ads):
            d = await repo.evaluate_ad(ad, competitors, benchmarks, {"USDT": 1.0}, config)
            decisions.append(d)
            if d.should_pause != expected_pauses[i]:
                all_passed = False

        # Auditar invariantes con AntiBanValidator
        pairs = [(ads[i], decisions[i]) for i in range(len(ads))]
        viols = AntiBanValidator.audit_asset_decisions("USDT", pairs, spot_price=1.0)
        all_violations.extend(viols)

    if verbose:
        print(f"  [Escenario 5] Asfixia de Liquidez: Resultado={all_passed} | Violaciones={len(all_violations)}")

    return {
        "name": "Progressive Liquidity Asphyxiation",
        "passed": all_passed and (len(all_violations) == 0),
        "violations": all_violations,
    }


async def run_scenario_6_passive_flapping(verbose: bool = False) -> dict:
    """
    Escenario 6: Micro-fluctuación pasiva de Spot (Anti-Error 83714).
    El spot fluctúa levemente (0.03%) sin cambio en competidores.
    Verifica que la histéresis frene las ediciones pasivas (0 llamadas API emitidas).
    """
    mock_db = MagicMock()
    war_detector = MagicMock()
    war_detector.is_in_war = MagicMock(return_value=False)
    war_detector.check_escalation = MagicMock(return_value=False)
    ads_manager = MockAdsManager()
    mock_liquidity = MagicMock()
    mock_liquidity.available_balance = 500000.0
    mock_liquidity.balance = 500000.0
    scanner = MarketScanner(client=MagicMock(), spot_client=MagicMock(), db=mock_db)

    repo = Repositioner(
        ads_manager=ads_manager,
        scanner=scanner,
        liquidity=mock_liquidity,
        war_detector=war_detector,
        db=mock_db,
    )

    config = BotConfig(price_step=0.01, margin_min=10.0, volume_ref=200000.0)
    ads = create_test_ads("BTC")
    ad = ads[0]
    ad.current_price = 84_348_000.0
    ad.init_amount = 0.005928
    ad.surplus_amount = 0.005928
    ad.min_trans_amount = 225_000.0
    ad.max_trans_amount = 495_000.0

    competitors = {("BTC", "MercadoPagoNew"): []}
    benchmarks = {"MercadoPagoNew": make_bm("MercadoPagoNew", 1420.0)}

    # Registrar que se actualizó hace 10 segundos (cooldown activo = 120s)
    repo._last_update_ts[ad.adv_no] = time.time() - 10.0

    # 3. Micro-variación del spot de BTC: 0.03% (muy por debajo de PASSIVE_PRICE_HYSTERESIS_PCT = 0.15%)
    flapping_spot = {"BTC": 60018.0, "USDT": 1.0}

    results = await repo.run_cycle([ad], competitors, benchmarks, flapping_spot, config)

    # Debe ser frenado por passive hold / no-op (0 llamadas de actualización a Binance)
    api_calls = len(ads_manager.update_calls)
    passed = (len(results) == 0) and (api_calls == 0)

    if verbose:
        print(f"  [Escenario 6] Flapping pasivo spot: Actualizados={len(results)} | Llamadas API={api_calls}")

    return {
        "name": "Anti-83714 Passive Flapping Hold",
        "passed": passed,
        "api_calls_made": api_calls,
        "violations": [],
    }


async def run_full_stress_suite(iterations: int = 100, verbose: bool = False):
    """Ejecuta el conjunto completo de escenarios en bucle de estrés."""
    print("=" * 65)
    print(f"🚀 INICIANDO STRESS TEST ANTI-BANEO ({iterations} ITERACIONES)")
    print("=" * 65)

    stats = {
        "Blitzkrieg Price War": {"passed": 0, "failed": 0},
        "Precision Squeeze Anti-Collision": {"passed": 0, "failed": 0},
        "Spot Flash Crash Protection": {"passed": 0, "failed": 0},
        "Troll Outlier Rejection": {"passed": 0, "failed": 0},
        "Progressive Liquidity Asphyxiation": {"passed": 0, "failed": 0},
        "Anti-83714 Passive Flapping Hold": {"passed": 0, "failed": 0},
    }

    start_time = time.time()
    total_violations = 0

    for i in range(1, iterations + 1):
        is_last = (i == iterations)
        show_v = verbose or (is_last and verbose)

        r1 = await run_scenario_1_blitzkrieg_war(verbose=(i == 1 and verbose))
        r2 = await run_scenario_2_precision_squeeze(verbose=(i == 1 and verbose))
        r3 = await run_scenario_3_flash_crash(verbose=(i == 1 and verbose))
        r4 = run_scenario_4_troll_outlier(verbose=(i == 1 and verbose))
        r5 = await run_scenario_5_liquidity_asphyxiation(verbose=(i == 1 and verbose))
        r6 = await run_scenario_6_passive_flapping(verbose=(i == 1 and verbose))

        for r in [r1, r2, r3, r4, r5, r6]:
            name = r["name"]
            if r["passed"]:
                stats[name]["passed"] += 1
            else:
                stats[name]["failed"] += 1
            if r.get("violations"):
                total_violations += len(r["violations"])

        if i % (max(1, iterations // 5)) == 0 or i == iterations:
            print(f"  • Progreso: {i}/{iterations} iteraciones completadas...")

    elapsed = time.time() - start_time
    print("\n" + "=" * 65)
    print(f"📊 RESULTADOS DEL STRESS TEST ({iterations} ciclos en {elapsed:.2f}s)")
    print("=" * 65)

    all_passed = True
    for name, s in stats.items():
        pass_rate = (s["passed"] / iterations) * 100
        icon = "✅" if s["failed"] == 0 else "❌"
        print(f"  {icon} {name:<36}: {s['passed']}/{iterations} ({pass_rate:.1f}%)")
        if s["failed"] > 0:
            all_passed = False

    print("-" * 65)
    print(f"  🛡️ Violaciones de reglas de Binance (Invariantes): {total_violations}")
    if all_passed and total_violations == 0:
        print("  🟢 VEREDICTO: ALGORITMO 100% ROBUSTO Y BLINDADO CONTRA BANEOS")
    else:
        print("  🔴 VEREDICTO: SE ENCONTRARON VULNERABILIDADES A REVISAR")
    print("=" * 65 + "\n")

    return all_passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stress Test Anti-Baneo Realista")
    parser.add_argument("--iterations", type=int, default=100, help="Cantidad de iteraciones")
    parser.add_argument("--verbose", action="store_true", help="Mostrar detalle de cada escenario")
    args = parser.parse_args()

    asyncio.run(run_full_stress_suite(iterations=args.iterations, verbose=args.verbose))
