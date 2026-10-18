import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, rm, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import {
  TUTORIAL_FILES,
  INPUT_GROUPS,
  validateTutorials,
  verifyInputs,
  stageInputs,
  treeRecords,
} from "./package-inputs.mjs";
async function fixture(t) {
  const root = await mkdtemp(join(tmpdir(), "easyai-approved-inputs-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const groups = {};
  for (const group of INPUT_GROUPS) {
    const dir = join(root, "payload", group);
    await mkdir(dir, { recursive: true });
    await writeFile(join(dir, "registered.dat"), `synthetic ${group}`);
    groups[group] = await treeRecords(dir);
  }
  const sourceCommit = "b".repeat(40);
  await writeFile(
    join(root, "approved-inputs.json"),
    JSON.stringify({
      schemaVersion: 1,
      origin: "exclusive-clean-build",
      sourceCommit,
      groups,
    }),
  );
  return { root, sourceCommit };
}
test("only seven explicit tutorial files are accepted; an ordinary extra file is rejected", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "easyai-tutorial-inputs-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  for (const name of TUTORIAL_FILES) {
    const file = join(root, "tutorials", name);
    await mkdir(dirname(file), { recursive: true });
    await writeFile(file, "synthetic tutorial");
  }
  await validateTutorials(root);
  await writeFile(
    join(root, "tutorials/zh-CN/extra-lesson.md"),
    "synthetic unapproved",
  );
  await assert.rejects(
    validateTutorials(root),
    /PACKAGE_TUTORIAL_INPUT_UNREGISTERED/,
  );
});
for (const group of INPUT_GROUPS)
  test(`sealed ${group} rejects an unregistered ordinary file without adopting it`, async (t) => {
    const { root, sourceCommit } = await fixture(t);
    await verifyInputs(root, sourceCommit);
    const receipt = await readFile(join(root, "approved-inputs.json"));
    await writeFile(
      join(root, "payload", group, "bonus-object.bin"),
      "synthetic unapproved",
    );
    await assert.rejects(
      stageInputs(root, join(root, "stage"), sourceCommit),
      /PACKAGE_INPUT_UNREGISTERED_OR_CHANGED/,
    );
    assert.deepEqual(
      await readFile(join(root, "approved-inputs.json")),
      receipt,
    );
    await assert.rejects(
      readFile(join(root, "stage/resources/app/registered.dat")),
      { code: "ENOENT" },
    );
  });
test("registered input mutation or deletion is refused; valid files copy exclusively", async (t) => {
  const { root, sourceCommit } = await fixture(t);
  const stage = join(root, "stage");
  await stageInputs(root, stage, sourceCommit);
  assert.deepEqual(
    await readFile(join(stage, "resources/backend/registered.dat")),
    await readFile(join(root, "payload/backend/registered.dat")),
  );
  await assert.rejects(stageInputs(root, stage, sourceCommit), {
    code: "EEXIST",
  });
  await writeFile(join(root, "payload/backend/registered.dat"), "altered");
  await assert.rejects(
    verifyInputs(root, sourceCommit),
    /PACKAGE_INPUT_UNREGISTERED_OR_CHANGED/,
  );
  await rm(join(root, "payload/backend/registered.dat"));
  await assert.rejects(
    verifyInputs(root, sourceCommit),
    /PACKAGE_INPUT_UNREGISTERED_OR_CHANGED/,
  );
});
