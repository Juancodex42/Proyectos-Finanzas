from .mean_reversion import MeanReversionStrategy
from .rsi_extremes import RsiExtremesStrategy
from .bollinger_bounce import BollingerBounceStrategy
from .ema_cross import EmaCrossStrategy
from .volatility_squeeze import VolatilitySqueezeStrategy
from .support_resistance import SupportResistanceStrategy
from .genetic_composite import GeneticCompositeStrategy
from .daily_confluence import DailyConfluenceStrategy
from .mtf_tcve import MtfTcveStrategy
from .deesr import DeesrStrategy
from .islg_rs import IslgRsStrategy
from .volatility_squeeze_ml import VolatilitySqueezeMLStrategy
from .climax_reversal import ClimaxReversalStrategy

STRATEGIES = {
    "mean_reversion": MeanReversionStrategy,
    "rsi_extremes": RsiExtremesStrategy,
    "bollinger_bounce": BollingerBounceStrategy,
    "ema_cross": EmaCrossStrategy,
    "volatility_squeeze": VolatilitySqueezeStrategy,
    "support_resistance": SupportResistanceStrategy,
    "genetic_composite": GeneticCompositeStrategy,
    "daily_confluence": DailyConfluenceStrategy,
    "mtf_tcve": MtfTcveStrategy,
    "deesr": DeesrStrategy,
    "islg_rs": IslgRsStrategy,
    "volatility_squeeze_ml": VolatilitySqueezeMLStrategy,
    "climax_reversal": ClimaxReversalStrategy
}
