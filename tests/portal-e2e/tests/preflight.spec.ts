import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

import { expect, test } from '@playwright/test';

import { writeCaseObservation } from '../support/case-observation';
import {
  configuredResultsDir,
  configuredSpecificationRoot,
  requiredContractProvenance,
  requiredRunId,
} from '../support/environment';
import { runFailureProbe } from '../support/execution-probe';
import {
  FrozenInfrastructureCaseCatalog,
  frozenInfrastructureTest,
} from '../support/infrastructure-cases';
import {
  inspectRunnerIsolation,
  type RunnerIsolationObservation,
} from '../support/runner-isolation';

const catalog = FrozenInfrastructureCaseCatalog.loadSync(
  configuredSpecificationRoot(),
);
const runnerSourceDirectory = path.resolve(__dirname, '..');
let isolationObservation: Promise<RunnerIsolationObservation> | undefined;

function validateFrozenRun(): { resultsDir: string; runId: string } {
  requiredContractProvenance(catalog.contractVersion);
  return { resultsDir: configuredResultsDir(), runId: requiredRunId() };
}

function runnerIsolation(): Promise<RunnerIsolationObservation> {
  isolationObservation ??= inspectRunnerIsolation({
    resultsDir: configuredResultsDir(),
    sourceDir: runnerSourceDirectory,
    specificationRoot: configuredSpecificationRoot(),
  });
  return isolationObservation;
}

test.describe('Frozen v0.2 external-container infrastructure acceptance', () => {
  test(
    'SECURITY-003 observes Runner mount, socket, source, and Git isolation',
    frozenInfrastructureTest(catalog, 'SECURITY-003'),
    async () => {
      const { resultsDir, runId } = validateFrozenRun();
      await writeCaseObservation({
        catalog,
        infrastructureCase: catalog.get('SECURITY-003'),
        observed: (await runnerIsolation()).security,
        resultsDir,
        runId,
      });
    },
  );

  test(
    'EXECUTION-001 preserves an injected failure as a nonzero exit',
    frozenInfrastructureTest(catalog, 'EXECUTION-001'),
    async () => {
      const { resultsDir, runId } = validateFrozenRun();
      const result = await runFailureProbe({
        caseId: 'EXECUTION-001',
        mode: 'deterministic',
        resultsDir,
        runId,
        sourceDirectory: runnerSourceDirectory,
      });
      expect(
        result.failure_retained,
        'the deterministic failure precondition must produce retained JUnit failure evidence',
      ).toBe(true);
      await writeCaseObservation({
        catalog,
        infrastructureCase: catalog.get('EXECUTION-001'),
        observed: {
          exit_code_is_zero: result.exit_code_is_zero,
          failure_converted_to_success: result.failure_converted_to_success,
        },
        resultsDir,
        runId,
      });
    },
  );

  test(
    'EXECUTION-002 retains JUnit, trace, and log with Run and Case identity',
    frozenInfrastructureTest(catalog, 'EXECUTION-002'),
    async () => {
      const { resultsDir, runId } = validateFrozenRun();
      const infrastructureCase = catalog.get('EXECUTION-002');
      const result = await runFailureProbe({
        caseId: 'EXECUTION-002',
        mode: 'deterministic',
        requiredArtifacts:
          infrastructureCase.expectedStringArray('artifacts_generated'),
        resultsDir,
        runId,
        sourceDirectory: runnerSourceDirectory,
      });
      expect(
        result.failure_retained,
        'the deterministic failure precondition must remain a failure',
      ).toBe(true);
      await writeCaseObservation({
        catalog,
        infrastructureCase,
        observed: {
          artifacts_generated: result.artifacts_generated,
          artifact_contains_run_id: result.artifact_contains_run_id,
          artifact_contains_case_id: result.artifact_contains_case_id,
        },
        resultsDir,
        runId,
      });
    },
  );

  test(
    'EXECUTION-003 runs a flaky-critical probe exactly once without retry masking',
    frozenInfrastructureTest(catalog, 'EXECUTION-003'),
    async () => {
      const { resultsDir, runId } = validateFrozenRun();
      const result = await runFailureProbe({
        caseId: 'EXECUTION-003',
        mode: 'flaky-first-attempt',
        resultsDir,
        runId,
        sourceDirectory: runnerSourceDirectory,
      });
      await writeCaseObservation({
        catalog,
        infrastructureCase: catalog.get('EXECUTION-003'),
        observed: {
          failure_retained: result.failure_retained,
          auto_retried_to_pass: result.auto_retried_to_pass,
          attempt_count: result.attempt_count,
        },
        resultsDir,
        runId,
      });
    },
  );

  test(
    'EXECUTION-004 observes the Runner-side Git and writable-source boundary',
    frozenInfrastructureTest(catalog, 'EXECUTION-004'),
    async () => {
      const { resultsDir, runId } = validateFrozenRun();
      await writeCaseObservation({
        catalog,
        infrastructureCase: catalog.get('EXECUTION-004'),
        observed: (await runnerIsolation()).execution,
        resultsDir,
        runId,
      });
    },
  );

  test(
    'ARTIFACT-001 proves the independent result volume is writable and readable in-run',
    frozenInfrastructureTest(catalog, 'ARTIFACT-001'),
    async () => {
      const { resultsDir, runId } = validateFrozenRun();
      const evidenceFile = path.join(
        resultsDir,
        'preflight',
        'artifact-write-probe.json',
      );
      const evidence = {
        artifact: 'portal-e2e-write-read-probe',
        case_id: 'ARTIFACT-001',
        run_id: runId,
        status: 'writable-and-readable-in-run',
      };
      await mkdir(path.dirname(evidenceFile), { recursive: true });
      await writeFile(evidenceFile, `${JSON.stringify(evidence)}\n`, 'utf8');
      expect(await readFile(evidenceFile, 'utf8')).toBe(
        `${JSON.stringify(evidence)}\n`,
      );

      await writeCaseObservation({
        catalog,
        infrastructureCase: catalog.get('ARTIFACT-001'),
        observed: (await runnerIsolation()).artifact,
        resultsDir,
        runId,
      });
    },
  );
});
