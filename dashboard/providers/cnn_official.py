from datetime import datetime, timezone

from curl_cffi import requests

from .base import BaseProvider


_RATING_LABELS = {
    'extreme fear': 'Extreme Fear',
    'fear': 'Fear',
    'neutral': 'Neutral',
    'greed': 'Greed',
    'extreme greed': 'Extreme Greed',
}


class CNNOfficialFearGreedProvider(BaseProvider):
    name = 'cnn_official_fear_greed'
    ENDPOINT = 'https://production.dataviz.cnn.io/index/fearandgreed/graphdata'

    def fetch(self, series, job):
        session = requests.Session(impersonate='chrome')
        resp = session.get(
            self.ENDPOINT,
            timeout=30,
            headers={
                'Accept': 'application/json',
                'Origin': 'https://www.cnn.com',
                'Referer': 'https://www.cnn.com/',
            },
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f'CNN Fear & Greed endpoint returned HTTP {resp.status_code}: {resp.text[:120]}'
            )
        try:
            data = resp.json()
        except ValueError as exc:
            raise RuntimeError(f'CNN Fear & Greed endpoint returned non-JSON body: {resp.text[:120]}') from exc

        summary = data.get('fear_and_greed') or {}
        if 'score' not in summary or 'timestamp' not in summary:
            raise RuntimeError('CNN Fear & Greed response missing score/timestamp fields')

        value = float(summary['score'])
        observed_at = self._parse_timestamp(summary['timestamp'])
        rating_key = str(summary.get('rating') or '').strip().lower()
        rating_label = _RATING_LABELS.get(rating_key, rating_key.title() or 'Unknown')
        previous_value = (
            float(summary['previous_close'])
            if summary.get('previous_close') is not None
            else None
        )
        change_label = rating_label

        return self.make_observation(
            series,
            value,
            observed_at,
            previous_value=previous_value,
            change_label=change_label,
            status_label='flat',
        )

    @staticmethod
    def _parse_timestamp(raw):
        text = str(raw or '').strip()
        if not text:
            return datetime.utcnow()
        try:
            dt = datetime.fromisoformat(text.replace('Z', '+00:00'))
        except ValueError:
            return datetime.utcnow()
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
