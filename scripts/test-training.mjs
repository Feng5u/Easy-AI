import { spawnSync } from "node:child_process";
if (
  !process.env.EASYAI_TRAINING_PYTHON ||
  !process.env.EASYAI_TRAINING_TEST_ROOT
) {
  throw new Error(
    "NOT RUN: select an authorized training Python and a new test root with EASYAI_TRAINING_PYTHON and EASYAI_TRAINING_TEST_ROOT. This command never installs dependencies.",
  );
}
const result = spawnSync(
  "uv",
  [
    "run",
    "--frozen",
    "pytest",
    "-q",
    "-s",
    "tests/test_training_integration.py",
  ],
  { cwd: "services/backend", stdio: "inherit", shell: false },
);
if (result.error) throw result.error;
process.exit(result.status ?? 1);
