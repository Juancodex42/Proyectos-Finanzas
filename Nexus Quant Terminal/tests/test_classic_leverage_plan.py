import unittest
from engine.optimizers.classic import ClassicOptimizer
from app import app

class TestClassicLeveragePlan(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_calculate_leveraged_execution_plan(self):
        """Verifies mathematical consistency of the leveraged execution plan."""
        plan = ClassicOptimizer.calculate_leveraged_execution_plan(
            base_patrimony=1000.0,
            monthly_flow=200.0,
            entry_price=60000.0,
            atr_val=1200.0,
            sl_multiplier=1.5,
            tp_multiplier=3.0,
            direction='LONG'
        )

        # 1. Base capital is protected
        self.assertEqual(plan["base_capital_at_risk"], 0.0)
        self.assertEqual(plan["base_capital_drawdown_pct"], 0.0)
        self.assertEqual(plan["margin_to_commit_usd"], 200.0)

        # 2. SL distance = 1.5 * 1200 = 1800. SL price = 60000 - 1800 = 58200.
        self.assertEqual(plan["sl_price"], 58200.0)
        # TP distance = 3.0 * 1200 = 3600. TP price = 60000 + 3600 = 63600.
        self.assertEqual(plan["tp_price"], 63600.0)

        # 3. SL distance pct = 1800 / 60000 = 3.0%
        self.assertAlmostEqual(plan["sl_distance_pct"], 3.0, places=1)
        # Position nominal = ~200 / 0.03 = ~6666 USD.
        self.assertGreater(plan["position_nominal_usd"], 6000.0)
        self.assertLess(plan["position_nominal_usd"], 7000.0)

        # 4. Effective leverage = Position / Margin = 6600 / 200 = ~33x
        self.assertGreaterEqual(plan["effective_leverage"], 30.0)
        self.assertLessEqual(plan["effective_leverage"], 35.0)

        # 5. Potential profit on TP = ~200 * 2.0 = ~400 USD
        self.assertGreater(plan["potential_net_profit_usd"], 350.0)
        
        # 6. Trades needed to double $1,000 = ceil(1000 / 400) = 2 or 3 trades
        self.assertIn(plan["trades_to_double_patrimony"], [2, 3])

    def test_api_classic_leverage_plan_endpoint(self):
        """Verifies GET and POST on /api/classic/leverage-plan."""
        resp = self.client.get('/api/classic/leverage-plan?pair=BTCUSDT&interval=4h&monthly_flow=200')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("recommended_leverage_tier", data)
        self.assertIn("position_nominal_usd", data)
        self.assertIn("sl_price", data)
        self.assertIn("tp_price", data)
        self.assertEqual(data["margin_to_commit_usd"], 200.0)

if __name__ == '__main__':
    unittest.main()
