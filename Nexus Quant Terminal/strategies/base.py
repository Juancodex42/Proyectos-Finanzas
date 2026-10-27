import pandas as pd

class BaseStrategy:
    name: str = "Base Strategy"
    description: str = "Base class for all strategies"
    
    def get_params_schema(self) -> list[dict]:
        """Returns [{name, type, default, min, max, step, description}]"""
        pass
    
    def prepare_data(self, df: pd.DataFrame) -> dict:
        """Precomputes indicator series/DataFrames once for fast signal generation."""
        return {}

    def generate_signals(self, df: pd.DataFrame, params: dict = None, precomputed: dict = None, **kwargs) -> pd.Series:
        """Returns Series with values: 'CALL', 'PUT', or None for each row.
        df has columns: open_time, open, high, low, close, volume, datetime"""
        pass

