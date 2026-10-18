import type { GuideDestination } from "./GettingStarted.js";

const stages = {
  service: [
    "连接本地服务未完成",
    "请查看顶部服务状态；服务就绪后再操作工程。",
    "project",
  ],
  restore: [
    "恢复工程未完成",
    "请前往工程设置重新选择目录；原文件未改。",
    "project",
  ],
  project: [
    "打开或新建工程未完成",
    "请检查所选目录，已有工程请使用打开入口。",
    "project",
  ],
  import: [
    "导入工程未完成",
    "请检查所选工程文件，保留原件后再选择。",
    "project",
  ],
  export: [
    "导出工程未完成",
    "请检查目标位置并选择新文件名；不要关闭仍有未保存修改的工程。",
    "project",
  ],
  save: [
    "保存工程未完成",
    "未保存内容仍保留，自动保存已暂停。可前往工程设置导出当前工程或手动重试保存。",
    "project",
  ],
  selection: [
    "选择环境或数据未完成",
    "请重新选择已有的训练 Python 或数据目录。",
    "environment",
  ],
  compile: [
    "检查与编译未完成",
    "请确认工程已保存，查看代码检查区域；已有诊断可直接定位积木。",
    "compile",
  ],
  start: [
    "启动运行未确认",
    "请求可能已到达服务。请先前往运行历史，点击“刷新运行历史”查看任务状态，确认后再决定下一步。",
    "history",
  ],
  history: [
    "读取历史未完成",
    "暂时无法确认任务状态。请保留当前工程，稍后点击“刷新运行历史”；不要据此重复启动。",
    "history",
  ],
} as const satisfies Record<
  string,
  readonly [string, string, GuideDestination]
>;
export type FailureStage = keyof typeof stages;
export interface OperationFailure {
  stage: FailureStage;
  category: "Error" | "TypeError" | "RangeError" | "Unknown";
}
// Do not stringify untrusted IPC exceptions, messages, paths, causes or stacks.
// Only fixed stage text and an allowlisted error class may reach this card.
export function operationFailure(
  stage: FailureStage,
  reason: unknown,
): OperationFailure {
  let category: OperationFailure["category"] = "Unknown";
  if (reason instanceof TypeError) category = "TypeError";
  else if (reason instanceof RangeError) category = "RangeError";
  else if (reason instanceof Error) category = "Error";
  return { stage, category };
}
export function FailureCard({
  failure,
  onNavigate,
}: {
  failure: OperationFailure;
  onNavigate(destination: GuideDestination): void;
}) {
  const [title, suggestion, destination] = stages[failure.stage];
  const labels: Record<GuideDestination, string> = {
    project: "前往工程设置",
    environment: "前往运行位置",
    compile: "前往检查与运行",
    history: "前往运行历史",
  };
  return (
    <div className="error" role="alert">
      <strong>{title}</strong>
      <p>{suggestion}</p>
      <button type="button" onClick={() => onNavigate(destination)}>
        {labels[destination]}
      </button>
      <details>
        <summary>技术详情</summary>
        <p>
          失败阶段：<code>{failure.stage}</code>；错误类别：
          <code>{failure.category}</code>
        </p>
        <p>此处仅显示安全摘要，原始异常消息与堆栈未包含在卡片中。</p>
      </details>
    </div>
  );
}
