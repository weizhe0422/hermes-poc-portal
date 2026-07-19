from controller_e2e.polling import BoundedPoller
from controller_e2e.errors import ExpectedResultMismatch

import pytest


def test_adaptive_polling_observes_until_expected_without_real_sleep():
    now = [0.0]
    values = iter(["STARTING", "STARTING", "HEALTHY"])
    waits = []

    def wait(seconds):
        waits.append(seconds)
        now[0] += seconds

    poller = BoundedPoller(
        initial_interval_seconds=0.1,
        max_interval_seconds=1.0,
        backoff_multiplier=2.0,
        clock=lambda: now[0],
        wait=wait,
    )
    result = poller.until(
        fetch=lambda: next(values),
        accepted=lambda value: value == "HEALTHY",
        timeout_seconds=2.0,
        description="fixture health",
    )

    assert result.value == "HEALTHY"
    assert result.attempts == 3
    assert waits == [0.1, 0.2]


def test_polling_does_not_fetch_again_at_the_deadline():
    now = [0.0]
    fetches = []

    def fetch():
        fetches.append(now[0])
        return "STARTING"

    poller = BoundedPoller(
        initial_interval_seconds=1.0,
        max_interval_seconds=1.0,
        backoff_multiplier=1.0,
        clock=lambda: now[0],
        wait=lambda seconds: now.__setitem__(0, now[0] + seconds),
    )

    with pytest.raises(ExpectedResultMismatch, match="within 1.000s"):
        poller.until(
            fetch=fetch,
            accepted=lambda value: value == "HEALTHY",
            timeout_seconds=1.0,
            description="fixture health",
        )

    assert fetches == [0.0]


def test_polling_rejects_a_success_observed_after_the_deadline():
    now = [0.0]

    def slow_success():
        now[0] = 1.1
        return "HEALTHY"

    poller = BoundedPoller(
        initial_interval_seconds=0.1,
        max_interval_seconds=1.0,
        backoff_multiplier=2.0,
        clock=lambda: now[0],
        wait=lambda _seconds: None,
    )

    with pytest.raises(ExpectedResultMismatch, match="observation exceeded"):
        poller.until(
            fetch=slow_success,
            accepted=lambda value: value == "HEALTHY",
            timeout_seconds=1.0,
            description="fixture health",
        )


def test_bounded_poller_supports_runtime_type_parameters() -> None:
    assert BoundedPoller[int] is not None
