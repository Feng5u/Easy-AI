# Windows native 主机信任默认集成验证候选

- 源码：`c28e955b7787ba1986fc40cd7aa13316f32d7e51`
- 分支：`codex/demo-v0.0.0`
- [CI39236337416](https://github.com/T1doo/Easy-AI/actions/runs/39236337416)：Linux job118006196540、Windows job118006196236 均完整 SUCCESS。
- ZIP：`easyai-0.0.0-win-x64.zip`，435171845 字节。
- SHA256：`9b7e9c8bc4c75778dab872c088be800aa9600b247aca31b2b05871a1e9a3ff46`。
- 获取位置：上述 run 的 Artifacts，`easyai-unsigned-win-x64-c28e955b7787ba1986fc40cd7aa13316f32d7e51`，上传 SUCCESS，保留一天。

先在独立关闭信任门的源码0254cce4b38f16843e8ecd070d1d52f4c96333b0完成实际Windows接受（CI39235525773全SUCCESS），经独审后开启独立trust门。本候选native八项直接断言产品默认True，没有临时开启gate或注入native storage/API。真实NTFS显式TOFU、错误指纹/changed key拒绝、锁/同步/原子发布/目录身份/失败清理合同通过；本地模拟Socket/Transport握手仍走实际HostKeyStore，没有外部连接、认证或真实凭据/信任写入。清理结果不确定保持进程级拒绝，无句柄盲重试。

包内四个trust/cache模块存在检查、backend PID/auth/resources/真实编译/EOF、Electron sandbox/ASAR/正常退出、ZIP完整性审计均PASS；Linux check/test/build全PASS。独审默认增量无新P1/P2，4PASS8nativeSKIP；Linux skip不冒充原生验收。

本执行器只读允许的run/jobs元数据及audit步骤实际字节/hash，未下载或本地独立重验ZIP，未获取artifact正文。日志/下载/browser被拒接口没有重试或绕过。旧候选与失败证据保全。

这是未签名短期验证候选，`distributionReady=false`、`legalReviewComplete=false`。包内模块存在不等于包内真实SSH握手，完整Windows/Linux SSH、正式MNIST训练/硬件矩阵、干净Windows TST33与法律审核仍未完成；A/B未完成。无Release/PR/部署、训练安装/数据下载或共享环境修改。
