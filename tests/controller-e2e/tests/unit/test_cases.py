from controller_e2e.cases import RuntimeCaseCatalog


def test_catalog_loads_only_existing_approved_cases(spec_root):
    catalog = RuntimeCaseCatalog(spec_root)

    assert catalog.get("RUNTIME-001").requirement_ids == ("RT-01", "RT-02")
    assert catalog.get("RUNTIME-003").expected["final_state"] == "HEALTHY"
    assert catalog.get("RUNTIME-006").critical is True
    assert catalog.get("RUNTIME-014").expected["persistent_marker_present"] is True
    assert "RUNTIME-004" not in catalog.case_ids
    assert "RUNTIME-005" not in catalog.case_ids
    assert "RUNTIME-007" not in catalog.case_ids
