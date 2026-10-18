import { useEffect, useRef, useState } from "react";
import type {
  DesktopAPI,
  InstallJob,
  InstallPlan,
  InstallPlanRequest,
  PackageCatalog,
} from "../electron/bridge.js";

type API = NonNullable<DesktopAPI["packages"]>;
const groups = {
  ml: "机器学习",
  dl: "深度学习",
  cv: "计算机视觉",
  nlp: "自然语言处理",
};
const states: Record<InstallJob["state"], string> = {
  AWAITING_EXECUTION: "已登记，等待执行（本版执行未启用）",
  INSTALLING: "安装进行中",
  VERIFYING: "重新检查中",
  SUCCEEDED: "执行与复检合同通过（真实执行通道未启用）",
  FAILED: "任务失败，需要重新检查",
  CANCEL_REQUESTED: "已请求停止，尚未确认停止",
  CANCELLED: "登记或任务已取消；不代表环境健康",
};
const logLabels: Record<string, string> = {
  PLAN_CONFIRMED: "已确认计划",
  INSTALL_EXECUTION_NOT_ENABLED: "执行通道未启用，尚未安装",
  INSTALL_PROGRESS: "安装任务进度记录",
  INSTALL_REPROBE_STARTED: "开始重新检查",
  INSTALL_VERIFIED: "复检合同通过",
  INSTALL_REPROBE_FAILED: "复检未通过",
  INSTALL_STOP_UNCONFIRMED: "停止尚未确认",
  INSTALL_CANCELLED_NO_EXECUTION: "已取消登记，尚未执行安装",
  INSTALL_CANCELLED_REPROBE_REQUIRED: "已停止，需要重新检查",
};
const blockerLabels: Record<string, string> = {
  INSTALL_PROFILE_PLATFORM_UNSUPPORTED:
    "此CPU锁定方案仅支持本机Linux x86_64 / Python 3.11；其他平台请选择已有健康环境。",
  INSTALL_DEPENDENCIES_UNRESOLVED: "可选包尚未完成受控依赖解析，不能确认执行。",
  INSTALL_VERSION_CONFLICT:
    "已有包版本与核心锁定约束冲突；请另用独立环境，不自动升级或降级。",
};
const size = (value: number | null) =>
  value === null ? "未知 / 待解析" : `${(value / 1024 ** 2).toFixed(1)} MiB`;
export function PackageManager({ api }: { api: API }) {
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
  const mounted = useRef(false),
    generation = useRef(0),
    pending = useRef(false);
  useEffect(() => {
    mounted.current = true;
    let alive = true;
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
  }
  async function operation(invoke: () => Promise<void>) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      await invoke();
    } catch {
      if (mounted.current)
        setError(
          "操作结果尚未确认。请核对或刷新；同一计划重复登记是幂等的，不代表已经安装。不会自动重试。",
        );
    } finally {
      pending.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  function makePlan() {
    const ticket = generation.current;
    const request: InstallPlanRequest = {
      targetId: "local",
      profileId: profile,
      packageIds: [...selected] as InstallPlanRequest["packageIds"],
      newEnvironmentSpec: { name },
    };
    void operation(async () => {
      const value = await api.plan(request);
      if (mounted.current && ticket === generation.current) {
        setPlan(value);
        setAcknowledged(false);
      }
    });
  }
  function confirm() {
    if (!plan || !acknowledged || plan.blockers.length || activeJob) return;
    const ticket = generation.current,
      expected = plan;
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
  return (
    <section className="panel" aria-labelledby="packages-heading">
      <h2 id="packages-heading" tabIndex={-1}>
        受控包安装计划
      </h2>
      <p>
        当前可离线生成计划、明确确认登记和取消登记；真实安装执行、新环境创建与真实依赖复检尚未启用。不会修改应用
        Python 或教师共享环境，也不会下载数据。
      </p>
      <p>
        目标是本机应用管理的新环境，独立于当前工程。任务登记仅保留在本次应用会话；关闭应用不会恢复执行。
      </p>
      {error && <p role="alert">{error}</p>}
      {!catalog ? (
        <p role="status">正在读取本地包目录…</p>
      ) : (
        <>
          <label className="field">
            环境方案
            <select
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
              !/^[A-Za-z][A-Za-z0-9_-]{0,31}$/.test(name)
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
            基线指纹：<code>{plan.baselineFingerprint}</code>
          </p>
          <p>
            约束 hash：<code>{plan.constraintsHash}</code>
          </p>
          <p>未来执行需要联网：是；本次仅登记，不会联网安装。</p>
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
            我已核对目标、包变更、约束及未来联网需求；本次仅登记计划
          </label>
          <button
            type="button"
            disabled={
              !acknowledged || busy || activeJob || plan.blockers.length > 0
            }
            onClick={confirm}
          >
            确认计划并登记任务
          </button>
        </section>
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
              : "已通过复检合同；真实执行通道仍需另行验收。"}
          </p>
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
