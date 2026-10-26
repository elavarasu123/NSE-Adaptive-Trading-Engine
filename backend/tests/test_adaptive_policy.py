from datetime import date, timedelta
import copy
import math
import pytest
from app.adaptive_policy import learn_entry_policy, entry_threshold


def observations(validation_reverses=False):
    rows = []
    start = date(2025, 1, 1)
    for day in range(130):
        high = day % 2 == 0
        value = .08 if high else -.10
        if validation_reverses and day >= 90:
            value = -.08 if high else .10
        for stock in range(3):
            rows.append({'modelVersion': 'champion-v0.2-frozen', 'predictionId': f'{day}-{stock}',
                         'predictionDate': str(start + timedelta(days=day)), 'symbol': str(stock),
                         'regime': 'RISK_ON', 'score': 90 if high else 76,
                         'outcomes': {'20D': {'maturityDate': str(start + timedelta(days=day + 20)),
                                               'stockReturn': value, 'niftyReturn': 0.}}})
    return rows


def test_waiting_evidence_does_not_claim_learning():
    policy = learn_entry_policy([], '2026-01-01')
    assert policy['status'] == 'BASELINE_RETAINED'
    assert policy['matured20D'] == 0
    assert entry_threshold(policy, 'RISK_ON', 75) == 75
    assert policy['regimes']['PANIC']['status'] == 'BLOCKED'


def test_validated_policy_updates_automatically_and_reproducibly():
    rows = observations()
    before = copy.deepcopy(rows)
    policy = learn_entry_policy(rows, '2026-01-01')
    regime = policy['regimes']['RISK_ON']
    assert policy['status'] == 'ACTIVE'
    assert regime['effectiveThreshold'] == 80
    assert regime['upliftLowerBound'] > 0 and regime['netExcessLowerBound'] > 0
    assert regime['validationCoverage'] == .5
    assert regime['trainingDates'] == 70  # Labels crossing validation start were purged.
    assert policy == learn_entry_policy(rows, '2026-01-01')
    assert rows == before  # Immutable predictions remain a comparison control.


def test_training_success_cannot_override_failed_future_validation():
    policy = learn_entry_policy(observations(True), '2026-01-01')
    assert policy['regimes']['RISK_ON']['status'] == 'VALIDATION_FAILED'
    assert entry_threshold(policy, 'RISK_ON', 75) == 75


def test_future_and_duplicate_outcomes_cannot_create_evidence():
    rows = observations()
    policy = learn_entry_policy(rows + rows, '2025-01-10')
    assert policy['matured20D'] == 0
    assert learn_entry_policy(rows + rows, '2026-01-01')['matured20D'] == len(rows)


def test_training_labels_must_finish_before_validation_starts():
    rows = observations()
    for row in rows:
        row['outcomes']['20D']['maturityDate'] = '2025-12-01'
    policy = learn_entry_policy(rows, '2026-01-01')
    assert policy['regimes']['RISK_ON']['status'] == 'WAITING_FOR_EVIDENCE'
    assert policy['regimes']['RISK_ON']['trainingDates'] == 0


@pytest.mark.parametrize('regime,baseline', [('RISK_ON', 75), ('NEUTRAL', 80), ('DEFENSIVE', 88), ('PANIC', 101)])
def test_policy_cannot_relax_risk_or_exceed_bounded_threshold(regime, baseline):
    policy = {'regimes': {regime: {'status': 'ACTIVE', 'effectiveThreshold': 0}}}
    assert entry_threshold(policy, regime, baseline) == baseline
    policy['regimes'][regime]['effectiveThreshold'] = 1000
    threshold = entry_threshold(policy, regime, baseline)
    assert baseline <= threshold <= max(baseline, min(baseline + 10, 100))
    policy['regimes'][regime]['effectiveThreshold'] = math.nan
    assert entry_threshold(policy, regime, baseline) == baseline


def test_friction_can_prevent_a_spurious_update():
    policy = learn_entry_policy(observations(), '2026-01-01', round_trip_cost=.1)
    assert policy['regimes']['RISK_ON']['status'] != 'ACTIVE'
