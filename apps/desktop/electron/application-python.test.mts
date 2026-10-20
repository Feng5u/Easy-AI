import { expect, it } from "vitest";
import {
  applicationPythonLaunch,
  applicationPythonEnvironment,
  windowsApplicationPython,
} from "./application-python.mjs";

const launcher =
  "C:\\repo with spaces\\services\\backend\\.venv\\Scripts\\python.exe";
const config =
  "home = C:\\managed python\r\nimplementation = CPython\r\nversion_info = 3.11\r\ninclude-system-site-packages = false\r\n";
it("reproduces CPython's venv command without the redirector process", () => {
  expect(windowsApplicationPython(config, launcher)).toEqual({
    executable: "C:\\managed python\\python.exe",
    launcher,
  });
});
it.each([
  config + "home = C:\\other\n",
  config.replace("home = C:\\managed python", "home = relative"),
  config.replace("home = C:\\managed python", "home = \\root-relative"),
  config.replace("home = C:\\managed python", "home ="),
  config.replace("implementation = CPython", "implementation = pypy"),
  config.replace("version_info = 3.11", "version_info = 3.12"),
  config.replace(
    "include-system-site-packages = false",
    "include-system-site-packages = true",
  ),
  config.replace(
    "home = C:\\managed python",
    "home = C:\\repo with spaces\\services\\backend\\.venv\\Scripts",
  ),
])(
  "rejects unsupported or ambiguous app configuration without a fallback",
  (value) => {
    expect(() => windowsApplicationPython(value, launcher)).toThrow(
      "启动配置不匹配",
    );
  },
);
it("does not reinterpret the frozen executable or another Python as the app venv", async () => {
  const frozen = await applicationPythonLaunch(
    "C:\\app\\easyai-sidecar.exe",
    "C:\\app",
    [],
  );
  expect(frozen.executable).toBe("C:\\app\\easyai-sidecar.exe");
  expect(frozen.env).toBe(process.env);
  const selected = await applicationPythonLaunch(
    "C:\\other\\python.exe",
    "C:\\app",
    ["-m", "easyai.main"],
  );
  expect(selected.executable).toBe("C:\\other\\python.exe");
});

it("sets only a child-local launcher value and removes case-insensitive prefix overrides", () => {
  const source = {
    Path: "synthetic-path",
    PythonHome: "wrong",
    PYTHONEXECUTABLE: "wrong",
    pythonpath: "wrong",
    __pyvenv_launcher__: "wrong",
  };
  const before = { ...source };
  expect(applicationPythonEnvironment(launcher, source)).toEqual({
    Path: "synthetic-path",
    __PYVENV_LAUNCHER__: launcher,
  });
  expect(source).toEqual(before);
});
