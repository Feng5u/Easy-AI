import { expect, it } from "vitest";
import {
  LOG_BLOCKS,
  LOG_PAGE_BYTES,
  LOG_ROW_CHARACTERS,
  appendRunLogs,
  emptyLogPair,
  logRows,
  logText,
  readLogPages,
  visibleLogRows,
} from "./logWindow.js";
import type { RunLogs } from "../electron/bridge.js";

it("keeps small polls and large dual-stream logs bounded without changing prior views", () => {
  let pair = emptyLogPair();
  for (let n = 0; n < 100; n++)
    pair = appendRunLogs(pair, {
      stdout: "x",
      stdoutAfter: n + 1,
      stderr: "",
      stderrAfter: 0,
      done: false,
    });
  expect(logText(pair.stdout)).toBe("x".repeat(100));
  const pinned = pair;
  for (let n = 0; n < 100; n++) {
    const before = pair;
    pair = appendRunLogs(pair, {
      stdout: "o".repeat(LOG_PAGE_BYTES),
      stdoutAfter: pair.stdout.end + LOG_PAGE_BYTES,
      stderr: "e".repeat(LOG_PAGE_BYTES),
      stderrAfter: pair.stderr.end + LOG_PAGE_BYTES,
      done: false,
    });
    for (const stream of ["stdout", "stderr"] as const) {
      expect(pair[stream].chunks.length).toBeLessThanOrEqual(LOG_BLOCKS);
      expect(pair[stream].end - pair[stream].start).toBeLessThanOrEqual(
        LOG_BLOCKS * LOG_PAGE_BYTES,
      );
      expect(logText(pair[stream]).length).toBeLessThanOrEqual(
        LOG_BLOCKS * LOG_PAGE_BYTES,
      );
      expect(before[stream].end).toBeLessThan(pair[stream].end);
    }
  }
  expect(logText(pinned.stdout)).toBe("x".repeat(100));
  expect(pinned.stderr.end).toBe(0);
  expect(pair.stdout.start).toBeGreaterThan(0);
});

it("uses opaque original byte cursors for Unicode, replacement and pending EOF", () => {
  const first = appendRunLogs(emptyLogPair(), {
    stdout: "😀中�",
    stdoutAfter: 8, // 4 + 3 + one invalid byte, not its UTF-8 re-encoding
    stderr: "",
    stderrAfter: 0,
    done: false,
  });
  const pending = appendRunLogs(first, {
    stdout: "",
    stdoutAfter: 8,
    stderr: "",
    stderrAfter: 0,
    done: false,
  });
  expect(pending.stdout).toBe(first.stdout);
  const completed = appendRunLogs(pending, {
    stdout: "文�",
    stdoutAfter: 13, // one complete character and two incomplete EOF bytes
    stderr: "e",
    stderrAfter: 1,
    done: true,
  });
  expect(logText(completed.stdout)).toBe("😀中�文�");
  expect(completed.stdout.end).toBe(13);
  expect(completed.stderr.end).toBe(1);
});

it.each(["backward", "fraction", "oversize", "text", "done"])(
  "rejects %s replies atomically, keeping both live cursors unchanged",
  (variant) => {
    const before = emptyLogPair();
    const response: RunLogs = {
      stdout: "valid",
      stdoutAfter: 5,
      stderr: "",
      stderrAfter: 0,
      done: false,
    };
    if (variant === "backward") response.stderrAfter = -1;
    if (variant === "fraction") response.stderrAfter = 0.5;
    if (variant === "oversize") response.stderrAfter = LOG_PAGE_BYTES + 1;
    if (variant === "text") response.stderr = "unaccounted";
    if (variant === "done") Object.assign(response, { done: "yes" });
    expect(() => appendRunLogs(before, response)).toThrow();
    expect(before).toEqual(emptyLogPair());
  },
);

it("reads history with independent offsets without changing live ranges", () => {
  const live = appendRunLogs(emptyLogPair(), {
    stdout: "live",
    stdoutAfter: 4,
    stderr: "err",
    stderrAfter: 3,
    done: false,
  });
  const saved = JSON.stringify(live);
  expect(
    readLogPages(
      {
        stdout: "old",
        stdoutAfter: 3,
        stderr: "",
        stderrAfter: 3,
        done: false,
      },
      { stdout: 0, stderr: 3 },
    ).stdout,
  ).toEqual({ start: 0, end: 3, text: "old" });
  expect(JSON.stringify(live)).toBe(saved);
});

it("preserves every long-line codepoint and handles visual newlines before fixed-height virtualization", () => {
  const long = "😀中".repeat(1500);
  const rows = logRows(long);
  expect(rows.join("")).toBe(long);
  expect(rows.every((row) => [...row].length <= LOG_ROW_CHARACTERS)).toBe(true);
  expect(rows.some((row) => /[\uD800-\uDBFF]$/.test(row))).toBe(false);
  expect(logRows("a\r\nb\rc\nd\u2028e\u2029f")).toEqual([
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
  ]);
  expect(logRows("x".repeat(256) + "\nnext")).toEqual([
    "x".repeat(256),
    "next",
  ]);
  const many = logRows("line\n".repeat(LOG_PAGE_BYTES));
  for (const scroll of [0, 17, 500, 2_000_000]) {
    const visible = visibleLogRows(many.length, scroll);
    expect(visible.end - visible.start).toBeLessThanOrEqual(24);
    expect(visible.start).toBeGreaterThanOrEqual(0);
    expect(visible.end).toBeLessThanOrEqual(many.length);
  }
  expect(logRows("")).toEqual([]);
});
