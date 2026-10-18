import type { RuntimeDiagnostic } from "./runEvents.js";
import { useState } from "react";

const explanations: Record<string, readonly [string, string]> = {
  NameError: [
    "RUNTIME_NAME_ERROR",
    "生成代码使用了尚未定义的名称。请检查旧运行中的对象定义与注册；若代码检查已通过，可能是生成器缺陷，请保留原诊断。",
  ],
  MemoryError: [
    "RUNTIME_MEMORY_ERROR",
    "训练执行报告内存不足。请核对运行环境与批量大小。",
  ],
  ValueError: [
    "RUNTIME_VALUE_ERROR",
    "训练执行遇到无效数值或参数。请查看旧运行对应积木与原始日志。",
  ],
  TypeError: [
    "RUNTIME_TYPE_ERROR",
    "训练执行遇到不兼容的值类型。请查看旧运行对应积木与原始日志。",
  ],
  RuntimeError: [
    "RUNTIME_EXECUTION_ERROR",
    "训练执行报告运行时异常。请核对环境、数据与旧运行对应代码。",
  ],
};
export function RuntimeErrorCard({
  diagnostic,
  sourceReady,
  onLocate,
  onInspect,
  onReport,
  objectsReady = false,
  reportReady = false,
}: {
  diagnostic: RuntimeDiagnostic;
  sourceReady: boolean;
  onLocate(): void;
  onInspect?(): void;
  onReport?(): void;
  objectsReady?: boolean;
  reportReady?: boolean;
}) {
  const [rawVisible, setRawVisible] = useState(false);
  // Never print arbitrary exception names, messages, variable names, filenames or IDs.
  const explanation =
    diagnostic.exceptionType &&
    Object.hasOwn(explanations, diagnostic.exceptionType)
      ? explanations[diagnostic.exceptionType]
      : null;
  return (
    <div className="error" role="alert">
      <strong>训练执行报告了异常</strong>
      <p>
        {explanation?.[1] ??
          "请查看此运行的原始日志与旧运行快照；此异常尚无专用解释规则。"}
      </p>
      {diagnostic.blockId && (
        <button type="button" disabled={!sourceReady} onClick={onLocate}>
          定位旧运行积木
        </button>
      )}
      {diagnostic.exceptionType === "NameError" && (
        <>
          {sourceReady && diagnostic.location && (
            <p>
              {
                {
                  registered:
                    "异常名称对应旧快照中已注册的对象；可能是生成器或执行环境问题。",
                  unregistered:
                    "异常名称对应旧快照中尚未注册的对象；请核对旧对象的注册状态。",
                  not_matched:
                    "异常名称未匹配旧快照对象；可能属于生成代码内部名称或依赖，不推断为学生改名。",
                  ambiguous: "旧快照对象名称存在歧义，无法确定对应对象。",
                  unavailable: "尚无可核实的旧对象解释。",
                }[diagnostic.location.nameState]
              }
            </p>
          )}
          <button type="button" disabled={!objectsReady} onClick={onInspect}>
            检查旧注册对象
          </button>
        </>
      )}
      <button type="button" disabled={!reportReady} onClick={onReport}>
        预览脱敏报告
      </button>
      <button
        type="button"
        aria-expanded={rawVisible}
        onClick={() => setRawVisible(!rawVisible)}
      >
        {rawVisible ? "收起原始错误" : "查看原始错误（仅本地）"}
      </button>
      {rawVisible && (
        <section aria-label="原始结构化错误">
          <p>
            此记录可能包含名称、路径或其他私密内容。请先核对内容再分享；脱敏报告不会包含这些原文。
          </p>
          <pre tabIndex={0}>{JSON.stringify(diagnostic.original, null, 2)}</pre>
        </section>
      )}
      <details>
        <summary>诊断技术摘要</summary>
        <p>
          诊断代码：<code>{explanation?.[0] ?? "RUNTIME_UNCLASSIFIED"}</code>
          ；异常类型：
          {explanation ? diagnostic.exceptionType : "未识别的异常类型"}
        </p>
        {diagnostic.location && (
          <p>
            {diagnostic.location.precision === "none" || !sourceReady
              ? "无法精确定位：旧代码、文件身份或映射尚未核实；不猜测来源积木。"
              : diagnostic.location.precision === "semantic"
                ? `定位精度：已核实旧生成代码第 ${diagnostic.location.line} 行的最窄语义映射。`
                : `定位精度：仅命中旧生成代码第 ${diagnostic.location.line} 行的脚手架映射。`}
          </p>
        )}
        {!diagnostic.location &&
          diagnostic.file === "train.py" &&
          diagnostic.line !== null && (
            <p>
              生成文件 train.py，第 {diagnostic.line}{" "}
              行。积木定位沿用事件来源，尚未按此行号细化。
            </p>
          )}
        <p>
          原始结构化诊断保留在本次运行记录中；此摘要不包含原始消息、名称或路径。
        </p>
      </details>
    </div>
  );
}
