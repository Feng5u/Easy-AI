# v0.0.0 剩余关键路径（2026-10-18 检查点）

以原 `docs/v0.0.0 plan.md` 的完整 B 为目标，不把 A 或编译/离线替身通过当作交付。此文件是当前代码盘点和滚动估工，不是日期承诺；已撤回的 11/2–11/16 预测不再使用。

## 尚需产品代码

| 原范围 | 已有基础可复用 | 尚缺的原功能 |
| --- | --- | --- |
| M5 SSH | 指纹、密码/用户主动选取私钥认证代码、owner、幂等执行、接续/取消、sealed及运行中不可变产物收据/增量缓存/字节进度/暂停恢复代码与合成链已有；新增显式上传的确认/预算/owner任务/取消/完成回读代码与合成链；私钥仅合成密钥/Main/HTTP受控验证 | 上传私有持久历史/重启恢复、manifest缺失文件补传已有合成闭环，真实跨进程/目标服务器兼容与未知清理解除仍待验；运行中同步的真实SFTP/断线/目标机验收与跨进程故障证据；`pnpm test:ssh`入口/私有目标配置/窗口守门已实现，本地检查不等于实际链成功；真实链收口仍缺，见ssh-acceptance.md。真实私钥/SSH/native picker未验，Windows安全gate仍关闭 |
| M6 数据/图表 | 21类积木、三数据集编译、SGD/Adam/Dropout、shape、图表字段与布局已有 | CIFAR10本机七文件/双split只读结构初检已有，安全官方构造探测仍阻断（pickle与全数据MD5限制待解），不能READY；真实运行覆盖未闭合；桌面完整Bundle导出入口与快照/hash/新目录保护已实现并定向验证；TST34脱离应用真实运行及原生picker仍未验 |
| M6.3 受控包管理 | CPU lock/来源、17包4组/计划确认取消UI、owned lease/受管进程/固定离线pip/独立probe、持久任务与半成品隔离；新增精确25.9.1离线CondaBootstrap、plan来源/预算绑定、LocalWorkspace inspector、confirm唯一worker及静止关闭；均有受控验证，默认执行禁用 | 可信launcher/conda模块/离线bootstrap及wheel实际来源与许可/目标预算授权、真实兼容/安装/import/tensor纵向验收；ML五包组、scikit-image、Lightning及NLP四库固定元数据/闭包与选择安装/复检已接（14卡可解析、其余3卡未支持，含OpenCV native要求未核），详见install-ml-sources.md、install-cv-sources.md及install-dl-sources.md；Main原生清单选择/预览/明确登记已接（执行授权false），真实对话框仍未验，见install-source-picker.md；普通面板64项只读任务历史/报告与合成重启恢复已接（install-history.md）；仍缺保留管理、存活安装重连/未知停止安全解除；远端owned适配已接入同一InstallService/固定离线命令与真实复检接口，带身份/根/来源预算绑定、预留WAL、唯一writer、取消与只核验收口；目前仅代码/合成协议验证，真实目标故障/重启/安装兼容仍NOT RUN，见remote-install.md。不是完整M6.3/B，见install-runtime-configuration.md |
| M7 | 向导、安全错误卡、旧运行精确来源、冻结对象解释/本地报告及原子新文件发布；七主题本地Markdown、块帮助/只读代码/新目录示例副本入口、5×5/3×3真实数值卷积已实现并定向验证（3cc9a0c） | 真实Electron/原生对话框/课堂错误修复与环境恢复E2E仍未验；不把定向组件链当M7阶段通过 |
| M8 | 复用已缓存Electron/PyInstaller的同宿主Linux x64离线便携目录、package/verify入口、Main冻结sidecar定位、manifest/资源漂移及包内后端smoke；已有许可证/教程/teacher-setup/release-checklist随包，developer-guide已更新；electron-builder26.15.3精确锁定与实际Linux dir/tar.gz入口已接，见electron-builder.md | 最终包/目标机验收须绑定具体SHA证据；项目许可证和精确native/system许可审核；真实Electron/干净机/Windows安装及课堂失败恢复E2E；签名授权（如需要）、性能基准与最终支持矩阵。当前本地产物distributionReady=false，不能替代M8.2实际目标机包验收 |

证据入口：`services/backend/src/easyai/services/local_workspace.py`（CIFAR结构检查/SAFE_PROBE_REQUIRED）、`services/backend/src/easyai/domain/connections.py`（password）、`packages/training-profiles/`、`packages/block-library/manifest.json`（helpKey不是教程）、`apps/desktop/src/`、`package.json`、`apps/desktop/package.json`、`tests/e2e/startup.spec.ts`、`.github/workflows/ci.yml`、`docs/developer-guide.md`。已有编译器/工作区/runner不从零重写，也不另建重复环境writer。

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
4. **CI**：最新父侧实证为 **e454f97044f84f20347b10f3807220727f2dac1f / run39181255841，2026-10-19 00:34:06 UTC，check 与 desktop 均在 pnpm install --frozen-lockfile 失败**，来源 https://github.com/T1doo/Easy-AI/actions/runs/39181255841 。前 **3616826e28cef2d2ce4fd874f1bb81a6fcf17d94 / run39180535293，00:24:34 UTC** 也在同安装步骤双失败，来源 https://github.com/T1doo/Easy-AI/actions/runs/39180535293 。d2ac2bf/run39158015941 的 check SUCCESS、desktop FAIL 已非最新。源码只读核对工作流 Node24.19.0/pnpm11.25.0 与本地版本一致、16 项直接依赖 importer specifier 匹配、本地 installed lock 与源 lock hash相同、两失败 SHA 间安装输入无差异；本地是已有依赖 Linux warm workspace，CI 是 ubuntu-latest/windows-latest clean runner，不能互相替代。缺准确安装错误正文，根因仍 UNKNOWN，不假修或猜 lock mismatch。既有 Actions 端点拒绝不重试、不绕路、不扩大账号权限，不主动重跑同 SHA。本轮后续 SHA CI 另核。

本轮CI修复在隔离工作树完成，原工作区的符号/报告WIP已保留后完成定向验证并提交为9f417561c75c49c163752a3ad21a76f4b4fc79d8，未称M7或B整体验收。M7.3教学纵切已提交3cc9a0c2f016ea7ed51165967b5f4d49f9679bb4。后续交付受控包管理合同与打包骨架时，仍须合同冻结、单一集成者和独立模块边界。上述预算暂不因一个已有基础切片机械递减；安装器/打包首个纵切后重估。

NLP 整批默认闭包裁决已接SentencePiece、spaCy、Transformers、Gensim的来源/预算/原安装器与选中import复检；NLTK候选安全阻断，HanLP三个依赖仅sdist而不支持。模型/语料API不提供，普通import零联网与ABI仍未验，详见[install-nlp-sources.md](install-nlp-sources.md)。14/17卡仅为元数据能力，非实际安装或B验收。
