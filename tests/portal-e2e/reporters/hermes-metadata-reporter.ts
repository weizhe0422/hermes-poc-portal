import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

import type {
  FullResult,
  Reporter,
  TestCase,
  TestResult,
} from '@playwright/test/reporter';

import { requiredContractProvenance } from '../support/environment';
import { FROZEN_INFRASTRUCTURE_ANNOTATIONS } from '../support/infrastructure-cases';

interface ReporterOptions {
  outputFile: string;
  resultsDir: string;
  summaryFile: string;
}

interface AttachmentRecord {
  content_type: string;
  name: string;
  path?: string;
}

interface CaseExecutionRecord {
  acceptance_status: string;
  attachments: AttachmentRecord[];
  case_id: string;
  case_source: string;
  coverage_claim: string;
  duration_ms: number;
  evidence_kind: string;
  execution_status: TestResult['status'];
  file: string;
  golden_status: string;
  requirement_ids: string[];
  retry: number;
  runner_subset_status: string;
  observed_fields: string[];
  observation_path: string;
  title: string;
  unobserved_fields: string[];
}

interface RunnerObservation {
  observed_fields?: string[];
  runner_subset_status?: string;
  unobserved_fields?: string[];
}

interface RunnerObservationAggregate {
  cases?: Record<string, RunnerObservation>;
}

function annotationValues(test: TestCase, type: string): string[] {
  return test.annotations
    .filter((annotation) => annotation.type === type)
    .map((annotation) => annotation.description ?? '')
    .filter(Boolean);
}

function annotationValue(test: TestCase, type: string): string {
  return annotationValues(test, type)[0] ?? 'missing';
}

function safeFileSegment(value: string): string {
  return value.replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '');
}

function attachmentBucket(
  attachment: TestResult['attachments'][number],
): 'screenshots' | 'traces' | 'videos' | undefined {
  const extension = attachment.path
    ? path.extname(attachment.path).toLowerCase()
    : '';

  if (attachment.contentType.startsWith('image/') || extension === '.png') {
    return 'screenshots';
  }
  if (attachment.name === 'trace' || extension === '.zip') {
    return 'traces';
  }
  if (attachment.contentType.startsWith('video/') || extension === '.webm') {
    return 'videos';
  }
  return undefined;
}

export default class HermesMetadataReporter implements Reporter {
  private readonly options: ReporterOptions;
  private readonly records: CaseExecutionRecord[] = [];

  constructor(options: ReporterOptions) {
    this.options = options;
  }

  async onTestEnd(test: TestCase, result: TestResult): Promise<void> {
    const caseId = annotationValue(
      test,
      FROZEN_INFRASTRUCTURE_ANNOTATIONS.caseId,
    );
    const copiedAttachments: AttachmentRecord[] = [];

    for (const [index, attachment] of result.attachments.entries()) {
      const bucket = attachmentBucket(attachment);
      if (bucket === undefined || (!attachment.path && !attachment.body)) {
        continue;
      }

      const originalName = attachment.path
        ? path.basename(attachment.path)
        : `${safeFileSegment(attachment.name)}.bin`;
      const destinationName = [
        safeFileSegment(caseId),
        `retry-${result.retry}`,
        String(index),
        safeFileSegment(originalName),
      ].join('-');
      const destination = path.join(
        this.options.resultsDir,
        bucket,
        destinationName,
      );

      await mkdir(path.dirname(destination), { recursive: true });
      if (attachment.path) {
        await copyFile(attachment.path, destination);
      } else if (attachment.body) {
        await writeFile(destination, attachment.body);
      }

      copiedAttachments.push({
        content_type: attachment.contentType,
        name: attachment.name,
        path: path.relative(this.options.resultsDir, destination),
      });
    }

    this.records.push({
      acceptance_status: annotationValue(
        test,
        FROZEN_INFRASTRUCTURE_ANNOTATIONS.acceptanceStatus,
      ),
      attachments: copiedAttachments,
      case_id: caseId,
      case_source: annotationValue(
        test,
        FROZEN_INFRASTRUCTURE_ANNOTATIONS.caseSource,
      ),
      coverage_claim: annotationValue(
        test,
        FROZEN_INFRASTRUCTURE_ANNOTATIONS.coverageClaim,
      ),
      duration_ms: result.duration,
      evidence_kind: annotationValue(
        test,
        FROZEN_INFRASTRUCTURE_ANNOTATIONS.evidenceKind,
      ),
      execution_status: result.status,
      file: test.location.file,
      golden_status: annotationValue(
        test,
        FROZEN_INFRASTRUCTURE_ANNOTATIONS.goldenStatus,
      ),
      requirement_ids: annotationValues(
        test,
        FROZEN_INFRASTRUCTURE_ANNOTATIONS.requirementId,
      ),
      retry: result.retry,
      runner_subset_status: 'MISSING',
      observed_fields: [],
      observation_path: `evidence/${caseId}.json`,
      title: test.titlePath().join(' > '),
      unobserved_fields: [],
    });
  }

  async onEnd(result: FullResult): Promise<void> {
    const observationFile = path.join(
      this.options.resultsDir,
      'runner-observations.json',
    );
    let observations: RunnerObservationAggregate = {};
    try {
      observations = JSON.parse(
        await readFile(observationFile, 'utf8'),
      ) as RunnerObservationAggregate;
    } catch {
      observations = {};
    }
    for (const record of this.records) {
      const observation = observations.cases?.[record.case_id];
      record.runner_subset_status =
        observation?.runner_subset_status ?? 'MISSING';
      record.observed_fields = observation?.observed_fields ?? [];
      record.unobserved_fields = observation?.unobserved_fields ?? [];
    }
    const provenance = requiredContractProvenance('0.2.0');
    const payload = {
      schema_version: '1.0.0',
      report_type: 'hermes.portal-e2e.frozen-infrastructure-execution',
      generated_at: new Date().toISOString(),
      ...provenance,
      suite_status: result.status,
      acceptance: {
        coverage_claim: 'case-level',
        golden_status: 'frozen-v0.2.0',
        note: 'Runner observations are compared to Frozen Expected field-by-field. Host and post-exit fields require outer evidence before the final Acceptance verdict.',
      },
      runner_observation_file: 'runner-observations.json',
      cases: this.records,
    };

    for (const destination of [
      this.options.outputFile,
      this.options.summaryFile,
    ]) {
      await mkdir(path.dirname(destination), { recursive: true });
      await writeFile(
        destination,
        `${JSON.stringify(payload, null, 2)}\n`,
        'utf8',
      );
    }
  }
}
