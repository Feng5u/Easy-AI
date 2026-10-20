import { constants } from "node:fs";
import { open, lstat } from "node:fs/promises";

/** Only called with a path returned by Main's explicit native picker. */
export async function readSelectedPrivateKey(path: string): Promise<string> {
  let buffer: Buffer | undefined;
  const selected = await lstat(path);
  if (!selected.isFile() || selected.isSymbolicLink())
    throw new Error("SSH_PRIVATE_KEY_INVALID");
  const file = await open(
    path,
    constants.O_RDONLY |
      (constants.O_NOFOLLOW ?? 0) |
      (constants.O_NONBLOCK ?? 0),
  );
  try {
    const before = await file.stat();
    if (
      !before.isFile() ||
      before.dev !== selected.dev ||
      before.ino !== selected.ino ||
      before.size < 1 ||
      before.size > 65536
    )
      throw new Error("SSH_PRIVATE_KEY_INVALID");
    buffer = Buffer.alloc(65537);
    const { bytesRead } = await file.read(buffer, 0, buffer.length, 0);
    const after = await file.stat();
    if (
      bytesRead < 1 ||
      bytesRead > 65536 ||
      before.size !== bytesRead ||
      after.size !== before.size ||
      before.mtimeMs !== after.mtimeMs
    )
      throw new Error("SSH_PRIVATE_KEY_INVALID");
    const value = new TextDecoder("utf-8", { fatal: true }).decode(
      buffer.subarray(0, bytesRead),
    );
    if (
      !/^-----BEGIN (OPENSSH|RSA|EC) PRIVATE KEY-----\r?\n/.test(value) ||
      value.includes("\0")
    )
      throw new Error("SSH_PRIVATE_KEY_INVALID");
    return value;
  } finally {
    buffer?.fill(0);
    await file.close();
  }
}
