import os from 'node:os';
import path from 'node:path';

export const ENVIRONMENT_VARIABLES = {
  contractCommit: 'CONTRACT_COMMIT',
  contractTag: 'CONTRACT_TAG',
  contractVersion: 'CONTRACT_VERSION',
  controllerBaseUrl: 'CONTROLLER_BASE_URL',
  hermesBaseUrl: 'HERMES_BASE_URL',
  networkProbeTimeoutMs: 'NETWORK_PROBE_TIMEOUT_MS',
  portalBaseUrl: 'PORTAL_BASE_URL',
  portalReadyTimeoutMs: 'PORTAL_READY_TIMEOUT_MS',
  resultsDir: 'RESULTS_DIR',
  runId: 'RUN_ID',
  specificationRoot: 'SPEC_ROOT',
  testTimeoutMs: 'PORTAL_E2E_TIMEOUT_MS',
} as const;

export interface ContractProvenance {
  contract_commit: string;
  contract_tag: string;
  contract_version: string;
}

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

export function configuredSpecificationRoot(): string {
  return path.resolve(
    configuredValue(ENVIRONMENT_VARIABLES.specificationRoot) ?? '/spec',
  );
}

export function requiredRunId(): string {
  const runId = configuredValue(ENVIRONMENT_VARIABLES.runId);
  if (
    runId === undefined ||
    !/^[a-z0-9](?:[a-z0-9_-]{0,61}[a-z0-9])?$/.test(runId)
  ) {
    throw new Error(
      `${ENVIRONMENT_VARIABLES.runId} must be one lowercase artifact-safe segment`,
    );
  }
  return runId;
}

export function requiredContractProvenance(
  frozenContractVersion: string,
): ContractProvenance {
  const contractVersion = configuredValue(
    ENVIRONMENT_VARIABLES.contractVersion,
  );
  const contractTag = configuredValue(ENVIRONMENT_VARIABLES.contractTag);
  const contractCommit = configuredValue(ENVIRONMENT_VARIABLES.contractCommit);
  if (contractVersion !== frozenContractVersion) {
    throw new Error(
      `${ENVIRONMENT_VARIABLES.contractVersion} must match Frozen suite version ${frozenContractVersion}`,
    );
  }
  if (contractTag !== `contract-m0-m1-v${frozenContractVersion}`) {
    throw new Error(
      `${ENVIRONMENT_VARIABLES.contractTag} must identify the Frozen M0/M1 tag`,
    );
  }
  if (contractCommit === undefined || !/^[0-9a-f]{40}$/.test(contractCommit)) {
    throw new Error(
      `${ENVIRONMENT_VARIABLES.contractCommit} must be a full lowercase Git commit`,
    );
  }
  return {
    contract_commit: contractCommit,
    contract_tag: contractTag,
    contract_version: contractVersion,
  };
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
