import { FailureCard, operationFailure } from "./FailureCard.js";
import type { OperationFailure } from "./FailureCard.js";
import { RuntimeErrorCard } from "./RuntimeErrorCard.js";
import { useEffect, useRef, useState } from "react";
import type {
  ArtifactRecord,
  ConnectionState,
  DesktopAPI,
  Run,
  RunSource,
  AuthenticatedConnection,
} from "../electron/bridge.js";
import {
  applyRunEvent,
  emptyEvents,
  isTerminal,
  isRunSettled,
  statusLabel,
} from "./runEvents.js";
import type { EpochPoint, RunEventState } from "./runEvents.js";
import { SnapshotCode } from "./RunSnapshot.js";
import type { SnapshotRequest } from "./RunSnapshot.js";

const LOG_WINDOW = 120_000;
export function MetricSeries({ points }: { points: EpochPoint[] }) {
  if (!points.length)
    return (
      <p className="empty-state">
        尚无真实训练指标。完成测试评估后，每轮指标会显示在这里。
      </p>
    );
  const charts = [
    {
      key: "loss" as const,
      label: "训练损失（交叉熵）",
      max: Math.max(...points.map((p) => p.loss), 0.001),
    },
    { key: "accuracy" as const, label: "测试准确率", max: 1 },
  ];
  return (
    <>
      <div className="metric-grid">
        {charts.map((chart) => {
          const coordinates = points
            .map(
              (point, i) =>
                `${24 + (i / Math.max(points.length - 1, 1)) * 352},${140 - (point[chart.key] / chart.max) * 116}`,
            )
            .join(" ");
          return (
            <figure key={chart.key}>
              <figcaption>{chart.label}</figcaption>
              <svg
                viewBox="0 0 400 164"
                role="img"
                aria-label={`${chart.label}，${points.length} 个真实 epoch 数据点`}
              >
                <path d="M24 16V140H384" className="chart-axis" />
                <polyline points={coordinates} className="chart-line" />
                {points.map((point, i) => (
                  <circle
                    key={point.epoch}
                    cx={24 + (i / Math.max(points.length - 1, 1)) * 352}
                    cy={140 - (point[chart.key] / chart.max) * 116}
                    r="3"
                    className="chart-point"
                  >
                    <title>
                      Epoch {point.epoch}：
                      {chart.key === "accuracy"
                        ? `${(point.accuracy * 100).toFixed(2)}%`
                        : point.loss.toPrecision(5)}
                    </title>
                  </circle>
                ))}
                <text x="24" y="158">
                  epoch {points[0].epoch}
                </text>
                <text x="312" y="158">
                  {points.at(-1)?.epoch}
                </text>
              </svg>
            </figure>
          );
        })}
      </div>
      <div className="table-scroll">
        <table>
          <caption>真实 epoch 记录（准确率显示为百分比）</caption>
          <thead>
            <tr>
              <th>轮次</th>
              <th>训练损失</th>
              <th>测试准确率</th>
              <th>训练 / 测试样本</th>
            </tr>
          </thead>
          <tbody>
            {points.map((point) => (
              <tr key={point.epoch}>
                <td>{point.epoch}</td>
                <td>{point.loss.toPrecision(6)}</td>
                <td>{(point.accuracy * 100).toFixed(2)}%</td>
                <td>
                  {point.trainSamples} / {point.testSamples}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
export function RunSummary({
  run,
  connection,
  device,
}: {
  run: Run;
  connection: ConnectionState;
  device?: string | null;
}) {
  return (
    <div className="run-summary">
      <strong>{statusLabel[run.status]}</strong>
      <span>
        事件连接：
        {
          {
            connected: "已连接",
            reconnecting: "重新连接中",
            closed: "已关闭",
            error: "连接异常",
          }[connection]
        }
      </span>
      <span>
        执行位置：
        {run.config.runner === "ssh"
          ? `${run.remote?.username ?? "待确认"}@${run.remote?.host ?? "服务器"}:${run.remote?.port ?? 22}`
          : "本机"}{" "}
        ·{" "}
        {run.config.executionMode === "quick"
          ? "快速检查（小样本）"
          : "完整工程参数"}
      </span>
      {run.config.runner === "ssh" && (
        <>
          <span>
            服务器读取：
            {run.connectionState === "connected"
              ? "已连接"
              : run.connectionState === "reconnecting"
                ? "等待核实原任务"
                : "已断开，执行状态可能尚未更新"}
          </span>
          <span>
            产物同步：{run.syncState}；产物校验：
            {run.remote?.artifactsVerified ? "已通过" : "尚未通过"}
          </span>
          <span>
            配置设备：{run.config.device ?? "auto"}；实际设备：
            {device ?? "等待执行事件确认"}
          </span>
          {run.config.environmentPrefix && (
            <span>Conda 环境：{run.config.environmentPrefix}</span>
          )}
        </>
      )}
      <span>
        工程 revision {run.config.projectRevision} · workers{" "}
        {run.config.numWorkers}
      </span>
    </div>
  );
}

interface RunDashboardProps {
  api: DesktopAPI;
  initialRun: Run;
  onRunUpdate: (run: Run) => void;
  remoteSession?: AuthenticatedConnection | null;
}
export function RunDashboard(props: RunDashboardProps) {
  return <RunDashboardForRun key={props.initialRun.runId} {...props} />;
}
function RunDashboardForRun({
  api,
  initialRun,
  onRunUpdate,
  remoteSession,
}: RunDashboardProps) {
  const initial = useRef(initialRun).current;
  const runId = initial.runId;
  const [run, setRun] = useState(initial);
  const [events, setEvents] = useState<RunEventState>(() => emptyEvents(runId));
  const [connection, setConnection] = useState<ConnectionState>("reconnecting");
  const [subscriptionError, setSubscriptionError] =
    useState<OperationFailure | null>(null);
  const [cancelError, setCancelError] = useState<OperationFailure | null>(null);
  const [resumeError, setResumeError] = useState<OperationFailure | null>(null);
  const [imageError, setImageError] = useState<OperationFailure | null>(null);
  const [readError, setReadError] = useState<OperationFailure | null>(null);
  const [sourceError, setSourceError] = useState<OperationFailure | null>(null);
  const [source, setSource] = useState<RunSource | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
  const [stdout, setStdout] = useState("");
  const [stderr, setStderr] = useState("");
  const [image, setImage] = useState<{
    id: string;
    dataUrl: string;
    label: string;
  } | null>(null);
  const [snapshotRequest, setSnapshotRequest] =
    useState<SnapshotRequest | null>(null);
  const snapshotVersion = useRef(0);
  function verifyRunIdentity(value: Run) {
    if (
      value.runId !== runId ||
      value.projectId !== initial.projectId ||
      value.config.runId !== runId ||
      value.config.projectId !== initial.projectId ||
      value.config.projectRevision !== initial.config.projectRevision ||
      value.config.programHash !== initial.config.programHash ||
      value.config.codeHash !== initial.config.codeHash
    )
      throw new Error("返回的运行身份与本次运行不一致，未更新运行或来源。");
  }
  function setSelectedBlock(id: string | null) {
    setSnapshotRequest(
      id === null ? null : { blockId: id, version: ++snapshotVersion.current },
    );
  }
  const [stopping, setStopping] = useState(false);
  const [resuming, setResuming] = useState(false);
  const [readGeneration, setReadGeneration] = useState(0);
  const imageRequest = useRef(0);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stdoutAfter = 0,
      stderrAfter = 0,
      terminalPolls = 0;
    let terminalEventReceived = false;
    setEvents(emptyEvents(runId));
    setStdout("");
    setStderr("");
    setSource(null);
    setSourceError(null);
    setSubscriptionError(null);
    setArtifacts([]);
    setImage(null);
    setSelectedBlock(null);
    setConnection("reconnecting");
    let unsubscribe: () => void = () => {};
    try {
      unsubscribe = api.runs.subscribe(
        runId,
        0,
        (event) => {
          if (active && event.runId === runId) {
            setEvents((previous) => applyRunEvent(previous, event));
            if (
              event.type === "process_exited" ||
              event.type === "process_spawn_failed" ||
              (event.type === "status_changed" &&
                ["SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"].includes(
                  String(event.payload.status),
                ))
            )
              terminalEventReceived = true;
          }
        },
        (state) => {
          if (active) {
            setConnection(state);
            setSubscriptionError(
              state === "error" ? operationFailure("runSubscribe", null) : null,
            );
          }
        },
      );
    } catch (reason) {
      setConnection("error");
      setSubscriptionError(operationFailure("runSubscribe", reason));
    }
    void api.runs
      .source(runId)
      .then((value) => {
        if (!active) return;
        if (
          value.projectRevision !== initial.config.projectRevision ||
          value.programHash !== initial.config.programHash ||
          value.codeHash !== initial.config.codeHash ||
          value.snapshot.projectId !== initial.projectId ||
          value.snapshot.revision !== initial.config.projectRevision
        ) {
          setSourceError(operationFailure("runSourceIdentity", null));
          return;
        }
        setSource(structuredClone(value));
      })
      .catch((reason) => {
        if (active) setSourceError(operationFailure("runSource", reason));
      });
    const poll = async () => {
      try {
        const [latest, logs, files] = await Promise.all([
          api.runs.get(runId),
          api.runs.logs(runId, stdoutAfter, stderrAfter),
          api.runs.artifacts(runId),
        ]);
        if (!active) return;
        verifyRunIdentity(latest);
        setRun(latest);
        onRunUpdate(latest);
        setReadError(null);
        stdoutAfter = logs.stdoutAfter;
        stderrAfter = logs.stderrAfter;
        setStdout((previous) => (previous + logs.stdout).slice(-LOG_WINDOW));
        setStderr((previous) => (previous + logs.stderr).slice(-LOG_WINDOW));
        setArtifacts(files.filter((item) => item.runId === runId));
        if (isRunSettled(latest) && logs.done) terminalPolls += 1;
        else terminalPolls = 0;
        if (terminalPolls >= 2 && terminalEventReceived) {
          unsubscribe();
          return;
        }
      } catch (reason) {
        if (!active) return;
        setReadError(operationFailure("runRead", reason));
      }
      if (active)
        timer = setTimeout(() => {
          void poll();
        }, 1000);
    };
    void poll();
    return () => {
      active = false;
      mounted.current = false;
      imageRequest.current += 1;
      if (timer) clearTimeout(timer);
      unsubscribe();
    };
    // The subscription belongs to the immutable run ID, not each polled snapshot.
  }, [api, runId, initial, onRunUpdate, readGeneration]);

  async function cancel() {
    setStopping(true);
    setCancelError(null);
    try {
      const updated = await api.runs.cancel(runId);
      if (mounted.current) {
        verifyRunIdentity(updated);
        setRun(updated);
        onRunUpdate(updated);
      }
    } catch (reason) {
      if (mounted.current)
        setCancelError(operationFailure("runCancel", reason));
    } finally {
      if (mounted.current) setStopping(false);
    }
  }
  async function resume() {
    if (!remoteSession) return;
    setResuming(true);
    setResumeError(null);
    try {
      const value = await api.runs.resume(
        runId,
        run.projectId,
        remoteSession.scope.connectionId,
      );
      if (mounted.current) {
        verifyRunIdentity(value);
        setRun(value);
        onRunUpdate(value);
      }
    } catch (reason) {
      if (mounted.current)
        setResumeError(operationFailure("runResume", reason));
    } finally {
      if (mounted.current) {
        setResuming(false);
        setReadGeneration((value) => value + 1);
      }
    }
  }
  const executionEnded =
    run.remote &&
    ["COMPLETED", "FAILED", "CANCELLED"].includes(run.remote.executionState);
  const sameTarget =
    !!remoteSession &&
    remoteSession.projectId === run.projectId &&
    remoteSession.username === run.remote?.username &&
    remoteSession.scope.endpoint.host === run.remote?.host &&
    remoteSession.scope.endpoint.port === run.remote?.port &&
    remoteSession.scope.hostFingerprint === run.remote?.hostFingerprint;
  async function preview(artifact: ArtifactRecord) {
    const request = ++imageRequest.current;
    setImageError(null);
    setSelectedBlock(artifact.producerBlockId);
    try {
      const result = await api.runs.image(runId, artifact.artifactId);
      if (!result.dataUrl.startsWith("data:image/png;base64,"))
        throw new Error("桥接返回了非 PNG 图像内容");
      if (mounted.current && imageRequest.current === request)
        setImage({
          id: artifact.artifactId,
          dataUrl: result.dataUrl,
          label: artifact.relativePath,
        });
    } catch (reason) {
      if (mounted.current && imageRequest.current === request)
        setImageError(operationFailure("runImage", reason));
    }
  }
  return (
    <section aria-labelledby="run-heading" className="run-workspace">
      <div className="section-heading">
        <div>
          <p className="eyebrow">运行记录</p>
          <h2 id="run-heading" tabIndex={-1}>
            本次运行
          </h2>
        </div>
        <button
          type="button"
          className="danger"
          disabled={
            isTerminal(run.status) ||
            !!executionEnded ||
            stopping ||
            run.status === "CANCELLING"
          }
          onClick={() => {
            void cancel();
          }}
        >
          {stopping || run.status === "CANCELLING"
            ? "等待停止确认…"
            : "停止本次运行"}
        </button>
      </div>
      <p className="run-id">{runId}</p>
      <RunSummary run={run} connection={connection} device={events.device} />
      {run.config.runner === "ssh" && (
        <div className="notice" role="status">
          {run.remote?.startOutcome === "unknown" && (
            <p>
              启动结果尚未确认，任务可能仍在运行。接续只检查原任务，不重新启动。
            </p>
          )}
          {run.connectionState !== "connected" && (
            <p>
              暂时无法读取服务器状态；请核对原主机身份并重新认证，再显式接续。
            </p>
          )}
          {run.remote?.cancelState === "pending" && (
            <p>停止请求待发送；尚未确认任务停止。</p>
          )}
          {run.remote?.cancelState === "acknowledged" && (
            <p>停止请求已送达，仍需等待执行侧确认停止。</p>
          )}
          <button
            type="button"
            disabled={
              !sameTarget ||
              resuming ||
              run.connectionState === "connected" ||
              (isRunSettled(run) && run.syncState === "complete")
            }
            onClick={() => void resume()}
          >
            {resuming ? "正在接续读取…" : "接续原任务（不重跑）"}
          </button>
          {!sameTarget && <p>接续需要原目标的已认证新会话。</p>}
        </div>
      )}
      {run.config.executionMode === "quick" && (
        <p className="notice">
          小样本快速检查：1 epoch，最多 1024 个训练 / 256
          个测试样本。指标不代表正式 MNIST 学习效果。
        </p>
      )}
      {[
        subscriptionError,
        sourceError,
        readError,
        cancelError,
        resumeError,
        imageError,
      ].map(
        (failure, index) =>
          failure && (
            <FailureCard
              key={index}
              failure={failure}
              actionLabel="查看运行状态"
              onNavigate={() => {
                const target = document.getElementById("run-heading");
                target?.focus();
                target?.scrollIntoView?.({ block: "start" });
              }}
            />
          ),
      )}
      {events.errors.map((item) => (
        <RuntimeErrorCard
          key={item.seq}
          diagnostic={item}
          sourceReady={Boolean(source)}
          onLocate={() => setSelectedBlock(item.blockId)}
        />
      ))}
      <section className="panel">
        <h3>训练指标</h3>
        <MetricSeries points={events.points} />
      </section>
      <section className="panel">
        <h3>输出文件</h3>
        {!artifacts.length ? (
          <p className="empty-state">尚无已登记的真实产物。</p>
        ) : (
          <ul className="artifacts">
            {artifacts.map((artifact) => (
              <li key={artifact.artifactId}>
                <div>
                  <strong>{artifact.relativePath}</strong>
                  <span>
                    {artifact.sizeBytes.toLocaleString()} 字节 ·{" "}
                    {artifact.syncState === "ready"
                      ? "已就绪"
                      : artifact.syncState}
                  </span>
                  <button
                    type="button"
                    className="text-button"
                    onClick={() => setSelectedBlock(artifact.producerBlockId)}
                  >
                    来源：{artifact.producerBlockId}
                  </button>
                </div>
                {artifact.kind === "figure" &&
                  artifact.mimeType === "image/png" && (
                    <button
                      type="button"
                      disabled={artifact.syncState !== "ready"}
                      onClick={() => {
                        void preview(artifact);
                      }}
                    >
                      查看图片
                    </button>
                  )}
              </li>
            ))}
          </ul>
        )}
        {image && (
          <figure className="image-preview">
            <img
              src={image.dataUrl}
              alt={`本次运行生成的图像：${image.label}`}
            />
            <figcaption>{image.label}</figcaption>
          </figure>
        )}
      </section>
      {source && (
        <SnapshotCode
          source={source}
          request={snapshotRequest}
          onSelectBlock={setSelectedBlock}
        />
      )}
      <section className="panel">
        <h3>终端输出（只读）</h3>
        <p className="muted">
          保留最近 {LOG_WINDOW.toLocaleString()} 个字符；stdout 与 stderr
          分开展示。
        </p>
        <details open>
          <summary>stdout</summary>
          <pre className="log" tabIndex={0}>
            {stdout || "尚无 stdout 日志。"}
          </pre>
        </details>
        <details open={Boolean(stderr)}>
          <summary>stderr</summary>
          <pre className="log stderr" tabIndex={0}>
            {stderr || "尚无 stderr 日志。"}
          </pre>
        </details>
      </section>
    </section>
  );
}
