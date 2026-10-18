import * as fs from "node:fs/promises";
import { dirname, join } from "node:path";
import type { BigIntStats } from "node:fs";

function same(actual: BigIntStats, expected: BigIntStats): boolean {
  return (
    expected.ino !== 0n &&
    actual.dev === expected.dev &&
    actual.ino === expected.ino
  );
}

/** Publish complete bytes to an absent native target; never remove that target. */
export async function publishNewReport(
  destination: string,
  content: string,
  checkCurrent: () => void,
): Promise<void> {
  const directory = await fs.mkdtemp(
    join(dirname(destination), ".easyai-report-"),
  );
  const directoryIdentity = await fs.lstat(directory, { bigint: true });
  const staged = join(directory, "report.partial");
  let handle: fs.FileHandle | undefined;
  let identity: BigIntStats | undefined;
  try {
    handle = await fs.open(staged, "wx", 0o600);
    identity = await handle.stat({ bigint: true });
    await handle.writeFile(content, "utf8");
    await handle.sync();
    await handle.close();
    handle = undefined;
    const parent = await fs.lstat(directory, { bigint: true });
    const file = await fs.lstat(staged, { bigint: true });
    if (
      !parent.isDirectory() ||
      !same(parent, directoryIdentity) ||
      !file.isFile() ||
      !same(file, identity)
    )
      throw new Error("报告暂存身份已变化。");
    checkCurrent();
    // Same-directory filesystem, hard-link publication is exclusive and atomic.
    // No rename/copy fallback: unsupported filesystems must fail without a target.
    await fs.link(staged, destination);
  } finally {
    if (handle) await handle.close().catch(() => undefined);
    await cleanStaging(directory, staged, directoryIdentity, identity);
  }
}

async function cleanStaging(
  directory: string,
  staged: string,
  directoryIdentity: BigIntStats,
  identity: BigIntStats | undefined,
): Promise<void> {
  // Never clean the destination. Only recognize our private staging identities;
  // a replacement or unknown entry is retained, never recursively removed.
  try {
    const currentDirectory = await fs.lstat(directory, { bigint: true });
    if (
      !currentDirectory.isDirectory() ||
      !same(currentDirectory, directoryIdentity)
    )
      return;
    if (identity) {
      const current = await fs.lstat(staged, { bigint: true });
      if (!current.isFile() || !same(current, identity)) return;
      await fs.unlink(staged);
    }
    const current = await fs.lstat(directory, { bigint: true });
    if (current.isDirectory() && same(current, directoryIdentity))
      await fs.rmdir(directory);
  } catch {
    // Cleanup failure must neither undo publication nor hide a publication error.
  }
}
