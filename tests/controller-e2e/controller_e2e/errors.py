"""Stable failure categories used by pytest, JUnit, and summary artifacts."""


class ControllerE2EError(Exception):
    """Base class for intentional runner failures."""


class ContractViolation(ControllerE2EError, AssertionError):
    """The service response does not satisfy the published contract."""


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
