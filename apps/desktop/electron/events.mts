import type { Event } from "./bridge.js";

const types = new Set<Event["type"]>([
  "runtime_started",
  "device_selected",
  "progress",
  "epoch_completed",
  "artifact_created",
  "runtime_error",
  "pipeline_cancelled",
  "pipeline_completed",
  "process_exited",
  "process_spawn_failed",
  "status_changed",
]);
export class EventProtocolError extends Error {}
export class EventStreamInterrupted extends Error {}
export function canonicalEvent(
  value: unknown,
  runId: string,
  expected: number,
): Event {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new EventProtocolError("事件格式不符。");
  const event = value as Record<string, unknown>;
  if (
    event.runId !== runId ||
    event.seq !== expected ||
    event.protocolVersion !== 1 ||
    typeof event.type !== "string" ||
    !types.has(event.type as Event["type"]) ||
    !["runtime", "application"].includes(String(event.source)) ||
    typeof event.timestamp !== "string" ||
    !(event.blockId === null || typeof event.blockId === "string") ||
    !event.payload ||
    typeof event.payload !== "object" ||
    Array.isArray(event.payload) ||
    (event.source === "runtime"
      ? !Number.isSafeInteger(event.sourceSeq) || Number(event.sourceSeq) < 1
      : event.sourceSeq !== null)
  ) {
    throw new EventProtocolError("事件身份或顺序不符，已停止订阅。");
  }
  return value as Event;
}

export async function consumeEvents(
  body: ReadableStream<Uint8Array>,
  runId: string,
  after: number,
  onEvent: (event: Event) => void,
  signal: AbortSignal,
): Promise<number> {
  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let buffer = "";
  let cursor = after;
  const abort = () => {
    void reader.cancel().catch(() => undefined);
  };
  signal.addEventListener("abort", abort, { once: true });
  try {
    while (!signal.aborted) {
      const chunk = await reader.read();
      if (chunk.done) break;
      try {
        buffer += decoder.decode(chunk.value, { stream: true });
      } catch {
        throw new EventProtocolError("事件UTF-8格式不符。");
      }
      buffer = buffer.replace(/\r\n/g, "\n");
      let boundary: number;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        if (new TextEncoder().encode(frame).byteLength > 70 * 1024)
          throw new EventProtocolError("事件超出大小限制。");
        const fields = frame.split("\n");
        const data = fields.filter((line) => line.startsWith("data: "));
        if (!data.length) continue;
        if (data.length !== 1) throw new EventProtocolError("事件负载不符。");
        let value: unknown;
        try {
          value = JSON.parse(data[0].slice(6));
        } catch {
          throw new EventProtocolError("事件JSON不符。");
        }
        const event = canonicalEvent(value, runId, cursor + 1);
        if (
          !fields.includes(`id: ${event.seq}`) ||
          !fields.includes(`event: ${event.type}`)
        )
          throw new EventProtocolError("事件信封不符。");
        onEvent(event);
        cursor = event.seq;
      }
      if (new TextEncoder().encode(buffer).byteLength > 70 * 1024)
        throw new EventProtocolError("事件超出大小限制。");
    }
    if (!signal.aborted) {
      try {
        if (decoder.decode() || buffer.trim())
          throw new EventStreamInterrupted(
            "事件流末尾不完整，将从已确认游标重连。",
          );
      } catch (error) {
        if (error instanceof EventStreamInterrupted) throw error;
        throw new EventStreamInterrupted("事件流在UTF-8字符中断开。");
      }
    }
    return cursor;
  } finally {
    signal.removeEventListener("abort", abort);
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
