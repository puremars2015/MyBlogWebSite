from datetime import datetime

from .base import BaseProvider


class YFinanceOptionsProvider(BaseProvider):
    name = 'yfinance_options'

    def fetch(self, series, job):
        import yfinance as yf

        symbol = (job.yfinance_symbol or '').strip() or 'SPY'
        ticker = yf.Ticker(symbol)
        expirations = list(ticker.options or [])
        if not expirations:
            raise RuntimeError(f'yfinance returned no options expirations for {symbol}')

        today = datetime.utcnow().date()
        chosen = None
        for exp in expirations:
            exp_date = datetime.strptime(exp, '%Y-%m-%d').date()
            if exp_date >= today:
                chosen = exp
                break
        if chosen is None:
            chosen = expirations[0]

        chain = ticker.option_chain(chosen)
        puts_oi = float(chain.puts['openInterest'].fillna(0).sum())
        calls_oi = float(chain.calls['openInterest'].fillna(0).sum())
        if calls_oi == 0:
            raise RuntimeError(f'yfinance options chain has 0 call OI for {symbol} {chosen}')

        ratio = puts_oi / calls_oi
        observed_at = datetime.utcnow()

        from app import EconomicObservation
        previous_obs = (
            EconomicObservation.query
            .filter_by(series_id=series.id)
            .order_by(EconomicObservation.observed_at.desc())
            .first()
        )
        previous = float(previous_obs.value) if previous_obs else None

        return self.make_observation(
            series,
            ratio,
            observed_at,
            previous_value=previous,
            change_label=f'基於 {symbol} {chosen}',
            status_label='flat',
        )
