# 安装任务历史与只读报告

包管理面板打开时自动读取本机持久安装账本，可刷新并选择“查看报告”，无需记住 jobId。Main 使用固定鉴权 GET 路由，renderer 只提交 UUID，不接收路径、命令或自由查询。此入口不安装、不复检、不恢复执行、不取消历史任务，也不清理账本。

沿用最多64任务的硬上限，无自动清理或新增保留策略。读取目录最多消费65项，第65项即拒绝；每任务完整日志最多4MiB/512条记录，原有事件顺序、身份和完整记录校验有效。部分尾行只读忽略，不修复或取得日志写入权。超限、非法目录或日志返回固定错误，不回显私有路径。

列表展示最后持久时间、原记录状态、本次观察状态、来源与停止证据。报告同时保留 recorded 和 observed：重启前 AWAITING_EXECUTION 的确认已经过期，显示 CANCELLED / INSTALL_RESTART_CONFIRMATION_EXPIRED；重启前 INSTALLING、VERIFYING 或 CANCEL_REQUESTED 保持 STOP_UNCONFIRMED 隔离，不按旧 PID 操作，不释放未知 owner、reservation 或 lease。

只有本服务实际登记且仍存活的 worker 才显示存活；外部实例新增记录不会被接管，其等待执行状态保守显示停止未确认。本次读取发现本服务逻辑执行状态却无存活worker，也只返回保守视图，不改内存状态或持久记录。刷新不能解除隔离。

历史 SUCCEEDED / verified 只表示当时复检成功。所有报告 currentEnvironmentVerified 恒为 false，查看报告没有重新检查环境。新计划仍须原有完整基线检查。报告展示的是已保存的生命周期摘要和变更/复检标记，未声称提供完整安装器原始输出归档。

受控验证覆盖成功、失败、过期等待、停止未知、外部实例与存活线程证据、读取不写盘、不释放lease、目录/字节上限、HTTP鉴权、固定Main路由和普通UI入口。冻结sidecar重启检查无已知ID发现及只读报告。没有运行真实安装、probe、训练、下载、SSH或原生Electron窗口；完整M6.3/B仍未通过。
