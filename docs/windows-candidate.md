# Windows 未签名候选

父级补齐构建正文后，确定发现递归ZIP计数把PyInstaller的_internal/base_library.zip当成第二个分发包。Node与Python均已改为artifacts顶层唯一、精确配置文件名，nested ZIP仍保留全部字节校验；红绿复现和32项独审通过。新Windows实际结果待正常修复CI，旧FAIL不改写。

2026-10-19 当前真实结果：`da5a1af18afd4115bf072273cc2b012a65cbee7e` / [run39222623389](https://github.com/T1doo/Easy-AI/actions/runs/39222623389) Linux SUCCESS，Windows打包保护SUCCESS，实际Build unsigned Windows candidate FAIL，后续ZIP/包内E2E/上传SKIPPED，尚无Windows候选。缺该构建步骤首异常/堆栈，父级可用已登录浏览器读取；根因UNKNOWN，不猜测或放宽保护。原Linux候选保留。

后续确定修复：固定ASAR3.4.1在Windows输出native反斜杠，原入口/隐私/集合检查只识别正斜杠。实际ASAR回归旧代码精确BUILDER_ASAR_ENTRY_MISSING，两个库输出边界归一后26项与独审通过；安全门不变。此源码缺陷不冒充旧CI首错，新的正常修复提交/自然CI结果待核。

2026-10-19 实测增量：源码 `ca184beffeb5850adea499e08fb50619d6b01bc7` 的 [run39221894722](https://github.com/T1doo/Easy-AI/actions/runs/39221894722) Linux SUCCESS；Windows原开发E2E成功，新增Packaging input and archive guards（pnpm test:package）FAIL，后续实际打包/包内E2E/上传SKIPPED，尚无Windows候选。首错误正文待父级已登录浏览器读取，根因UNKNOWN；保护不跳过、不猜测同因。下文“待本轮CI”为提交时状态，现以此结果为准。

原计划 §4/§18 M8.2 优先 Windows 11 x64 客户端，但此前 builder 只接受 Linux。开发态 Windows E2E 成功不证明学生能使用包。本轮扩展原有同主机固定 Git 快照、offline/frozen 应用依赖、PyInstaller --onedir、electron-builder26.15.3 流程，生成 Windows x64 `win-unpacked/easyai.exe` 与 ZIP，不增加安装器、签名、发布或训练环境。

已有 Linux 候选 `a4de782a5efa717868d7180eee18d60e71dfb16a` 及其证据提交 `b05a375eb490c6c69828cbbb03fca3a5cc34b3f4` 保留；新候选绑定本次实际构建提交，不冒用旧包。源码、原计划与 D01–D14 不变。

## 原有保护及 Windows 差异

固定 tracked 普通文件 Git archive、构建前后 clean/HEAD、五组批准输入、ASAR 精确内容、资源集合/hash 和独占新目录门均沿用。Node 依赖只复用已有冻结 store，应用依赖只进入新快照 venv；不改教师或训练环境。Windows 通过 pnpm/action-setup v4 登记的 PNPM_HOME 定位固定11.25.0包内 `bin/pnpm.mjs`，使用 Node + argv + shell:false，拒绝错版本/任意入口，不以 shell:true 执行 .cmd。依据是[官方 action v4 安装源码](https://raw.githubusercontent.com/pnpm/action-setup/v4/src/install-pnpm/run.ts)及已装锁定 pnpm 声明；没有新增依赖。

Windows vendor 只允许 `electron.exe→easyai.exe`、原许可证变换与 builder 默认 ASAR integrity PE 资源变换。`win.signAndEditExecutable=false` 禁用额外品牌编辑和签名，却不能阻止更早的 integrity 写入。本机锁定 builder 的 platformPackager/ElectronFramework/electronWin 源码确认这一顺序，因此**不关闭 disableAsarIntegrity**。校验器先核 `input/vendor/electron.exe` 的封存 bytes/mode/hash，再独立临时副本重放锁定 builder 的默认 integrity 变换，比较最终 EXE 全字节 hash/大小，其余 vendor 继续精确闭集。输出 EXE 不能自行批准变更，篡改原始 vendor 也拒绝。完整 Windows v2 verifier 需要保留该原始 input/vendor 文件；上传收据不会假称只有 ZIP 就能独立重放此步骤。

归档审计只读、不解包：Windows ZIP 精确文件集合/大小/hash，拒绝绝对/盘符/ADS/反斜杠/越界、大小写别名、设备名、末尾点空格、重复、链接、特殊类型、加密和未批准目录。Windows 权限合同仅验证 readonly，不声称 POSIX 执行位；Linux tar 保留原精确 POSIX mode。额外已知秘密特征扫描不打印匹配内容，不证明任意秘密或嵌入 PYZ/native 数据安全。没有修改系统 helper 权限或 sandbox。

## CI 实际步骤和获取方式

原 Windows 开发态检查和 E2E 保留。随后运行打包保护、`node scripts/build-candidate.mjs`、固定应用Python `-I scripts/verify-candidate-archive.py <输出目录>`、包内冻结 sidecar PID/health鉴权/资源/EOF smoke，再对 `win-unpacked/easyai.exe` 运行同一安全启动/关闭 E2E，额外严格断言 app.isPackaged 和 app.asar。窗口仍 chromiumSandbox:true、原 timeout、无重试；没有给产品增加测试入口或绕过选择/身份/停止门。

成功后既有免费 CI 仅上传 ZIP、builder-manifest.json、candidate-provenance.json、candidate-audit.json，名称 `easyai-unsigned-win-x64-<完整SHA>`，保留1天、ZIP上限450MiB；不上传源快照/node_modules/venv/任务数据。GitHub Actions artifact 是短期验证候选，不是 Release、上架或正式发布。请在对应运行的 Artifacts 下载；归档字节/hash/源码/依赖锁与 vendor 来源 hash 均在收据中。未因本功能新增付费、凭据、签名材料或许可接受；第三方既有 notices 保留，法律审核和 distributionReady 恒 false。

当前实际 Windows 构建和包内 E2E 结果须以本轮 CI 为准。Linux上的合成PE/ZIP负例和已有Linux候选回归只证明这些校验器，不冒充Windows实测。即使本轮成功，干净机器TST33、真实课堂编辑操作、正式MNIST十轮、真实SSH/断线/取消/恢复和硬件矩阵仍未验；Windows production storage 门及 CIFAR 安全构造限制未改变，完整A/B仍未通过。
