import unittest
import numpy as np
from engine.optimizer import CapitalOptimizer
from app import extract_markov_params


class TestMarkovDynamicSimulation(unittest.TestCase):
    def setUp(self):
        self.optimizer = CapitalOptimizer()
        self.win_rate = 0.58
        self.payout = 0.85
        self.risk_capital = 200.0
        self.target_capital = 1000.0
        self.attempts = 6

    def test_calculate_streak_plan_iid_fallback(self):
        """Without Markov parameters, calculate_streak_plan should use IID (p^n)."""
        res = self.optimizer.calculate_streak_plan(
            win_rate=self.win_rate,
            payout=self.payout,
            risk_capital=self.risk_capital,
            target_capital=self.target_capital,
            attempts=self.attempts
        )
        self.assertFalse(res['markov_mode'])
        self.assertIsNone(res['p_ww_used'])
        self.assertIsNone(res['p_wl_used'])

        # Verify each N matches effective_wr ** n
        for r in res['results_by_n']:
            n = r['n']
            expected_p = float(self.win_rate ** n)
            self.assertAlmostEqual(r['p_success_single'], expected_p, places=5)
            self.assertAlmostEqual(r['p_success_single_iid'], expected_p, places=5)

    def test_calculate_streak_plan_markov_positive_momentum(self):
        """With P(W|W) > P(W), Markov probability for N>1 should be strictly greater than IID."""
        p_ww = 0.68
        p_wl = 0.50

        res_iid = self.optimizer.calculate_streak_plan(
            win_rate=self.win_rate,
            payout=self.payout,
            risk_capital=self.risk_capital,
            target_capital=self.target_capital,
            attempts=self.attempts
        )

        res_markov = self.optimizer.calculate_streak_plan(
            win_rate=self.win_rate,
            payout=self.payout,
            risk_capital=self.risk_capital,
            target_capital=self.target_capital,
            attempts=self.attempts,
            p_ww=p_ww,
            p_wl=p_wl
        )

        self.assertTrue(res_markov['markov_mode'])
        self.assertEqual(res_markov['p_ww_used'], p_ww)
        self.assertEqual(res_markov['p_wl_used'], p_wl)

        # For n=3:
        # IID: 0.58^3 = ~0.1951
        # Markov: 0.58 * (0.68^2) = ~0.2682
        item_iid = next(x for x in res_iid['results_by_n'] if x['n'] == 3)
        item_markov = next(x for x in res_markov['results_by_n'] if x['n'] == 3)

        self.assertGreater(item_markov['p_success_single'], item_iid['p_success_single'])
        self.assertGreater(item_markov['p_success_campaign'], item_iid['p_success_campaign'])
        self.assertGreater(item_markov['prob_duplication_pct'], item_iid['prob_duplication_pct'])

    def test_monte_carlo_discrete_markov_effect(self):
        """Monte Carlo discrete with strong positive momentum should have higher success probability."""
        np.random.seed(42)
        res_iid = self.optimizer.monte_carlo_discrete(
            win_rate=0.55,
            payout=0.85,
            n_consecutive=3,
            bet_fraction=1.0 / 6,
            risk_capital=200.0,
            target_capital=1000.0,
            num_simulations=3000,
            max_trades=1000
        )

        np.random.seed(42)
        res_markov = self.optimizer.monte_carlo_discrete(
            win_rate=0.55,
            payout=0.85,
            n_consecutive=3,
            bet_fraction=1.0 / 6,
            risk_capital=200.0,
            target_capital=1000.0,
            num_simulations=3000,
            max_trades=1000,
            p_ww=0.72,
            p_wl=0.50
        )

        self.assertGreater(res_markov['success_probability'], res_iid['success_probability'])
        self.assertLessEqual(res_markov['ruin_probability'], res_iid['ruin_probability'])

    def test_monte_carlo_campaign_markov_effect(self):
        """Monte Carlo campaign with Markov momentum should boost campaign completion probability."""
        np.random.seed(42)
        res_iid = self.optimizer.monte_carlo_campaign(
            win_rate=0.55,
            payout=0.85,
            n_streak=3,
            k_attempts=6,
            bet_per_attempt=33.33,
            num_simulations=3000
        )

        np.random.seed(42)
        res_markov = self.optimizer.monte_carlo_campaign(
            win_rate=0.55,
            payout=0.85,
            n_streak=3,
            k_attempts=6,
            bet_per_attempt=33.33,
            num_simulations=3000,
            p_ww=0.70,
            p_wl=0.52
        )

        self.assertGreater(res_markov['success_probability'], res_iid['success_probability'])
        self.assertGreater(res_markov['expected_value'], res_iid['expected_value'])

    def test_monte_carlo_paths_markov_execution(self):
        """monte_carlo paths method should execute without errors when p_ww and p_wl are provided."""
        res = self.optimizer.monte_carlo(
            win_rate=0.58,
            payout=0.85,
            n=3,
            kelly_f=0.1,
            num_simulations=500,
            num_cycles=50,
            p_ww=0.65,
            p_wl=0.50
        )
        self.assertIn('paths', res)
        self.assertIn('final_equity', res)
        self.assertIn('ruin_probability', res)
        self.assertIn('max_drawdowns', res)

    def test_extract_markov_params_guardrails(self):
        """extract_markov_params should only extract when >= 20 decisive trades are present."""
        # Empty stats
        p_ww, p_wl = extract_markov_params({})
        self.assertIsNone(p_ww)
        self.assertIsNone(p_wl)

        # Less than 20 decisive trades
        small_sample_stats = {
            'basic': {'decisive': 12},
            'markov': {'transition_matrix': [[0.7, 0.3], [0.5, 0.5]]}
        }
        p_ww, p_wl = extract_markov_params(small_sample_stats)
        self.assertIsNone(p_ww)
        self.assertIsNone(p_wl)

        # >= 20 decisive trades
        valid_stats = {
            'basic': {'decisive': 45},
            'markov': {'transition_matrix': [[0.68, 0.32], [0.51, 0.49]]}
        }
        p_ww, p_wl = extract_markov_params(valid_stats)
        self.assertEqual(p_ww, 0.68)
        self.assertEqual(p_wl, 0.51)


if __name__ == '__main__':
    unittest.main()
