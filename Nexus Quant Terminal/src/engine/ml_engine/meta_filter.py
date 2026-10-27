import pandas as pd
import numpy as np

class BinaryMLMetaFilter:
    """
    Clasificador Meta-Labeling ML para Opciones Binarias.
    Actúa como Filtro de Alta Confianza procesando únicamente operaciones donde P(WIN) >= probability_threshold.
    """
    def __init__(self, probability_threshold: float = 0.65, model_type: str = 'auto',
                 adaptive_threshold: bool = True):
        self.base_threshold = probability_threshold
        self.probability_threshold = probability_threshold
        self.adaptive_threshold = adaptive_threshold
        self.model = None
        self.is_fitted = False

        # Inicializar modelo con fallback robusto
        if model_type == 'lgb':
            try:
                import lightgbm as lgb
                self.model = lgb.LGBMClassifier(
                    n_estimators=100, max_depth=4, num_leaves=15,
                    learning_rate=0.03, subsample=0.8, colsample_bytree=0.8,
                    random_state=42, verbose=-1
                )
            except ImportError:
                from sklearn.ensemble import HistGradientBoostingClassifier
                self.model = HistGradientBoostingClassifier(
                    max_iter=100, max_depth=4, learning_rate=0.03, random_state=42
                )
        else:
            from sklearn.ensemble import HistGradientBoostingClassifier
            self.model = HistGradientBoostingClassifier(
                max_iter=100, max_depth=4, learning_rate=0.03, random_state=42
            )

    def fit(self, X: pd.DataFrame, y: pd.Series):
        if X is None or len(X) == 0 or y is None or len(y) == 0:
            return self

        # Eliminar NaN e infinitos
        X_clean = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        
        # Validar balance de clases
        unique_classes = np.unique(y)
        if len(unique_classes) < 2:
            self.is_fitted = False
            return self

        self.model.fit(X_clean, y)
        self.is_fitted = True
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted or X is None or len(X) == 0:
            return np.full(len(X) if X is not None else 0, 0.5)

        X_clean = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        probs = self.model.predict_proba(X_clean)
        if probs.shape[1] > 1:
            return probs[:, 1]  # Probabilidad de WIN (clase 1)
        return probs[:, 0]

    def filter_signals(self, signals: pd.Series, X: pd.DataFrame) -> pd.Series:
        """
        Filtra la serie de señales original devolviendo SOLO aquellas donde P(WIN) >= threshold.
        """
        has_natr = self.adaptive_threshold and ('natr' in X.columns)
        if has_natr:
            natr_series = X['natr']
            natr_median_series = natr_series.rolling(100, min_periods=1).median()

        filtered_signals = pd.Series(index=signals.index, data=None, dtype=object)
        
        if not self.is_fitted:
            return signals  # Passthrough si no está entrenado

        active_mask = signals.isin(['CALL', 'PUT'])
        active_indices = signals[active_mask].index

        if len(active_indices) == 0:
            return filtered_signals

        X_active = X.loc[active_indices]
        win_probs = self.predict_proba(X_active)

        for idx, prob in zip(active_indices, win_probs):
            eff_threshold = self.base_threshold
            if has_natr and idx in natr_series.index:
                c_natr = natr_series.loc[idx]
                m_natr = natr_median_series.loc[idx]
                if c_natr > m_natr * 1.5:
                    eff_threshold = min(self.base_threshold + 0.10, 0.85)
                elif c_natr < m_natr * 0.5:
                    eff_threshold = max(self.base_threshold - 0.05, 0.55)
                else:
                    eff_threshold = self.base_threshold
            self.probability_threshold = eff_threshold

            if prob >= eff_threshold:
                filtered_signals.loc[idx] = signals.loc[idx]

        return filtered_signals
