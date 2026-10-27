"""Real PostgreSQL checks in an isolated schema of a local disposable database."""
import os
import uuid
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import ForwardEvent, Portfolio
from app.transactions import cycle_ownership
from app.schema_integrity import ensure_event_indexes




def event(event_id, **changes):
    return ForwardEvent(event_id=event_id, event_type='PREDICTION', prediction_id=event_id,
                        model_version='control', prediction_date='2026-10-26', symbol='TEST', payload={}, **changes)


def test_postgres_lock_competition_and_release(postgres):
    engine, _ = postgres
    first, second = sessionmaker(bind=engine)(), sessionmaker(bind=engine)()
    try:
        with cycle_ownership(first):
            with pytest.raises(RuntimeError, match='Another paper execution'):
                with cycle_ownership(second):
                    pytest.fail('Concurrent execution acquired the lock')
        with cycle_ownership(second):
            second.add(Portfolio(initial_capital=100000, cash=100000)); second.commit()
    finally:
        first.close(); second.close()


def test_lost_postgres_lock_prevents_account_commit(postgres):
    engine, admin = postgres
    db = sessionmaker(bind=engine)()
    try:
        with cycle_ownership(db):
            db.add(Portfolio(initial_capital=100000, cash=100000)); db.flush()
            # Only this dedicated test database's known runtime advisory key.
            with admin.begin() as connection:
                pid = connection.scalar(text("SELECT pid FROM pg_locks WHERE locktype='advisory' AND granted AND classid=1 AND objid=3057015105"))
                assert pid
                connection.execute(text('SELECT pg_terminate_backend(:pid)'), {'pid': pid})
            with pytest.raises(Exception):
                db.commit()
            db.rollback()
        assert db.query(Portfolio).count() == 0
    finally:
        db.close()


def test_postgres_logical_prediction_and_outcome_keys_are_unique(postgres):
    engine, _ = postgres
    db = sessionmaker(bind=engine)()
    try:
        db.add(event('first')); db.commit()
        db.add(event('different-event-id'))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(ForwardEvent(event_id='out1', event_type='OUTCOME', prediction_id='first', horizon=20, payload={}))
        db.commit()
        db.add(ForwardEvent(event_id='out2', event_type='OUTCOME', prediction_id='first', horizon=20, payload={}))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.query(ForwardEvent).count() == 2
    finally:
        db.close()


def test_migration_refuses_duplicates_without_removing_evidence(postgres):
    engine, _ = postgres
    for index in ForwardEvent.__table__.indexes:
        if index.name.startswith('uq_forward_'):
            index.drop(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add_all([event('first'), event('duplicate')]); db.commit()
        with pytest.raises(RuntimeError, match='require review'):
            ensure_event_indexes(engine)
        assert db.query(ForwardEvent).count() == 2
    finally:
        db.close()


def test_migration_upgrades_existing_clean_schema_idempotently(postgres):
    engine, _ = postgres
    for index in ForwardEvent.__table__.indexes:
        if index.name.startswith('uq_forward_'):
            index.drop(bind=engine)
    ensure_event_indexes(engine); ensure_event_indexes(engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add(event('first')); db.commit()
        db.add(event('duplicate'))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()


def test_migration_refuses_incomplete_identity_without_removing_record(postgres):
    engine, _ = postgres
    db = sessionmaker(bind=engine)()
    try:
        db.add(ForwardEvent(event_id='legacy-incomplete', event_type='PREDICTION', prediction_id='legacy', payload={}))
        db.commit()
        with pytest.raises(RuntimeError, match='Incomplete forward identities'):
            ensure_event_indexes(engine)
        assert db.query(ForwardEvent).count() == 1
    finally:
        db.close()
