import os
import time
from datetime import datetime, timedelta
from decimal import Decimal

from app import (EconomicFetchJob, EconomicFetchRun, EconomicObservation,
    EconomicSeries, app, db, ensure_schema_and_seed)


POLL_SECONDS = int(os.getenv('DASHBOARD_SCHEDULER_POLL_SECONDS', '30'))


def next_run_for(job, now):
    if job.schedule_type == 'interval_minutes':
        return now + timedelta(minutes=max(job.interval_minutes or 60, 1))
    if job.schedule_type == 'interval_hours':
        return now + timedelta(hours=max(job.interval_minutes or 60, 1) / 60)

    daily_time = job.daily_time or '08:00'
    try:
        hour, minute = [int(part) for part in daily_time.split(':', 1)]
    except ValueError:
        hour, minute = 8, 0
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def run_mock_provider(job):
    series = EconomicSeries.query.filter_by(code=job.series_code).first()
    if not series:
        return f'Series {job.series_code} not found; mock job skipped.'

    latest = EconomicObservation.query.filter_by(series_id=series.id).order_by(EconomicObservation.observed_at.desc()).first()
    base = Decimal(latest.value if latest else 0)
    bump = Decimal('0.01') if series.unit == '%' else Decimal('1.00')
    value = base + bump
    db.session.add(EconomicObservation(
        series_id=series.id,
        observed_at=datetime.utcnow(),
        value=value,
        previous_value=base,
        change_label='Mock 更新',
        status_label='up'
    ))
    return f'Mock updated {series.code} from {base} to {value}.'


def execute_job(job):
    started_at = datetime.utcnow()
    run = EconomicFetchRun(job_id=job.id, started_at=started_at, status='running')
    db.session.add(run)
    db.session.flush()

    try:
        if job.provider == 'mock':
            message = run_mock_provider(job)
        else:
            message = f'Provider {job.provider} is not implemented. API keys should be read from .env.'
        run.status = 'success'
        run.message = message
        job.last_status = 'success'
        job.last_message = message
    except Exception as exc:
        run.status = 'error'
        run.message = str(exc)
        job.last_status = 'error'
        job.last_message = str(exc)
    finally:
        now = datetime.utcnow()
        run.finished_at = now
        job.last_run_at = now
        job.next_run_at = next_run_for(job, now)
        job.updated_at = now
        db.session.commit()


def tick():
    now = datetime.utcnow()
    jobs = EconomicFetchJob.query.filter(
        EconomicFetchJob.is_active == True,
        (EconomicFetchJob.next_run_at == None) | (EconomicFetchJob.next_run_at <= now)
    ).order_by(EconomicFetchJob.id).all()
    for job in jobs:
        execute_job(job)


def main():
    with app.app_context():
        ensure_schema_and_seed()
        while True:
            tick()
            time.sleep(POLL_SECONDS)


if __name__ == '__main__':
    main()
