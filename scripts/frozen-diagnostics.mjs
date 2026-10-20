// Smoke-only diagnostics. Never emit response bodies, stderr messages or paths.
const routes = new Set([
  "/local/session",
  "/local/preflight",
  "/catalog/packages",
  "/environments/install-source/preview",
  "/environments/install-plan",
  "/install-jobs",
  "/connections",
  "/local/selections",
  "/projects",
  "/local/export",
]);
export function safeRequest(method, path, status = null) {
  const route = routes.has(path)
    ? path
    : /^\/projects\/[0-9a-f-]{36}\/compile$/.test(path)
      ? "/projects/:id/compile"
      : "<other>";
  return {
    method: ["GET", "POST", "PATCH"].includes(method) ? method : "<other>",
    route,
    status,
  };
}
export async function readSmokeResponse(response, request) {
  const body = await response.text();
  let value;
  try {
    value = JSON.parse(body);
  } catch {
    throw new Error(`FROZEN_HTTP_NON_JSON ${JSON.stringify(request)}`);
  }
  if (response.status >= 500)
    throw new Error(`FROZEN_HTTP_SERVER_ERROR ${JSON.stringify(request)}`);
  return { response, value };
}
const files = new Set([
  "api.py",
  "install_runtime.py",
  "install_registry.py",
  "install_service.py",
  "local_workspace.py",
  "remote_cache.py",
  "install_source_selection.py",
  "install_sources.py",
  "project_service.py",
  "project_lock.py",
  "files.py",
  "main.py",
]);
const classes = new Set([
  "AttributeError",
  "ModuleNotFoundError",
  "ImportError",
  "FileNotFoundError",
  "PermissionError",
  "OSError",
  "ValueError",
  "TypeError",
  "RuntimeError",
  "KeyError",
  "AssertionError",
  "NameError",
]);
export function stderrDiagnostics(limit = 65536) {
  let buffer = Buffer.alloc(0);
  let truncated = false;
  return {
    append(chunk) {
      const bytes = Buffer.from(chunk);
      truncated ||= buffer.length + bytes.length > limit;
      buffer = Buffer.concat([buffer, bytes.subarray(-limit)]).subarray(-limit);
    },
    summary() {
      const frames = [],
        exceptions = [];
      for (const line of buffer.toString("utf8").split(/\r?\n/)) {
        const frame = /File "([^"]+)", line ([0-9]{1,7}), in /.exec(line);
        if (frame) {
          const basename = frame[1].split(/[\\/]/).at(-1);
          frames.push({
            file: files.has(basename) ? basename : "<other>",
            line: Number(frame[2]),
          });
        }
        const exception = /^\s*(?:\|\s*)?([A-Za-z]+Error)(?::|$)/.exec(line);
        if (exception && classes.has(exception[1]))
          exceptions.push(exception[1]);
      }
      return {
        truncated,
        retainedBytes: buffer.length,
        frames: frames.slice(-24),
        exceptions: exceptions.slice(-12),
      };
    },
  };
}
