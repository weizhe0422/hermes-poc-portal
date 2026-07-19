import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';

import { parse } from 'yaml';

import {
  FROZEN_INFRASTRUCTURE_CASE_IDS,
  FrozenInfrastructureCaseCatalog,
  frozenInfrastructureTest,
} from '../support/infrastructure-cases';

const repositoryRoot = path.resolve(
  __dirname,
  '../../..',
);
const specificationRoot = path.join(
  repositoryRoot,
  'hermes-poc-specification-v0.1',
);

test('frozen case metadata is sourced exactly from infrastructure cases.yaml', async () => {
  const catalog = await FrozenInfrastructureCaseCatalog.load(specificationRoot);
  const source = parse(
    await readFile(
      path.join(specificationRoot, 'test-cases/infrastructure/cases.yaml'),
      'utf8',
    ),
  ) as { cases: Array<Record<string, unknown>>; suite_id: string };

  assert.equal(catalog.suiteId, source.suite_id);
  assert.equal(catalog.contractVersion, '0.2.0');

  for (const caseId of FROZEN_INFRASTRUCTURE_CASE_IDS) {
    const raw = source.cases.find((candidate) => candidate.case_id === caseId);
    assert.ok(raw, `${caseId} must exist in the Frozen YAML`);
    const loaded = catalog.get(caseId);
    const details = frozenInfrastructureTest(catalog, caseId);

    assert.deepEqual(loaded.requirementIds, raw.requirement_ids);
    assert.equal(loaded.critical, raw.critical);
    assert.deepEqual(loaded.expected, raw.expected);
    assert.equal(Object.isFrozen(loaded.expected), true);
    for (const value of Object.values(loaded.expected)) {
      if (typeof value === 'object' && value !== null) {
        assert.equal(Object.isFrozen(value), true);
      }
    }
    assert.deepEqual(
      details.annotation
        .filter(({ type }) => type === 'hermes.requirement_id')
        .map(({ description }) => description),
      raw.requirement_ids,
    );
    assert.ok(
      details.annotation.some(
        ({ type, description }) =>
          type === 'critical' && description === 'true',
      ),
    );
  }
});

test('loader rejects a selected case whose metadata is not critical', async () => {
  const tempRoot = await mkdtemp(path.join(os.tmpdir(), 'hermes-infra-cases-'));
  const caseDirectory = path.join(tempRoot, 'test-cases/infrastructure');
  await mkdir(caseDirectory, { recursive: true });
  await writeFile(
    path.join(caseDirectory, 'cases.yaml'),
    [
      'suite_id: infrastructure-v0.2',
      'cases:',
      '  - case_id: SECURITY-001',
      '    purpose: synthetic invalid metadata',
      '    scenario: SECURITY',
      '    requirement_ids: [BLD-07]',
      '    critical: false',
      '    input: {action: NETWORK_SCAN}',
      '    expected: {controller_published: false}',
      '    verdict_mode: AUTOMATED',
      '',
    ].join('\n'),
    'utf8',
  );

  await assert.rejects(
    FrozenInfrastructureCaseCatalog.load(tempRoot),
    /SECURITY-001.*critical=true/,
  );
});

test('expected accessors reject an absent or mistyped Frozen field', async () => {
  const catalog = await FrozenInfrastructureCaseCatalog.load(specificationRoot);
  const security = catalog.get('SECURITY-002');

  assert.equal(typeof security.expectedBoolean('can_connect_portal'), 'boolean');
  assert.ok(
    security.expectedStringArray('networks').every((value) =>
      typeof value === 'string'),
  );
  assert.throws(
    () => security.expectedBoolean('networks'),
    /SECURITY-002 expected\.networks must be boolean/,
  );
  assert.throws(
    () => security.expectedBoolean('not_in_contract'),
    /SECURITY-002 expected\.not_in_contract must be boolean/,
  );
});
