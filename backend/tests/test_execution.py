from app.execution import (
    policy_for_regime,
    simulation_config,
)


def test_risk_on_policy():
    policy = (
        policy_for_regime(
            "RISK_ON"
        )
    )

    assert (
        policy.entries_allowed
        is True
    )

    assert (
        policy.minimum_score
        == 75
    )

    assert (
        policy.exposure_multiplier
        == 1.0
    )


def test_defensive_reduces_exposure():
    policy = (
        policy_for_regime(
            "DEFENSIVE"
        )
    )

    assert (
        policy.entries_allowed
        is True
    )

    assert (
        policy.minimum_score
        == 88
    )

    assert (
        policy.exposure_multiplier
        == 0.40
    )


def test_panic_blocks_entry():
    policy = (
        policy_for_regime(
            "PANIC"
        )
    )

    assert (
        policy.entries_allowed
        is False
    )

    assert (
        policy.exposure_multiplier
        == 0
    )

    assert (
        policy.minimum_score
        > 100
    )


def test_simulation_costs_are_explicit():
    config = simulation_config()

    assert (
        config[
            "buySlippageBps"
        ]
        >= 0
    )

    assert (
        config[
            "sellSlippageBps"
        ]
        >= 0
    )

    assert (
        config[
            "feeBpsPerSide"
        ]
        >= 0
    )


def test_batch_entry_cap_is_conservative():
    config = simulation_config()

    assert (
        config[
            "batchEntryCap"
        ]
        >= 1
    )

    assert (
        config[
            "batchEntryCap"
        ]
        <= 6
    )
