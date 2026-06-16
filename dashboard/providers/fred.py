import os
from datetime import datetime, timedelta

from .base import BaseProvider


class FREDProvider(BaseProvider):
    name = 'fred'

    def __init__(self):
        self._client = None
        self._init_error = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        if self._init_error is not None:
            raise self._init_error
        api_key = os.getenv('FRED_API_KEY', '').strip()
        if not api_key:
            self._init_error = RuntimeError('FRED_API_KEY is not set')
            raise self._init_error
        try:
            from fredapi import Fred
            self._client = Fred(api_key=api_key)
        except Exception as exc:
            self._init_error = exc
            raise
        return self._client

    def _fetch_series(self, fred_code, start):
        client = self._get_client()
        df = client.get_series(fred_code, observation_start=start)
        if df is None or len(df) == 0:
            return None
        return df.dropna()

    @staticmethod
    def _value_at(df, target_date):
        if df is None or len(df) == 0:
            return None, None
        try:
            idx = df.index.get_indexer([target_date], method='ffill')[0]
        except Exception:
            return None, None
        if idx < 0 or idx >= len(df):
            return None, None
        return float(df.iloc[idx]), df.index[idx].to_pydatetime()

    def fetch(self, series, job):
        fred_code = (series.fred_code or '').strip()
        if not fred_code:
            raise ValueError(f'series {series.code} has no fred_code configured')

        today = datetime.utcnow().date()
        start = today - timedelta(days=400 * 5)
        df = self._fetch_series(fred_code, start)
        if df is None or len(df) == 0:
            raise RuntimeError(f'FRED returned no data for {fred_code}')

        latest_value, latest_date = self._value_at(df, today)
        if latest_value is None:
            latest_value = float(df.iloc[-1])
            latest_date = df.index[-1].to_pydatetime()

        transformation = (series.transformation or 'level').lower()
        unit = series.unit or ''

        if transformation == 'level':
            current = latest_value
            change_label = ''
            previous = None
            if len(df) >= 2:
                previous = float(df.iloc[-2])
                delta = current - previous
                change_label = f'{delta:+.4f}'.rstrip('0').rstrip('.')
        elif transformation == 'yoy':
            target = (df.index[-1].to_pydatetime().date()
                      if hasattr(df.index[-1], 'to_pydatetime') else df.index[-1].date())
            target = target.replace(year=target.year - 1)
            year_ago, _ = self._value_at(df, target)
            if year_ago is None or year_ago == 0:
                raise RuntimeError(f'cannot compute YoY for {fred_code}: missing 1y-ago data')
            current = (latest_value / year_ago - 1) * 100
            change_label = f'{current:+.2f} %'
            previous = None
        elif transformation == 'mom':
            if len(df) < 2:
                raise RuntimeError(f'cannot compute MoM for {fred_code}: insufficient history')
            previous = float(df.iloc[-2])
            current = latest_value - previous
            change_label = f'{current:+,.0f}' if unit == '千人' else f'{current:+.4f}'.rstrip('0').rstrip('.')
        elif transformation == 'mom_pct':
            if len(df) < 2:
                raise RuntimeError(f'cannot compute MoM% for {fred_code}: insufficient history')
            previous = float(df.iloc[-2])
            if previous == 0:
                raise RuntimeError(f'cannot compute MoM% for {fred_code}: prev is zero')
            current = (latest_value / previous - 1) * 100
            change_label = f'{current:+.2f} %'
        else:
            raise ValueError(f'unknown transformation: {transformation}')

        observed_at = latest_date.replace(tzinfo=None) if hasattr(latest_date, 'tzinfo') else latest_date
        return self.make_observation(
            series,
            current,
            observed_at,
            previous_value=previous if transformation != 'level' else previous,
            change_label=change_label,
            status_label='flat',
        )
