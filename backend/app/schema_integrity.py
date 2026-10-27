"""Idempotent, non-destructive uniqueness migration for existing ledgers."""
from sqlalchemy import text
from .models import ForwardEvent


def ensure_event_indexes(engine):
    with engine.begin() as connection:
        invalid = connection.execute(text(
            "SELECT COUNT(*) FROM forward_events WHERE "
            "(event_type = 'PREDICTION' AND (model_version IS NULL OR model_version = '' OR "
            "prediction_date IS NULL OR prediction_date = '' OR symbol IS NULL OR symbol = '' OR prediction_id IS NULL)) OR "
            "(event_type = 'OUTCOME' AND (prediction_id IS NULL OR horizon IS NULL))")).scalar()
        if invalid:
            raise RuntimeError('Incomplete forward identities require review; no data was removed')
        for event_type, fields in [('PREDICTION', 'model_version, prediction_date, symbol'),
                                   ('OUTCOME', 'prediction_id, horizon')]:
            duplicate = connection.execute(text(
                f'SELECT COUNT(*) FROM forward_events WHERE event_type = :kind '
                f'GROUP BY {fields} HAVING COUNT(*) > 1 LIMIT 1'), {'kind': event_type}).first()
            if duplicate:
                raise RuntimeError('Duplicate logical ' + event_type + ' records require review; no data was removed')
        for index in ForwardEvent.__table__.indexes:
            if index.name in {'uq_forward_prediction_logical', 'uq_forward_outcome_logical'}:
                index.create(bind=connection, checkfirst=True)
