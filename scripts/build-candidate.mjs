// Same locked builder, bounded CI outputs. No publish, installer or signing.
import { appendFile, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { execFileSync } from "node:child_process";
import { packageBuilder, builderLayout } from "./package-builder.mjs";
import { hash } from "./package.mjs";

const candidate = await packageBuilder();
if (process.env.GITHUB_SHA && process.env.GITHUB_SHA !== candidate.sourceCommit)
  throw Error("CANDIDATE_CI_SOURCE_MISMATCH");
if (candidate.archive.bytes > 450 * 1024 * 1024)
  throw Error("CANDIDATE_ARCHIVE_SIZE_LIMIT");
const layout = builderLayout(process.platform, process.arch);
const files = [
  "pnpm-lock.yaml",
  "pnpm-workspace.yaml",
  "services/backend/uv.lock",
  "electron-builder.json",
];
const sourceFiles = {};
for (const file of files) sourceFiles[file] = await hash(file);
const manifest = JSON.parse(
  await readFile(join(candidate.output, "builder-manifest.json"), "utf8"),
);
await writeFile(
  join(candidate.output, "candidate-provenance.json"),
  JSON.stringify(
    {
      sourceCommit: candidate.sourceCommit,
      sourceTree: execFileSync("git", ["rev-parse", "HEAD^{tree}"], {
        encoding: "utf8",
      }).trim(),
      platform: process.platform,
      arch: process.arch,
      sourceFiles,
      vendorArchiveSha256: manifest.approvedInputs.vendorArchiveSha256,
      builderManifestSha256: await hash(
        join(candidate.output, "builder-manifest.json"),
      ),
      archive: candidate.archive,
      workflowRun: process.env.GITHUB_RUN_ID ?? null,
      distributionReady: false,
      legalReviewComplete: false,
      limitations: [
        "Unsigned local candidate; not a release",
        "No installer or signing",
        "Application runtime included; no training environment/data/models",
        "No clean-machine TST33, formal MNIST or real SSH acceptance",
        "Notices are retained; project/native/system legal review remains incomplete",
        "Full Windows verifier also requires the sealed input/vendor/electron.exe for independent PE integrity replay",
      ],
    },
    null,
    2,
  ) + "\n",
  { flag: "wx" },
);
if (process.env.GITHUB_OUTPUT) {
  const outputs = {
    directory: candidate.output,
    sha256: candidate.archive.sha256,
    bytes: String(candidate.archive.bytes),
    archive: join(candidate.output, "artifacts", candidate.archive.path),
    backend: join(
      candidate.output,
      "artifacts",
      layout.unpacked,
      "resources/backend",
    ),
    executable: join(
      candidate.output,
      "artifacts",
      layout.unpacked,
      layout.executable,
    ),
  };
  for (const [key, value] of Object.entries(outputs)) {
    if (/[\r\n]/.test(value)) throw Error("CANDIDATE_OUTPUT_INVALID");
    await appendFile(process.env.GITHUB_OUTPUT, `${key}=${value}\n`);
  }
}
console.log(candidate);
