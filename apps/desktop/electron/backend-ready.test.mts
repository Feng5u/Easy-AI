import { expect, it } from "vitest";
import { backendReady, BackendReadyError } from "./backend-ready.mjs";

const ready = { port: 49152, protocolVersion: 1, pid: 123 };
it("accepts only the exact ready schema with the directly owned PID, including CRLF", () => {
  expect(backendReady(JSON.stringify(ready) + "\r", 123)).toEqual(ready);
});
it.each([
  ["BOM", "\ufeff" + JSON.stringify(ready), "JSON"],
  ["stdout debug", "debug\n" + JSON.stringify(ready), "JSON"],
  ["extra key", JSON.stringify({ ...ready, token: "synthetic" }), "SCHEMA"],
  ["array", "[]", "SCHEMA"],
  ["port type", JSON.stringify({ ...ready, port: "49152" }), "PORT"],
  ["port range", JSON.stringify({ ...ready, port: 65536 }), "PORT"],
  ["version", JSON.stringify({ ...ready, protocolVersion: 2 }), "VERSION"],
  ["launcher PID", JSON.stringify({ ...ready, pid: 456 }), "PID"],
  ["string PID", JSON.stringify({ ...ready, pid: "123" }), "PID"],
] as const)(
  "rejects %s without accepting a second ready line",
  (_, line, code) => {
    try {
      backendReady(line, 123);
      throw new Error("invalid ready accepted");
    } catch (error) {
      expect(error).toBeInstanceOf(BackendReadyError);
      expect((error as BackendReadyError).code).toBe(code);
      expect((error as Error).message).toBe("本地服务启动协议不匹配。");
    }
  },
);
