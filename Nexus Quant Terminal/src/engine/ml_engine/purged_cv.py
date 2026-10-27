import numpy as np
import pandas as pd

class PurgedGroupTimeSeriesSplit:
    """
    Purged & Embargoed Group TimeSeries Cross-Validator para Opciones Binarias (Metodología Marcos López de Prado).
    Previene la fuga de datos (Data Leakage) entre la ventana de expiración del trade de entrenamiento y la ventana de prueba.
    """
    def __init__(self, n_splits: int = 5, expiry_candles: int = 1, embargo_pct: float = 0.01):
        self.n_splits = n_splits
        self.expiry_candles = expiry_candles
        self.embargo_pct = embargo_pct

    @staticmethod
    def purge_embargo_split(n_samples: int, train_ratio: float = 0.60, expiry_candles: int = 1, embargo_pct: float = 0.01):
        """
        Retorna (is_end_idx, oos_start_idx) con purga de expiración y embargo temporal.
        - IS finaliza en max(0, raw_split - expiry_candles)
        - OOS inicia en min(n_samples, raw_split + embargo_offset)
        """
        raw_split = int(n_samples * train_ratio)
        embargo_offset = max(1, int(n_samples * embargo_pct))
        
        is_end = max(0, raw_split - expiry_candles)
        oos_start = min(n_samples, raw_split + embargo_offset)
        
        return is_end, oos_start

    def get_n_splits(self, X=None, y=None, groups=None):
        return self.n_splits

    def split(self, X, y=None, groups=None):
        n_samples = len(X)
        indices = np.arange(n_samples)
        embargo_offset = int(n_samples * self.embargo_pct)
        test_size = n_samples // self.n_splits

        for i in range(self.n_splits):
            test_start = i * test_size
            test_end = (i + 1) * test_size if i < self.n_splits - 1 else n_samples
            
            # Máscara inicial: todo en train excepto la ventana de test
            train_mask = np.ones(n_samples, dtype=bool)
            train_mask[test_start:test_end] = False

            # Purga previa al test start: si un trade de train vence dentro del conjunto test
            purge_start = max(0, test_start - self.expiry_candles)
            train_mask[purge_start:test_start] = False

            # Embargo posterior al test end: prevenir autocorrelación serial
            embargo_end = min(n_samples, test_end + max(embargo_offset, self.expiry_candles))
            train_mask[test_end:embargo_end] = False

            train_indices = indices[train_mask]
            test_indices = indices[test_start:test_end]
            
            yield train_indices, test_indices


class WalkForwardTimeSeriesSplit:
    """
    Causal Walk-Forward Cross-Validator (Expanding Window con Purga y Embargo).
    Garantiza que el conjunto de entrenamiento siempre preceda estrictamente al conjunto de test
    (train_time < test_time). Cero look-ahead bias, cero entrenamiento con el futuro.
    """
    def __init__(self, n_splits: int = 5, min_train_ratio: float = 0.40, expiry_candles: int = 1, embargo_pct: float = 0.01):
        self.n_splits = max(1, n_splits)
        self.min_train_ratio = min_train_ratio
        self.expiry_candles = expiry_candles
        self.embargo_pct = embargo_pct

    def get_n_splits(self, X=None, y=None, groups=None):
        return self.n_splits

    def split(self, X, y=None, groups=None):
        n_samples = len(X)
        indices = np.arange(n_samples)
        min_train = max(10, int(n_samples * self.min_train_ratio))
        remaining = n_samples - min_train
        if remaining <= 0:
            yield indices[:n_samples//2], indices[n_samples//2:]
            return

        test_size = max(1, remaining // self.n_splits)
        embargo_offset = max(1, int(n_samples * self.embargo_pct))

        for i in range(self.n_splits):
            train_end_raw = min_train + i * test_size
            test_start = min(n_samples, train_end_raw + embargo_offset)
            test_end = min(n_samples, test_start + test_size) if i < self.n_splits - 1 else n_samples

            if test_start >= test_end:
                break

            train_end = max(0, train_end_raw - self.expiry_candles)
            train_indices = indices[0:train_end]
            test_indices = indices[test_start:test_end]

            if len(train_indices) > 0 and len(test_indices) > 0:
                yield train_indices, test_indices
