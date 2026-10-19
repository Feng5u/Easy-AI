import { FigureInspector } from "./FigureInspector.js";
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import type { ProjectEditorProps, WorkspaceTab } from "./editor-contract.js";
import { WorkspaceManager, workspaceTabs } from "./WorkspaceManager.js";
import type { SymbolRecord } from "../../../packages/block-library/symbols.mjs";
import "./ProjectEditor.css";

const labels: Record<WorkspaceTab, string> = {
  data: "数据处理",
  model: "模型结构",
  training: "训练管线",
};

export function ProjectEditor(props: ProjectEditorProps) {
  const workspaceId = useId();
  const callbacks = useRef(props);
  callbacks.current = props;
  const manager = useRef<WorkspaceManager | null>(null);
  const data = useRef<HTMLDivElement>(null);
  const model = useRef<HTMLDivElement>(null);
  const training = useRef<HTMLDivElement>(null);
  const container = useRef<HTMLDivElement>(null);
  const [symbols, setSymbols] = useState<SymbolRecord[]>([]);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [name, setName] = useState("");
  const [version, refresh] = useState(0);

  useLayoutEffect(() => {
    if (!data.current || !model.current || !training.current) return;
    let alive = true;
    const instance = new WorkspaceManager(
      { data: data.current, model: model.current, training: training.current },
      callbacks.current.readOnly,
      {
        onChange: (workspaces) => callbacks.current.onChange(workspaces),
        onSelect: (id) => callbacks.current.onSelect(id),
        onTabChange: (tab) => callbacks.current.onTabChange(tab),
        onRefresh: () => {
          if (alive) {
            setSymbols(instance.symbols());
            refresh((value) => value + 1);
          }
        },
      },
    );
    manager.current = instance;
    try {
      instance.receive(callbacks.current.project.workspaces);
      setLoadError("");
    } catch (failure) {
      setLoadError(
        failure instanceof Error
          ? failure.message
          : "工作区未载入。原文件未更改。",
      );
    }
    instance.setActive(callbacks.current.activeTab);
    const resize = () => instance.resize();
    const observer =
      typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
    if (container.current) observer?.observe(container.current);
    window.addEventListener("resize", resize);
    return () => {
      alive = false;
      observer?.disconnect();
      window.removeEventListener("resize", resize);
      instance.dispose();
      if (manager.current === instance) manager.current = null;
    };
  }, [props.project.projectId]);

  useEffect(() => {
    try {
      manager.current?.receive(props.project.workspaces);
      setLoadError("");
    } catch (failure) {
      setLoadError(
        failure instanceof Error
          ? failure.message
          : "工作区未载入。原文件未更改。",
      );
    }
  }, [props.project.workspaces]);
  useLayoutEffect(() => {
    manager.current?.setActive(props.activeTab);
  }, [props.activeTab]);
  useEffect(() => {
    manager.current?.setReadOnly(props.readOnly || Boolean(loadError));
  }, [props.readOnly, loadError]);
  useEffect(() => {
    manager.current?.syncSelection(props.selectedBlock);
  }, [props.selectedBlock]);

  const selected = props.selectedBlock
    ? manager.current?.block(props.selectedBlock)
    : null;
  const figure = props.selectedBlock
    ? manager.current?.figure(props.selectedBlock)
    : null;
  const entry = symbols.find((symbol) => symbol.id === props.selectedBlock);
  const selectedName = entry?.name ?? "";
  useEffect(() => {
    setName(selectedName);
  }, [selectedName, props.selectedBlock, version]);
  const readOnly = props.readOnly || Boolean(loadError);
  const action = (run: (instance: WorkspaceManager) => void) => {
    const instance = manager.current;
    if (!instance || readOnly) return;
    try {
      run(instance);
      // Blockly updates synchronously but delivers change events later. Publish
      // its actual snapshot before React restores controlled Inspector inputs.
      // Persistence and Undo still use the original Blockly events.
      setSymbols(instance.symbols());
      setError("");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "无法完成修改。");
    }
  };

  return (
    <section className="project-editor" aria-label="积木工作台">
      <div className="project-editor-toolbar">
        <div role="tablist" aria-label="三个积木工作区">
          {workspaceTabs.map((tab) => (
            <button
              key={tab}
              role="tab"
              aria-selected={props.activeTab === tab}
              aria-controls={`${workspaceId}-${tab}`}
              onClick={() => props.onTabChange(tab)}
            >
              {labels[tab]}
            </button>
          ))}
        </div>
        <div className="project-editor-history">
          <button
            disabled={readOnly}
            onClick={() => action((instance) => instance.undo())}
          >
            撤销
          </button>
          <button
            disabled={readOnly}
            onClick={() => action((instance) => instance.undo(true))}
          >
            重做
          </button>
        </div>
      </div>
      {(loadError || error) && (
        <div role="alert" className="project-editor-error">
          {loadError || error}
          {!loadError && <button onClick={() => setError("")}>关闭提示</button>}
        </div>
      )}
      {props.readOnly && (
        <p className="project-editor-note">
          此工程以只读方式打开，不能修改积木。
        </p>
      )}
      <div className="project-editor-body">
        <div className="project-editor-canvases" ref={container}>
          <div
            id={`${workspaceId}-data`}
            role="tabpanel"
            aria-label="数据处理"
            hidden={props.activeTab !== "data"}
            className="project-editor-canvas"
            ref={data}
          />
          <div
            id={`${workspaceId}-model`}
            role="tabpanel"
            aria-label="模型结构"
            hidden={props.activeTab !== "model"}
            className="project-editor-canvas"
            ref={model}
          />
          <div
            id={`${workspaceId}-training`}
            role="tabpanel"
            aria-label="训练管线"
            hidden={props.activeTab !== "training"}
            className="project-editor-canvas"
            ref={training}
          />
        </div>
        <aside className="project-editor-inspector" aria-label="对象注册与引用">
          {figure && (
            <FigureInspector
              key={`${props.project.projectId}:${figure.id}`}
              figure={figure}
              selectedBlock={props.selectedBlock}
              readOnly={readOnly}
              onApply={(layout, size) =>
                action((instance) =>
                  instance.configureFigure(figure.id, layout, size),
                )
              }
              onSelect={(id) => {
                props.onSelect(id);
                manager.current?.select(id);
              }}
            />
          )}
          <h3>所选积木</h3>
          {selected ? (
            <>
              <p>
                <strong>
                  <output aria-label="所选积木类型">{selected.type}</output>
                </strong>
              </p>
              <small>
                <output aria-label="所选积木 ID">{selected.id}</output>
              </small>
              {props.onHelp && (
                <button
                  type="button"
                  onClick={() => props.onHelp?.(selected.type)}
                >
                  查看此积木教程
                </button>
              )}
              {entry && (
                <>
                  <label>
                    用于生成代码的名称
                    <input
                      value={name}
                      maxLength={64}
                      disabled={readOnly}
                      onChange={(event) => setName(event.target.value)}
                      onBlur={() => {
                        if (name !== selectedName)
                          action((instance) => instance.rename(entry.id, name));
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.currentTarget.blur();
                        }
                      }}
                    />
                  </label>
                  <p className="project-editor-note">
                    以英文字母开头，只使用字母、数字和下划线。最终检查由编译器完成。
                  </p>
                  <label className="project-editor-register">
                    <input
                      type="checkbox"
                      disabled={readOnly}
                      checked={entry.registered}
                      onChange={(event) =>
                        action((instance) =>
                          instance.register(entry.id, event.target.checked),
                        )
                      }
                    />
                    供本项目引用
                  </label>
                  <p>
                    {entry.role
                      ? `${entry.role === "train" ? "训练" : "测试"}角色`
                      : "共享定义"}{" "}
                    · 引用使用固定ID，改名不会改变关联。
                  </p>
                </>
              )}
              <button
                disabled={readOnly}
                onClick={() =>
                  action((instance) => instance.remove(selected.id))
                }
              >
                删除所选积木
              </button>
            </>
          ) : (
            <p>点击积木查看参数与注册信息。可从左侧分类拖入新积木。</p>
          )}
          <h3>可引用对象</h3>
          <ul className="project-editor-symbols">
            {symbols
              .filter((symbol) => symbol.registered)
              .map((symbol) => (
                <li key={symbol.id}>
                  <button
                    onClick={() => {
                      props.onSelect(symbol.id);
                      manager.current?.select(symbol.id);
                    }}
                  >
                    {symbol.name}
                    <small>
                      {labels[symbol.workspace]}
                      {symbol.role
                        ? ` · ${symbol.role === "train" ? "训练" : "测试"}`
                        : ""}
                    </small>
                  </button>
                </li>
              ))}
          </ul>
          <p className="project-editor-note">
            带 ⚠
            的引用保留原对象ID，不会自动换成其他对象；请恢复原积木或重新选择。
          </p>
        </aside>
      </div>
    </section>
  );
}
