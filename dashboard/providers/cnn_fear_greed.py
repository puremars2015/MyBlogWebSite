from datetime import datetime

import requests
from .base import BaseProvider


class CNNFearGreedProvider(BaseProvider):
    name = 'cnn_fear_greed'
    ENDPOINT = 'https://api.alternative.me/fng/'

    def fetch(self, series, job):
        resp = requests.get(self.ENDPOINT, params={'limit': 30, 'format': 'json'}, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        items = data.get('data') or []
        if not items:
            raise RuntimeError('CNN Fear & Greed API returned no data')

        latest = items[0]
        value = float(latest.get('value'))
        ts = int(latest.get('timestamp'))
        observed_at = datetime.utcfromtimestamp(ts)

        from app import EconomicObservation
        previous_obs = (
            EconomicObservation.query
            .filter_by(series_id=series.id)
            .order_by(EconomicObservation.observed_at.desc())
            .first()
        )
        previous = float(previous_obs.value) if previous_obs else None
        if previous is None and len(items) >= 2:
            previous = float(items[1].get('value'))

        classification = latest.get('value_classification', '')
        change_label = classification

        return self.make_observation(
            series,
            value,
            observed_at,
            previous_value=previous,
            change_label=change_label,
            status_label='flat',
        )
