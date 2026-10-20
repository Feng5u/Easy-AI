import dataset from "../../../tutorials/zh-CN/dataset-loader.md?raw";
import iterations from "../../../tutorials/zh-CN/batch-epoch.md?raw";
import convolution from "../../../tutorials/zh-CN/convolution.md?raw";
import metrics from "../../../tutorials/zh-CN/loss-accuracy.md?raw";
import modes from "../../../tutorials/zh-CN/train-test.md?raw";
import environments from "../../../tutorials/zh-CN/device-environment.md?raw";
import errors from "../../../tutorials/zh-CN/errors-output.md?raw";
import manifest from "../../../packages/block-library/manifest.json";
import type { ProjectDocument } from "../electron/bridge.js";
import type { WorkspaceTab } from "./editor-contract.js";
export const tutorials = [
  {
    id: "dataset",
    title: "Dataset 与 DataLoader",
    relevantBlockTypes: [
      "data.dataloader",
      "data.dataset_builtin",
      "data.compose",
      "data.to_tensor",
      "data.normalize",
    ],
    markdown: dataset,
  },
  {
    id: "iterations",
    title: "batch 与 epoch",
    relevantBlockTypes: ["data.dataloader", "train.loop"],
    markdown: iterations,
  },
  {
    id: "convolution",
    title: "卷积、池化与 Flatten",
    relevantBlockTypes: [
      "model.conv2d",
      "model.maxpool2d",
      "model.flatten",
      "model.linear",
      "model.relu",
      "model.sequential",
      "model.define",
    ],
    markdown: convolution,
  },
  {
    id: "metrics",
    title: "loss 与 accuracy",
    relevantBlockTypes: [
      "viz.data_source",
      "train.loop",
      "viz.figure",
      "viz.panel",
      "viz.axis",
      "viz.legend",
      "viz.title",
    ],
    markdown: metrics,
  },
  {
    id: "modes",
    title: "训练模式与测试模式",
    relevantBlockTypes: ["model.dropout", "train.loop"],
    markdown: modes,
  },
  {
    id: "environments",
    title: "设备与运行环境",
    relevantBlockTypes: ["train.loop"],
    markdown: environments,
  },
  {
    id: "errors",
    title: "如何阅读错误与输出",
    relevantBlockTypes: ["train.loop", "viz.savefig", "viz.figure"],
    markdown: errors,
  },
] as const;
export type TutorialId = (typeof tutorials)[number]["id"];
export interface TutorialTarget {
  id: string;
  type: string;
  workspace: WorkspaceTab;
  label: string;
}
export function tutorialForBlock(type: string) {
  const spec = manifest.blocks.find(
    (item) => item.id === type && item.helpKey === `blocks.${type}`,
  );
  return (
    spec &&
    tutorials.find((item) =>
      (item.relevantBlockTypes as readonly string[]).includes(type),
    )
  );
}
export function tutorialTargets(
  project: ProjectDocument,
  types: readonly string[],
): TutorialTarget[] {
  const targets: TutorialTarget[] = [],
    ids = new Set<string>();
  let visited = 0;
  for (const workspace of ["data", "model", "training"] as const) {
    const pending: unknown[] = [
      ...(project.workspaces[workspace]?.blocks.blocks ?? []),
    ];
    while (pending.length) {
      if (++visited > 500) return [];
      const raw = pending.pop();
      if (!raw || typeof raw !== "object" || Array.isArray(raw)) continue;
      const block = raw as Record<string, unknown>;
      if (
        typeof block.id !== "string" ||
        !block.id ||
        block.id.length > 256 ||
        ids.has(block.id)
      )
        return [];
      ids.add(block.id);
      if (block.next && typeof block.next === "object")
        pending.push((block.next as Record<string, unknown>).block);
      if (Array.isArray(block.disabledReasons) && block.disabledReasons.length)
        continue;
      const spec = manifest.blocks.find((item) => item.id === block.type);
      if (spec && types.includes(spec.id))
        targets.push({
          id: block.id,
          type: spec.id,
          workspace,
          label: spec.label,
        });
      if (block.inputs && typeof block.inputs === "object")
        for (const value of Object.values(block.inputs)) {
          if (value && typeof value === "object") {
            const entry = value as Record<string, unknown>;
            if (entry.block) pending.push(entry.block);
            else if (entry.shadow) pending.push(entry.shadow);
          }
        }
    }
  }
  return targets.sort(
    (a, b) =>
      types.indexOf(a.type) - types.indexOf(b.type) || a.id.localeCompare(b.id),
  );
}
