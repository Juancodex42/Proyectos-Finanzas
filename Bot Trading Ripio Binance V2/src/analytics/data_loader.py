"""
Módulo de carga, validación, limpieza y generación sintética de series temporales.
Soporta formatos OHLCV estándar y snapshots de spreads generados por collect_data.py.
Referencia de diseño: docs/DATA_COLLECTION.md
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, Union
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class DataLoader:
    """Carga, normaliza y preprocesa datos históricos o sintéticos para backtesting."""

    PRICE_FALLBACK_COLS = ("USDT_ARS_mid", "USDC_ARS_mid", "price", "mid")

    def __init__(self, data_dir: Optional[Union[str, Path]] = None):
        self.data_dir = Path(data_dir) if data_dir else PROJECT_ROOT / "data" / "historical"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[DATA LOADER] Initialized - Data dir: {self.data_dir}")

    def _normalize_price_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Asegura que exista una columna `close` si el CSV proviene de collect_data.py."""
        if "close" not in df.columns:
            for col in self.PRICE_FALLBACK_COLS:
                if col in df.columns:
                    df = df.copy()
                    df["close"] = pd.to_numeric(df[col], errors="coerce")
                    break
        return df

    def load_csv(
        self,
        file_path: str,
        date_column: str = "timestamp",
        parse_dates: bool = True,
    ) -> Optional[pd.DataFrame]:
        """Carga un archivo CSV histórico aceptando rutas absolutas o relativas a data_dir."""
        try:
            candidate = Path(file_path)
            if not candidate.exists():
                candidate = self.data_dir / file_path

            if not candidate.exists():
                logger.error(f"[DATA LOADER] File not found: {candidate}")
                return None

            df = pd.read_csv(candidate)
            if date_column not in df.columns:
                logger.error(f"[DATA LOADER] Missing date column: {date_column}")
                return None

            if parse_dates:
                df[date_column] = pd.to_datetime(df[date_column])

            df = self._normalize_price_columns(df)
            df = df.sort_values(date_column).reset_index(drop=True)
            logger.info(f"[DATA LOADER] Loaded {len(df)} rows from {candidate.name}")
            return df

        except Exception as e:
            logger.error(f"[DATA LOADER] Error loading CSV: {e}")
            return None

    def load_json(self, file_path: str) -> Optional[pd.DataFrame]:
        """Carga archivo JSON y lo convierte a DataFrame normalizado."""
        try:
            candidate = Path(file_path)
            if not candidate.exists():
                candidate = self.data_dir / file_path

            if not candidate.exists():
                logger.error(f"[DATA LOADER] File not found: {candidate}")
                return None

            df = pd.read_json(candidate)
            return self._normalize_price_columns(df)
        except Exception as e:
            logger.error(f"[DATA LOADER] Error loading JSON: {e}")
            return None

    def validate_ohlcv_data(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """Valida integridad de datos OHLCV o snapshots de spreads de Ripio."""
        if "timestamp" not in df.columns:
            return False, "Missing columns: ['timestamp']"

        # Soportar formato de collect_data.py (USDT_ARS_mid / USDC_ARS_mid)
        if "USDT_ARS_mid" in df.columns or "USDC_ARS_mid" in df.columns:
            col = "USDT_ARS_mid" if "USDT_ARS_mid" in df.columns else "USDC_ARS_mid"
            if df[col].isnull().all():
                return False, f"Column {col} contains only NaN values"
            return True, "OK"

        required_columns = ["timestamp", "open", "high", "low", "close", "volume"]
        missing = [c for c in required_columns if c not in df.columns]
        if missing:
            return False, f"Missing columns: {missing}"

        if (df["high"] < df["low"]).any():
            return False, "Invalid OHLC: high < low in some rows"

        if ((df["close"] > df["high"]) | (df["close"] < df["low"])).any():
            return False, "Invalid OHLC: close outside [low, high] range"

        if df[required_columns].isnull().any().any():
            return False, "Data contains NaN values"

        if (df["volume"] < 0).any():
            return False, "Negative volume detected"

        return True, "OK"

    def clean_data(
        self,
        df: pd.DataFrame,
        remove_duplicates: bool = True,
        remove_outliers: bool = True,
        outlier_std_threshold: float = 5.0,
    ) -> pd.DataFrame:
        """Limpia duplicados, valores nulos y outliers estadísticos."""
        df_clean = self._normalize_price_columns(df.copy())

        if remove_duplicates and "timestamp" in df_clean.columns:
            df_clean = df_clean.drop_duplicates(subset=["timestamp"])

        if remove_outliers and "close" in df_clean.columns and len(df_clean) > 3:
            returns = df_clean["close"].pct_change()
            std = returns.std()
            if std and std > 0:
                z_scores = np.abs((returns - returns.mean()) / std)
                mask = (z_scores < outlier_std_threshold) | z_scores.isna()
                df_clean = df_clean[mask]

        if "timestamp" in df_clean.columns:
            df_clean = df_clean.sort_values("timestamp")
        return df_clean.reset_index(drop=True)

    def resample_ohlcv(self, df: pd.DataFrame, timeframe: str = "5min") -> pd.DataFrame:
        """Resamplea series OHLCV o de precios medios al timeframe indicado."""
        try:
            df_norm = self._normalize_price_columns(df.copy())
            df_resampled = df_norm.set_index("timestamp")
            agg_rules = {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
                "USDT_ARS_mid": "last",
                "USDC_ARS_mid": "last",
            }
            agg_rules = {k: v for k, v in agg_rules.items() if k in df_resampled.columns}
            df_resampled = df_resampled.resample(timeframe).agg(agg_rules).dropna()
            return df_resampled.reset_index()
        except Exception as e:
            logger.error(f"[DATA LOADER] Error resampling: {e}")
            return df

    def generate_synthetic_data(
        self,
        pair: str = "USDT_ARS",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        freq: str = "5min",
        initial_price: float = 1500.0,
        volatility: float = 0.02,
        seed: Optional[int] = 42,
    ) -> pd.DataFrame:
        """
        Genera series sintéticas con proceso Ornstein-Uhlenbeck (reversión a la media)
        para pares de stablecoins, incluyendo columnas OHLCV y USDT_ARS_mid / USDC_ARS_mid.
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now()

        rng = np.random.default_rng(seed)
        timestamps = pd.date_range(start=start_date, end=end_date, freq=freq)
        n = len(timestamps)

        # Proceso Ornstein-Uhlenbeck alrededor de initial_price para simular stablecoins
        theta = 0.12
        sigma = volatility * initial_price * 0.15
        prices = np.zeros(n, dtype=float)
        usdc_prices = np.zeros(n, dtype=float)
        prices[0] = initial_price
        usdc_prices[0] = initial_price

        for i in range(1, n):
            noise_usdt = rng.normal(0.0, sigma)
            noise_usdc = rng.normal(0.0, sigma * 0.6)
            prices[i] = prices[i - 1] + theta * (initial_price - prices[i - 1]) + noise_usdt
            usdc_prices[i] = usdc_prices[i - 1] + theta * (initial_price - usdc_prices[i - 1]) + noise_usdc

        spread_half = np.maximum(prices * 0.0015, 0.5)
        highs = prices + rng.uniform(0.1, 1.0, size=n) * spread_half
        lows = prices - rng.uniform(0.1, 1.0, size=n) * spread_half
        opens = np.roll(prices, 1)
        opens[0] = prices[0]
        opens = np.clip(opens, lows, highs)
        closes = np.clip(prices, lows, highs)
        volumes = rng.uniform(1000.0, 10000.0, size=n)

        df = pd.DataFrame({
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "price": closes,
            "USDT_ARS_mid": closes,
            "USDC_ARS_mid": usdc_prices,
            "volume": volumes,
            "pair": pair,
        })
        logger.info(f"[DATA LOADER] Generated {len(df)} synthetic bars for {pair}")
        return df

    def split_train_test(
        self,
        df: pd.DataFrame,
        test_size: float = 0.2,
        shuffle: bool = False,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Divide un DataFrame en conjuntos de entrenamiento y prueba."""
        if shuffle:
            df = df.sample(frac=1.0, random_state=42)
        split_idx = int(len(df) * (1.0 - test_size))
        return df.iloc[:split_idx].copy(), df.iloc[split_idx:].copy()

    def save_data(self, df: pd.DataFrame, filename: str) -> bool:
        """Guarda un DataFrame en formato CSV dentro de data_dir."""
        try:
            file_path = self.data_dir / filename
            df.to_csv(file_path, index=False)
            return True
        except Exception as e:
            logger.error(f"[DATA LOADER] Error saving data: {e}")
            return False
