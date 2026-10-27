import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.transactions import cycle_ownership


def test_competing_sessions_cannot_own_cycle_and_release_allows_retry(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'lock.db'))
    first, second = sessionmaker(bind=engine)(), sessionmaker(bind=engine)()
    try:
        with cycle_ownership(first):
            with cycle_ownership(first):
                pass  # Nested execution helpers reuse the same ownership.
            with pytest.raises(RuntimeError, match='Another paper execution'):
                with cycle_ownership(second):
                    pytest.fail('Conflicting session acquired ownership')
        with cycle_ownership(second):
            pass
    finally:
        first.close(); second.close(); engine.dispose()
