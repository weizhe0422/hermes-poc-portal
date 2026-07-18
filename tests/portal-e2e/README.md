# Hermes PoC Portal E2E — T-M0 Runner Skeleton

This directory contains only the external-container runner foundation for T-M0.
It does not implement T-M3 Portal Runtime, Knowledge, Deployment, History,
Feedback, Artifact, Live Hermes, or Golden Case flows.

## Version and container boundary

- `@playwright/test` is pinned to `1.61.0`.
- The Docker base is pinned to the matching
  `mcr.microsoft.com/playwright:v1.61.0-noble` patch tag. A build argument may
  point `PLAYWRIGHT_IMAGE` at the approved internal mirror, but the mirrored
  image must contain the same Playwright patch release.
- `npm ci` uses `package-lock.json`; browser downloads are disabled because the
  browser binaries come from the matching image.
- Tests run as the image's non-root `pwuser` account.
- Runner source and dependencies remain root-owned image content; only the
  artifact path is writable by `pwuser`.
- The runner must join only `e2e-network`. It must not receive a Docker socket,
  writable source mount, Controller network, or Agent network.

## Configuration

| Variable | Required | Purpose |
|---|---:|---|
| `PORTAL_BASE_URL` | yes | Absolute HTTP(S) URL visible to the runner |
| `RESULTS_DIR` | yes | Writable artifact-volume directory; the image defaults to `/test-results/portal-e2e` |
| `CONTROLLER_BASE_URL` | for network checks | Contract-supplied internal Controller URL that must be unreachable |
| `HERMES_BASE_URL` | for network checks | Contract-supplied internal Hermes URL that must be unreachable |
| `NETWORK_PROBE_TIMEOUT_MS` | no | Positive integer; default `3000` |
| `PORTAL_READY_TIMEOUT_MS` | no | Bounded public-boundary startup wait; default `60000` |
| `PORTAL_E2E_TIMEOUT_MS` | no | Positive integer; default `75000` |

`PORTAL_BASE_URL` is intentionally not assigned a Dockerfile default. The
orchestrator must select the Portal service through the external E2E network.

Example image invocation after the orchestrator has created the network and
artifact volume:

```sh
docker run --rm \
  --network e2e-network \
  -e PORTAL_BASE_URL=http://portal:8080 \
  -e CONTROLLER_BASE_URL=http://controller:8090 \
  -e HERMES_BASE_URL=http://hermes:8000 \
  -e RESULTS_DIR=/test-results/portal-e2e \
  -v test-results:/test-results \
  hermes-poc-portal-e2e:0.1.0
```

The network names and URLs above illustrate the frozen Environment Contract;
the actual external compose runner owns their values.

## Evidence

Under `RESULTS_DIR`, the configuration emits:

```text
junit/portal-e2e.xml
metadata.json
playwright-report/
test-output/                         # failure attachment 時產生
screenshots/                         # failure attachment 時產生
traces/                              # failure attachment 時產生
videos/                              # failure attachment 時產生
preflight/artifact-write-probe.json
compose.log                           # orchestration 產生
cleanup.json                          # orchestration 產生
runner-status.json                    # orchestration 產生
```

Trace, screenshot, and video capture is retained on failure. Playwright keeps
the original attachment in `test-output/`; the custom reporter copies supported
attachments into the stable evidence directories.

## Placeholder metadata convention

The Traceability Matrix says that `SECURITY-*`, `EXECUTION-*`, and
`ARTIFACT-*` are planned Test IDs and must not be reported as approved tests
merely because the YAML Golden Cases do not yet exist. Every test in this
skeleton therefore carries these annotations:

| Annotation | T-M0 value |
|---|---|
| `hermes.case_id` | Matrix placeholder such as `SECURITY-002` |
| `hermes.requirement_id` | One entry per mapped Requirement ID |
| `hermes.case_source` | `traceability-matrix-placeholder` |
| `hermes.coverage_claim` | `none` |
| `hermes.acceptance_status` | `not-evaluated` |
| `hermes.golden_status` | `not-applicable` |
| `hermes.evidence_kind` | `preflight`, `artifact`, or `network-isolation` |

The JUnit reporter embeds the annotations as testcase properties. The custom
reporter writes the same convention to `metadata.json`. A passing execution
means only that the runner-level check passed in that environment; it does not
claim Contract coverage, Golden Case acceptance, or PoC acceptance.

`EXECUTION-004` is deliberately reported as `fixme` until the external
orchestrator implements pre/post Git-tree evidence. The test container itself
must not be given Git access merely to make that placeholder pass.
