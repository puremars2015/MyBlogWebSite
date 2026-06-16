from datetime import datetime

from .base import BaseProvider


class TaiwanEconomicProvider(BaseProvider):
    name = 'taiwan_economic'

    def fetch(self, series, job):
        # data.gov.tw does not expose a stable CKAN-like API for these macro series.
        # Keep the job explicit so dashboards show operational status, but require
        # the generic ingest endpoint as a safe fallback instead of fabricating data.
        raise RuntimeError(
            f'{series.code} requires manual ingest fallback: '
            f'POST /api/ingest/{series.code}'
        )
