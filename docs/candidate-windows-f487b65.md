# Windows 教程算术与名称草稿修复验收候选

- 源码：`f487b6531f9e492fba3820d8408f3f372227cec9`；开发分支 `codex/demo-v0.0.0`。
- [CI39264647912](https://github.com/T1doo/Easy-AI/actions/runs/39264647912)：Windows job118100940580、Linux job118100941005 全部 SUCCESS。
- ZIP：`easyai-0.0.0-win-x64.zip`，`435255641` 字节。
- SHA256：`94d9873d1692c533e2b0d758aa47d4df3d6123f57686ad24930b13b91cf4eec8`。
- 获取：该运行的 Artifacts，`easyai-unsigned-win-x64-f487b6531f9e492fba3820d8408f3f372227cec9`；上传 SUCCESS，留存一天。

Windows step14 开发态与 step19 实际打包应用执行同一个 `pnpm test:e2e`，本提交共三个场景，均 SUCCESS：

1. 原示例 Dataset 错误/Undo 修复、Monaco 只读/实际语义高亮与反向源定位、保存重启。
2. 原空白三工作区实际工具箱构建 13 块 CNN、稳定 ID 注册/引用、Python 权威编译、二次数值编辑及 shape 修复、重复同目标诊断/代码定位、严格保存重开。
3. 新增离线教程入口→卷积主题→固定 1–25 输入，验证九个合法窗口的具体高亮值、位置、九项乘积、求和及输出格选择；编辑核首项为 2，右下和为 184、输出各格按实际算术改变；点击首行第二格得 74；非法 11/空值隐藏旧结果，填回 2 恢复，重置全部核 1 与首窗 63。全程无需工程、解释器或数据，不运行训练。

TST32 依原计划 §16.5 的 React 本地数值演示验收；全 1 输入/核每窗和 9 另有真实单元测试，不冒称桌面固定矩阵也是全 1。当前证据为 CI 执行成功与固定测试集合，并未独立读取每条断言的运行日志。

此前 [CI39263027274](https://github.com/T1doo/Easy-AI/actions/runs/39263027274) 的两个失败保留：TrainBatches NAME 仍 MyObject，以及 startup 语义高亮坐标差 63px。该轮教程开发态 PASS 依据测试集合/总计归属，包内未执行；startup 没有单独可归属退出 PID，仍 Unknown，不能用本轮退出门回填。

名称修复有本地真实 Blockly/React RED→GREEN：聚焦输入草稿经实际 move 事件、序列化和刷新后原被 version effect 覆盖；现在只在已提交名称、对象或工程改变时同步。未改稳定 ID、注册、引用、Undo/Redo 或持久化门。Monaco 仅修测试观测：同帧读取目标 ID、精确唯一源码行、唯一高亮、非零尺寸、原 `<2px` 与颜色，两次相邻帧都满足；保留可见/视口断言，无 sleep/放宽阈值/强制渲染，产品控制器未改。63px 的唯一历史根因没有被独立确诊。

本地 `pnpm check`、`pnpm test`（400 TS/2skip、950 Python/19skip、36 Node）、桌面 build 与独审 PASS。真实 SVG 单元中的布局度量受控，不冒充 GUI；GUI 证据来自本轮 Windows 两种模式。Windows native 安全、冻结 backend、资源/鉴权/PID/EOF、打包保护、ZIP 审计及上传全部 SUCCESS。

本执行器只读取允许的 run/jobs 审计元数据，ZIP 字节/hash 来自成功的审计步骤名，未下载或在本机独立重算 ZIP，未重试受限日志/artifact 接口。未签名候选，`distributionReady=false`、`legalReviewComplete=false`；完整 M4/M7、真实 MNIST/SSH、TST33 干净机、TST34 外部训练 Bundle、硬件/许可与完整 A/B 均未整体验收。最小条件见 [独立验收条件](acceptance-prerequisites-20261019.md)。没有新增训练、安装、数据下载、SSH、凭据/安全权限/教师环境变化、main 写入、PR、Release 或部署。
