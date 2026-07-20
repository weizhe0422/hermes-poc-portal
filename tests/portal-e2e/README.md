# Hermes PoC Portal E2E — Frozen M0/M1 Infrastructure Runner

This external Playwright container evaluates the eight Portal-runner cases in
the Frozen M0/M1 Acceptance Contract v0.2.1. It does not implement the T-M3
Portal Runtime, Knowledge, Deployment, History, Feedback, Live Hermes, or
Golden Case flows.

## Expected source and metadata

The runner reads `/spec/test-cases/infrastructure/cases.yaml` at collection
time and requires `suite_id: infrastructure-v0.2`. Requirement IDs,
`critical`, and every asserted Expected field come from that file. The suite
does not copy Expected values into test code or relax them to match a platform
candidate.

Every JUnit row carries:

- `critical=true`
- `hermes.case_source=frozen-infrastructure-case`
- `hermes.coverage_claim=case-level`
- `hermes.acceptance_status=case-evaluated`
- `hermes.golden_status=frozen-v0.2.1`
- the exact Requirement IDs loaded from the Frozen YAML

The eight rows are `SECURITY-001..003`, `EXECUTION-001..004`, and
`ARTIFACT-001`.

## Split evidence boundary

The Runner writes actual observations to
`runner-observations.json`. Each case record has `observed_fields`,
`unobserved_fields`, and `runner_subset_status`; an unobserved field is never
defaulted to `true`.

Runner-observable coverage:

- `SECURITY-002`: Portal, Controller, and Hermes connectivity.
- `SECURITY-003`: Docker endpoint/socket, Knowledge/Skill/formal mounts,
  writable source, and Git metadata isolation.
- `EXECUTION-001..003`: real isolated Playwright failure processes, nonzero
  exit, JUnit, trace, log, Run ID, Case ID, one attempt, and no retry masking.
- `EXECUTION-004`: no Runner Git metadata and no writable source.
- `ARTIFACT-001`: independent result volume plus in-run write/read probe.

The external orchestrator must merge Host/container inspection and post-exit
evidence for `SECURITY-001`, `SECURITY-002`, `EXECUTION-004`, and
`ARTIFACT-001` before issuing the final Acceptance verdict.

## Container boundary

- `@playwright/test` and the base image are pinned to `1.61.0`.
- Tests run as the image's non-root `pwuser`.
- Runner source and dependencies are root-owned image content.
- The only writable mount is the independent `/test-results` volume.
- `/spec` is read-only.
- No Docker endpoint, Git metadata, production/formal volume, Controller
  network, or Agent network is supplied.

Required environment:

| Variable | Purpose |
|---|---|
| `PORTAL_BASE_URL` | Portal public boundary visible on `e2e-network` |
| `CONTROLLER_BASE_URL` | Controller target that must be unreachable |
| `HERMES_BASE_URL` | Hermes target that must be unreachable |
| `RESULTS_DIR` | Per-run directory below the independent result volume |
| `RUN_ID` | Lowercase artifact-safe run identity |
| `SPEC_ROOT` | Read-only specification root, normally `/spec` |
| `CONTRACT_TAG` | Must identify `contract-m0-m1-v0.2.1` |
| `CONTRACT_COMMIT` | Full lowercase commit injected by orchestration |
| `CONTRACT_VERSION` | Must equal `0.2.1` |

Optional bounded timeout variables remain `NETWORK_PROBE_TIMEOUT_MS`,
`PORTAL_READY_TIMEOUT_MS`, and `PORTAL_E2E_TIMEOUT_MS`.

## Verification

From this directory:

```sh
npm ci --ignore-scripts --no-audit --no-fund
npm run test:unit
npm run typecheck
```

The supported end-to-end entry point remains:

```sh
# First export the six repository-level provenance variables documented in README.md.
scripts/run-portal-e2e
```

The entrypoint calls `scripts/verify-acceptance-source` before Docker, build, or
artifact creation. It accepts detached HEAD or a branch only when HEAD exactly
equals the required Integration commit, the observed remote ref matches, all
candidate ancestry/ownership checks pass, and the full working tree is clean.
Branch is recorded rather than used as a gate. Runtime image identity is stored
as reference plus immutable image ID; no OCI revision label is required.

## Artifacts

Under `RESULTS_DIR` the Runner emits:

```text
junit/portal-e2e.xml
metadata.json
summary.json
runner-observations.json
evidence/<CASE-ID>.json
playwright-report/
preflight/artifact-write-probe.json
execution-probe/<run-id>/<case-id>/
├── junit.xml
├── playwright.log
├── probe-result.json
├── attempts/attempt-1.json
└── test-output/**/trace.zip
```

The outer orchestrator owns `manifest.yaml`, Host/container inspection,
post-exit readability, cleanup, source-tree cleanliness, final JUnit evidence
merge, and repository-wide secret scan.
