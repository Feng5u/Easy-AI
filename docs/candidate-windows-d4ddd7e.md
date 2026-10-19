# Windows x64 未签名验证候选

2026-10-19 09:33:34 UTC 通过允许的 GitHub run/jobs 元数据确认，两项 CI job 均 SUCCESS，候选留存步骤 SUCCESS。不是 GitHub Release 或正式发布。

- 源码：`d4ddd7e02ead22d54ac4fea32c3706a733551fc4`
- 分支：`codex/demo-v0.0.0`；该时点远端同 SHA，构建前本地工作区 clean。
- [CI run39230592065](https://github.com/T1doo/Easy-AI/actions/runs/39230592065)
- [Windows job117987314931](https://github.com/T1doo/Easy-AI/actions/runs/39230592065/job/117987314931)
- Linux check job117987315485：SUCCESS，`pnpm check`、`pnpm test`、`pnpm build` 均通过。
- 包：`easyai-0.0.0-win-x64.zip`
- 大小：`435166382` 字节。
- SHA256：`e0e96bf48beccc78c96c866a9be0f1a57ba589f8fe1c6372d477df1a9ce5a860`

Windows 实际通过：项目持久化/native lock/包目录与被阻止计划、Git checkout LF/golden/全部编译测试/图表边界/同步失败回归、NTFS 实验合同、PyInstaller 冻结资源、应用 venv PID/隔离、开发态 E2E、打包输入与归档保护、实际 builder、ZIP 字节审计、包内后端 PID/auth/resources/真实编译/EOF exit0，以及 packaged Electron sandbox、ASAR 身份与正常关闭。没有跳过原测试、放宽沙盒或忽略 fsync。

## 获取与证据范围

在上述 CI run 的 Artifacts 下载：

`easyai-unsigned-win-x64-d4ddd7e02ead22d54ac4fea32c3706a733551fc4`

既有免费 CI 仅留存一天，包含候选 ZIP、builder-manifest.json、candidate-provenance.json、candidate-audit.json。源码/依赖锁/vendor 来源以随包收据为准。下载后对 ZIP 再核大小和 SHA256，GitHub artifact 外层容器的 hash 不是内层 ZIP hash。没有创建 Release/PR/部署。

本执行器依据允许的 jobs 元数据确认步骤成功及审计步骤实际输出的 ZIP hash/大小；没有重试被拒 logs/artifacts/browser 接口，没有下载该 Windows 包或独立读取上传收据。因此不声称执行器在本地重验 Windows ZIP/全部 provenance。完整 builder v2 重放 vendor 变换仍需要原批准 input/vendor，单独 ZIP/收据不能替代。

## 本轮修复与本地验证

`atomic_target` 用不截断的 `r+b` 句柄 fsync，再排他 hard-link 发布；同步、序列化、发布失败和竞争者先发布均保留失败清理与不覆盖。仅对确定的导出/冻结字节文本固定 LF，编译器 golden/实际产物字节断言不变。正常源码修复与之前全部失败证据保全。

本地 57 项针对性 Python、36 项打包保护、完整 `pnpm check`、最终源码实际冻结后端完整 HTTP/golden compile/EOF smoke PASS；只读独审 34 项 PASS，无新增明确 P1/P2。详细命令、日志 hash 和红绿证据见 implementation-progress.md。

## 尚未完成

`distributionReady=false`，`legalReviewComplete=false`。短期 CI 候选不代表完整 A/B 验收。Windows production storage 门仍关闭；没有训练环境或共享教师环境变更。

下一项是干净 Windows 11 x64 普通用户环境的 TST33 与真实课堂 UI 操作（先验证 ZIP hash，再解压启动/退出/编译，不需要 torch、数据或 SSH）。本执行器没有该桌面机器，不冒充 CI Electron smoke 为此项通过。正式 MNIST 十轮效果、真实 SSH/断线/取消/重连恢复、硬件矩阵和第三方法律审核仍 NOT RUN/未完成；相应数据、隔离训练环境、主机和授权条件需单独满足。不绕过系统安全提示、不自动安装训练依赖/下载数据模型或正式发布。

原 Linux 候选和计划/规格/README/依赖锁/golden 均保持；main 仍 `5323f86232529efcfb52131168ad049f01b219f3`。
