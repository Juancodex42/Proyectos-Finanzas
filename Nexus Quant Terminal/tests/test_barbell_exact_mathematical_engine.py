import unittest
import math
from engine.optimizers.capital import CapitalOptimizer

class TestBarbellExactMathematicalEngine(unittest.TestCase):
    def setUp(self):
        self.optimizer = CapitalOptimizer()

    def test_n_star_exact_derivation(self):
        """Verifies that N* = ceil(ln(1 + 1/alpha) / ln(1 + payout)) equals 3 for alpha=0.20, payout=0.85."""
        res = self.optimizer.calculate_barbell_patrimony_duplication_engine(
            base_patrimony=1000.0,
            monthly_flow_pct=0.20,
            win_rate=0.55,
            payout=0.85
        )
        opt_n = res["optimal_n"]
        self.assertEqual(opt_n["n_star"], 3)
        self.assertAlmostEqual(opt_n["n_star_exact"], 2.9125, places=3)
        self.assertTrue(opt_n["doubled_in_1_hit"])
        self.assertGreater(opt_n["patrimony_after_1_hit"], 2000.0)
        self.assertEqual(res["base_capital_ruin_probability"], 0.0)
        self.assertEqual(res["base_capital_max_drawdown_pct"], 0.0)

    def test_speed_and_probabilities_invariance(self):
        """Verifies geometric distribution probabilities for varying win rates."""
        for wr in [0.50, 0.55, 0.60, 0.65]:
            res = self.optimizer.calculate_barbell_patrimony_duplication_engine(
                base_patrimony=1000.0,
                monthly_flow_pct=0.20,
                win_rate=wr,
                payout=0.85
            )
            opt_n = res["optimal_n"]
            # Expected months = 1 / (wr^3)
            expected_m = 1.0 / (wr ** 3)
            self.assertAlmostEqual(opt_n["expected_months_to_double"], expected_m, places=2)
            
            # Cumulative prob at 12 months = 1 - (1 - wr^3)^12
            expected_p12 = (1.0 - ((1.0 - (wr ** 3)) ** 12)) * 100.0
            self.assertAlmostEqual(opt_n["cumulative_probabilities_pct"]["month_12"], expected_p12, places=1)

    def test_low_variance_n2_properties(self):
        """Verifies N=2 requires 2 hits and yields expected results."""
        res = self.optimizer.calculate_barbell_patrimony_duplication_engine(
            base_patrimony=1000.0,
            monthly_flow_pct=0.20,
            win_rate=0.60,
            payout=0.85
        )
        n2 = res["low_variance_n2"]
        self.assertEqual(n2["n"], 2)
        self.assertEqual(n2["needed_hits_to_double"], 2)
        self.assertAlmostEqual(n2["monthly_success_prob"], 36.0, places=1) # 0.60^2 = 0.36
        self.assertAlmostEqual(n2["expected_months_to_double"], 2.0 / 0.36, places=1) # 5.56 months

if __name__ == '__main__':
    unittest.main()
