import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  classifyRunnerMounts,
  parseMountInfo,
} from '../support/runner-isolation';

const isolatedMountInfo = [
  '19 1 0:1 / / rw,relatime - overlay overlay rw',
  '20 19 0:2 / /proc rw,nosuid,nodev,noexec,relatime - proc proc rw',
  '21 19 0:3 / /dev rw,nosuid - tmpfs tmpfs rw',
  '22 19 0:4 / /sys ro,nosuid,nodev,noexec,relatime - sysfs sysfs ro',
  '23 19 8:1 /spec /spec ro,relatime - ext4 /dev/root ro',
  '24 19 8:1 /results /test-results/run rw,relatime - ext4 /dev/root rw',
  '25 19 8:1 /etc/hosts /etc/hosts rw,relatime - ext4 /dev/root rw',
  '',
].join('\n');

test('mount classifier accepts only read-only spec and independent results mounts', () => {
  const mounts = parseMountInfo(isolatedMountInfo);
  const result = classifyRunnerMounts({
    mounts,
    resultsDir: '/test-results/run/portal-e2e',
    sourceDir: '/opt/hermes/portal-e2e',
    sourceDirectoryWritable: false,
  });

  assert.deepEqual(result, {
    has_docker_socket_mount: false,
    has_formal_volume: false,
    has_knowledge_mount: false,
    has_skill_mount: false,
    has_writable_source_mount: false,
    results_volume_is_independent: true,
    unexpected_application_mounts: [],
  });
});

test('mount classifier detects forbidden assets without treating values as Expected', () => {
  const mounts = parseMountInfo(
    isolatedMountInfo +
      [
        '30 19 8:1 /assets /knowledge rw,relatime - ext4 /dev/root rw',
        '31 19 8:1 /socket /var/run/docker.sock rw,relatime - ext4 /dev/root rw',
        '32 19 8:1 /source /opt/hermes/portal-e2e rw,relatime - ext4 /dev/root rw',
        '',
      ].join('\n'),
  );
  const result = classifyRunnerMounts({
    mounts,
    resultsDir: '/test-results/run/portal-e2e',
    sourceDir: '/opt/hermes/portal-e2e',
    sourceDirectoryWritable: false,
  });

  assert.equal(result.has_docker_socket_mount, true);
  assert.equal(result.has_formal_volume, true);
  assert.equal(result.has_knowledge_mount, true);
  assert.equal(result.has_skill_mount, false);
  assert.equal(result.has_writable_source_mount, true);
  assert.deepEqual(result.unexpected_application_mounts, [
    '/knowledge',
    '/opt/hermes/portal-e2e',
    '/var/run/docker.sock',
  ]);
});

test('mount parser decodes escaped path characters', () => {
  const [mount] = parseMountInfo(
    '41 19 8:1 /source\\040tree /opt/source\\040tree ro - ext4 /dev/root ro\n',
  );
  assert.equal(mount.mountPoint, '/opt/source tree');
  assert.equal(mount.root, '/source tree');
});
