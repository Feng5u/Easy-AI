import { open, stat } from "node:fs/promises";
import { win32 } from "node:path";

const configurationError = () => new Error("应用后端环境启动配置不匹配。");

/** Only the Main-owned Windows development venv uses this CPython launcher contract. */
export function windowsApplicationPython(config: string, launcher: string) {
  const fields = new Map<string, string>();
  for (const line of config.split(/\r?\n/)) {
    if (!line.trim()) continue;
    const separator = line.indexOf("=");
    if (separator < 1) throw configurationError();
    const key = line.slice(0, separator).trim().toLowerCase();
    const value = line.slice(separator + 1).trim();
    if (fields.has(key) || /[\x00-\x1f]/.test(value))
      throw configurationError();
    fields.set(key, value);
  }
  const home = fields.get("home");
  if (
    !win32.isAbsolute(launcher) ||
    !home ||
    !win32.isAbsolute(home) ||
    win32.parse(home).root.length < 3 ||
    fields.get("implementation")?.toLowerCase() !== "cpython" ||
    !/^3\.11(?:\.|$)/.test(fields.get("version_info") ?? "") ||
    fields.get("include-system-site-packages")?.toLowerCase() !== "false"
  )
    throw configurationError();
  const executable = win32.join(home, "python.exe");
  if (executable.toLowerCase() === win32.normalize(launcher).toLowerCase())
    throw configurationError();
  return { executable, launcher };
}

export function applicationPythonEnvironment(
  launcher: string,
  source: NodeJS.ProcessEnv = process.env,
): NodeJS.ProcessEnv {
  const overrides = new Set([
    "PYTHONHOME",
    "PYTHONEXECUTABLE",
    "PYTHONPATH",
    "__PYVENV_LAUNCHER__",
  ]);
  // Windows environment names are case insensitive, even when a spread clone
  // is not. Remove every spelling before installing the fixed app-only value.
  const env = Object.fromEntries(
    Object.entries(source).filter(([key]) => !overrides.has(key.toUpperCase())),
  );
  env.__PYVENV_LAUNCHER__ = launcher;
  return env;
}

export async function applicationPythonLaunch(
  executable: string,
  cwd: string,
  args: string[],
): Promise<{ executable: string; env: NodeJS.ProcessEnv }> {
  if (
    process.platform !== "win32" ||
    args.length !== 2 ||
    args[0] !== "-m" ||
    args[1] !== "easyai.main" ||
    win32.normalize(executable).toLowerCase() !==
      win32.join(cwd, ".venv/Scripts/python.exe").toLowerCase()
  )
    return { executable, env: process.env };

  // Bounded read of the same fixed pyvenv.cfg that CPython's redirector uses.
  // Never fall back to PATH, another environment, or a guessed interpreter.
  try {
    const file = await open(win32.join(cwd, ".venv/pyvenv.cfg"), "r");
    let config: string;
    try {
      const info = await file.stat();
      if (!info.isFile() || info.size > 8192) throw configurationError();
      const buffer = Buffer.alloc(8193);
      const { bytesRead } = await file.read(buffer, 0, buffer.length, 0);
      if (bytesRead > 8192) throw configurationError();
      config = buffer.subarray(0, bytesRead).toString("utf8");
    } finally {
      await file.close();
    }
    const launch = windowsApplicationPython(config, executable);
    if (!(await stat(launch.executable)).isFile()) throw configurationError();
    const env = applicationPythonEnvironment(launch.launcher);
    return { executable: launch.executable, env };
  } catch {
    throw configurationError();
  }
}
