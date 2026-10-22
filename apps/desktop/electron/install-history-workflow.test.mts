import { expect, it, vi } from "vitest";
import { MainWorkflow } from "./workflow.mjs";
import type { Backend } from "./backend.mjs";
it("saved installation discovery and reports have fixed read-only GET routes", async () => {
  const request = vi.fn(async () => ({})),
    id = "d6851d61-92e8-4909-b02b-2313f1fd585d";
  const workflow = new MainWorkflow(
    () => ({ request }) as unknown as Backend,
    vi.fn(),
    vi.fn(),
  );
  await workflow.invoke("easyai:installJobs:list", []);
  expect(request).toHaveBeenLastCalledWith("GET", "/api/v1/install-jobs");
  await workflow.invoke("easyai:installJobs:report", [id]);
  expect(request).toHaveBeenLastCalledWith(
    "GET",
    `/api/v1/install-jobs/${id}/report`,
  );
  request.mockClear();
  for (const [channel, args] of [
    ["easyai:installJobs:list", [{ limit: 1000 }]],
    ["easyai:installJobs:report", ["../teacher"]],
    ["easyai:installJobs:report", [id, { resume: true }]],
  ] as const)
    await expect(workflow.invoke(channel, [...args])).rejects.toThrow();
  expect(request).not.toHaveBeenCalled();
});
