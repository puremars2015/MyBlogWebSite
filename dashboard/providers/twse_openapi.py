from datetime import datetime, timedelta, timezone
from decimal import Decimal

import requests
from .base import BaseProvider


class TWSEOpenAPIProvider(BaseProvider):
    name = 'twse_openapi'

    FOREIGN_URL = 'https://www.twse.com.tw/rwd/zh/fund/BFI82U'
    MARGIN_URL = 'https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN'
    INDEX_URL = 'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX'

    TW_TZ = timezone(timedelta(hours=8))

    @classmethod
    def _now_gmt8(cls):
        return datetime.now(cls.TW_TZ).replace(tzinfo=None)

    def _today_roc(self):
        today = self._now_gmt8()
        return today.year - 1911, today.strftime('%Y%m%d')

    def _get(self, url, params):
        last_error = None
        for timeout in (60, 90):
            try:
                resp = requests.get(url, params=params, timeout=timeout,
                                    headers={'User-Agent': 'Mozilla/5.0'})
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.RequestException as exc:
                last_error = exc
        raise last_error

    def fetch(self, series, job):
        code = series.code
        if code == 'twse_index':
            return self._fetch_index(series, job)
        if code in {'tw_foreign_net', 'tw_trust_net', 'tw_dealer_net'}:
            return self._fetch_fund_flow(series, job)
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

    def _fetch_fund_flow(self, series, job):
        records, observed_at = self._records_with_date_fallback(self.FOREIGN_URL, 'data')
        value = self._fund_flow_value(series.code, records)
        direction = '買超' if value > 0 else '賣超' if value < 0 else '持平'
        status_label = 'up' if value > 0 else 'down' if value < 0 else 'flat'
        return self.make_observation(
            series,
            value,
            observed_at,
            previous_value=None,
            change_label=f'{direction} · 每日收盤 / 億元',
            status_label=status_label,
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
        return self._recent_records_with_date_fallback(url, key, count=1)[0]

    def _recent_records_with_date_fallback(self, url, key, count=1):
        latest = self._get_latest(url, key)
        snapshots = [latest] if latest else []
        for days_back in range(0, 14):
            day = self._now_gmt8() - timedelta(days=days_back)
            try:
                data = self._get(url, {
                    'response': 'json',
                    'date': day.strftime('%Y%m%d'),
                    'dayDate': day.strftime('%Y%m%d'),
                })
            except requests.exceptions.RequestException:
                continue
            records = self._extract_records(data, key)
            if not records:
                continue
            observed_at = self._parse_twse_date(data.get('date'))
            if any(existing[1].date() == observed_at.date() for existing in snapshots):
                continue
            snapshots.append((records, observed_at))
            if len(snapshots) >= count:
                break
        if not snapshots:
            raise RuntimeError(f'TWSE {url} returned no records in last 14 days')
        return snapshots[:count]

    def _get_latest(self, url, key):
        params = {'response': 'json'}
        if key == 'margin':
            params['selectType'] = 'MS'
        data = self._get(url, params)
        records = self._extract_records(data, key)
        if not records:
            return None
        raw_date = str(data.get('date') or '')
        observed_at = self._now_gmt8()
        if len(raw_date) == 8 and raw_date.isdigit():
            observed_at = self._parse_twse_date(raw_date)
        return records, observed_at

    def _fund_flow_value(self, code, records):
        if not records:
            return None
        if code == 'tw_foreign_net':
            row = next((r for r in records if r and '外資及陸資(不含外資自營商)' in str(r[0])), None)
            if row is None:
                raise RuntimeError(f'TWSE foreign row not found: {records[:4]}')
            return self._net_billions(row)
        if code == 'tw_trust_net':
            row = next((r for r in records if r and str(r[0]) == '投信'), None)
            if row is None:
                raise RuntimeError(f'TWSE trust row not found: {records[:4]}')
            return self._net_billions(row)
        if code == 'tw_dealer_net':
            dealer_rows = [r for r in records if r and str(r[0]).startswith('自營商(')]
            if not dealer_rows:
                raise RuntimeError(f'TWSE dealer rows not found: {records[:4]}')
            return sum(self._net_billions(row) for row in dealer_rows)
        raise ValueError(f'unsupported fund flow series: {code}')

    @staticmethod
    def _net_billions(row):
        try:
            return float(str(row[3]).replace(',', '')) / 100000000
        except (IndexError, ValueError) as exc:
            raise RuntimeError(f'TWSE fund payload unexpected: {row}') from exc

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
        return TWSEOpenAPIProvider._now_gmt8()
