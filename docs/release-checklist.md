# v0.0.0 发布验收清单

此表是待执行门槛，不授权发布。状态只使用 PASS / FAIL / NOT RUN；代码存在、单元测试通过或产物生成不能替代真实平台结果。完整 B 尚未通过。

| 项目 | 当前状态 | 必需证据 |
| --- | --- | --- |
| 原计划、原规格与README保存 | PASS | 原始plan116185字节及SHA见implementation-progress |
| Python权威合同/编译器、21类积木 | PASS（定向代码测试） | 真实Blockly fixtures、schema漂移与编译测试；不等于完整课堂验收 |
| 本机Linux便携布局/冻结sidecar | 待本轮记录 | 精确源码SHA、资源hash manifest、暂存目录独立启动/EOF退出记录 |
| 真Electron安全启动/编辑/原生picker/Monaco/Blockly | NOT RUN | sandbox=true；可用桌面上的完整课堂操作，无安全绕过 |
| Windows 11 x64 | FAIL（CI desktop） | 最新736b984/run39154349633失败正文待取得；后续原生新SHA独立验证 |
| macOS/MPS/GPU矩阵 | NOT RUN | 真实设备、驱动、环境与实际结果；不得伪称支持 |
| 至少一个干净目标机包 | NOT RUN | 无Node/开发Python/本机torch，能启动编辑并连接已准备环境 |
| 真实MNIST正式10轮 | NOT RUN | 机器/环境/数据来源、seed/模式、实际指标与截图，非合成曲线 |
| SSH取消/断线/接续/重启/日志与产物映射 | NOT RUN | 授权隔离目标及真实生命周期记录；不以接受请求代替退出 |
| 受控安装 | 受控验证PASS／真实NOT RUN（默认禁用） | 四项生产接线、ML与scikit-image元数据闭包已有，9卡可解析/8卡未支持（OpenCV native未核）；Main原生来源清单选择/预算预览/明确登记已接，真实对话框未验；实际可信来源/许可/owned目标授权、conda兼容/真实安装/退出/import/tensor仍未验；不以合成inventory代替 |
| 私钥正常入口 | PASS（合成/受控代码链），真实NOT RUN | 明确选择、秘密不持久、pin/取消；真实私钥/SSH/native picker仍需授权目标机验证 |
| 完整代码Bundle桌面导出 | PASS（定向Main/HTTP/文件链）／TST34 NOT RUN | 已保存编译快照、新目录/辅助文件/hash；真实独立训练运行/原生picker/Windows仍缺，见code-bundle-export.md |
| 显式本地数据上传 | PASS（合成SFTP/协议/组件）／真实NOT RUN | source/target/预算确认、owned任务、取消和回读已接；新增私有持久历史、重选源/认证、只读核验与同slot缺失补传合成链；真实服务器仍未验，见data-upload.md |
| 运行中远端产物同步 | PASS（合成协议/组件）／真实NOT RUN | 不可变收据/raw事件前缀、增量hash缓存、字节进度、暂停恢复；真实SFTP/跨进程故障未验，见live-artifact-sync.md |
| 离线教程、教师准备与已知限制随包 | 待本轮记录 | 本地文件/hash、七主题教程与无网络加载，不含私密材料 |
| 许可证与分发授权 | NOT RUN（未完成） | 保留Electron/Chromium及前端/Python许可文本，补精确冻结native/system库审核，项目自身许可证由所有者决定；不得自选新增授权 |
| 签名/安装器/升级卸载 | NOT RUN | electron-builder26.15.3已精确锁定，Linux dir/tar.gz实际入口已接；仅本地未签名包，不自动发布，无干净机/安装升级验收 |
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

代码缺口也仍存在：Windows host storage生产门尚未开放，Windows原生失败正文/后续修复与目标机包仍须推进；17包中8卡无支持闭包（pytorch-lightning、opencv-python、nltk、spacy、sentencepiece、transformers、gensim、hanlp），其中OpenCV native要求未核，不能换headless。包卡要补兼容版本/许可/依赖闭包、hash/预算/安装与复检合同及真实验证；NLP语料/模型另需明确条件，不能自动下载。

远端受控安装也仍是代码缺口：当前InstallPlanRequest.targetId只允许local，teacher-existing只读；没有远端安装计划/owned目标边界、来源与预算传输、远端环境锁/受管执行/WAL、取消与重连/未知停止隔离、远端复检及可信回读闭环。已有SSH训练执行/产物同步不是远端包安装器。另有本地历史保留管理和未知停止显式安全解除等既有未实现项。本轮只关闭输入封闭P2，停止包装外围开发，不把这些范围造作已完成或只待环境。
