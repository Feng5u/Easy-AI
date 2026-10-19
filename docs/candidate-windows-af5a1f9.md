# Windows native cache 默认集成验证候选

- 源码：`af5a1f96509976f9474eee80b5852b66aea1cee6`
- 分支：`codex/demo-v0.0.0`
- [CI39233339421](https://github.com/T1doo/Easy-AI/actions/runs/39233339421)：Linux job117996371304、Windows job117996371933 均 SUCCESS。
- ZIP：`easyai-0.0.0-win-x64.zip`
- 字节：`435167215`
- SHA256：`7ae7812c414dc5ed1a4d02c7d5e13db758c175c2333200ead0f11e4080bada21`
- 下载位置：上述 run 的 Artifacts，`easyai-unsigned-win-x64-af5a1f96509976f9474eee80b5852b66aea1cee6`，保留一天，上传步骤 SUCCESS。

包内后端 PID/auth/resources/真实编译/EOF exit0、packaged Electron sandbox/ASAR/正常关闭、实际 builder/ZIP 审计和原开发态检查全部成功；Linux pnpm check/test/build全通过。

本轮新增 Windows x64宿主缓存生产 selector。先以真实NTFS默认调用路径完成有界枚举、本地源流读取、RunService ledger/journal取消与恢复、SSH coordinator不确定启动恢复，再启用内部gate；最终CI测试不再临时开启gate或注入storage/native API。ACL/reparse/volume/held identity、永久内核锁和FlushFileBuffers门保持，无POSIX替代/权限修复/吞异常。关闭gate和未验证架构负例保留。

Linux上旧“os.name=nt即未验证”夹具已改成明确关闭gate，保留原拒绝码及零storage/bind/staging断言；父级浏览器确认该两例就是前轮2FAIL944PASS11SKIP的失败，历史FAIL保全。

这是未签名短期验证候选，不是发布。`distributionReady=false`、`legalReviewComplete=false`，完整A/B仍未完成。本执行器依据允许jobs元数据核验step与实际audit输出，不曾下载该包/读取artifact收据，不冒充独立复验ZIP或TST33。原d4/06c/f898候选和收据保留。

下一项具体代码缺口是 `HostKeyStore.__init__` 的独立POSIX门（`services/backend/src/easyai/security/host_keys.py`），而且 `SshClient._open` 在任何出站dial之前先验证该信任存储；当前Windows因此仍明确拒绝完整SSH路径。不得把缓存可用等同主机指纹持久化或SSH全链就绪。原计划§13.2的未知/变化密钥、确认、私有存储、原子写入与身份门须由原生信任库适配继续保持，无需等正式数据才可开发。

真实SSH/正式MNIST/数据、硬件矩阵、干净Windows TST33、法律审核仍未验；没有下载模型/数据、安装训练依赖、修改教师环境或创建Release/PR/部署。main及输入原件未动。
