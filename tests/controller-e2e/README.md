# Hermes Controller E2E — Frozen M0/M1 Runtime Runner

This is an external-container, HTTP-only black-box runner for the Frozen
M0/M1 Acceptance Contract v0.2.0. It reads the published Controller OpenAPI,
runtime state machine, schemas, error catalog, and Runtime YAML cases from the
read-only `/spec` mount. It never imports platform code or changes Expected
Results to match a candidate.

## Executed cases

The Controller child suite has 13 rows: one isolated-environment case plus all
12 Frozen Runtime cases.

| Case | Requirements | Main assertion/evidence |
|---|---|---|
| `CONTROLLER-ENV-001` | E2E-03, E2E-04 | Runner/container/Engine isolation and run-scoped cleanup |
| `RUNTIME-001` | RT-01, RT-02 | stopped managed-instance status |
| `RUNTIME-003` | RT-03, RT-09 | Start accepted body, state path, health, Engine start |
| `RUNTIME-004` | RT-04 | Stop accepted body, STOPPED, container/volume preservation |
| `RUNTIME-005` | RT-05 | Restart accepted body, HEALTHY, no removal/duplicate restart |
| `RUNTIME-006` | RT-06 | Start idempotent 200 and no duplicate container |
| `RUNTIME-007` | RT-06 | Stop idempotent 200 and no duplicate stop |
| `RUNTIME-008` | RT-07 | parallel lifecycle lock and one 409 conflict |
| `RUNTIME-009` | RT-08 | bounded start timeout; explicit Contract ambiguity gate |
| `RUNTIME-012` | RT-10, RT-11 | unmanaged Stop forbidden and fixture remains running |
| `RUNTIME-013` | RT-13, NF-03 | logs API redaction and forbidden synthetic secret scan |
| `RUNTIME-014` | RT-05 | Restart preserves run-scoped volume marker |
| `RUNTIME-017` | RT-06 | concurrent Restart returns same operation, no duplicate |

Every HTTP response is checked for a Contract-declared status and content type,
valid JSON, and the exact OpenAPI response schema, including external Draft
2020-12 references and RFC 3339 date-times. The runner then applies the YAML
Expected and state-machine assertions. OpenAPI-valid behavior can still fail as
`EXPECTED_RESULT_MISMATCH`.

Every JUnit row carries the exact Frozen Requirement IDs plus:

- `hermes.case_source=frozen-runtime-case` (environment row uses
  `frozen-infrastructure-case`)
- `hermes.coverage_claim=case-level`
- `hermes.acceptance_status=case-evaluated`
- `hermes.golden_status=frozen-v0.2.0`
- `retry_policy=NO_RETRY`

## Isolated environment and Engine evidence

The approved entrypoint provisions five synthetic fixtures in a dedicated
rootless Docker-in-Docker Engine. Controller-under-test alone is attached to
the Engine network. This Runner is attached only to `controller-e2e-network`,
calls `http://controller:8090`, has no Docker endpoint/socket, and cannot see or
control the Engine directly.

The external orchestrator runs one Runtime case per fresh Controller phase,
opens a case-specific Docker event window, and adds Engine-only evidence to the
JUnit after the Runner exits. Depending on the Case, this proves container ID,
running/stopped status, exact event counts, absence of duplicate action,
unmanaged-container preservation, volume identity/marker preservation, and
run-labelled cleanup. Evidence cannot replace an API/Expected assertion; both
gates must pass.

The five fixtures are:

- `hermes-fixture-001`: normal lifecycle; recreated as slow-start only for
  `RUNTIME-017`.
- `hermes-fixture-slow`: `RUNTIME-008/009` concurrency and timeout.
- `unmanaged-fixture-001`: deliberately lacks the managed label.
- `hermes-fixture-secret`: emits only `TEST_SECRET_123456`.
- `hermes-fixture-persistent`: health is gated by a marker in its named volume.

All Engine resources carry `poc.test-run=<run-id>`. Cleanup operates only on
that label and is independently checked before the outer Compose resources and
volumes are removed.

## Contract ambiguity and concurrency boundary

`RUNTIME-009.expected.error_code` has no published mapping to the only
AgentInstance candidate, `last_error_code`. The runner validates all published
observations but raises `BLOCKED_BY_CONTRACT` at that mapping boundary; it does
not invent an equivalence. A child/master result containing only this Contract
block is `CONTRACT_BLOCKED`, not PASS or a platform FAIL.

`RUNTIME-008` freezes one accepted request and one `OPERATION_CONFLICT`, but
does not state whether Start or Stop wins. The test uses a two-thread barrier,
runs once, and reports the scheduler outcome. It has no automatic retry.

## Build and run

Use the repository-level external orchestrator; invoking the image directly
does not create the required isolated Engine or Engine evidence.

```sh
# Build Controller Runner and synthetic Fixture images only
scripts/run-controller-e2e --build-only

# Execute Controller Environment + 12 Runtime cases
RUN_ID=m0m1-runtime-001 \
TEST_RESULTS_ROOT=/absolute/path/to/test-results \
PLATFORM_COMMIT=<40-character-platform-commit> \
CONTROLLER_IMAGE=<controller-candidate-image> \
scripts/run-controller-e2e
```

The entrypoint requires branch `test/t-m0-m1`, a clean source tree, Docker,
tag `contract-m0-m1-v0.2.0`, Contract version `0.2.0`, and a candidate image
whose OCI revision label equals `PLATFORM_COMMIT`. `--keep` is diagnostic only;
because it intentionally prevents cleanup acceptance, it cannot produce PASS.

Build context for the Runner image alone is `tests/controller-e2e`:

```sh
docker build --tag hermes-poc-controller-e2e:0.1.0 tests/controller-e2e
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `SPEC_ROOT` | `/spec` | read-only specification root |
| `RESULTS_DIR` | `/test-results` | writable result volume/path |
| `CONTROLLER_BASE_URL` | `http://controller-under-test:8090` | public Controller boundary |
| `CONTRACT_TAG` | `contract-m0-m1-v0.2.0` | Frozen baseline |
| `CONTRACT_VERSION` | `0.2.0` | Frozen Contract version |
| `CONTROLLER_READY_TIMEOUT_SECONDS` | `60` | readiness deadline |
| `E2E_HTTP_TIMEOUT_SECONDS` | `10` | per-request timeout |
| `HERMES_START_TIMEOUT_SECONDS` | phase-specific | Contract lifecycle timeout |
| `HERMES_STOP_TIMEOUT_SECONDS` | `15` in orchestration | Contract lifecycle timeout |
| `E2E_DEADLINE_GRACE_SECONDS` | `5` | observation grace |
| `POLL_INITIAL_INTERVAL_SECONDS` | `0.1` | bounded polling start |
| `POLL_MAX_INTERVAL_SECONDS` | `1.0` | polling cap |
| `POLL_BACKOFF_MULTIPLIER` | `1.5` | polling backoff |
| `TRACE_REDACT_VALUES` | `TEST_SECRET_123456` in orchestration | synthetic values removed from artifacts |

Do not use production secrets. Adaptive polling observes a single operation;
it never reruns a Critical case.

## Artifacts

For run `<id>`, the result root receives:

```text
<id>/
├── manifest.yaml
├── summary.json
├── summary.md
├── junit/*.xml
└── controller-e2e/
    ├── infrastructure/junit.xml
    ├── runtime-001/
    ├── runtime-003/
    ├── runtime-004/
    ├── runtime-005/
    ├── runtime-006/
    ├── runtime-007/
    ├── runtime-008/
    ├── runtime-009/
    ├── runtime-012/
    ├── runtime-013/
    ├── runtime-014/
    ├── runtime-017/                  # each: junit.xml, HTTP trace, JSON/MD summary
    ├── docker-snapshots/             # environment, events, evidence, persistence, cleanup
    ├── logs/
    ├── phase-status.jsonl
    └── runner-status.json
```

Failure classes are `CONTRACT_VIOLATION`, `EXPECTED_RESULT_MISMATCH`,
`TRANSPORT_FAILURE`, `BLOCKED_BY_ENVIRONMENT`, `ASSERTION_FAILURE`,
`TEST_IMPLEMENTATION_ERROR`, and the explicit `BLOCKED_BY_CONTRACT` result.

## Unit tests

```sh
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=tests/controller-e2e \
SPEC_ROOT=hermes-poc-specification-v0.1 \
python3 -m pytest tests/controller-e2e/tests/unit
```
