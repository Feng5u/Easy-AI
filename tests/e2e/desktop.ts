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

/** Observe only fixed native-dialog categories; preserve actual dialog behavior. */
export async function observeTemporaryDesktop(app: ElectronApplication) {
  app.on("console", (message) => {
    if (
      /^EASYAI_TOOLBOX_NATIVE_DIALOG (dirty|active-run|shutdown-error|other)$/.test(
        message.text(),
      )
    )
      console.info(message.text());
  });
  const process = app.process();
  process.once("exit", (code, signal) => {
    console.info(
      "EASYAI_TOOLBOX_PROCESS_EXIT",
      JSON.stringify({ pid: process.pid, code, signal }),
    );
  });
  await app.evaluate(({ dialog }) => {
    const original = dialog.showMessageBox;
    dialog.showMessageBox = async (...args: unknown[]) => {
      const options = args.at(-1) as Electron.MessageBoxOptions;
      const category =
        options.title === "仍有未保存编辑"
          ? "dirty"
          : options.title === "本地任务仍在运行"
            ? "active-run"
            : options.title === "无法安全退出"
              ? "shutdown-error"
              : "other";
      console.info(`EASYAI_TOOLBOX_NATIVE_DIALOG ${category}`);
      return Reflect.apply(original, dialog, args);
    };
  });
}

/** Only failure cleanup may discard this test's own temporary unsaved draft. */
export async function closeTemporaryDesktop(
  app: ElectronApplication,
  failed: boolean,
) {
  // The Electron channel is disposed during close; process() then resolves an
  // already removed dispatcher. Keep the real ChildProcess before shutdown.
  const process = app.process();
  const shutdown = new AbortController();
  async function closeOwnedProcess() {
    if (failed)
      await app.evaluate(({ dialog }) => {
        const original = dialog.showMessageBox;
        dialog.showMessageBox = async (...args: unknown[]) => {
          const options = args.at(-1) as Electron.MessageBoxOptions;
          if (
            options.title === "仍有未保存编辑" &&
            options.buttons?.join("|") === "留在应用|放弃未保存编辑并退出"
          ) {
            console.info("EASYAI_TOOLBOX_NATIVE_DIALOG dirty");
            return { response: 1, checkboxChecked: false };
          }
          return Reflect.apply(original, dialog, args);
        };
      });
    shutdown.signal.throwIfAborted();
    await app.close();
  }
  let timeout: ReturnType<typeof setTimeout> | undefined;
  try {
    await Promise.race([
      closeOwnedProcess(),
      new Promise<never>((_, reject) => {
        timeout = setTimeout(() => {
          const error = new Error(
            "Temporary desktop shutdown was not confirmed within 12 seconds",
          );
          shutdown.abort(error);
          reject(error);
        }, 12000);
      }),
    ]);
    if (process.exitCode === null && process.signalCode === null)
      throw new Error(
        "Temporary desktop close returned without process exit evidence",
      );
    if (process.exitCode !== 0 || process.signalCode !== null)
      throw new Error("Temporary desktop did not exit normally");
    console.info(
      "EASYAI_TOOLBOX_CLOSE_CONFIRMED",
      JSON.stringify({
        pid: process.pid,
        code: process.exitCode,
        signal: process.signalCode,
      }),
    );
  } finally {
    clearTimeout(timeout);
  }
}
