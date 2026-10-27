import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from datetime import datetime, timedelta

from core.sell_guardrails import SellGuardrails


class TestSellGuardrails(unittest.TestCase):

    def test_validate_break_even_below_wac(self):
        """Verifica que un precio menor al costo WAC + margen sea rechazado inmediatamente."""
        wac_cost = 1580.0
        # Margen 0.2% -> min_allowed = 1580.0 * 1.002 = 1583.16
        below_price = 1582.0
        ok, reason = SellGuardrails.validate_break_even(below_price, wac_cost, min_margin_pct=0.002)
        self.assertFalse(ok)
        self.assertIn("Pérdida evitada", reason)
        self.assertIn("inferior al costo WAC", reason)

    def test_validate_break_even_above_wac(self):
        """Verifica que un precio que cubre el WAC sea aceptado."""
        wac_cost = 1580.0
        above_price = 1585.0
        ok, reason = SellGuardrails.validate_break_even(above_price, wac_cost, min_margin_pct=0.002)
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_validate_break_even_zero_wac(self):
        """Si no hay compras previas (WAC=0), permite operar si el precio es positivo."""
        ok, reason = SellGuardrails.validate_break_even(1580.0, 0.0)
        self.assertTrue(ok)

    def test_validate_oracle_sanity_abnormal_low(self):
        """Rechaza precios que desvíen más de 3% por debajo del bid oficial de Fiwind."""
        fiwind_bid = 1600.0
        # 1600 * 0.97 = 1552.00
        anomalous_low = 1540.0
        ok, reason = SellGuardrails.validate_oracle_sanity(anomalous_low, fiwind_bid, max_dev_pct=0.03)
        self.assertFalse(ok)
        self.assertIn("Anomalía de mercado", reason)
        self.assertIn("abajo de Fiwind Bid", reason)

    def test_validate_oracle_sanity_normal(self):
        """Acepta precios dentro de la banda creíble de Fiwind."""
        fiwind_bid = 1600.0
        normal_price = 1602.0
        ok, reason = SellGuardrails.validate_oracle_sanity(normal_price, fiwind_bid, max_dev_pct=0.03)
        self.assertTrue(ok)

    def test_validate_data_freshness_recent(self):
        """Acepta timestamps recientes (< 90 segundos)."""
        recent = datetime.now() - timedelta(seconds=20)
        ok, reason = SellGuardrails.validate_data_freshness(recent, max_age_seconds=90.0)
        self.assertTrue(ok)

    def test_validate_data_freshness_stale(self):
        """Rechaza timestamps de más de 90 segundos."""
        stale = datetime.now() - timedelta(seconds=120)
        ok, reason = SellGuardrails.validate_data_freshness(stale, max_age_seconds=90.0)
        self.assertFalse(ok)
        self.assertIn("Datos de mercado obsoletos", reason)

    def test_validate_data_freshness_none(self):
        """Rechaza ausencia de timestamp."""
        ok, reason = SellGuardrails.validate_data_freshness(None)
        self.assertFalse(ok)
        self.assertIn("Sin marca de tiempo", reason)

    def test_validate_order_book_depth_insufficient(self):
        """Rechaza libros con menos de 2 vendedores."""
        ok, reason = SellGuardrails.validate_order_book_depth([1585.0], min_sellers=2)
        self.assertFalse(ok)
        self.assertIn("Profundidad insuficiente", reason)

    def test_validate_order_book_depth_sufficient(self):
        """Acepta libros con al menos 2 vendedores válidos."""
        ok, reason = SellGuardrails.validate_order_book_depth([1585.0, 1586.0], min_sellers=2)
        self.assertTrue(ok)

    def test_validate_tranche_limit(self):
        """Recorta cantidades mayores al límite de tranche permitido."""
        clamped = SellGuardrails.validate_tranche_limit(1000.0, max_allowed=500.0)
        self.assertEqual(clamped, 500.0)
        clamped_low = SellGuardrails.validate_tranche_limit(250.0, max_allowed=500.0)
        self.assertEqual(clamped_low, 250.0)

    def test_audit_sell_price_all_pass(self):
        """Prueba la suite completa de auditoría con parámetros correctos."""
        ok, msg = SellGuardrails.audit_sell_price(
            price=1588.0,
            wac_cost=1580.0,
            fiwind_bid=1585.0,
            data_timestamp=datetime.now() - timedelta(seconds=10),
            individual_prices=[1587.0, 1588.0, 1589.0],
        )
        self.assertTrue(ok)
        self.assertIn("aprobada", msg)


if __name__ == "__main__":
    unittest.main()
