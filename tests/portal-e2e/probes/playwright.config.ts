import path from 'node:path';

import { defineConfig } from '@playwright/test';

const artifactDirectory = process.env.PROBE_ARTIFACT_DIR;
if (!artifactDirectory) {
  throw new Error('PROBE_ARTIFACT_DIR is required');
}

export default defineConfig({
  testDir: '.',
  testMatch: 'failing.spec.ts',
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  timeout: 30_000,
  outputDir: path.join(artifactDirectory, 'test-output'),
  reporter: [
    ['line'],
    [
      'junit',
      {
        outputFile: path.join(artifactDirectory, 'junit.xml'),
        embedAnnotationsAsProperties: true,
      },
    ],
  ],
  use: {
    screenshot: 'off',
    trace: 'on',
    video: 'off',
  },
});
