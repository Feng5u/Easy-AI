import Blockly from "blockly/core";
import { mkdir, writeFile, readFile } from "node:fs/promises";
import manifest from "../packages/block-library/manifest.json" with { type: "json" };
import { registerBlocks } from "../packages/block-library/register.mjs";
registerBlocks();
const workspaceNames = ["data", "model", "training"];
function project() {
  return {
    schemaVersion: 1,
    appVersion: "0.0.0",
    blockLibraryVersion: "0.0.0",
    projectId: "d27ce785-6e51-4f50-a709-35de949c0d93",
    name: "MNIST 入门实验",
    revision: 1,
    workspaces: Object.fromEntries(
      workspaceNames.map((k) => [
        k,
        { blocks: { languageVersion: 0, blocks: [] } },
      ]),
    ),
    settings: { dataDirectory: "data", seed: 42, executionMode: "full" },
    ui: { activeTab: "data", codeVisible: false },
  };
}
function add(ws, type, id, fields = {}, registered = false) {
  const b = ws.newBlock(type, id);
  for (const [key, value] of Object.entries(fields))
    b.setFieldValue(String(value), key);
  b.easyai = { version: 1, registered };
  return b;
}
function connect(parent, input, children) {
  if (!children.length) return;
  parent.getInput(input).connection.connect(children[0].previousConnection);
  for (let i = 1; i < children.length; i++)
    children[i - 1].nextConnection.connect(children[i].previousConnection);
}
const doc = project();
const data = new Blockly.Workspace(),
  model = new Blockly.Workspace(),
  training = new Blockly.Workspace();
const compose = add(
  data,
  "data.compose",
  "transform",
  { NAME: "preprocess" },
  true,
);
connect(compose, "steps", [
  add(data, "data.to_tensor", "tensor"),
  add(data, "data.normalize", "normalize"),
]);
for (const split of ["train", "test"]) {
  add(
    data,
    "data.dataset_builtin",
    `${split}-dataset`,
    { NAME: `${split}_data`, SPLIT: split, TRANSFORM_REF: "transform" },
    true,
  );
  add(
    data,
    "data.dataloader",
    `${split}-loader`,
    {
      NAME: `${split}_batches`,
      DATASET_REF: `${split}-dataset`,
      SHUFFLE: split === "train" ? "TRUE" : "FALSE",
    },
    true,
  );
}
const cnn = add(model, "model.define", "cnn", { NAME: "MnistCNN" }, true);
const layerSpecs = [
  ["model.conv2d", { IN_CHANNELS: 1, OUT_CHANNELS: 16 }],
  ["model.relu", {}],
  ["model.maxpool2d", {}],
  ["model.conv2d", { IN_CHANNELS: 16, OUT_CHANNELS: 32 }],
  ["model.relu", {}],
  ["model.maxpool2d", {}],
  ["model.flatten", {}],
  ["model.linear", { IN_FEATURES: 1568, OUT_FEATURES: 128 }],
  ["model.relu", {}],
  ["model.linear", { IN_FEATURES: 128, OUT_FEATURES: 10 }],
];
connect(
  cnn,
  "body",
  layerSpecs.map(([type, fields], i) => add(model, type, `layer-${i}`, fields)),
);
add(training, "train.loop", "training", {
  MODEL_REF: "cnn",
  TRAIN_LOADER_REF: "train-loader",
  TEST_LOADER_REF: "test-loader",
});
for (const [key, ws] of [
  ["data", data],
  ["model", model],
  ["training", training],
])
  doc.workspaces[key] = Blockly.serialization.workspaces.save(ws);
await mkdir("packages/contracts/fixtures", { recursive: true });
await mkdir("examples/mnist-cnn", { recursive: true });
const save = async (path, value) => {
  const text = JSON.stringify(value, null, 2) + "\n";
  if (process.argv.includes("--check")) {
    if ((await readFile(path, "utf8")) !== text)
      throw new Error("Blockly fixture drift: " + path);
  } else await writeFile(path, text);
};
await save("packages/contracts/fixtures/blank.json", project());
await save("packages/contracts/fixtures/mnist.json", doc);
await save("examples/mnist-cnn/project.easyai.json", doc);
// Each declared type is actually created, saved, loaded and re-saved by frozen Blockly.
const all = new Blockly.Workspace();
for (const spec of manifest.blocks) add(all, spec.id, `fixture-${spec.id}`);
all
  .getBlockById("fixture-model.dropout")
  .setDisabledReason(true, "MANUALLY_DISABLED");
const state = Blockly.serialization.workspaces.save(all);
const reloaded = new Blockly.Workspace();
Blockly.serialization.workspaces.load(state, reloaded);
await save(
  "packages/contracts/fixtures/all-blocks.json",
  Blockly.serialization.workspaces.save(reloaded),
);
for (const ws of [all, reloaded, data, model, training]) ws.dispose();

const shadowWorkspace = new Blockly.Workspace();
const shadowRoot = add(
  shadowWorkspace,
  "model.define",
  "shadow-root",
  { NAME: "ShadowModel" },
  true,
);
const shadowLayer = add(shadowWorkspace, "model.relu", "shadow-layer");
shadowLayer.setShadow(true);
connect(shadowRoot, "body", [shadowLayer]);
await save(
  "packages/contracts/fixtures/shadow.json",
  Blockly.serialization.workspaces.save(shadowWorkspace),
);
shadowWorkspace.dispose();
