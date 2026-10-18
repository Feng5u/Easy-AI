import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { Event, Run } from "../electron/bridge.js";
import {
  applyRunEvent,
  emptyEvents,
  isTerminal,
  isRunSettled,
} from "./runEvents.js";
import { MetricSeries, RunSummary } from "./RunDashboard.js";
import { CodeView } from "./CodeView.js";

function metric(seq: number, epoch = 1): Event {
  return {
    runId: "current",
    seq,
    source: "runtime",
    sourceSeq: seq,
    timestamp: "2026-10-18T00:00:00Z",
    type: "epoch_completed",
    blockId: "train-loop",
    payload: {
      epoch,
      train_loss: 0.25,
      test_accuracy: 0.973,
      train_samples: 8,
      test_samples: 4,
    },
  };
}

describe("authoritative runtime event view", () => {
  it("filters old runs and duplicate event sequences", () => {
    const initial = emptyEvents("current");
    expect(applyRunEvent(initial, { ...metric(1), runId: "old" })).toBe(
      initial,
    );
    const accepted = applyRunEvent(initial, metric(1));
    expect(applyRunEvent(accepted, metric(1))).toBe(accepted);
    const duplicateEpoch = applyRunEvent(accepted, metric(2));
    expect(duplicateEpoch.after).toBe(2);
    expect(duplicateEpoch.points).toHaveLength(1);
    const next = applyRunEvent(duplicateEpoch, metric(3, 2));
    expect(next.points).toHaveLength(2);
    expect(next.points[0]).toEqual({
      epoch: 1,
      loss: 0.25,
      accuracy: 0.973,
      trainSamples: 8,
      testSamples: 4,
    });
  });
  it("rejects malformed or nonfinite metric values without creating chart data", () => {
    for (const payload of [
      { ...metric(1).payload, train_loss: Number.NaN },
      { ...metric(1).payload, test_accuracy: 97.3 },
      { ...metric(1).payload, epoch: 0 },
      { ...metric(1).payload, test_samples: -1 },
      { train_loss: 0.2 },
    ]) {
      expect(
        applyRunEvent(emptyEvents("current"), { ...metric(1), payload }).points,
      ).toEqual([]);
    }
  });
  it("keeps runtime errors separate from connection status and bounds the visible errors", () => {
    let state = emptyEvents("current");
    for (let seq = 1; seq <= 30; seq++)
      state = applyRunEvent(state, {
        ...metric(seq),
        type: "runtime_error",
        payload: { message: `failure ${seq}` },
      });
    expect(state.errors).toHaveLength(20);
    expect(state.errors.at(-1)?.message).toBe("failure 30");
    expect(state.points).toEqual([]);
  });
  it("renders empty state without preset curves; renders fractional accuracy once as a percentage", () => {
    const empty = renderToStaticMarkup(
      createElement(MetricSeries, { points: [] }),
    );
    expect(empty).toContain("尚无真实训练指标");
    expect(empty).not.toContain("polyline");
    const actual = applyRunEvent(emptyEvents("current"), metric(1));
    const markup = renderToStaticMarkup(
      createElement(MetricSeries, { points: actual.points }),
    );
    expect(markup).toContain("97.30%");
    expect(markup).not.toContain("9730");
    expect(markup).toContain("0.250000");
    expect(markup).toContain("polyline");
  });
  it("shows real run state independently from a disconnected event channel", () => {
    const run = {
      status: "RUNNING",
      config: { executionMode: "quick", projectRevision: 3, numWorkers: 0 },
    } as Run;
    const markup = renderToStaticMarkup(
      createElement(RunSummary, { run, connection: "error" }),
    );
    expect(markup).toContain("运行中");
    expect(markup).toContain("连接异常");
    expect(markup).toContain("快速检查（小样本）");
    expect(markup).not.toContain("运行失败");
    expect(isTerminal("RUNNING")).toBe(false);
    expect(isTerminal("CANCELLING")).toBe(false);
    expect(isTerminal("CANCELLED")).toBe(true);
    expect(isTerminal("SUCCEEDED")).toBe(true);
  });
  it("escapes code text and marks the exact source-map line", () => {
    const markup = renderToStaticMarkup(
      createElement(CodeView, {
        code: "<script>literal</script>\nx = model(x)",
        selectedBlock: "conv",
        spans: [
          {
            file: "train.py",
            startLine: 2,
            endLine: 2,
            origin: { blockId: "conv", workspace: "model" },
            kind: "semantic",
          },
        ],
      }),
    );
    expect(markup).not.toContain("<script>");
    expect(markup).toContain("&lt;script&gt;");
    expect(markup.match(/code-selected/g)).toHaveLength(1);
  });
});
it("remote completion waits for artifact settlement and keeps independent execution evidence", () => {
  const run = {
    status: "COMPLETED",
    syncState: "syncing",
    connectionState: "disconnected",
    config: {
      runner: "ssh",
      executionMode: "full",
      projectRevision: 1,
      device: "cpu",
      numWorkers: 2,
    },
    remote: {
      executionState: "COMPLETED",
      startOutcome: "acknowledged",
      cancelState: "resolved",
      artifactsVerified: false,
      host: "historical.invalid",
      port: 2222,
      username: "historical-user",
      hostFingerprint: "SHA256:historical",
    },
  } as Run;
  expect(isRunSettled(run)).toBe(false);
  const markup = renderToStaticMarkup(
    createElement(RunSummary, { run, connection: "error" }),
  );
  expect(markup).toContain("historical-user");
  expect(markup).toContain("historical.invalid");
  expect(markup).not.toContain("运行成功");
  expect(isRunSettled({ ...run, syncState: "error" })).toBe(true);
  expect(
    isRunSettled({
      ...run,
      status: "CANCELLING",
      remote: {
        ...run.remote!,
        executionState: "RUNNING",
        cancelState: "acknowledged",
      },
    }),
  ).toBe(false);
});

it("retains structured runtime exception and original record without aliasing caller data", () => {
  const event = {
    runId: "structured",
    seq: 1,
    source: "runtime",
    sourceSeq: 1,
    timestamp: "2026-10-18T00:00:00Z",
    type: "runtime_error",
    blockId: "old-block",
    payload: {
      exceptionType: "NameError",
      message: "private raw error",
      variableName: "train_data",
      file: "train.py",
      line: 42,
      frames: [
        { filename: "/private/train.py", lineno: 42, function: "train" },
      ],
    },
  } as import("../electron/bridge.js").Event;
  const original = structuredClone(event);
  const result = applyRunEvent(emptyEvents("structured"), event).errors[0];
  expect(result).toMatchObject({
    exceptionType: "NameError",
    variableName: "train_data",
    file: "train.py",
    line: 42,
    message: "private raw error",
    blockId: "old-block",
  });
  expect(result.original).toEqual(original);
  event.payload.message = "caller changed later";
  expect(result.original).toEqual(original);
  expect(result.message).toBe("private raw error");
});

it("unknown runtime types and private fields cannot enter the safe card, including prototype names", async () => {
  const { RuntimeErrorCard } = await import("./RuntimeErrorCard.js");
  for (const exceptionType of [
    "__proto__",
    "constructor",
    "private-exception",
  ]) {
    const event = {
      runId: "safe",
      seq: 1,
      source: "runtime",
      sourceSeq: 1,
      timestamp: "2026-10-18T00:00:00Z",
      type: "runtime_error",
      blockId: "token=secret",
      payload: {
        exceptionType,
        message: "alice@private.example /home/alice",
        variableName: "password=secret",
        file: "C:\\Users\\Alice\\private.py",
        line: -1,
      },
    } as import("../electron/bridge.js").Event;
    const diagnostic = applyRunEvent(emptyEvents("safe"), event).errors[0];
    const locate = () => {
      throw new Error("must not automatically locate");
    };
    const markup = renderToStaticMarkup(
      createElement(RuntimeErrorCard, {
        diagnostic,
        sourceReady: false,
        onLocate: locate,
      }),
    );
    for (const text of [
      exceptionType,
      "private.example",
      "/home/alice",
      "Alice",
      "password=",
      "token=",
      "secret",
    ])
      expect(markup).not.toContain(text);
    expect(markup).toContain("RUNTIME_UNCLASSIFIED");
    expect(markup).toContain("disabled");
    expect(diagnostic.original).toEqual(event);
    expect(diagnostic.line).toBeNull();
  }
});
