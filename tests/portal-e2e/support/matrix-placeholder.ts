export const MATRIX_PLACEHOLDER_ANNOTATIONS = {
  acceptanceStatus: 'hermes.acceptance_status',
  caseId: 'hermes.case_id',
  caseSource: 'hermes.case_source',
  coverageClaim: 'hermes.coverage_claim',
  evidenceKind: 'hermes.evidence_kind',
  goldenStatus: 'hermes.golden_status',
  requirementId: 'hermes.requirement_id',
} as const;

const MATRIX_PLACEHOLDER_CASE_ID =
  /^(ARTIFACT-001|EXECUTION-00[1-4]|SECURITY-00[1-3])$/;
const REQUIREMENT_ID = /^(BLD|E2E)-\d{2}$/;

export interface MatrixPlaceholderMetadata {
  caseId: string;
  evidenceKind: 'artifact' | 'network-isolation' | 'preflight';
  requirementIds: readonly string[];
}

interface TestDetails {
  annotation: Array<{ description: string; type: string }>;
  tag: string[];
}

export function matrixPlaceholder(
  metadata: MatrixPlaceholderMetadata,
): TestDetails {
  if (!MATRIX_PLACEHOLDER_CASE_ID.test(metadata.caseId)) {
    throw new Error(
      `${metadata.caseId} is not a T-M0 placeholder ID from the traceability matrix`,
    );
  }
  if (metadata.requirementIds.length === 0) {
    throw new Error(`${metadata.caseId} must reference at least one Requirement ID`);
  }
  for (const requirementId of metadata.requirementIds) {
    if (!REQUIREMENT_ID.test(requirementId)) {
      throw new Error(`Invalid Requirement ID: ${requirementId}`);
    }
  }

  return {
    tag: [
      `@case:${metadata.caseId}`,
      ...metadata.requirementIds.map(
        (requirementId) => `@requirement:${requirementId}`,
      ),
      '@coverage:matrix-placeholder',
    ],
    annotation: [
      {
        type: 'test_case_id',
        description: metadata.caseId,
      },
      {
        type: 'requirement_ids',
        description: metadata.requirementIds.join(','),
      },
      {
        type: 'critical',
        description: 'false',
      },
      {
        type: MATRIX_PLACEHOLDER_ANNOTATIONS.caseId,
        description: metadata.caseId,
      },
      ...metadata.requirementIds.map((requirementId) => ({
        type: MATRIX_PLACEHOLDER_ANNOTATIONS.requirementId,
        description: requirementId,
      })),
      {
        type: MATRIX_PLACEHOLDER_ANNOTATIONS.caseSource,
        description: 'traceability-matrix-placeholder',
      },
      {
        type: MATRIX_PLACEHOLDER_ANNOTATIONS.coverageClaim,
        description: 'none',
      },
      {
        type: MATRIX_PLACEHOLDER_ANNOTATIONS.acceptanceStatus,
        description: 'not-evaluated',
      },
      {
        type: MATRIX_PLACEHOLDER_ANNOTATIONS.goldenStatus,
        description: 'not-applicable',
      },
      {
        type: MATRIX_PLACEHOLDER_ANNOTATIONS.evidenceKind,
        description: metadata.evidenceKind,
      },
    ],
  };
}
