import path from 'node:path';

import { defineConfig, devices } from '@playwright/test';

import {
  configuredResultsDir,
  configuredValue,
  configurationSafePositiveInteger,
  DEFAULT_TEST_TIMEOUT_MS,
  ENVIRONMENT_VARIABLES,
} from './support/environment';

const resultsDir = configuredResultsDir();
const portalBaseUrl = configuredValue(ENVIRONMENT_VARIABLES.portalBaseUrl);

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  timeout: configurationSafePositiveInteger(
    ENVIRONMENT_VARIABLES.testTimeoutMs,
    DEFAULT_TEST_TIMEOUT_MS,
  ),
  expect: {
    timeout: 5_000,
  },
  outputDir: path.join(resultsDir, 'test-output'),
  reporter: [
    [
      'junit',
      {
        outputFile: path.join(resultsDir, 'junit', 'portal-e2e.xml'),
        embedAnnotationsAsProperties: true,
      },
    ],
    [
      'html',
      {
        outputFolder: path.join(resultsDir, 'playwright-report'),
        open: 'never',
      },
    ],
    [
      './reporters/hermes-metadata-reporter.ts',
      {
        outputFile: path.join(resultsDir, 'metadata.json'),
        resultsDir,
      },
    ],
  ],
  use: {
    baseURL: portalBaseUrl,
    ignoreHTTPSErrors: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
      },
    },
  ],
});
