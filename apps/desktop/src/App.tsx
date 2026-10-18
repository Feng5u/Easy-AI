import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import type {
  CompileResult,
  DesktopAPI,
  ProjectDocument,
  ProjectSession,
  Run,
  SelectionResult,
} from "../electron/bridge.js";
import { ConnectionPanel } from "./ConnectionPanel.js";
import { CodeView } from "./CodeView.js";
import { RunDashboard } from "./RunDashboard.js";
import { isTerminal } from "./runEvents.js";
import { ProjectDraft } from "./ProjectDraft.js";
import type { WorkspaceTab } from "./editor-contract.js";
const ProjectEditor = lazy(() =>
  import("./ProjectEditor.js").then((module) => ({
    default: module.ProjectEditor,
  })),
);

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
  const [saving, setSaving] = useState(false);
  const [autosaveStopped, setAutosaveStopped] = useState(false);
  const [history, setHistory] = useState<Run[]>([]);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [viewTab, setViewTab] = useState<WorkspaceTab>("data");
  const [identityVisible, setIdentityVisible] = useState(false);
  const [viewCode, setViewCode] = useState(false);
  const draft = useRef<ProjectDraft | null>(null);
  const compiledSemantic = useRef(-1);
  const compileRequest = useRef(0);
  const intent = useRef<{ signature: string; key: string } | null>(null);
  const active = useRef(true);
  const updateRun = useCallback((latest: Run) => {
    setRun(latest);
    setHistory((previous) =>
      previous.map((item) => (item.runId === latest.runId ? latest : item)),
    );
  }, []);
  const activeRun =
    (run !== null && !isTerminal(run.status)) ||
    history.some((item) => !isTerminal(item.status));
  useEffect(() => {
    active.current = true;
    let mounted = true;
    if (!bridge) {
      setStatus("桌面桥接不可用，请从 Easy-AI 桌面应用启动。");
      return;
    }
    const unsubscribeStatus = bridge.status.subscribe((value) => {
      if (mounted) {
        setReady(value.ready);
        setStatus(value.message);
      }
    });
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
          acceptSession(value);
        }
      })
      .catch((reason) => {
        if (mounted) setError(`无法恢复当前工程：${String(reason)}`);
      });
    return () => {
      mounted = false;
      unsubscribeStatus();
      active.current = false;
      compileRequest.current += 1;
    };
  }, [bridge]);

  useEffect(() => {
    if (bridge) void bridge.projects.setDirty(dirty).catch(() => undefined);
  }, [bridge, dirty]);

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
    draft.current = value.project ? new ProjectDraft(value) : null;
    setSession(value);
    setProject(value.project);
    setViewTab(value.project?.ui?.activeTab ?? "data");
    setViewCode(value.project?.ui?.codeVisible ?? false);
    setHistoryOffset(0);
    setHistory([]);
    setRun(null);
    setAutosaveStopped(false);
    setCompilation(null);
    setDirty(false);
    setSelectedBlock(null);
    intent.current = null;
  }
  async function openProject(
    create: boolean,
    template: "mnist-cnn" | "blank" = "mnist-cnn",
  ) {
    if (!bridge) return;
    await perform(create ? "新建工程" : "打开工程", async () => {
      const choice = await bridge.selections.pick("project");
      if (!choice || !active.current) return;
      const opened = create
        ? await bridge.projects.create(
            choice.selectionId,
            projectName.trim(),
            template,
          )
        : await bridge.projects.open(choice.selectionId);
      if (active.current) {
        acceptSession(opened);
        setNotice(
          create
            ? template === "blank"
              ? "已新建空白工程，可从工具箱构建数据、模型和训练管线。"
              : "已新建 MNIST 示例工程。原有 data 内容由服务保留，运行不会下载数据。"
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
  const edit = useCallback(
    (change: (value: ProjectDocument) => ProjectDocument, semantic = true) => {
      const current = draft.current;
      if (!current || current.saved.readOnly) return;
      current.edit(change(current.value), semantic);
      setProject(current.value);
      setDirty(true);
      if (semantic) {
        setCompilation(null);
        compileRequest.current += 1;
        intent.current = null;
      }
    },
    [],
  );
  const changeWorkspaces = useCallback(
    (workspaces: ProjectDocument["workspaces"]) =>
      edit((value) => ({ ...value, workspaces })),
    [edit],
  );
  const changeTab = useCallback(
    (activeTab: WorkspaceTab) => {
      setViewTab(activeTab);
      if (!activeRun && !busy && !saving)
        edit((value) => ({ ...value, ui: { ...value.ui, activeTab } }), false);
    },
    [edit, activeRun, busy, saving],
  );
  const saveDraft = useCallback(async () => {
    const current = draft.current;
    if (!bridge || !current || !current.dirty || current.saved.readOnly)
      return false;
    setSaving(true);
    try {
      await current.save((value, revision) =>
        bridge.projects.save(value, revision),
      );
      if (active.current && draft.current === current) {
        setCompilation((previous) =>
          previous && current.semanticVersion === compiledSemantic.current
            ? { ...previous, revision: current.saved.project.revision }
            : null,
        );
        setSession(current.saved);
        setProject(current.value);
        setDirty(current.dirty);
        setAutosaveStopped(false);
        setNotice(
          current.dirty
            ? "已保存前一批更改，继续保存新的编辑。"
            : "工程已保存。",
        );
      }
      return true;
    } catch (reason) {
      if (active.current && draft.current === current) {
        setAutosaveStopped(true);
        setError(
          `保存失败，未保存内容仍保留。自动保存已暂停；可导出当前工程或手动重试：${String(reason)}`,
        );
      }
      return false;
    } finally {
      if (active.current) setSaving(false);
    }
  }, [bridge]);
  useEffect(() => {
    if (
      !dirty ||
      saving ||
      busy ||
      !ready ||
      autosaveStopped ||
      session?.readOnly
    )
      return;
    const timer = setTimeout(() => {
      void saveDraft();
    }, 800);
    return () => clearTimeout(timer);
  }, [
    dirty,
    saving,
    busy,
    ready,
    autosaveStopped,
    session?.readOnly,
    project,
    saveDraft,
  ]);
  useEffect(() => {
    if (!bridge || !project?.projectId) return;
    let valid = true;
    void bridge.runs
      .list(project.projectId, historyOffset, 25)
      .then((values) => {
        if (valid) setHistory(values);
      })
      .catch((reason) => {
        if (valid) setError(`读取历史失败：${String(reason)}`);
      });
    return () => {
      valid = false;
    };
  }, [bridge, project?.projectId, historyOffset, run?.runId]);
  async function save() {
    setError("");
    await saveDraft();
  }
  async function importProject() {
    if (!bridge) return;
    await perform("导入工程", async () => {
      const opened = await bridge.projects.importProject();
      if (active.current && opened) acceptSession(opened);
    });
  }
  async function exportProject() {
    if (!bridge) return;
    await perform("导出工程", async () => {
      const result = await bridge.projects.exportProject(
        dirty ? (project ?? undefined) : undefined,
      );
      if (active.current && result?.exported)
        setNotice(
          dirty
            ? "当前未保存草稿已导出为新文件，原工程未覆盖。"
            : "已导出工程原件为新文件。",
        );
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
        compiledSemantic.current = draft.current?.semanticVersion ?? -1;
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
    !busy &&
    !saving;
  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">EASY-AI · v0.0.0 开发版</p>
          <h1>华为 ICT · AI 积木工作台</h1>
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
        通过数据、模型和训练三个工作区构建工程。真实桌面交互与完整版本验收仍在进行。
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
      {saving && <p role="status">正在保存工程；期间的新编辑会继续保留。</p>}
      {autosaveStopped && (
        <p className="error" role="alert">
          自动保存已暂停。未保存状态仍在内存中，请导出草稿或手动重试。
        </p>
      )}
      <div className="button-row">
        <button
          type="button"
          disabled={!ready || !project}
          onClick={() => setIdentityVisible((value) => !value)}
        >
          SSH 主机身份设置
        </button>
      </div>
      {identityVisible && ready && bridge && project && (
        <ConnectionPanel
          key={project.projectId}
          api={bridge.connections}
          environments={bridge.environments}
          projectId={project.projectId}
          onClose={() => setIdentityVisible(false)}
        />
      )}
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
              disabled={!ready || Boolean(busy) || saving || dirty || activeRun}
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
                saving ||
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
            <button
              type="button"
              disabled={
                !ready ||
                Boolean(busy) ||
                saving ||
                dirty ||
                activeRun ||
                !projectName.trim()
              }
              onClick={() => {
                void openProject(true, "blank");
              }}
            >
              新建空白工程
            </button>
            <button
              type="button"
              disabled={!ready || Boolean(busy) || saving || dirty || activeRun}
              onClick={() => {
                void importProject();
              }}
            >
              导入 JSON 工程
            </button>
            <button
              type="button"
              disabled={
                !ready ||
                !session ||
                Boolean(busy) ||
                saving ||
                session.reason === "PROJECT_SIZE_LIMIT"
              }
              onClick={() => {
                void exportProject();
              }}
            >
              导出当前工程
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
                    const quick = event.target.checked;
                    edit((value) => ({
                      ...value,
                      settings: {
                        ...value.settings,
                        executionMode: quick ? "quick" : "full",
                      },
                    }));
                  }}
                />
                快速检查：1 epoch，最多 1024 个训练 / 256 个测试样本
              </label>
              <p className="muted">
                此开关只改变执行模式，不改示例积木中的正式训练参数。更改后需保存并重新编译。
              </p>
              <button
                type="button"
                disabled={
                  !writable || !dirty || Boolean(busy) || saving || activeRun
                }
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
      {session?.readOnly && !project && (
        <section className="panel" aria-labelledby="unsupported-heading">
          <h2 id="unsupported-heading">
            只读工程：{session.label ?? "不支持的格式"}
          </h2>
          <p className="error">
            {session.reason ?? "无法安全加载"}。原文件未更改，不加载
            Blockly、不自动保存；未超限时可导出原件。
          </p>
          <details>
            <summary>原始文本预览（最多 64KiB）</summary>
            <pre className="log">{session.rawText}</pre>
          </details>
        </section>
      )}
      {project && (
        <section className="panel">
          <Suspense fallback={<p role="status">正在加载积木编辑器…</p>}>
            <ProjectEditor
              project={project}
              readOnly={!writable || Boolean(busy) || activeRun}
              selectedBlock={selectedBlock}
              onChange={changeWorkspaces}
              onSelect={setSelectedBlock}
              activeTab={viewTab}
              onTabChange={changeTab}
            />
          </Suspense>
        </section>
      )}
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
              disabled={!ready || !project || dirty || Boolean(busy) || saving}
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
              <details
                open={viewCode}
                onToggle={(event) => {
                  const visible = event.currentTarget.open;
                  setViewCode(visible);
                  if (
                    !activeRun &&
                    !busy &&
                    !saving &&
                    visible !== (project?.ui?.codeVisible ?? false)
                  )
                    edit(
                      (value) => ({
                        ...value,
                        ui: { ...value.ui, codeVisible: visible },
                      }),
                      false,
                    );
                }}
              >
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
      {project && (
        <section className="panel">
          <h2>运行历史（只读快照）</h2>
          <p className="muted">查看旧运行不会替换当前编辑工程或映射。</p>
          {history.length ? (
            <ul className="history-list">
              {history.map((item) => (
                <li key={item.runId}>
                  <button type="button" onClick={() => setRun(item)}>
                    {item.runId.slice(0, 8)} · revision{" "}
                    {item.config.projectRevision} · {item.status}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p>暂无运行记录。</p>
          )}
          <div className="button-row">
            <button
              type="button"
              disabled={historyOffset === 0}
              onClick={() =>
                setHistoryOffset((value) => Math.max(0, value - 25))
              }
            >
              上一页
            </button>
            <button
              type="button"
              disabled={history.length < 25}
              onClick={() => setHistoryOffset((value) => value + 25)}
            >
              下一页
            </button>
          </div>
        </section>
      )}
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
