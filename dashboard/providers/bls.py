import os
from datetime import datetime, timedelta

import requests
from .base import BaseProvider


class BLSProvider(BaseProvider):
    name = 'bls'

    ENDPOINT = 'https://api.bls.gov/publicAPI/v2/timeseries/data/'

    def _post(self, series_ids, start_year, end_year):
        api_key = os.getenv('BLS_API_KEY', '').strip()
        payload = {
            'seriesid': list(series_ids),
            'startyear': str(start_year),
            'endyear': str(end_year),
        }
        if api_key:
            payload['registrationkey'] = api_key
        resp = requests.post(self.ENDPOINT, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get('status') != 'REQUEST_SUCCEEDED':
            raise RuntimeError(f'BLS error: {data.get("message") or data}')
        return {row['seriesID']: row['data'] for row in data.get('Results', {}).get('series', [])}

    def fetch(self, series, job):
        raise NotImplementedError(
            'BLS provider requires explicit series-id mapping; '
            'FRED is preferred for now. Use provider="fred".'
        )
