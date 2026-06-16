from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

from .base import BaseProvider


class TAIFEXProvider(BaseProvider):
    name = 'taifex'
    DAILY_URL = 'https://www.taifex.com.tw/cht/3/futDailyMarketReport'

    def fetch(self, series, job):
        latest = self._latest_close(start_days_back=1)
        if not latest:
            raise RuntimeError('TAIFEX TX daily close not found in last 14 days')
        previous = self._latest_close(start_days_back=(datetime.utcnow().date() - latest['date']).days + 1)
        previous_value = previous['close'] if previous else None
        return self.make_observation(
            series,
            latest['close'],
            datetime.combine(latest['date'], datetime.min.time()),
            previous_value=previous_value,
            change_label=f"{latest['contract']} 前一交易日收盤",
            status_label='flat',
        )

    def _latest_close(self, start_days_back):
        for days_back in range(start_days_back, start_days_back + 14):
            day = datetime.utcnow().date() - timedelta(days=days_back)
            row = self._fetch_day(day)
            if row:
                return row
        return None

    def _fetch_day(self, day):
        resp = requests.get(self.DAILY_URL, params={
            'queryType': '2',
            'marketCode': '0',
            'commodity_id': 'TX',
            'queryDate': day.strftime('%Y/%m/%d'),
        }, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, 'html.parser')
        for tr in soup.find_all('tr'):
            cells = [c.get_text(' ', strip=True) for c in tr.find_all(['th', 'td'])]
            if len(cells) < 6 or cells[0] != 'TX':
                continue
            try:
                close = float(str(cells[5]).replace(',', ''))
            except ValueError:
                continue
            return {
                'date': day,
                'contract': cells[1],
                'close': close,
            }
        return None
