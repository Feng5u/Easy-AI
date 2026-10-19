import { test, expect, _electron as electron } from "@playwright/test";
import path from "node:path";
import { mkdtemp, mkdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";

test("secure desktop, Dataset error repair, Monaco and saved project reopen", async () => {
  test.setTimeout(120000);
  const directory = await mkdtemp(path.join(tmpdir(), "easyai-editor-e2e-"));
  const projectDirectory = path.join(directory, "project");
  const stateDirectory = path.join(directory, "application-state");
  await mkdir(projectDirectory);
  await mkdir(stateDirectory);
  const packaged = process.env.EASYAI_E2E_PACKAGE;
  const launch = () =>
    electron.launch({
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
  let app = await launch();
  try {
    expect(await app.evaluate(({ app }) => app.getPath("userData"))).toBe(
      stateDirectory,
    );
    const page = await app.firstWindow();
    const identity = await app.evaluate(({ app }) => ({
      packaged: app.isPackaged,
      appPath: app.getAppPath(),
    }));
    expect(identity.packaged).toBe(Boolean(packaged));
    if (packaged) expect(identity.appPath.endsWith("app.asar")).toBe(true);
    await expect(page.getByTestId("backend-status")).toHaveText(
      "本地服务已就绪。",
    );
    expect(
      await page.evaluate(() => ({
        node: typeof (globalThis as Record<string, unknown>).require,
        bridge: Object.keys((window as unknown as { easyai: object }).easyai),
      })),
    ).toEqual({
      node: "undefined",
      bridge: [
        "dataTransfers",
        "packages",
        "local",
        "connections",
        "environments",
        "status",
        "selections",
        "projects",
        "runs",
      ],
    });
    const rendererSecurity = await app.evaluate(({ app }) => ({
      platform: process.platform,
      processes: app.getAppMetrics().filter((metric) => metric.type === "Tab"),
    }));
    expect(rendererSecurity.processes.length).toBeGreaterThan(0);
    if (
      rendererSecurity.platform === "win32" ||
      rendererSecurity.platform === "darwin"
    ) {
      expect(
        rendererSecurity.processes.every((metric) => metric.sandboxed === true),
      ).toBe(true);
    }
    expect(
      await app.evaluate(() => process.argv.includes("--no-sandbox")),
    ).toBe(false);
    // Only replace the OS directory picker; real IPC, backend, Blockly and compiler remain.
    await app.evaluate(({ dialog }, root) => {
      dialog.showOpenDialog = async (...args: unknown[]) => {
        const options = args.at(-1) as {
          title?: string;
          properties?: string[];
        };
        if (
          options.title !== "选择项目目录" ||
          options.properties?.join() !== "openDirectory"
        )
          throw new Error(
            "Unexpected dialog: editor scenario must not select training, data or credentials",
          );
        return { canceled: false, filePaths: [root] };
      };
    }, projectDirectory);
    const failures: string[] = [];
    page.on("pageerror", (error) => failures.push(error.name));
    page.on("console", (message) => {
      if (
        /Content Security Policy|Refused to (?:load|apply|execute|create)/i.test(
          message.text(),
        )
      )
        failures.push("CSP violation");
    });
    await page
      .getByRole("button", { name: "新建 MNIST 示例", exact: true })
      .click();
    const symbols = page.getByRole("complementary", { name: "对象注册与引用" });
    await expect(
      symbols.getByRole("button", { name: /^train_data/ }),
    ).toBeVisible();
    const compile = page.getByRole("button", {
      name: "检查与编译",
      exact: true,
    });
    const passed = page
      .getByRole("status")
      .filter({ hasText: /^代码检查通过/ });
    await compile.click();
    await expect(passed).toBeVisible();
    await page.getByText("查看当前工程的只读生成代码", { exact: true }).click();
    const monaco = page
      .getByLabel("Monaco 只读代码视图")
      .locator(".monaco-editor");
    await expect(monaco).toBeVisible();
    await expect(monaco.locator("textarea.inputarea")).toHaveJSProperty(
      "readOnly",
      true,
    );
    await expect(
      page.getByText(/代码编辑器无法加载|代码编辑器缺少/),
    ).toHaveCount(0);
    // Both editors must use this document's nonce for dynamically created styles.
    expect(
      await page.evaluate(() => {
        const nonce = document.querySelector<HTMLMetaElement>(
          'meta[name="easyai-style-nonce"]',
        )?.content;
        const styles = Array.from(document.querySelectorAll("style"));
        return (
          Boolean(nonce) &&
          styles.length > 0 &&
          styles.every((style) => style.nonce === nonce)
        );
      }),
    ).toBe(true);
    // The hidden text fallback retains the full backend-generated payload even
    // while Monaco virtualizes its visible lines; do not use it as an editor stub.
    const originalCode = await page
      .locator(".code-view > ol > li code")
      .allTextContents();
    await symbols.getByRole("button", { name: /^train_data/ }).click();
    const datasetId = (await symbols.locator(":scope > small").textContent())!;
    await expect(symbols.locator("strong")).toHaveText("data.dataset_builtin");
    await expect(
      monaco.locator(".monaco-source-selected-semantic").first(),
    ).toBeVisible();
    await expect(compile).toBeEnabled();
    const before = JSON.parse(
      await readFile(
        path.join(projectDirectory, "project.easyai.json"),
        "utf8",
      ),
    );
    await symbols
      .getByRole("button", { name: "删除所选积木", exact: true })
      .click();
    await expect(
      symbols.getByRole("button", { name: /^train_data/ }),
    ).toHaveCount(0);
    await expect(
      page.getByText("尚无编译结果。检查不会启动训练。", { exact: true }),
    ).toBeVisible();
    await expect(compile).toBeEnabled(); // Wait for actual autosave, not a fixed timer.
    await compile.click();
    await expect(
      page.getByRole("status").filter({ hasText: /^暂不能运行/ }),
    ).toBeVisible();
    const missing = page
      .locator(".diagnostics li")
      .filter({ hasText: "REF_NOT_FOUND" })
      .filter({ hasText: "DATASET_REF" });
    await expect(missing).toHaveCount(1);
    await expect(missing).toContainText("找不到原先选择的对象");
    await expect(
      page.getByRole("button", { name: "开始本次运行", exact: true }),
    ).toBeDisabled();
    await missing.getByRole("button", { name: /^源积木 / }).click();
    await expect(symbols.locator("strong")).toHaveText("data.dataloader");
    await expect(
      page.getByRole("tab", { name: "数据处理", exact: true }),
    ).toHaveAttribute("aria-selected", "true");
    await page.getByRole("button", { name: "撤销", exact: true }).click();
    await expect(
      symbols.getByRole("button", { name: /^train_data/ }),
    ).toBeVisible();
    await symbols.getByRole("button", { name: /^train_data/ }).click();
    await expect(symbols.locator(":scope > small")).toHaveText(datasetId);
    await expect(compile).toBeEnabled();
    await compile.click();
    await expect(passed).toBeVisible();
    await expect(page.locator(".diagnostics .error")).toHaveCount(0);
    await expect
      .poll(() => page.locator(".code-view > ol > li code").allTextContents())
      .toEqual(originalCode);
    await expect(monaco).toBeVisible();
    await page.getByRole("tab", { name: "模型结构", exact: true }).click();
    await expect(compile).toBeEnabled();
    const restored = JSON.parse(
      await readFile(
        path.join(projectDirectory, "project.easyai.json"),
        "utf8",
      ),
    );
    // Blockly may append an undone root to the root list; compare the full saved
    // blocks/IDs/references/layout independently of that non-semantic ordering.
    const ordered = (workspaces: typeof restored.workspaces) =>
      Object.fromEntries(
        Object.entries(workspaces).map(([tab, value]) => {
          const workspace = value as {
            blocks: { languageVersion: number; blocks: { id: string }[] };
          };
          return [
            tab,
            {
              ...workspace,
              blocks: {
                ...workspace.blocks,
                blocks: [...workspace.blocks.blocks].sort((a, b) =>
                  a.id.localeCompare(b.id),
                ),
              },
            },
          ];
        }),
      );
    expect(ordered(restored.workspaces)).toEqual(ordered(before.workspaces));
    expect(restored.ui.activeTab).toBe("model");
    expect(restored.ui.codeVisible).toBe(true);
    expect(restored.revision).toBeGreaterThan(before.revision);
    expect(failures).toEqual([]);
    await app.close();
    app = await launch();
    const reopened = await app.firstWindow();
    await expect(reopened.getByTestId("backend-status")).toHaveText(
      "本地服务已就绪。",
    );
    await expect(
      reopened.getByRole("tab", { name: "模型结构", exact: true }),
    ).toHaveAttribute("aria-selected", "true");
    await expect(
      reopened
        .getByRole("complementary", { name: "对象注册与引用" })
        .getByRole("button", { name: /^train_data/ }),
    ).toBeVisible();
    await reopened
      .getByRole("button", { name: "检查与编译", exact: true })
      .click();
    await expect(
      reopened.getByRole("status").filter({ hasText: /^代码检查通过/ }),
    ).toBeVisible();
    await expect(
      reopened.getByLabel("Monaco 只读代码视图").locator(".monaco-editor"),
    ).toBeVisible();
    await expect
      .poll(() =>
        reopened.locator(".code-view > ol > li code").allTextContents(),
      )
      .toEqual(originalCode);
    await expect(
      reopened.getByRole("button", { name: "开始本次运行", exact: true }),
    ).toBeDisabled();
  } finally {
    await app.close();
    await rm(directory, { recursive: true });
  }
});
