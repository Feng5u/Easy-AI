# 远端 owned 环境受控安装

本轮交付代码与受控合成协议链，真实 SSH/安装/ABI 均 NOT RUN，默认无执行权。不是完整 M6.3 或 B 验收，也没有扩展分发打包范围。

## 产品入口与复用

先通过现有服务器概要、可信指纹确认和认证入口建立当前会话。在包面板选择“当前已认证保存的 SSH 目标”，选择新环境名称或已有 owned 环境 UUID，勾选包/包组，生成计划，核对远端 host/user/owned 根、来源指纹、实际可用容量、下载/解包未知值、预算、版本变化与执行状态，再明确确认。教师 profile 永远只读；普通训练按钮不会安装。

Main 只接受 targetId/projectId/connectionId 等引用，不接受远端 shell、prefix 或来源 URL。后端再核当前 target revision、endpoint、host fingerprint、username 和项目；renderer 不能把另一连接的计划指向教师环境。服务端从私有策略确定 root，prefix 固定为 `root/training-environments/<后端UUID>`。

仍使用 InstallService 的计划/确认/唯一 worker/WAL/取消/最终精确版本、选定 import 和 tensor 门。InstallRegistry 只路由同一生命周期的 target adapter，bootstrap/pip/probe 源码生成器与本机共享；无第二套解析器/安装器。远端只需要已有兼容 Python/conda 来源，临时 helper 与 ManagedProcess/PortableJournal 都是标准库文件，不安装 Easy-AI/FastAPI/Paramiko 到训练目标。

## 必须先提供的最小条件（本轮未提供、未执行）

- 明确授权的隔离 Linux x86_64 目标、已保存概要及当前认证会话、通过可信渠道核验的 host fingerprint、测试账号/预算/窗口。当前 profile 只覆盖 CPython3.11 CPU；GPU、其它系统或不兼容配置不能自动猜测安装。
- 预备的私有 owned root：逐级规范绝对路径、无 symlink、非其它用户可写，root 的 `.easyai-install-root.json` 必须精确标记 `ownedByEasyAI=true`、实际 uid、protocolVersion=1。此标记本身不是操作授权；它与私有策略和明确计划确认共同约束目标。本应用不自动采用已有教师/共享目录，也不创建该远端根。
- 目标上已备、可信审查并单独获准使用的 launcher/stdlib、精确 conda25.9.1 模块树、Python3.11.17/pip 等 explicit bootstrap 归档，以及完整所选核心/可选 wheel 闭包。须提供实际 hash、字节及许可/目标使用授权；不下载、上传或自动修复缺失来源。保留原批准 launcher 可用才能执行后续固定 RPC，无猜测备用解释器。
- 本机应用私有状态中的 `remote-install-runtime.json`，schemaVersion=1、最多16个 targets。每项为现有 OfflineConfiguration 的 launcher/moduleRoot/moduleTreeSha256/bootstrap/wheelhouse/diskBudgetBytes/seconds/executionAuthorized/authorizationExpires，另加 identity（projectId/targetId/targetRevision/endpoint/hostFingerprint/username/root）。文件必须本人拥有、0600、非链接；未配置或默认 executionAuthorized=false 不会启动安装。此文件没有 renderer 写入入口，不得提交仓库。

snapshot 只读真实来源 hash/字节、module tree、owned 基线和 dist-info METADATA，读取 statvfs 的真实可用容量；这些不是 ABI/import 通过。来源/平台/容量不满足就拒绝；解包总量未知仍保持 null。来源 fingerprint、基线、constraints hash、目标身份、预算/时限都进入确认计划。执行前重验；固定 `--offline` conda 与 `--no-index --require-hashes --only-binary` pip，不接受任意 requirements URL，也无全局 upgrade。

## 唯一 writer、取消及重连核验

私有恢复策略先落盘/fsync，再记录 reservation WAL，之后才可能发远端 reserve；预留 ACK 丢失也保留任务与本机环境租约。远端保留独占 job claim、精确 root/prefix inode、来源及身份约束，flock 串行每个 owner；phase intent/index/last-phase/last-writer 全部先于 detached spawn。detached owner 通过 pass_fds 继承同一 writer flock 的 open-file description，父子只 close 各自 FD，不解锁再竞争，且校验 FD 的权限与锁文件 inode。相同 phase 绝不重发 start，只 inspect。失败/取消后不承诺回滚，也不删除部分环境。

SSH 通道关闭不是进程退出。RPC SDK cleanup 未确认时保留实际 channel 与共享 I/O gate；adapter 自身的操作锁也覆盖 cleanup 回收，避免并发误释放别人的 gate。同一认证会话按 launcher 保留 adapter；重新取得 target、切换 launcher 或会话退出时，均可非阻塞回收该会话原 owner，但必须同时取得 cleanup 完成与实际 channel.closed 证据。已持久化且绑定同一 job/plan/phase 的取消会在实际 spawn 前检查；尚未派发时保留独占 serve claim，记录 dispatched=false、quiescent=true、cancelled 与空事件，不伪造退出事件。运行中仍必须取得真实进程静止证据。owner 复用真实 ManagedProcess 进程组取消/管道 drain/close，只有其完成静止证据匹配同一 job/plan/phase 才允许 release；未知永久保留隔离，不按裸 PID 杀、不删锁接管。

未收口安装任务会阻止保存目标的身份或别名编辑（别名也会改变revision），避免失去取消所需的原目标绑定。检查复用既有只读账本重放，不在workspace锁内反向取得安装registry锁。

重新认证同一保存目标后，可在历史报告打开远端任务，使用“核验远端停止状态”或“请求远端 owner 停止”。恢复只 inspect/cancel/release，不继续剩余安装，也不把一个已静止 phase 当成功。授权过期、策略删除或包来源丢失不会把私有恢复快照变成执行权；它只能定位原 claim 并收口。静止收口仍是失败/取消且 needsReprobe=true；已成功、失败、取消或仅登记的终态/等待记录不会被核验降级或重写。

每个后续 writer 的持久 last-writer 意图会使旧 ready 收据失效。新建与已有 owned 环境均须最终真实 import/版本/tensor 门通过后写本次 ready，再经 owner 静止收口，才可作为健康目标。新建的未分配/已分配 bootstrap 阶段按独占 claim/inode 核验，已有环境缺 marker 仍拒绝。

## 证据边界与剩余工作

测试以合成来源、固定 fake SSH channel、捕获 bootstrap/pip/probe 命令和明确 stdlib 打印子进程验证协议。真实 helper↔client 测试实际使用文件 hash、容量、claim、flock、ManagedProcess 和退出证据，但把依赖命令明确替换为打印合成报告；不代表真实安装、torch ABI 或 tensor 执行。

真实正向安装/网络故障/进程重启/目标兼容及图形入口仍须以后具体窗口验收。Windows host storage/CI、CIFAR 安全探测裁决、7张未支持包卡（OpenCV native及六张NLP）、本地任务保留管理/未知停止安全解除、真实数据训练、干净平台包和课堂验收仍未完成；不能表述为“全部只差环境”。本片不发布、不生成新 electron-builder 包、不新建凭据/费用/权限。
