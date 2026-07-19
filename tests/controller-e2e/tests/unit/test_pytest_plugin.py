from controller_e2e.errors import ContractAmbiguity, EnvironmentBlocker
from controller_e2e.pytest_plugin import _failure_classification


def test_environment_blocker_uses_acceptance_classification_name():
    assert (
        _failure_classification(EnvironmentBlocker("synthetic setup failure"))
        == "BLOCKED_BY_ENVIRONMENT"
    )


def test_contract_ambiguity_remains_distinct_from_platform_failure():
    assert (
        _failure_classification(ContractAmbiguity("synthetic ambiguity"))
        == "BLOCKED_BY_CONTRACT"
    )
