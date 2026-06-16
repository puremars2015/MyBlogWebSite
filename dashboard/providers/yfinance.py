from datetime import datetime
from decimal import Decimal

from .base import BaseProvider


class YFinanceProvider(BaseProvider):
    name = 'yfinance'

    def fetch(self, series, job):
        import yfinance as yf

        symbol = (job.yfinance_symbol or '').strip() or (series.fred_code or '').strip()
        if not symbol:
            raise ValueError(f'series {series.code} has no yfinance_symbol configured')

        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='5d', auto_adjust=False)
        if hist is None or len(hist) == 0:
            raise RuntimeError(f'yfinance returned no data for {symbol}')

        closes = hist['Close'].dropna()
        if len(closes) == 0:
            raise RuntimeError(f'yfinance returned no close prices for {symbol}')

        current = float(closes.iloc[-1])
        previous = float(closes.iloc[-2]) if len(closes) >= 2 else None
        observed_at = closes.index[-1].to_pydatetime()
        if observed_at.tzinfo is not None:
            observed_at = observed_at.replace(tzinfo=None)

        return self.make_observation(
            series,
            current,
            observed_at,
            previous_value=previous,
            change_label='',
            status_label='flat',
        )
