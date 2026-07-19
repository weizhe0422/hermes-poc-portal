import pytest

from controller_e2e.errors import (
    ExpectedResultMismatch,
    require_forbidden_values_absent,
)


def test_forbidden_value_failure_does_not_repeat_secret_in_artifacts():
    secret = "TEST_SECRET_123456"

    with pytest.raises(ExpectedResultMismatch) as raised:
        require_forbidden_values_absent(
            f'{{"logs":["leaked {secret}"]}}',
            (secret,),
            "RUNTIME-013 response",
        )

    assert secret not in str(raised.value)
    assert str(raised.value).endswith("forbidden value at index 0")
