import * as BlocklyModule from "blockly/core";
// Blockly publishes browser ESM and Node CJS under this same subpath.
const Blockly =
  "FieldDropdown" in BlocklyModule
    ? BlocklyModule
    : Reflect.get(BlocklyModule, "default");

const providers = new WeakMap();
const kinds = {
  "data.compose": "transform",
  "data.dataset_builtin": "dataset",
  "data.dataloader": "dataloader",
  "model.define": "model_class",
};
export const referenceKinds = {
  TRANSFORM_REF: ["transform", null],
  DATASET_REF: ["dataset", null],
  MODEL_REF: ["model_class", null],
  TRAIN_LOADER_REF: ["dataloader", "train"],
  TEST_LOADER_REF: ["dataloader", "test"],
};

export function symbolSnapshot(workspaces) {
  const nodes = new Map();
  for (const [workspace, instance] of Object.entries(workspaces)) {
    for (const block of instance.getTopBlocks(false)) {
      if (!kinds[block.type]) continue;
      if ((workspace === "model") !== (block.type === "model.define")) continue;
      if (workspace !== "data" && workspace !== "model") continue;
      nodes.set(block.id, { block, workspace });
    }
  }
  function role(block, seen = new Set()) {
    if (seen.has(block.id)) return null;
    if (block.type === "data.dataset_builtin") {
      const split = block.getFieldValue("SPLIT");
      return split === "train" || split === "test" ? split : null;
    }
    if (block.type === "data.dataloader") {
      const target = nodes.get(block.getFieldValue("DATASET_REF"))?.block;
      if (target?.type === "data.dataset_builtin")
        return role(target, new Set([...seen, block.id]));
    }
    return null;
  }
  return [...nodes.values()]
    .map(({ block, workspace }) => ({
      id: block.id,
      kind: kinds[block.type],
      name: String(block.getFieldValue("NAME") ?? ""),
      registered: block.isEnabled() && block.easyai?.registered === true,
      role: role(block),
      workspace,
    }))
    .sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
}

export function bindSymbolProvider(workspace, provider) {
  providers.set(workspace, provider);
  return () => providers.delete(workspace);
}

export function referenceStatus(value, kind, role, symbols) {
  if (!value)
    return {
      valid: false,
      label: "请选择对象",
      message: "请先选择要引用的对象。",
    };
  const found = symbols.find((entry) => entry.id === value);
  if (!found)
    return {
      valid: false,
      label: `⚠ 已删除对象 (${value.slice(0, 16)})`,
      message: "找不到原先选择的对象；恢复原积木或重新选择。",
    };
  if (!found.registered)
    return {
      valid: false,
      label: `⚠ ${found.name}（未注册）`,
      message: "原先选择的对象尚未供本项目引用。",
    };
  if (found.kind !== kind || (role && found.role !== role)) {
    return {
      valid: false,
      label: `⚠ ${found.name}（角色不符）`,
      message: "原先选择的对象类型或训练/测试角色不符。",
    };
  }
  return { valid: true, label: found.name, message: null };
}

export class FieldSymbolRef extends Blockly.FieldDropdown {
  constructor(kind, role = null) {
    let field;
    super(() => (field ? field.referenceOptions() : [["请选择对象", ""]]));
    field = this;
    this.symbolKind = kind;
    this.symbolRole = role;
  }
  symbols() {
    const workspace = this.getSourceBlock()?.workspace;
    return workspace ? (providers.get(workspace)?.() ?? []) : [];
  }
  status() {
    return referenceStatus(
      this.getValue(),
      this.symbolKind,
      this.symbolRole,
      this.symbols(),
    );
  }
  referenceOptions() {
    const options = [["请选择对象", ""]];
    for (const symbol of this.symbols()) {
      if (
        symbol.registered &&
        symbol.kind === this.symbolKind &&
        (!this.symbolRole || symbol.role === this.symbolRole)
      )
        options.push([symbol.name, symbol.id]);
    }
    const value = this.getValue();
    if (value && !options.some((option) => option[1] === value))
      options.push([this.status().label, value]);
    return options;
  }
  doClassValidation_(value) {
    // An unavailable ID is a tombstone, never permission to choose another object.
    return typeof value === "string" && value.length <= 256 ? value : null;
  }
  getText_() {
    return this.status().label;
  }
  refresh() {
    this.getOptions(false);
    this.forceRerender();
  }
}

export function refreshReferences(workspaces) {
  for (const workspace of Object.values(workspaces)) {
    for (const block of workspace.getAllBlocks(false)) {
      const messages = [];
      for (const input of block.inputList)
        for (const field of input.fieldRow) {
          if (field instanceof FieldSymbolRef) {
            field.refresh();
            const status = field.status();
            if (!status.valid) messages.push(status.message);
          }
        }
      block.setWarningText(
        messages.length ? [...new Set(messages)].join("\n") : null,
        "easyai-reference",
      );
    }
  }
}

export function setRegistration(block, registered) {
  if (!kinds[block.type] || typeof registered !== "boolean")
    throw new Error("此积木不能注册对象。");
  const previous = block.saveExtraState();
  if (previous.easyai.registered === registered) return;
  const next = { easyai: { version: 1, registered } };
  block.loadExtraState(next);
  if (Blockly.Events.isEnabled())
    Blockly.Events.fire(
      new Blockly.Events.BlockChange(
        block,
        "mutation",
        null,
        JSON.stringify(previous),
        JSON.stringify(next),
      ),
    );
}
