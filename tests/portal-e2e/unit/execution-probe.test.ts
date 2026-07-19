import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';

import { evaluateFailureProbe } from '../support/execution-probe';
import { FrozenInfrastructureCaseCatalog } from '../support/infrastructure-cases';

const specificationRoot = path.resolve(
  __dirname,
  '../../../hermes-poc-specification-v0.1',
);

async function writeSyntheticProbeArtifacts(
  artifactDirectory: string,
  runId: string,
  caseId: string,
): Promise<void> {
  const traceDirectory = path.join(artifactDirectory, 'test-output/probe');
  const attemptDirectory = path.join(artifactDirectory, 'attempts');
  await mkdir(traceDirectory, { recursive: true });
  await mkdir(attemptDirectory, { recursive: true });
  await writeFile(
    path.join(artifactDirectory, 'junit.xml'),
    `<testsuite failures="1"><testcase name="${caseId} ${runId}"><failure /></testcase></testsuite>`,
    'utf8',
  );
  await writeFile(
    path.join(artifactDirectory, 'playwright.log'),
    `run_id=${runId} case_id=${caseId} attempt=1\n`,
    'utf8',
  );
  await writeFile(path.join(traceDirectory, 'trace.zip'), 'synthetic-trace', 'utf8');
  await writeFile(
    path.join(attemptDirectory, 'attempt-1.json'),
    JSON.stringify({ attempt: 1, case_id: caseId, run_id: runId }),
    'utf8',
  );
}

test('failure probe evaluator retains nonzero failure and all required evidence', async () => {
  const resultsDir = await mkdtemp(path.join(os.tmpdir(), 'hermes-probe-'));
  const runId = 'unit-probe';
  const caseId = 'EXECUTION-002';
  const artifactDirectory = path.join(
    resultsDir,
    'execution-probe',
    runId,
    caseId,
  );
  await writeSyntheticProbeArtifacts(artifactDirectory, runId, caseId);
  const catalog = await FrozenInfrastructureCaseCatalog.load(specificationRoot);
  const requiredArtifacts = catalog
    .get('EXECUTION-002')
    .expectedStringArray('artifacts_generated');

  const result = await evaluateFailureProbe({
    artifactDirectory,
    caseId,
    exitCode: 1,
    requiredArtifacts,
    runId,
  });

  assert.deepEqual(result.artifacts_generated, ['junit', 'trace', 'log']);
  assert.equal(result.artifact_contains_run_id, true);
  assert.equal(result.artifact_contains_case_id, true);
  assert.equal(result.exit_code_is_zero, false);
  assert.equal(result.failure_converted_to_success, false);
  assert.equal(result.failure_retained, true);
  assert.equal(result.auto_retried_to_pass, false);
  assert.equal(result.attempt_count, 1);
});

test('failure probe evaluator exposes a retry-to-pass instead of masking it', async () => {
  const resultsDir = await mkdtemp(path.join(os.tmpdir(), 'hermes-probe-'));
  const runId = 'unit-retry';
  const caseId = 'EXECUTION-003';
  const artifactDirectory = path.join(
    resultsDir,
    'execution-probe',
    runId,
    caseId,
  );
  await writeSyntheticProbeArtifacts(artifactDirectory, runId, caseId);
  await writeFile(
    path.join(artifactDirectory, 'attempts/attempt-2.json'),
    JSON.stringify({ attempt: 2, case_id: caseId, run_id: runId }),
    'utf8',
  );

  const result = await evaluateFailureProbe({
    artifactDirectory,
    caseId,
    exitCode: 0,
    requiredArtifacts: ['junit', 'trace', 'log'],
    runId,
  });

  assert.equal(result.attempt_count, 2);
  assert.equal(result.failure_retained, false);
  assert.equal(result.auto_retried_to_pass, true);
  assert.equal(result.failure_converted_to_success, true);
});

test('failure probe evaluator does not mistake a missing exit code for retained failure', async () => {
  const resultsDir = await mkdtemp(path.join(os.tmpdir(), 'hermes-probe-'));
  const runId = 'unit-signal';
  const caseId = 'EXECUTION-001';
  const artifactDirectory = path.join(
    resultsDir,
    'execution-probe',
    runId,
    caseId,
  );
  await writeSyntheticProbeArtifacts(artifactDirectory, runId, caseId);

  const result = await evaluateFailureProbe({
    artifactDirectory,
    caseId,
    exitCode: null,
    runId,
  });

  assert.equal(result.exit_code_is_zero, false);
  assert.equal(result.failure_retained, false);
});
