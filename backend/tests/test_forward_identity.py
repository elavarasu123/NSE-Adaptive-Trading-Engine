import pytest
from app import shared_state


@pytest.mark.parametrize('event', [
    {'eventType': 'PREDICTION', 'predictionId': 'missing-fields'},
    {'eventType': 'OUTCOME', 'predictionId': 'missing-horizon'},
    {'eventType': 'OUTCOME', 'predictionId': 'wrong-horizon', 'horizon': 1},
    {'eventType': 'UNKNOWN'},
])
def test_invalid_forward_identity_is_rejected_before_any_db_write(monkeypatch, event):
    def forbidden():
        raise AssertionError('Invalid identity must not reach the database')
    monkeypatch.setattr(shared_state, 'SessionLocal', forbidden)
    with pytest.raises(ValueError):
        shared_state.append_forward_event(event)
