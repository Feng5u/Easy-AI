import { useEffect, useRef, useState } from "react";
import type { TransferHistory } from "../../../packages/contracts/types/TransferHistory.js";
import type {
  DesktopAPI,
  AuthenticatedConnection,
  SelectionResult,
  TransferPlan,
  TransferJob,
} from "../electron/bridge.js";

const terminal = (job: TransferJob) =>
  ["COMPLETED", "CANCELLED", "FAILED"].includes(job.status);
export function DataUpload({
  api,
  session,
  revision,
  disabled,
}: {
  api: DesktopAPI;
  session: AuthenticatedConnection;
  revision: number;
  disabled: boolean;
}) {
  const [history, setHistory] = useState<TransferHistory[]>([]);
  const [slot, setSlot] = useState<string | null>(null);
  const [selection, setSelection] = useState<SelectionResult | null>(null);
  const [megabytes, setMegabytes] = useState(256);
  const [files, setFiles] = useState(64);
  const [seconds, setSeconds] = useState(120);
  const [plan, setPlan] = useState<TransferPlan | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [job, setJob] = useState<TransferJob | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const epoch = useRef(0);
  const readRequest = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const scope = {
    projectId: session.projectId,
    connectionId: session.scope.connectionId,
  };
  useEffect(() => {
    epoch.current++;
    setHistory([]);
    setSlot(null);
    setSelection(null);
    setPlan(null);
    setConfirmed(false);
    setJob(null);
    setUncertain(false);
    setError("");
    setBusy(false);
    return () => {
      epoch.current++;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [session.projectId, session.scope.connectionId, revision]);
  if (!api.dataTransfers) return null;
  const transfers = api.dataTransfers;
  const active = uncertain || (job !== null && !terminal(job));
  const valid = (value: TransferJob) =>
    value.projectId === scope.projectId &&
    value.connectionId === scope.connectionId;
  function accept(value: TransferJob, generation: number) {
    if (generation !== epoch.current) return;
    if (!valid(value)) {
      setError("上传回执与当前会话不一致，状态未确认。");
      return;
    }
    setUncertain(false);
    setJob((previous) =>
      previous?.transferId === value.transferId && terminal(previous)
        ? previous
        : value,
    );
    if (!terminal(value))
      timer.current = setTimeout(() => {
        void read(value.transferId, generation);
      }, 1000);
  }
  async function read(identity: string, generation = epoch.current) {
    const request = ++readRequest.current;
    if (timer.current) clearTimeout(timer.current);
    try {
      const value = await transfers.get(identity, scope);
      if (request === readRequest.current) accept(value, generation);
    } catch {
      if (generation === epoch.current && request === readRequest.current)
        setError("读取上传状态失败，不代表任务已停止；请重试读取或请求停止。");
    }
  }
  async function loadHistory() {
    if (!transfers.history) return;
    const generation = epoch.current;
    setBusy(true);
    setError("");
    try {
      const rows = await transfers.history(scope.projectId);
      if (generation === epoch.current) setHistory(rows);
    } catch {
      if (generation === epoch.current)
        setError("本机上传记录读取失败；未连接服务器。");
    } finally {
      if (generation === epoch.current) setBusy(false);
    }
  }
  function selectSlot(value: string | null) {
    epoch.current++;
    setSlot(value);
    setSelection(null);
    setPlan(null);
    setConfirmed(false);
    setJob(null);
    setUncertain(false);
    setError("");
  }
  async function choose() {
    const generation = ++epoch.current;
    setBusy(true);
    setError("");
    setPlan(null);
    setConfirmed(false);
    try {
      const value = await api.selections.pick("data");
      if (generation === epoch.current && value) setSelection(value);
    } catch {
      if (generation === epoch.current) setError("数据目录选择未完成。");
    } finally {
      if (generation === epoch.current) setBusy(false);
    }
  }
  async function preview() {
    if (!selection) return;
    const generation = ++epoch.current;
    setBusy(true);
    setError("");
    setPlan(null);
    setConfirmed(false);
    setJob(null);
    try {
      const request = {
        ...scope,
        expectedRevision: revision,
        dataSelectionId: selection.selectionId,
        budget: { maxBytes: megabytes * 1024 * 1024, maxFiles: files, seconds },
      };
      const value = slot
        ? await transfers.inspect?.(slot, request)
        : await transfers.plan(request);
      if (!value) throw new Error("unsupported-recovery");
      if (generation !== epoch.current) return;
      if (
        value.projectId !== scope.projectId ||
        value.connectionId !== scope.connectionId ||
        value.writesStarted !== false
      )
        throw new Error("foreign-plan");
      setPlan(value);
    } catch {
      if (generation === epoch.current)
        setError(
          "上传计划未完成或预算/目录不受支持；没有开始上传。请保留源数据并重新选择或预览。",
        );
    } finally {
      if (generation === epoch.current) setBusy(false);
    }
  }
  async function start(retry = false) {
    if (!plan || (!confirmed && !retry)) return;
    const generation = epoch.current;
    setBusy(true);
    setError("");
    setConfirmed(false);
    setUncertain(true); // Intent sent, outcome unknown until a validated job reply.
    try {
      accept(
        await transfers.confirm({
          ...scope,
          planId: plan.planId,
          planHash: plan.planHash,
          confirmed: true,
        }),
        generation,
      );
    } catch {
      if (generation === epoch.current)
        setError(
          "上传开始未确认；不要据此认为远端没有写入。请保留计划，重试同一计划确认可查询既有任务。",
        );
    } finally {
      if (generation === epoch.current) setBusy(false);
    }
  }
  async function cancel() {
    const identity = job?.transferId ?? (uncertain ? plan?.planId : undefined);
    if (!identity) return;
    const generation = ++epoch.current;
    setError("");
    if (timer.current) clearTimeout(timer.current);
    try {
      accept(await transfers.cancel(identity, scope), generation);
    } catch {
      if (generation === epoch.current)
        setError("停止请求未确认；上传可能仍在清理，请重试读取。");
    } finally {
      if (generation === epoch.current) setBusy(false);
    }
  }
  function budgetChanged() {
    setPlan(null);
    setConfirmed(false);
  }
  return (
    <section className="panel" aria-label="显式上传本地数据">
      <h3>上传本地数据</h3>
      <p>
        优先使用老师已准备的远端数据。此操作仅在确认后上传所选目录；不会随训练自动上传，也不包含代码
        Bundle；仅传输确认清单中的文件。请选择专门的数据目录，确认其中没有凭据或私钥。
      </p>
      <p>
        目标账号：{session.username}；指纹：{session.scope.hostFingerprint}
      </p>
      {transfers.history && transfers.inspect && (
        <div>
          <button
            type="button"
            disabled={busy || active}
            onClick={() => void loadHistory()}
          >
            查看本机上传记录（不连接服务器）
          </button>
          <p>
            历史不证明远端任务已停止或数据完整。重新选源后，检查将读取本机和远端文件的完整SHA256；不同内容、身份或未知文件会阻断，不删除未知partial。
          </p>
          {history.map((item) => (
            <div key={item.transferId}>
              <span>
                {item.targetPath} · {item.fileCount} 文件 · {item.totalBytes}{" "}
                字节 · 上次{item.lastCompleted ? "已核验完成" : "未确认完成"}
              </span>
              <button
                type="button"
                disabled={
                  disabled ||
                  busy ||
                  active ||
                  item.targetId !== session.targetId ||
                  item.targetRevision !== session.targetRevision
                }
                onClick={() => selectSlot(item.transferId)}
              >
                选择此上传重新检查
              </button>
            </div>
          ))}
          {slot && (
            <>
              <p>
                补传目标任务：{slot}。须重新选择相同内容的源目录并明确确认。
              </p>
              <button
                type="button"
                disabled={busy || active}
                onClick={() => selectSlot(null)}
              >
                改为新建上传
              </button>
            </>
          )}
        </div>
      )}
      <button
        type="button"
        disabled={disabled || busy || active}
        onClick={() => void choose()}
      >
        选择上传数据目录
      </button>
      <p>源目录：{selection?.label ?? "未选择"}</p>
      <label>
        最大文件数
        <input
          type="number"
          min={1}
          max={256}
          value={files}
          disabled={busy || active}
          onChange={(e) => {
            setFiles(Number(e.target.value));
            budgetChanged();
          }}
        />
      </label>
      <label>
        最大源数据 MiB
        <input
          type="number"
          min={1}
          max={256}
          value={megabytes}
          disabled={busy || active}
          onChange={(e) => {
            setMegabytes(Number(e.target.value));
            budgetChanged();
          }}
        />
      </label>
      <label>
        传输超时秒数
        <input
          type="number"
          min={1}
          max={120}
          value={seconds}
          disabled={busy || active}
          onChange={(e) => {
            setSeconds(Number(e.target.value));
            budgetChanged();
          }}
        />
      </label>
      <button
        type="button"
        disabled={disabled || busy || active || !selection}
        onClick={() => void preview()}
      >
        {slot ? "核对源并检查原上传（只读SHA256）" : "预览上传计划（不写远端）"}
      </button>
      {plan && (
        <div>
          <p>源目录：{plan.sourceLabel}</p>
          <p>应用管理目标：{plan.targetPath}</p>
          {plan.slotId && (
            <p>
              保留原目录；缺少 {plan.missingFiles} 文件，已校验可复用{" "}
              {plan.reusedBytes}{" "}
              字节。只补缺文件，不覆盖不同内容；确认前不写远端。
            </p>
          )}
          <p>
            {plan.fileCount} 文件，共 {plan.totalBytes} 字节；预算{" "}
            {plan.budget.maxBytes} 字节／{plan.budget.maxFiles} 文件／
            {plan.budget.seconds} 秒。计划最多有效 {plan.expiresInSeconds} 秒。
          </p>
          <p>
            源数据字节预算不含 SFTP
            协议及回读校验流量；校验会读取远端文件。中断保留任务专用部分目录，不覆盖未知文件，不自动重传。
          </p>
          <label>
            <input
              type="checkbox"
              checked={confirmed}
              disabled={busy || active}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            我确认源目录、目标目录、文件数量与预算，并明确上传这些数据。
          </label>
          <button
            type="button"
            disabled={disabled || busy || active || !confirmed}
            onClick={() => void start()}
          >
            确认并上传数据
          </button>
        </div>
      )}
      {uncertain && plan && (
        <div role="status">
          <p>
            上传开始尚未确认；可能已经写入远端。停止请求也覆盖尚未开始的确认意图。
          </p>
          <button type="button" onClick={() => void cancel()}>
            请求停止未确认上传
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => void start(true)}
          >
            重试同一计划确认
          </button>
          <button type="button" onClick={() => void read(plan.planId)}>
            重新读取未确认上传
          </button>
        </div>
      )}
      {job && (
        <div role="status">
          <p>
            上传状态：{job.status}；已发送 {job.sentBytes}/{job.totalBytes}{" "}
            字节；已复用 {job.reusedBytes ?? 0} 字节；终检 {job.verifiedBytes}/
            {job.totalBytes} 字节、
            {job.completedFiles}/{job.fileCount} 文件。
          </p>
          {job.errorCode && (
            <p>
              上传未完成；请保留任务目录，检查来源、预算与已认证目标后重试。
            </p>
          )}
          {job.status === "COMPLETED" ? (
            <p>
              数据传输和回读核验完成：{job.targetPath}。这不代表 Dataset
              已就绪；请用该远端路径重新进行环境与数据探测，再绑定运行。
            </p>
          ) : (
            <p>
              部分数据可能保留在任务专用目录；取消请求和连接断开都不等于清理完成。
            </p>
          )}
          {!terminal(job) && (
            <>
              <button type="button" onClick={() => void cancel()}>
                请求停止上传
              </button>
              <button type="button" onClick={() => void read(job.transferId)}>
                重新读取上传状态
              </button>
            </>
          )}
        </div>
      )}
      {busy && <p role="status">正在处理数据上传请求…</p>}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
