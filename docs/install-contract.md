# M6.3 离线安装计划与生命周期合同

当前交付是受控安装的前半段：17 包/4 组目录、离线计划、明确确认、会话内任务查询/取消及结果复检合同。**生产安装通道没有接通，确认不创建环境、不安装包。** `executionEnabled` 固定为 false；没有 HTTP execute 路由。不能据此宣称 M6.3 或完整 B 已完成。

## 计划与确认

后端是唯一计划权威。桌面仅提交目录白名单中的 packageIds、固定 profile 和新环境名称或 owned UUID，不接收命令、索引 URL、任意 prefix 或远端目标。teacher-existing 始终只读；应用 Python 与训练 Python 分离。

新环境路径由服务在应用受控 training-environments 下分配 UUID，规划只观察路径缺失，不创建目录。当前 UI 仅提供这个入口。已有 owned 环境须在受控根下、没有末端符号链接、有精确所有权 marker，并经过可信 inspector；生产 inspector 尚未接通，因此该入口拒绝实际使用。

easyai-cpu 复用已有 Linux x86_64 / CPython 3.11 CPU 来源及 hash lock。单包请求也展示完整基础闭包，不隐瞒附带包。未锁定的可选包、平台不符或已有版本冲突产生明确 blocker，不猜版本、不自动升级。downloadBytes 是 wheel 下载元数据之和，installedBytes 是解包估计，均不是完整环境占用；未解析时为 null，不宣称零。

计划包含 baselineFingerprint、constraintsHash、planHash 和十分钟有效期。确认必须携带同一 planId/hash，confirmed 与 networkAcknowledged 必须是真正的布尔 true；整数 1 被拒绝。确认会重新核基线与来源 hash；重试同计划返回同一 job。固定错误码不回显用户路径、凭据或原始异常。

## 任务状态与所有权

生产路径只到 AWAITING_EXECUTION，明确 INSTALL_EXECUTION_NOT_ENABLED；取消后为 CANCELLED / INSTALL_CANCELLED_NO_EXECUTION，verified 仍为 false。会话最多保留 64 个计划；尚无跨重启持久任务账本，不能把重启视为恢复安装。

内部 executor/inspector 接缝用于合同测试，没有生产调用者。已有 owned 环境执行前先取得内核环境 lease，再核 TTL、基线、来源及计划 hash；独立服务实例也不能并发写同一环境。日志最多 128 条固定生命周期记录，尚不是实际安装器原始日志采集器。

内部状态依次为 INSTALLING、VERIFYING、SUCCEEDED，异常可为 FAILED；取消发出后为 CANCEL_REQUESTED，只有适配器证明已停止才可成为 CANCELLED。未知停止结果或执行异常保留环境 reservation 与内核 lease，不宣称已停止或可以再次安装。关闭会话仅发取消信号，不释放未证实停止的 lease；跨进程恢复方案尚缺。

只有新的 nonce/prefix 匹配的可信复检、精确锁定版本、Python 3.11、torch/torchvision/matplotlib 导入和 tensor 检查都成功，内部合同才允许 verified=true。取消/失败不承诺回滚，保留 changesPossible/needsReprobe。测试 inspector 读取合成 inventory JSON，executor 只改测试 fixture；**这些不是实际 Python 导入、tensor 运算或包安装证据**。

## 尚缺与真实验证条件

尚需受控 conda/环境 provisioner、实际安装 executor、可信只读 inventory 与安装后 probe、可选包解析来源、真实有界日志、持久账本/重启恢复、远端目标以及实际 owned 环境纵向验收。现有 CPU lock 没有被当作上述实现。

真实执行前需明确一次性 owned 环境范围、包源和下载预算，展示具体计划后再获得执行授权；SDK/许可另核。不使用教师共享环境、不在应用 Python 安装 torch、不下载训练数据。当前合同/组件/Main/冻结 sidecar 测试均不执行这些动作。
