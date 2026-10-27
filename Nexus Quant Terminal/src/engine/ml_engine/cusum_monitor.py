import numpy as np
import pandas as pd

class CUSUMMonitor:
    """
    Monitorea la curva de equity en tiempo real usando CUSUM.
    Detecta cuándo el edge de la estrategia desaparece y genera
    señales de PAUSE/RESUME.
    
    Basado en: Page, E.S. (1954). Continuous Inspection Schemes.
    """
    def __init__(self, expected_wr: float = 0.60, payout: float = 0.85,
                 threshold_sigma: float = 3.0, window: int = 50):
        self.expected_wr = expected_wr
        self.payout = payout
        self.threshold_sigma = threshold_sigma
        self.window = window
        
        # EV esperado por trade: WR * payout - (1-WR) * 1.0
        self.expected_ev = expected_wr * payout - (1 - expected_wr) * 1.0
        
        # Estado interno (con límites de memoria para evitar fugas de memoria)
        self.trade_results = []  # Lista de PnL por trade (+payout o -1.0), acotada a max 1000
        self.post_pause_results = []  # Resultados de trades durante pausa para evaluar recuperación limpia
        self.pause_history = []  # Historia de pausados/reanudados, acotada a max 100
        self.cusum_pos = 0.0  # CUSUM positivo (detecta deterioro)
        self.cusum_neg = 0.0  # CUSUM negativo (detecta mejora)
        self.is_paused = False
        self.total_trades_count = 0
        
    def reset(self):
        """Reinicia el estado interno del monitor CUSUM."""
        self.trade_results.clear()
        self.pause_history.clear()
        self.post_pause_results.clear()
        self.cusum_pos = 0.0
        self.cusum_neg = 0.0
        self.is_paused = False
        self.total_trades_count = 0

    def update(self, trade_pnl: float) -> str:
        """
        Actualizar con resultado de un trade.
        trade_pnl: +payout si WIN, -1.0 si LOSS, 0 si TIE
        
        Returns: 'CONTINUE', 'PAUSE', or 'RESUME'
        """
        self.total_trades_count += 1
        self.trade_results.append(trade_pnl)
        if len(self.trade_results) > 1000:
            self.trade_results = self.trade_results[-1000:]
        
        if len(self.trade_results) < 10:
            return 'CONTINUE'  # No hay suficientes datos aún
        
        # Residual: desviación del PnL respecto al EV esperado
        residual = trade_pnl - self.expected_ev
        
        # Slack (allowance): mitad del EV esperado
        slack = abs(self.expected_ev) / 2.0
        
        # Actualizar CUSUM bilateral
        self.cusum_pos = max(0, self.cusum_pos + residual - slack)
        self.cusum_neg = max(0, self.cusum_neg - residual - slack)
        
        # Calcular threshold dinámico basado en std de los residuales recientes
        recent = self.trade_results[-self.window:]
        residuals = [r - self.expected_ev for r in recent]
        std_residuals = np.std(residuals) if len(residuals) > 1 else 1.0
        threshold = self.threshold_sigma * std_residuals
        
        # Decisión
        if not self.is_paused and self.cusum_neg > threshold:
            self.is_paused = True
            self.post_pause_results = []
            self.pause_history.append({
                'action': 'PAUSE',
                'trade_num': self.total_trades_count,
                'cusum': self.cusum_neg,
                'threshold': threshold
            })
            if len(self.pause_history) > 100:
                self.pause_history = self.pause_history[-100:]
            return 'PAUSE'
        
        if self.is_paused:
            # Evaluar recuperación limpia basándose en resultados post-pausa
            self.post_pause_results.append(trade_pnl)
            if len(self.post_pause_results) > 100:
                self.post_pause_results = self.post_pause_results[-100:]
                
            recent_short = self.post_pause_results[-10:]
            if len(recent_short) >= 5:
                recent_wr = sum(1 for r in recent_short if r > 0) / len(recent_short)
                if recent_wr >= self.expected_wr:
                    self.is_paused = False
                    self.cusum_pos = 0.0
                    self.cusum_neg = 0.0
                    self.post_pause_results = []
                    self.pause_history.append({
                        'action': 'RESUME',
                        'trade_num': self.total_trades_count,
                        'recent_wr': recent_wr
                    })
                    if len(self.pause_history) > 100:
                        self.pause_history = self.pause_history[-100:]
                    return 'RESUME'
            return 'PAUSED'
        
        return 'CONTINUE'
    
    def should_trade(self) -> bool:
        """Retorna True si el sistema debe seguir operando."""
        return not self.is_paused
    
    def get_stats(self) -> dict:
        """Estadísticas del monitor."""
        if not self.trade_results:
            return {'total_trades': 0, 'current_wr': 0, 'is_paused': False}
        
        recent = self.trade_results[-self.window:]
        return {
            'total_trades': self.total_trades_count if self.total_trades_count > 0 else len(self.trade_results),
            'current_wr': sum(1 for r in recent if r > 0) / len(recent) if len(recent) > 0 else 0.0,
            'cusum_pos': self.cusum_pos,
            'cusum_neg': self.cusum_neg,
            'is_paused': self.is_paused,
            'pause_count': sum(1 for p in self.pause_history if p['action'] == 'PAUSE')
        }
