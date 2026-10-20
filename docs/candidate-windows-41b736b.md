# Windows 本机环境运算预检修复候选

- 源码：`41b736b532e008634d01821b02a8d7b493351fcb`，开发分支 `codex/demo-v0.0.0`。
- [CI39346965518](https://github.com/T1doo/Easy-AI/actions/runs/39346965518)：Linux job118381784830、Windows job118381785172 全 SUCCESS。
- ZIP：`easyai-0.0.0-win-x64.zip`，435256032 字节。
- SHA256：`abee57c5f61db79b202f876ff97858a4f1007e51c39dcb2bead276da07b614ec`。
- Artifacts：`easyai-unsigned-win-x64-41b736b532e008634d01821b02a8d7b493351fcb`，上传 SUCCESS，一天留存；未发布 Release。

原计划 §14.2 要求实际基础张量运算，本机预检原仅导入训练库/读版本便报环境就绪。本候选在已选解释器隔离子进程中，no_grad 对全1输入3×3/全1核3×3执行固定 CPU functional.conv2d，shape、finite、值9全部满足后才输出原版本报告。导入成功但运算失败不再误报 READY；预检与运行入口共用此门。成功/失败文案准确覆盖导入与基础CPU运算，明确不训练/不安装。未改超时、输出上限、清理、工程作用域或合同；应用 sidecar 不导入 torch。

实际真实子进程合成模块回归获得旧5RED→GREEN；相关28Python/13TS、完整400TS/955Python/36Node、check、桌面build及独审 PASS。已有独立CPU环境执行生产probe约6.26秒 PASS，只做导入/固定小卷积，没有训练或数据读取。该 Linux CPU 实测不冒充 Windows 训练环境/ABI 验收。

Windows 开发态 step14 与实际包内 step19 执行同组三个完整桌面场景：原示例错误修复/Monaco只读与语义映射、空白13块CNN实际构建/注册引用/数值与shape修复/重复定位/保存重开、离线教程真实算术及错误修复，均 SUCCESS；sandbox/ASAR/正常退出门保留。原生安全、后端冻结/鉴权资源/PID/EOF、打包保护、ZIP审计与上传均 SUCCESS。独审仅允许的 run/jobs 元数据与当前 workflow，不读受限日志/artifact。

此前两份本地证据提交 `4b89ecb59052fea53ac5d734bc957909fa9968bf`、`fdb525557a05be58f9fe942da9087d417493b649` 已经内容/敏感性独审并随必要产品修复同次正常推送；当前源码均以它们为祖先。没有为纯文档单独触发CI、改写旧提交或跳过产品检查。

旧候选 artifact12192547002（435255641字节，SHA256 `94d9873d1692c533e2b0d758aa47d4df3d6123f57686ad24930b13b91cf4eec8`）是另一文件。本执行器在/workspace及可访问/tmp未发现其本地ZIP；历史artifact拒绝范围未解除，已请求明确专用工具单次下载许可或已登录页面保全后转交，仍 pending，未调用下载/受限接口、不改留存。不能将本轮新hash或上传成功冒充旧包已本地保全，也不能声称本机已独立重算任何Windows ZIP。

本轮不是完整 M0–M8/A/B：真实MNIST/SSH、Windows训练环境、TST33干净机、全部可选库安装/许可/硬件矩阵仍未整体验收。TST32 GUI1..25与unit全1=9、旧startup退出Unknown、63px唯一根因未确定及TST34合成外部执行边界保留。无新依赖/数据下载、训练、外部模型服务、许可或安全例外、教师环境修改、main/PR/Release/部署。
