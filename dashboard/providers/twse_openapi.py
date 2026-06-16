from datetime import datetime, timedelta
from decimal import Decimal

import requests
from .base import BaseProvider


class TWSEOpenAPIProvider(BaseProvider):
    name = 'twse_openapi'

    FOREIGN_URL = 'https://www.twse.com.tw/rwd/zh/fund/BFI82U'
    MARGIN_URL = 'https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN'
    INDEX_URL = 'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX'

    def _today_roc(self):
        today = datetime.utcnow()
        return today.year - 1911, today.strftime('%Y%m%d')

    def _get(self, url, params):
        resp = requests.get(url, params=params, timeout=20,
                            headers={'User-Agent': 'Mozilla/5.0'})
        resp.raise_for_status()
        return resp.json()

    def fetch(self, series, job):
        code = series.code
        if code == 'twse_index':
            return self._fetch_index(series, job)
        if code == 'tw_foreign_net':
            return self._fetch_foreign(series, job)
        if code == 'tw_margin_balance':
            return self._fetch_margin(series, job)
        raise ValueError(f'TWSE provider cannot handle series {code}')

    def _fetch_index(self, series, job):
        data = self._get(self.INDEX_URL, {
            'response': 'json',
            'type': 'IND',
        })
        records = self._extract_records(data, 'index')
        if not records:
            raise RuntimeError('TWSE index returned no records')
        row = next((r for r in records if r and str(r[0]) == '發行量加權股價指數'), records[0])
        try:
            value = float(str(row[1]).replace(',', ''))
        except (IndexError, ValueError) as exc:
            raise RuntimeError(f'TWSE index payload unexpected: {row}') from exc
        observed_at = self._parse_twse_date(data.get('date'))
        return self.make_observation(
            series,
            value,
            observed_at,
            previous_value=None,
            change_label=row[3] if len(row) > 3 else '',
            status_label='flat',
        )

    def _fetch_foreign(self, series, job):
        records, observed_at = self._records_with_date_fallback(self.FOREIGN_URL, 'data')
        row = next((r for r in records if r and '外資' in str(r[0])), None)
        if row is None:
            raise RuntimeError(f'TWSE foreign row not found: {records[:4]}')
        try:
            value = float(str(row[3]).replace(',', '')) / 100000000
        except (IndexError, ValueError) as exc:
            raise RuntimeError(f'TWSE foreign payload unexpected: {row}') from exc
        return self.make_observation(
            series,
            value,
            observed_at,
            previous_value=None,
            change_label='單位: 億元',
            status_label='flat',
        )

    def _fetch_margin(self, series, job):
        records, observed_at = self._records_with_date_fallback(self.MARGIN_URL, 'margin')
        latest = next((r for r in records if r and '融資金額' in str(r[0])), records[-1])
        try:
            value = float(str(latest[5]).replace(',', ''))
        except (IndexError, ValueError) as exc:
            raise RuntimeError(f'TWSE margin payload unexpected: {latest}') from exc
        return self.make_observation(
            series,
            value,
            observed_at,
            previous_value=None,
            change_label='融資餘額 (千元)',
            status_label='flat',
        )

    def _records_with_date_fallback(self, url, key):
        latest = self._get_latest(url, key)
        if latest:
            return latest
        for days_back in range(0, 8):
            day = datetime.utcnow() - timedelta(days=days_back)
            data = self._get(url, {
                'response': 'json',
                'date': day.strftime('%Y%m%d'),
                'dayDate': day.strftime('%Y%m%d'),
            })
            records = self._extract_records(data, key)
            if records:
                return records, day.replace(hour=0, minute=0, second=0, microsecond=0)
        raise RuntimeError(f'TWSE {url} returned no records in last 8 days')

    def _get_latest(self, url, key):
        params = {'response': 'json'}
        if key == 'margin':
            params['selectType'] = 'MS'
        data = self._get(url, params)
        records = self._extract_records(data, key)
        if not records:
            return None
        raw_date = str(data.get('date') or '')
        observed_at = datetime.utcnow()
        if len(raw_date) == 8 and raw_date.isdigit():
            observed_at = self._parse_twse_date(raw_date)
        return records, observed_at

    @staticmethod
    def _extract_records(data, key):
        if key == 'margin':
            tables = data.get('tables') or []
            if tables:
                return tables[0].get('data') or []
            return []
        if key == 'index':
            tables = data.get('tables') or []
            if tables:
                return tables[0].get('data') or []
            return []
        return data.get(key) or []

    @staticmethod
    def _parse_twse_date(raw_date):
        text = str(raw_date or '')
        if len(text) == 8 and text.isdigit():
            return datetime.strptime(text, '%Y%m%d')
        return datetime.utcnow()
