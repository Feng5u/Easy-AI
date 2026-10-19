import { useEffect, useRef, useState } from "react";
import type {
  DesktopAPI,
  AuthenticatedConnection,
  InstallJob,
  InstallPlan,
  InstallPlanRequest,
  PackageCatalog,
  InstallSourcePreview,
  InstallJobHistory,
  InstallJobReport,
  InstallJobSummary,
} from "../electron/bridge.js";

type API = NonNullable<DesktopAPI["packages"]>;
const groups = {
  ml: "机器学习",
  dl: "深度学习",
  cv: "计算机视觉",
  nlp: "自然语言处理",
};
const states: Record<InstallJob["state"], string> = {
  AWAITING_EXECUTION: "已登记，等待执行",
  INSTALLING: "安装进行中",
  VERIFYING: "重新检查中",
  SUCCEEDED: "执行与复检通过",
  FAILED: "任务失败，需要重新检查",
  CANCEL_REQUESTED: "已请求停止，尚未确认停止",
  CANCELLED: "登记或任务已取消；不代表环境健康",
};
const logLabels: Record<string, string> = {
  PLAN_CONFIRMED: "已确认计划",
  INSTALL_EXECUTION_QUEUED: "已登记，等待唯一安装任务执行",
  INSTALL_EXECUTION_NOT_ENABLED: "执行通道未启用，尚未安装",
  INSTALL_PROGRESS: "安装任务进度记录",
  INSTALL_REPROBE_STARTED: "开始重新检查",
  INSTALL_VERIFIED: "复检合同通过",
  INSTALL_REPROBE_FAILED: "复检未通过",
  INSTALL_EXECUTION_FAILED: "安装进程失败，需要重新检查",
  INSTALL_LEDGER_WRITE_FAILED: "任务记录未能安全保存，不能继续执行",
  INSTALL_RESTART_CONFIRMATION_EXPIRED:
    "应用已重启，原确认失效；需要重新生成计划",
  INSTALL_STOP_UNCONFIRMED: "停止尚未确认",
  INSTALL_CANCELLED_NO_EXECUTION: "已取消登记，尚未执行安装",
  INSTALL_CANCELLED_REPROBE_REQUIRED: "已停止，需要重新检查",
};
const blockerLabels: Record<string, string> = {
  INSTALL_PROFILE_PLATFORM_UNSUPPORTED:
    "此CPU锁定方案仅支持本机Linux x86_64 / Python 3.11；其他平台请选择已有健康环境。",
  INSTALL_DEPENDENCIES_UNRESOLVED: "可选包尚未完成受控依赖解析，不能确认执行。",
  INSTALL_KNOWN_PACKAGE_VULNERABILITY:
    "当前候选发行元数据列有尚未修复的漏洞，暂不提供该固定来源。",
  INSTALL_NLP_CLOSURE_UNREVIEWED:
    "此NLP包的完整固定依赖闭包尚未核实，暂不支持安装。",
  INSTALL_VERSION_CONFLICT:
    "已有包版本与核心锁定约束冲突；请另用独立环境，不自动升级或降级。",
};
const size = (value: number | null) =>
  value === null ? "未知 / 待解析" : `${(value / 1024 ** 2).toFixed(1)} MiB`;
const observationLabels = {
  "managed-worker-alive": "本应用的安装 worker 当前仍存活",
  "registered-only": "本次会话仅登记，尚无安装 worker",
  historical: "历史结果记录，本次未检查当前环境",
  "stop-unconfirmed": "停止未确认；可能仍有进程或管道 owner，不可视为已停止",
};
export function PackageManager({
  api,
  remoteSession,
}: {
  api: API;
  remoteSession?: AuthenticatedConnection | null;
}) {
  const [target, setTarget] = useState<"local" | "remote">("local");
  const [ownedId, setOwnedId] = useState("");
  const [existing, setExisting] = useState(false);
  const remoteKey = remoteSession
    ? `${remoteSession.projectId}:${remoteSession.scope.connectionId}:${remoteSession.targetId}`
    : "";
  const targetKey = `${target}:${remoteKey}`;
  const currentTargetKey = useRef(targetKey);
  currentTargetKey.current = targetKey;

  const [catalog, setCatalog] = useState<PackageCatalog | null>(null);
  const [profile, setProfile] = useState<"easyai-cpu" | "teacher-existing">(
    "easyai-cpu",
  );
  const [name, setName] = useState("easyai-classroom");
  const [selected, setSelected] = useState<string[]>([
    "torch",
    "torchvision",
    "matplotlib",
  ]);
  const [plan, setPlan] = useState<InstallPlan | null>(null);
  const [job, setJob] = useState<InstallJob | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sourcePreview, setSourcePreview] =
    useState<InstallSourcePreview | null>(null);
  const [sourceAcknowledged, setSourceAcknowledged] = useState(false);
  const [sourceStatus, setSourceStatus] = useState("");
  const [history, setHistory] = useState<InstallJobHistory | null>(null);
  const [historyReport, setHistoryReport] = useState<InstallJobReport | null>(
    null,
  );
  const [historyError, setHistoryError] = useState("");
  const historySequence = useRef(0),
    reportSequence = useRef(0);
  const mounted = useRef(false),
    generation = useRef(0),
    pending = useRef(false);
  useEffect(() => {
    mounted.current = true;
    let alive = true;
    const historyTicket = ++historySequence.current;
    void api
      .history()
      .then((value) => {
        if (alive && historyTicket === historySequence.current)
          setHistory(value);
      })
      .catch(() => {
        if (alive && historyTicket === historySequence.current)
          setHistoryError(
            "已保存任务读取未完成；未修改记录或解除隔离，请重新读取。",
          );
      });
    void api
      .catalog()
      .then((value) => {
        if (alive) setCatalog(value);
      })
      .catch(() => {
        if (alive)
          setError("包目录读取未完成，请稍后重新打开应用；未执行安装。");
      });
    return () => {
      alive = false;
      mounted.current = false;
      generation.current++;
      historySequence.current++;
      reportSequence.current++;
    };
  }, [api]);
  const activeJob = Boolean(
    job && !["CANCELLED", "FAILED", "SUCCEEDED"].includes(job.state),
  );
  const locked = busy || activeJob;
  function invalidate() {
    generation.current++;
    setPlan(null);
    setAcknowledged(false);
    setError("");
    setSourcePreview(null);
    setSourceAcknowledged(false);
  }
  function refreshHistory() {
    const ticket = ++historySequence.current;
    void operation(async () => {
      const value = await api.history();
      if (mounted.current && ticket === historySequence.current) {
        setHistory(value);
        setHistoryError("");
      }
    }, "已保存任务读取未完成；不会重放安装、清理账本或解除隔离。");
  }
  function openHistoryReport(expected: InstallJobSummary) {
    const ticket = ++reportSequence.current;
    void operation(async () => {
      const value = await api.report(expected.jobId);
      if (
        value.summary.jobId !== expected.jobId ||
        value.summary.planHash !== expected.planHash ||
        value.summary.environmentId !== expected.environmentId ||
        value.recorded.jobId !== expected.jobId ||
        value.observed.jobId !== expected.jobId ||
        value.currentEnvironmentVerified !== false
      )
        throw Error("安装历史身份不符");
      if (mounted.current && ticket === reportSequence.current)
        setHistoryReport(value);
    }, "安装报告读取未完成；未重新安装或复检，也不会按旧进程标识操作。");
  }
  async function operation(
    invoke: () => Promise<void>,
    failureMessage?: string,
  ) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      await invoke();
    } catch {
      if (mounted.current)
        setError(
          failureMessage ??
            "操作结果尚未确认。请核对或刷新；同一计划重复登记是幂等的，不代表已经安装。不会自动重试。",
        );
    } finally {
      pending.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  function chooseSources() {
    const ticket = generation.current;
    setSourcePreview(null);
    setSourceAcknowledged(false);
    void operation(async () => {
      const result = await api.chooseSources({
        packageIds: [...selected] as Parameters<
          API["chooseSources"]
        >[0]["packageIds"],
      });
      if (mounted.current && ticket === generation.current && result) {
        setSourcePreview(result);
        setSourceStatus("");
      }
    }, "来源校验未完成，现配置未获替换确认。请核对来源权限、有效期和预算；不会安装或自动重试。");
  }
  function registerSources() {
    if (!sourcePreview || !sourceAcknowledged || activeJob) return;
    const expected = sourcePreview,
      ticket = generation.current;
    void operation(async () => {
      const result = await api.confirmSources({
        previewId: expected.previewId,
        previewHash: expected.previewHash,
        confirmed: true,
      });
      if (
        result.previewId !== expected.previewId ||
        result.manifestSha256 !== expected.manifestSha256 ||
        result.executionEnabled !== false
      )
        throw Error("来源登记身份不符");
      if (mounted.current && ticket === generation.current) {
        invalidate();
        setCatalog(null);
        setSourceStatus(
          "本地来源已登记，执行授权仍关闭。请经独立授权后重新生成安装计划；不会自动安装。",
        );
        const updated = await api.catalog();
        if (mounted.current) setCatalog(updated);
      }
    }, "来源登记结果尚未确认；不会自动重试或安装。请核对现配置与来源，必要时重新预览。");
  }
  function makePlan() {
    const ticket = generation.current,
      expectedTarget = currentTargetKey.current;
    if (target === "remote" && !remoteSession?.targetId) return;
    const request: InstallPlanRequest = {
      targetId: target === "remote" ? remoteSession!.targetId! : "local",
      ...(target === "remote"
        ? {
            remoteSession: {
              projectId: remoteSession!.projectId,
              connectionId: remoteSession!.scope.connectionId,
            },
          }
        : {}),
      profileId: profile,
      packageIds: [...selected] as InstallPlanRequest["packageIds"],
      ...(existing
        ? { ownedEnvironmentId: ownedId }
        : { newEnvironmentSpec: { name } }),
    };
    void operation(async () => {
      const value = await api.plan(request);
      if (
        mounted.current &&
        ticket === generation.current &&
        expectedTarget === currentTargetKey.current
      ) {
        setPlan(value);
        setAcknowledged(false);
      }
    });
  }
  function confirm() {
    if (!plan || !acknowledged || plan.blockers.length || activeJob) return;
    const ticket = generation.current,
      expected = plan;
    if (
      expected.targetId !== "local" &&
      (expected.targetId !== remoteSession?.targetId ||
        expected.targetIdentity?.projectId !== remoteSession?.projectId)
    )
      return;
    void operation(async () => {
      const value = await api.confirm({
        planId: expected.planId,
        planHash: expected.planHash,
        confirmed: true,
        networkAcknowledged: true,
      });
      if (
        value.planId !== expected.planId ||
        value.planHash !== expected.planHash ||
        value.environmentId !== expected.environmentId
      )
        throw Error("安装登记身份不符");
      if (mounted.current && ticket === generation.current) setJob(value);
    });
  }
  function jobAction(cancel: boolean) {
    if (!job) return;
    const expected = job;
    void operation(async () => {
      const value = await (cancel
        ? api.cancel(expected.jobId)
        : api.job(expected.jobId));
      if (
        value.jobId !== expected.jobId ||
        value.planHash !== expected.planHash ||
        value.environmentId !== expected.environmentId
      )
        throw Error("安装任务身份不符");
      if (mounted.current) setJob(value);
    });
  }
  function reconcile(expected: InstallJob, cancel: boolean) {
    if (
      !api.reconcile ||
      !remoteSession ||
      expected.targetId !== remoteSession.targetId ||
      expected.targetIdentity?.projectId !== remoteSession.projectId
    )
      return;
    const scope = {
      projectId: remoteSession.projectId,
      connectionId: remoteSession.scope.connectionId,
    };
    const key = currentTargetKey.current;
    void operation(async () => {
      const value = await api.reconcile!(expected.jobId, scope, cancel);
      if (
        value.jobId !== expected.jobId ||
        value.planHash !== expected.planHash ||
        value.targetId !== expected.targetId
      )
        throw Error("安装任务身份不符");
      if (mounted.current && key === currentTargetKey.current) setJob(value);
    }, "远端核验结果未知，继续保留隔离；没有重放或继续安装。请重新认证同一目标后核验。");
  }
  return (
    <section className="panel" aria-labelledby="packages-heading">
      <h2 id="packages-heading" tabIndex={-1}>
        受控包安装计划
      </h2>
      <p>
        {target === "remote"
          ? "远端方案只使用目标上已备的离线来源；执行权以固定目标策略和本次计划为准，不沿用本机授权。"
          : catalog?.executionEnabled
            ? "本机离线安装来源已获授权；是否执行仍以具体计划及本次明确确认为准。"
            : "当前可离线生成计划、明确确认登记和取消登记；真实安装执行、新环境创建与真实依赖复检尚未启用。"}
        不会修改应用 Python 或教师共享环境，也不会下载数据。
      </p>
      <p>
        目标仅限应用拥有的隔离环境，独立于工程的教师环境。任务状态保存在本机，重启不自动恢复执行；可在下方查看已保存任务的只读报告。
      </p>
      <label>
        安装目标
        <select
          aria-label="安装目标"
          disabled={locked}
          value={target}
          onChange={(event) => {
            invalidate();
            setTarget(event.target.value as "local" | "remote");
          }}
        >
          <option value="local">本机 owned 环境</option>
          <option value="remote" disabled={!remoteSession?.targetId}>
            当前已认证保存的 SSH 目标
          </option>
        </select>
      </label>
      {target === "remote" && (
        <p role="status">
          {remoteSession?.targetId
            ? `远端 ${remoteSession.scope.endpoint.host} / ${remoteSession.username}；${remoteSession.scope.hostFingerprint}。仅使用已备离线来源，默认执行关闭，不自动上传或下载。`
            : "SSH 会话已失效；请重新认证，旧计划不能沿用。"}
        </p>
      )}
      <label>
        <input
          type="checkbox"
          checked={existing}
          disabled={locked}
          onChange={(event) => {
            invalidate();
            setExisting(event.target.checked);
          }}
        />
        选择已有 owned 环境
      </label>
      {existing && (
        <label>
          owned 环境 ID
          <input
            aria-label="owned 环境 ID"
            value={ownedId}
            disabled={locked}
            onChange={(event) => {
              invalidate();
              setOwnedId(event.target.value);
            }}
          />
        </label>
      )}
      {error && <p role="alert">{error}</p>}
      <section aria-label="已保存安装任务">
        <h3>已保存安装任务与报告</h3>
        <p>
          本机账本上限64项，达到上限不会自动清理。重新打开或刷新只读记录，不重放安装、不按旧进程标识操作，也不解除停止未确认的隔离。
        </p>
        <button type="button" disabled={busy} onClick={refreshHistory}>
          刷新已保存安装任务
        </button>
        {historyError && <p role="alert">{historyError}</p>}
        {!history && !historyError && <p role="status">正在读取已保存任务…</p>}
        {history && !history.entries.length && <p>暂无已保存安装任务。</p>}
        {history && (
          <ul>
            {history.entries.map((entry) => (
              <li key={entry.jobId}>
                <p>
                  任务 {entry.jobId.slice(0, 8)} · {states[entry.state]} ·{" "}
                  {entry.recordedAt}
                </p>
                <p>
                  {observationLabels[entry.observation]}。
                  {entry.origin === "recovered"
                    ? "来自重启恢复的只读记录。"
                    : entry.origin === "external"
                      ? "来自另一实例的持久记录，不宣称其 worker 已退出。"
                      : "来自当前应用会话。"}
                </p>
                <button
                  type="button"
                  disabled={busy}
                  aria-label={`查看安装报告 ${entry.jobId}`}
                  onClick={() => openHistoryReport(entry)}
                >
                  查看报告
                </button>
              </li>
            ))}
          </ul>
        )}
        {historyReport && (
          <section aria-label="已保存安装报告">
            <h4>安装任务报告（只读快照）</h4>
            <p>
              任务：<code>{historyReport.summary.jobId}</code>；环境：
              <code>{historyReport.summary.environmentId}</code>；目标：
              {historyReport.summary.targetId ?? "local"}
            </p>
            <p>
              最后持久记录：{historyReport.summary.recordedAt}，状态：
              {states[historyReport.recorded.state]}；本次读取：
              {states[historyReport.observed.state]}。
            </p>
            <p>
              {observationLabels[historyReport.summary.observation]}
              。本实例管理的worker：
              {historyReport.summary.workerAlive
                ? "读取时仍存活"
                : "没有存活证明；不等于确认其他进程已退出"}
              。
            </p>
            {historyReport.summary.statusCode ===
              "INSTALL_RESTART_CONFIRMATION_EXPIRED" && (
              <p>旧等待确认已失效；如仍需安装，请重新生成计划并明确确认。</p>
            )}
            <p>
              {historyReport.recorded.verified
                ? "账本记载当时已通过复检；本次查看未重新检查当前环境，不能据此启动训练。"
                : "账本没有通过复检的证明，环境不能视为健康。"}
            </p>
            <p>
              {historyReport.observed.changesPossible
                ? "可能已有变更，不承诺回滚。"
                : "记录未报告安装变更；本次未探测环境。"}
            </p>
            <p>
              计划指纹：<code>{historyReport.summary.planHash}</code>
              。以下为已保存生命周期摘要，不是安装器原始输出：
            </p>
            <ul>
              {historyReport.recorded.logs.map((code, index) => (
                <li key={index}>
                  {Object.hasOwn(logLabels, code)
                    ? logLabels[code]
                    : "任务状态记录"}
                </li>
              ))}
            </ul>
            <button
              type="button"
              disabled={busy}
              onClick={() => openHistoryReport(historyReport.summary)}
            >
              重新读取此报告
            </button>
          </section>
        )}
      </section>
      <section aria-label="本地离线来源">
        <h3>本地离线来源</h3>
        <p>
          由可信操作者准备来源清单及本地文件。选择后只读校验，不下载或运行文件；登记不创建或搬入执行授权，预算与授权截止时间不会延长。
        </p>
        <button
          type="button"
          disabled={
            locked ||
            target === "remote" ||
            !selected.length ||
            profile === "teacher-existing"
          }
          onClick={chooseSources}
        >
          选择本地离线来源
        </button>
        {sourceStatus && <p role="status">{sourceStatus}</p>}
        {sourcePreview && (
          <div aria-label="来源核验预览">
            <p>
              来源清单：{sourcePreview.sourceName}；SHA256：
              <code>{sourcePreview.manifestSha256}</code>
            </p>
            <p>
              解释器：{sourcePreview.launcher.name}，
              {size(sourcePreview.launcher.bytes)}；SHA256：
              <code>{sourcePreview.launcher.sha256}</code>
            </p>
            <p>
              运行组件：{sourcePreview.moduleName}；完整目录校验：
              <code>{sourcePreview.moduleTreeSha256}</code>
            </p>
            <p>
              启动档案 {sourcePreview.bootstrap.length} 个，wheel{" "}
              {sourcePreview.wheels.length} 个；档案和wheel合计{" "}
              {size(sourcePreview.sourceBytes)}，实际解包占用未知。磁盘预算{" "}
              {size(sourcePreview.diskBudgetBytes)}，每条命令时限{" "}
              {sourcePreview.executionSeconds} 秒。
            </p>
            <p>
              来源校验通过；原授权截止 {sourcePreview.authorizationExpires}
              ，本预览截止 {sourcePreview.expiresAt}
              。无论清单是否声明执行授权，本次登记都保持执行授权关闭；安装须另行授权并明确确认具体计划。
            </p>
            <details>
              <summary>查看文件核验清单</summary>
              <ul>
                {[...sourcePreview.bootstrap, ...sourcePreview.wheels].map(
                  (item) => (
                    <li key={item.name}>
                      {item.name}，{size(item.bytes)}；SHA256：
                      <code>{item.sha256}</code>
                    </li>
                  ),
                )}
              </ul>
            </details>
            <label>
              <input
                type="checkbox"
                checked={sourceAcknowledged}
                disabled={locked}
                onChange={(event) =>
                  setSourceAcknowledged(event.target.checked)
                }
              />
              我已确认来源来自可信操作者；仅登记来源，不授权执行。
            </label>
            <button
              type="button"
              disabled={locked || !sourceAcknowledged}
              onClick={registerSources}
            >
              确认登记本地来源
            </button>
          </div>
        )}
      </section>
      {!catalog ? (
        <p role="status">正在读取本地包目录…</p>
      ) : (
        <>
          <label className="field">
            环境方案
            <select
              aria-label="环境方案"
              value={profile}
              disabled={locked}
              onChange={(event) => {
                invalidate();
                setProfile(event.target.value as typeof profile);
              }}
            >
              <option value="easyai-cpu">
                easyai-cpu：Linux x86_64 / Python 3.11 的锁定 CPU 组合
              </option>
              <option value="teacher-existing">
                teacher-existing：教师现有环境，只检查
              </option>
            </select>
          </label>
          {profile === "teacher-existing" && (
            <p role="status">
              教师现有环境只读。请通过原环境检查入口选择已有环境，此处不生成写入计划。
            </p>
          )}
          <label className="field">
            新环境显示名称
            <input
              value={name}
              maxLength={32}
              disabled={locked}
              onChange={(event) => {
                invalidate();
                setName(event.target.value);
              }}
            />
          </label>
          <p>
            以英文字母开头，仅字母、数字、下划线或连字符；实际目录由后端分配，不接受路径。
          </p>
          <button
            type="button"
            disabled={locked}
            onClick={() => {
              invalidate();
              setSelected(["torch", "torchvision", "matplotlib"]);
            }}
          >
            选择 MNIST 最小依赖
          </button>
          <p>
            CPU
            方案保留完整核心依赖闭包，单包和整组使用同一计划器。可选包未取得受控解析结果时会阻止确认，不自动改动核心版本。
          </p>
          {Object.entries(groups).map(([group, label]) => {
            const cards = catalog.packages.filter(
                (item) => item.group === group,
              ),
              all = cards.every((item) => selected.includes(item.packageId));
            return (
              <details key={group}>
                <summary>
                  {label}（{cards.length} 包）
                </summary>
                <label>
                  <input
                    type="checkbox"
                    checked={all}
                    disabled={locked}
                    onChange={(event) => {
                      invalidate();
                      const ids = cards.map((item) => item.packageId),
                        checked = event.target.checked;
                      setSelected((previous) =>
                        checked
                          ? [...new Set([...previous, ...ids])]
                          : previous.filter((item) => !ids.includes(item)),
                      );
                    }}
                  />
                  选择整组{label}
                </label>
                <ul>
                  {cards.map((item) => (
                    <li key={item.packageId}>
                      <label>
                        <input
                          type="checkbox"
                          checked={selected.includes(item.packageId)}
                          disabled={locked}
                          onChange={(event) => {
                            invalidate();
                            const checked = event.target.checked;
                            setSelected((previous) =>
                              checked
                                ? [...new Set([...previous, item.packageId])]
                                : previous.filter(
                                    (id) => id !== item.packageId,
                                  ),
                            );
                          }}
                        />
                        {item.packageId} · {item.purpose}
                      </label>
                      <p>
                        import：{item.importName}
                        ；已安装状态：尚未探测；目标版本：
                        {item.targetVersion ?? "待解析"}
                      </p>
                      <p>{item.dependencyNote}</p>
                    </li>
                  ))}
                </ul>
              </details>
            );
          })}
          <button
            type="button"
            disabled={
              locked ||
              profile === "teacher-existing" ||
              selected.length === 0 ||
              (target === "remote" && !remoteSession?.targetId) ||
              (existing
                ? !/^[a-f0-9-]{36}$/.test(ownedId)
                : !/^[A-Za-z][A-Za-z0-9_-]{0,31}$/.test(name))
            }
            onClick={makePlan}
          >
            只生成安装计划
          </button>
        </>
      )}
      {busy && <p role="status">正在处理本地计划或登记…</p>}
      {plan && (
        <section aria-label="安装计划预览">
          <h3>核对计划</h3>
          <p>
            环境：{plan.environmentName}；方案：{plan.profileId}；目标：
            {plan.platform}
          </p>
          <p>
            目标：{plan.targetId}；
            {plan.targetIdentity
              ? `${plan.targetIdentity.endpoint.host} / ${plan.targetIdentity.username} / ${plan.targetIdentity.root}`
              : "本机应用根"}
            ；远端实际可用容量：{size(plan.remoteFreeBytes ?? null)}。
            基线指纹：<code>{plan.baselineFingerprint}</code>
          </p>
          <p>
            约束 hash：<code>{plan.constraintsHash}</code>
          </p>
          <p>
            {plan.requiresNetwork
              ? "未来执行需要联网：是。"
              : plan.targetId === "local"
                ? "本次来源已在本机，不下载依赖。"
                : "本次来源已在远端目标，不下载依赖；SSH 通道本身仍需要连接。"}
            {plan.executionEnabled
              ? plan.targetId === "local"
                ? "确认后将创建或修改本机应用受控环境并实际复检。"
                : "确认后将创建或修改远端应用受控环境并实际复检。"
              : "本次仅登记，不执行安装。"}
          </p>
          {plan.runtimeFingerprint && (
            <p>
              执行来源指纹：<code>{plan.runtimeFingerprint}</code>；bootstrap
              目标文件：{size(plan.bootstrapBytes ?? null)}；磁盘预算：
              {size(plan.diskBudgetBytes ?? null)}；单进程时间预算：
              {plan.executionSeconds ?? "未知"} 秒。
            </p>
          )}
          <p>
            下载量估计：{size(plan.downloadBytes)}；wheel 解包量估计：
            {size(plan.installedBytes)}。
          </p>
          <p>
            {plan.sizeStatus === "locked-wheel-estimate"
              ? "来自已锁定的 wheel 元数据，未扣除本机缓存；解包量不是环境总磁盘占用。"
              : "依赖或目标平台尚未解析，不提供猜测体积。"}
          </p>
          <table>
            <thead>
              <tr>
                <th>distribution</th>
                <th>原版本</th>
                <th>目标版本</th>
                <th>计划动作</th>
              </tr>
            </thead>
            <tbody>
              {plan.packageChanges.map((item) => (
                <tr key={item.packageId}>
                  <td>
                    {item.packageId}
                    {item.requested ? "（已选择）" : "（核心依赖）"}
                  </td>
                  <td>{item.previousVersion ?? "未安装 / 新环境"}</td>
                  <td>{item.targetVersion ?? "待解析"}</td>
                  <td>
                    {item.action === "add"
                      ? "新增"
                      : item.action === "keep"
                        ? "保持"
                        : "尚未解析或冲突"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {plan.blockers.length > 0 && (
            <div role="alert">
              <p>
                计划被阻止：平台、依赖尚未解析或核心版本冲突。请选择已配置环境或单独的兼容方案；不会自动升级。
              </p>
              <ul>
                {plan.blockers.map((code, index) => (
                  <li key={index}>
                    {Object.hasOwn(blockerLabels, code)
                      ? blockerLabels[code]
                      : "计划约束尚未核实，不能确认。"}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <label>
            <input
              type="checkbox"
              checked={acknowledged}
              disabled={busy || activeJob || plan.blockers.length > 0}
              onChange={(event) => setAcknowledged(event.target.checked)}
            />
            {plan.executionEnabled
              ? "我已核对目标、来源、包变更及预算，确认执行受控安装"
              : "我已核对目标、包变更、约束及未来联网需求；本次仅登记计划"}
          </label>
          <button
            type="button"
            disabled={
              !acknowledged || busy || activeJob || plan.blockers.length > 0
            }
            onClick={confirm}
          >
            {plan.executionEnabled
              ? "确认计划并执行受控安装"
              : "确认计划并登记任务"}
          </button>
        </section>
      )}
      {historyReport &&
        historyReport.observed.targetId &&
        historyReport.observed.targetId !== "local" && (
          <button
            disabled={busy || activeJob}
            onClick={() => setJob(historyReport.observed)}
          >
            打开远端任务核验
          </button>
        )}
      {job && (
        <section aria-label="安装任务登记">
          <h3>安装任务</h3>
          <p role="status">
            {Object.hasOwn(states, job.state)
              ? states[job.state]
              : "任务状态未核实"}
          </p>
          <p>
            {job.changesPossible
              ? "可能已有变更，不能承诺完整回滚。"
              : "尚未执行安装变更。"}
          </p>
          <p>
            {job.needsReprobe
              ? "环境仍需真实复检；取消不代表健康。"
              : job.executionEnabled
                ? "本次受控环境已通过依赖与张量复检；不代表数据或训练验收。"
                : "已通过复检合同；真实执行通道仍需另行验收。"}
          </p>
          {job.targetId && job.targetId !== "local" && (
            <>
              <p>
                远端任务；断线或重启后保持隔离。重新认证同一目标后可只读核验或请求取消；不会重放安装。静止收口后仍需重新计划与复检。
              </p>
              <button
                disabled={
                  busy ||
                  !remoteSession ||
                  job.targetId !== remoteSession.targetId
                }
                onClick={() => reconcile(job, false)}
              >
                核验远端停止状态
              </button>
              <button
                disabled={
                  busy ||
                  !remoteSession ||
                  job.targetId !== remoteSession.targetId
                }
                onClick={() => reconcile(job, true)}
              >
                请求远端 owner 停止
              </button>
            </>
          )}
          <ul>
            {job.logs.map((code, index) => (
              <li key={index}>
                {Object.hasOwn(logLabels, code)
                  ? logLabels[code]
                  : "任务状态记录"}
              </li>
            ))}
          </ul>
          <button
            type="button"
            disabled={busy}
            onClick={() => jobAction(false)}
          >
            刷新安装任务
          </button>
          <button
            type="button"
            disabled={busy || !activeJob}
            onClick={() => jobAction(true)}
          >
            取消登记或请求停止
          </button>
        </section>
      )}
    </section>
  );
}
