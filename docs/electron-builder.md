# M8.2 electron-builder 本地打包合同

精确开发依赖electron-builder26.15.3及完整npm integrity在pnpm-lock.yaml。仅同主机Linux x64、unsigned dir+tar.gz，publish=never与配置null，不签名、不部署、不修改sandbox。原appId io.easyai.desktop保留。distributionReady和legalReviewComplete恒false。

`pnpm package:builder` 现在自动在独占新目录执行干净构建，不再采用现有apps/desktop/dist、dist-electron、services/backend/dist或已安装Electron dist树。tsc、Vite、PyInstaller均输出到新建的dist/builder-inputs-<SHA>-<UUID>；Python的dist/work/spec路径分离，资源路径绝对绑定原仓库。Vite关闭ambient publicDir复制，应用资源只来自构建的明确import。生成目录不覆盖旧构建或用户文件。构建源码从固定完整commit的Git archive导出，只允许普通tracked文件，拒source symlink/submodule；忽略文件或未跟踪文件不会被tsc或PyInstaller读取。Node开发依赖按原frozen lock从现有store离线安装到快照内真实node_modules目录（ignore-scripts，不链接任务状态根）；应用构建venv也用原frozen应用锁在快照中新建并offline同步，避免原editable .pth回退工作区源码；只用现有Python基线，同步目标用绝对UV_PROJECT_ENVIRONMENT固定在快照内新.venv，覆盖继承变量、忽略VIRTUAL_ENV；运行前要求路径不存在，运行后核真实目录非symlink，原venv不作为同步目标、不装训练包。编译器/标准库/系统库仍是独立信任边界，不能称完全hermetic构建；隔离Python的PYTHONPATH指向快照。原工作区构建前/封存前再次核HEAD与源码clean，发现修改拒绝而不重置用户工作。

Electron来自精确npm依赖注册的44.9.0 archive，官方get以包内checksums校验后解压到新vendor目录，不采用可能污染的已安装dist。构建可能使用官方缓存或正常工具下载，不下载训练依赖、模型或数据。tar工具沿用builder官方7zip@1.0.0固定校验；没有新增需接受的许可/费用/权限。

手工教程只批准代码中TUTORIAL_FILES列出的七个zh-CN文件，遍历发现任何额外普通文件就拒绝，包括名字不在任何黑名单中的文件；不把整个tutorials树复制进包。离线docs和示例仍按明确单文件集合复制。notices由原许可生成器写入全新目录；第三方依赖和许可审查仍是独立信任边界，不是任意秘密扫描。

干净构建结束封存approved-inputs.json：五个固定组app/backend/offline/notices/vendor、完整sourceCommit、vendor archive hash，以及每个已生成或明确批准文件的path/bytes/hash/mode。只在新payload里将普通数据mode归一为0644、原本有执行位的文件归一为0755（去除特殊位），再封存；不改源码/系统helper权限。打包不能把后来目录遍历结果重新批准为输入。stage前核完整集合，逐登记文件独占复制后再次核验；builder后核stage没有变化，输出backend/offline/notices必须与批准集合逐项相同，ASAR也须精确匹配批准应用文件和字节。vendor仅允许已知electron→easyai、LICENSE复制/改名变换（默认app资源按原vendor批准集合保留）。额外文件即使加入输出inventory也不能通过批准输入校验。

builder-manifest schemaVersion=2保存批准输入收据和输出完整性记录。`pnpm package:builder:verify <输出目录>` 同时校验两层。它不是签名，也不检测源码/依赖中主动嵌入的任意秘密。此前schemaVersion=1实际包及原始证据原样保留；旧PASS只证明当时输出完整性，不证明输入封闭，不是本轮批准候选。旧pnpm package递归复制流程仍保留兼容，亦不据此声称已获新输入封闭保证。

应用在resources/app.asar；完整PyInstaller目录在resources/backend，offline/notices独立于ASAR。产物为artifacts/linux-unpacked和easyai-0.0.0-linux-x64.tar.gz，使用compression=store限制验证耗时。每次独占输出SHA+时间戳目录，已有/失败产物保留；不自动覆盖、清理或发布。

`node scripts/test-frozen.mjs <artifacts/linux-unpacked/resources/backend>` 只证明包内sidecar在临时cwd完成鉴权、资源/离线计划、禁执行登记取消、项目创建/黄金编译和EOF退出。不证明真实Electron编辑、原生picker或干净机。原生sandbox已有拒绝仍不重试/绕过。完整M8.2/TST33的最小条件与当前缺口见release-checklist.md；剩余包卡与远端安装仍有代码范围，不能概括成只差环境。

官方依据：稳定入口https://www.electron.build/v26/；概念文档https://www.electron.build/docs/contents/默认next，实际选项以已装26.15.3配置类型/API为准。
