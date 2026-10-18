import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { randomBytes } from "node:crypto";
import { createInterface } from "node:readline";
import { once } from "node:events";

export interface Backend {
  process: ChildProcessWithoutNullStreams;
  stop(): Promise<void>;
}
export async function startBackend(
  python: string,
  cwd: string,
  timeoutMs = 10000,
): Promise<Backend> {
  const token = randomBytes(32).toString("hex");
  const child = spawn(python, ["-m", "easyai.main"], {
    cwd,
    shell: false,
    stdio: "pipe",
  });
  // Keep this pipe open: EOF is the backend's parent-liveness signal.
  child.stdin.write(JSON.stringify({ token }) + "\n");
  child.stdin.on("error", () => {
    /* exit/timeout below reports failure without exposing token */
  });
  child.stderr.resume();
  const lines = createInterface({ input: child.stdout });
  const stop = async () => {
    if (!child.pid || child.exitCode !== null || child.signalCode !== null)
      return;
    const exited = once(child, "exit");
    child.stdin.end();
    const timer = setTimeout(() => child.kill(), 3000);
    try {
      await exited;
    } finally {
      clearTimeout(timer);
      lines.close();
    }
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
    return { process: child, stop };
  } catch (error) {
    await stop();
    throw error;
  }
}
