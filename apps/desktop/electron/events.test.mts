import { it, expect } from "vitest";
import {
  consumeEvents,
  EventProtocolError,
  EventStreamInterrupted,
} from "./events.mjs";
import type { Event } from "./bridge.js";
const runId = "6a459e57-3609-4c4d-97c8-94ec3b0ad45b";
const event: Event = {
  protocolVersion: 1,
  runId,
  seq: 1,
  source: "application",
  sourceSeq: null,
  timestamp: "2026-10-18T09:00:00Z",
  type: "status_changed",
  blockId: null,
  payload: { status: "RUNNING", message: "中文" },
};
function frame(value = event) {
  return `id: ${value.seq}\nevent: ${value.type}\ndata: ${JSON.stringify(value)}\n\n`;
}
function bytes(input: string, chunkSize = 1) {
  const data = new TextEncoder().encode(input);
  let cursor = 0;
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      if (cursor >= data.length) {
        controller.close();
        return;
      }
      controller.enqueue(data.slice(cursor, (cursor += chunkSize)));
    },
  });
}
it("parses arbitrary UTF8/CRLF chunks and forwards exact canonical events", async () => {
  const received: Event[] = [];
  expect(
    await consumeEvents(
      bytes(frame().replace(/\n/g, "\r\n")),
      runId,
      0,
      (e) => received.push(e),
      new AbortController().signal,
    ),
  ).toBe(1);
  expect(received).toEqual([event]);
});
it("rejects wrong run identities, gaps, envelope ids and unknown types", async () => {
  for (const input of [
    frame({ ...event, runId: "other" }),
    frame({ ...event, seq: 2 }),
    frame().replace("id: 1", "id: 3"),
    frame({ ...event, type: "made_up" as Event["type"] }),
  ]) {
    await expect(
      consumeEvents(
        bytes(input, 32),
        runId,
        0,
        () => expect.fail("untrusted event"),
        new AbortController().signal,
      ),
    ).rejects.toBeInstanceOf(EventProtocolError);
  }
});
it("does not acknowledge an incomplete transport tail", async () => {
  const received: Event[] = [];
  await expect(
    consumeEvents(
      bytes(frame() + frame({ ...event, seq: 2 }).slice(0, -4), 8),
      runId,
      0,
      (e) => received.push(e),
      new AbortController().signal,
    ),
  ).rejects.toBeInstanceOf(EventStreamInterrupted);
  expect(received.map((e) => e.seq)).toEqual([1]);
});
it("bounds oversized frames and cancels stream readers on unsubscribe", async () => {
  await expect(
    consumeEvents(
      bytes("data: " + "x".repeat(72 * 1024)),
      runId,
      0,
      () => undefined,
      new AbortController().signal,
    ),
  ).rejects.toBeInstanceOf(EventProtocolError);
  const controller = new AbortController();
  let cancelled = false;
  const stream = new ReadableStream<Uint8Array>({
    cancel() {
      cancelled = true;
    },
  });
  const task = consumeEvents(
    stream,
    runId,
    0,
    () => undefined,
    controller.signal,
  );
  controller.abort();
  await task;
  expect(cancelled).toBe(true);
});
it("handles simultaneous stream failure and cancellation without an orphan rejection", async () => {
  let source!: ReadableStreamDefaultController<Uint8Array>;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      source = controller;
    },
  });
  const controller = new AbortController();
  const failure = new Error("owned network failure");
  const task = consumeEvents(
    stream,
    runId,
    0,
    () => undefined,
    controller.signal,
  );
  source.error(failure);
  controller.abort();
  await expect(task).rejects.toBe(failure);
  // Vitest also fails this test if reader.cancel produces an unhandled rejection.
  await new Promise<void>((resolve) => setImmediate(resolve));
});
