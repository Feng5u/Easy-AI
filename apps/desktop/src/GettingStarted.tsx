export type GuideDestination =
  "project" | "environment" | "compile" | "history";
export interface GettingStartedProps {
  projectName: string | null;
  readOnly: boolean;
  dirty: boolean;
  mode: "local" | "ssh";
  pythonSelected: boolean;
  dataSelected: boolean;
  remoteBound: boolean;
  compiled: boolean;
  hasRun: boolean;
  ready: boolean;
  blocked: boolean;
  onNavigate(destination: GuideDestination): void;
  onServer(): void;
}
export function GettingStarted(props: GettingStartedProps) {
  const hasProject = props.projectName !== null;
  return (
    <section
      className="panel getting-started"
      aria-labelledby="getting-started-heading"
    >
      <h2 id="getting-started-heading">开始使用 Easy-AI</h2>
      <p>
        从已有工程、MNIST
        示例或空白工程开始。新建时选择目标目录，不会覆盖已有工程或数据。
      </p>
      {!props.ready && (
        <p role="status">本地服务尚未就绪，请等待后再创建或打开工程。</p>
      )}
      <ol>
        <li>
          <strong>工程</strong>
          <p>
            {props.readOnly
              ? "当前工程只读，可以查看或导出原件，不能修改或启动训练。"
              : hasProject
                ? `${props.projectName} · ${props.dirty ? "有未保存修改，先保存再检查" : "已保存"}`
                : "尚未打开工程。请选择目录打开，或新建示例/空白工程。"}
          </p>
          <button type="button" onClick={() => props.onNavigate("project")}>
            前往工程设置
          </button>
        </li>
        <li>
          <strong>运行位置</strong>
          <p>
            {props.mode === "local"
              ? "本机：需要明确选择已有的训练 Python 和数据目录。"
              : "学校服务器：使用服务器上的环境和数据，不要求本机有数据副本。"}
          </p>
          <button type="button" onClick={() => props.onNavigate("environment")}>
            前往运行位置
          </button>
        </li>
        <li>
          <strong>环境与数据</strong>
          <p>
            {props.mode === "local"
              ? `Python${props.pythonSelected ? "已选择" : "尚未选择"}，数据目录${props.dataSelected ? "已选择" : "尚未选择"}。选择完成不代表预检通过，请查看“检查本机环境与数据”的结果。`
              : props.remoteBound
                ? "已有服务器环境与数据绑定；开始运行时仍会复检。"
                : "先保存或选择服务器概要，再显式检查指纹、认证、发现环境和检查服务器数据；保存工程并通过代码检查后再绑定工程。"}
          </p>
          {props.mode === "ssh" && (
            <button
              type="button"
              disabled={!props.ready || !hasProject || props.blocked}
              onClick={props.onServer}
            >
              配置服务器环境与数据
            </button>
          )}
        </li>
        <li>
          <strong>代码检查</strong>
          <p>
            {props.readOnly
              ? "只读工程不能启动训练。"
              : props.dirty
                ? "先保存当前修改，再检查代码。"
                : props.compiled
                  ? "当前保存版本的代码检查通过。环境与数据仍需分别检查。"
                  : "保存后点击“检查与编译”，按问题卡片定位并修复积木。"}
          </p>
          <button
            type="button"
            disabled={!hasProject}
            onClick={() => props.onNavigate("compile")}
          >
            前往检查与运行
          </button>
        </li>
        <li>
          <strong>训练与历史</strong>
          <p>
            {props.hasRun
              ? "已有运行记录，可查看真实状态、日志、指标和只读快照。"
              : "准备好后，在“检查与运行”中单独点击“开始本次运行”。预检和代码检查不会启动训练。"}
          </p>
          <button
            type="button"
            disabled={!hasProject}
            onClick={() => props.onNavigate("history")}
          >
            前往运行历史
          </button>
        </li>
      </ol>
    </section>
  );
}
