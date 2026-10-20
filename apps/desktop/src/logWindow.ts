import type { RunLogs } from "../electron/bridge.js";

export const LOG_PAGE_BYTES = 32768;
export const LOG_BLOCKS = 4;
export const LOG_BOOKMARKS = 64;
export const LOG_ROW_CHARACTERS = 256;
export const LOG_ROW_HEIGHT = 20;
export const LOG_VIEW_ROWS = 16;
export const LOG_OVERSCAN = 4;
export type LogStream = "stdout" | "stderr";
export interface LogChunk {
  start: number;
  end: number;
  text: string;
}
export interface LogWindow {
  start: number;
  end: number;
  chunks: LogChunk[];
}
export type LogPair = Record<LogStream, LogWindow>;

export function emptyLogPair(): LogPair {
  return {
    stdout: { start: 0, end: 0, chunks: [] },
    stderr: { start: 0, end: 0, chunks: [] },
  };
}

export function readLogPages(
  value: RunLogs,
  offsets: Record<LogStream, number>,
) {
  if (!value || typeof value.done !== "boolean")
    throw new Error("日志分页响应无效。");
  const pages = {} as Record<LogStream, LogChunk>;
  for (const stream of ["stdout", "stderr"] as const) {
    const start = offsets[stream];
    const end = value[stream === "stdout" ? "stdoutAfter" : "stderrAfter"];
    const text = value[stream];
    if (
      !Number.isSafeInteger(start) ||
      start < 0 ||
      !Number.isSafeInteger(end) ||
      end < start ||
      end - start > LOG_PAGE_BYTES ||
      typeof text !== "string" ||
      text.length > end - start ||
      (end > start && text.length === 0)
    )
      throw new Error("日志分页范围或内容无效。");
    // Returned cursors count ORIGINAL bytes. Re-encoding U+FFFD from an
    // invalid UTF-8 byte would inflate its size and corrupt the next offset.
    pages[stream] = { start, end, text };
  }
  return pages;
}

export function appendLogChunk(window: LogWindow, chunk: LogChunk): LogWindow {
  if (chunk.start !== window.end) throw new Error("日志读取范围不连续。");
  if (chunk.end === chunk.start) return window;
  const chunks = [...window.chunks];
  const last = chunks.at(-1);
  // Coalesce small polls, so the tail is not limited to four seconds of text.
  if (last && chunk.end - last.start <= LOG_PAGE_BYTES)
    chunks[chunks.length - 1] = {
      start: last.start,
      end: chunk.end,
      text: last.text + chunk.text,
    };
  else chunks.push(chunk);
  const bounded = chunks.slice(-LOG_BLOCKS);
  return { start: bounded[0].start, end: chunk.end, chunks: bounded };
}

export function appendRunLogs(previous: LogPair, value: RunLogs): LogPair {
  const pages = readLogPages(value, {
    stdout: previous.stdout.end,
    stderr: previous.stderr.end,
  });
  // Both streams are validated before either cursor/window can be committed.
  return {
    stdout: appendLogChunk(previous.stdout, pages.stdout),
    stderr: appendLogChunk(previous.stderr, pages.stderr),
  };
}

export function logText(window: LogWindow): string {
  return window.chunks.map((chunk) => chunk.text).join("");
}

export function logRows(text: string): string[] {
  const rows: string[] = [];
  let row = "";
  let count = 0;
  let previousCR = false;
  let wrapped = false;
  for (const character of text) {
    if (character === "\n" && previousCR) {
      previousCR = false;
      continue;
    }
    previousCR = character === "\r";
    if (["\n", "\r", "\u2028", "\u2029"].includes(character)) {
      if (!wrapped) rows.push(row);
      row = "";
      count = 0;
      wrapped = false;
    } else {
      row += character;
      wrapped = false;
      if (++count === LOG_ROW_CHARACTERS) {
        rows.push(row);
        row = "";
        count = 0;
        wrapped = true;
      }
    }
  }
  if (row) rows.push(row);
  return rows;
}

export function visibleLogRows(total: number, scrollTop: number) {
  const first = Math.min(
    Math.max(0, total - LOG_VIEW_ROWS),
    Math.max(0, Math.floor(scrollTop / LOG_ROW_HEIGHT)),
  );
  return {
    start: Math.max(0, first - LOG_OVERSCAN),
    end: Math.min(total, first + LOG_VIEW_ROWS + LOG_OVERSCAN),
  };
}
