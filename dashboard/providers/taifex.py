from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from .base import BaseProvider


class TAIFEXProvider(BaseProvider):
    name = 'taifex'
    DAILY_URL = 'https://www.taifex.com.tw/cht/3/futDailyMarketReport'

    TW_TZ = timezone(timedelta(hours=8))
    VOLUME_SHARE_CODES = {
        'tx_volume_share': 'TX',
        'mtx_volume_share': 'MTX',
        'tmf_volume_share': 'TMF',
    }

    @classmethod
    def _now_gmt8(cls):
        return datetime.now(cls.TW_TZ).replace(tzinfo=None)

    def fetch(self, series, job):
        if series.code == 'txf_price':
            latest = self._latest_close(start_days_back=1)
            if not latest:
                raise RuntimeError('TAIFEX TX daily close not found in last 14 days')
            previous = self._latest_close(start_days_back=(self._now_gmt8().date() - latest['date']).days + 1)
            previous_value = previous['close'] if previous else None
            return self.make_observation(
                series,
                latest['close'],
                datetime.combine(latest['date'], datetime.min.time()),
                previous_value=previous_value,
                change_label=f"{latest['contract']} 前一交易日收盤",
                status_label='flat',
            )
        if series.code in self.VOLUME_SHARE_CODES:
            return self._fetch_volume_share(series)
        raise ValueError(f'TAIFEX provider cannot handle series {series.code}')

    def _fetch_volume_share(self, series):
        latest = self._latest_volume_mix(start_days_back=1)
        if not latest:
            raise RuntimeError('TAIFEX TX/MTX/TMF volume mix not found in last 14 days')
        previous = self._latest_volume_mix(start_days_back=(self._now_gmt8().date() - latest['date']).days + 1)
        contract = self.VOLUME_SHARE_CODES[series.code]
        previous_value = previous['shares'].get(contract) if previous else None
        return self.make_observation(
            series,
            latest['shares'][contract],
            datetime.combine(latest['date'], datetime.min.time()),
            previous_value=previous_value,
            change_label='TX/MTX/TMF 全契約合計成交量占比',
            status_label='flat',
        )

    def _latest_close(self, start_days_back):
        for days_back in range(start_days_back, start_days_back + 14):
            day = self._now_gmt8().date() - timedelta(days=days_back)
            row = self._fetch_day(day)
            if row:
                return row
        return None

    def _latest_volume_mix(self, start_days_back):
        for days_back in range(start_days_back, start_days_back + 14):
            day = self._now_gmt8().date() - timedelta(days=days_back)
            snapshot = self._fetch_day_volume_mix(day)
            if snapshot:
                return snapshot
        return None

    def _fetch_day_volume_mix(self, day):
        volumes = {}
        for contract in self.VOLUME_SHARE_CODES.values():
            rows = self._fetch_day_rows(day, contract)
            if not rows:
                return None
            volumes[contract] = sum(self._parse_number(row[10], as_int=True) for row in rows)
        total_volume = sum(volumes.values())
        if total_volume <= 0:
            return None
        return {
            'date': day,
            'volumes': volumes,
            'shares': {
                contract: volumes[contract] / total_volume * 100
                for contract in volumes
            },
        }

    def _fetch_day(self, day):
        rows = self._fetch_day_rows(day, 'TX')
        if not rows:
            return None
        cells = rows[0]
        try:
            close = self._parse_number(cells[5])
        except ValueError:
            return None
        return {
            'date': day,
            'contract': cells[1],
            'close': close,
        }

    def _fetch_day_rows(self, day, commodity_id):
        resp = requests.get(self.DAILY_URL, params={
            'queryType': '2',
            'marketCode': '0',
            'commodity_id': commodity_id,
            'queryDate': day.strftime('%Y/%m/%d'),
        }, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, 'html.parser')
        rows = []
        for tr in soup.find_all('tr'):
            cells = [c.get_text(' ', strip=True) for c in tr.find_all(['th', 'td'])]
            if len(cells) < 11 or cells[0] != commodity_id:
                continue
            if '/' in cells[1]:
                continue
            rows.append(cells)
        return rows

    @staticmethod
    def _parse_number(raw_value, as_int=False):
        normalized = str(raw_value).replace(',', '').strip()
        if normalized in {'', '-'}:
            raise ValueError(f'invalid numeric value: {raw_value!r}')
        return int(normalized) if as_int else float(normalized)
