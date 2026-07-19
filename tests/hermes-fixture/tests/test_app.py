from __future__ import annotations

from fastapi.testclient import TestClient

from hermes_fixture.app import create_app
from hermes_fixture.config import FixtureMode, Settings


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def fixture_settings(tmp_path, mode: FixtureMode) -> Settings:
    return Settings.from_env(
        {
            "FIXTURE_MODE": mode.value,
            "FIXTURE_INSTANCE_ID": "hermes-fixture-test",
            "FIXTURE_RUN_ID": "unit-test-run",
            "FIXTURE_MARKER_PATH": str(tmp_path / "state" / "runtime-014.marker"),
            "FIXTURE_START_DELAY_SECONDS": "10",
        }
    )


def test_healthy_mode_exposes_health_and_deterministic_openai_probes(tmp_path):
    settings = fixture_settings(tmp_path, FixtureMode.HEALTHY)

    with TestClient(create_app(settings, event_sink=lambda _: None)) as client:
        first_health = client.get("/health")
        second_health = client.get("/health")
        models = client.get("/v1/models")
        completion = client.post(
            "/v1/chat/completions",
            json={
                "model": settings.model_name,
                "messages": [{"role": "user", "content": "probe"}],
            },
        )

    assert first_health.status_code == 200
    assert first_health.json() == second_health.json()
    assert first_health.json()["test_only"] is True
    assert first_health.json()["classification"] == "SYNTHETIC_TEST_ONLY"
    assert first_health.json()["hermes_status"] == "AVAILABLE"
    assert first_health.json()["llm_status"] == "AVAILABLE"
    assert models.json()["data"][0]["id"] == settings.model_name
    assert completion.status_code == 200
    assert completion.json()["id"] == "chatcmpl-synthetic-deterministic"
    assert completion.json()["created"] == 0


def test_slow_start_is_unavailable_until_exact_delay_elapses(tmp_path):
    settings = fixture_settings(tmp_path, FixtureMode.SLOW_START)
    clock = FakeClock()

    with TestClient(
        create_app(settings, clock=clock, event_sink=lambda _: None)
    ) as client:
        pending = client.get("/health")
        pending_models = client.get("/v1/models")
        clock.advance(9.999)
        still_pending = client.get("/health")
        clock.advance(0.001)
        ready = client.get("/health")

    assert pending.status_code == 503
    assert pending.json()["reason"] == "SLOW_START_PENDING"
    assert pending_models.status_code == 503
    assert still_pending.status_code == 503
    assert ready.status_code == 200
    assert ready.json()["reason"] == "SLOW_START_COMPLETE"


def test_unhealthy_keeps_process_and_llm_probe_available(tmp_path):
    settings = fixture_settings(tmp_path, FixtureMode.UNHEALTHY)

    with TestClient(create_app(settings, event_sink=lambda _: None)) as client:
        health = client.get("/health")
        llm_health = client.get("/llm/health")
        models = client.get("/v1/models")

    assert health.status_code == 503
    assert health.json()["hermes_status"] == "UNAVAILABLE"
    assert health.json()["llm_status"] == "AVAILABLE"
    assert llm_health.status_code == 200
    assert models.status_code == 200


def test_secret_log_emits_exact_synthetic_secret_but_never_returns_it(tmp_path):
    settings = fixture_settings(tmp_path, FixtureMode.SECRET_LOG)
    events = []

    with TestClient(create_app(settings, event_sink=events.append)) as client:
        health_body = client.get("/health").text
        metadata_body = client.get("/metadata").text

    secret_events = [event for event in events if event["event"] == "synthetic_secret_log"]
    assert len(secret_events) == 1
    assert secret_events[0]["secret"] == "TEST_SECRET_123456"
    assert "TEST_SECRET_123456" not in health_body
    assert "TEST_SECRET_123456" not in metadata_body


def test_persistent_mode_health_is_gated_by_exact_marker_across_app_restart(tmp_path):
    settings = fixture_settings(tmp_path, FixtureMode.PERSISTENT)

    with TestClient(create_app(settings, event_sink=lambda _: None)) as client:
        missing = client.get("/health")
        seeded = client.put("/test-only/persistent-marker")
        ready = client.get("/health")

    assert missing.status_code == 503
    assert missing.json()["reason"] == "PERSISTENT_MARKER_MISSING"
    assert seeded.status_code == 200
    assert seeded.json()["persistent_marker"]["valid"] is True
    assert ready.status_code == 200
    assert ready.json()["persistent_marker"]["valid"] is True

    # A new app models a process restart while retaining the mounted state path.
    with TestClient(create_app(settings, event_sink=lambda _: None)) as restarted:
        after_restart = restarted.get("/health")
        marker_probe = restarted.get("/test-only/persistent-marker")

    assert after_restart.status_code == 200
    assert after_restart.json()["reason"] == "PERSISTENT_MARKER_VALID"
    assert marker_probe.status_code == 200
    assert marker_probe.json()["persistent_marker"]["sha256"]


def test_persistent_mode_rejects_corrupted_marker(tmp_path):
    settings = fixture_settings(tmp_path, FixtureMode.PERSISTENT)
    settings.marker_path.parent.mkdir(parents=True)
    settings.marker_path.write_text("wrong", encoding="utf-8")

    with TestClient(create_app(settings, event_sink=lambda _: None)) as client:
        health = client.get("/health")
        marker_probe = client.get("/test-only/persistent-marker")

    assert health.status_code == 503
    assert health.json()["reason"] == "PERSISTENT_MARKER_INVALID"
    assert marker_probe.status_code == 409
    assert marker_probe.json()["persistent_marker"]["present"] is True
    assert marker_probe.json()["persistent_marker"]["valid"] is False


def test_openai_probe_rejects_streaming_and_unknown_models(tmp_path):
    settings = fixture_settings(tmp_path, FixtureMode.HEALTHY)
    base_request = {
        "model": settings.model_name,
        "messages": [{"role": "user", "content": "probe"}],
    }

    with TestClient(create_app(settings, event_sink=lambda _: None)) as client:
        streaming = client.post(
            "/v1/chat/completions", json={**base_request, "stream": True}
        )
        unknown = client.post(
            "/v1/chat/completions", json={**base_request, "model": "other"}
        )

    assert streaming.status_code == 400
    assert streaming.json()["error"]["code"] == "FIXTURE_STREAMING_UNSUPPORTED"
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "FIXTURE_MODEL_NOT_FOUND"


def test_nonpersistent_modes_cannot_mutate_marker(tmp_path):
    settings = fixture_settings(tmp_path, FixtureMode.HEALTHY)

    with TestClient(create_app(settings, event_sink=lambda _: None)) as client:
        response = client.put("/test-only/persistent-marker")

    assert response.status_code == 409
    assert response.json()["error_code"] == "FIXTURE_MODE_NOT_PERSISTENT"
    assert not settings.marker_path.exists()
