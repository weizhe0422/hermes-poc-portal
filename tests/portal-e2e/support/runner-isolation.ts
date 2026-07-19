import { constants, existsSync } from 'node:fs';
import { access, readFile } from 'node:fs/promises';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

export interface MountRecord {
  fileSystem: string;
  mountOptions: readonly string[];
  mountPoint: string;
  root: string;
  source: string;
}

export interface ClassifiedRunnerMounts {
  has_docker_socket_mount: boolean;
  has_formal_volume: boolean;
  has_knowledge_mount: boolean;
  has_skill_mount: boolean;
  has_writable_source_mount: boolean;
  results_volume_is_independent: boolean;
  unexpected_application_mounts: string[];
}

interface ClassifyRunnerMountsOptions {
  mounts: readonly MountRecord[];
  resultsDir: string;
  sourceDir: string;
  sourceDirectoryWritable: boolean;
  specificationRoot?: string;
}

export interface RunnerIsolationObservation {
  artifact: {
    written_to_independent_volume: boolean;
  };
  diagnostic: {
    results_volume_is_independent: boolean;
    unexpected_application_mounts: string[];
  };
  execution: {
    runner_has_git_metadata: boolean;
    runner_has_writable_source: boolean;
  };
  security: {
    can_access_git_metadata: boolean;
    has_docker_socket: boolean;
    has_formal_volume: boolean;
    has_knowledge_mount: boolean;
    has_skill_mount: boolean;
    has_writable_source_mount: boolean;
  };
}

function decodeMountPath(value: string): string {
  return value.replace(/\\(040|011|012|134)/g, (_, code: string) => {
    const decoded: Record<string, string> = {
      '011': '\t',
      '012': '\n',
      '040': ' ',
      '134': '\\',
    };
    return decoded[code];
  });
}

export function parseMountInfo(contents: string): MountRecord[] {
  const mounts: MountRecord[] = [];
  for (const line of contents.split('\n')) {
    if (line.trim() === '') {
      continue;
    }
    const separator = line.indexOf(' - ');
    if (separator < 0) {
      throw new Error('Malformed /proc/self/mountinfo line: missing separator');
    }
    const before = line.slice(0, separator).split(' ');
    const after = line.slice(separator + 3).split(' ');
    if (before.length < 6 || after.length < 3) {
      throw new Error('Malformed /proc/self/mountinfo line: missing fields');
    }
    mounts.push({
      root: decodeMountPath(before[3]),
      mountPoint: decodeMountPath(before[4]),
      mountOptions: before[5].split(','),
      fileSystem: after[0],
      source: decodeMountPath(after[1]),
    });
  }
  return mounts;
}

function isWithin(candidate: string, root: string): boolean {
  const normalizedCandidate = path.posix.resolve(candidate);
  const normalizedRoot = path.posix.resolve(root);
  return (
    normalizedCandidate === normalizedRoot ||
    normalizedCandidate.startsWith(`${normalizedRoot}/`)
  );
}

function isSystemMount(mountPoint: string): boolean {
  return (
    ['/proc', '/sys', '/dev'].some((root) => isWithin(mountPoint, root)) ||
    ['/etc/hostname', '/etc/hosts', '/etc/resolv.conf'].includes(mountPoint)
  );
}

function deepestMountForPath(
  mounts: readonly MountRecord[],
  candidate: string,
): MountRecord | undefined {
  return mounts
    .filter((mount) => isWithin(candidate, mount.mountPoint))
    .sort((left, right) => right.mountPoint.length - left.mountPoint.length)[0];
}

export function classifyRunnerMounts({
  mounts,
  resultsDir,
  sourceDir,
  sourceDirectoryWritable,
  specificationRoot = '/spec',
}: ClassifyRunnerMountsOptions): ClassifiedRunnerMounts {
  const normalizedResults = path.posix.resolve(resultsDir);
  const normalizedSource = path.posix.resolve(sourceDir);
  const normalizedSpec = path.posix.resolve(specificationRoot);
  const resultsMount = deepestMountForPath(mounts, normalizedResults);
  const resultsVolumeIsIndependent =
    resultsMount !== undefined &&
    resultsMount.mountPoint !== '/' &&
    resultsMount.mountOptions.includes('rw');

  const unexpected = mounts.filter((mount) => {
    if (mount.mountPoint === '/' || isSystemMount(mount.mountPoint)) {
      return false;
    }
    if (mount.mountPoint === normalizedSpec) {
      return false;
    }
    if (
      resultsMount !== undefined &&
      mount.mountPoint === resultsMount.mountPoint
    ) {
      return false;
    }
    return true;
  });
  const unexpectedApplicationMounts = unexpected
    .map(({ mountPoint }) => mountPoint)
    .sort();
  const searchableMountValues = unexpected.map(
    ({ mountPoint, root, source }) => `${mountPoint}\n${root}\n${source}`.toLowerCase(),
  );
  const writableSourceMount = mounts.some(
    (mount) =>
      mount.mountPoint !== '/' &&
      mount.mountOptions.includes('rw') &&
      (isWithin(normalizedSource, mount.mountPoint) ||
        isWithin(mount.mountPoint, normalizedSource)),
  );

  return {
    has_docker_socket_mount: unexpected.some(
      ({ mountPoint, source }) =>
        /(^|\/)docker\.sock$/.test(mountPoint) ||
        /(^|\/)docker\.sock$/.test(source),
    ),
    has_formal_volume: unexpected.length > 0,
    has_knowledge_mount: searchableMountValues.some((value) =>
      /knowledge|control-wafer/.test(value),
    ),
    has_skill_mount: searchableMountValues.some((value) => /skill/.test(value)),
    has_writable_source_mount:
      sourceDirectoryWritable || writableSourceMount,
    results_volume_is_independent: resultsVolumeIsIndependent,
    unexpected_application_mounts: unexpectedApplicationMounts,
  };
}

async function isWritable(directory: string): Promise<boolean> {
  try {
    await access(directory, constants.W_OK);
    return true;
  } catch {
    return false;
  }
}

function hasVisibleGitMetadata(sourceDir: string, mounts: readonly MountRecord[]): boolean {
  if (process.env.GIT_DIR || process.env.GIT_WORK_TREE) {
    return true;
  }
  let candidate = path.resolve(sourceDir);
  while (true) {
    if (existsSync(path.join(candidate, '.git'))) {
      return true;
    }
    const parent = path.dirname(candidate);
    if (parent === candidate) {
      break;
    }
    candidate = parent;
  }
  if (
    mounts.some(
      ({ mountPoint }) =>
        mountPoint.endsWith('/.git') || mountPoint.includes('/.git/'),
    )
  ) {
    return true;
  }
  const gitProbe = spawnSync('git', ['rev-parse', '--git-dir'], {
    cwd: sourceDir,
    encoding: 'utf8',
    stdio: 'ignore',
  });
  return gitProbe.status === 0;
}

export async function inspectRunnerIsolation({
  resultsDir,
  sourceDir,
  specificationRoot,
}: {
  resultsDir: string;
  sourceDir: string;
  specificationRoot: string;
}): Promise<RunnerIsolationObservation> {
  const mounts = parseMountInfo(await readFile('/proc/self/mountinfo', 'utf8'));
  const mountClassification = classifyRunnerMounts({
    mounts,
    resultsDir,
    sourceDir,
    sourceDirectoryWritable: await isWritable(sourceDir),
    specificationRoot,
  });
  const dockerEndpointConfigured = Boolean(process.env.DOCKER_HOST?.trim());
  const dockerSocketVisible = [
    '/var/run/docker.sock',
    '/run/docker.sock',
  ].some((candidate) => existsSync(candidate));
  const gitMetadataVisible = hasVisibleGitMetadata(sourceDir, mounts);

  return {
    security: {
      has_docker_socket:
        mountClassification.has_docker_socket_mount ||
        dockerEndpointConfigured ||
        dockerSocketVisible,
      has_knowledge_mount: mountClassification.has_knowledge_mount,
      has_skill_mount: mountClassification.has_skill_mount,
      has_formal_volume: mountClassification.has_formal_volume,
      has_writable_source_mount:
        mountClassification.has_writable_source_mount,
      can_access_git_metadata: gitMetadataVisible,
    },
    execution: {
      runner_has_git_metadata: gitMetadataVisible,
      runner_has_writable_source:
        mountClassification.has_writable_source_mount,
    },
    artifact: {
      written_to_independent_volume:
        mountClassification.results_volume_is_independent,
    },
    diagnostic: {
      results_volume_is_independent:
        mountClassification.results_volume_is_independent,
      unexpected_application_mounts:
        mountClassification.unexpected_application_mounts,
    },
  };
}
