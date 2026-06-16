import logging
import os
import time
from datetime import datetime, timedelta

from app import (EconomicFetchJob, EconomicFetchRun, EconomicObservation,
    EconomicSeries, app, db, ensure_schema_and_seed)
from providers import get_provider


logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv('DASHBOARD_LOG_LEVEL', 'INFO'))


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


def _resolve_series(job):
    if not job.series_code:
        return None
    return EconomicSeries.query.filter_by(code=job.series_code).first()


def _apply_result(series, result):
    obs = EconomicObservation(
        series_id=series.id,
        observed_at=result['observed_at'],
        value=result['value'],
        previous_value=result.get('previous_value'),
        change_label=result.get('change_label', ''),
        status_label=result.get('status_label', 'flat'),
    )
    db.session.add(obs)


def execute_job(job):
    started_at = datetime.utcnow()
    run = EconomicFetchRun(job_id=job.id, started_at=started_at, status='running')
    db.session.add(run)
    db.session.flush()

    try:
        series = _resolve_series(job)
        if series is None:
            raise ValueError(f'job {job.name}: series {job.series_code} not found')

        provider = get_provider(job.provider)
        result = provider.fetch(series, job)
        if not result:
            raise RuntimeError(f'job {job.name}: provider returned no data')

        _apply_result(series, result)
        run.status = 'success'
        run.message = f'{provider.name} updated {series.code}: {result["value"]}'
        job.last_status = 'success'
        job.last_message = run.message
    except Exception as exc:
        logger.exception('job %s failed', job.name)
        run.status = 'error'
        run.message = str(exc)[:480]
        job.last_status = 'error'
        job.last_message = run.message
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
