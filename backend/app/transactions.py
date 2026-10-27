"""Atomic paper operations and a process-independent runtime ownership guard."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from hashlib import sha256
from pathlib import Path
import fcntl

from sqlalchemy import event, text
from sqlalchemy.orm import Session

_guard = ContextVar('runtime_commit_guard', default=None)
_owner = ContextVar('runtime_lock_owner', default=None)


def _before_commit(session):
    guard = _guard.get()
    if guard:
        guard()


event.listen(Session, 'before_commit', _before_commit)


def persist(db):
    if db.info.get('atomic_paper_operation'):
        db.flush()
    else:
        db.commit()


def atomic_paper_operation(function):
    @wraps(function)
    def wrapped(db, *args, **kwargs):
        if db.info.get('atomic_paper_operation'):
            return function(db, *args, **kwargs)
        db.info['atomic_paper_operation'] = True
        try:
            result = function(db, *args, **kwargs)
            db.commit()
            return result
        except BaseException:
            db.rollback()
            raise
        finally:
            db.info.pop('atomic_paper_operation', None)
    return wrapped


@contextmanager
def cycle_ownership(db):
    """Postgres transaction lock also works with Neon transaction pooling.

    Use a dedicated pinned transaction: application commits must not release
    ownership. A lost lock connection stops subsequent Session commits.
    """
    bind = db.get_bind()
    engine = bind.engine if hasattr(bind, 'engine') else bind
    if _owner.get() is db:
        yield
        return
    if engine.dialect.name == 'postgresql':
        with engine.connect() as connection:
            transaction = connection.begin()
            token = owner_token = None
            try:
                if not connection.scalar(text('SELECT pg_try_advisory_xact_lock(7351982401)')):
                    raise RuntimeError('Another paper execution owns the runtime lock')
                def verify():
                    if not transaction.is_active or not connection.in_transaction():
                        raise RuntimeError('Runtime lock ownership was lost')
                    connection.execute(text('SELECT 1'))
                token = _guard.set(verify)
                owner_token = _owner.set(db)
                yield
            finally:
                if owner_token is not None:
                    _owner.reset(owner_token)
                if token is not None:
                    _guard.reset(token)
                if transaction.is_active:
                    transaction.rollback()
    elif engine.dialect.name == 'sqlite':
        database = engine.url.database
        identity = str(Path(database).resolve()) if database and database != ':memory:' else str(engine.url)
        filename = '/tmp/nse-runtime-' + sha256(identity.encode()).hexdigest()[:24] + '.lock'
        with open(filename, 'a') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError('Another paper execution owns the runtime lock') from error
            owner_token = _owner.set(db)
            try:
                yield
            finally:
                _owner.reset(owner_token)
                fcntl.flock(handle, fcntl.LOCK_UN)
    else:
        raise RuntimeError('Runtime locking is unsupported for this database')


def exclusive_cycle(function):
    @wraps(function)
    def wrapped(db, *args, **kwargs):
        with cycle_ownership(db):
            return function(db, *args, **kwargs)
    return wrapped
