import { useCallback, useEffect, useRef, useState } from "react";
import type {
  CompileResult,
  DesktopAPI,
  ProjectDocument,
  ProjectSession,
  Run,
  SelectionResult,
} from "../electron/bridge.js";
import { CodeView } from "./CodeView.js";
import { RunDashboard } from "./RunDashboard.js";
import { isTerminal } from "./runEvents.js";

declare global {
  interface Window {
    easyai: DesktopAPI;
  }
}

export function App({ api }: { api?: DesktopAPI }) {
  const bridge =
    api ?? (typeof window === "undefined" ? undefined : window.easyai);
  const [status, setStatus] = useState("正在连接本地服务…");
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<ProjectSession | null>(null);
  const [project, setProject] = useState<ProjectDocument | null>(null);
  const [dirty, setDirty] = useState(false);
  const [projectName, setProjectName] = useState("MNIST CNN");
  const [python, setPython] = useState<SelectionResult | null>(null);
  const [data, setData] = useState<SelectionResult | null>(null);
  const [compilation, setCompilation] = useState<CompileResult | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selectedBlock, setSelectedBlock] = useState<string | null>(null);
  const compileRequest = useRef(0);
  const intent = useRef<{ signature: string; key: string } | null>(null);
  const active = useRef(true);
  const updateRun = useCallback((latest: Run) => setRun(latest), []);
  const activeRun = run !== null && !isTerminal(run.status);
  useEffect(() => {
    active.current = true;
    let mounted = true;
    if (!bridge) {
      setStatus("桌面桥接不可用，请从 Easy-AI 桌面应用启动。");
      return;
    }
    void bridge.status
      .get()
      .then((value) => {
        if (mounted) {
          setReady(value.ready);
          setStatus(value.ready ? "本地服务已就绪。" : value.message);
        }
      })
      .catch((reason) => {
        if (mounted) setStatus(`无法连接本地服务：${String(reason)}`);
      });
    void bridge.projects
      .current()
      .then((value) => {
        if (mounted && value) {
          setSession(value);
          setProject(value.project);
        }
      })
      .catch((reason) => {
        if (mounted) setError(`无法恢复当前工程：${String(reason)}`);
      });
    return () => {
      mounted = false;
      active.current = false;
      compileRequest.current += 1;
    };
  }, [bridge]);

  async function perform(label: string, operation: () => Promise<void>) {
    setBusy(label);
    setError("");
    setNotice("");
    try {
      await operation();
    } catch (reason) {
      if (active.current) setError(`${label}失败：${String(reason)}`);
    } finally {
      if (active.current) setBusy(null);
    }
  }
  function acceptSession(value: ProjectSession) {
    compileRequest.current += 1;
    setSession(value);
    setProject(value.project);
    setCompilation(null);
    setDirty(false);
    setSelectedBlock(null);
    intent.current = null;
  }
  async function openProject(create: boolean) {
    if (!bridge) return;
    await perform(create ? "新建工程" : "打开工程", async () => {
      const choice = await bridge.selections.pick("project");
      if (!choice || !active.current) return;
      const opened = create
        ? await bridge.projects.create(choice.selectionId, projectName.trim())
        : await bridge.projects.open(choice.selectionId);
      if (active.current) {
        acceptSession(opened);
        setNotice(
          create
            ? "已新建 MNIST 示例工程。原有 data 内容由服务保留，运行不会下载数据。"
            : "已打开工程。请选择当前机器的训练 Python 与数据目录。",
        );
      }
    });
  }
  async function choose(kind: "python" | "data") {
    if (!bridge) return;
    await perform(
      kind === "python" ? "选择 Python" : "选择数据目录",
      async () => {
        const choice = await bridge.selections.pick(kind);
        if (!choice || !active.current) return;
        if (kind === "python") setPython(choice);
        else setData(choice);
        intent.current = null;
      },
    );
  }
  async function save() {
    if (!bridge || !project || !session) return;
    await perform("保存工程", async () => {
      const saved = await bridge.projects.save(
        project,
        session.project.revision,
      );
      if (active.current) {
        acceptSession(saved);
        setNotice("已保存。请重新检查代码后运行。");
      }
    });
  }
  async function compile() {
    if (!bridge || !project) return;
    const request = ++compileRequest.current;
    await perform("检查与编译", async () => {
      const result = await bridge.projects.compile(project, request);
      if (
        active.current &&
        request === compileRequest.current &&
        result.revision === project.revision
      ) {
        setCompilation(result);
        intent.current = null;
        setNotice(
          result.runnable
            ? "权威编译检查通过。点击“开始本次运行”才会启动训练。"
            : "工程尚不能运行，请查看问题说明。",
        );
      }
    });
  }
  async function start() {
    if (
      !bridge ||
      !project ||
      !compilation ||
      !python ||
      !data ||
      dirty ||
      compilation.revision !== project.revision
    )
      return;
    const request = {
      projectId: project.projectId,
      expectedRevision: project.revision,
      expectedProgramHash: compilation.programHash,
      pythonSelectionId: python.selectionId,
      dataSelectionId: data.selectionId,
    };
    const signature = JSON.stringify(request);
    if (intent.current?.signature !== signature)
      intent.current = { signature, key: crypto.randomUUID() };
    const idempotencyKey = intent.current.key;
    await perform("启动运行", async () => {
      const created = await bridge.runs.start({ ...request, idempotencyKey });
      if (active.current) {
        setRun(created);
        intent.current = null;
        setNotice("运行请求已确认。日志、指标和文件均来自本次真实子进程。");
      }
    });
  }
  const writable = project && session && !session.readOnly;
  const canRun =
    ready &&
    writable &&
    !dirty &&
    compilation?.runnable &&
    compilation.revision === project.revision &&
    python &&
    data &&
    !activeRun &&
    !busy;
  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">EASY-AI · v0.0.0 开发版</p>
          <h1>训练调试工作台</h1>
          <p>打开工程，检查代码，在选定的现有环境中运行。</p>
        </div>
        <span
          data-testid="backend-status"
          className={`service-state ${ready ? "ready" : ""}`}
          role="status"
        >
          {status}
        </span>
      </header>
      <p className="notice">
        当前提供工程、编译与本地运行调试。三页积木编辑工作区尚未提供；完整版本与桌面验收仍在进行。
      </p>
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {busy && <p role="status">{busy}中，请稍候…</p>}
      <div className="setup-grid">
        <section className="panel" aria-labelledby="project-heading">
          <h2 id="project-heading">1. 工程</h2>
          <label className="field">
            新工程名称
            <input
              value={projectName}
              maxLength={128}
              onChange={(event) => setProjectName(event.target.value)}
            />
          </label>
          <div className="button-row">
            <button
              type="button"
              disabled={!ready || Boolean(busy) || dirty || activeRun}
              onClick={() => {
                void openProject(false);
              }}
            >
              选择目录并打开
            </button>
            <button
              type="button"
              disabled={
                !ready ||
                Boolean(busy) ||
                dirty ||
                activeRun ||
                !projectName.trim()
              }
              onClick={() => {
                void openProject(true);
              }}
            >
              新建 MNIST 示例
            </button>
          </div>
          <p className="muted">
            新建只写入新工程文件，不覆盖已有工程或数据。正式训练固定不自动下载数据。
          </p>
          {project ? (
            <>
              <h3>{project.name}</h3>
              <p>
                revision {project.revision} ·{" "}
                {dirty ? "有未保存配置" : "已保存"}
              </p>
              {session?.readOnly && (
                <p className="error" role="alert">
                  工程为只读：{session.reason ?? "无法取得写入权限"}
                  。保存和运行已禁用。
                </p>
              )}
              <label className="checkbox-field">
                <input
                  type="checkbox"
                  checked={project.settings?.executionMode === "quick"}
                  disabled={!writable || Boolean(busy) || activeRun}
                  onChange={(event) => {
                    setProject({
                      ...project,
                      settings: {
                        ...project.settings,
                        executionMode: event.target.checked ? "quick" : "full",
                      },
                    });
                    setDirty(true);
                    setCompilation(null);
                    compileRequest.current += 1;
                    intent.current = null;
                  }}
                />
                快速检查：1 epoch，最多 1024 个训练 / 256 个测试样本
              </label>
              <p className="muted">
                此开关只改变执行模式，不改示例积木中的正式训练参数。更改后需保存并重新编译。
              </p>
              <button
                type="button"
                disabled={!writable || !dirty || Boolean(busy) || activeRun}
                onClick={() => {
                  void save();
                }}
              >
                保存工程配置
              </button>
            </>
          ) : (
            <p className="empty-state">
              尚未打开工程。可选择已有工程目录，或在新目录创建 MNIST 示例。
            </p>
          )}
        </section>
        <section className="panel" aria-labelledby="environment-heading">
          <h2 id="environment-heading">2. 运行环境与数据</h2>
          <p>
            选择已安装训练依赖的
            Python，以及已准备好数据的目录。此页面不会安装包或下载数据。
          </p>
          <div className="binding">
            <span>训练 Python</span>
            <strong>{python?.label ?? "尚未选择"}</strong>
            <button
              type="button"
              disabled={!ready || Boolean(busy) || activeRun}
              onClick={() => {
                void choose("python");
              }}
            >
              选择现有 Python
            </button>
          </div>
          <div className="binding">
            <span>数据目录</span>
            <strong>{data?.label ?? "尚未选择"}</strong>
            <button
              type="button"
              disabled={!ready || Boolean(busy) || activeRun}
              onClick={() => {
                void choose("data");
              }}
            >
              选择数据目录
            </button>
          </div>
          <p className="muted">
            当前运行位置：本机。学校服务器连接将在后续阶段提供。
          </p>
        </section>
      </div>
      <section className="panel" aria-labelledby="compile-heading">
        <div className="section-heading">
          <div>
            <h2 id="compile-heading">3. 检查与运行</h2>
            <p className="muted">
              保存的工程与编译 revision 一致后，才能显式启动。
            </p>
          </div>
          <div className="button-row">
            <button
              type="button"
              disabled={!ready || !project || dirty || Boolean(busy)}
              onClick={() => {
                void compile();
              }}
            >
              检查与编译
            </button>
            <button
              type="button"
              className="primary"
              disabled={!canRun}
              onClick={() => {
                void start();
              }}
            >
              开始本次运行
            </button>
          </div>
        </div>
        {dirty && <p className="notice">请先保存当前配置，再检查与运行。</p>}
        {compilation ? (
          <>
            <p role="status">
              {compilation.runnable ? "代码检查通过" : "暂不能运行"} · revision{" "}
              {compilation.revision}
            </p>
            {compilation.diagnostics.length > 0 && (
              <ul className="diagnostics">
                {compilation.diagnostics.map((diagnostic, index) => (
                  <li
                    key={`${diagnostic.code}-${index}`}
                    className={
                      diagnostic.severity === "error" ? "error" : "notice"
                    }
                  >
                    <strong>{diagnostic.message}</strong>
                    {diagnostic.suggestion && <p>{diagnostic.suggestion}</p>}
                    {diagnostic.origin && (
                      <button
                        type="button"
                        onClick={() =>
                          setSelectedBlock(diagnostic.origin?.blockId ?? null)
                        }
                      >
                        源积木 {diagnostic.origin.blockId}
                      </button>
                    )}
                    <small>
                      {diagnostic.code}
                      {diagnostic.field ? ` · ${diagnostic.field}` : ""}
                    </small>
                  </li>
                ))}
              </ul>
            )}
            {compilation.code && (
              <details>
                <summary>查看当前工程的只读生成代码</summary>
                {selectedBlock && (
                  <p>
                    来源积木：<code>{selectedBlock}</code>
                  </p>
                )}
                <CodeView
                  code={compilation.code}
                  spans={compilation.sourceMap ?? []}
                  selectedBlock={selectedBlock}
                  onSelectBlock={setSelectedBlock}
                />
              </details>
            )}
          </>
        ) : (
          <p className="empty-state">尚无编译结果。检查不会启动训练。</p>
        )}
      </section>
      {bridge && run && (
        <RunDashboard
          key={run.runId}
          api={bridge}
          initialRun={run}
          onRunUpdate={updateRun}
        />
      )}
    </main>
  );
}
