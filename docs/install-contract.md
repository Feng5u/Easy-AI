# M6.3 离线安装计划与生命周期合同

当前交付包括17包/4组目录、离线计划、明确确认、持久任务查询/取消、内部受管进程与复检适配器。**生产安装通道没有接通，确认不创建环境、不安装包。** `executionEnabled` 固定为 false；没有 HTTP execute 路由。不能据此宣称 M6.3 或完整 B 已完成。

## 计划与确认

后端是唯一计划权威。桌面仅提交目录白名单中的 packageIds、固定 profile 和新环境名称或 owned UUID，不接收命令、索引 URL、任意 prefix 或远端目标。teacher-existing 始终只读；应用 Python 与训练 Python 分离。

新环境路径由服务在应用受控 training-environments 下分配 UUID，规划只观察路径缺失，不创建目录。当前 UI 仅提供这个入口。已有 owned 环境须在受控根下、没有末端符号链接、有精确所有权 marker，并经过可信 inspector；生产 inspector 尚未接通，因此该入口拒绝实际使用。

内部 execute 现在可显式传入 bootstrap adapter，按原计划的新 UUID 创建流程运行；API没有接入。OwnedCreation 在目标外建立独占 claim/内核锁，绑定UUID、jobId、planHash和应用根身份；锁后重核指纹/TTL、执行意图落盘后才独占mkdir受控空prefix。它不删除、覆盖、采用已有prefix或复用旧claim。每阶段核根/claim/prefix dev+ino，拒绝符号链接及目录替换。bootstrap必须接受已有空目录；当前只有可控标准库子进程/合成目录测试，**真实conda bootstrap adapter尚缺**，没有创建实际Python环境。

bootstrap停止且nonce/sys.prefix/Python3.11检查通过，才写兼容的两字段owned marker；此前先在prefix内写origin并fsync目录。安装与最终完整复检通过后才写ready；require_ready同时核origin、claim、prefix身份、ready及持久SUCCEEDED/verified job。新job持久事件额外记录creationRequired，API DTO不变，读取兼容原无该内部字段的旧记录。claim缺失时有origin或同env新创建日志就保持INCOMPLETE，不能退回legacy接纳；缺失/冲突/取消/未知均保全目录和证据。失败的新环境不自动修复、清理或解除隔离，需要后续显式安全流程。

easyai-cpu 复用已有 Linux x86_64 / CPython 3.11 CPU 来源及 hash lock。单包请求也展示完整基础闭包，不隐瞒附带包。未锁定的可选包、平台不符或已有版本冲突产生明确 blocker，不猜版本、不自动升级。downloadBytes 是 wheel 下载元数据之和，installedBytes 是解包估计，均不是完整环境占用；未解析时为 null，不宣称零。

计划包含 baselineFingerprint、constraintsHash、planHash 和十分钟有效期。确认必须携带同一 planId/hash，confirmed 与 networkAcknowledged 必须是真正的布尔 true；整数 1 被拒绝。确认会重新核基线与来源 hash；重试同计划返回同一 job。固定错误码不回显用户路径、凭据或原始异常。

## 任务状态与所有权

生产路径只到 AWAITING_EXECUTION，明确 INSTALL_EXECUTION_NOT_ENABLED；取消后为 CANCELLED / INSTALL_CANCELLED_NO_EXECUTION，verified 仍为 false。会话最多64计划，持久目录最多64任务，当前没有自动清理历史或分页入口。任务状态复用 EventJournal 的单写入、fsync、序号及严格完整记录校验；执行意图先落盘再启动子进程。落盘失败关闭该服务的后续写入，不冒称执行成功。此处验证进程重启，不保证断电后的目录项持久性。

内部 executor/inspector 接缝用于合同测试，没有生产调用者。已有 owned 环境执行前先取得内核环境 lease，再核 TTL、基线、来源及计划 hash；独立服务实例也不能并发写同一环境。日志最多 128 条固定生命周期记录，尚不是实际安装器原始日志采集器。

内部状态依次为 INSTALLING、VERIFYING、SUCCEEDED，异常可为 FAILED；取消发出后为 CANCEL_REQUESTED，只有适配器证明已停止才可成为 CANCELLED。未知停止结果或执行异常保留环境 reservation 与内核 lease，不宣称已停止或可以再次安装。关闭会话发取消信号，不释放未证实停止的 lease。

重启后按已知 jobId 可查询持久记录，但不重放安装、不按旧 PID 发信号：未执行确认作废，未确认结束的 INSTALLING/VERIFYING/CANCEL_REQUESTED 保守恢复为 CANCEL_REQUESTED/STOP_UNCONFIRMED 并隔离环境。取得环境内核锁后还会重新读其他任务的持久意图，防止早已打开的第二实例把“锁已释放”误当子进程停止。未知任务没有自动解除隔离入口；重连存活安装子进程、人工核实停止后的恢复/重建仍缺。当前UI没有历史任务列表，不宣称重启自动找回任务卡。历史SUCCEEDED仅表示当时复检结果，新的安装计划仍须重新探测环境。

只有新的 nonce/prefix 匹配的可信复检、精确锁定版本、Python 3.11、torch/torchvision/matplotlib 导入和 tensor 检查都成功，内部合同才允许 verified=true。取消/失败不承诺回滚，保留 changesPossible/needsReprobe。

新增内部 ManagedInstallCommand 复用现有 ManagedSupervisor/ManagedProcess，而非第二套 Popen/进程管理器。POSIX独立进程组、取消升级、两管道排空、持久原始日志；每条stdout/stderr文件上限1MiB，超限继续排空。目标包原始输出重定向stderr，不能伪造stdout完成协议。已知非零退出判 FAILED，与未知停止区分。原训练进程默认日志行为不变，Windows安装进程入口仍拒绝。

OfflineWheelInstaller 实现固定目标 Python 的 isolated pip、require-hashes、only-binary、no-index、已提供本地wheelhouse和锁文件副本；无默认升级、自由命令/requirements URL或自动下载入口。authorized默认false且无API调用者。owned marker核对后同一固定适配器可用于刚bootstrap的新目录。本轮只截获并编译该固定命令，不运行pip；来源hash也在复制lock前重核。ManagedInstallInspector 实现独立选中Python的精确metadata、实际核心imports和小CPU卷积报告；本轮仅在既有应用venv子进程做缺torch的负向只读探测。成功闭环测试仍是标准库子进程写合成inventory，再走合同复检，**不是实际训练环境安装/import成功或tensor效果证据**。

pip的isolated不等于禁用global/site配置，no-index也不移除配置追加的find-links。安装子进程在导入pip前清除所有继承PIP_*并设置PIP_CONFIG_FILE=os.devnull，禁用全部配置文件；不改宿主配置。现有base Python的pip26.2.1真实参数解析（未调用install.run）复现污染后target/远程候选链接，并验证修后只有固定本地find-links且无target/prefix。其他目标pip版本仍须兼容验证，测试机未提供pip时该可选兼容测试明确SKIP，不能算通过。依据：[pip配置文档](https://pip.pypa.io/en/stable/topics/configuration/#pip-config-file)。

## 尚缺与真实验证条件

尚需真实conda bootstrap adapter（已存在独占FS创建与阶段接线）、实际安装适配器与许可/来源/目标授权的生产接线、正向真实环境probe、可选包解析来源、任务历史/保留策略、存活安装子进程重连和未知停止安全解除、远端目标以及实际owned环境纵向验收。现有CPU lock没有被当作上述实现。实际安装器、probe及持久日志现在已有代码基础，但尚未完成真实依赖安装纵向验证。目录fsync仅用于本地origin先于owned marker的顺序，未据此签完整跨目录断电恢复保证。

真实执行前需明确一次性 owned 环境范围、包源和下载预算，展示具体计划后再获得执行授权；SDK/许可另核。不使用教师共享环境、不在应用 Python 安装 torch、不下载训练数据。当前合同/组件/Main/冻结 sidecar 测试均不执行这些动作。

生产接线审计与最小实施顺序见 [install-production-wiring.md](install-production-wiring.md)：真实conda bootstrap、LocalWorkspace inspector和confirm→唯一execute worker仍是代码缺口；不是只缺真实环境验收。本轮仅审计，安装门继续关闭。
