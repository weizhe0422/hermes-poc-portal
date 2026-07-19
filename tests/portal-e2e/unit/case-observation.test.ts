import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';

import { writeCaseObservation } from '../support/case-observation';
import { FrozenInfrastructureCaseCatalog } from '../support/infrastructure-cases';

const specificationRoot = path.resolve(
  __dirname,
  '../../../hermes-poc-specification-v0.1',
);

test('observation compares only observed fields and preserves unobserved fields', async () => {
  const resultsDir = await mkdtemp(path.join(os.tmpdir(), 'hermes-observation-'));
  const catalog = await FrozenInfrastructureCaseCatalog.load(specificationRoot);
  const infrastructureCase = catalog.get('SECURITY-002');

  const record = await writeCaseObservation({
    catalog,
    infrastructureCase,
    observed: {
      can_connect_controller: infrastructureCase.expectedBoolean(
        'can_connect_controller',
      ),
      can_connect_hermes:
        infrastructureCase.expectedBoolean('can_connect_hermes'),
      can_connect_portal:
        infrastructureCase.expectedBoolean('can_connect_portal'),
    },
    resultsDir,
    runId: 'unit-observation',
  });

  assert.equal(record.runner_subset_status, 'PASS');
  assert.deepEqual(record.observed_fields, [
    'can_connect_controller',
    'can_connect_hermes',
    'can_connect_portal',
  ]);
  assert.deepEqual(record.unobserved_fields, [
    'is_independent_container',
    'networks',
  ]);
  assert.equal('is_independent_container' in record.observed, false);

  const persisted = JSON.parse(
    await readFile(
      path.join(resultsDir, 'evidence/SECURITY-002.json'),
      'utf8',
    ),
  ) as typeof record;
  assert.deepEqual(persisted, record);
  const aggregate = JSON.parse(
    await readFile(path.join(resultsDir, 'runner-observations.json'), 'utf8'),
  ) as { cases: Record<string, typeof record>; run_id: string };
  assert.equal(aggregate.run_id, 'unit-observation');
  assert.deepEqual(aggregate.cases['SECURITY-002'], record);
});

test('observation persists a mismatch before failing the case', async () => {
  const resultsDir = await mkdtemp(path.join(os.tmpdir(), 'hermes-observation-'));
  const catalog = await FrozenInfrastructureCaseCatalog.load(specificationRoot);
  const infrastructureCase = catalog.get('EXECUTION-001');

  await assert.rejects(
    writeCaseObservation({
      catalog,
      infrastructureCase,
      observed: {
        exit_code_is_zero: !infrastructureCase.expectedBoolean(
          'exit_code_is_zero',
        ),
      },
      resultsDir,
      runId: 'unit-mismatch',
    }),
    /EXECUTION-001 runner observation differs from Frozen Expected/,
  );

  const persisted = JSON.parse(
    await readFile(
      path.join(resultsDir, 'evidence/EXECUTION-001.json'),
      'utf8',
    ),
  ) as {
    mismatches: Array<{ field: string }>;
    runner_subset_status: string;
  };
  assert.equal(persisted.runner_subset_status, 'FAIL');
  assert.deepEqual(persisted.mismatches.map(({ field }) => field), [
    'exit_code_is_zero',
  ]);
});

test('observation rejects fields not defined by Frozen Expected', async () => {
  const resultsDir = await mkdtemp(path.join(os.tmpdir(), 'hermes-observation-'));
  const catalog = await FrozenInfrastructureCaseCatalog.load(specificationRoot);

  await assert.rejects(
    writeCaseObservation({
      catalog,
      infrastructureCase: catalog.get('SECURITY-001'),
      observed: { invented_expected: true },
      resultsDir,
      runId: 'unit-invented',
    }),
    /invented_expected is not present in Frozen Expected/,
  );
});

test('observation refuses to overwrite a malformed aggregate', async () => {
  const resultsDir = await mkdtemp(path.join(os.tmpdir(), 'hermes-observation-'));
  const catalog = await FrozenInfrastructureCaseCatalog.load(specificationRoot);
  await writeFile(
    path.join(resultsDir, 'runner-observations.json'),
    '{malformed',
    'utf8',
  );

  await assert.rejects(
    writeCaseObservation({
      catalog,
      infrastructureCase: catalog.get('SECURITY-001'),
      observed: {},
      resultsDir,
      runId: 'unit-corrupt',
    }),
    /runner-observations\.json is invalid/,
  );
});
