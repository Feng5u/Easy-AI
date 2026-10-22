import type { DiagnosticReport } from "./bridge.js";

// Both preview and export pass this whitelist; never serialize an arbitrary backend DTO.
export function safeReport(
  raw: unknown,
  runId: string,
  eventSeq: number,
): DiagnosticReport {
  const fail = () => {
    throw new Error("诊断报告未通过安全校验。");
  };
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return fail();
  const value = raw as Record<string, unknown>;
  const keys = [
    "reportVersion",
    "scope",
    "code",
    "runId",
    "eventSeq",
    "codeHash",
    "projectRevision",
    "precision",
    "nameState",
    "referenceCheck",
    "objectsTotal",
    "registeredTotal",
  ];
  if (
    Object.keys(value).length !== keys.length ||
    Object.keys(value).some((key) => !keys.includes(key)) ||
    value.reportVersion !== 1 ||
    value.scope !== "local_safe_summary" ||
    value.runId !== runId ||
    value.eventSeq !== eventSeq ||
    typeof value.codeHash !== "string" ||
    !/^[a-f0-9]{64}$/.test(value.codeHash) ||
    !Number.isSafeInteger(value.projectRevision) ||
    Number(value.projectRevision) < 1
  )
    return fail();
  const member = (key: string, choices: string[]) =>
    typeof value[key] === "string" && choices.includes(value[key] as string);
  const count = (item: unknown) =>
    item === null ||
    (Number.isSafeInteger(item) && Number(item) >= 0 && Number(item) <= 500);
  if (
    !member("code", ["RUNTIME_NAME_ERROR", "RUNTIME_EXCEPTION"]) ||
    !member("precision", ["semantic", "scaffold", "none"]) ||
    !member("nameState", [
      "registered",
      "unregistered",
      "not_matched",
      "ambiguous",
      "unavailable",
    ]) ||
    !member("referenceCheck", ["passed", "failed", "unavailable"]) ||
    !count(value.objectsTotal) ||
    !count(value.registeredTotal) ||
    (value.objectsTotal === null) !== (value.registeredTotal === null) ||
    (value.objectsTotal !== null &&
      Number(value.registeredTotal) > Number(value.objectsTotal))
  )
    return fail();
  return Object.fromEntries(
    keys.map((key) => [key, value[key]]),
  ) as unknown as DiagnosticReport;
}
