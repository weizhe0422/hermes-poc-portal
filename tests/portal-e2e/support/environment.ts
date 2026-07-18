import os from 'node:os';
import path from 'node:path';

export const ENVIRONMENT_VARIABLES = {
  controllerBaseUrl: 'CONTROLLER_BASE_URL',
  hermesBaseUrl: 'HERMES_BASE_URL',
  networkProbeTimeoutMs: 'NETWORK_PROBE_TIMEOUT_MS',
  portalBaseUrl: 'PORTAL_BASE_URL',
  portalReadyTimeoutMs: 'PORTAL_READY_TIMEOUT_MS',
  resultsDir: 'RESULTS_DIR',
  testTimeoutMs: 'PORTAL_E2E_TIMEOUT_MS',
} as const;

export const DEFAULT_NETWORK_PROBE_TIMEOUT_MS = 3_000;
export const DEFAULT_PORTAL_READY_TIMEOUT_MS = 60_000;
export const DEFAULT_TEST_TIMEOUT_MS = 75_000;

export function configuredValue(name: string): string | undefined {
  const value = process.env[name]?.trim();
  return value ? value : undefined;
}

export function configuredResultsDir(): string {
  const value = configuredValue(ENVIRONMENT_VARIABLES.resultsDir);
  return path.resolve(
    value ?? path.join(os.tmpdir(), 'hermes-poc-portal-e2e-results'),
  );
}

export function configuredPositiveInteger(
  name: string,
  fallback: number,
): number {
  const rawValue = configuredValue(name);
  if (rawValue === undefined) {
    return fallback;
  }

  const value = Number(rawValue);
  if (!Number.isSafeInteger(value) || value <= 0) {
    throw new Error(`${name} must be a positive integer; received ${rawValue}`);
  }

  return value;
}

export function configurationSafePositiveInteger(
  name: string,
  fallback: number,
): number {
  try {
    return configuredPositiveInteger(name, fallback);
  } catch {
    // Keep Playwright configuration loadable so the preflight test can report
    // invalid environment input through JUnit instead of failing before tests.
    return fallback;
  }
}

export function requiredHttpUrl(name: string): URL {
  const value = configuredValue(name);
  if (value === undefined) {
    throw new Error(`${name} is required`);
  }

  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error(`${name} must be an absolute HTTP(S) URL`);
  }

  if (!['http:', 'https:'].includes(url.protocol)) {
    throw new Error(`${name} must use the http or https scheme`);
  }
  if (url.username || url.password) {
    throw new Error(`${name} must not contain embedded credentials`);
  }

  return url;
}
