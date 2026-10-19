# Windows 主机信任库原生集成

原计划 §13.2 要求未知主机显式核对指纹、变化密钥阻断，禁止 AutoAddPolicy；§3.3/M5要求 Windows客户端连接Linux。缓存 native selector 通过不能替代主机信任库验证。

第一阶段独立关闭信任门，以源码 `0254cce4b38f16843e8ecd070d1d52f4c96333b0` 通过实际 Windows/Linux CI39235525773。独审确认本地原生验收条件后，第二阶段将 `WINDOWS_NATIVE_TRUST_VERIFIED=True` 并移除 native 测试临时开门，验证实际产品默认路径；新一轮 CI 尚待完成。无环境变量/API/renderer开门入口。

新增 WindowsTrustStore/Transaction 复用 WindowsDirectory 的ACL/reparse/volume/held identity、CRT非继承fd、内核锁、原子发布和FlushFileBuffers。应用state父目录必须已经存在且通过私有目录保护，仅使用native child创建末级信任目录，不修权限或创建任意祖先。固定(volume,128位file-id)跨事务钉住root；读前后验证已打开文件身份，1MiB上限。确认事务持有永久 `.known-hosts.lock`，读最新catalog，再按共同TOFU策略写临时bytes、flush/sync/verify后原子发布整份catalog；临时文件在失败时清理。

所有平台共用原有challenge/fingerprint/expiry/endpoint/key解析。首次写入只能显式确认；错误fingerprint拒绝；changed key仍硬拒、没有新替换入口或静默覆盖；原POSIX目录flock/dir_fd保护保持。原子替换catalog文件不等于允许替换已pin主机key。

任何关闭结果不确定时，仍尝试其余owner清理，保留实际owner/原fd/目录链，不盲目重试可能已复用的句柄；进程内之后的新store/transaction/read/write返回 `SSH_TRUST_CLEANUP_UNCONFIRMED`，恢复边界为进程退出释放内核资源。独审发现的清理P2已补回归关闭。

Windows CI使用合成SSH public wire key（没有私钥生成/保存）、本地Socket/Transport模拟握手，真实HostKeyStore校验不关闭。测试实际NTFS确认/重开/changed阻断/并发确认/永久writer锁/sync与发布失败/root替换/非规则文件；socket.create_connection禁止，认证和外部服务器均不运行。第一阶段测试临时开启内部gate，产品仍关闭；实际native CI成功后才评估默认开启，并再验证真实默认路径。

冻结包另有只读模块清单检查，确认host_keys/windows_host_keys/windows_store/remote_cache在实际sidecar内；不会执行归档代码、操作真实SSH信任或连接服务器。该检查与实际native测试互补，不冒充包内真实SSH。
