import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { DesktopAPI } from "../electron/bridge.js";
import {
  LOG_BLOCKS,
  LOG_BOOKMARKS,
  LOG_PAGE_BYTES,
  LOG_ROW_HEIGHT,
  LOG_ROW_CHARACTERS,
  LOG_VIEW_ROWS,
  logRows,
  logText,
  readLogPages,
  visibleLogRows,
} from "./logWindow.js";
import type { LogStream, LogWindow } from "./logWindow.js";

interface Props {
  api: DesktopAPI;
  runId: string;
  stream: LogStream;
  live: LogWindow;
  otherEnd: number;
}
type Mode =
  | { kind: "live" }
  | { kind: "paused"; window: LogWindow }
  | {
      kind: "history";
      window: LogWindow;
      previous: number[];
      dropped: boolean;
    };

export function RunLogViewer(props: Props) {
  return <LogStreamViewer key={`${props.runId}:${props.stream}`} {...props} />;
}

function LogStreamViewer({ api, runId, stream, live, otherEnd }: Props) {
  const [mode, setMode] = useState<Mode>({ kind: "live" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [notice, setNotice] = useState("");
  const [scrollTop, setScrollTop] = useState(0);
  const viewport = useRef<HTMLDivElement>(null);
  const generation = useRef(0);
  const pending = useRef(false);
  const mounted = useRef(true);
  const window = mode.kind === "live" ? live : mode.window;
  const text = useMemo(() => logText(window), [window]);
  const rows = useMemo(() => logRows(text), [text]);
  const visible = visibleLogRows(rows.length, scrollTop);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      generation.current += 1;
    };
  }, []);
  useLayoutEffect(() => {
    const host = viewport.current;
    if (!host || mode.kind === "paused") return;
    const top =
      mode.kind === "live"
        ? Math.max(0, host.scrollHeight - host.clientHeight)
        : 0;
    host.scrollTop = top;
    setScrollTop(host.scrollTop);
  }, [window, mode, rows.length]);

  function resume() {
    generation.current += 1;
    setMode({ kind: "live" });
    setError(false);
    setNotice("");
    // A retired request still occupies its physical slot until finally.
  }

  async function page(start: number, previous: number[], dropped: boolean) {
    if (pending.current) return;
    pending.current = true;
    const request = ++generation.current;
    setBusy(true);
    setError(false);
    setNotice("");
    if (mode.kind === "live") setMode({ kind: "paused", window: live });
    const offsets = {
      stdout: stream === "stdout" ? start : otherEnd,
      stderr: stream === "stderr" ? start : otherEnd,
    };
    try {
      const value = await api.runs.logs(runId, offsets.stdout, offsets.stderr);
      const chunk = readLogPages(value, offsets)[stream];
      if (!mounted.current || request !== generation.current) return;
      if (chunk.end === chunk.start) {
        setNotice(
          value.done
            ? "本次双路读取已确认日志末尾。"
            : "当前暂无新的完整文本，日志可能仍在增长；可稍后再读。",
        );
        return;
      }
      setMode({
        kind: "history",
        window: { start: chunk.start, end: chunk.end, chunks: [chunk] },
        previous: previous.slice(-LOG_BOOKMARKS),
        dropped: dropped || previous.length > LOG_BOOKMARKS,
      });
      if (value.done) setNotice("本次双路读取已确认日志末尾。");
    } catch {
      if (mounted.current && request === generation.current) setError(true);
    } finally {
      pending.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  return (
    <section className="run-log-stream" aria-label={`${stream} 日志查看器`}>
      <h4>{stream}</h4>
      <div className="run-log-controls">
        <button
          type="button"
          onClick={() => {
            if (mode.kind === "live") setMode({ kind: "paused", window: live });
            else resume();
          }}
        >
          {mode.kind === "live" ? "暂停自动滚动" : "恢复实时"} {stream}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void page(0, [], false)}
        >
          从头查看 {stream}
        </button>
        <button
          type="button"
          disabled={busy || mode.kind !== "history" || !mode.previous.length}
          onClick={() => {
            if (mode.kind === "history" && mode.previous.length)
              void page(
                mode.previous.at(-1)!,
                mode.previous.slice(0, -1),
                mode.dropped,
              );
          }}
        >
          上一页 {stream}
        </button>
        <button
          type="button"
          disabled={busy || mode.kind !== "history"}
          onClick={() => {
            if (mode.kind === "history")
              void page(
                mode.window.end,
                [...mode.previous, mode.window.start],
                mode.dropped,
              );
          }}
        >
          下一页 {stream}
        </button>
      </div>
      <p className="muted">
        {mode.kind === "live"
          ? "实时尾窗"
          : mode.kind === "paused"
            ? "已暂停滚动"
            : "历史页"}
        ：显示字节 [{window.start.toLocaleString()},{" "}
        {window.end.toLocaleString()})；实时已读取至 {live.end.toLocaleString()}{" "}
        字节。
      </p>
      <p className="muted">
        每页最多 {LOG_PAGE_BYTES.toLocaleString()} 字节，实时最多保留{" "}
        {LOG_BLOCKS} 块；暂停与查看历史均不停止后台采集。
      </p>
      {window.start > 0 && (
        <p className="muted">
          此视图不含更早的字节，可从头分页读取；页首或页尾可能位于一行中间。
        </p>
      )}
      {mode.kind !== "live" && live.end > window.end && (
        <p className="muted">
          此视图之后另有 {(live.end - window.end).toLocaleString()}{" "}
          字节已被实时读取；恢复实时显示最新有界尾窗，更早内容仍可分页查看。
        </p>
      )}
      {mode.kind === "history" && mode.dropped && (
        <p className="muted">
          仅保留最近 {LOG_BOOKMARKS} 个回退位置，更早的页请从头读取。
        </p>
      )}
      {busy && <p role="status">正在读取 {stream} 历史页…</p>}
      {error && (
        <p role="alert">此页日志读取失败，当前内容和实时游标保持不变。</p>
      )}
      {notice && <p role="status">{notice}</p>}
      {!text && <p>尚无 {stream} 日志。</p>}
      <div
        ref={viewport}
        className={`log run-log-viewport ${stream}`}
        style={{ height: LOG_ROW_HEIGHT * LOG_VIEW_ROWS }}
        role="list"
        aria-label={`${stream} 虚拟文本窗口`}
        tabIndex={0}
        onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
      >
        <div
          className="run-log-spacer"
          style={{ height: rows.length * LOG_ROW_HEIGHT }}
        >
          {rows.slice(visible.start, visible.end).map((row, index) => (
            <div
              key={visible.start + index}
              className="run-log-row"
              style={{
                top: (visible.start + index) * LOG_ROW_HEIGHT,
                height: LOG_ROW_HEIGHT,
                lineHeight: `${LOG_ROW_HEIGHT}px`,
              }}
              role="listitem"
              aria-posinset={visible.start + index + 1}
              aria-setsize={rows.length}
            >
              {row}
            </div>
          ))}
        </div>
      </div>
      <p className="muted">
        本页共 {rows.length.toLocaleString()} 个显示片段，长行按最多{" "}
        {LOG_ROW_CHARACTERS} 个字符折段；片段不是原始行号，可滚动查看完整文本。
      </p>
    </section>
  );
}
