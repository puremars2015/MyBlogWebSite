import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from .base import BaseProvider


class CBOEProvider(BaseProvider):
    name = 'cboe'
    DAILY_URL = 'https://www.cboe.com/us/options/market_statistics/daily/'

    def fetch(self, series, job):
        resp = requests.get(self.DAILY_URL, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36',
        })
        resp.raise_for_status()
        ratio = self._parse_put_call_ratio(resp.text)
        if ratio is None:
            raise RuntimeError('CBOE put/call ratio not found in daily statistics page')
        return self.make_observation(
            series,
            ratio,
            datetime.utcnow(),
            change_label='CBOE daily stats',
            status_label='flat',
        )

    def _parse_put_call_ratio(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        current_group = ''
        candidates = []

        for tr in soup.find_all('tr'):
            cells = [c.get_text(' ', strip=True) for c in tr.find_all(['th', 'td'])]
            if not cells:
                continue
            if len(cells) == 1:
                current_group = cells[0]
                continue
            if cells[0].upper() != 'VOLUME' or len(cells) < 4:
                continue
            call = self._num(cells[1])
            put = self._num(cells[2])
            if call and put:
                ratio = put / call
                candidates.append((current_group, ratio))

        preferred = [
            item for item in candidates
            if re.search(r'equity|total|options', item[0], re.I)
        ]
        if preferred:
            return preferred[0][1]
        return candidates[0][1] if candidates else None

    @staticmethod
    def _num(raw):
        text = str(raw).replace(',', '').strip()
        try:
            return float(text)
        except ValueError:
            return None
