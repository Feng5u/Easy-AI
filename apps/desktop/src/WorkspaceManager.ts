import * as Blockly from "blockly/core";
import manifest from "../../../packages/block-library/manifest.json";
import { registerBlocks } from "../../../packages/block-library/register.mjs";
import {
  bindSymbolProvider,
  refreshReferences,
  setRegistration,
  symbolSnapshot,
  type SymbolRecord,
} from "../../../packages/block-library/symbols.mjs";
import type { ProjectDocument } from "../electron/bridge.js";
import type { WorkspaceTab } from "./editor-contract.js";

export const workspaceTabs = ["data", "model", "training"] as const;
type Workspaces = ProjectDocument["workspaces"];
type JsonObject = Record<string, unknown>;
interface FieldSpec {
  type: string;
  default: string | number | boolean;
  options?: string[];
  min?: number;
  max?: number;
  maxLength?: number;
  exclusiveMin?: boolean;
  exclusiveMax?: boolean;
}
interface BlockSpec {
  id: string;
  category: string;
  placement: string;
  fields: Record<string, FieldSpec | undefined>;
  inputs: Record<string, string[] | undefined>;
}
const catalog: Record<string, BlockSpec> = Object.fromEntries(
  manifest.blocks.map((spec) => [spec.id, spec]),
);

export const figureLayouts = catalog["viz.figure"].fields.LAYOUT?.options ?? [];
export const figureSizes = catalog["viz.figure"].fields.SIZE?.options ?? [];
export interface FigureView {
  id: string;
  layout: string;
  size: string;
  rows: number;
  columns: number;
  disabled: boolean;
  panels: { id: string; chartType: string; disabled: boolean }[];
}

function object(value: unknown): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
export function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (object(value))
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`)
      .join(",")}}`;
  return JSON.stringify(value);
}

/** Structural preservation gate only; Python remains the semantic authority. */
export function validateWorkspaces(
  value: unknown,
): asserts value is Workspaces {
  if (
    !object(value) ||
    Object.keys(value).sort().join(",") !== "data,model,training"
  )
    throw new Error("工程需要完整的三个工作区。原文件未更改。");
  if (JSON.stringify(value).length > 5 * 1024 * 1024)
    throw new Error("工程过大，无法安全载入。");
  const ids = new Set<string>();
  const allowed = new Set([
    "type",
    "id",
    "x",
    "y",
    "extraState",
    "fields",
    "inputs",
    "next",
    "disabledReasons",
    "collapsed",
    "inline",
    "data",
    "editable",
    "deletable",
    "movable",
  ]);
  function visit(
    raw: unknown,
    depth: number,
    parent?: BlockSpec,
    slot?: string,
  ): void {
    if (!object(raw) || Object.keys(raw).some((key) => !allowed.has(key)))
      throw new Error("积木格式包含不支持的字段，未载入或覆盖原件。");
    if (typeof raw.type !== "string" || !catalog[raw.type])
      throw new Error(
        `发现未知积木 ${String(raw.type)}；原始内容已保留，未载入。`,
      );
    const spec = catalog[raw.type];
    if (
      typeof raw.id !== "string" ||
      !raw.id ||
      raw.id.length > 256 ||
      ids.has(raw.id)
    )
      throw new Error("积木ID重复或无效。");
    ids.add(raw.id);
    if (ids.size > 500 || depth > 64)
      throw new Error("积木数量或嵌套超过安全限制。");
    if (parent && slot && !parent.inputs[slot]?.includes(raw.type))
      throw new Error("积木连接格式不受支持；原内容未更改。");
    for (const key of ["x", "y"])
      if (
        raw[key] !== undefined &&
        (typeof raw[key] !== "number" || !Number.isFinite(raw[key]))
      )
        throw new Error("积木坐标格式无效。");
    if (
      raw.disabledReasons !== undefined &&
      (!Array.isArray(raw.disabledReasons) ||
        raw.disabledReasons.some((reason) => typeof reason !== "string"))
    )
      throw new Error("积木停用状态无效。");
    for (const key of [
      "collapsed",
      "inline",
      "editable",
      "deletable",
      "movable",
    ])
      if (raw[key] !== undefined && typeof raw[key] !== "boolean")
        throw new Error("积木显示状态无效。");
    if (raw.data !== undefined && typeof raw.data !== "string")
      throw new Error("积木附加数据格式无效。");
    if (raw.extraState !== undefined) {
      const state = raw.extraState;
      if (
        !object(state) ||
        Object.keys(state).join(",") !== "easyai" ||
        !object(state.easyai) ||
        Object.keys(state.easyai).sort().join(",") !== "registered,version" ||
        state.easyai.version !== 1 ||
        typeof state.easyai.registered !== "boolean"
      )
        throw new Error("积木版本或注册状态不受支持。");
    }
    const fields = raw.fields ?? {};
    if (!object(fields) || Object.keys(fields).some((key) => !spec.fields[key]))
      throw new Error("积木参数包含未知字段。");
    for (const [key, item] of Object.entries(fields)) {
      const rule = spec.fields[key];
      if (!rule) throw new Error("积木参数包含未知字段。");
      let valid = true;
      if (rule.type === "number" || rule.type === "integer") {
        valid =
          typeof item === "number" &&
          Number.isFinite(item) &&
          (rule.type !== "integer" || Number.isInteger(item));
        if (valid && typeof item === "number")
          valid =
            item >= (rule.min ?? -Infinity) &&
            item <= (rule.max ?? Infinity) &&
            !(rule.exclusiveMin && item === rule.min) &&
            !(rule.exclusiveMax && item === rule.max);
      } else if (rule.type === "enum")
        valid =
          typeof item === "string" && Boolean(rule.options?.includes(item));
      else if (rule.type === "boolean")
        valid =
          typeof item === "boolean" || item === "TRUE" || item === "FALSE";
      else
        valid =
          typeof item === "string" && item.length <= (rule.maxLength ?? 256);
      if (!valid)
        throw new Error(`参数 ${key} 无法无损载入，请查看工程检查说明。`);
    }
    const inputs = raw.inputs ?? {};
    if (!object(inputs) || Object.keys(inputs).some((key) => !spec.inputs[key]))
      throw new Error("积木包含未知连接槽。");
    for (const [key, connection] of Object.entries(inputs)) {
      if (
        !object(connection) ||
        !Object.keys(connection).length ||
        Object.keys(connection).some(
          (key) => key !== "block" && key !== "shadow",
        )
      )
        throw new Error("积木连接格式无效。");
      for (const child of Object.values(connection))
        visit(child, depth + 1, spec, key);
    }
    if (raw.next !== undefined) {
      if (
        spec.placement.endsWith("_root") ||
        !object(raw.next) ||
        Object.keys(raw.next).join(",") !== "block"
      )
        throw new Error("根积木或顺序连接格式无效。");
      if (
        !object(raw.next.block) ||
        typeof raw.next.block.type !== "string" ||
        catalog[raw.next.block.type]?.placement !== spec.placement
      )
        throw new Error("积木顺序连接类型不受支持；原内容未更改。");
      visit(raw.next.block, depth);
    }
  }
  for (const tab of workspaceTabs) {
    const workspace = value[tab];
    if (
      !object(workspace) ||
      Object.keys(workspace).join(",") !== "blocks" ||
      !object(workspace.blocks) ||
      Object.keys(workspace.blocks).some(
        (key) => key !== "languageVersion" && key !== "blocks",
      ) ||
      (workspace.blocks.languageVersion ?? 0) !== 0 ||
      !Array.isArray(workspace.blocks.blocks ?? [])
    )
      throw new Error("工作区保存格式不受支持。");
    for (const root of (workspace.blocks.blocks ?? []) as unknown[])
      visit(root, 1);
  }
}

export function toolboxFor(
  tab: WorkspaceTab,
): Blockly.utils.toolbox.ToolboxDefinition {
  const categories =
    tab === "data" ? ["data"] : tab === "model" ? ["model"] : ["train", "viz"];
  return {
    kind: "categoryToolbox",
    contents: categories.map((category) => ({
      kind: "category",
      name: {
        data: "数据处理",
        model: "模型结构",
        train: "训练管线",
        viz: "图表",
      }[category],
      colour: { data: "160", model: "220", train: "30", viz: "290" }[category],
      contents: manifest.blocks
        .filter((block) => block.category === category)
        .map((block) => ({ kind: "block", type: block.id })),
    })),
  };
}

export interface WorkspaceHandle {
  workspace: Blockly.Workspace;
  resize(): void;
  setVisible(visible: boolean): void;
  setReadOnly(readOnly: boolean): void;
  select(blockId: string | null): void;
  dispose(): void;
}
export type WorkspaceFactory = (
  host: HTMLElement,
  tab: WorkspaceTab,
  readOnly: boolean,
) => WorkspaceHandle;
export const browserWorkspaceFactory: WorkspaceFactory = (
  host,
  tab,
  readOnly,
) => {
  const workspace = Blockly.inject(host, {
    // Build the complete canvas once. Readonly is a live interaction gate,
    // not a reason to omit the toolbox that may later become available.
    toolbox: toolboxFor(tab),
    readOnly: false,
    sounds: false,
    trashcan: false,
    comments: false,
    css: true,
    media: "assets/",
    renderer: "geras",
    move: { scrollbars: true, drag: true, wheel: true },
    zoom: {
      controls: true,
      wheel: false,
      startScale: 0.8,
      minScale: 0.3,
      maxScale: 1.5,
    },
  });
  const setReadOnly = (value: boolean) => {
    workspace.options.readOnly = value;
    workspace.getToolbox()?.setVisible(!value);
    for (const block of workspace.getAllBlocks(false))
      for (const input of block.inputList) {
        for (const field of input.fieldRow) field.updateEditable();
      }
  };
  setReadOnly(readOnly);
  return {
    workspace,
    resize: () => Blockly.svgResize(workspace),
    setVisible: (visible) => workspace.setVisible(visible),
    setReadOnly,
    select: (id) => {
      workspace.highlightBlock(id);
      if (id) {
        if (!workspace.options.readOnly)
          (workspace.getBlockById(id) as Blockly.BlockSvg | null)?.select();
        workspace.centerOnBlock(id);
      }
    },
    dispose: () => workspace.dispose(),
  };
};

export interface ManagerCallbacks {
  onChange(workspaces: Workspaces): void;
  onSelect(id: string | null): void;
  onTabChange(tab: WorkspaceTab): void;
  onRefresh(): void;
}

export class WorkspaceManager {
  private handles: Record<WorkspaceTab, WorkspaceHandle>;
  private listeners: [
    Blockly.Workspace,
    (event: Blockly.Events.Abstract) => void,
  ][] = [];
  private unbind: (() => void)[] = [];
  private seenIds = new Set<string>();
  private currentSignature = "";
  private inputSignature = "";
  private suppressed = false;
  private blocked = false;
  private disposed = false;
  private readOnly: boolean;
  private active: WorkspaceTab = "data";
  constructor(
    hosts: Record<WorkspaceTab, HTMLElement>,
    readOnly: boolean,
    private callbacks: ManagerCallbacks,
    factory: WorkspaceFactory = browserWorkspaceFactory,
  ) {
    registerBlocks();
    this.readOnly = readOnly;
    const handles: Partial<Record<WorkspaceTab, WorkspaceHandle>> = {};
    try {
      for (const tab of workspaceTabs)
        handles[tab] = factory(hosts[tab], tab, readOnly);
    } catch (error) {
      Object.values(handles).forEach((handle) => handle.dispose());
      throw error;
    }
    this.handles = handles as Record<WorkspaceTab, WorkspaceHandle>;
    for (const tab of workspaceTabs) {
      const workspace = this.handles[tab].workspace;
      this.unbind.push(bindSymbolProvider(workspace, () => this.symbols()));
      const listener = (event: Blockly.Events.Abstract) => this.changed(event);
      workspace.addChangeListener(listener);
      this.listeners.push([workspace, listener]);
    }
  }
  get workspaces(): Record<WorkspaceTab, Blockly.Workspace> {
    return Object.fromEntries(
      workspaceTabs.map((tab) => [tab, this.handles[tab].workspace]),
    ) as Record<WorkspaceTab, Blockly.Workspace>;
  }
  symbols(): SymbolRecord[] {
    return symbolSnapshot(this.workspaces);
  }
  block(id: string): Blockly.Block | null {
    for (const workspace of Object.values(this.workspaces)) {
      const block = workspace.getBlockById(id);
      if (block) return block;
    }
    return null;
  }
  serialize(): Workspaces {
    const capture = (tab: WorkspaceTab): Workspaces[WorkspaceTab] => {
      const snapshot = Blockly.serialization.workspaces.save(
        this.handles[tab].workspace,
      );
      return { blocks: snapshot.blocks ?? { languageVersion: 0, blocks: [] } };
    };
    return {
      data: capture("data"),
      model: capture("model"),
      training: capture("training"),
    };
  }
  receive(value: Workspaces): void {
    if (this.disposed) return;
    const signature = canonical(value);
    if (
      signature === this.inputSignature ||
      signature === this.currentSignature
    ) {
      this.inputSignature = signature;
      this.blocked = false;
      return;
    }
    try {
      validateWorkspaces(value);
    } catch (error) {
      this.blocked = true;
      throw error;
    }
    this.suppressed = true;
    Blockly.Events.disable();
    const trial = workspaceTabs.map(() => new Blockly.Workspace());
    try {
      // Exercise the real loader before replacing any visible canvas.
      workspaceTabs.forEach((tab, index) =>
        Blockly.serialization.workspaces.load(value[tab], trial[index]),
      );
      for (const tab of workspaceTabs) {
        const workspace = this.handles[tab].workspace;
        Blockly.serialization.workspaces.load(value[tab], workspace);
        workspace.clearUndo();
      }
      this.blocked = false;
      this.seenIds = new Set(
        Object.values(this.workspaces).flatMap((workspace) =>
          workspace.getAllBlocks(false).map((block) => block.id),
        ),
      );
      this.inputSignature = signature;
      this.currentSignature = canonical(this.serialize());
      refreshReferences(this.workspaces);
      this.callbacks.onRefresh();
    } catch (error) {
      this.blocked = true;
      throw error;
    } finally {
      trial.forEach((workspace) => workspace.dispose());
      Blockly.Events.enable();
      this.suppressed = false;
    }
  }
  private changed(event: Blockly.Events.Abstract): void {
    if (this.disposed || this.suppressed || this.blocked) return;
    if (event.type === Blockly.Events.SELECTED) {
      this.callbacks.onSelect(
        (event as Blockly.Events.Selected).newElementId ?? null,
      );
      this.callbacks.onRefresh();
      return;
    }
    if (event.isUiEvent) return;
    const group = Blockly.Events.getGroup();
    Blockly.Events.setGroup(event.group || true);
    try {
      for (const workspace of Object.values(this.workspaces))
        for (const block of workspace.getAllBlocks(false)) {
          if (this.seenIds.has(block.id)) continue;
          this.seenIds.add(block.id);
          const entry = this.symbols().find((symbol) => symbol.id === block.id);
          if (entry && block.saveExtraState?.()?.easyai?.registered === true) {
            setRegistration(block, false);
            const names = new Set(
              this.symbols()
                .filter((symbol) => symbol.id !== block.id)
                .map((symbol) => symbol.name),
            );
            let suffix = 1;
            let name = entry.name;
            while (names.has(name))
              name = `${entry.name.slice(0, 54)}_copy${suffix++}`;
            block.setFieldValue(name, "NAME");
          }
        }
    } finally {
      Blockly.Events.setGroup(group);
    }
    refreshReferences(this.workspaces);
    const value = this.serialize();
    const signature = canonical(value);
    if (signature !== this.currentSignature) {
      this.currentSignature = signature;
      if (!this.readOnly) this.callbacks.onChange(value);
    }
    this.callbacks.onRefresh();
  }
  setActive(tab: WorkspaceTab): void {
    if (this.disposed) return;
    this.active = tab;
    for (const current of workspaceTabs)
      this.handles[current].setVisible(current === tab);
    this.resize();
  }
  resize(): void {
    if (!this.disposed) this.handles[this.active].resize();
  }
  setReadOnly(value: boolean): void {
    this.readOnly = value;
    for (const handle of Object.values(this.handles)) handle.setReadOnly(value);
  }
  select(id: string | null): void {
    if (!id) {
      for (const handle of Object.values(this.handles)) handle.select(null);
      return;
    }
    for (const tab of workspaceTabs)
      if (this.handles[tab].workspace.getBlockById(id)) {
        if (tab !== this.active) this.callbacks.onTabChange(tab);
        this.handles[tab].select(id);
        return;
      }
  }
  figure(id: string): FigureView | null {
    if (this.disposed || this.blocked) return null;
    let block = this.block(id);
    const ancestors = new Set<string>();
    while (block && block.type !== "viz.figure") {
      if (ancestors.has(block.id) || ancestors.size >= 500) return null;
      ancestors.add(block.id);
      block = block.getParent();
    }
    if (!block) return null;
    const layout = String(block.getFieldValue("LAYOUT"));
    const size = String(block.getFieldValue("SIZE"));
    if (!figureLayouts.includes(layout) || !figureSizes.includes(size))
      return null;
    const [rows, columns] = layout.split(",").map(Number);
    const panels: FigureView["panels"] = [];
    const seen = new Set<string>();
    let panel = block.getInputTargetBlock("panels");
    while (panel) {
      if (panel.type !== "viz.panel" || seen.has(panel.id) || seen.size >= 500)
        return null;
      seen.add(panel.id);
      panels.push({
        id: panel.id,
        chartType: String(panel.getFieldValue("CHART_TYPE")),
        disabled: !panel.isEnabled(),
      });
      panel = panel.getNextBlock();
    }
    let container: Blockly.Block | null = block;
    let disabled = false;
    const surrounding = new Set<string>();
    while (container) {
      if (surrounding.has(container.id) || surrounding.size >= 500) return null;
      surrounding.add(container.id);
      disabled ||= !container.isEnabled();
      container = container.getSurroundParent();
    }
    return { id: block.id, layout, size, rows, columns, disabled, panels };
  }
  configureFigure(id: string, layout: string, size: string): void {
    if (this.disposed || this.readOnly || this.blocked) return;
    const block = this.block(id);
    const figure = this.figure(id);
    if (!block || block.type !== "viz.figure" || !figure)
      throw new Error("画布结构不可安全编辑，请检查积木连接。");
    if (!figureLayouts.includes(layout) || !figureSizes.includes(size))
      throw new Error("请选择支持的画布布局和尺寸。");
    const capacity = layout
      .split(",")
      .map(Number)
      .reduce((rows, columns) => rows * columns);
    if (layout !== figure.layout && figure.panels.length > capacity)
      throw new Error(
        `此布局只有 ${capacity} 个格子，已连接 ${figure.panels.length} 个子图（含停用块）。请选择更大布局；所有积木已保留。`,
      );
    const tab = workspaceTabs.find(
      (value) => this.handles[value].workspace === block.workspace,
    );
    if (tab && tab !== this.active) {
      this.setActive(tab);
      this.callbacks.onTabChange(tab);
    }
    const group = Blockly.Events.getGroup();
    Blockly.Events.setGroup(group || true);
    try {
      block.setFieldValue(layout, "LAYOUT");
      block.setFieldValue(size, "SIZE");
    } finally {
      Blockly.Events.setGroup(group);
    }
  }
  rename(id: string, name: string): void {
    if (this.readOnly || this.blocked) return;
    if (!/^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(name))
      throw new Error(
        "名称须以英文字母开头，只使用字母、数字和下划线（最多64字符）。",
      );
    this.block(id)?.setFieldValue(name, "NAME");
  }
  register(id: string, registered: boolean): void {
    if (this.readOnly || this.blocked) return;
    const block = this.block(id);
    if (!block) return;
    const symbols = this.symbols();
    const entry = symbols.find((item) => item.id === id);
    if (
      registered &&
      entry &&
      symbols.some(
        (item) =>
          item.id !== id &&
          item.registered &&
          item.kind === entry.kind &&
          item.role === entry.role,
      )
    )
      throw new Error("同类训练/测试角色只能注册一个对象，请先注销原对象。");
    if (
      registered &&
      entry &&
      symbols.some((item) => item.id !== id && item.name === entry.name)
    )
      throw new Error("已有同名对象，请先修改名称。");
    setRegistration(block, registered);
  }
  undo(redo = false): void {
    if (!this.readOnly && !this.blocked)
      this.handles[this.active].workspace.undo(redo);
  }
  remove(id: string): void {
    if (!this.readOnly && !this.blocked) this.block(id)?.dispose(true);
  }
  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.listeners.forEach(([workspace, listener]) =>
      workspace.removeChangeListener(listener),
    );
    this.unbind.forEach((unbind) => unbind());
    for (const handle of Object.values(this.handles)) handle.dispose();
  }
}
