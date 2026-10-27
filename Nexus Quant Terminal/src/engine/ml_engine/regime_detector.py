import numpy as np
import pandas as pd
import warnings

class RegimeDetector:
    """
    Detector de Régimen de Mercado usando Hidden Markov Model.
    Clasifica el mercado en 3 estados latentes basándose en:
    - Retornos
    - Volatilidad realizada
    - Eficiencia de Kaufman
    
    Solo permite operar en estados donde la estrategia históricamente funciona.
    """
    
    # Constantes de estado
    STATE_TRENDING = 0
    STATE_MEAN_REVERTING = 1
    STATE_CHAOTIC = 2
    
    STATE_NAMES = {0: 'TRENDING', 1: 'MEAN_REVERTING', 2: 'CHAOTIC'}
    
    def __init__(self, n_states: int = 3, lookback: int = 100,
                 favorable_states: list = None):
        self.n_states = n_states
        self.lookback = lookback
        self.favorable_states = favorable_states or [0, 1]  # Por defecto: trending y mean-reverting
        self.model = None
        self.is_fitted = False
        self.state_stats = {}
    
    def _prepare_observations(self, df: pd.DataFrame) -> np.ndarray:
        """Prepara la matriz de observaciones para el HMM."""
        close = df['close']
        returns = close.pct_change().fillna(0)
        
        # Feature 1: Retornos
        feat_returns = returns.values
        
        # Feature 2: Volatilidad realizada (rolling std de 20 periodos sin look-ahead bias)
        feat_vol = returns.rolling(20, min_periods=1).std().fillna(0.0).values
        
        # Feature 3: Eficiencia de Kaufman (10 periodos)
        change_10 = (close - close.shift(10)).abs()
        vol_10 = (close - close.shift(1)).abs().rolling(10).sum().replace(0, 1e-8)
        feat_er = (change_10 / vol_10).fillna(0.5).values
        
        obs = np.column_stack([feat_returns, feat_vol, feat_er])
        
        # Limpiar NaN e infinitos
        obs = np.nan_to_num(obs, nan=0.0, posinf=1.0, neginf=-1.0)
        
        return obs
    
    def fit(self, df: pd.DataFrame, signals: pd.Series = None, 
            results: pd.Series = None):
        """
        Entrenar el HMM y, opcionalmente, mapear estados a performance de la estrategia.
        """
        try:
            from hmmlearn.hmm import GaussianHMM
        except ImportError:
            warnings.warn("hmmlearn no instalado. RegimeDetector deshabilitado.")
            return self
        
        obs = self._prepare_observations(df)
        
        if len(obs) < 100:
            return self
        
        # Entrenar HMM
        self.model = GaussianHMM(
            n_components=self.n_states,
            covariance_type='diag',
            min_covar=1e-3,
            n_iter=200,
            random_state=42,
            tol=0.01
        )
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.model.fit(obs)
        
        self.is_fitted = True
        
        # Si tenemos resultados de trades, mapear estados a win rates
        if signals is not None and results is not None:
            states = self.predict_forward(obs)
            self._map_states_to_performance(states, signals, results)
        
        return self
    
    def predict_forward_proba(self, obs: np.ndarray) -> np.ndarray:
        """
        Calcula la matriz de probabilidades de estado filtradas forward-only P(S_t = k | O_{1:t}).
        Elimina estrictamente el lookahead bias y la fuga por suavizado (Viterbi/Forward-Backward).
        """
        if not self.is_fitted or self.model is None:
            return np.zeros((len(obs), self.n_states))
        
        n_samples, n_components = obs.shape[0], self.n_states
        if n_samples == 0:
            return np.empty((0, n_components))
            
        from scipy.special import logsumexp

        log_frameprob = self.model._compute_log_likelihood(obs)
        log_alpha = np.zeros((n_samples, n_components))
        log_startprob = np.log(np.maximum(self.model.startprob_, 1e-12))
        log_transmat = np.log(np.maximum(self.model.transmat_, 1e-12))
        
        log_alpha[0] = log_startprob + log_frameprob[0]
        log_alpha[0] -= logsumexp(log_alpha[0])
        
        for t in range(1, n_samples):
            log_alpha[t] = logsumexp(log_alpha[t-1, :, None] + log_transmat, axis=0) + log_frameprob[t]
            log_alpha[t] -= logsumexp(log_alpha[t])
            
        return np.exp(log_alpha)

    def predict_forward(self, obs: np.ndarray) -> np.ndarray:
        """Retorna la secuencia de estados derivada estrictamente de probabilidades forward-only."""
        probs = self.predict_forward_proba(obs)
        if len(probs) == 0:
            return np.array([], dtype=int)
        return np.argmax(probs, axis=1)

    def get_filtered_state_probabilities(self, df: pd.DataFrame) -> np.ndarray:
        """Retorna la matriz completa de probabilidades filtradas P(S_t = k | O_{1:t})."""
        if not self.is_fitted or self.model is None:
            return np.array([])
        obs = self._prepare_observations(df)
        return self.predict_forward_proba(obs)
    
    def _map_states_to_performance(self, states: np.ndarray, 
                                    signals: pd.Series, results: pd.Series):
        """Calcula el win rate por estado para determinar cuáles son favorables."""
        self.state_stats = {}
        
        for state in range(self.n_states):
            state_mask = states == state
            state_indices = np.where(state_mask)[0]
            
            # Filtrar solo los indices donde hubo señal y resultado
            active_in_state = []
            for idx in state_indices:
                if idx in signals.index and signals.loc[idx] in ['CALL', 'PUT']:
                    if idx in results.index and not pd.isna(results.loc[idx]):
                        active_in_state.append(results.loc[idx])
            
            if len(active_in_state) > 5:
                wr = sum(active_in_state) / len(active_in_state)
                self.state_stats[state] = {
                    'win_rate': wr,
                    'n_trades': len(active_in_state),
                    'name': self.STATE_NAMES.get(state, f'STATE_{state}')
                }
        
        # Auto-determinar estados favorables: solo los que tienen WR > breakeven
        breakeven_wr = 1.0 / (1.0 + 0.85)  # ~54.1% para payout 85%
        self.favorable_states = [
            s for s, stats in self.state_stats.items() 
            if stats['win_rate'] > breakeven_wr and stats['n_trades'] >= 10
        ]
    
    def get_current_state(self, df: pd.DataFrame) -> int:
        """Predice el estado actual del mercado usando probabilidades filtradas forward-only."""
        if not self.is_fitted or self.model is None:
            return -1
        
        obs = self._prepare_observations(df)
        if len(obs) == 0:
            return -1
        
        states = self.predict_forward(obs)
        if len(states) == 0:
            return -1
        return int(states[-1])
    
    def should_trade(self, df: pd.DataFrame) -> bool:
        """Retorna True solo si el régimen actual es favorable."""
        if not self.is_fitted:
            return True  # Passthrough si no está entrenado
        
        current = self.get_current_state(df)
        return current in self.favorable_states
    
    def get_regime_report(self, df: pd.DataFrame) -> dict:
        """Genera un reporte del régimen actual."""
        if not self.is_fitted:
            return {'status': 'NOT_FITTED'}
        
        current = self.get_current_state(df)
        return {
            'current_state': current,
            'state_name': self.STATE_NAMES.get(current, 'UNKNOWN'),
            'should_trade': current in self.favorable_states,
            'favorable_states': self.favorable_states,
            'state_stats': self.state_stats
        }
