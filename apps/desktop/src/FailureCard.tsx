import type { GuideDestination } from "./GettingStarted.js";

const stages = {
  runReport: [
    "诊断报告操作未完成",
    "请重新预览本次运行的脱敏摘要，导出时选择尚不存在的新文件。",
    "history",
  ],
  runSubscribe: [
    "运行事件订阅未完成",
    "事件通道不可用不代表训练失败。请查看当前运行状态与只读日志。",
    "history",
  ],
  runSource: [
    "读取运行快照未完成",
    "当前无法载入旧运行来源；请保留本次记录，不使用当前工程替代。",
    "history",
  ],
  runSourceIdentity: [
    "运行快照与本次运行身份不一致",
    "未载入来源；请核对本次记录，不使用当前工程替代。",
    "history",
  ],
  runRead: [
    "读取运行结果失败",
    "不会因此将训练判为失败。若返回身份与本次运行不一致，不采纳该结果；请查看当前运行状态。",
    "history",
  ],
  runCancel: [
    "停止请求未确认",
    "若返回身份与本次运行不一致，不采纳该结果。请等待运行状态确认停止，不要据此认为任务已停止。",
    "history",
  ],
  runResume: [
    "接续读取未确认",
    "不会重新启动任务。若返回身份与本次运行不一致，不采纳该结果；请核对原目标会话与运行状态。",
    "history",
  ],
  runImage: [
    "图片尚不可用",
    "请查看本次运行的已登记输出文件和同步状态。",
    "history",
  ],
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
  actionLabel,
}: {
  failure: OperationFailure;
  onNavigate(destination: GuideDestination): void;
  actionLabel?: string;
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
        {actionLabel ?? labels[destination]}
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
