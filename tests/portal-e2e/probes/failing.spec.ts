import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

import { expect, test } from '@playwright/test';

const artifactDirectory = process.env.PROBE_ARTIFACT_DIR;
const caseId = process.env.PROBE_CASE_ID;
const mode = process.env.PROBE_MODE;
const runId = process.env.PROBE_RUN_ID;
if (!artifactDirectory || !caseId || !mode || !runId) {
  throw new Error('Failure probe environment is incomplete');
}

test(
  `[${caseId}] injected failure for ${runId}`,
  {
    annotation: [
      { type: 'test_case_id', description: caseId },
      { type: 'run_id', description: runId },
      { type: 'critical', description: 'true' },
      { type: 'attempt_policy', description: 'NO_RETRY' },
    ],
  },
  async ({ page }, testInfo) => {
    const attempt = testInfo.retry + 1;
    const attemptDirectory = path.join(artifactDirectory, 'attempts');
    await mkdir(attemptDirectory, { recursive: true });
    await writeFile(
      path.join(attemptDirectory, `attempt-${attempt}.json`),
      `${JSON.stringify({ attempt, case_id: caseId, run_id: runId })}\n`,
      'utf8',
    );
    console.log(`run_id=${runId} case_id=${caseId} attempt=${attempt}`);
    await page.setContent('<main>Hermes deterministic failure probe</main>');

    if (mode === 'flaky-first-attempt' && testInfo.retry > 0) {
      return;
    }
    expect(false, `${caseId} injected failure must remain visible`).toBe(true);
  },
);
