import type { APIRequestContext } from '@playwright/test';
import { expect, test } from '@playwright/test';

import { writeCaseObservation } from '../support/case-observation';
import {
  configuredResultsDir,
  configuredSpecificationRoot,
  configuredPositiveInteger,
  DEFAULT_NETWORK_PROBE_TIMEOUT_MS,
  DEFAULT_PORTAL_READY_TIMEOUT_MS,
  ENVIRONMENT_VARIABLES,
  requiredContractProvenance,
  requiredHttpUrl,
  requiredRunId,
} from '../support/environment';
import {
  FrozenInfrastructureCaseCatalog,
  frozenInfrastructureTest,
} from '../support/infrastructure-cases';

const catalog = FrozenInfrastructureCaseCatalog.loadSync(
  configuredSpecificationRoot(),
);

function probeTimeoutMs(): number {
  return configuredPositiveInteger(
    ENVIRONMENT_VARIABLES.networkProbeTimeoutMs,
    DEFAULT_NETWORK_PROBE_TIMEOUT_MS,
  );
}

function portalReadyTimeoutMs(): number {
  return configuredPositiveInteger(
    ENVIRONMENT_VARIABLES.portalReadyTimeoutMs,
    DEFAULT_PORTAL_READY_TIMEOUT_MS,
  );
}

async function isReachable(
  request: APIRequestContext,
  target: URL,
): Promise<boolean> {
  try {
    const response = await request.get(target.toString(), {
      failOnStatusCode: false,
      maxRedirects: 0,
      timeout: probeTimeoutMs(),
    });
    return response.status() >= 100 && response.status() < 600;
  } catch {
    return false;
  }
}

async function portalBecomesReachable(
  request: APIRequestContext,
  portal: URL,
): Promise<boolean> {
  try {
    await expect
      .poll(() => isReachable(request, portal), {
        intervals: [100, 250, 500, 1_000],
        message: 'Portal public boundary must become reachable',
        timeout: portalReadyTimeoutMs(),
      })
      .toBe(true);
    return true;
  } catch {
    return false;
  }
}

function validateFrozenRun(): { resultsDir: string; runId: string } {
  requiredContractProvenance(catalog.contractVersion);
  return { resultsDir: configuredResultsDir(), runId: requiredRunId() };
}

test.describe('Frozen v0.2 Portal runner network isolation', () => {
  test(
    'SECURITY-001 records runner precondition while Host evidence stays external',
    frozenInfrastructureTest(catalog, 'SECURITY-001'),
    async ({ request }) => {
      const { resultsDir, runId } = validateFrozenRun();
      await writeCaseObservation({
        catalog,
        infrastructureCase: catalog.get('SECURITY-001'),
        observed: {},
        resultsDir,
        runId,
      });

      expect(
        await portalBecomesReachable(
          request,
          requiredHttpUrl(ENVIRONMENT_VARIABLES.portalBaseUrl),
        ),
        'SECURITY-001 precondition requires the Portal to be running; Host-published ports are evaluated by outer evidence',
      ).toBe(true);
    },
  );

  test(
    'SECURITY-002 observes all Runner connectivity fields',
    frozenInfrastructureTest(catalog, 'SECURITY-002'),
    async ({ request }) => {
      const { resultsDir, runId } = validateFrozenRun();
      const infrastructureCase = catalog.get('SECURITY-002');
      const observed = {
        can_connect_portal: await portalBecomesReachable(
          request,
          requiredHttpUrl(ENVIRONMENT_VARIABLES.portalBaseUrl),
        ),
        can_connect_controller: await isReachable(
          request,
          requiredHttpUrl(ENVIRONMENT_VARIABLES.controllerBaseUrl),
        ),
        can_connect_hermes: await isReachable(
          request,
          requiredHttpUrl(ENVIRONMENT_VARIABLES.hermesBaseUrl),
        ),
      };
      await writeCaseObservation({
        catalog,
        infrastructureCase,
        observed,
        resultsDir,
        runId,
      });
    },
  );
});
