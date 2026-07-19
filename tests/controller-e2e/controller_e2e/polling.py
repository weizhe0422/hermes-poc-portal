"""Deadline-bounded adaptive state observation."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event
import time
from typing import Callable, Generic, TypeVar

from .errors import ExpectedResultMismatch


T = TypeVar("T")


@dataclass(frozen=True)
class PollResult(Generic[T]):
    value: T
    attempts: int
    elapsed_seconds: float


class OrderedStatePath:
    """Reject non-contract states and backwards transitions in an async path."""

    def __init__(self, states: tuple[str, ...]) -> None:
        if not states or len(set(states)) != len(states):
            raise ValueError("ordered state path must contain unique states")
        self._rank = {state: index for index, state in enumerate(states)}
        self._last_rank = -1
        self._last_state: str | None = None

    def observe(self, state: object, description: str) -> None:
        if not isinstance(state, str) or state not in self._rank:
            raise ExpectedResultMismatch(
                f"{description} observed unreachable state={state!r}"
            )
        rank = self._rank[state]
        if rank < self._last_rank:
            raise ExpectedResultMismatch(
                f"{description} regressed from {self._last_state!r} to {state!r}"
            )
        self._last_rank = rank
        self._last_state = state


class BoundedPoller(Generic[T]):
    def __init__(
        self,
        initial_interval_seconds: float,
        max_interval_seconds: float,
        backoff_multiplier: float,
        clock: Callable[[], float] = time.monotonic,
        wait: Callable[[float], None] | None = None,
    ) -> None:
        self._initial_interval = initial_interval_seconds
        self._max_interval = max_interval_seconds
        self._multiplier = backoff_multiplier
        self._clock = clock
        self._wait = wait or (lambda seconds: Event().wait(seconds))

    def until(
        self,
        fetch: Callable[[], T],
        accepted: Callable[[T], bool],
        timeout_seconds: float,
        description: str,
        terminal_failure: Callable[[T], str | None] | None = None,
    ) -> PollResult[T]:
        started = self._clock()
        deadline = started + timeout_seconds
        interval = self._initial_interval
        attempts = 0
        last_value: T | None = None

        while True:
            # Do not start another observation after the configured deadline.
            # The first observation is always allowed, including for a zero-latency
            # readiness result at the beginning of the window.
            if attempts and self._clock() >= deadline:
                raise ExpectedResultMismatch(
                    f"{description} did not complete within {timeout_seconds:.3f}s "
                    f"after {attempts} observations; last value={last_value!r}"
                )
            attempts += 1
            last_value = fetch()
            observed_at = self._clock()
            if observed_at > deadline:
                raise ExpectedResultMismatch(
                    f"{description} observation exceeded the "
                    f"{timeout_seconds:.3f}s deadline after {attempts} attempts; "
                    f"last value={last_value!r}"
                )
            if accepted(last_value):
                return PollResult(
                    value=last_value,
                    attempts=attempts,
                    elapsed_seconds=observed_at - started,
                )
            if terminal_failure:
                reason = terminal_failure(last_value)
                if reason:
                    raise ExpectedResultMismatch(
                        f"{description} reached a terminal failure after {attempts} "
                        f"observations: {reason}"
                    )

            remaining = deadline - observed_at
            if remaining <= 0:
                raise ExpectedResultMismatch(
                    f"{description} did not complete within {timeout_seconds:.3f}s "
                    f"after {attempts} observations; last value={last_value!r}"
                )
            self._wait(min(interval, remaining))
            interval = min(self._max_interval, interval * self._multiplier)
