import { readFileSync } from 'node:fs';
import path from 'node:path';

import { parse } from 'yaml';

export const FROZEN_INFRASTRUCTURE_CASE_IDS = [
  'SECURITY-001',
  'SECURITY-002',
  'SECURITY-003',
  'EXECUTION-001',
  'EXECUTION-002',
  'EXECUTION-003',
  'EXECUTION-004',
  'ARTIFACT-001',
] as const;

export type FrozenInfrastructureCaseId =
  (typeof FROZEN_INFRASTRUCTURE_CASE_IDS)[number];

const FROZEN_CASE_ID_SET = new Set<string>(FROZEN_INFRASTRUCTURE_CASE_IDS);
const FROZEN_SUITE_ID = 'infrastructure-v0.2';
const FROZEN_CONTRACT_VERSION = '0.2.0';
const REQUIREMENT_ID = /^[A-Z][A-Z0-9]*-\d+$/;

export const FROZEN_INFRASTRUCTURE_ANNOTATIONS = {
  acceptanceStatus: 'hermes.acceptance_status',
  caseId: 'hermes.case_id',
  caseSource: 'hermes.case_source',
  contractVersion: 'hermes.contract_version',
  coverageClaim: 'hermes.coverage_claim',
  evidenceKind: 'hermes.evidence_kind',
  goldenStatus: 'hermes.golden_status',
  requirementId: 'hermes.requirement_id',
} as const;

export type InfrastructureEvidenceKind =
  | 'artifact'
  | 'execution-probe'
  | 'host-network'
  | 'network-isolation'
  | 'runner-isolation';

const EVIDENCE_KINDS: Record<
  FrozenInfrastructureCaseId,
  InfrastructureEvidenceKind
> = {
  'ARTIFACT-001': 'artifact',
  'EXECUTION-001': 'execution-probe',
  'EXECUTION-002': 'execution-probe',
  'EXECUTION-003': 'execution-probe',
  'EXECUTION-004': 'runner-isolation',
  'SECURITY-001': 'host-network',
  'SECURITY-002': 'network-isolation',
  'SECURITY-003': 'runner-isolation',
};

type JsonObject = Record<string, unknown>;

interface RawInfrastructureCase {
  case_id?: unknown;
  critical?: unknown;
  expected?: unknown;
  requirement_ids?: unknown;
}

interface RawInfrastructureDocument {
  cases?: unknown;
  suite_id?: unknown;
}

function isJsonObject(value: unknown): value is JsonObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function deepFreeze<T>(value: T): T {
  if (typeof value === 'object' && value !== null && !Object.isFrozen(value)) {
    for (const nested of Object.values(value)) {
      deepFreeze(nested);
    }
    Object.freeze(value);
  }
  return value;
}

function requireString(value: unknown, description: string): string {
  if (typeof value !== 'string' || value.length === 0) {
    throw new Error(`${description} must be a non-empty string`);
  }
  return value;
}

export class FrozenInfrastructureCase {
  readonly caseId: FrozenInfrastructureCaseId;
  readonly critical: true;
  readonly expected: Readonly<JsonObject>;
  readonly requirementIds: readonly string[];

  constructor(raw: RawInfrastructureCase) {
    const caseId = requireString(raw.case_id, 'case_id');
    if (!FROZEN_CASE_ID_SET.has(caseId)) {
      throw new Error(`${caseId} is not a Portal T-M0 Frozen infrastructure case`);
    }
    if (raw.critical !== true) {
      throw new Error(`${caseId} must declare critical=true in the Frozen YAML`);
    }
    if (
      !Array.isArray(raw.requirement_ids) ||
      raw.requirement_ids.length === 0 ||
      raw.requirement_ids.some(
        (value) => typeof value !== 'string' || !REQUIREMENT_ID.test(value),
      )
    ) {
      throw new Error(`${caseId} must declare valid requirement_ids`);
    }
    if (new Set(raw.requirement_ids).size !== raw.requirement_ids.length) {
      throw new Error(`${caseId} contains duplicate requirement_ids`);
    }
    if (!isJsonObject(raw.expected)) {
      throw new Error(`${caseId} must declare an expected object`);
    }

    this.caseId = caseId as FrozenInfrastructureCaseId;
    this.critical = true;
    this.expected = deepFreeze(structuredClone(raw.expected));
    this.requirementIds = Object.freeze([...raw.requirement_ids]);
  }

  expectedBoolean(field: string): boolean {
    const value = this.expected[field];
    if (typeof value !== 'boolean') {
      throw new Error(`${this.caseId} expected.${field} must be boolean`);
    }
    return value;
  }

  expectedNumberArray(field: string): readonly number[] {
    const value = this.expected[field];
    if (
      !Array.isArray(value) ||
      value.some((item) => typeof item !== 'number')
    ) {
      throw new Error(`${this.caseId} expected.${field} must be a number array`);
    }
    return value;
  }

  expectedStringArray(field: string): readonly string[] {
    const value = this.expected[field];
    if (
      !Array.isArray(value) ||
      value.some((item) => typeof item !== 'string')
    ) {
      throw new Error(`${this.caseId} expected.${field} must be a string array`);
    }
    return value;
  }
}

export class FrozenInfrastructureCaseCatalog {
  readonly contractVersion = FROZEN_CONTRACT_VERSION;
  readonly sourcePath: string;
  readonly suiteId: string;
  private readonly cases: ReadonlyMap<
    FrozenInfrastructureCaseId,
    FrozenInfrastructureCase
  >;

  private constructor(
    sourcePath: string,
    suiteId: string,
    cases: Map<FrozenInfrastructureCaseId, FrozenInfrastructureCase>,
  ) {
    this.sourcePath = sourcePath;
    this.suiteId = suiteId;
    this.cases = cases;
  }

  static loadSync(specificationRoot: string): FrozenInfrastructureCaseCatalog {
    const sourcePath = path.join(
      path.resolve(specificationRoot),
      'test-cases',
      'infrastructure',
      'cases.yaml',
    );
    let document: RawInfrastructureDocument;
    try {
      const parsed: unknown = parse(readFileSync(sourcePath, 'utf8'));
      if (!isJsonObject(parsed)) {
        throw new Error('document root must be an object');
      }
      document = parsed;
    } catch (error) {
      throw new Error(
        `Unable to load Frozen infrastructure cases from ${sourcePath}: ${String(error)}`,
      );
    }

    if (document.suite_id !== FROZEN_SUITE_ID) {
      throw new Error(
        `${sourcePath} suite_id must be ${FROZEN_SUITE_ID}; received ${String(document.suite_id)}`,
      );
    }
    if (!Array.isArray(document.cases)) {
      throw new Error(`${sourcePath} must contain a cases array`);
    }

    const selected = new Map<
      FrozenInfrastructureCaseId,
      FrozenInfrastructureCase
    >();
    const seenIds = new Set<string>();
    for (const raw of document.cases) {
      if (!isJsonObject(raw)) {
        throw new Error(`${sourcePath} contains a non-object case`);
      }
      const caseId = requireString(raw.case_id, 'case_id');
      if (seenIds.has(caseId)) {
        throw new Error(`Duplicate infrastructure case ID: ${caseId}`);
      }
      seenIds.add(caseId);
      if (!FROZEN_CASE_ID_SET.has(caseId)) {
        continue;
      }
      const frozenCase = new FrozenInfrastructureCase(raw);
      selected.set(frozenCase.caseId, frozenCase);
    }

    const missing = FROZEN_INFRASTRUCTURE_CASE_IDS.filter(
      (caseId) => !selected.has(caseId),
    );
    if (missing.length > 0) {
      throw new Error(
        `${sourcePath} is missing Frozen Portal cases: ${missing.join(', ')}`,
      );
    }

    return new FrozenInfrastructureCaseCatalog(
      sourcePath,
      document.suite_id,
      selected,
    );
  }

  static async load(
    specificationRoot: string,
  ): Promise<FrozenInfrastructureCaseCatalog> {
    return FrozenInfrastructureCaseCatalog.loadSync(specificationRoot);
  }

  get(caseId: FrozenInfrastructureCaseId): FrozenInfrastructureCase {
    const infrastructureCase = this.cases.get(caseId);
    if (infrastructureCase === undefined) {
      throw new Error(`${caseId} is absent from ${this.sourcePath}`);
    }
    return infrastructureCase;
  }
}

interface TestDetails {
  annotation: Array<{ description: string; type: string }>;
  tag: string[];
}

export function frozenInfrastructureTest(
  catalog: FrozenInfrastructureCaseCatalog,
  caseId: FrozenInfrastructureCaseId,
): TestDetails {
  const infrastructureCase = catalog.get(caseId);
  return {
    tag: [
      `@case:${caseId}`,
      ...infrastructureCase.requirementIds.map(
        (requirementId) => `@requirement:${requirementId}`,
      ),
      '@coverage:case-level',
    ],
    annotation: [
      { type: 'test_case_id', description: caseId },
      {
        type: 'requirement_ids',
        description: infrastructureCase.requirementIds.join(','),
      },
      { type: 'critical', description: 'true' },
      {
        type: FROZEN_INFRASTRUCTURE_ANNOTATIONS.caseId,
        description: caseId,
      },
      ...infrastructureCase.requirementIds.map((requirementId) => ({
        type: FROZEN_INFRASTRUCTURE_ANNOTATIONS.requirementId,
        description: requirementId,
      })),
      {
        type: FROZEN_INFRASTRUCTURE_ANNOTATIONS.caseSource,
        description: 'frozen-infrastructure-case',
      },
      {
        type: FROZEN_INFRASTRUCTURE_ANNOTATIONS.coverageClaim,
        description: 'case-level',
      },
      {
        type: FROZEN_INFRASTRUCTURE_ANNOTATIONS.acceptanceStatus,
        description: 'case-evaluated',
      },
      {
        type: FROZEN_INFRASTRUCTURE_ANNOTATIONS.goldenStatus,
        description: 'frozen-v0.2.0',
      },
      {
        type: FROZEN_INFRASTRUCTURE_ANNOTATIONS.evidenceKind,
        description: EVIDENCE_KINDS[caseId],
      },
      {
        type: FROZEN_INFRASTRUCTURE_ANNOTATIONS.contractVersion,
        description: catalog.contractVersion,
      },
    ],
  };
}
