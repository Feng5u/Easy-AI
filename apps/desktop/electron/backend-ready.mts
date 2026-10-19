export class BackendReadyError extends Error {
  constructor(readonly code: "JSON" | "SCHEMA" | "PORT" | "VERSION" | "PID") {
    super("本地服务启动协议不匹配。");
  }
}

export function backendReady(line: string, spawnedPid: number | undefined) {
  let value: unknown;
  try {
    value = JSON.parse(line);
  } catch {
    throw new BackendReadyError("JSON");
  }
  if (
    !value ||
    typeof value !== "object" ||
    Object.keys(value).sort().join(",") !== "pid,port,protocolVersion"
  )
    throw new BackendReadyError("SCHEMA");
  const v = value as Record<string, unknown>;
  if (!Number.isInteger(v.port) || Number(v.port) < 1 || Number(v.port) > 65535)
    throw new BackendReadyError("PORT");
  if (v.protocolVersion !== 1) throw new BackendReadyError("VERSION");
  if (
    !Number.isSafeInteger(spawnedPid) ||
    Number(spawnedPid) <= 0 ||
    v.pid !== spawnedPid
  )
    throw new BackendReadyError("PID");
  return v as { port: number; protocolVersion: number; pid: number };
}
