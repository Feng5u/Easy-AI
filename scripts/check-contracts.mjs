import { compileFromFile } from "json-schema-to-typescript";
import {
  readdir,
  readFile,
  writeFile,
  mkdir,
  mkdtemp,
  rm,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
const check = process.argv.includes("--check");
const directory = check
  ? await mkdtemp(join(tmpdir(), "easyai-contracts-"))
  : resolve("packages/contracts/schema");
try {
  const result = spawnSync(
    "uv",
    [
      "run",
      "--frozen",
      "--project",
      "services/backend",
      "python",
      "-m",
      "easyai.domain.export",
      directory,
    ],
    { stdio: "inherit", shell: false },
  );
  if (result.status !== 0) throw new Error("Schema generation failed");
  await mkdir("packages/contracts/src", { recursive: true });
  await mkdir("packages/contracts/types", { recursive: true });
  for (const file of (await readdir(directory)).sort()) {
    const schema = await readFile(join(directory, file), "utf8");
    const ts = await compileFromFile(join(directory, file), {
      bannerComment: "/* Generated from Pydantic. Do not edit. */",
      additionalProperties: false,
    });
    const tsPath = join("packages/contracts/src", file.replace(".json", ".ts"));
    const schemaPath = join("packages/contracts/schema", file);
    const declarationPath = join(
      "packages/contracts/types",
      file.replace(".json", ".d.ts"),
    );
    if (check) {
      if (
        (await readFile(schemaPath, "utf8")) !== schema ||
        (await readFile(tsPath, "utf8")) !== ts ||
        (await readFile(declarationPath, "utf8")) !== ts
      )
        throw new Error(`Contract drift: ${file}`);
    } else {
      await writeFile(tsPath, ts);
      await writeFile(declarationPath, ts);
    }
  }
} finally {
  if (check) await rm(directory, { recursive: true, force: true });
}
