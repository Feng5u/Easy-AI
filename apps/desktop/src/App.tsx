import "./Workbench.css";
import { PackageManager } from "./PackageManager.js";
import { DataUpload } from "./DataUpload.js";
import { TutorialPanel } from "./TutorialPanel.js";
import { tutorialForBlock, tutorialTargets, tutorials } from "./tutorials.js";
import type { TutorialId, TutorialTarget } from "./tutorials.js";
import { FailureCard, operationFailure } from "./FailureCard.js";
import type { OperationFailure, FailureStage } from "./FailureCard.js";
import { GettingStarted } from "./GettingStarted.js";
import type { GuideDestination } from "./GettingStarted.js";
import { LocalPreflight } from "./LocalPreflight.js";
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
  RemoteBinding,
  AuthenticatedConnection,
} from "../electron/bridge.js";
import { ServerProfiles } from "./ServerProfiles.js";
import { CodeView } from "./CodeView.js";
import { RunDashboard } from "./RunDashboard.js";
import { isRunSettled } from "./runEvents.js";
import { ProjectDraft } from "./ProjectDraft.js";
import type {
  BlockNavigationRequest,
  WorkspaceTab,
} from "./editor-contract.js";
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
  const [restoringProject, setRestoringProject] = useState(true);
  const [session, setSession] = useState<ProjectSession | null>(null);
  const [project, setProject] = useState<ProjectDocument | null>(null);
  const [dirty, setDirty] = useState(false);
  const [projectName, setProjectName] = useState("MNIST CNN");
  const [python, setPython] = useState<SelectionResult | null>(null);
  const [data, setData] = useState<SelectionResult | null>(null);
  const [runMode, setRunMode] = useState<"local" | "ssh">("local");
  const [remoteBinding, setRemoteBinding] = useState<RemoteBinding | null>(
    null,
  );
  const [remoteSession, setRemoteSession] =
    useState<AuthenticatedConnection | null>(null);
  const [compilation, setCompilation] = useState<CompileResult | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<OperationFailure | null>(null);
  const [notice, setNotice] = useState("");
  const [selectedBlock, setSelectedBlock] = useState<string | null>(null);
  const [blockNavigation, setBlockNavigation] =
    useState<BlockNavigationRequest | null>(null);
  const [saving, setSaving] = useState(false);
  const [autosaveStopped, setAutosaveStopped] = useState(false);
  const [history, setHistory] = useState<Run[]>([]);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [historyRefresh, setHistoryRefresh] = useState(0);
  const [historyError, setHistoryError] = useState<OperationFailure | null>(
    null,
  );
  const [viewTab, setViewTab] = useState<WorkspaceTab>("data");
  const [packagesVisible, setPackagesVisible] = useState(false);
  const [packagesOpened, setPackagesOpened] = useState(false);
  useEffect(() => {
    if (packagesVisible) document.getElementById("packages-heading")?.focus();
  }, [packagesVisible]);
  const [tutorialVisible, setTutorialVisible] = useState(false);
  const [tutorialTopic, setTutorialTopic] = useState<TutorialId>("convolution");
  useEffect(() => {
    if (tutorialVisible) document.getElementById("tutorial-heading")?.focus();
  }, [tutorialVisible, tutorialTopic]);
  const [identityVisible, setIdentityVisible] = useState(false);
  const [viewCode, setViewCode] = useState(false);
  const [settingsPanel, setSettingsPanel] = useState<
    "project" | "environment" | null
  >(null);
  const [guideVisible, setGuideVisible] = useState(false);
  const [dock, setDock] = useState<"checks" | "history" | "results" | null>(
    null,
  );
  const [dockExpanded, setDockExpanded] = useState(false);
  const pendingFocus = useRef<string | null>(null);
  const previewAttempt = useRef("");
  useEffect(() => {
    const id = pendingFocus.current;
    if (!id) return;
    document.getElementById(id)?.focus();
    pendingFocus.current = null;
  }, [settingsPanel, dock, guideVisible]);

  const serverFocusProject = useRef<string | null>(null);
  const focusServer = () => {
    const target = document.getElementById("server-configuration");
    if (!target || target.closest("[hidden]")) return false;
    target.focus();
    target.scrollIntoView?.({ block: "start" });
    return true;
  };
  function openServerSettings() {
    if (!project) return;
    setSettingsPanel("environment");
    setGuideVisible(false);
    if (!focusServer()) serverFocusProject.current = project.projectId;
    setIdentityVisible(true);
  }
  useEffect(() => {
    if (
      identityVisible &&
      ready &&
      project &&
      serverFocusProject.current === project.projectId
    )
      focusServer();
    serverFocusProject.current = null;
  }, [identityVisible, ready, project?.projectId, settingsPanel]);

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
  const acceptRemoteSession = useCallback(
    (value: AuthenticatedConnection | null) => {
      setRemoteSession(value);
      if (!value) setRemoteBinding(null);
    },
    [],
  );
  const acceptRemoteBinding = useCallback(
    (value: RemoteBinding | null) => {
      if (
        value &&
        (dirty ||
          value.projectId !== project?.projectId ||
          value.projectRevision !== project.revision ||
          value.programHash !== compilation?.programHash)
      )
        return;
      setRemoteBinding(value);
      if (value) setRunMode("ssh");
    },
    [dirty, project?.projectId, project?.revision, compilation?.programHash],
  );
  useEffect(() => {
    if (!remoteBinding) return;
    if (
      dirty ||
      remoteBinding.projectId !== project?.projectId ||
      remoteBinding.projectRevision !== project.revision ||
      remoteBinding.programHash !== compilation?.programHash
    ) {
      setRemoteBinding(null);
      return;
    }
    const expected = remoteBinding.bindingId;
    const timer = setTimeout(
      () =>
        setRemoteBinding((previous) =>
          previous?.bindingId === expected ? null : previous,
        ),
      remoteBinding.expiresInSeconds * 1000,
    );
    return () => clearTimeout(timer);
  }, [
    remoteBinding,
    dirty,
    project?.projectId,
    project?.revision,
    compilation?.programHash,
  ]);
  const activeRun =
    (run !== null && !isRunSettled(run)) ||
    history.some((item) => !isRunSettled(item));
  useEffect(() => {
    active.current = true;
    let mounted = true;
    if (!bridge) {
      setStatus("桌面桥接不可用，请从 Easy-AI 桌面应用启动。");
      return;
    }
    setRestoringProject(true);
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
        if (mounted) {
          setStatus("无法连接本地服务，请查看错误卡片。");
          setError(operationFailure("service", reason));
        }
      });
    void bridge.projects
      .current()
      .then((value) => {
        if (mounted && value) {
          acceptSession(value);
        }
      })
      .catch((reason) => {
        if (mounted) setError(operationFailure("restore", reason));
      })
      .finally(() => {
        if (mounted) setRestoringProject(false);
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

  async function perform(
    stage: FailureStage,
    label: string,
    operation: () => Promise<void>,
  ) {
    setBusy(label);
    setError(null);
    setNotice("");
    try {
      await operation();
    } catch (reason) {
      if (active.current) {
        setError(operationFailure(stage, reason));
      }
    } finally {
      if (active.current) setBusy(null);
    }
  }
  function acceptSession(value: ProjectSession) {
    setRemoteBinding(null);
    setRemoteSession(null);
    compileRequest.current += 1;
    draft.current = value.project ? new ProjectDraft(value) : null;
    setSettingsPanel(null);
    setGuideVisible(false);
    setDock(null);
    previewAttempt.current = "";
    setSession(value);
    setProject(value.project);
    setViewTab(value.project?.ui?.activeTab ?? "data");
    setViewCode(value.project?.ui?.codeVisible ?? false);
    setHistoryOffset(0);
    setHistory([]);
    setHistoryError(null);
    setRun(null);
    setAutosaveStopped(false);
    setCompilation(null);
    setDirty(false);
    setSelectedBlock(null);
    setBlockNavigation(null);
    intent.current = null;
  }
  async function openProject(
    create: boolean,
    template: "mnist-cnn" | "blank" = "mnist-cnn",
    protectDraft = false,
  ) {
    if (!bridge) return;
    if (
      protectDraft &&
      (restoringProject || draft.current?.dirty || saving || busy || activeRun)
    ) {
      setNotice("请先保存或导出当前草稿，再创建教学副本；当前工程已保留。");
      return;
    }
    const priorDraft = draft.current,
      priorValue = draft.current?.value;
    await perform("project", create ? "新建工程" : "打开工程", async () => {
      const choice = await bridge.selections.pick("project");
      if (!choice || !active.current) return;
      if (
        protectDraft &&
        (draft.current !== priorDraft ||
          draft.current?.value !== priorValue ||
          draft.current?.dirty)
      ) {
        setNotice("工程在选择目录期间变化，已停止创建教学副本并保留草稿。");
        return;
      }
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
      "selection",
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
        setError(operationFailure("save", reason));
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
        if (valid) {
          setHistory(values);
          setHistoryError(null);
        }
      })
      .catch((reason) => {
        if (valid) setHistoryError(operationFailure("history", reason));
      });
    return () => {
      valid = false;
    };
  }, [bridge, project?.projectId, historyOffset, historyRefresh, run?.runId]);
  async function save() {
    setError(null);
    await saveDraft();
  }
  async function importProject() {
    if (!bridge) return;
    await perform("import", "导入工程", async () => {
      const opened = await bridge.projects.importProject();
      if (active.current && opened) acceptSession(opened);
    });
  }
  async function exportProject() {
    if (!bridge) return;
    await perform("export", "导出工程", async () => {
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
  async function exportBundle() {
    if (
      !bridge?.projects.exportBundle ||
      !project ||
      dirty ||
      !compilation?.runnable ||
      compilation.revision !== project.revision ||
      !compilation.programHash
    )
      return;
    await perform("export", "导出代码 Bundle", async () => {
      try {
        const result = await bridge.projects.exportBundle!(
          project.projectId,
          project.revision,
          compilation.programHash!,
        );
        if (active.current && result?.exported)
          setNotice(
            `已导出 revision ${result.projectRevision} 的完整代码到所选目录下 ${result.directoryName}。请按 README 在已有训练环境运行；此次没有安装依赖、读取数据或启动训练。`,
          );
      } catch (error) {
        if (active.current)
          setNotice(
            "代码导出未确认；所选父目录可能已留下完整或未完成的 easyai-code 子目录，请保留检查。重试会创建新目录，不合并已有输出。",
          );
        throw error;
      }
    });
  }
  async function compile() {
    if (!bridge || !project) return;
    const request = ++compileRequest.current;
    await perform("compile", "检查与编译", async () => {
      const result = await bridge.projects.compile(project, request);
      if (
        active.current &&
        request === compileRequest.current &&
        result.revision === project.revision
      ) {
        compiledSemantic.current = draft.current?.semanticVersion ?? -1;
        setCompilation(result);
        if (!result.runnable) setDock("checks");
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
      dirty ||
      compilation.revision !== project.revision
    )
      return;
    if (runMode === "local" && (!python || !data)) return;
    if (runMode === "ssh" && (!remoteBinding || !remoteSession)) return;
    const common = {
      projectId: project.projectId,
      expectedRevision: project.revision,
      expectedProgramHash: compilation.programHash,
    };
    const request =
      runMode === "ssh"
        ? {
            ...common,
            runner: "ssh" as const,
            bindingId: remoteBinding!.bindingId,
          }
        : {
            ...common,
            pythonSelectionId: python!.selectionId,
            dataSelectionId: data!.selectionId,
          };
    const signature = JSON.stringify(request);
    if (intent.current?.signature !== signature)
      intent.current = { signature, key: crypto.randomUUID() };
    const idempotencyKey = intent.current.key;
    await perform("start", "启动运行", async () => {
      const created = await bridge.runs.start({ ...request, idempotencyKey });
      if (active.current) {
        setRun(created);
        setDock("results");
        intent.current = null;
        setNotice(
          created.config.runner === "ssh"
            ? "远端运行请求已登记。启动、连接和同步状态将分别更新；未知状态不会重新启动。"
            : "运行请求已确认。日志、指标和文件均来自本次真实子进程。",
        );
      }
    });
  }
  function locateBlock(blockId: string | null) {
    if (!project || !blockId) return;
    setSettingsPanel(null);
    setGuideVisible(false);
    setSelectedBlock(blockId);
    setBlockNavigation((previous) => ({
      projectId: project.projectId,
      blockId,
      sequence: (previous?.sequence ?? 0) + 1,
    }));
  }
  function tutorialLocate(target: TutorialTarget) {
    if (!project) return;
    const topic = tutorials.find((item) => item.id === tutorialTopic)!;
    const hit = tutorialTargets(project, topic.relevantBlockTypes).find(
      (item) => item.id === target.id && item.workspace === target.workspace,
    );
    if (!hit) return;
    setViewTab(hit.workspace);
    locateBlock(hit.id);
  }
  function tutorialHelp(blockType: string) {
    const topic = tutorialForBlock(blockType);
    if (!topic) return;
    setTutorialTopic(topic.id);
    setTutorialVisible(true);
    setSettingsPanel(null);
    setGuideVisible(false);
  }
  function navigate(destination: GuideDestination) {
    const ids: Record<GuideDestination, string> = {
      project: "project-heading",
      environment: "environment-heading",
      compile: "compile-heading",
      history: "history-heading",
    };
    pendingFocus.current = ids[destination];
    setGuideVisible(false);
    if (destination === "project" || destination === "environment") {
      setSettingsPanel(destination);
    } else {
      setSettingsPanel(null);
      setDock(destination === "compile" ? "checks" : "history");
    }
    // Already visible destinations do not trigger another render.
    const target = document.getElementById(ids[destination]);
    if (target && !target.closest("[hidden]")) target.focus();
  }
  const writable = project && session && !session.readOnly;
  const canRun =
    ready &&
    writable &&
    !dirty &&
    compilation?.runnable &&
    compilation.revision === project.revision &&
    (runMode === "local" ? python && data : remoteBinding && remoteSession) &&
    !activeRun &&
    !busy &&
    !saving;
  function showCode(visible: boolean) {
    setViewCode(visible);
    setTutorialVisible(false);
    setSettingsPanel(null);
    setGuideVisible(false);
    if (
      !activeRun &&
      !busy &&
      !saving &&
      visible !== (project?.ui?.codeVisible ?? false)
    )
      edit(
        (value) => ({ ...value, ui: { ...value.ui, codeVisible: visible } }),
        false,
      );
  }
  // Preview uses the same authoritative compiler as the explicit check button.
  // One attempt per saved revision prevents retry loops after a failed request.
  useEffect(() => {
    if (
      !viewCode ||
      !ready ||
      !project ||
      dirty ||
      saving ||
      busy ||
      activeRun ||
      compilation
    )
      return;
    const key = `${project.projectId}:${project.revision}`;
    if (previewAttempt.current === key) return;
    previewAttempt.current = key;
    void compile();
  }, [viewCode, ready, project, dirty, saving, busy, activeRun, compilation]);
  const settingsVisible = !project || settingsPanel !== null || guideVisible;
  const problemCount = compilation?.diagnostics.length ?? 0;
  const saveStatus = session?.readOnly
    ? "只读工程"
    : saving
      ? "正在保存…"
      : dirty
        ? "有未保存修改"
        : "已保存";
  return (
    <main className="app-shell workbench-shell">
      <header className="workbench-header">
        <div className="workbench-brand">
          <span className="workbench-brand-mark" aria-hidden="true">
            E
          </span>
          <h1>Easy-AI</h1>
          <span>AI 积木工作台</span>
        </div>
        <nav className="workbench-navigation" aria-label="工作台工具">
          <button
            type="button"
            aria-pressed={settingsPanel === "project"}
            onClick={() => {
              setGuideVisible(false);
              setSettingsPanel(settingsPanel === "project" ? null : "project");
            }}
          >
            工程
          </button>
          <button
            type="button"
            aria-pressed={settingsPanel === "environment"}
            onClick={() => {
              setGuideVisible(false);
              setSettingsPanel(
                settingsPanel === "environment" ? null : "environment",
              );
            }}
          >
            环境与数据
          </button>
          <button
            type="button"
            aria-pressed={
              !viewCode && !tutorialVisible && !settingsPanel && !guideVisible
            }
            onClick={() => showCode(false)}
          >
            积木
          </button>
          <button
            type="button"
            disabled={!project}
            aria-pressed={viewCode && !tutorialVisible}
            aria-controls="workbench-code"
            onClick={() => showCode(!viewCode || tutorialVisible)}
          >
            代码对照
          </button>
          <button
            type="button"
            aria-expanded={tutorialVisible}
            onClick={() => {
              setTutorialVisible((previous) => !previous);
              setSettingsPanel(null);
              setGuideVisible(false);
            }}
          >
            {tutorialVisible ? "收起离线教程" : "打开离线教程"}
          </button>
          <button
            type="button"
            aria-expanded={guideVisible}
            onClick={() => {
              setGuideVisible((previous) => !previous);
              setSettingsPanel(null);
            }}
          >
            使用指引
          </button>
        </nav>
        <span
          data-testid="backend-status"
          className={`service-state ${ready ? "ready" : ""}`}
          role="status"
        >
          {status}
        </span>
      </header>
      <div className="workbench-commandbar">
        <div className="workbench-project-name">
          <strong>{project?.name ?? "开始一个 AI 实验"}</strong>
          <span>{project ? saveStatus : "从数据到模型，再到训练"}</span>
          {project?.settings?.executionMode === "quick" && (
            <span className="workbench-quick">小样本快速检查</span>
          )}
        </div>
        <button
          className="workbench-environment"
          type="button"
          onClick={() => navigate("environment")}
        >
          {runMode === "local" ? "本机" : "学校服务器"} ·{" "}
          {runMode === "local"
            ? python
              ? "已选择 Python"
              : "待选择环境"
            : remoteBinding
              ? "已绑定环境"
              : "待配置环境"}
        </button>
        {project && (
          <>
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
        )}
        <div className="button-row">
          <button
            type="button"
            disabled={!ready || !project || dirty || Boolean(busy) || saving}
            onClick={() => {
              setDock("checks");
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
        {run && (
          <button
            type="button"
            className={activeRun ? "danger" : ""}
            onClick={() => setDock("results")}
          >
            {activeRun ? "运行状态 / 停止" : "查看运行结果"}
          </button>
        )}
      </div>
      <div className="workbench-feedback" aria-label="操作反馈">
        {error && <FailureCard failure={error} onNavigate={navigate} />}
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
      </div>
      <div
        className="workbench-main"
        data-side-panel={tutorialVisible || (viewCode && Boolean(project))}
      >
        <div className="workbench-primary">
          <div className="workbench-settings" hidden={!settingsVisible}>
            {project && (
              <div className="workbench-settings-heading">
                <h2>
                  {guideVisible
                    ? "使用指引"
                    : settingsPanel === "environment"
                      ? "准备运行环境与数据"
                      : "工程设置"}
                </h2>
                <button
                  type="button"
                  onClick={() => {
                    setSettingsPanel(null);
                    setGuideVisible(false);
                  }}
                >
                  返回积木
                </button>
              </div>
            )}
            <div hidden={!guideVisible}>
              <GettingStarted
                projectName={project?.name ?? null}
                readOnly={Boolean(session?.readOnly)}
                dirty={dirty}
                mode={runMode}
                pythonSelected={Boolean(python)}
                dataSelected={Boolean(data)}
                remoteBound={Boolean(
                  remoteBinding &&
                  remoteSession &&
                  !dirty &&
                  remoteBinding.projectId === project?.projectId &&
                  remoteBinding.projectRevision === project.revision &&
                  remoteBinding.programHash === compilation?.programHash &&
                  remoteBinding.connectionId ===
                    remoteSession.scope.connectionId &&
                  remoteSession.projectId === project.projectId,
                )}
                compiled={Boolean(
                  !dirty &&
                  compilation?.runnable &&
                  compilation.revision === project?.revision,
                )}
                hasRun={Boolean(run || history.length)}
                ready={ready}
                blocked={Boolean(busy) || saving || activeRun}
                onServer={openServerSettings}
                onNavigate={navigate}
              />
            </div>
            <div hidden={settingsPanel === "environment" || guideVisible}>
              <section className="panel" aria-labelledby="project-heading">
                <h2 id="project-heading" tabIndex={-1}>
                  1. 工程
                </h2>
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
                    disabled={
                      !ready || Boolean(busy) || saving || dirty || activeRun
                    }
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
                    disabled={
                      !ready || Boolean(busy) || saving || dirty || activeRun
                    }
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
                  <button
                    type="button"
                    disabled={
                      !ready ||
                      !bridge?.projects.exportBundle ||
                      !project ||
                      Boolean(busy) ||
                      saving ||
                      dirty ||
                      session?.readOnly ||
                      !compilation?.runnable ||
                      compilation.revision !== project.revision
                    }
                    onClick={() => {
                      void exportBundle();
                    }}
                  >
                    导出已保存代码 Bundle
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
                  </>
                ) : (
                  <p className="empty-state">
                    尚未打开工程。可选择已有工程目录，或在新目录创建 MNIST
                    示例。
                  </p>
                )}
              </section>

              {session?.readOnly && !project && (
                <section
                  className="panel"
                  aria-labelledby="unsupported-heading"
                >
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
            </div>
            <div hidden={settingsPanel !== "environment" || guideVisible}>
              <section className="panel" aria-labelledby="environment-heading">
                <h2 id="environment-heading" tabIndex={-1}>
                  2. 运行环境与数据
                </h2>
                <p>
                  选择已安装训练依赖的
                  Python，以及已准备好数据的目录。此页面不会安装包或下载数据。
                </p>
                <label className="field">
                  运行位置
                  <select
                    value={runMode}
                    disabled={!!busy || activeRun}
                    onChange={(event) =>
                      setRunMode(event.target.value as "local" | "ssh")
                    }
                  >
                    <option value="local">本机</option>
                    <option value="ssh">SSH 服务器</option>
                  </select>
                </label>
                {runMode === "ssh" && (
                  <p role="status">
                    {remoteBinding
                      ? `已绑定 revision ${remoteBinding.projectRevision} · ${remoteBinding.pythonExecutable} · ${remoteBinding.device}`
                      : "请在 SSH 设置中完成身份、认证、环境和数据检查，再绑定已保存工程。"}
                  </p>
                )}
                {runMode === "local" ? (
                  <>
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
                      训练 Python 是已安装训练依赖的解释器。MNIST
                      示例的数据目录内需有
                      MNIST/raw；数据由你或老师预先准备，选择目录不会下载。
                    </p>
                  </>
                ) : (
                  <div aria-label="服务器环境与数据说明">
                    <p>
                      使用服务器已有的 Python
                      环境与数据目录，本机无需准备数据副本。老师环境只做检查，不安装或升级包；数据不会自动上传。
                    </p>
                    {remoteBinding && (
                      <p>
                        服务器 Python：{remoteBinding.pythonExecutable}
                        ；服务器数据：
                        {remoteBinding.dataRoot}
                      </p>
                    )}
                    <button
                      type="button"
                      disabled={
                        !ready || !project || Boolean(busy) || activeRun
                      }
                      onClick={openServerSettings}
                    >
                      打开服务器配置
                    </button>
                  </div>
                )}
                {runMode === "local" && bridge && project && python && data && (
                  <LocalPreflight
                    key={`${project.projectId}:${project.revision}:${python.selectionId}:${data.selectionId}:${dirty}:${ready}`}
                    api={bridge.local}
                    request={{
                      projectId: project.projectId,
                      expectedRevision: project.revision,
                      pythonSelectionId: python.selectionId,
                      dataSelectionId: data.selectionId,
                    }}
                    pythonLabel={python.label}
                    dataLabel={data.label}
                    disabled={!ready || dirty || Boolean(busy) || activeRun}
                  />
                )}
                <p className="muted">
                  运行位置：{runMode === "ssh" ? "SSH 服务器" : "本机"}
                  。服务器数据不会自动上传或下载。
                </p>
              </section>

              <div className="button-row">
                <button
                  type="button"
                  disabled={!ready || !project}
                  onClick={() => {
                    if (identityVisible) setIdentityVisible(false);
                    else openServerSettings();
                  }}
                >
                  SSH 主机身份设置
                </button>
                {bridge?.packages && (
                  <button
                    type="button"
                    aria-expanded={packagesVisible}
                    onClick={() => {
                      setSettingsPanel("environment");
                      setGuideVisible(false);
                      setPackagesOpened(true);
                      setPackagesVisible((previous) => !previous);
                    }}
                  >
                    {packagesVisible ? "收起包安装计划" : "打开包安装计划"}
                  </button>
                )}
              </div>
              {identityVisible && ready && bridge && project && (
                <div
                  id="server-configuration"
                  role="region"
                  aria-label="服务器配置"
                  tabIndex={-1}
                >
                  <ServerProfiles
                    key={project.projectId}
                    api={bridge.connections}
                    environments={bridge.environments}
                    projectId={project.projectId}
                    remote={{
                      runs: bridge.runs,
                      authority:
                        !dirty &&
                        compilation?.runnable &&
                        compilation.revision === project.revision
                          ? {
                              expectedRevision: project.revision,
                              expectedProgramHash: compilation.programHash,
                            }
                          : undefined,
                      onBinding: acceptRemoteBinding,
                      onSession: acceptRemoteSession,
                    }}
                    onClose={() => setIdentityVisible(false)}
                  />
                </div>
              )}

              {packagesOpened && bridge?.packages && (
                <div hidden={!packagesVisible}>
                  <PackageManager
                    api={bridge.packages}
                    remoteSession={remoteSession}
                  />
                </div>
              )}

              {remoteSession && project && !session?.readOnly && (
                <DataUpload
                  key={`${project.projectId}:${remoteSession.scope.connectionId}`}
                  api={bridge!}
                  session={remoteSession}
                  revision={project.revision}
                  disabled={
                    !ready || dirty || saving || Boolean(busy) || activeRun
                  }
                />
              )}
            </div>
          </div>
          <div className="workbench-editor-host" hidden={settingsVisible}>
            {project && (
              <section className="workbench-canvas">
                <Suspense fallback={<p role="status">正在加载积木编辑器…</p>}>
                  <ProjectEditor
                    project={project}
                    readOnly={!writable || Boolean(busy) || activeRun}
                    selectedBlock={selectedBlock}
                    navigationRequest={blockNavigation}
                    onChange={changeWorkspaces}
                    onSelect={setSelectedBlock}
                    onHelp={tutorialHelp}
                    activeTab={viewTab}
                    onTabChange={changeTab}
                  />
                </Suspense>
              </section>
            )}
          </div>
        </div>
        <aside
          id="workbench-code"
          className="workbench-side"
          aria-label="当前工程代码对照"
          hidden={!viewCode || tutorialVisible || !project}
        >
          <div className="workbench-side-heading">
            <div>
              <h2>PyTorch 代码</h2>
              <span>只读 · 点击代码可定位积木</span>
            </div>
            <button
              type="button"
              onClick={() => showCode(false)}
              aria-label="关闭代码对照"
            >
              ×
            </button>
          </div>
          {dirty && (
            <p className="notice">正在等待当前修改保存，随后更新代码。</p>
          )}
          {compilation?.code ? (
            <CodeView
              code={compilation.code}
              spans={compilation.sourceMap ?? []}
              selectedBlock={selectedBlock}
              onSelectBlock={locateBlock}
            />
          ) : (
            <div className="workbench-code-empty">
              <p>
                {busy === "检查与编译"
                  ? "正在生成当前工程的 PyTorch 代码…"
                  : "保存并检查积木后，这里会显示完整 PyTorch 代码。"}
              </p>
              <button
                type="button"
                onClick={() => {
                  setDock("checks");
                }}
              >
                查看检查结果
              </button>
            </div>
          )}
        </aside>
        <aside
          className="workbench-side workbench-tutorial"
          aria-label="学习与教程"
          hidden={!tutorialVisible}
        >
          <div className="workbench-side-heading">
            <h2>边做边学</h2>
            <button
              type="button"
              onClick={() => setTutorialVisible(false)}
              aria-label="关闭学习面板"
            >
              ×
            </button>
          </div>
          {tutorialVisible && (
            <TutorialPanel
              topicId={tutorialTopic}
              onTopic={setTutorialTopic}
              project={project}
              compilation={compilation}
              dirty={dirty}
              canCreateExample={Boolean(
                ready &&
                bridge &&
                !restoringProject &&
                !dirty &&
                !busy &&
                !saving &&
                !activeRun,
              )}
              onExample={() => {
                void openProject(true, "mnist-cnn", true);
              }}
              onLocate={tutorialLocate}
            />
          )}
        </aside>
      </div>
      <section
        className="workbench-dock"
        data-open={dock !== null}
        data-expanded={dockExpanded}
        aria-label="检查与运行面板"
      >
        <div className="workbench-dock-toolbar">
          <div role="tablist" aria-label="检查与运行视图">
            {(
              [
                [
                  "checks",
                  `检查与问题${problemCount ? ` (${problemCount})` : ""}`,
                ],
                ["history", "运行记录"],
                ["results", "日志与结果"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                id={`dock-tab-${id}`}
                role="tab"
                aria-selected={dock === id}
                aria-controls={`dock-${id}`}
                onClick={() => setDock(dock === id ? null : id)}
              >
                {label}
              </button>
            ))}
          </div>
          {dock && (
            <div className="button-row">
              <button
                type="button"
                aria-pressed={dockExpanded}
                onClick={() => setDockExpanded((previous) => !previous)}
              >
                {dockExpanded ? "恢复面板高度" : "展开结果面板"}
              </button>
              <button type="button" onClick={() => setDock(null)}>
                收起面板
              </button>
            </div>
          )}
        </div>
        <div className="workbench-dock-body" hidden={!dock}>
          <div
            id="dock-checks"
            role="tabpanel"
            aria-labelledby="dock-tab-checks"
            hidden={dock !== "checks"}
          >
            <section className="panel" aria-labelledby="compile-heading">
              <div className="section-heading">
                <div>
                  <h2 id="compile-heading" tabIndex={-1}>
                    3. 检查与运行
                  </h2>
                  <p className="muted">
                    保存的工程与编译 revision 一致后，才能显式启动。
                  </p>
                </div>
              </div>
              {dirty && (
                <p className="notice">请先保存当前配置，再检查与运行。</p>
              )}
              {compilation ? (
                <>
                  <p role="status">
                    {compilation.runnable ? "代码检查通过" : "暂不能运行"} ·
                    revision {compilation.revision}
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
                          {diagnostic.suggestion && (
                            <p>{diagnostic.suggestion}</p>
                          )}
                          {diagnostic.origin && (
                            <button
                              type="button"
                              onClick={() =>
                                locateBlock(diagnostic.origin?.blockId ?? null)
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
                </>
              ) : (
                <p className="empty-state">尚无编译结果。检查不会启动训练。</p>
              )}
            </section>
          </div>
          <div
            id="dock-history"
            role="tabpanel"
            aria-labelledby="dock-tab-history"
            hidden={dock !== "history"}
          >
            {project && (
              <section className="panel">
                <h2 id="history-heading" tabIndex={-1}>
                  运行历史（只读快照）
                </h2>
                <p className="muted">查看旧运行不会替换当前编辑工程或映射。</p>
                {historyError && (
                  <FailureCard failure={historyError} onNavigate={navigate} />
                )}
                <button
                  type="button"
                  disabled={!ready}
                  onClick={() => {
                    setHistoryOffset(0);
                    setHistoryRefresh((value) => value + 1);
                  }}
                >
                  刷新运行历史
                </button>
                {history.length ? (
                  <ul className="history-list">
                    {history.map((item) => (
                      <li key={item.runId}>
                        <button
                          type="button"
                          onClick={() => {
                            setRun(item);
                            setDock("results");
                          }}
                        >
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

            {!project && (
              <p className="empty-state">
                打开工程后，可以在这里查看运行记录。
              </p>
            )}
          </div>
          <div
            id="dock-results"
            role="tabpanel"
            aria-labelledby="dock-tab-results"
            hidden={dock !== "results"}
          >
            {bridge && run && (
              <RunDashboard
                key={run.runId}
                api={bridge}
                initialRun={run}
                onRunUpdate={updateRun}
                remoteSession={remoteSession}
              />
            )}

            {!run && (
              <p className="empty-state">
                尚未开始训练。训练产生的日志、指标、图像和文件会显示在这里。
              </p>
            )}
          </div>
        </div>
      </section>
      <footer className="workbench-statusbar">
        <span>
          {project
            ? `${{ data: "数据处理", model: "模型结构", training: "训练管线" }[viewTab]} · ${saveStatus}`
            : "准备工程"}
        </span>
        <span>PyTorch · {runMode === "local" ? "本机运行" : "服务器运行"}</span>
      </footer>
    </main>
  );
}
