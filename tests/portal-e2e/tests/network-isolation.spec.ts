import type { APIRequestContext } from '@playwright/test';
import { expect, test } from '@playwright/test';

import {
  configuredPositiveInteger,
  DEFAULT_NETWORK_PROBE_TIMEOUT_MS,
  DEFAULT_PORTAL_READY_TIMEOUT_MS,
  ENVIRONMENT_VARIABLES,
  requiredHttpUrl,
} from '../support/environment';
import { matrixPlaceholder } from '../support/matrix-placeholder';

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

async function expectUnreachable(
  request: APIRequestContext,
  targetName: string,
  target: URL,
): Promise<void> {
  try {
    const response = await request.get(target.toString(), {
      failOnStatusCode: false,
      maxRedirects: 0,
      timeout: probeTimeoutMs(),
    });
    throw new Error(
      `${targetName} was reachable from the Portal E2E runner (HTTP ${response.status()})`,
    );
  } catch (error) {
    if (
      error instanceof Error &&
      error.message.startsWith(`${targetName} was reachable`)
    ) {
      throw error;
    }
  }
}

test.describe('T-M0 Portal runner network-isolation placeholders', () => {
  test(
    'SECURITY-001 reaches the configured Portal through its public boundary',
    matrixPlaceholder({
      caseId: 'SECURITY-001',
      evidenceKind: 'network-isolation',
      requirementIds: ['E2E-01'],
    }),
    async ({ request }) => {
      const portal = requiredHttpUrl(ENVIRONMENT_VARIABLES.portalBaseUrl);
      await expect
        .poll(
          async () => {
            try {
              const response = await request.get(portal.toString(), {
                failOnStatusCode: false,
                maxRedirects: 0,
                timeout: probeTimeoutMs(),
              });
              return response.status() >= 100 && response.status() < 600;
            } catch {
              return false;
            }
          },
          {
            intervals: [100, 250, 500, 1_000],
            message: 'Portal public boundary must become reachable',
            timeout: portalReadyTimeoutMs(),
          },
        )
        .toBe(true);
    },
  );

  test(
    'SECURITY-002 cannot reach the Controller directly',
    matrixPlaceholder({
      caseId: 'SECURITY-002',
      evidenceKind: 'network-isolation',
      requirementIds: ['E2E-02'],
    }),
    async ({ request }) => {
      await expectUnreachable(
        request,
        'Controller',
        requiredHttpUrl(ENVIRONMENT_VARIABLES.controllerBaseUrl),
      );
    },
  );

  test(
    'SECURITY-003 cannot reach Hermes directly',
    matrixPlaceholder({
      caseId: 'SECURITY-003',
      evidenceKind: 'network-isolation',
      requirementIds: ['E2E-02'],
    }),
    async ({ request }) => {
      await expectUnreachable(
        request,
        'Hermes',
        requiredHttpUrl(ENVIRONMENT_VARIABLES.hermesBaseUrl),
      );
    },
  );
});
