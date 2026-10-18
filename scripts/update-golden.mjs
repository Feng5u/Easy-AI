// Deliberate source snapshot refresh. Never executes generated training code.
import { spawnSync } from "node:child_process";
const source = `
import json
from pathlib import Path
from easyai.compiler.pipeline import compile_project
from easyai.domain.contracts import ProjectDocument
root = Path.cwd().parents[1]
project = ProjectDocument.model_validate_json((root / 'packages/contracts/fixtures/mnist-figures.json').read_bytes())
compiled = compile_project(project)
assert compiled.result.runnable and compiled.program is not None
output = Path('tests/fixtures/golden')
output.mkdir(parents=True, exist_ok=True)
(output / 'mnist.py.txt').write_text(compiled.result.code, encoding='utf-8')
(output / 'mnist-program.json').write_text(compiled.program.model_dump_json(by_alias=True, indent=2) + '\\n', encoding='utf-8')
(output / 'mnist-source-map.json').write_text(json.dumps([span.model_dump(by_alias=True) for span in compiled.result.source_map], ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')
`;
const result = spawnSync("uv", ["run", "--frozen", "python", "-c", source], {
  cwd: "services/backend",
  stdio: "inherit",
  shell: false,
});
if (result.error) throw result.error;
process.exit(result.status ?? 1);
