# Windows 宿主运行与 SSH 本地缓存

原计划 §3.3（第156行）优先 Windows 11 x64 客户端连接 Linux SSH，M5.3/M5.4要求运行、事件持久化、重连与产物同步。本地缓存原先仅允许POSIX，阻断该产品路径；不是等待正式数据才可处理的问题。

第一阶段源码 `06c470cdb83e622e0cdabbf84359ce6a3ff3c4f2` 的 [CI39232044136](https://github.com/T1doo/Easy-AI/actions/runs/39232044136) Linux/Windows 全 SUCCESS。实际 Windows native 步骤包含原ACL/reparse/身份/锁/flush合同及新增三项默认selector集成：本地源枚举与流读取、RunService日志/取消/重启回放、SSH coordinator丢失ACK后的unknown恢复且不重复start。第一阶段产品门仍关，仅测试开启内部接受条件；没有注入storage factory/native API，没有外部SSH或训练。该CI的候选审计/包内backend/Electron/上传也成功：ZIP435167246字节，SHA256 `36cace8fd194eb584181386da33783182cb91770910489ae58cc66518ccb3267`。原d4候选及证据仍保留。

在上述真实native证据和独审确认后，本阶段启用内部 `WINDOWS_NATIVE_CACHE_VERIFIED`，集成测试移除门的monkeypatch，直接断言产品默认selector。关闭门负例和未验证ARM64负例保留；没有env/API/renderer开启权限入口。Windows默认路径与最终包内启动须以新CI结果为准。

`require_local_cache`、`local_directory` 与 RunService 默认选择统一：经过验证的Windows x64选择真实WindowsDirectory；POSIX保留原实现；其它平台拒绝。`limited_names`调用实际NTFS句柄枚举，固定64KiB缓冲、结果上限与调用次数上限，拒重复、畸形记录、不一致完成收据，枚举前后复核持有身份。ACL、reparse、volume、永久kernel owner lock和FlushFileBuffers保持原门，不修权限、不绕过失败、不用POSIX模拟成功。

这只接受宿主缓存，不等于完整Windows SSH。`HostKeyStore.__init__` 仍在 `host_keys.py` 拒绝非POSIX，其持久化目前直接用fcntl/dir_fd；这是下一项具体代码缺口。正式SSH身份/凭据/网络行为、数据、十轮MNIST、硬件与TST33均独立未验证。本地应用与训练环境仍分离，默认不下载、不改教师环境、不执行外部SSH。
