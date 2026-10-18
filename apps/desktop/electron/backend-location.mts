import { join } from "node:path";

/** Main-owned launch description. Never supplied by Renderer or an environment override. */
export function backendLocation(
  packaged: boolean,
  resourcesPath: string,
  repository: string,
  platform: NodeJS.Platform,
) {
  if (packaged) {
    const cwd = join(resourcesPath, "backend");
    return {
      executable: join(
        cwd,
        platform === "win32" ? "easyai-sidecar.exe" : "easyai-sidecar",
      ),
      cwd,
      args: [] as string[],
    };
  }
  return {
    executable: join(
      repository,
      "services/backend/.venv",
      platform === "win32" ? "Scripts/python.exe" : "bin/python",
    ),
    cwd: join(repository, "services/backend"),
    args: ["-m", "easyai.main"],
  };
}
