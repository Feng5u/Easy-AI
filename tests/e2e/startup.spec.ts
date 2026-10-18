import { test, expect, _electron as electron } from "@playwright/test";
import path from "node:path";

test("secure desktop startup and normal shutdown", async () => {
  const app = await electron.launch({
    args: [path.resolve("apps/desktop")],
    chromiumSandbox: true,
    timeout: 15000,
  });
  try {
    const page = await app.firstWindow();
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
  } finally {
    await app.close();
  }
});
