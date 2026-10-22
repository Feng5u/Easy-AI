import { expect, it } from "vitest";
import * as Blockly from "blockly/core";
import { registerBlocks } from "./register.mjs";
import { readFile, mkdtemp, rm } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import type { ProjectDocument } from "../../apps/desktop/electron/bridge.js";
it("existing real viz fields cover type, sources and styles with grouped Undo and authoritative save/reopen compile", async () => {
  registerBlocks();
  const project = JSON.parse(
    await readFile(
      new URL("../contracts/fixtures/mnist-figures.json", import.meta.url),
      "utf8",
    ),
  ) as ProjectDocument;
  const spaces = Object.fromEntries(
    (["data", "model", "training"] as const).map((tab) => {
      const workspace = new Blockly.Workspace();
      Blockly.serialization.workspaces.load(project.workspaces[tab], workspace);
      return [tab, workspace];
    }),
  );
  const space = spaces.training;
  const root = await mkdtemp(join(tmpdir(), "easyai-viz-fields-"));
  try {
    await new Promise((r) => setTimeout(r, 20));
    space.clearUndo();
    const original = Blockly.serialization.workspaces.save(space);
    const group = Blockly.Events.getGroup();
    Blockly.Events.setGroup(true);
    try {
      for (const [id, field, value] of [
        ["body-0-panel", "CHART_TYPE", "scatter"],
        ["body-0-source", "SOURCE", "test_accuracy"],
        ["body-0-title", "TEXT", "课堂子图"],
        ["body-0-title", "COLOR", "blue"],
        ["body-0-axis", "SHOW_TICKS", "FALSE"],
      ])
        space.getBlockById(id)!.setFieldValue(value, field);
    } finally {
      Blockly.Events.setGroup(group);
    }
    await new Promise((r) => setTimeout(r, 20));
    expect(space.getBlockById("body-0-legend")).not.toBeNull();
    const changed = {
      ...project,
      workspaces: Object.fromEntries(
        Object.entries(spaces).map(([tab, workspace]) => [
          tab,
          { blocks: Blockly.serialization.workspaces.save(workspace).blocks },
        ]),
      ),
    };
    const backend = fileURLToPath(
      new URL("../../services/backend/", import.meta.url),
    );
    const code = `import json,sys\nfrom pathlib import Path\nfrom easyai.domain.contracts import ProjectDocument\nfrom easyai.services.project_service import ProjectService\nfrom easyai.compiler.pipeline import compile_project\np=ProjectDocument.model_validate_json(sys.stdin.read()); root=Path(sys.argv[1]); (root/'project.easyai.json').write_text(p.model_dump_json(by_alias=True)); s=ProjectService(root)\ntry: saved=s.save(p,p.revision)\nfinally: s.close()\ns=ProjectService(root)\ntry: reopened=s.snapshot(saved.revision).document\nfinally: s.close()\na=compile_project(p); b=compile_project(reopened); assert a.result.runnable and b.result.runnable; assert (a.result.code,a.result.code_hash,a.result.program_hash,a.result.source_map)==(b.result.code,b.result.code_hash,b.result.program_hash,b.result.source_map); assert 'ax.scatter' in b.result.code and '课堂子图' in b.result.code and \"color='blue'\" in b.result.code; panel=b.program.training.body[0].panels[0]; assert panel.chart_type=='scatter' and panel.sources[0].source=='test_accuracy' and panel.title.text=='课堂子图' and panel.title.color=='blue' and not panel.axis.show_ticks and panel.legend.block_id=='body-0-legend'; assert any(x.origin.block_id=='body-0-source' for x in b.result.source_map); assert p.workspaces==reopened.workspaces; print('PASS existing field semantics/save/reopen/compiler/source-map')`;
    const result = spawnSync(
      join(
        backend,
        process.platform === "win32"
          ? ".venv/Scripts/python.exe"
          : ".venv/bin/python",
      ),
      ["-c", code, root],
      {
        cwd: backend,
        input: JSON.stringify(changed),
        encoding: "utf8",
        timeout: 10000,
      },
    );
    expect(result.status, result.stderr).toBe(0);
    expect(result.stdout).toContain("PASS existing field semantics");
    space.undo(false);
    await new Promise((r) => setTimeout(r, 20));
    expect(Blockly.serialization.workspaces.save(space)).toEqual(original);
  } finally {
    Object.values(spaces).forEach((w) => w.dispose());
    await rm(root, { recursive: true, force: true });
  }
});
