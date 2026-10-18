# v0.0.0 剩余关键路径（2026-10-18 检查点）

以原 `docs/v0.0.0 plan.md` 的完整 B 为目标，不把 A 或编译/离线替身通过当作交付。此文件是当前代码盘点和滚动估工，不是日期承诺；已撤回的 11/2–11/16 预测不再使用。

## 尚需产品代码

| 原范围 | 已有基础可复用 | 尚缺的原功能 |
| --- | --- | --- |
| M5 SSH | 指纹、密码认证、owner、幂等执行、接续/取消、sealed产物同步已有 | 私钥正常入口（当前method仅password）；显式本地数据上传任务；运行中远端产物同步（当前sealed后）；正常`test:ssh`入口及真实链收口 |
| M6 数据/图表 | 21类积木、三数据集编译、SGD/Adam/Dropout、shape、图表字段与布局已有 | CIFAR10本机preflight当前明确拒绝，运行覆盖未闭合；桌面完整Bundle导出仍缺（现为工程JSON导出） |
| M6.3 受控包管理 | 两份CPU profile lock和来源材料 | package-groups、多选/单包、InstallPlan/InstallJob合同与服务、计划/体积状态/确认、owned新环境执行、取消、复检及UI完整纵向流程；不是“只缺安装验证” |
| M7 | 向导、安全错误卡、结构化诊断、旧运行精确来源已有 | 冻结对象/变量解释、显式原始错误入口及本地脱敏报告代码与定向测试已交付，原生桌面保存仍待实测；七主题本地Markdown与帮助/旧代码/示例副本入口；5×5输入、可编辑3×3核、窗口乘积/求和/输出网格真实数值交互 |
| M8 | 桌面静态构建、PyInstaller onedir、冻结sidecar smoke已有 | electron-builder/`package`入口、完整资源布置及安装包；课堂/失败恢复桌面E2E，当前仅startup smoke；teacher-setup/release-checklist、更新已过时developer-guide、性能记录与最终支持矩阵 |

证据入口：`services/backend/src/easyai/services/local_workspace.py`（CIFAR拒绝）、`services/backend/src/easyai/domain/connections.py`（password）、`packages/training-profiles/`、`packages/block-library/manifest.json`（helpKey不是教程）、`apps/desktop/src/`、`package.json`、`apps/desktop/package.json`、`tests/e2e/startup.spec.ts`、`.github/workflows/ci.yml`、`docs/developer-guide.md`。已有编译器/工作区/runner不从零重写，也不另建重复环境writer。

## 已有主体但仍缺真实验证

- M4：实际Electron sandbox、Blockly拖拽/SVG、Monaco Worker/CSP、原生picker、关闭未保存窗口、从空白搭建并启动的完整课堂流；headless/JSDOM不替代这些操作。
- A：已准备的真实MNIST与健康独立训练Python在安全桌面完成本地闭环；合成IDX和真实stdlib进程只证明执行链，不证明MNIST学习效果。
- B：真实SSH的指纹确认、正式10 epoch、取消/断线/接续/应用重启、日志补读及产物映射；正常安装包在无Node/开发Python的干净目标机验证。未测GPU/OS按原计划说明，但不以skip绕过发布目标的关键失败。
- Windows host storage生产门仍关闭。本轮只修其首个TrustedInstaller祖先阻塞；新原生CI及后续证据通过前，不能把Linux policy/ABI结果签成Windows能力。

## 当前速度与工作量范围

近期已交付的中等已有基础切片，从主源码到证据提交约8–16分钟（Dashboard与traceback切片）；这只适合小/中等已有骨架改动，不能按测试数量算完成百分比，也不能线性外推成新安装器或原生平台的截止时间。

按上述实际未实现工作拆成可交付纵切、包含定向回归与独审修复，当前**低置信代码预算约25–50个有效开发小时**：M5/完整Bundle补齐8–14；M6数据/受控安装8–16；M7剩余产品流3–6；M8包装/E2E/CI/文档6–14。该范围建立在复用现有架构、单一集成者、合同冻结后并行独立教程/包管理合同/打包骨架的条件上；不是人日/日历日期，也不是保证的上限。受控安装与真实安装包的首个纵切完成后，必须用实际耗时重估，不能把尚无基准的大模块包装成精确测速结论。

另预留约6–18个有效小时做真实集成、验收记录及首轮修复；若新Windows原生错误或解析/打包需要结构性方案，重新估工。**资源授权、机器准备、网络下载和训练计算的等待时间单列，当前没有可靠上限，不虚算成固定数周。** 完整B仍须所有原功能和真实证据齐备，不能把上述代码预算结束当作发布验收。

## 最小可行动条件

1. **A真实MNIST/安全桌面**：可保留原Electron sandbox的目标桌面；用户/教师已准备的真实train/test数据路径；已准备的独立训练Python及明确CPU/GPU。没有批准前不下载数据、不在应用Python装torch、不操作个人PC，也不使用`--no-sandbox`或改系统权限。
2. **B真实SSH**：明确授权的隔离Linux目标/账号范围、通过可信渠道核验的指纹、已有训练环境和真实数据路径，以及允许正式运行/取消/断连/恢复的测试窗口。凭据走安全会话，不进入仓库或公开日志。当前不执行这些动作。
3. **受控安装实测**：一次性owned新环境/应用受控prefix、明确包源及下载范围/预算授权；预览具体计划后再确认执行。不得借用或修改老师共享环境；代码/协议/纯计划测试可先继续。
4. **CI**：用户已提供旧f1ecaf7首错日志，因此不再以“缺原日志”暂停修复。本轮四组修复后需要新SHA对应的实际check/desktop结果；若出现新红步骤，再使用其正文判断。此前Actions端点拒绝仍不重试、不绕路、不扩大账号权限。Node20 action警告和ubuntu迁移通知不是已证实失败根因。

本轮CI修复在隔离工作树完成，原工作区的符号/报告WIP已保留后完成定向验证并提交为9f417561c75c49c163752a3ad21a76f4b4fc79d8，未称M7或B整体验收。后续并行交付教程、受控包管理合同与打包骨架时，仍须合同冻结、单一集成者和独立模块边界。上述预算暂不因一个已有基础切片机械递减；安装器/打包首个纵切后重估。
