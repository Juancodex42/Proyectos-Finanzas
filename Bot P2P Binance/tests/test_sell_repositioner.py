import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from core.pricing.sell_repositioner import SellRepositioner
from data.models import Benchmark, MyAd, SellDecision


class TestSellRepositioner(unittest.TestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_ads = MagicMock()
        self.mock_profit = MagicMock()
        self.mock_fiwind = MagicMock()
        self.repositioner = SellRepositioner(
            db=self.mock_db,
            ads_manager=self.mock_ads,
            profit_tracker=self.mock_profit,
            fiwind_client=self.mock_fiwind,
        )

    def test_resolve_sell_collisions_strict_separation(self):
        """Verifica que entre G1, G2 y G3 se aplique la escalera de $0.35 ARS y supere los $0.15 de Binance."""
        decisions = [
            SellDecision(
                cluster_id=1,
                title="Billeteras",
                anchor_method="MercadoPagoNew",
                suggested_price=1585.00,
                top1_price=1584.50,
                spread_added=0.50,
                estimated_position="Puesto #2",
                wac_cost=1570.0,
                fiwind_bid=1580.0,
            ),
            # Supongamos que G2 calculó 1585.10 (demasiado cerca de G1)
            SellDecision(
                cluster_id=2,
                title="Bancos",
                anchor_method="SantanderArgentina",
                suggested_price=1585.10,
                top1_price=1584.50,
                spread_added=0.60,
                estimated_position="Puesto #2",
                wac_cost=1570.0,
                fiwind_bid=1580.0,
            ),
            # Supongamos que G3 calculó 1585.20 (también demasiado cerca)
            SellDecision(
                cluster_id=3,
                title="Fintechs",
                anchor_method="personalpay",
                suggested_price=1585.20,
                top1_price=1584.50,
                spread_added=0.70,
                estimated_position="Puesto #2",
                wac_cost=1570.0,
                fiwind_bid=1580.0,
            ),
        ]

        resolved = self.repositioner.resolve_sell_collisions(decisions, available_crypto_stock=350.0)
        self.assertEqual(len(resolved), 3)

        p1 = resolved[0].suggested_price
        p2 = resolved[1].suggested_price
        p3 = resolved[2].suggested_price

        # G3 (1585.20) es el más caro del mercado -> Anuncio Base (1585.20)
        # G2 (Bancos) es el del medio -> Base + $0.35 = 1585.55
        # G1 (Billeteras, el más líquido) -> al final, Base + $0.70 = 1585.90
        self.assertEqual(p3, 1585.20)
        self.assertEqual(p2, 1585.55)
        self.assertEqual(p1, 1585.90)

        # Separación exacta de $0.35 ARS
        diff_1_2 = round(p1 - p2, 2)
        diff_2_3 = round(p2 - p3, 2)
        self.assertEqual(diff_1_2, 0.35)
        self.assertEqual(diff_2_3, 0.35)

        # Supera con creces el límite de solapamiento de Binance [X-0.15, X+0.15]
        self.assertGreater(diff_1_2, 0.15)
        self.assertGreater(diff_2_3, 0.15)

    def test_resolve_sell_collisions_spread_first_anchors_highest_illiquid(self):
        """Verifica que en SPREAD_FIRST se tome el más caro de los ilíquidos como base y MP quede arriba de todo."""
        decisions = [
            SellDecision(
                cluster_id=1,
                title="Billeteras",
                anchor_method="MercadoPagoNew",
                suggested_price=1605.00,  # Líquido, precio de libro bajo
                top1_price=1604.50,
                spread_added=0.50,
                estimated_position="Puesto #2",
                wac_cost=1570.0,
                fiwind_bid=1580.0,
            ),
            SellDecision(
                cluster_id=2,
                title="Bancos",
                anchor_method="SantanderArgentina",
                suggested_price=1615.00,  # Ilíquido intermedio
                top1_price=1614.50,
                spread_added=0.50,
                estimated_position="Puesto #2",
                wac_cost=1570.0,
                fiwind_bid=1580.0,
            ),
            SellDecision(
                cluster_id=3,
                title="Fintechs",
                anchor_method="personalpay",
                suggested_price=1622.00,  # Ilíquido más caro
                top1_price=1621.50,
                spread_added=0.50,
                estimated_position="Puesto #2",
                wac_cost=1570.0,
                fiwind_bid=1580.0,
            ),
        ]

        resolved = self.repositioner.resolve_sell_collisions(decisions, available_crypto_stock=350.0)
        self.assertEqual(len(resolved), 3)

        p1 = resolved[0].suggested_price  # G1 (MP - Billeteras)
        p2 = resolved[1].suggested_price  # G2 (Bancos)
        p3 = resolved[2].suggested_price  # G3 (Fintechs)

        # Base = más caro del mercado = G3 (1622.00)
        # G3 (Fintechs) es el más caro del mercado -> pasa a ser nuestro anuncio base (1622.00)
        # G2 (Bancos) es el del medio -> Base + $0.35 = 1622.35
        # G1 (Mercado Pago, el más líquido) -> al final, Base + $0.70 = 1622.70
        self.assertEqual(p3, 1622.00)
        self.assertEqual(p2, 1622.35)
        self.assertEqual(p1, 1622.70)

        # Verificar que MP sea estrictamente el más caro (+0.70 sobre base)
        self.assertGreater(p1, p2)
        self.assertGreater(p2, p3)
        self.assertEqual(round(p1 - p3, 2), 0.70)
        self.assertEqual(round(p2 - p3, 2), 0.35)

    def test_resolve_sell_collisions_bancos_highest(self):
        """Verifica que si G2 (Bancos) es el más caro del mercado, G2 sea Base, G3 sea +$0.35 y G1 sea +$0.70."""
        decisions = [
            SellDecision(
                cluster_id=1,
                title="Billeteras",
                anchor_method="MercadoPagoNew",
                suggested_price=1610.00,
                top1_price=1609.50,
                spread_added=0.50,
                estimated_position="Puesto #2",
                wac_cost=1570.0,
                fiwind_bid=1580.0,
            ),
            SellDecision(
                cluster_id=2,
                title="Bancos",
                anchor_method="SantanderArgentina",
                suggested_price=1625.00,  # Más caro del mercado
                top1_price=1624.50,
                spread_added=0.50,
                estimated_position="Puesto #2",
                wac_cost=1570.0,
                fiwind_bid=1580.0,
            ),
            SellDecision(
                cluster_id=3,
                title="Fintechs",
                anchor_method="personalpay",
                suggested_price=1618.00,  # Intermedio
                top1_price=1617.50,
                spread_added=0.50,
                estimated_position="Puesto #2",
                wac_cost=1570.0,
                fiwind_bid=1580.0,
            ),
        ]

        resolved = self.repositioner.resolve_sell_collisions(decisions, available_crypto_stock=350.0)
        self.assertEqual(len(resolved), 3)

        p1 = resolved[0].suggested_price  # G1 Billeteras
        p2 = resolved[1].suggested_price  # G2 Bancos
        p3 = resolved[2].suggested_price  # G3 Fintechs

        # G2 (Bancos) es el más caro del mercado -> pasa a ser nuestro anuncio base (1625.00)
        # G3 (Fintechs) es el del medio -> Base + $0.35 = 1625.35
        # G1 (Billeteras) es el más líquido -> al final, Base + $0.70 = 1625.70
        self.assertEqual(p2, 1625.00)
        self.assertEqual(p3, 1625.35)
        self.assertEqual(p1, 1625.70)
        self.assertEqual(round(p1 - p2, 2), 0.70)
        self.assertEqual(round(p3 - p2, 2), 0.35)

    def test_shared_inventory_and_50_to_100_percent_limits(self):
        """Verifica que con Inventario Compartido los 3 anuncios tengan 100% del stock y límites del 50% al 100%."""
        decisions = [
            SellDecision(
                cluster_id=1,
                title="G1",
                anchor_method="MP",
                suggested_price=1585.00,
                top1_price=1584.50,
                spread_added=0.50,
                estimated_position="#2",
                wac_cost=1570.0,
                fiwind_bid=1580.0,
            ),
            SellDecision(
                cluster_id=2,
                title="G2",
                anchor_method="Santander",
                suggested_price=1590.00,
                top1_price=1588.00,
                spread_added=2.00,
                estimated_position="#2",
                wac_cost=1570.0,
                fiwind_bid=1580.0,
            ),
            SellDecision(
                cluster_id=3,
                title="G3",
                anchor_method="PersonalPay",
                suggested_price=1595.00,
                top1_price=1592.00,
                spread_added=3.00,
                estimated_position="#2",
                wac_cost=1570.0,
                fiwind_bid=1580.0,
            ),
        ]

        resolved = self.repositioner.resolve_sell_collisions(decisions, available_crypto_stock=350.0)

        for dec in resolved:
            # 100% del stock para cada anuncio (Shared Inventory)
            self.assertEqual(dec.new_init_amount, 350.0)
            # Límites entre 50% y 100% de la capacidad
            self.assertGreater(dec.new_max_trans_amount, 0)
            self.assertGreater(dec.new_min_trans_amount, 0)
            self.assertLessEqual(dec.new_min_trans_amount, dec.new_max_trans_amount)
            # El máximo debe ser <= capacidad real
            capacity = dec.new_init_amount * dec.suggested_price
            self.assertLessEqual(dec.new_max_trans_amount, capacity)

        # Verificar proporciones dinámicas según SELL_GROUP_LIMIT_FACTORS
        g1 = next(d for d in resolved if d.cluster_id == 1)
        g2 = next(d for d in resolved if d.cluster_id == 2)
        g3 = next(d for d in resolved if d.cluster_id == 3)

        cap1 = g1.new_init_amount * g1.suggested_price
        cap2 = g2.new_init_amount * g2.suggested_price
        cap3 = g3.new_init_amount * g3.suggested_price

        # G1 min debe ser 50% (factor 0.50) y max 100% (factor 1.00)
        self.assertAlmostEqual(g1.new_min_trans_amount / cap1, 0.50, delta=0.02)
        self.assertAlmostEqual(g1.new_max_trans_amount / cap1, 1.00, delta=0.02)

        # G2 min debe ser 50% (factor 0.50) y max 100% (factor 1.00)
        self.assertAlmostEqual(g2.new_min_trans_amount / cap2, 0.50, delta=0.02)
        self.assertAlmostEqual(g2.new_max_trans_amount / cap2, 1.00, delta=0.02)

        # G3 min debe ser 50% (factor 0.50) y max 100% (factor 1.00)
        self.assertAlmostEqual(g3.new_min_trans_amount / cap3, 0.50, delta=0.02)
        self.assertAlmostEqual(g3.new_max_trans_amount / cap3, 1.00, delta=0.02)

    def test_execute_sell_decisions_respects_allow_offline(self):
        """Verifica que en calibración en frío (allow_offline=True) no se reanuden anuncios a ONLINE."""
        async def _run():
            from data.models import BotConfig
            self.mock_db.get_my_sell_ads.return_value = [
                MyAd(adv_no="AD1", asset="USDT", ad_group=1, current_price=1600.0, payment_methods=[], status=3)
            ]
            self.mock_db.load_bot_config.return_value = BotConfig(is_paused=False, paused_ads=[])
            self.mock_ads.update_sell_ad_params = AsyncMock(return_value=True)
            self.mock_ads.resume_sell_ad = AsyncMock()

            decisions = [
                SellDecision(cluster_id=1, title="G1", anchor_method="MP", suggested_price=1610.0,
                             top1_price=1608.0, spread_added=2.0, estimated_position="#2",
                             wac_cost=0, fiwind_bid=0, adv_no="AD1", should_update=True)
            ]

            # Con allow_offline=True, NO debe llamar a resume_sell_ad
            await self.repositioner.execute_sell_decisions(decisions, allow_offline=True)
            self.mock_ads.resume_sell_ad.assert_not_called()

            # Con allow_offline=False y SELL_AUTO_EXECUTION=True, sí debe reanudar
            with patch("config.settings.SELL_AUTO_EXECUTION", True):
                await self.repositioner.execute_sell_decisions(decisions, allow_offline=False)
                self.mock_ads.resume_sell_ad.assert_called_once_with("AD1")

        asyncio.run(_run())

    def test_low_balance_auto_pause(self):
        """Verifica que si el saldo libre cae por debajo de 10 USDT o del piso, se pause preventivamente."""
        decisions = [
            SellDecision(
                cluster_id=1,
                title="G1",
                anchor_method="MP",
                suggested_price=1585.00,
                top1_price=1584.50,
                spread_added=0.50,
                estimated_position="#2",
                wac_cost=1570.0,
                fiwind_bid=1580.0,
            )
        ]
        # Stock de solo 5 USDT (< 10 USDT piso legal de Binance)
        resolved = self.repositioner.resolve_sell_collisions(decisions, available_crypto_stock=5.0)
        self.assertTrue(resolved[0].should_pause)
        self.assertFalse(resolved[0].should_update)
        self.assertIn("saldo_menor_a_piso", resolved[0].pause_reason)

    def test_hysteresis_anti_spam(self):
        """Verifica que cambios de precio < $0.05 ARS no disparen actualización, pero >= $0.05 sí."""
        self.mock_db.get_my_sell_ads.return_value = [
            MyAd(adv_no="AD1", asset="USDT", ad_group=1, current_price=1585.00, init_amount=350.0, payment_methods=["MP"]),
        ]
        # Caso A: Diferencia de 2 centavos ($1585.02 vs $1585.00) -> NO actualizar
        decisions_a = [
            SellDecision(
                cluster_id=1, title="G1", anchor_method="MP",
                suggested_price=1585.02, top1_price=1584.50, spread_added=0.52,
                estimated_position="#2", wac_cost=1570.0, fiwind_bid=1580.0,
            )
        ]
        res_a = self.repositioner.resolve_sell_collisions(decisions_a, available_crypto_stock=350.0)
        self.assertFalse(res_a[0].should_update)

        # Caso B: Diferencia de 6 centavos ($1585.06 vs $1585.00) -> SÍ actualizar
        decisions_b = [
            SellDecision(
                cluster_id=1, title="G1", anchor_method="MP",
                suggested_price=1585.06, top1_price=1584.50, spread_added=0.56,
                estimated_position="#2", wac_cost=1570.0, fiwind_bid=1580.0,
            )
        ]
        res_b = self.repositioner.resolve_sell_collisions(decisions_b, available_crypto_stock=350.0)
        self.assertTrue(res_b[0].should_update)

    def test_execute_sell_decisions_rising_prices_order(self):
        """Si los precios suben, la ejecución debe ser descendente en grupo (G3 -> G2 -> G1)."""
        async def _run():
            # Simular anuncios existentes con precios bajos
            self.mock_db.get_my_sell_ads.return_value = [
                MyAd(adv_no="AD1", asset="USDT", ad_group=1, current_price=1580.0, payment_methods=["MP"]),
                MyAd(adv_no="AD2", asset="USDT", ad_group=2, current_price=1582.0, payment_methods=["Santander"]),
                MyAd(adv_no="AD3", asset="USDT", ad_group=3, current_price=1584.0, payment_methods=["PersonalPay"]),
            ]

            call_order = []

            async def fake_update(adv_no, **kwargs):
                call_order.append(adv_no)
                return True

            self.mock_ads.update_sell_ad_params = AsyncMock(side_effect=fake_update)

            decisions = [
                SellDecision(cluster_id=1, title="G1", anchor_method="MP", suggested_price=1585.0, top1_price=1584.0, spread_added=1.0, estimated_position="#2", wac_cost=0, fiwind_bid=0, adv_no="AD1", should_update=True),
                SellDecision(cluster_id=2, title="G2", anchor_method="Santander", suggested_price=1590.0, top1_price=1588.0, spread_added=2.0, estimated_position="#2", wac_cost=0, fiwind_bid=0, adv_no="AD2", should_update=True),
                SellDecision(cluster_id=3, title="G3", anchor_method="PersonalPay", suggested_price=1595.0, top1_price=1592.0, spread_added=3.0, estimated_position="#2", wac_cost=0, fiwind_bid=0, adv_no="AD3", should_update=True),
            ]

            results = await self.repositioner.execute_sell_decisions(decisions)
            self.assertEqual(len(results), 3)
            self.assertEqual(call_order, ["AD3", "AD2", "AD1"])

        asyncio.run(_run())

    def test_cascade_collision_g2_g3_follow_g1(self):
        """Verifica que si G2 es el más caro del mercado, G2 sea Base, G3 sea +$0.35 y G1 sea +$0.70."""
        decisions = [
            SellDecision(
                cluster_id=1, title="Billeteras", anchor_method="MP",
                suggested_price=1608.80, top1_price=1608.50, spread_added=0.30,
                estimated_position="#2", wac_cost=1570.0, fiwind_bid=1580.0,
            ),
            # G2 es el más caro ($1618.00)
            SellDecision(
                cluster_id=2, title="Bancos", anchor_method="Santander",
                suggested_price=1618.00, top1_price=1616.00, spread_added=2.00,
                estimated_position="#2", wac_cost=1570.0, fiwind_bid=1580.0,
            ),
            # G3 es intermedio ($1614.00)
            SellDecision(
                cluster_id=3, title="Fintechs", anchor_method="PersonalPay",
                suggested_price=1614.00, top1_price=1612.00, spread_added=2.00,
                estimated_position="#2", wac_cost=1570.0, fiwind_bid=1580.0,
            ),
        ]

        resolved = self.repositioner.resolve_sell_collisions(decisions, available_crypto_stock=350.0)
        self.assertEqual(len(resolved), 3)

        by_grp = {d.cluster_id: d for d in resolved}
        p1 = by_grp[1].suggested_price
        p2 = by_grp[2].suggested_price
        p3 = by_grp[3].suggested_price

        # G2 más caro -> Base = 1618.00
        self.assertEqual(p2, 1618.00)
        # G3 intermedio -> Base + 0.35 = 1618.35
        self.assertEqual(p3, 1618.35)
        # G1 más líquido -> Base + 0.70 = 1618.70
        self.assertEqual(p1, 1618.70)

        # Verificar separación estricta > 0.15 ARS de Binance
        self.assertGreater(round(p3 - p2, 2), 0.15)
        self.assertGreater(round(p1 - p3, 2), 0.15)

    def test_cascade_collision_market_independent_mode(self):
        """Verifica que si G1 (Billeteras) es el más caro del mercado, G1 sea Base, G2 sea +$0.35 y G3 sea +$0.70."""
        decisions = [
            # G1 es el más caro ($1625.00)
            SellDecision(
                cluster_id=1, title="Billeteras", anchor_method="MP",
                suggested_price=1625.00, top1_price=1624.50, spread_added=0.50,
                estimated_position="#2", wac_cost=1570.0, fiwind_bid=1580.0,
            ),
            SellDecision(
                cluster_id=2, title="Bancos", anchor_method="Santander",
                suggested_price=1618.00, top1_price=1616.00, spread_added=2.00,
                estimated_position="#2", wac_cost=1570.0, fiwind_bid=1580.0,
            ),
            SellDecision(
                cluster_id=3, title="Fintechs", anchor_method="PersonalPay",
                suggested_price=1614.00, top1_price=1612.00, spread_added=2.00,
                estimated_position="#2", wac_cost=1570.0, fiwind_bid=1580.0,
            ),
        ]

        resolved = self.repositioner.resolve_sell_collisions(decisions, available_crypto_stock=350.0)
        by_grp = {d.cluster_id: d for d in resolved}
        # G1 más caro -> Base = 1625.00
        self.assertEqual(by_grp[1].suggested_price, 1625.00)
        # G2 -> Base + 0.35 = 1625.35
        self.assertEqual(by_grp[2].suggested_price, 1625.35)
        # G3 -> Base + 0.70 = 1625.70
        self.assertEqual(by_grp[3].suggested_price, 1625.70)
        self.assertGreater(round(by_grp[2].suggested_price - by_grp[1].suggested_price, 2), 0.15)
        self.assertGreater(round(by_grp[3].suggested_price - by_grp[2].suggested_price, 2), 0.15)

    def test_cascade_collision_spread_first_mode(self):
        """Verifica que si G3 es el más caro, G3 ancle la base (1621.80), G2 sea +$0.35 y G1 (MP) quede blindado +$0.70 arriba."""
        decisions = [
            SellDecision(
                cluster_id=1, title="Billeteras", anchor_method="MP",
                suggested_price=1618.00, top1_price=1617.99, spread_added=0.01,
                estimated_position="#2", wac_cost=1570.0, fiwind_bid=1580.0,
            ),
            SellDecision(
                cluster_id=2, title="Bancos", anchor_method="Santander",
                suggested_price=1621.36, top1_price=1620.00, spread_added=1.36,
                estimated_position="#2", wac_cost=1570.0, fiwind_bid=1580.0,
            ),
            SellDecision(
                cluster_id=3, title="Fintechs", anchor_method="PersonalPay",
                suggested_price=1621.80, top1_price=1621.80, spread_added=0.00,
                estimated_position="#2", wac_cost=1570.0, fiwind_bid=1580.0,
            ),
        ]

        resolved = self.repositioner.resolve_sell_collisions(decisions, available_crypto_stock=350.0)
        by_grp = {d.cluster_id: d for d in resolved}
        # G3 es el más caro -> Base = 1621.80
        self.assertEqual(by_grp[3].suggested_price, 1621.80)
        # G2 es el intermedio -> Base + 0.35 = 1622.15
        self.assertEqual(by_grp[2].suggested_price, 1622.15)
        # G1 (Mercado Pago, el más líquido) queda por encima de todos (1621.80 + 0.70 = 1622.50)
        self.assertEqual(by_grp[1].suggested_price, 1622.50)

        # Verificar separación estricta > 0.15 ARS de Binance en todos los tramos
        self.assertGreater(round(by_grp[2].suggested_price - by_grp[3].suggested_price, 2), 0.15)
        self.assertGreater(round(by_grp[1].suggested_price - by_grp[2].suggested_price, 2), 0.15)


if __name__ == "__main__":
    unittest.main()

