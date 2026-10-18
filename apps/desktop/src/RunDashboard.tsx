import { useEffect, useRef, useState } from "react";
import type {
  ArtifactRecord,
  ConnectionState,
  DesktopAPI,
  Run,
  RunSource,
} from "../electron/bridge.js";
import {
  applyRunEvent,
  emptyEvents,
  isTerminal,
  statusLabel,
} from "./runEvents.js";
import type { EpochPoint, RunEventState } from "./runEvents.js";
import { SnapshotCode } from "./CodeView.js";

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
}: {
  run: Run;
  connection: ConnectionState;
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
        执行位置：本机 ·{" "}
        {run.config.executionMode === "quick"
          ? "快速检查（小样本）"
          : "完整工程参数"}
      </span>
      <span>
        工程 revision {run.config.projectRevision} · workers{" "}
        {run.config.numWorkers}
      </span>
    </div>
  );
}

export function RunDashboard({
  api,
  initialRun,
  onRunUpdate,
}: {
  api: DesktopAPI;
  initialRun: Run;
  onRunUpdate: (run: Run) => void;
}) {
  const initial = useRef(initialRun).current;
  const runId = initial.runId;
  const [run, setRun] = useState(initial);
  const [events, setEvents] = useState<RunEventState>(() => emptyEvents(runId));
  const [connection, setConnection] = useState<ConnectionState>("reconnecting");
  const [connectionMessage, setConnectionMessage] = useState("");
  const [error, setError] = useState("");
  const [readError, setReadError] = useState("");
  const [source, setSource] = useState<RunSource | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
  const [stdout, setStdout] = useState("");
  const [stderr, setStderr] = useState("");
  const [image, setImage] = useState<{
    id: string;
    dataUrl: string;
    label: string;
  } | null>(null);
  const [selectedBlock, setSelectedBlock] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);
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
    setRun(initial);
    setEvents(emptyEvents(runId));
    setStdout("");
    setStderr("");
    setSource(null);
    setArtifacts([]);
    setImage(null);
    setSelectedBlock(null);
    setError("");
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
              (event.type === "status_changed" &&
                ["SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"].includes(
                  String(event.payload.status),
                ))
            )
              terminalEventReceived = true;
          }
        },
        (state, message) => {
          if (active) {
            setConnection(state);
            setConnectionMessage(message ?? "");
          }
        },
      );
    } catch (reason) {
      setConnection("error");
      setConnectionMessage(`无法订阅运行事件：${String(reason)}`);
    }
    void api.runs
      .source(runId)
      .then((value) => {
        if (active) setSource(value);
      })
      .catch((reason) => {
        if (active) setError(`无法读取运行快照：${String(reason)}`);
      });
    const poll = async () => {
      try {
        const [latest, logs, files] = await Promise.all([
          api.runs.get(runId),
          api.runs.logs(runId, stdoutAfter, stderrAfter),
          api.runs.artifacts(runId),
        ]);
        if (!active) return;
        setRun(latest);
        onRunUpdate(latest);
        setReadError("");
        stdoutAfter = logs.stdoutAfter;
        stderrAfter = logs.stderrAfter;
        setStdout((previous) => (previous + logs.stdout).slice(-LOG_WINDOW));
        setStderr((previous) => (previous + logs.stderr).slice(-LOG_WINDOW));
        setArtifacts(files.filter((item) => item.runId === runId));
        if (isTerminal(latest.status) && logs.done) terminalPolls += 1;
        else terminalPolls = 0;
        if (terminalPolls >= 2 && terminalEventReceived) {
          unsubscribe();
          return;
        }
      } catch (reason) {
        if (!active) return;
        setReadError(
          `读取运行结果失败；不会因此将训练判为失败：${String(reason)}`,
        );
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
  }, [api, runId, initial, onRunUpdate]);

  async function cancel() {
    setStopping(true);
    setError("");
    try {
      const updated = await api.runs.cancel(runId);
      if (mounted.current) {
        setRun(updated);
        onRunUpdate(updated);
      }
    } catch (reason) {
      if (mounted.current) setError(`停止请求未确认：${String(reason)}`);
    } finally {
      if (mounted.current) setStopping(false);
    }
  }
  async function preview(artifact: ArtifactRecord) {
    const request = ++imageRequest.current;
    setError("");
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
        setError(`图片尚不可用：${String(reason)}`);
    }
  }
  return (
    <section aria-labelledby="run-heading" className="run-workspace">
      <div className="section-heading">
        <div>
          <p className="eyebrow">运行记录</p>
          <h2 id="run-heading">本次运行</h2>
        </div>
        <button
          type="button"
          className="danger"
          disabled={
            isTerminal(run.status) || stopping || run.status === "CANCELLING"
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
      <RunSummary run={run} connection={connection} />
      {run.config.executionMode === "quick" && (
        <p className="notice">
          小样本快速检查：1 epoch，最多 1024 个训练 / 256
          个测试样本。指标不代表正式 MNIST 学习效果。
        </p>
      )}
      {connectionMessage && (
        <p className="notice" role="status">
          {connectionMessage}
        </p>
      )}
      {readError && (
        <p className="notice" role="status">
          {readError}
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {events.errors.map((item) => (
        <div className="error" role="alert" key={item.seq}>
          <p>{item.message}</p>
          {item.blockId && (
            <button
              type="button"
              onClick={() => setSelectedBlock(item.blockId)}
            >
              查看源积木 {item.blockId}
            </button>
          )}
        </div>
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
          selectedBlock={selectedBlock}
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
