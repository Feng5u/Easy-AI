# M3 Main / 本地入口检查点

起点：`db4ff73af93f852787f844bb9c30f0509eeadb57`，开发分支 `codex/demo-v0.0.0`。这是 M3 的实现与有限验证，不是门槛 A/B 完成。M0 的真实 Electron 沙箱启动仍未通过；没有关闭沙箱、调整系统权限或重试被拒绝的 Actions API。

## 实现范围

Python 权威导出 SelectionResult、ProjectSession、RunStartRequest、RunLogs、RunSource，同时生成 schema、TS 与 Electron 使用的声明文件。Main 原生选择器只接收 project/python/data 三种角色，实际路径直接交给后端换成会话 ID；renderer 没有通用文件、HTTP、token 或端口接口。每条 IPC 均检查 sender、主 frame 与精确 app origin。正式启动必须匹配保存 revision 和 ProgramHash，并使用独立 Idempotency-Key；预览编译不会启动训练。

后端默认配置持久运行库，提供工程创建/打开/保存、数据只读预检、选定 Python 的固定 import 探测、真实 RunService 启动、状态/取消/SSE、冻结源码、日志分页和登记产物。创建保留已有 data，拒绝覆盖已有工程。应用环境仍不安装 torch。MNIST/FashionMNIST 原始 IDX 预检不下载数据；CIFAR 本地预检明确报不支持，不能据纯编译支持声称本地已全支持。

Main 解析 SSE 的分片 UTF-8/CRLF，校验 runId、连续 seq、事件类型及 envelope；只在完整事件后推进游标，半尾断线重连不吞事件，组件卸载或 renderer 崩溃/销毁会撤销读取。退出时先询问活动任务、显式取消并等待终态；sidecar EOF 最长等 20 秒，未确认则保持窗口，不强杀负责清理训练进程的 sidecar。异常崩溃/恢复和完整桌面交互仍需桌面环境验收。

调试 UI 已包含新建/打开、环境与数据绑定、快速模式保存、编译/显式运行、取消、真实指标、双路日志、PNG 和旧运行源码/span。UI 不提供假曲线；尚无数据时显示空状态。当前源码面板为基础只读视图；三 Blockly workspace、Monaco、自动保存和历史导航属于 M4，尚未交付。

## 独立审查与修复

合同冻结后按后端与 renderer 独立分工，单一集成者提交。独立只读审查重跑新后端 19 项，发现并复现两项问题后修复：

1. 流先 error 再 abort 时 `reader.cancel()` 返回拒绝而形成未处理 Promise；现显式处理拒绝，同时 error/abort 回归通过。
2. import probe leader 退出后，孙进程仍持有 stdout/stderr；原实现 15 秒报超时却遗留进程和两条线程。真实标准库 fixture 先 RED；现 finally 清理专用进程组、POSIX 读取可停止、有界 join，无法确认则报清理待定。独立 9 项 PASS，确认原孙进程与读线程已退出。没有用 torch 或假 Runner 证明这个修复。

独立 Electron events/workflow/backend 11 项 PASS；renderer 崩溃清订阅和停止超时处理另作源码有限核验。Windows 进程树仍 NOT RUN。

## 实际执行与边界

实际命令：

```sh
pnpm check
pnpm test
pnpm build
node scripts/test-frozen.mjs
```

全部 PASS。普通测试为 **27 TS PASS / 2 CPU opt-in SKIP，186 Python PASS / 1 CPU opt-in SKIP**；保留上游 Starlette/AnyIO 弃用警告。`check` 包括严格 TS/mypy、ruff/格式、合同与真实 Blockly fixture 漂移检查。冻结 smoke 从临时工作目录实际运行 PyInstaller sidecar，认证选择项目/创建/编译，代码与 golden 一致，模板和两个 runtime helper 资源逐字一致，EOF exit0。它未启动 Electron 或训练。

在先前明确批准的独立 CPU 环境中，复用既有 32/16 合成 IDX 和 1 epoch / batch8 工程，没有新安装或下载。明确设置以下变量后执行；测试拒绝覆盖已有 evidence 目录：

```sh
EASYAI_TRAINING_PYTHON=<已批准CPU解释器> \
EASYAI_MAIN_TEST_ROOT=<新证据目录> \
EASYAI_SYNTHETIC_PROJECT=<已有1轮合成数据工程文件> \
EASYAI_SYNTHETIC_DATA_ROOT=<已有合成IDX目录> \
EASYAI_TRAINING_BUDGET_ROOT=<受5GB限制的独立训练目录> \
pnpm exec vitest run apps/desktop/electron/workflow.cpu.test.mts -t 'real CPU bundle'
```

真实结果 PASS，17.76 秒；runId `81d607f1-aef0-423b-9904-21fc8731639b`。MainWorkflow → 认证真实 sidecar → 数据预检/import probe → 已保存快照 → 真实生成 Bundle/torch → Main SSE/源码/图像链全部实际执行。原生选择回调由测试注入合法路径，**不代表 Electron 原生对话框已打开**。13 条连续 canonical 事件、唯一 exit0、SUCCEEDED；3 张 PNG 经登记 ID 读取，其字节数与 SHA256 一致；state_dict/CSV 的终态校验由真实 RunService 执行。数据文件逐一 hash 未变化。真实 loss `2.3290645480155945`，准确率 `0.125`；这些是合成样本执行证据，不是 MNIST 学习效果。

- programHash：`4a367d3633473260a10a6657d4f63cc752ab900e9d988b47878f12bb905c5772`
- codeHash：`67564b0f6308014453f4d7684f0b77688b665ae6c96c39b332bb7cbe1cce8543`
- bundleHash：`d420de2ffb814663375001fe3317a48c4fdde7481623422839b4a18df3d57ca3`

取消命令使用同一组变量、另一个新证据目录及 `-t cancels`。首次运行 FAIL：读取自己 sidecar 的 `/proc/<pid>/task/<pid>/children` 返回 ENOENT，本执行器该路径不可见；finally 实际取消成功，journal 留存 CANCELLED，但那次测试仍记 FAIL。没有从这个错误猜测进程不存在，也没有获取额外系统权限。

随后移除不具备环境前提的外部 `/proc` 检查，**不改变生产取消门、超时或既有进程树测试**，改以实际 supervisor 的唯一 process_exited、空活动任务、干净 sidecar EOF 及重开恢复验证。新测试 PASS，18.40 秒：runId `f66c2068-56b5-4b47-b343-0a4009235bb6`，真实 torch runtime_started 后显式取消，pipeline_cancelled → process_exited → CANCELLED。新 sidecar 重开仍为 CANCELLED、无活动任务。未声称该取消运行完成 epoch，也未声称这次 Main 测试独立观察了训练 PID；Linux 子进程组/无关进程保护另有标准库真实进程测试，真实训练 PID 的外部检查仍 NOT VERIFIED。

新增运行后独立训练目录约 1.99GB，小于 5GB；没有增加 wheel 下载，既有保守累计下载约 509MB，小于 2GB；各运行远低于 30 分钟。数据、权重、日志、机器配置与个人绑定均保存在仓库外，不提交公开仓库。

## 未完成门与下一步

M0 桌面启动仍 FAIL（此前本地 Chromium sandbox 错误）；新 Electron 窗口、原生对话框、点击/卸载/关闭确认行为 NOT RUN。没有新证据允许重复那次启动或改变沙箱。远端 desktop job 已知失败，原因未知，Actions API Forbidden 未重试。需要提供支持安全沙箱的桌面执行环境，以及已失败 job 的实际日志。

真实教师 MNIST 数据的小样本人工运行 NOT RUN；当前没有授权数据源或准备好的实际数据路径，默认 download=False。M4–M8、SSH、跨平台、受控安装、正式教程、发布验收尚未完成。下一步先由父级有限复核本检查点并闭合桌面/实际数据前提；不把这里的 API/CPU 证据升级为 A，更不升级为 B。不创建 PR、Release 或部署。
