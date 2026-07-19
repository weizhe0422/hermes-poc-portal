"""Stable failure categories used by pytest, JUnit, and summary artifacts."""


class ControllerE2EError(Exception):
    """Base class for intentional runner failures."""


class ContractViolation(ControllerE2EError, AssertionError):
    """The service response does not satisfy the published contract."""


class ContractAmbiguity(ContractViolation):
    """Frozen inputs do not publish enough mapping to determine a verdict."""


class ExpectedResultMismatch(ControllerE2EError, AssertionError):
    """A valid response differs from the Bundle test-case expectation."""


class TransportFailure(ControllerE2EError):
    """The Controller could not be reached or an HTTP exchange failed."""


class EnvironmentBlocker(ControllerE2EError):
    """The isolated test environment does not meet a declared precondition."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ExpectedResultMismatch(message)


def require_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise ExpectedResultMismatch(
            f"{label}: expected {expected!r}, received {actual!r}"
        )


def require_forbidden_values_absent(
    serialized: str, forbidden_values: tuple[str, ...], label: str
) -> None:
    """Fail without copying a forbidden value into JUnit or log artifacts."""

    for index, forbidden in enumerate(forbidden_values):
        if forbidden in serialized:
            raise ExpectedResultMismatch(
                f"{label}: response contains forbidden value at index {index}"
            )
