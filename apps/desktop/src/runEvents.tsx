import type { Event as RuntimeEvent, Run } from "../electron/bridge.js";

export interface EpochPoint {
  epoch: number;
  loss: number;
  accuracy: number;
  trainSamples: number;
  testSamples: number;
}
export interface RuntimeLocation {
  codeHash: string;
  nameState:
    "registered" | "unregistered" | "not_matched" | "ambiguous" | "unavailable";
  referenceCheck: "passed" | "failed" | "unavailable";
  precision: "semantic" | "scaffold" | "none";
  reason: string;
  blockId: string | null;
  workspace: "data" | "model" | "training" | null;
  line: number | null;
}
function runtimeLocation(event: RuntimeEvent): RuntimeLocation | null {
  const raw = event.payload.applicationLocation;
  if (raw === undefined) return null; // Legacy record: retain the existing coarse event source.
  const invalid: RuntimeLocation = {
    codeHash: "",
    nameState: "unavailable",
    referenceCheck: "unavailable",
    precision: "none",
    reason: "INVALID_LOCATION",
    blockId: null,
    workspace: null,
    line: null,
  };
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return invalid;
  const value = raw as Record<string, unknown>;
  if (
    value.version !== 1 ||
    value.runId !== event.runId ||
    value.eventSeq !== event.seq ||
    typeof value.codeHash !== "string" ||
    !/^[a-f0-9]{64}$/.test(value.codeHash)
  )
    return invalid;
  const reasons = [
    "FRAMES_MISSING",
    "RUNTIME_CODE_UNVERIFIED",
    "FILE_IDENTITY_MISMATCH",
    "FRAMES_INVALID",
    "NO_GENERATED_FRAME",
    "LINE_OUT_OF_RANGE",
    "SOURCE_MAP_INVALID",
    "NO_SOURCE_SPAN",
    "VERIFIED_GENERATED_FRAME",
    "SOURCE_UNVERIFIED",
  ];
  if (typeof value.reason !== "string" || !reasons.includes(value.reason))
    return invalid;
  if (value.precision === "none")
    return { ...invalid, codeHash: value.codeHash, reason: value.reason };
  const origin = value.origin as Record<string, unknown> | null;
  if (
    (value.precision !== "semantic" && value.precision !== "scaffold") ||
    value.reason !== "VERIFIED_GENERATED_FRAME" ||
    !origin ||
    typeof origin.blockId !== "string" ||
    !origin.blockId ||
    origin.blockId.length > 256 ||
    typeof origin.workspace !== "string" ||
    !["data", "model", "training"].includes(origin.workspace) ||
    typeof value.line !== "number" ||
    !Number.isSafeInteger(value.line) ||
    value.line < 1
  )
    return invalid;
  return {
    codeHash: value.codeHash,
    nameState:
      typeof value.nameState === "string" &&
      [
        "registered",
        "unregistered",
        "not_matched",
        "ambiguous",
        "unavailable",
      ].includes(value.nameState)
        ? (value.nameState as RuntimeLocation["nameState"])
        : "unavailable",
    referenceCheck:
      typeof value.referenceCheck === "string" &&
      ["passed", "failed", "unavailable"].includes(value.referenceCheck)
        ? (value.referenceCheck as RuntimeLocation["referenceCheck"])
        : "unavailable",
    precision: value.precision,
    reason: value.reason,
    blockId: origin.blockId,
    workspace: origin.workspace as "data" | "model" | "training",
    line: value.line,
  };
}
export interface RuntimeDiagnostic {
  seq: number;
  blockId: string | null;
  message: string;
  exceptionType: string | null;
  variableName: string | null;
  file: string | null;
  line: number | null;
  // Keep the original structured record for local diagnosis; never render it as a summary.
  original: RuntimeEvent;
  location: RuntimeLocation | null;
}
export interface RunEventState {
  runId: string;
  after: number;
  points: EpochPoint[];
  device: string | null;
  errors: RuntimeDiagnostic[];
}
export const isTerminal = (status: Run["status"]) =>
  ["SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"].includes(status);
export const isRunSettled = (run: Run) =>
  run.config.runner === "ssh"
    ? !!run.remote &&
      ["COMPLETED", "FAILED", "CANCELLED"].includes(
        run.remote.executionState,
      ) &&
      ["complete", "error"].includes(run.syncState)
    : isTerminal(run.status);
export const statusLabel: Record<Run["status"], string> = {
  CREATED: "已创建",
  PRECHECKING: "检查中",
  STAGING: "准备中",
  STARTING: "启动中",
  RUNNING: "运行中",
  CLEANUP_PENDING: "等待进程清理确认",
  COMPLETED: "执行已结束，产物尚未完整验证",
  SUCCEEDED: "已成功完成",
  FAILED: "运行失败",
  CANCELLING: "正在停止",
  CANCELLED: "已停止",
  INTERRUPTED: "运行中断",
};
export function emptyEvents(runId: string): RunEventState {
  return { runId, after: 0, points: [], errors: [], device: null };
}
export function applyRunEvent(
  state: RunEventState,
  event: RuntimeEvent,
): RunEventState {
  if (
    event.runId !== state.runId ||
    !Number.isSafeInteger(event.seq) ||
    event.seq <= state.after
  )
    return state;
  const next = { ...state, after: event.seq };
  if (
    event.type === "device_selected" &&
    typeof event.payload.device === "string" &&
    event.payload.device.length <= 64
  )
    next.device = event.payload.device;
  if (event.type === "epoch_completed") {
    const {
      epoch,
      train_loss: loss,
      test_accuracy: accuracy,
      train_samples: trainSamples,
      test_samples: testSamples,
    } = event.payload;
    if (
      typeof epoch !== "number" ||
      !Number.isSafeInteger(epoch) ||
      epoch < 1 ||
      typeof loss !== "number" ||
      !Number.isFinite(loss) ||
      loss < 0 ||
      typeof accuracy !== "number" ||
      !Number.isFinite(accuracy) ||
      accuracy < 0 ||
      accuracy > 1 ||
      typeof trainSamples !== "number" ||
      !Number.isSafeInteger(trainSamples) ||
      trainSamples < 1 ||
      typeof testSamples !== "number" ||
      !Number.isSafeInteger(testSamples) ||
      testSamples < 1 ||
      state.points.some((point) => point.epoch === epoch)
    )
      return next;
    next.points = [
      ...state.points,
      { epoch, loss, accuracy, trainSamples, testSamples },
    ];
  }
  if (event.type === "runtime_error") {
    const message =
      typeof event.payload.message === "string"
        ? event.payload.message
        : "运行过程报告了错误，请查看 stderr。";
    const location = runtimeLocation(event);
    next.errors = [
      ...state.errors,
      {
        seq: event.seq,
        blockId: location ? location.blockId : (event.blockId ?? null),
        location,
        message,
        exceptionType:
          typeof event.payload.exceptionType === "string"
            ? event.payload.exceptionType
            : null,
        variableName:
          typeof event.payload.variableName === "string"
            ? event.payload.variableName
            : null,
        file:
          typeof event.payload.file === "string" ? event.payload.file : null,
        line:
          typeof event.payload.line === "number" &&
          Number.isSafeInteger(event.payload.line) &&
          event.payload.line > 0
            ? event.payload.line
            : null,
        original: structuredClone(event),
      },
    ].slice(-20);
  }
  return next;
}
