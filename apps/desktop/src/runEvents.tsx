import type { Event as RuntimeEvent, Run } from "../electron/bridge.js";

export interface EpochPoint {
  epoch: number;
  loss: number;
  accuracy: number;
  trainSamples: number;
  testSamples: number;
}
export interface RunEventState {
  runId: string;
  after: number;
  points: EpochPoint[];
  device: string | null;
  errors: { seq: number; blockId: string | null; message: string }[];
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
    next.errors = [
      ...state.errors,
      { seq: event.seq, blockId: event.blockId ?? null, message },
    ].slice(-20);
  }
  return next;
}
