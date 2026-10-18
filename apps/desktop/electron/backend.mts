import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { randomBytes } from "node:crypto";
import { createInterface } from "node:readline";
import { setTimeout as delay } from "node:timers/promises";
import { consumeEvents, EventProtocolError } from "./events.mjs";
import type { Event, ConnectionState } from "./bridge.js";

export interface Backend {
  process: ChildProcessWithoutNullStreams;
  stop(): Promise<void>;
  request<T>(
    method: "GET" | "POST" | "PUT",
    path: string,
    body?: unknown,
    idempotencyKey?: string,
  ): Promise<T>;
  image(path: string): Promise<{ dataUrl: string }>;
  events(
    runId: string,
    after: number,
    onEvent: (event: Event) => void,
    onConnection: (state: ConnectionState, message?: string) => void,
    signal: AbortSignal,
  ): Promise<void>;
}
export async function startBackend(
  python: string,
  cwd: string,
  timeoutMs = 10000,
  storageRoot?: string,
): Promise<Backend> {
  const token = randomBytes(32).toString("hex");
  const child = spawn(python, ["-m", "easyai.main"], {
    cwd,
    shell: false,
    stdio: "pipe",
  });
  // Keep this pipe open: EOF is the backend's parent-liveness signal.
  child.stdin.write(
    JSON.stringify(storageRoot ? { token, storageRoot } : { token }) + "\n",
  );
  child.stdin.on("error", () => {
    /* exit/timeout below reports failure without exposing token */
  });
  child.stderr.resume();
  const lines = createInterface({ input: child.stdout });
  const stop = async () => {
    if (!child.pid || child.exitCode !== null || child.signalCode !== null)
      return;
    await new Promise<void>((resolve, reject) => {
      const onExit = () => {
        cleanup();
        lines.close();
        resolve();
      };
      const timer = setTimeout(() => {
        cleanup();
        reject(new Error("本地服务尚未确认退出，应用将保持打开。"));
      }, 20000);
      const cleanup = () => {
        clearTimeout(timer);
        child.off("exit", onExit);
      };
      child.once("exit", onExit);
      // Do not terminate the cleanup owner while it may be reaping training children.
      child.stdin.end();
    });
  };
  try {
    const ready = await new Promise<{
      port: number;
      protocolVersion: number;
      pid: number;
    }>((resolve, reject) => {
      const timer = setTimeout(
        () => reject(new Error("本地服务启动超时。")),
        timeoutMs,
      );
      const finish = (
        error?: Error,
        value?: { port: number; protocolVersion: number; pid: number },
      ) => {
        clearTimeout(timer);
        child.off("error", onError);
        child.off("exit", onExit);
        if (error) reject(error);
        else if (value) resolve(value);
      };
      const onError = () =>
        finish(new Error("无法启动本地服务，请检查应用后端环境。"));
      const onExit = () => finish(new Error("本地服务在就绪前退出。"));
      child.once("error", onError);
      child.once("exit", onExit);
      lines.once("line", (line) => {
        try {
          const value: unknown = JSON.parse(line);
          if (!value || typeof value !== "object") throw new Error();
          const v = value as Record<string, unknown>;
          if (
            Object.keys(v).sort().join(",") !== "pid,port,protocolVersion" ||
            !Number.isInteger(v.port) ||
            Number(v.port) < 1 ||
            Number(v.port) > 65535 ||
            v.protocolVersion !== 1 ||
            v.pid !== child.pid
          )
            throw new Error();
          finish(
            undefined,
            v as unknown as {
              port: number;
              protocolVersion: number;
              pid: number;
            },
          );
        } catch {
          finish(new Error("本地服务启动协议不匹配。"));
        }
      });
    });
    const result = await fetch(`http://127.0.0.1:${ready.port}/api/v1/health`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(3000),
    });
    const health = (await result.json()) as {
      ready?: boolean;
      protocolVersion?: number;
    };
    if (!result.ok || health.ready !== true || health.protocolVersion !== 1)
      throw new Error("本地服务健康检查失败。");
    child.stderr.resume();
    const origin = `http://127.0.0.1:${ready.port}`;
    const target = (path: string) => {
      if (
        !path.startsWith("/api/v1/") ||
        path.includes("\\") ||
        path.includes("#") ||
        path.includes("://")
      )
        throw new Error("本地接口路径不受支持。");
      return origin + path;
    };
    const limited = async (response: Response, max: number) => {
      const reader = response.body?.getReader();
      if (!reader) throw new Error("本地服务未返回内容。");
      const chunks: Uint8Array[] = [];
      let count = 0;
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          count += value.byteLength;
          if (count > max) throw new Error("本地服务内容超出限制。");
          chunks.push(value);
        }
      } finally {
        await reader.cancel().catch(() => undefined);
      }
      return Buffer.concat(chunks);
    };
    const request = async <T,>(
      method: "GET" | "POST" | "PUT",
      path: string,
      body?: unknown,
      idempotencyKey?: string,
    ): Promise<T> => {
      const response = await fetch(target(path), {
        method,
        redirect: "error",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        signal: AbortSignal.timeout(30000),
      });
      const raw = await limited(response, 16 * 1024 * 1024);
      let value: unknown;
      try {
        value = JSON.parse(raw.toString("utf8"));
      } catch {
        throw new Error("本地服务返回格式不符。");
      }
      if (!response.ok) {
        const error = value as {
          error?: { message?: unknown };
          detail?: unknown;
        };
        const descriptions: Record<string, string> = {
          PROJECT_REVISION_CONFLICT: "工程已更新，请保存并重新编译后再运行。",
          PROGRAM_HASH_CONFLICT: "编译结果已过期，请重新检查代码。",
          RUN_ACTIVE_CONFLICT:
            "已有本地任务正在执行，请先等待结束或停止该任务。",
          RUN_IDEMPOTENCY_CONFLICT: "本次运行请求已改变，请重新检查后开始。",
          ENVIRONMENT_IMPORT_FAILED:
            "所选Python无法导入训练依赖，请选择已准备的独立训练环境。",
          ENVIRONMENT_PROBE_TIMEOUT: "所选Python检查超时，未启动训练。",
          ENVIRONMENT_PYTHON_UNAVAILABLE:
            "无法启动所选Python，请重新选择已有训练环境。",
          DATASET_MISSING_NO_DOWNLOAD:
            "所选目录缺少已准备的数据文件。应用不会自动下载。",
          DATASET_IDX_INVALID:
            "数据文件头或长度不符合IDX格式，请检查数据目录。",
          DATASET_PREFLIGHT_NOT_SUPPORTED:
            "当前本地运行预检支持MNIST和FashionMNIST，尚未开放CIFAR10入口。",
          PROJECT_ALREADY_EXISTS:
            "所选目录已有工程，请打开它，或选择新的工程目录。",
          PROJECT_READ_ONLY: "工程为只读，无法保存或启动。",
          PROJECT_SIZE_LIMIT:
            "工程超过5MiB安全上限。原文件未改，无法从内存预览导出，请保留完整原文件。",
          PROJECT_EXPORT_TARGET_EXISTS:
            "导出目标已存在，未覆盖。请选择新文件名。",
          LOCAL_SESSION_RESTORE_FAILED:
            "无法安全恢复上次工程；原文件未改，请重新选择工程目录。",
          LOCAL_SELECTION_NOT_FOUND: "路径选择已失效，请重新使用选择按钮。",
          LOCAL_FILE_NOT_FOUND: "所需本地文件不存在，请检查所选目录。",
          FILE_NOT_REGULAR: "本地持久文件类型不受支持，已拒绝读取。",
        };
        const code = (value as { error?: { code?: unknown } })?.error?.code;
        const message =
          typeof code === "string" && descriptions[code]
            ? descriptions[code]
            : typeof error?.error?.message === "string"
              ? error.error.message
              : typeof error?.detail === "string"
                ? error.detail
                : `本地服务拒绝请求（${response.status}）。`;
        throw new Error(message.slice(0, 1024));
      }
      return value as T;
    };
    const image = async (path: string) => {
      const response = await fetch(target(path), {
        redirect: "error",
        headers: { Authorization: `Bearer ${token}` },
        signal: AbortSignal.timeout(10000),
      });
      if (
        !response.ok ||
        response.headers.get("Content-Type")?.split(";")[0] !== "image/png"
      )
        throw new Error("图像尚未就绪或无法读取。");
      const data = await limited(response, 8 * 1024 * 1024);
      if (
        !data
          .subarray(0, 8)
          .equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))
      )
        throw new Error("图像格式不符。");
      return { dataUrl: `data:image/png;base64,${data.toString("base64")}` };
    };
    const events = async (
      runId: string,
      after: number,
      onEvent: (event: Event) => void,
      onConnection: (state: ConnectionState, message?: string) => void,
      signal: AbortSignal,
    ) => {
      let cursor = after;
      let backoff = 250;
      while (!signal.aborted) {
        try {
          const response = await fetch(
            target(`/api/v1/runs/${runId}/events?after=${cursor}`),
            {
              redirect: "error",
              headers: { Authorization: `Bearer ${token}` },
              signal,
            },
          );
          if (
            !response.ok ||
            !response.body ||
            !response.headers
              .get("Content-Type")
              ?.startsWith("text/event-stream")
          )
            throw new EventProtocolError("运行事件不可用。");
          onConnection("connected");
          backoff = 250;
          cursor = await consumeEvents(
            response.body,
            runId,
            cursor,
            (event) => {
              cursor = event.seq;
              onEvent(event);
            },
            signal,
          );
          if (signal.aborted) break;
          const state = await request<{ status: string }>(
            "GET",
            `/api/v1/runs/${runId}`,
          );
          if (
            ["SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"].includes(
              state.status,
            )
          ) {
            onConnection("closed");
            return;
          }
        } catch (error) {
          if (signal.aborted) break;
          if (error instanceof EventProtocolError) {
            onConnection("error", error.message);
            return;
          }
        }
        onConnection("reconnecting", "事件连接中断，正在重连。");
        await delay(backoff, undefined, { signal }).catch(() => undefined);
        backoff = Math.min(backoff * 2, 8000);
      }
    };
    return { process: child, stop, request, image, events };
  } catch (error) {
    await stop();
    throw error;
  }
}
