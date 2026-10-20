# M6.3 生产安装接线审计与最小方案

审计范围为原计划14节及M6.3。**本文件记录实施前审计基线。四项缺口现已落实源码与受控验证：固定离线CondaBootstrap、LocalWorkspace inspector注入、confirm唯一execute worker、静止后关闭journal。** 默认执行能力仍false；实际conda/bootstrap/pip/安装/tensor验收NOT RUN。精确来源与权限合同见install-runtime-configuration.md，没有配置真实来源、安装conda、下载依赖或接受新许可。

现有代码核对：

| 环节 | 已有基础 | 实施前缺口（历史） |
| --- | --- | --- |
| 产品入口 | API install-plan/confirm/get/cancel；Main固定IPC；UI包卡、计划/确认/任务状态 | confirm只持久化AWAITING_EXECUTION，executionEnabled固定false，无执行调度 |
| LocalWorkspace.installs | `InstallService(self.root)`，应用/训练根分开 | 未传ManagedInstallInspector，无可信安装runtime配置，已有owned环境实际probe拒绝 |
| InstallService.execute | 环境lease、planHash/TTL/指纹重核、write-ahead、OwnedCreation、provision/install/reprobe、取消及unknown保留锁 | 仅内部seam，没有产品调用者/worker生命周期；不能把接口存在当作端到端可用 |
| OwnedCreation | 受控UUID路径、外置claim/排他锁、空prefix、origin→owned→ready及恢复拒绝 | 真实bootstrap必须接受已分配空目录，不覆盖它、不接管已有prefix；不能以conda默认mkdir行为替换此合同 |
| ManagedInstallCommand | 既有ManagedSupervisor拥有子进程组、取消/日志排空、输出上限；unknown保留lease | 新的runtime必须登记worker并在close时先等静止再关journal；现有InstallService.close只发cancel后关闭journal，不足以直接接并发生产execute |
| OfflineWheelInstaller | 内部真实pip固定argv，no-index/require-hashes/only-binary、来源lock重核、清PIP_*及全局配置 | 默认authorized=false；无可信wheelhouse来源配置、实际安装调用者；不含conda Python创建 |
| ManagedInstallInspector | 选定训练Python独立metadata/import/CPU卷积、nonce/prefix核验 | 尚未接LocalWorkspace；实际正向核心依赖probe未验，现有只读负向探测不能替代 |
| sources/lock | CPU Linux x64 CPython3.11的真实wheel来源/hash/字节清单；17包/4组目录 | 无conda bootstrap explicit包清单/hash/体积/可信launcher记录；可选包未全部解析，已有unresolved blocker应保留 |

本轮按以下四个步骤落实接线，保留设计约束供审查；先限定Linux x64 CPU、本机新UUID受控环境及现有锁支持的包。远端安装、Windows、未知可选包不随这一片启用。

1. **可信runtime配置与bootstrap来源合同。** Main通过受控原生选择已有conda launcher/其base Python、预先获准的本地conda包缓存及wheelhouse；仅后端持有native selection映射，Renderer请求仍只有包ID、profile、新环境名/owned UUID。v0.0.0不自动安装conda。只读核平台、launcher身份、来源清单/hash、CPython3.11精确版本及pip基础包；没有缓存/可信来源时给固定不可执行状态，不隐式联网解析。bootstrap来源尚未确定，不能凭空填版本/hash或把wheel体积当Python创建总量。
2. **CondaBootstrap实现EnvironmentProvisioner.create。** 使用已有ManagedInstallCommand/ManagedSupervisor的进程所有权。固定参数列表、shell=False，不接受命令/频道/URL/prefix自由文本，不使用conda activate。只消费审核的离线explicit bootstrap清单，目标严格为OwnedCreation已锁定/已分配空prefix；执行前/后核claim、应用根、prefix身份，拒绝symlink/替换/未知文件。命令参数与“已有空prefix”兼容性必须按选定conda版本官方接口及本地受控协议验证后冻结，不能用未经验证的create覆盖/force替代。通过固定标准库launcher桥接原始conda输出与已有进程协议，包管理器输出只作raw log，不解释为可信应用事件；取消始终由同一进程owner管理，不增加PID扫描或删除回退。
3. **接通inspector与唯一安装worker。** LocalWorkspace构建唯一InstallRuntime，注入ManagedInstallInspector；UI确认具体计划后，后端原子登记job与唯一worker，并在worker里只调用一次InstallService.execute(executor, provisioner)。确认重放返回原job，不重新启动。先核新bootstrap Python的nonce/sys.prefix/版本，再允许mark_owned；固定OfflineWheelInstaller后完整版本/import/实际tensor复检才mark_ready。每个环境仍只有一个内核lease，未知停止不得释放。关闭流程先发取消、锁外有界等待worker/SDK/pipe drain静止，再关闭journal与release；超时保留owner/lease及可核状态。重启只读恢复，不按历史PID重连/重启安装，不自动解除unknown。
4. **更新能力与计划合同再接UI。** 当前executionEnabled字面false和requiresNetwork字面true不能直接改全局常量。明确backend能力/目标来源是否齐备、实际计划是否允许执行；planHash绑定bootstrap与wheel来源清单、launcher身份、平台、基线指纹和预算，执行前重核。离线已备缓存与未来显式下载分别展示真实网络需求；来源未解析则体积未知并block，下载/解压/安装估计分开，含Python bootstrap部分。只开放已被精确锁覆盖的包，其余保留unresolved。已有确认true/networkAcknowledged true守门不降级；是否需要网络确认取决于最终合同语义，变更须生成合同并补Main/UI兼容测试。

权限边界：

- 规划、配置解析、固定adapter代码和受控本地进程/协议验证可在现有仓库开发授权下继续；它们不是执行真实安装的许可。
- 用户确认具体、可审查的目标/来源/包/真实体积或未知状态/网络预算后，才允许真实bootstrap与pip；本轮这项授权不存在。默认executionEnabled仍false。
- 只写应用受控training-environments下新UUID或有完整owned/ready证据的受控环境；teacher-existing、系统Python、应用venv、任意远端prefix均拒绝。应用环境不得安装torch。
- 现有conda不等于允许修改其base环境或配置。独立私有缓存/配置路径、不继承用户频道/插件/自动更新行为的策略要纳入launcher合同，不能静默接受许可或变更共享conda。
- 真实下载是另一个明确动作：源白名单、内容hash、大小/时间/磁盘预算、部分文件保护与取消均需接线，不由pip/conda自由解析代办。第一片只用已获准且完整的离线缓存，不实现隐式下载。
- 真实环境/训练/数据下载/新凭据/许可接受、CIFAR决策和此前被拒访问均不由本方案启用；不创建Release/部署/更改main。

最低验证顺序：固定argv与能力门（不运行安装）→标准库受控子进程验证取消/日志排空/未知保持lease→LocalWorkspace确认到唯一execute调度的受控协议闭环→重放/关闭/重启时不重跑→来源/指纹/目录替换拒绝→获得一次性owned环境和具体来源预算授权后，才真实bootstrap、离线wheel安装及nonce/import/tensor复检。最后一步记录实际失败/网络情况；前面的绿灯不能称为实际依赖安装通过。

尚需决策的是确切受支持conda launcher/版本与可信离线bootstrap清单、对应来源许可及体积预算。它们影响adapter合同，先补代码时可保持未配置拒绝；不能因尚无真实目标就宣布adapter/生产接线已完成。
