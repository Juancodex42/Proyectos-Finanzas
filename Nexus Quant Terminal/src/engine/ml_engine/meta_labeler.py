import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from engine.ml_engine.feature_extractor import BinaryFeatureExtractor

class MetaLabeler:
    """
    Implementación de Meta-Labeling (López de Prado, AFML Ch. 3.6).
    
    Pipeline:
    1. El modelo primario (estrategia) genera señales CALL/PUT
    2. El meta-modelo aprende CUÁNDO esas señales son correctas
    3. Solo se ejecutan señales donde P(correcta) >= threshold
    
    La clave: el meta-modelo usa features de CONTEXTO DE MERCADO,
    NO las mismas features que la estrategia usa para decidir dirección.
    """
    def __init__(self, threshold: float = 0.65):
        self.threshold = threshold
        self.meta_model = HistGradientBoostingClassifier(
            max_iter=200, max_depth=3, learning_rate=0.05,
            min_samples_leaf=20, l2_regularization=1.0,
            random_state=42
        )
        self.is_fitted = False
        self.feature_names = []
    
    def _extract_context_features(self, df: pd.DataFrame, 
                                   signal_indices: pd.Index) -> pd.DataFrame:
        """
        Extrae features de CONTEXTO (no de señal).
        Estas features capturan el ESTADO del mercado en el momento de la señal.
        Funciona con DataFrames cortos (< 50 filas) usando solo features temporales
        y rolling reducidas cuando BinaryFeatureExtractor no puede extraer.
        """
        context = pd.DataFrame(index=signal_indices)

        if signal_indices is None or len(signal_indices) == 0:
            return context

        # Intentar extraer features completas (requiere >= 50 filas)
        base_features = BinaryFeatureExtractor.extract_features(df)
        if not base_features.empty:
            available_idx = signal_indices.intersection(base_features.index)
            for col in base_features.columns:
                context.loc[available_idx, col] = base_features.loc[available_idx, col]

        # Features temporales (siempre disponibles si existe open_time)
        if 'open_time' in df.columns:
            open_times = df['open_time'].reindex(signal_indices)
            if pd.api.types.is_datetime64_any_dtype(open_times):
                times = open_times
            else:
                valid_num = pd.to_numeric(open_times, errors='coerce').dropna()
                if not valid_num.empty:
                    max_val = valid_num.abs().max()
                    if max_val > 1e17:
                        unit = 'ns'
                    elif max_val > 1e14:
                        unit = 'us'
                    elif max_val > 1e11:
                        unit = 'ms'
                    else:
                        unit = 's'
                    times = pd.to_datetime(open_times, unit=unit, errors='coerce')
                else:
                    times = pd.to_datetime(open_times, errors='coerce')

            if not times.isna().all():
                context['hour_of_day'] = times.dt.hour.values
                context['day_of_week'] = times.dt.dayofweek.values
                context['is_session_overlap'] = ((times.dt.hour >= 13) &
                                                  (times.dt.hour <= 17)).astype(int).values

        # Micro-features de régimen (rolling adaptativas al tamaño del df)
        close = df['close']
        returns = close.pct_change()

        n = len(df)
        win10 = min(10, max(2, n // 3))
        win30 = min(30, max(3, n // 2))
        win20 = min(20, max(2, n // 2))

        context['realized_vol_10'] = returns.rolling(win10).std().reindex(signal_indices).values
        context['realized_vol_30'] = returns.rolling(win30).std().reindex(signal_indices).values
        context['vol_ratio'] = (
            context['realized_vol_10'] /
            context['realized_vol_30'].replace(0, 1e-8)
        )

        shifted_ret = returns.shift(min(5, n // 4))
        context['autocorr_5'] = returns.rolling(win20).corr(shifted_ret).reindex(signal_indices).values
        context['skew_20'] = returns.rolling(win20).skew().reindex(signal_indices).values

        result = context.replace([np.inf, -np.inf], np.nan).ffill().fillna(0.0)
        return result
    
    def fit(self, df: pd.DataFrame, signals: pd.Series, 
            results: pd.Series) -> 'MetaLabeler':
        """
        Entrena el meta-modelo.
        
        signals: Serie con CALL/PUT/None del modelo primario
        results: Serie con 1 (WIN) / 0 (LOSS) para cada señal
        """
        # Solo usar filas donde hubo señal y resultado conocido
        active_mask = signals.isin(['CALL', 'PUT']) & results.notna()
        active_idx = signals[active_mask].index
        
        if len(active_idx) < 30:
            return self
        
        X = self._extract_context_features(df, active_idx)
        if X.empty or len(X) < 30:
            return self
        
        y = results.loc[active_idx].astype(int)
        
        # Verificar balance de clases
        if len(np.unique(y)) < 2:
            return self
        
        self.feature_names = list(X.columns)
        self.meta_model.fit(X, y)
        self.is_fitted = True
        
        return self
    
    def filter(self, df: pd.DataFrame, signals: pd.Series) -> pd.Series:
        """
        Filtra señales usando el meta-modelo.
        Retorna solo las señales donde P(WIN) >= threshold.
        """
        filtered = pd.Series(index=signals.index, data=None, dtype=object)
        
        if not self.is_fitted:
            return signals  # Passthrough
        
        active_mask = signals.isin(['CALL', 'PUT'])
        active_idx = signals[active_mask].index
        
        if len(active_idx) == 0:
            return filtered
        
        X = self._extract_context_features(df, active_idx)
        if X.empty:
            return signals
        
        # Alinear features con el modelo entrenado
        for col in self.feature_names:
            if col not in X.columns:
                X[col] = 0.0
        X = X[self.feature_names]
        
        probas = self.meta_model.predict_proba(X)
        win_probs = probas[:, 1] if probas.shape[1] > 1 else probas[:, 0]
        
        for idx, prob in zip(active_idx, win_probs):
            if prob >= self.threshold:
                filtered.loc[idx] = signals.loc[idx]
        
        return filtered
    
    def get_feature_importance(self) -> dict:
        """Retorna importancia de features del meta-modelo."""
        if not self.is_fitted:
            return {}
        importances = self.meta_model.feature_importances_
        return dict(sorted(
            zip(self.feature_names, importances),
            key=lambda x: x[1], reverse=True
        ))
