from controller_e2e.cases import RuntimeCaseCatalog


def test_catalog_exposes_frozen_runtime_suite_identity(spec_root):
    catalog = RuntimeCaseCatalog(spec_root)

    assert catalog.suite_id == "runtime-v0.2"
    assert catalog.fixture_type == "SYNTHETIC"


def test_catalog_loads_every_frozen_runtime_case(spec_root):
    catalog = RuntimeCaseCatalog(spec_root)

    expected_case_ids = (
        "RUNTIME-001",
        "RUNTIME-003",
        "RUNTIME-004",
        "RUNTIME-005",
        "RUNTIME-006",
        "RUNTIME-007",
        "RUNTIME-008",
        "RUNTIME-009",
        "RUNTIME-012",
        "RUNTIME-013",
        "RUNTIME-014",
        "RUNTIME-017",
    )
    assert catalog.case_ids == expected_case_ids
    for case_id in expected_case_ids:
        runtime_case = catalog.get(case_id)
        assert runtime_case.case_id == case_id
        assert runtime_case.expected
        assert runtime_case.critical is True


def test_runtime_009_uses_frozen_last_error_code_without_an_alias(spec_root):
    runtime_case = RuntimeCaseCatalog(spec_root).get("RUNTIME-009")

    assert runtime_case.expected == {
        "initial_http_status": 202,
        "final_state": "ERROR",
        "last_error_code": "RUNTIME_START_TIMEOUT",
    }
    assert "error_code" not in runtime_case.expected
