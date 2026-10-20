# Windows 重复源定位验收候选

- 源码：`3c53280b16fc63f30567520951b3fe3055624863`；开发分支 `codex/demo-v0.0.0`。
- [CI39261021740](https://github.com/T1doo/Easy-AI/actions/runs/39261021740)：Windows job118088364839、Linux job118088365188 全部 SUCCESS。
- ZIP：`easyai-0.0.0-win-x64.zip`，`435255629` 字节。
- SHA256：`74f3522825f4e3f9106319f6af65515ab539304e708bd31e572ad60ccefe3615`。
- 获取：该运行的 Artifacts，`easyai-unsigned-win-x64-3c53280b16fc63f30567520951b3fe3055624863`；上传 SUCCESS，工作流保留一天。

本候选保留[4d60b86空白CNN编辑闭环](candidate-windows-4d60b86.md)，增加同一已选目标的重复显式源定位。Windows step14开发态和step19实际打包应用均执行同一组两个完整E2E场景并PASS；原示例错误修复/Monaco只读与映射、空白13块CNN构建/稳定ID注册引用/权威编译/二次数值编辑/shape修复/保存正常重开全部保留。

新增真实UI验证在每种模式各执行：

1. Linear已经选中，3135编辑产生真实SHAPE_MISMATCH；实际滚轮将该源积木标题完全移出画布，确认原ID仍选中。
2. 点击诊断“源积木”后，整条Linear path回到实际画布可用区域，且块位于页面viewport。再次滚离同一目标并点击同一诊断按钮，仍恢复；原ID不变。
3. 实际修复3136、重编译代码与原始全等后，选中状态保持。再次实际滚离，点击Monaco真实渲染的Linear声明行，源块恢复可见；重复相同行点击仍有效。
4. 随后原保存、正常退出、重启、全workspaces字段/连接/ID/坐标严格恢复及代码全等检查继续通过。

Blockly将内容滚动限制为带半视口padding的范围，宽积木不保证能够整块先滚出。回归如实检查标题完全离开主画布、点击前仍不可见；定位后则严格要求整条path完全进入实际画布，并检查页面viewport。断言不调用reveal/平移/设置选择来帮助恢复，实际动作只有wheel和来源控件点击，没有程序注入图、连接、字段、注册或编译响应。原场景时限、sandbox/CSP/nonce/IPC与正常退出门不变。

修复使用仅内存的显式导航请求（当前工程、目标ID、序号），同ID每次显式操作也会消费一次；隐藏目标页先激活再定位，缺失/外工程请求结束且不迟后重放。原生选择仍走4d60的非导航syncSelection，不重新居中或关闭正在编辑的输入；显式select保留强导航。旧运行快照映射没有连接到当前工程导航，工程文件/schema/依赖锁/权限无扩展。

本地最终pnpm check、pnpm test（399 TS、950 Python、36 Node）及桌面build PASS，独立复核无新增明确P1/P2。一次本地完整测试曾在未改Python的离线fixture teardown报REMOTE_CLEANUP_UNCONFIRMED；原FAIL日志保留，单节点有界重现及完整重跑PASS，本轮Linux完整CI亦PASS，具体线程时序原因未确诊，没有降低清理门或改Python。SVG/React单元使用受控布局度量，不冒充GUI；GUI证明来自本轮Windows开发态与包内真实步骤SUCCESS。

Windows native存储/主机信任、冻结backend、HTTP资源、应用环境隔离、打包保护/build、ZIP审计、包内PID/鉴权/资源/EOF和上传均SUCCESS。本执行器只读取允许的run/jobs审计元数据，未下载或本机独立重算ZIP，未读取artifact正文或重试受限日志接口。

这是未签名短期候选，`distributionReady=false`、`legalReviewComplete=false`；新增验收仅重复诊断/代码源定位切片。完整M4/M7、真实SSH/MNIST训练/效果、硬件矩阵、干净机器TST33、许可和完整A/B仍未完成。没有真实训练、训练依赖安装、数据下载、SSH、凭据/安全权限/共享环境变化、main写入、PR、Release或部署。
