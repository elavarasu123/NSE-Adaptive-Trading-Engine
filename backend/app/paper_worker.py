"""Disabled-by-default entrypoint for a separately approved scheduled worker.

No web server, broker integration, portfolio initialization or force mode.
"""
from datetime import datetime, timezone
import json
import os

from sqlalchemy.engine import make_url
from .database import SessionLocal
from .models import Portfolio
from .runtime import load_state, run_cycle
from .scheduled_recovery import execution_due
from .transactions import exclusive_cycle
from scripts.ensure_market_history import ensure_history


def now():
    return datetime.now(timezone.utc)


def validate_configuration(environ):
    try:
        backend = make_url(environ.get('DATABASE_URL', '')).get_backend_name()
    except Exception:
        backend = None
    if (backend not in {'postgres', 'postgresql'}
            or environ.get('SHARED_STATE_BACKEND') != 'db'):
        raise RuntimeError('Worker requires the existing shared PostgreSQL database')
    if (environ.get('RUNTIME_SOURCE') != 'SCHEDULED_PAPER_WORKER'
            or environ.get('PUBLIC_DASHBOARD_READ_ONLY', '').lower() != 'false'
            or environ.get('MARKET_PROVIDER') != 'yahoo'):
        raise RuntimeError('Worker requires its dedicated paper execution configuration')
    if environ.get('FORCE_RUNTIME', '').lower() in {'true', '1', 'yes', 'on'}:
        raise RuntimeError('Force mode is forbidden for the scheduled worker')


def existing_portfolio(db):
    if db.get(Portfolio, 1) is None:
        raise RuntimeError('Worker will not initialize or fund a portfolio; use the existing canonical database')


@exclusive_cycle
def execute_due(db):
    # Recheck inside the same cross-process lock as the actual cycle. A second
    # executor may have completed the slot while market history was downloading.
    due, reason = execution_due(load_state(), now())
    if not due:
        return {'status': 'SKIPPED', 'reason': reason}
    existing_portfolio(db)
    return run_cycle(db)


def main():
    if os.getenv('WORKER_EXECUTION_ENABLED', '').lower() != 'true':
        print(json.dumps({'status': 'DISABLED', 'reason': 'Explicit worker activation required'}))
        return 0
    validate_configuration(os.environ)
    from .scheduler_guard import session_guard
    if not session_guard(now()).should_run:
        print(json.dumps({'status': 'SKIPPED', 'reason': 'OUTSIDE_EXECUTION_WINDOW'}))
        return 0
    db = SessionLocal()
    try:
        existing_portfolio(db)
        due, reason = execution_due(load_state(), now())
        if not due:
            print(json.dumps({'status': 'SKIPPED', 'reason': reason}))
            return 0
        db.rollback()  # Release the read-only transaction before network I/O.
        ensure_history(force=session_guard(now()).in_post_close_window)
        result = execute_due(db)
        print(json.dumps({key: result.get(key) for key in ['status', 'reason', 'runId', 'completedAt']}, default=str))
        return 0 if result.get('status') in {'HEALTHY', 'SKIPPED'} else 1
    finally:
        db.close()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        # Provider/connection errors can contain credentials. Keep them out of
        # public process output; canonical runtime evidence holds cycle failures.
        print(json.dumps({'status': 'ERROR', 'errorType': type(error).__name__}))
        raise SystemExit(1)
