# v0.0.0 发布验收清单

2026-10-19 run39198400814增量：父侧已确认Linux pnpm test PASS（build当时运行中），Windows安装/后端前置及desktop build全部PASS，当前pnpm test:e2e FAIL。真实桌面阶段仍未通过。已准备旧bridge键名断言的确定本地修复，未推送；该问题未确认是本次首个错误，等待首错误块/expect差异或call log，见implementation-progress末节。未重试浏览器/日志接口或降低sandbox。

2026-10-19 新正文后的有界修复：Linux截图已定位`test_running_png_sync_pause_resume_keeps_training_owner_and_rejects_retired_scope`的paused/syncing发布竞争；Windows首错误已定位RunSnapshot.tsx与runSnapshot.ts的大小写/扩展名替换歧义，MISSING_EXPORT SnapshotCode。当前改为原子paused/pending（保持complete/error终态）与唯一组件名RunSnapshotCode.tsx，严格测试/安全门保留。后续CI结果仍待父侧核验；此前“缺这两个错误正文”已解除，不再当当前阻塞。详见implementation-progress末节。

2026-10-19 后续CI证据：父侧通过允许的run/jobs元数据确认 [run39195428530](https://github.com/T1doo/Easy-AI/actions/runs/39195428530) 的Linux/Windows安装门均PASS，原安装阻塞解除。Linux setup/check PASS、pnpm test FAIL（失败正文仍缺）；Windows persistence/实验NTFS/freeze/frozenHTTP资源门均PASS，随后desktop build FAIL、e2e skipped。精确源码a62b48ac04e9c9fd434f9217d78679ebe1a2fa7a本地Linux完整test与desktop build均PASS，不能覆盖云CI FAIL或证明Windows通过。未读被拒接口，本轮无确定修复、不推送触发新CI。最小所需错误段见implementation-progress末节。

2026-10-19 CI增量更正：用户现已提供 run39181255841 的 **Windows** 安装正文：锁文件/供应链校验通过后，`ERR_PNPM_IGNORED_BUILDS: electron-winstaller@5.4.0`。本轮将不需要的 Squirrel 安装脚本精确设为禁止，保持 strictDepBuilds；Linux原job原因仍UNKNOWN，不能据此同因归类。本文原“缺正文/根因UNKNOWN”的合并叙述已由此更正，仅保留未提供正文的job/历史项。当前修复的Windows CI仍待实证，不改旧FAIL为PASS；Actions接口拒绝未重试。详见 [pnpm脚本策略修复](ci-build-policy.md)。

此表是待执行门槛，不授权发布。状态只使用 PASS / FAIL / NOT RUN；代码存在、单元测试通过或产物生成不能替代真实平台结果。完整 B 尚未通过。

| 项目 | 当前状态 | 必需证据 |
| --- | --- | --- |
| 原计划、原规格与README保存 | PASS | 原始plan116185字节及SHA见implementation-progress |
| Python权威合同/编译器、21类积木 | PASS（定向代码测试） | 真实Blockly fixtures、schema漂移与编译测试；不等于完整课堂验收 |
| 本机Linux便携布局/冻结sidecar | PASS（定向冻结sidecar）／干净机NOT RUN | 源码467a2018194ae131789f45cd62a56ffdc0783950的check/build/frozen记录见implementation-progress；旧builder包不代表当前源码包 |
| 真Electron安全启动/编辑/原生picker/Monaco/Blockly | NOT RUN | sandbox=true；可用桌面上的完整课堂操作，无安全绕过 |
| 开发 CI 安装门（Linux/Windows） | PASS（run39195428530） | 当前安装门已解除，以下两次旧FAIL为历史，不改写旧结果： 父侧提供：e454f97044f84f20347b10f3807220727f2dac1f / [run39181255841](https://github.com/T1doo/Easy-AI/actions/runs/39181255841)，2026-10-19 00:34:06 UTC，两 job 均在 pnpm install --frozen-lockfile 失败；前3616826e28cef2d2ce4fd874f1bb81a6fcf17d94 / [run39180535293](https://github.com/T1doo/Easy-AI/actions/runs/39180535293)，00:24:34 UTC 同步骤双失败。用户已补Windows正文：ERR_PNPM_IGNORED_BUILDS electron-winstaller@5.4.0，本轮策略修复待CI；Linux正文/根因仍UNKNOWN，不能凭步骤名归因 lock mismatch；Actions 访问拒绝继续尊重，无重试/绕路/重跑 |
| Windows 11 x64 | FAIL（CI desktop build） | run39195428530安装、persistence、实验NTFS、freeze和frozenHTTP PASS；desktop build FAIL、e2e skipped，production storage门仍关闭。既有 d2ac2bf/check SUCCESS、desktop FAIL 已是历史，不能继续称最新。新修复 SHA 的 CI 结果另核 |
| macOS/MPS/GPU矩阵 | NOT RUN | 真实设备、驱动、环境与实际结果；不得伪称支持 |
| 至少一个干净目标机包 | NOT RUN | 无Node/开发Python/本机torch，能启动编辑并连接已准备环境 |
| 真实MNIST正式10轮 | NOT RUN | 机器/环境/数据来源、seed/模式、实际指标与截图，非合成曲线 |
| SSH取消/断线/接续/重启/日志与产物映射 | NOT RUN | 授权隔离目标及真实生命周期记录；不以接受请求代替退出 |
| 受控安装 | 受控验证PASS／真实NOT RUN（默认禁用） | 四项生产接线、ML、scikit-image、Lightning与NLP四库元数据闭包已有，14卡可解析/3卡未支持（OpenCV native未核）；Main原生来源清单选择/预算预览/明确登记已接，真实对话框未验；实际可信来源/许可/owned目标授权、conda兼容/真实安装/退出/import/tensor仍未验；不以合成inventory代替 |
| 私钥正常入口 | PASS（合成/受控代码链），真实NOT RUN | 明确选择、秘密不持久、pin/取消；真实私钥/SSH/native picker仍需授权目标机验证 |
| 完整代码Bundle桌面导出 | PASS（定向Main/HTTP/文件链）／TST34 NOT RUN | 已保存编译快照、新目录/辅助文件/hash；真实独立训练运行/原生picker/Windows仍缺，见code-bundle-export.md |
| 显式本地数据上传 | PASS（合成SFTP/协议/组件）／真实NOT RUN | source/target/预算确认、owned任务、取消和回读已接；新增私有持久历史、重选源/认证、只读核验与同slot缺失补传合成链；真实服务器仍未验，见data-upload.md |
| 运行中远端产物同步 | PASS（合成协议/组件）／真实NOT RUN | 不可变收据/raw事件前缀、增量hash缓存、字节进度、暂停恢复；真实SFTP/跨进程故障未验，见live-artifact-sync.md |
| 离线教程、教师准备与已知限制随包 | PASS（资源/定向测试）／真实课堂NOT RUN | 七主题教程、教师文档与冻结资源已有；当前源码整包/真实桌面离线加载仍待验 |
| 许可证与分发授权 | NOT RUN（未完成） | 保留Electron/Chromium及前端/Python许可文本，补精确冻结native/system库审核，项目自身许可证由所有者决定；不得自选新增授权 |
| 正式打包/目标机验收 | PASS（旧源码Linux构建）／当前源码及干净机NOT RUN | electron-builder26.15.3已锁定，Linux dir/tar.gz实际入口已接；未签名状态明确；签名与升级卸载不是本期额外必做项 |
| 性能基准 | NOT RUN | 目标机器、工程/日志规模、启动/编译/图表延迟和内存实际值 |

交付报告须绑定完整SHA、平台/架构、构建命令、测试实际结果和包hash；未验项不得改为PASS。资源manifest只检测相对完整性，不是数字签名或可信来源证明。出现关键启动/SSH/取消/映射失败不放行。Release、部署、签名凭据、收费服务和主分支变更均需另有明确授权。

## M8.2 / TST33 最小目标机条件与当前缺口

原计划M8.2要求“无Node/开发Python的干净机器可启动编辑并连接已备环境”；TST33进一步要求只配置远端训练环境即可启动、编辑和远端运行。以下条件没有提供，当前不执行真实目标测试，不把包生成或HTTP smoke算作通过。

| 最小条件 | 本执行器已知现状 / 需要补充的证据 |
| --- | --- |
| 明确的一台干净图形目标机，OS/架构/版本与一次性测试用户目录；保留Electron sandbox，不用no-sandbox、不改系统安全或helper权限 | 当前云机Linux x86_64，UID1000，无DISPLAY/WAYLAND_DISPLAY/XDG_SESSION_TYPE；且安装了开发Node与Python，不能充当无开发环境干净桌面。此前原生sandbox动作被拒绝，未重试；需要可正常保留sandbox的独立图形目标及已授权测试窗口。 |
| 包转移/解包/启动方式、可写临时项目与导出父目录，桌面交互及结果采集渠道 | 当前没有这样的独立目标或授权渠道。须记录包完整SHA/hash、首次启动、空白/MNIST工程打开编辑保存、Blockly/Monaco/CSP、原生打开/保存/导出picker和退出结果；不能用API模拟点击替代。未签名状态明确告知。 |
| 明确授权的隔离Linux SSH目标/账号、可信渠道核验的host fingerprint、已准备训练Python/torch等兼容环境、真实数据路径、预算和测试窗口 | 当前没有本片可用目标/这些条件与执行授权；凭据经私密会话/原生入口提供，不进仓库/公开日志。先验证连接和环境只读检查，再按明确授权进行远端运行、停止、断线接续及产物回读；不默认下载安装、不触碰老师共享环境。 |
| 不依赖客户端开发Node/Python/本机torch的真实远端运行证据 | 包内sidecar直接运行/黄金编译已能定向验证，但无干净机桌面启动/编辑/原生picker/远端运行的完整证据，仍NOT RUN。 |

代码缺口也仍存在：Windows host storage生产门尚未开放，Windows原生失败正文/后续修复与目标机包仍须推进；17包中3卡无支持闭包（opencv-python、nltk、hanlp），其中OpenCV native要求未核，不能换headless。包卡要补兼容版本/许可/依赖闭包、hash/预算/安装与复检合同及真实验证；NLP语料/模型另需明确条件，不能自动下载。

远端受控安装已新增同一InstallService的owned目标适配、来源预算/身份绑定、预留WAL、唯一owner、取消与断线隔离、只核验收口、最终固定真实复检接口及UI状态，见[remote-install.md](remote-install.md)。目前只有受控合成协议证据，真实远端来源/许可/目标/预算执行授权、安装/ABI/故障/跨进程重启/课堂流仍NOT RUN。恢复不重放安装；未知停止保留锁。三张未支持包卡、CIFAR安全官方构造及Windows生产门仍是具体限制，不能称全部仅待环境。原计划§5.5将清理/保留策略明确留待后续设计；§12.6要求未知身份人工检查，不要求强制解除未知停止。已有恢复收口待真实验收，不再列作未实现。本片停止包装外围开发，无新分发包、Release或PR。

NLP 整批默认闭包裁决已接SentencePiece、spaCy、Transformers、Gensim的来源/预算/原安装器与选中import复检；NLTK候选安全阻断，HanLP三个依赖仅sdist而不支持。模型/语料API不提供，普通import零联网与ABI仍未验，详见[install-nlp-sources.md](install-nlp-sources.md)。14/17卡仅为元数据能力，非实际安装或B验收。

当前逐阶段范围、既有裁决待答和下一最小输入以[有界收口盘点](remaining-critical-path.md)为准；旧估工撤回，本轮停止新增产品及包装开发。
