from .base import BaseProvider
from .fred import FREDProvider
from .bls import BLSProvider
from .yfinance import YFinanceProvider
from .yfinance_options import YFinanceOptionsProvider
from .twse_openapi import TWSEOpenAPIProvider
from .derived import DerivedProvider
from .cboe import CBOEProvider
from .cnn_official import CNNOfficialFearGreedProvider
from .taiwan_economic import TaiwanEconomicProvider
from .taifex import TAIFEXProvider


_REGISTRY = {
    'fred': FREDProvider,
    'bls': BLSProvider,
    'yfinance': YFinanceProvider,
    'yfinance_options': YFinanceOptionsProvider,
    'twse_openapi': TWSEOpenAPIProvider,
    'derived': DerivedProvider,
    'cboe': CBOEProvider,
    'cnn_official_fear_greed': CNNOfficialFearGreedProvider,
    'taiwan_economic': TaiwanEconomicProvider,
    'taifex': TAIFEXProvider,
}


def get_provider(name):
    cls = _REGISTRY.get((name or '').strip())
    if cls is None:
        raise ValueError(f'unknown provider: {name!r}')
    return cls()


__all__ = [
    'BaseProvider',
    'get_provider',
]
