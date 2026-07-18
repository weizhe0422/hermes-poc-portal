import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

import { expect, test } from '@playwright/test';

import {
  configuredPositiveInteger,
  configuredResultsDir,
  configuredValue,
  DEFAULT_NETWORK_PROBE_TIMEOUT_MS,
  DEFAULT_PORTAL_READY_TIMEOUT_MS,
  DEFAULT_TEST_TIMEOUT_MS,
  ENVIRONMENT_VARIABLES,
  requiredHttpUrl,
} from '../support/environment';
import { matrixPlaceholder } from '../support/matrix-placeholder';

test.describe('T-M0 external-container preflight placeholders', () => {
  test(
    'EXECUTION-001 validates required external-runner configuration',
    matrixPlaceholder({
      caseId: 'EXECUTION-001',
      evidenceKind: 'preflight',
      requirementIds: ['E2E-05'],
    }),
    async () => {
      expect(
        configuredValue(ENVIRONMENT_VARIABLES.resultsDir),
        'RESULTS_DIR must be explicitly configured by the external runner',
      ).toBeTruthy();
      expect(() =>
        requiredHttpUrl(ENVIRONMENT_VARIABLES.portalBaseUrl),
      ).not.toThrow();
      expect(() =>
        configuredPositiveInteger(
          ENVIRONMENT_VARIABLES.networkProbeTimeoutMs,
          DEFAULT_NETWORK_PROBE_TIMEOUT_MS,
        ),
      ).not.toThrow();
      expect(() =>
        configuredPositiveInteger(
          ENVIRONMENT_VARIABLES.portalReadyTimeoutMs,
          DEFAULT_PORTAL_READY_TIMEOUT_MS,
        ),
      ).not.toThrow();
      expect(() =>
        configuredPositiveInteger(
          ENVIRONMENT_VARIABLES.testTimeoutMs,
          DEFAULT_TEST_TIMEOUT_MS,
        ),
      ).not.toThrow();
    },
  );

  test(
    'ARTIFACT-001 verifies the isolated result directory is writable',
    matrixPlaceholder({
      caseId: 'ARTIFACT-001',
      evidenceKind: 'artifact',
      requirementIds: ['BLD-08'],
    }),
    async () => {
      const evidenceFile = path.join(
        configuredResultsDir(),
        'preflight',
        'artifact-write-probe.json',
      );
      const evidence = {
        artifact: 'portal-e2e-write-probe',
        status: 'writable',
      };

      await mkdir(path.dirname(evidenceFile), { recursive: true });
      await writeFile(evidenceFile, `${JSON.stringify(evidence)}\n`, 'utf8');

      const writtenEvidence = await readFile(evidenceFile, 'utf8');
      expect(writtenEvidence).toBe(`${JSON.stringify(evidence)}\n`);
    },
  );

  test(
    'EXECUTION-002 keeps per-test output inside the configured result directory',
    matrixPlaceholder({
      caseId: 'EXECUTION-002',
      evidenceKind: 'artifact',
      requirementIds: ['E2E-06'],
    }),
    async ({}, testInfo) => {
      const relativeOutputDir = path.relative(
        configuredResultsDir(),
        testInfo.outputDir,
      );

      expect(relativeOutputDir).not.toBe('');
      expect(relativeOutputDir).not.toBe('..');
      expect(relativeOutputDir.startsWith(`..${path.sep}`)).toBe(false);
      expect(path.isAbsolute(relativeOutputDir)).toBe(false);
    },
  );

  test(
    'EXECUTION-003 keeps automatic retries disabled',
    matrixPlaceholder({
      caseId: 'EXECUTION-003',
      evidenceKind: 'preflight',
      requirementIds: ['E2E-07'],
    }),
    async ({}, testInfo) => {
      expect(testInfo.project.retries).toBe(0);
    },
  );

  test(
    'EXECUTION-004 reserves source-tree immutability evidence for orchestration',
    matrixPlaceholder({
      caseId: 'EXECUTION-004',
      evidenceKind: 'preflight',
      requirementIds: ['E2E-08'],
    }),
    async () => {
      test.fixme(
        true,
        'The external runner must compare the Git tree before and after execution; this container must not receive Git or a writable source mount.',
      );
    },
  );
});
