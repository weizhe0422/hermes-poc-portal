import { copyFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

import type {
  FullResult,
  Reporter,
  TestCase,
  TestResult,
} from '@playwright/test/reporter';

import { MATRIX_PLACEHOLDER_ANNOTATIONS } from '../support/matrix-placeholder';

interface ReporterOptions {
  outputFile: string;
  resultsDir: string;
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
  title: string;
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
      MATRIX_PLACEHOLDER_ANNOTATIONS.caseId,
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
        MATRIX_PLACEHOLDER_ANNOTATIONS.acceptanceStatus,
      ),
      attachments: copiedAttachments,
      case_id: caseId,
      case_source: annotationValue(
        test,
        MATRIX_PLACEHOLDER_ANNOTATIONS.caseSource,
      ),
      coverage_claim: annotationValue(
        test,
        MATRIX_PLACEHOLDER_ANNOTATIONS.coverageClaim,
      ),
      duration_ms: result.duration,
      evidence_kind: annotationValue(
        test,
        MATRIX_PLACEHOLDER_ANNOTATIONS.evidenceKind,
      ),
      execution_status: result.status,
      file: test.location.file,
      golden_status: annotationValue(
        test,
        MATRIX_PLACEHOLDER_ANNOTATIONS.goldenStatus,
      ),
      requirement_ids: annotationValues(
        test,
        MATRIX_PLACEHOLDER_ANNOTATIONS.requirementId,
      ),
      retry: result.retry,
      title: test.titlePath().join(' > '),
    });
  }

  async onEnd(result: FullResult): Promise<void> {
    const payload = {
      schema_version: '1.0.0',
      report_type: 'hermes.portal-e2e.matrix-placeholder-execution',
      generated_at: new Date().toISOString(),
      suite_status: result.status,
      acceptance: {
        coverage_claim: 'none',
        golden_status: 'not-applicable',
        note: 'Passing placeholder checks are runner evidence only; they are not Contract or Golden Case acceptance.',
      },
      cases: this.records,
    };

    await mkdir(path.dirname(this.options.outputFile), { recursive: true });
    await writeFile(
      this.options.outputFile,
      `${JSON.stringify(payload, null, 2)}\n`,
      'utf8',
    );
  }
}
