import {
  _electron as electron,
  type ElectronApplication,
} from "@playwright/test";
import path from "node:path";

export function launchDesktop(stateDirectory: string) {
  const packaged = process.env.EASYAI_E2E_PACKAGE;
  return electron.launch({
    ...(packaged
      ? {
          executablePath: path.resolve(packaged),
          args: [`--user-data-dir=${stateDirectory}`],
        }
      : {
          args: [
            path.resolve("apps/desktop"),
            `--user-data-dir=${stateDirectory}`,
          ],
        }),
    chromiumSandbox: true,
    timeout: 15000,
  });
}

/** Replace only native project-directory selection, not any application operation. */
export async function projectPicker(app: ElectronApplication, root: string) {
  await app.evaluate(({ dialog }, directory) => {
    dialog.showOpenDialog = async (...args: unknown[]) => {
      const options = args.at(-1) as { title?: string; properties?: string[] };
      if (
        options.title !== "选择项目目录" ||
        options.properties?.join() !== "openDirectory"
      )
        throw new Error(
          "Unexpected dialog: editor scenario must not select training, data or credentials",
        );
      return { canceled: false, filePaths: [directory] };
    };
  }, root);
}
