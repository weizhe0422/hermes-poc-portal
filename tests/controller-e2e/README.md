# Hermes Controller E2E — T-M0/T-M1

This directory is an external-container, HTTP-only black-box runner for the
published Controller API. It does not import platform code, mount a Docker
socket, create a runtime, or call the isolated Docker Engine. The specification
bundle is mounted read-only and is the source of test inputs and Expected
Results.

## Implemented Bundle runtime cases

| Case | Requirements | Assertion source |
|---|---|---|
| `RUNTIME-001` | RT-01, RT-02 | runtime case + AgentInstance schema |
| `RUNTIME-003` | RT-03, RT-09 | runtime case + OpenAPI + health state contract + isolated Engine start evidence |
| `RUNTIME-006` | RT-06 | runtime case + OpenAPI idempotent response |
| `RUNTIME-014` | RT-05, NF-05 | runtime case + Restart OpenAPI + marker-gated fixture assumption |

Each HTTP response is checked for a declared status, JSON content type, valid
JSON, and the exact OpenAPI response schema. External Draft 2020-12 schema
references and RFC 3339 date-time fields are validated. An OpenAPI-valid
response can still fail as `EXPECTED_RESULT_MISMATCH` when it differs from the
Bundle runtime case.

No tests are generated for missing Expected Results. These remain explicit in
both summaries:

- `RUNTIME-004` — basic Stop (`RT-04`)
- `RUNTIME-005` — basic Restart (`RT-05`); persistence case 014 is not a substitute
- `RUNTIME-007` — Stop/Restart idempotency (`RT-06`)

## Required isolated environment

The outer Compose/harness is responsible for provisioning fixtures inside a
dedicated Docker Engine before the Runner starts. The Runner joins only the
Controller E2E network and reaches only `controller-under-test:8090`. The
Controller-under-test, not this Runner, is the service connected to the isolated
Docker Engine.

Required preconditions follow the Bundle cases:

- `hermes-fixture-001` exists, is managed, and starts stopped.
- The `core-start` phase runs RUNTIME-003 and leaves that fixture HEALTHY. A
  freshly recreated Controller then runs only RUNTIME-006 in the
  `core-idempotency` phase. If RUNTIME-006 is run alone, its fixture must already
  be HEALTHY.
- `hermes-fixture-persistent` is restartable and has already written its marker
  to its persistent volume.
- The persistent fixture's health endpoint is marker-gated: after restart it can
  report Hermes/LLM AVAILABLE only if the marker is still present. Consequently,
  final `HEALTHY` is the authorized black-box evidence for
  `persistent_marker_present: true`; the Runner never inspects the volume.

For RUNTIME-003, the outer isolated-engine harness additionally proves that the
fixed runtime container is Running and that a start event occurred after the
bootstrap baseline. For RUNTIME-006, the public API proves that the
managed-instance registry is unchanged and contains the requested ID once. Its
independent Engine window also requires zero create, start, stop, and restart
events while retaining the exact final container set and labels. The Runner
cannot expose raw Docker identities; those checks stay in the outer isolated
Engine harness without granting this Runner Docker access.

For RUNTIME-014, the outer harness starts a fresh event window immediately
before the Restart request. JUnit is accepted only when the same persistent
container ID and named volume remain, the marker remains valid, and isolated
Docker events show a stop/restart plus a subsequent start. A `202` no-op cannot
pass this evidence gate.

## Build and run

Build with this directory as context:

```sh
docker build --tag hermes-controller-e2e:0.1.0 tests/controller-e2e
```

Illustrative invocation from the repository root (network and writable result
directory are created by the approved external harness):

```sh
docker run --rm \
  --network controller-e2e-network \
  --env CONTROLLER_BASE_URL=http://controller-under-test:8090 \
  --env SPEC_ROOT=/spec \
  --env RESULTS_DIR=/test-results \
  --mount type=bind,src="$PWD/hermes-poc-specification-v0.1",dst=/spec,readonly \
  --mount type=bind,src="$PWD/test-results",dst=/test-results \
  hermes-controller-e2e:0.1.0
```

The mounted result directory must be writable by UID/GID 10001. The container
exit code is pytest's exit code and is non-zero for any failure. The image has no
retry plugin, disables third-party pytest plugin auto-loading, and executes each
Critical case exactly once. Adaptive bounded polling observes an asynchronous
operation; it never reruns a case.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `SPEC_ROOT` | `/spec` | Read-only specification bundle root |
| `RESULTS_DIR` | `/test-results` | Writable artifact volume |
| `CONTROLLER_BASE_URL` | `http://controller-under-test:8090` | Controller-under-test only |
| `CONTROLLER_READY_TIMEOUT_SECONDS` | `60` | Bounded startup/readiness preflight |
| `E2E_HTTP_TIMEOUT_SECONDS` | `10` | Per-exchange timeout |
| `HERMES_START_TIMEOUT_SECONDS` | `120` | Contract lifecycle timeout |
| `HERMES_STOP_TIMEOUT_SECONDS` | `30` | Contract lifecycle timeout |
| `E2E_DEADLINE_GRACE_SECONDS` | `5` | Network/observation grace |
| `POLL_INITIAL_INTERVAL_SECONDS` | `0.1` | Initial poll interval |
| `POLL_MAX_INTERVAL_SECONDS` | `1.0` | Poll interval cap |
| `POLL_BACKOFF_MULTIPLIER` | `1.5` | Adaptive poll backoff |
| `TRACE_REDACT_VALUES` | empty | Comma-separated synthetic values to remove from artifacts |

Do not put production secrets in `TRACE_REDACT_VALUES`; T-M0/T-M1 must use only
synthetic fixtures. Sensitive header/body keys are redacted automatically.

## Artifacts

The result volume receives:

- `junit.xml` — JUnit with `test_case_id`, `requirement_ids`, `critical`,
  `milestone`, `retry_policy`, assumption, and failure-classification properties
- `http-trace.jsonl` — redacted request/response evidence and schema verdict
- `summary.json` — machine-readable counts, versions, classifications,
  assumptions, and coverage gaps
- `summary.md` — human-readable equivalent

Failure classes are `CONTRACT_VIOLATION`, `EXPECTED_RESULT_MISMATCH`,
`TRANSPORT_FAILURE`, `ENVIRONMENT_BLOCKER`, `ASSERTION_FAILURE`, and
`TEST_IMPLEMENTATION_ERROR`.

## Unit tests

With the pinned dependencies installed:

```sh
cd tests/controller-e2e
SPEC_ROOT=../../hermes-poc-specification-v0.1 pytest tests/unit
```
