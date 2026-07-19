import { isDeepStrictEqual } from 'node:util';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

import type {
  FrozenInfrastructureCase,
  FrozenInfrastructureCaseCatalog,
} from './infrastructure-cases';

export interface CaseObservationRecord {
  case_id: string;
  contract_version: string;
  expected_source: string;
  expected_suite_id: string;
  mismatches: Array<{ field: string }>;
  observed: Record<string, unknown>;
  observed_fields: string[];
  run_id: string;
  runner_subset_status: 'FAIL' | 'NOT_EVALUATED' | 'PASS';
  schema_version: '1.0.0';
  unobserved_fields: string[];
}

interface RunnerObservationAggregate {
  cases: Record<string, CaseObservationRecord>;
  contract_version: string;
  expected_source: string;
  expected_suite_id: string;
  run_id: string;
  schema_version: '1.0.0';
}

interface WriteCaseObservationOptions {
  catalog: FrozenInfrastructureCaseCatalog;
  infrastructureCase: FrozenInfrastructureCase;
  observed: Record<string, unknown>;
  resultsDir: string;
  runId: string;
}

export async function writeCaseObservation({
  catalog,
  infrastructureCase,
  observed,
  resultsDir,
  runId,
}: WriteCaseObservationOptions): Promise<CaseObservationRecord> {
  const expectedFields = Object.keys(infrastructureCase.expected).sort();
  const observedFields = Object.keys(observed).sort();
  for (const field of observedFields) {
    if (!Object.hasOwn(infrastructureCase.expected, field)) {
      throw new Error(
        `${infrastructureCase.caseId} observed.${field} is not present in Frozen Expected`,
      );
    }
  }

  const mismatches = observedFields
    .filter(
      (field) =>
        !isDeepStrictEqual(observed[field], infrastructureCase.expected[field]),
    )
    .map((field) => ({ field }));
  const record: CaseObservationRecord = {
    schema_version: '1.0.0',
    case_id: infrastructureCase.caseId,
    contract_version: catalog.contractVersion,
    expected_source: 'test-cases/infrastructure/cases.yaml',
    expected_suite_id: catalog.suiteId,
    run_id: runId,
    runner_subset_status:
      mismatches.length > 0
        ? 'FAIL'
        : observedFields.length > 0
          ? 'PASS'
          : 'NOT_EVALUATED',
    observed_fields: observedFields,
    unobserved_fields: expectedFields.filter(
      (field) => !Object.hasOwn(observed, field),
    ),
    observed,
    mismatches,
  };

  const evidencePath = path.join(
    path.resolve(resultsDir),
    'evidence',
    `${infrastructureCase.caseId}.json`,
  );
  await mkdir(path.dirname(evidencePath), { recursive: true });
  await writeFile(evidencePath, `${JSON.stringify(record, null, 2)}\n`, 'utf8');
  const aggregatePath = path.join(
    path.resolve(resultsDir),
    'runner-observations.json',
  );
  let aggregate: RunnerObservationAggregate = {
    schema_version: '1.0.0',
    contract_version: catalog.contractVersion,
    expected_source: 'test-cases/infrastructure/cases.yaml',
    expected_suite_id: catalog.suiteId,
    run_id: runId,
    cases: {},
  };
  let existingText: string | undefined;
  try {
    existingText = await readFile(aggregatePath, 'utf8');
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') {
      throw error;
    }
  }
  if (existingText !== undefined) {
    try {
      const existing: unknown = JSON.parse(existingText);
      if (
        typeof existing !== 'object' ||
        existing === null ||
        !('cases' in existing) ||
        typeof existing.cases !== 'object' ||
        existing.cases === null
      ) {
        throw new Error('missing cases object');
      }
      aggregate = existing as RunnerObservationAggregate;
    } catch (error) {
      throw new Error(
        `runner-observations.json is invalid: ${String(error)}`,
      );
    }
  }
  if (
    aggregate.run_id !== runId ||
    aggregate.contract_version !== catalog.contractVersion ||
    aggregate.expected_suite_id !== catalog.suiteId
  ) {
    throw new Error('Existing runner-observations.json has incompatible provenance');
  }
  aggregate.cases[infrastructureCase.caseId] = record;
  await writeFile(
    aggregatePath,
    `${JSON.stringify(aggregate, null, 2)}\n`,
    'utf8',
  );

  if (mismatches.length > 0) {
    throw new Error(
      `${infrastructureCase.caseId} runner observation differs from Frozen Expected: ${mismatches
        .map(({ field }) => field)
        .join(', ')}`,
    );
  }
  return record;
}
