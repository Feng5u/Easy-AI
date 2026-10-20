import { test, expect } from "@playwright/test";
import { mkdtemp, mkdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { launchDesktop, closeTemporaryDesktop } from "./desktop.js";

test("offline tutorial computes convolution and repairs an invalid kernel without a project", async () => {
  test.setTimeout(90000);
  const directory = await mkdtemp(path.join(tmpdir(), "easyai-tutorial-e2e-"));
  const stateDirectory = path.join(directory, "application-state");
  await mkdir(stateDirectory);
  const app = await launchDesktop(stateDirectory);
  let failed = false;
  try {
    expect(await app.evaluate(({ app }) => app.getPath("userData"))).toBe(
      stateDirectory,
    );
    expect(await app.evaluate(({ app }) => app.isPackaged)).toBe(
      Boolean(process.env.EASYAI_E2E_PACKAGE),
    );
    const page = await app.firstWindow();
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
    await expect(page.getByTestId("backend-status")).toHaveText(
      "本地服务已就绪。",
    );
    const noProject = page.getByText(
      "尚未打开工程。可选择已有工程目录，或在新目录创建 MNIST 示例。",
      { exact: true },
    );
    await expect(noProject).toBeVisible();
    await page
      .getByRole("button", { name: "打开离线教程", exact: true })
      .click();
    const tutorial = page.getByRole("region", {
      name: "离线教程",
      exact: true,
    });
    await tutorial
      .getByRole("button", { name: "卷积、池化与 Flatten", exact: true })
      .click();
    const lab = tutorial.getByRole("region", { name: "本地数值卷积实验" });
    await expect(lab).toBeVisible();
    const input = lab.getByRole("table", { name: "固定输入，当前窗口已标记" });
    await expect(input.getByRole("cell")).toHaveText(
      Array.from({ length: 25 }, (_, index) => String(index + 1)),
    );
    const previous = lab.getByRole("button", {
      name: "上一个窗口",
      exact: true,
    });
    const next = lab.getByRole("button", { name: "下一个窗口", exact: true });
    const products = lab
      .getByRole("list", { name: "九项乘积" })
      .getByRole("listitem");
    const output = lab.locator("output");
    const grid = lab.getByRole("table", { name: "3×3 输出（点击选择窗口）" });
    // The fixed desktop input is 1..25. The separate all-ones unit fixture is
    // deliberately not substituted into the actual renderer or its state.
    const sums = [63, 72, 81, 108, 117, 126, 153, 162, 171];
    await expect(grid.getByRole("button")).toHaveText(sums.map(String));
    await expect(previous).toBeDisabled();
    for (let position = 0; position < 9; position++) {
      const row = Math.floor(position / 3);
      const column = position % 3;
      await expect(
        lab.getByText(`窗口左上角：第 ${row + 1} 行，第 ${column + 1} 列`, {
          exact: true,
        }),
      ).toBeVisible();
      await expect(products).toHaveText(
        Array.from({ length: 9 }, (_, index) => {
          const value =
            (row + Math.floor(index / 3)) * 5 + column + (index % 3) + 1;
          return `${value} × 1 = ${value}`;
        }),
      );
      await expect(input.locator(".convolution-window")).toHaveText(
        Array.from({ length: 9 }, (_, index) =>
          String((row + Math.floor(index / 3)) * 5 + column + (index % 3) + 1),
        ),
      );
      await expect(output).toHaveText(`窗口求和：${sums[position]}`);
      await expect(
        grid.getByRole("button", {
          name: `输出第 ${row + 1} 行第 ${column + 1} 列`,
          exact: true,
        }),
      ).toHaveAttribute("aria-pressed", "true");
      if (position < 8) await next.click();
    }
    await expect(next).toBeDisabled();
    const weight = lab.getByRole("spinbutton", {
      name: "核第 1 行第 1 列",
      exact: true,
    });
    await weight.fill("2");
    await expect(products.first()).toHaveText("13 × 2 = 26");
    await expect(output).toHaveText("窗口求和：184");
    await expect(grid.getByRole("button")).toHaveText(
      sums.map((sum, index) =>
        String(sum + Math.floor(index / 3) * 5 + (index % 3) + 1),
      ),
    );
    await grid
      .getByRole("button", { name: "输出第 1 行第 2 列", exact: true })
      .click();
    await expect(output).toHaveText("窗口求和：74");
    await expect(products.first()).toHaveText("2 × 2 = 4");
    // Both an out-of-bounds number and an empty field must hide stale results.
    for (const invalid of ["11", ""]) {
      await weight.fill(invalid);
      await expect(lab.getByRole("alert")).toContainText(
        "无效时不显示旧计算结果",
      );
      await expect(output).toHaveCount(0);
      await expect(products).toHaveCount(0);
      await expect(grid).toHaveCount(0);
      await weight.fill("2");
      await expect(lab.getByRole("alert")).toHaveCount(0);
      await expect(output).toHaveText("窗口求和：74");
    }
    await lab
      .getByRole("button", { name: "重置卷积演示", exact: true })
      .click();
    for (const field of await lab.getByRole("spinbutton").all())
      await expect(field).toHaveValue("1");
    await expect(output).toHaveText("窗口求和：63");
    await expect(grid.getByRole("button")).toHaveText(sums.map(String));
    await expect(previous).toBeDisabled();
    await expect(noProject).toBeVisible();
    await expect(
      page.getByRole("button", { name: "开始本次运行", exact: true }),
    ).toBeDisabled();
    expect(failures).toEqual([]);
  } catch (error) {
    failed = true;
    throw error;
  } finally {
    // Retain the temporary state if a normal sandboxed shutdown is unconfirmed.
    let closed = false;
    try {
      await closeTemporaryDesktop(app, failed);
      closed = true;
    } catch (error) {
      console.error("EASYAI_TUTORIAL_CLOSE_FAILED");
      if (!failed) throw error;
    }
    if (closed) {
      try {
        await rm(directory, { recursive: true });
      } catch (error) {
        console.error("EASYAI_TUTORIAL_TEMP_CLEANUP_FAILED");
        if (!failed) throw error;
      }
    }
  }
});
