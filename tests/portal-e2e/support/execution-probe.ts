import { spawn } from 'node:child_process';
import { mkdir, readFile, readdir, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';

export type ProbeArtifactName = 'junit' | 'log' | 'trace';
export type ProbeMode = 'deterministic' | 'flaky-first-attempt';

const PROBE_ARTIFACTS: readonly ProbeArtifactName[] = [
  'junit',
  'trace',
  'log',
];
const SAFE_RUN_ID = /^[a-z0-9](?:[a-z0-9_-]{0,61}[a-z0-9])?$/;
const SAFE_CASE_ID = /^[A-Z]+-[0-9]{3}$/;

export interface FailureProbeResult {
  artifact_contains_case_id: boolean;
  artifact_contains_run_id: boolean;
  artifact_paths: Partial<Record<ProbeArtifactName, string>>;
  artifacts_generated: ProbeArtifactName[];
  attempt_count: number;
  auto_retried_to_pass: boolean;
  exit_code: number | null;
  exit_code_is_zero: boolean;
  failure_converted_to_success: boolean;
  failure_retained: boolean;
}

interface EvaluateFailureProbeOptions {
  artifactDirectory: string;
  caseId: string;
  exitCode: number | null;
  requiredArtifacts?: readonly string[];
  runId: string;
}

async function nonEmptyFile(candidate: string): Promise<boolean> {
  try {
    return (await stat(candidate)).isFile() && (await stat(candidate)).size > 0;
  } catch {
    return false;
  }
}

async function findNamedFile(
  directory: string,
  filename: string,
): Promise<string | undefined> {
  let entries;
  try {
    entries = await readdir(directory, { withFileTypes: true });
  } catch {
    return undefined;
  }
  for (const entry of entries) {
    const candidate = path.join(directory, entry.name);
    if (entry.isFile() && entry.name === filename && (await nonEmptyFile(candidate))) {
      return candidate;
    }
    if (entry.isDirectory()) {
      const nested = await findNamedFile(candidate, filename);
      if (nested !== undefined) {
        return nested;
      }
    }
  }
  return undefined;
}

function validateArtifactNames(
  requiredArtifacts: readonly string[],
): asserts requiredArtifacts is readonly ProbeArtifactName[] {
  for (const artifact of requiredArtifacts) {
    if (!PROBE_ARTIFACTS.includes(artifact as ProbeArtifactName)) {
      throw new Error(`Unsupported Frozen probe artifact: ${artifact}`);
    }
  }
}

export async function evaluateFailureProbe({
  artifactDirectory,
  caseId,
  exitCode,
  requiredArtifacts = PROBE_ARTIFACTS,
  runId,
}: EvaluateFailureProbeOptions): Promise<FailureProbeResult> {
  validateArtifactNames(requiredArtifacts);
  const junitPath = path.join(artifactDirectory, 'junit.xml');
  const logPath = path.join(artifactDirectory, 'playwright.log');
  const tracePath = await findNamedFile(
    path.join(artifactDirectory, 'test-output'),
    'trace.zip',
  );
  const candidates: Partial<Record<ProbeArtifactName, string>> = {
    junit: (await nonEmptyFile(junitPath)) ? junitPath : undefined,
    log: (await nonEmptyFile(logPath)) ? logPath : undefined,
    trace: tracePath,
  };
  const generated = PROBE_ARTIFACTS.filter(
    (artifact) => candidates[artifact] !== undefined,
  );
  const junit = candidates.junit
    ? await readFile(candidates.junit, 'utf8')
    : '';
  const log = candidates.log ? await readFile(candidates.log, 'utf8') : '';
  const junitRetainedFailure = /<(?:failure|error)(?:\s|\/|>)/.test(junit);
  const attemptDirectory = path.join(artifactDirectory, 'attempts');
  let attemptFiles: string[] = [];
  try {
    attemptFiles = (await readdir(attemptDirectory)).filter((filename) =>
      /^attempt-[1-9][0-9]*\.json$/.test(filename),
    );
  } catch {
    attemptFiles = [];
  }
  const artifactPaths = Object.fromEntries(
    Object.entries(candidates)
      .filter((entry): entry is [ProbeArtifactName, string] => entry[1] !== undefined)
      .map(([name, absolutePath]) => [
        name,
        path.relative(artifactDirectory, absolutePath),
      ]),
  );
  const allRequiredPresent = requiredArtifacts.every((name) =>
    generated.includes(name),
  );
  const pathCarriesIdentity = Object.values(candidates)
    .filter((value): value is string => value !== undefined)
    .every(
      (candidate) => candidate.includes(runId) && candidate.includes(caseId),
    );

  return {
    exit_code: exitCode,
    exit_code_is_zero: exitCode === 0,
    failure_converted_to_success: junitRetainedFailure && exitCode === 0,
    artifacts_generated: generated,
    artifact_contains_run_id:
      allRequiredPresent &&
      pathCarriesIdentity &&
      junit.includes(runId) &&
      log.includes(runId),
    artifact_contains_case_id:
      allRequiredPresent &&
      pathCarriesIdentity &&
      junit.includes(caseId) &&
      log.includes(caseId),
    failure_retained:
      junitRetainedFailure && exitCode !== null && exitCode !== 0,
    auto_retried_to_pass:
      attemptFiles.length > 1 && junitRetainedFailure && exitCode === 0,
    attempt_count: attemptFiles.length,
    artifact_paths: artifactPaths,
  };
}

async function executeProbeProcess({
  artifactDirectory,
  caseId,
  mode,
  runId,
  sourceDirectory,
}: {
  artifactDirectory: string;
  caseId: string;
  mode: ProbeMode;
  runId: string;
  sourceDirectory: string;
}): Promise<{ exitCode: number | null; output: string }> {
  const cliPath = require.resolve('@playwright/test/cli');
  const configPath = path.join(sourceDirectory, 'probes/playwright.config.ts');
  const environment = { ...process.env };
  for (const name of Object.keys(environment)) {
    if (
      name.startsWith('PW_TEST_') ||
      name === 'TEST_PARALLEL_INDEX' ||
      name === 'TEST_WORKER_INDEX'
    ) {
      delete environment[name];
    }
  }
  Object.assign(environment, {
    CI: '1',
    PROBE_ARTIFACT_DIR: artifactDirectory,
    PROBE_CASE_ID: caseId,
    PROBE_MODE: mode,
    PROBE_RUN_ID: runId,
  });

  return new Promise((resolve) => {
    const child = spawn(
      process.execPath,
      [cliPath, 'test', '--config', configPath],
      {
        cwd: sourceDirectory,
        env: environment,
        stdio: ['ignore', 'pipe', 'pipe'],
      },
    );
    let output = '';
    child.stdout.on('data', (chunk: Buffer) => {
      output += chunk.toString('utf8');
    });
    child.stderr.on('data', (chunk: Buffer) => {
      output += chunk.toString('utf8');
    });
    child.on('error', (error) => {
      output += `\nprobe process error: ${String(error)}\n`;
    });
    child.on('close', (exitCode) => resolve({ exitCode, output }));
  });
}

export async function runFailureProbe({
  caseId,
  mode,
  requiredArtifacts,
  resultsDir,
  runId,
  sourceDirectory,
}: {
  caseId: string;
  mode: ProbeMode;
  requiredArtifacts?: readonly string[];
  resultsDir: string;
  runId: string;
  sourceDirectory: string;
}): Promise<FailureProbeResult> {
  if (!SAFE_RUN_ID.test(runId)) {
    throw new Error(`RUN_ID is not a safe artifact segment: ${runId}`);
  }
  if (!SAFE_CASE_ID.test(caseId)) {
    throw new Error(`Case ID is not a safe artifact segment: ${caseId}`);
  }
  const artifactDirectory = path.join(
    path.resolve(resultsDir),
    'execution-probe',
    runId,
    caseId,
  );
  await mkdir(path.dirname(artifactDirectory), { recursive: true });
  await mkdir(artifactDirectory);
  const processResult = await executeProbeProcess({
    artifactDirectory,
    caseId,
    mode,
    runId,
    sourceDirectory,
  });
  await writeFile(
    path.join(artifactDirectory, 'playwright.log'),
    `run_id=${runId} case_id=${caseId}\n${processResult.output}`,
    'utf8',
  );
  const result = await evaluateFailureProbe({
    artifactDirectory,
    caseId,
    exitCode: processResult.exitCode,
    requiredArtifacts,
    runId,
  });
  await writeFile(
    path.join(artifactDirectory, 'probe-result.json'),
    `${JSON.stringify(result, null, 2)}\n`,
    'utf8',
  );
  return result;
}
