# M6.3 远端 owned 安装设计冻结

本轮只代码与合成协议验证，真实执行门默认关闭。复用 InstallService 的计划、确认、WAL、worker、取消、复检与历史合同，以及既有固定离线 conda/pip/probe 命令；远端是同一生命周期的 target adapter，不是第二套包解析或安装器。真实 SSH、上传包/数据、下载依赖、许可接受与共享环境修改不在本轮授权。

## 身份与路径

请求仅引用已保存 targetId 和当前已认证 projectId/connectionId，不接收shell、远端路径或来源URL。配置由私有 operator 文件提供，绑定endpoint、host fingerprint、username及target revision；每次I/O重验当前lease。远端root由该配置限定，必须绝对规范路径、逐级非symlink、归属正确、无非owner写权限，含精确root ownership marker。prefix仅root/training-environments/后端UUID。教师profile、根外prefix与无owned marker一律拒绝。新环境只独占分配，不覆盖旧目录。

## 来源、预算与计划

远端已准备的launcher/conda模块/explicit bootstrap/wheelhouse均只读真实核对hash和字节；核心/可选锁沿用现有resolver，不自动联网/上传。snapshot绑定remote uid/root inode、来源清单及内容、owned基线、版本与平台和剩余容量。planHash包括目标身份与来源快照、约束、预算/时限，明确确认后重验。资源缺失、容量不足、版本冲突或平台不兼容拒绝执行；解包估计未知必须保持未知，执行过程按实际占用停止，不能伪造容量。

## 唯一writer与未知停止

本机仍用现有InstallService独占租约与写前日志；远端另有持久claim和flock，claim绑定jobId/planHash/envId，未收口不得被另一个任务接管。每个命令先记唯一phase intent，再由标准库portable owner复用ManagedProcess管理进程组、日志与取消。启动ACK丢失只inspect/cancel，绝不再start。断线、应用重启、超时、未知停止都保持隔离，不能把SSH channel关闭当停止证明。新会话必须重验持久身份才可只读观察/取消；只有owner证明确实静止后才收口失败/取消，健康需要重新明确生成计划/真实复检，不自动继续未执行的安装阶段。

## 内部适配合同

InstallService注入target adapter，保留plan/confirm/execute核心；adapter提供prefix、owned、baseline、capability、creation/lease、progress、provision、install、inspection和恢复核验。公共Plan/Job附加目标摘要和remote状态，local默认兼容。生产adapter经ConnectionManager取得固定协议通道；仅允许固定helper的snapshot/reserve/allocate/mark-owned/mark-ready/run/inspect/cancel/release操作，不提供HTTP raw command。助手和ManagedProcess作为临时标准库协议文件运行，无远端Easy-AI/FastAPI安装要求。固定pip/bootstrap/probe source由现有实现共用生成器产生，远端不得自行另解析包或从网络解析依赖。

## 产品状态与验收

UI从已认证保存目标进入同一包面板，展示目标/指纹/owned根/来源快照/实际容量/预算、禁执行状态、确认和任务取消/重连核验。未知停止显示隔离并阻止新writer。成功必须精确版本、全部选定import及tensor真实复检，且owner静止证据匹配同一job/plan/phase。合成协议只证明代码与门，不冒充真实安装。原剩余7卡、CIFAR、Windows及真实桌面/SSH门仍列为未完成。


## 父子交接与会话清理边界

远端 RPC 父进程把已锁定 writer FD 经 pass_fds 交给 detached owner；校验同 inode/私有权限后继续使用同一 open-file description，双方仅 close，不 LOCK_UN。子进程无需与仍持锁的父进程重新竞争。相同 phase 仍只观察，不重试未知启动。

serve 在真正调用 ManagedProcess.start 前核对持久取消的 job/plan/phase。独占 serve claim 与 writer 所有权证明尚未派发，才允许写 dispatched=false、cancelled、quiescent=true、events=[]。运行中取消先于 done 判断，未知/不静止仍不得释放。

ConnectionManager 的认证 lease 按 launcher 保存 InstallSshTransport，target adapter 的重建不丢失 SDK cleanup owner。重取 transport、切换 launcher 与 lease retiring 均非阻塞 reap；operation gate 串行回收，只有实际 channel.closed 且 cleanup thread done 才释放本 owner 持有的共享 I/O gate，不释放其他操作的 gate。
