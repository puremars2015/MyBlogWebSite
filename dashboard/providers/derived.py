from datetime import datetime
from decimal import Decimal

from .base import BaseProvider


class DerivedProvider(BaseProvider):
    name = 'derived'

    def fetch(self, series, job):
        from app import EconomicObservation, EconomicSeries

        sources = (job.derived_sources or '').split(',')
        sources = [s.strip() for s in sources if s.strip()]
        if len(sources) < 2:
            raise ValueError(f'derived job {job.name} needs at least 2 source series')

        op = (job.derived_op or 'sub').lower()

        def latest_value(code):
            s = EconomicSeries.query.filter_by(code=code).first()
            if not s:
                return None, None
            obs = (
                EconomicObservation.query
                .filter_by(series_id=s.id)
                .order_by(EconomicObservation.observed_at.desc())
                .first()
            )
            if not obs:
                return None, None
            return Decimal(obs.value), obs.observed_at

        a_val, a_time = latest_value(sources[0])
        b_val, b_time = latest_value(sources[1])
        if a_val is None or b_val is None:
            raise ValueError(
                f'derived job {job.name}: source data missing for {sources[0]}/{sources[1]}'
            )

        if op == 'sub':
            current = a_val - b_val
        elif op == 'add':
            current = a_val + b_val
        elif op == 'div':
            if b_val == 0:
                raise ValueError(f'derived job {job.name}: division by zero')
            current = a_val / b_val
        else:
            raise ValueError(f'derived job {job.name}: unsupported op {op}')

        observed_at = max(a_time, b_time) if a_time and b_time else datetime.utcnow()
        previous = None
        prev_query = (
            EconomicObservation.query
            .filter_by(series_id=series.id)
            .order_by(EconomicObservation.observed_at.desc())
            .offset(1)
            .first()
        )
        if prev_query is not None:
            previous = float(prev_query.value)

        return self.make_observation(
            series,
            current,
            observed_at,
            previous_value=previous,
            change_label='衍生指標',
            status_label='flat',
        )
