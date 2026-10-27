"""
tests/test_signal_dispatcher.py
Pruebas unitarias para el Orquestador de Señales, Motor de Prioridad y Streak Mutex Lock.
"""

import unittest
from engine.execution.signal_dispatcher import (
    StreakMutexManager,
    PriorityRankingEngine,
    SignalCandidate,
    MutexState
)


class TestSignalDispatcher(unittest.TestCase):
    def setUp(self):
        self.mutex = StreakMutexManager()

    def test_mutex_initial_state_idle(self):
        """El Mutex debe inicializarse en estado IDLE_WAITING y permitir despachos."""
        self.assertEqual(self.mutex.state, MutexState.IDLE_WAITING)
        self.assertTrue(self.mutex.can_dispatch())

    def test_mutex_acquire_and_block_interim(self):
        """Al adquirir el lock, el Mutex debe bloquear nuevas señales hasta que se libere."""
        candidate1 = SignalCandidate(
            symbol="BTC/USDT",
            strategy_id="daily_confluence",
            direction="BUY",
            candle_ts=1700000000,
            close_price=75000.0,
            atr=400.0,
            sl_price=74500.0,
            tp_price=76000.0
        )

        # 1. Adquirir lock
        acquired = self.mutex.acquire_lock(candidate1, bullet_usd=5.0)
        self.assertTrue(acquired)
        self.assertEqual(self.mutex.state, MutexState.LOCKED_IN_TRADE)
        self.assertFalse(self.mutex.can_dispatch())
        self.assertEqual(self.mutex.active_symbol, "BTC/USDT")

        # 2. Intentar adquirir con un segundo candidato debe ser rechazado
        candidate2 = SignalCandidate(
            symbol="ETH/USDT",
            strategy_id="climax_reversal",
            direction="BUY",
            candle_ts=1700000000,
            close_price=2400.0,
            atr=20.0,
            sl_price=2370.0,
            tp_price=2450.0
        )
        rejected = self.mutex.acquire_lock(candidate2, bullet_usd=5.0)
        self.assertFalse(rejected)

        # 3. Liberar el lock
        self.mutex.release_lock(reason="FLAT_COMPLETED")
        self.assertEqual(self.mutex.state, MutexState.IDLE_WAITING)
        self.assertTrue(self.mutex.can_dispatch())
        self.assertIsNone(self.mutex.active_symbol)

    def test_priority_ranking_cross_veto(self):
        """Si dos estrategias emiten BUY y SELL en el mismo par, el par debe ser vetado."""
        cand_buy = SignalCandidate(
            symbol="BTC/USDT",
            strategy_id="daily_confluence",
            direction="BUY",
            candle_ts=1700000000,
            close_price=75000.0,
            atr=400.0,
            sl_price=74500.0,
            tp_price=76000.0
        )
        cand_sell = SignalCandidate(
            symbol="BTC/USDT",
            strategy_id="climax_reversal",
            direction="SELL",
            candle_ts=1700000000,
            close_price=75000.0,
            atr=400.0,
            sl_price=75500.0,
            tp_price=74000.0
        )

        ranked = PriorityRankingEngine.rank_candidates([cand_buy, cand_sell])
        # Ambos deben ser descartados por veto cruzado contradictorio
        self.assertEqual(len(ranked), 0)

    def test_priority_ranking_confluence_bonus(self):
        """Si dos estrategias coinciden en BUY en el mismo par, reciben bonus de confluencia."""
        cand_1 = SignalCandidate(
            symbol="BTC/USDT",
            strategy_id="daily_confluence",
            direction="BUY",
            candle_ts=1700000000,
            close_price=75000.0,
            atr=400.0,
            sl_price=74500.0,
            tp_price=76000.0
        )
        cand_2 = SignalCandidate(
            symbol="BTC/USDT",
            strategy_id="volatility_squeeze_ml",
            direction="BUY",
            candle_ts=1700000000,
            close_price=75000.0,
            atr=400.0,
            sl_price=74500.0,
            tp_price=76000.0
        )

        ranked = PriorityRankingEngine.rank_candidates([cand_1, cand_2])
        self.assertEqual(len(ranked), 1)
        winner = ranked[0]
        self.assertEqual(winner.symbol, "BTC/USDT")
        self.assertEqual(winner.confluence_count, 2)
        self.assertGreater(winner.priority_score, 0.70)
        self.assertIn("volatility_squeeze_ml", winner.metadata["contributing_strategies"])

    def test_priority_ranking_respects_blocked_symbols(self):
        """Los símbolos ocupados por Bot 2 no deben ser seleccionados para Bot 1."""
        cand_btc = SignalCandidate(
            symbol="BTC/USDT",
            strategy_id="daily_confluence",
            direction="BUY",
            candle_ts=1700000000,
            close_price=75000.0,
            atr=400.0,
            sl_price=74500.0,
            tp_price=76000.0
        )
        cand_eth = SignalCandidate(
            symbol="ETH/USDT",
            strategy_id="climax_reversal",
            direction="BUY",
            candle_ts=1700000000,
            close_price=2400.0,
            atr=20.0,
            sl_price=2370.0,
            tp_price=2450.0
        )

        # Si BTC/USDT está bloqueado por Bot 2
        ranked = PriorityRankingEngine.rank_candidates([cand_btc, cand_eth], blocked_symbols=["BTC/USDT"])
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].symbol, "ETH/USDT")


if __name__ == '__main__':
    unittest.main()
