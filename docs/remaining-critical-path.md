# v0.0.0 有界收口盘点（2026-10-19）

2026-10-19 原计划独立欠项继续：Windows x64 dir/ZIP候选接入原封闭输入流程，默认PE ASAR完整性保留并独立重放验证，新增包内sidecar/packaged Electron CI；真实结果尚待本轮CI，Linux候选a4de782及b05证据保留。见[windows-candidate.md](windows-candidate.md)。不以训练/SSH缺资源停止独立开发，也不据本项通过宣称A/B。

2026-10-19 最新真实候选已更新至源码 `a4de782a5efa717868d7180eee18d60e71dfb16a`：Linux x64未签名dir/tar.gz、v2封闭输入/输出、归档逐项核验、包内sidecar及独审PASS；原开发CI两平台SUCCESS。详见[candidate-a4de782.md](candidate-a4de782.md)。包内Electron GUI/干净机TST33/正式训练/SSH仍NOT RUN，distributionReady/legalReviewComplete仍false；不是正式发布或完整A/B。下方旧“最新源码包未生成”描述属于历史状态，以本增量为准。

2026-10-19 Windows sidecar身份修复：父侧确认 [run39211585475](https://github.com/T1doo/Easy-AI/actions/runs/39211585475) Linux SUCCESS，Windows launch/firstWindow已成功，后续ready显示“本地服务启动协议不匹配。”。固定应用venv的CPython redirector可能使launcher PID与服务PID不同，现按CPython自身venv语义直接启动固定基础解释器，严格PID/协议/鉴权/EOF门保留。原错误无类别，不宣称唯一实测根因。新增Windows非GUI身份检查；本轮Windows E2E待自然CI，完整A/B仍未通过。见[windows-application-python.md](windows-application-python.md)。

2026-10-19 启动/恢复等待边界修复：用户已提供Windows launch超时和Linux lost-ACK fresh-resume BUSY正文（Windows片段runId未附，不擅自归属）。锁定版本源码确认Main ESM ready等待环，已改入口非阻塞异步启动；显式resume在锁外有界等旧worker并重核scope/auth，原安全门保留。详见[startup-ready-and-resume-fences.md](startup-ready-and-resume-fences.md)。新修复Windows E2E尚未实测，不能把VM或本地Linux结果当通过。

2026-10-19 新正文后的有界修复：Linux截图已定位`test_running_png_sync_pause_resume_keeps_training_owner_and_rejects_retired_scope`的paused/syncing发布竞争；Windows首错误已定位RunSnapshot.tsx与runSnapshot.ts的大小写/扩展名替换歧义，MISSING_EXPORT SnapshotCode。当前改为原子paused/pending（保持complete/error终态）与唯一组件名RunSnapshotCode.tsx，严格测试/安全门保留。后续CI结果仍待父侧核验；此前“缺这两个错误正文”已解除，不再当当前阻塞。详见implementation-progress末节。

2026-10-19 后续CI证据：父侧通过允许的run/jobs元数据确认 [run39195428530](https://github.com/T1doo/Easy-AI/actions/runs/39195428530) 的Linux/Windows安装门均PASS，原安装阻塞解除。Linux setup/check PASS、pnpm test FAIL（失败正文仍缺）；Windows persistence/实验NTFS/freeze/frozenHTTP资源门均PASS，随后desktop build FAIL、e2e skipped。精确源码a62b48ac04e9c9fd434f9217d78679ebe1a2fa7a本地Linux完整test与desktop build均PASS，不能覆盖云CI FAIL或证明Windows通过。未读被拒接口，本轮无确定修复、不推送触发新CI。最小所需错误段见implementation-progress末节。

2026-10-19 CI增量更正：用户现已提供 run39181255841 的 **Windows** 安装正文：锁文件/供应链校验通过后，`ERR_PNPM_IGNORED_BUILDS: electron-winstaller@5.4.0`。本轮将不需要的 Squirrel 安装脚本精确设为禁止，保持 strictDepBuilds；Linux原job原因仍UNKNOWN，不能据此同因归类。本文原“缺正文/根因UNKNOWN”的合并叙述已由此更正，仅保留未提供正文的job/历史项。当前修复的Windows CI仍待实证，不改旧FAIL为PASS；Actions接口拒绝未重试。详见 [pnpm脚本策略修复](ci-build-policy.md)。

以原 [v0.0.0 plan.md](v0.0.0%20plan.md) 的 M0–M8、TST01–34 与完整 B 为准。原计划基线为 `5323f86232529efcfb52131168ad049f01b219f3`；当前已接受产品源码为 `467a2018194ae131789f45cd62a56ffdc0783950`，配套证据为 `1e345b954f745ac5154f211dcc7200d6527db78b`。后续本次提交仅纠正文档，不新增产品能力。A 和 B 均未获得完整实机验收，不把合成 IDX 的真实 torch 执行或离线合同测试当作 MNIST 效果。

## M0–M8：实现、限制与验收分别记录

| 阶段 | 已有代码及受控证据 | 具体未完成能力或关闭门 | 尚未通过的真实验收 |
| --- | --- | --- | --- |
| M0 安全启动/兼容锁定/CI | Electron 安全配置、受鉴权 sidecar、依赖锁、CI 脚本、冻结后端均已有 | Windows host storage 生产门仍关闭；Windows旧CI根因已知且策略已修，Linux原因未知 | 干净环境复现、保留 sandbox 的真实桌面启动/退出；当前源码 CI 未知 |
| M1 合同基础 | Python 权威 DTO/生成 TS、21 类 manifest、真实 Blockly fixtures、稳定引用、原子保存/未知版本只读已有 | 本次盘点未发现输入齐全的新增合同编码项 | 相关真实课堂操作与最终矩阵仍待验 |
| M2 编译/Bundle | 实际 handler/lowering、shape、训练控制流、源码映射、辅助文件与 Bundle 导出已有 | CIFAR 编译存在不表示安全构造已就绪，见 M6 | TST34：导出后在已准备第三方 Python 脱离应用执行；完整执行覆盖 |
| M3 本地纵向闭环 | 不可变快照、幂等/独占、实际 supervisor、日志/事件/PNG/权重、取消已有；已有合成 IDX 的真实 CPU torch 训练证据 | 不增加假 runner 或假曲线 | 安全桌面上真实 MNIST 正式 10 epoch、指标/取消/退出；A 尚未通过 |
| M4 编辑 UI | 工作区、FieldSymbolRef、Monaco、旧运行冻结映射、保存恢复、导入导出/历史已有 | 本次未发现可独立完成的高价值新增编码项 | 真 Blockly 拖拽/SVG、Monaco Worker/CSP、原生 picker、未保存关闭、空白到运行课堂流 |
| M5 SSH | 指纹/密码/主动选私钥、owner、恢复/取消、日志补读、持续产物同步、显式上传/持久补传均已有 | Windows 门如上；不按未知裸 PID 操作 | 授权目标上的真实认证、正式训练、取消/断线/接续/应用重启、SFTP/跨进程故障与产物映射，见 [ssh-acceptance.md](ssh-acceptance.md) |
| M6 积木/图表/受控安装 | 21 类、三数据集编译、SGD/Adam/Dropout、图表/Undo/快照导出、同一安装服务的本地及远端 owned 接线、持久 reconcile 已有 | CIFAR 官方安全构造仍阻断；17 卡中仅 14 卡有固定元数据闭包，OpenCV native 未核、NLTK 安全阻断、HanLP 依赖只有 sdist 而不支持；执行门默认关闭 | 三数据集/优化器/Dropout 真实覆盖、原生选择、真实安装/退出/import/ABI/tensor、远端安装故障与重启、TST34；14 卡不等于实际可安装 |
| M7 教学/诊断 | 欢迎/数据/服务器/环境向导、错误定位/原 traceback/本地报告、七主题离线教程、5×5/3×3 真实数值卷积已有 | 本次未发现输入齐全的新增教学编码项 | 真桌面删除引用→定位→修复→运行，以及缺依赖→选择健康环境的课堂流 |
| M8 发布验收 | 正式 electron-builder 入口、冻结 sidecar/输入封闭、旧源码实际 Linux 未签名目录/tar 包及随包文档已有 | 最新源码包未生成；精确 native/system 许可审核、项目许可证/最终支持声明未完成 | 干净目标机 TST33、完整十轮/SSH课堂流、性能/平台矩阵和最终报告；旧包不是当前 SHA 的包 |

最近源码的定向结果、实际命令、失败与日志 hash 均保留在 [implementation-progress.md](implementation-progress.md)。最新批次有 50 项包组、99 项服务/远端、13 项 UI、20 项包保护及 check/build/frozen 定向 PASS；独审 26 项与前述重叠，不累加。不代表实机安装、真实桌面、SSH 或完整 B。旧 226 PASS/1 FAIL 原始日志缺失、根因 UNKNOWN，未追溯关闭。

## 纠正范围和旧估工

原计划 §5.5 明确：“后续增加清理功能时再独立设计确认和保留策略。”因此不把本地历史保留/清理管理列为 v0.0.0 必做代码；继续不自动删除历史 runs、不递归清理老师数据。§12.6 要求身份无法验证时提示人工检查，不能凭裸 PID 杀进程；它不要求新增强制解除未知停止/解锁工具。已有安装恢复只观察/取消/释放，不自动重放安装；未知停止继续保留锁，真实恢复链待验。远端目录保留同样不能被解释为自动清理需求。

撤下原 25–50 小时代码与 6–18 小时集成预算：其中包含已实现模块及超出本期的清理工作，不能继续代表当前欠账。没有以测试数量计算完成率或新的日期承诺。签名不是 M8.2 的强制条件，未签名状态必须明确；不扩展升级/卸载或新包装工作。

## 阻塞和下一最小输入

1. **CIFAR 既有裁决待答**：2026-10-18 19:18 UTC 已向用户提出窄例外，尚无答复。固定 torchvision 官方构造会全数据 MD5 并读取 pickle，与当前约束冲突，现保持 `DATASET_CIFAR10_SAFE_PROBE_REQUIRED`、`data.ok=false`，不执行构造、不重复提问、不以替代解析器绕过。详见 [cifar10-preflight.md](cifar10-preflight.md)。下一动作取决于该既有问题的明确答复；目前没有合规实现路径可直接继续。
2. **CI 按 job 分别确认**：最新已知 `e454f97044f84f20347b10f3807220727f2dac1f` / [run39181255841](https://github.com/T1doo/Easy-AI/actions/runs/39181255841)，2026-10-19 00:34:06 UTC，check/desktop 均在 `pnpm install --frozen-lockfile` 失败；前 `3616826e28cef2d2ce4fd874f1bb81a6fcf17d94` / [run39180535293](https://github.com/T1doo/Easy-AI/actions/runs/39180535293)，00:24:34 UTC 同步骤双失败。Windows根因现已确认为未裁决winstaller脚本，本轮明确禁止执行；Linux正文/根因仍UNKNOWN。本地 warm Linux 的同版本 check/build 不能替代 clean Linux/Windows CI。Actions 读取此前被拒绝，本次不重试、不换路径、不重跑；Windows待本修复SHA实证，Linux仍需父侧提供原错误正文后才能有根据地修复。当前源码及本文档 SHA 的 CI 未知。
3. **原计划 A/B 真实验收条件**：一套可保留 Electron sandbox 的图形目标、已准备独立训练 Python/真实 MNIST、明确 CPU/GPU 和窗口；B 另需授权隔离 Linux SSH 账号/范围、可信渠道核验的 host fingerprint、既有训练环境/数据与取消/断连/恢复窗口。凭据走私密入口，不能入库。当前云机无图形桌面且有开发 Node/Python，不能冒充干净目标。此前 sandbox 动作拒绝继续有效，不降低安全开关。
4. **受控安装实测条件**：一次性 owned 环境/私有受控根、可信来源与许可、明确下载/容量预算及具体计划执行授权；老师共享环境只读。三张不支持卡仍是具体产品限制；不以提供服务器就声称它们已支持。当前不安装、下载、import 候选库或变更执行门。
5. **M8 最终条件**：明确实际支持的平台/架构、干净目标机与许可决定。已有旧包完整性证据保留；本轮不生成新包、不新增签名、权限、费用、发布或 PR。

当前没有发现输入齐全且值得继续的新产品编码项；停止新增开发，保全分支、原件、失败记录与已有产物。收到上述相关输入后，只恢复其对应的有界工作；不是把全部欠账统称为“只差环境”。
