# 实施进度

记录时间：2026-10-18。所有状态仅描述实际证据，不代表完整 v0.0.0 已完成。

## 原件与基线

- 仓库 `/workspace/Easy-AI`，origin `https://github.com/T1doo/Easy-AI.git`。
- 初始分支 `work`，HEAD、origin/main、在线远端 main 均为 `5323f86232529efcfb52131168ad049f01b219f3`，与计划基线相符；初始工作区干净，没有旧实现或 AGENTS.md。
- 完整阅读 README、原 v0.0.0 和 1544 行计划；原 README/需求未被覆盖。
- Library 受支持下载流程两次失败，停止重试；父级通过十块精确 Base64 传递原件。拼接66400字符，gzip解压后116185字节，SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`。仅在校验相符后写入 `docs/v0.0.0 plan.md`。
- D01–D14 原文登记于 decisions.md，无自行修改裁决。

## M0 — 实际实现，桌面验收仍阻塞

M0.1：PASS，仓库约束、决策、源文件和任务清单已建立。
M0.2：PASS，Node24.19.0/pnpm11.25.0/Python3.11.17，前后端精确锁定；独立新目录冻结安装通过；应用环境无torch。
M0.3：后端和Main启动协议PASS；桌面真实窗口FAIL（下述环境限制），不能宣布整体完成。
M0.4：检查/启动测试及有界CI已实现；远端CI执行结果待记录。

实现：Electron Main/preload、React欢迎页、仅本地的easyai自定义协议、显式四项安全开关、主frame与sender鉴权、固定status方法；256-bit token仅经stdin进入sidecar，不进入argv或renderer；loopback bind(0) socket直接交给Uvicorn；ready之后鉴权health；EOF退出清理；错误/超时有中文状态。

## M1 — 合同基础及保护逻辑已实现并验证

M1.1：Project/BlockIR/ProgramIR/Diagnostic/SourceSpan/Symbol/CompileResult/Event/EpochMetrics/Artifact/RunConfig/Run为Pydantic权威；导出JSON Schema再生成TS，check重生成比较并对生成TS执行strict检查。
M1.2：完整21类manifest、严格schema、范围/槽/import/help/静态handler目标；M2尚未实现emitter，不能把handler目标清单称为可执行编译器。
M1.3：冻结Blockly真实创建/保存/重载fixtures，覆盖空项目、全部种类、MNIST模型、next、shadow、disabledReasons、extraState与引用；Python权威Decoder及Registry校验名称/角色/引用。TS实测删除/Undo保留同一ID，缺失引用保留原值。
M1.4：未来版本/未知块（含禁用子树）只读保护原文；体积/结构/总块数/深度限制；单写锁、revision冲突、备份、fsync/原子替换；保存中断、并发save和close/save竞争有回归。

当前只有0.0.0格式，没有已发布旧格式需要迁移；不猜测未来格式。复制UI、完整FieldSymbolRef展示和工作区生命周期属于M4，尚未实现。

## 实际命令与结果

此云沙箱的用户home不可写，因此仅对开发命令设置以下缓存变量，未改HOME/系统权限：
`UV_CACHE_DIR=/workspace/.uv-cache UV_PYTHON_INSTALL_DIR=/workspace/.python XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache`。
Electron官方安装器下载时使用`NODE_USE_ENV_PROXY=1 ELECTRON_CACHE=/workspace/.electron-cache`；未使用第三方镜像。

| 命令/检查 | 结果 | 证据 |
| --- | --- | --- |
| `pnpm install` + `uv sync --project services/backend --python 3.11` | PASS | 两锁文件已产生，源码依赖精确版本 |
| `pnpm install --frozen-lockfile --dir /tmp/easyai-repro-jo_6jja3` | PASS | 新开发目录107个Node包 |
| `uv sync --frozen --project /tmp/easyai-repro-jo_6jja3/services/backend --python /workspace/.python/cpython-3.11.17-linux-x86_64-gnu/bin/python3.11` | PASS | 新venv安装43个应用/开发包 |
| `pnpm check` | PASS | TS strict（含合同与测试）、ruff、mypy strict、schema/TS同步、真实Blockly fixture同步、Prettier |
| `pnpm test` | PASS | 最终11 TS +32 Python，全43项通过 |
| `pnpm build` | PASS | Vite renderer、Electron main/preload、PyInstaller目录sidecar |
| frozen sidecar在`cwd=/tmp`启动并请求health/catalog，关闭stdin | PASS | ready、鉴权health、21类目录、exitCode0，不依赖仓库cwd |
| `timeout 15s pnpm dev` | FAIL | Chromium拒绝本环境SUID sandbox配置，未显示窗口 |
| `pnpm test:e2e` | FAIL | Process failed to launch；明确chromiumSandbox:true，无关闭sandbox参数 |
| SSH/真实训练/Windows安装包/发布验收 | NOT RUN | 未配置SSH、训练环境、数据或目标机器；未安装torch、未下载数据、未发布 |

Python测试有1个上游Starlette/AnyIO弃用警告，未吞掉或屏蔽；不影响断言。

## 独立审查

M1合同候选冻结并同步通过后，安排只读独立agent审查。发现并复现4项：并发保存丢编辑、close/save竞争、超大整数OverflowError、非ASCII鉴权头返回500。全部修复并新增针对性回归。独立审查者复核：4项针对性测试PASS，无文件修改，这4项不再阻断M0/M1。未把此结论扩展成未实现功能的验收。

## 准确阻塞与下一项

动作：在本云环境启动Electron桌面（pnpm dev/test:e2e）。结果：明确失败，非权限审批拒绝、非未知执行结果。原因：Chromium SUID sandbox helper不满足运行条件；环境也未提供Xvfb。未使用--no-sandbox、未改helper所有者/权限、未申请安全权限。
下一项：在支持Chromium sandbox的桌面环境完成窗口启动/关闭/renderer隔离实测；已准备Windows CI smoke，但执行结果必须单独核实。M0此项通过后依次M2→M3；编译器与协议不需要训练环境。到M3真实训练之前，需明确批准独立训练环境安装或提供已有健康解释器及已准备数据；真实SSH需单独目标/凭据授权。

门槛A：未达到。门槛B：未达到。没有真实训练指标或安装包支持声明。

## 全阶段任务清单（验收前保持未勾选）

- [x] M0.1 — AGENTS.md、docs/decisions.md、implementation-progress.md
- [ ] M0.2 — pnpm workspace、desktop、backend、锁文件、dependency-baseline.md
- [ ] M0.3 — Electron main/preload、backend/main.py、health、安全 IPC
- [ ] M0.4 — CI 基础、开发脚本
- [x] M1.1 — domain/project、ir、events；packages/contracts
- [x] M1.2 — packages/block-library/manifest.json、schema
- [x] M1.3 — compiler/decode、domain/symbols、headless fixtures
- [x] M1.4 — migrations、ProjectService 初稿
- [x] M2.1 — compiler/validate、lower、data/model emitters
- [x] M2.2 — train emitter、基本 viz emitter、runtime helper 合同
- [x] M2.3 — source_map、compile API、golden tests
- [x] M2.4 — examples/mnist-cnn、Bundle 导出测试
- [ ] M3.1 — project_service、run_service、snapshot
- [ ] M3.2 — runtime/supervisor.py、entry.py、easyai_runtime.py
- [ ] M3.3 — runners/local、LocalFileTransport
- [ ] M3.4 — SSE、指标、基本产物服务与调试 UI
- [ ] M4.1 — WorkspaceManager、三个标签页、blockly 注册
- [ ] M4.2 — FieldSymbolRef、注册面板、字段校验
- [ ] M4.3 — Monaco 只读面板、代码映射交互
- [ ] M4.4 — 自动保存、导入/导出、历史快照查看
- [ ] M5.1 — ssh_client、host_keys、连接 UI
- [ ] M5.2 — EnvironmentService 的只读探测
- [ ] M5.3 — runners/ssh、SFTP stage、supervisor --start
- [ ] M5.4 — 重连、远端取消、产物同步、数据绑定/显式上传
- [ ] M6.1 — Dataset adapters、optimizer、全部参数校验
- [ ] M6.2 — FigureInspector、完整 viz emitters、ArtifactPathResolver
- [ ] M6.3 — package-groups、training-profiles、InstallJob、安装 UI
- [ ] M6.4 — 图像/指标/文件面板、code bundle 导出说明
- [ ] M7.1 — Welcome、项目/服务器/环境/data 向导
- [ ] M7.2 — diagnostics rules、运行错误卡片、问题报告
- [ ] M7.3 — tutorials/zh-CN、卷积交互组件、帮助关联
- [ ] M8.1 — 单元/集成/e2e/SSH/安全测试与 CI
- [ ] M8.2 — PyInstaller、electron-builder、资源复制
- [ ] M8.3 — 真 MNIST 课堂验收记录、支持矩阵
- [ ] M8.4 — README 开发入口、developer-guide、teacher-setup、release-checklist

最终补充：完整测试为11 TS +32 Python。真实Blockly Undo已实测；桌面e2e静态类型检查通过，运行仍受sandbox环境阻塞。

## 开发分支检查点与远端核验

功能检查点完整SHA：`d918a73b2ba446453b484a79920848619bc7907c`，已正常推送`origin/codex/demo-v0.0.0`；在线远端该分支与本地一致。远端main仍为`5323f86232529efcfb52131168ad049f01b219f3`。没有创建PR或Release。

执行`gh run list --repo T1doo/Easy-AI --branch codex/demo-v0.0.0 --limit 3 --json databaseId,headSha,status,conclusion,url`时，GitHub Actions API读取返回`Forbidden`。因此远端CI状态为NOT VERIFIED，不能称已启动或通过；未重试、未扩大权限或改走其他读取通道。此项为API访问拒绝，不是sandbox自动审批拒绝。

M0总体仍未完成：实际桌面启动FAIL、远端CI未能核实。M1合同基础的上述证据可独立审查；M2尚未开始，不因合同测试通过就宣称已生成/执行训练代码。


## M1 父级独审续修（保存限制与锁崩溃恢复）

基于父级独审，先新增定向回归并实际复现RED：
`uv run --project services/backend pytest -q services/backend/tests/test_project_persistence.py` → 3 FAIL（超5MiB保存未拒绝、深度超64保存未拒绝、真实持锁子进程kill后仍无法取得写锁）。首次命令误用了相对于仓库根不存在的tests路径，结果为NOT RUN；修正测试路径后得到上述3项真实失败，不将路径错误计作RED。

修复：读写共用`validate_project_bytes`，先对本次实际UTF-8序列化字节执行5MiB、JSON深度64、schema与Decoder校验，任何拒绝都发生在备份与项目写入之前。JSON深度64明确包含Blockly next/block包装；语义input嵌套64、总块数500是另两道独立上限，500不表示任意串行链都满足JSON深度。实际fixture next链27层（原始JSON深度63）可保存→重开；28层（深度65）在同一门被拒绝，原件和已有备份逐字节保持。未改原计划资源限值。

锁改为持有整个项目服务生命周期的OS文件锁句柄：POSIX flock / Windows msvcrt byte-range lock。固定版本marker通过已fsync临时文件+不覆盖的hardlink原子发布；正常关闭只释放内核锁，不unlink，避免等待者锁住不同inode。进程崩溃由内核释放，不查询PID，不盲删文件。每次save验证所持fd与路径inode一致；不继承锁到子进程。

旧版本空lock没有可验证的kernel所有权，返回`PROJECT_LOCK_LEGACY_UNVERIFIED`并保持原文件不动；不自动接管仍可能属于旧应用的锁。Windows代码先锁定再读取marker，避免在另一进程持有mandatory byte lock时先读报错。当前Linux已实测；Windows分支尚未实测，新增Windows CI定向测试步骤供以后可核验的运行使用，不能据此声称Windows通过。

新增定向用例8项：两种超限不改原件/备份、真实子进程活跃互斥与异常退出恢复、close后保持同inode、旧空锁只读保留、替换锁拒绝旧owner写入、next链保存重开边界27/28。定向GREEN 8 PASS；全量`pnpm check` PASS、`pnpm test`为11 TS +40 Python PASS。已有1项上游弃用警告保留。

父级提供独立邮箱证据：GitHub认证邮件报告提交`5b3a4c7f5465052c4600f784bd022a3df48f5cf3`的[run39111551340](https://github.com/T1doo/Easy-AI/actions/runs/39111551340)在2026-10-18 08:29:08 UTC已终态，**check成功，desktop失败**。这是父级提供的job级证据，不是本执行器读取Actions API；desktop失败步骤和原因未知，不能归因为本地sandbox。原Actions读取Forbidden仍保留，未重试或改用其他通道。后续诊断需要维护者提供该desktop job的具体失败日志原件，或恢复相应授权读取能力。

本续修不重跑桌面e2e、不改变sandbox、不安装训练环境。M0桌面总体验收仍FAIL；已知该次远端check PASS，desktop FAIL，细节NOT VERIFIED。M2仅可按父级许可提前准备独立纯编译部分，须保留阶段阻塞与typed IR要求；当前尚未开始，先交本次两P2的修复证据供复核。

## M2.1–M2.4 独立纯编译检查点

父级明确允许在M0桌面门仍FAIL时提前完成独立的M2纯编译工作；这是局部并行推进授权，不修改M0→M8验收顺序，也不代表门槛A/B通过。本阶段起点为`967cec351a39fc6e5734ebce7934b1ae9b6bf511`，相对计划基线`5323f86232529efcfb52131168ad049f01b219f3`包含已记录的M0/M1实现与修复；开发分支为`codex/demo-v0.0.0`。未覆盖原README、原需求或计划原件。

完成：

- M2.1：BlockIR只在lower边界使用；生成器仅消费Pydantic严格类型的TransformDef、DatasetDef、LoaderDef、ModelDef/LayerSpec、TrainingSpec、FigureSpec。训练根依赖闭包、确定性定义顺序、白名单import去重；未引用草稿不执行。8类模型节点含Sequential子层与Dropout；纯数学shape检查支持MNIST/FashionMNIST/CIFAR10，不自动修补Linear。MNIST输出轨迹为16×28×28→16×14×14→32×14×14→32×7×7→1568→128→10。
- M2.2：按IR生成展开的模型类、前向、CE与SGD/Adam训练测试循环；训练损失按实际样本加权，测试准确率使用实际计数。main guard、seed、CUDA/MPS/CPU选择、平台worker与CUDA pin、显式data root、download=False。quick编译产物明确1epoch与1024/256样本上限，不能当作完整例子。三阶段图使用Agg、显式Axes、反归一化、有限样本与finally关闭；权重保存state_dict。代码从未导入/执行torch。
- M2.3：同一块支持构造/前向等多个真实行span，提供最窄semantic优先的行反查；纯编译HTTP端点校验授权、工程ID和requestId。ProgramHash排除坐标/revision/时间，保留稳定块ID。冻结真实Blockly示例的代码/IR/source-map golden；`node scripts/update-golden.mjs`是人工更新命令，测试只比较、不自动刷新。
- M2.4：`examples/mnist-cnn/project.easyai.json`由真实Blockly序列化得到，包含训练前样本、每epoch双曲线、训练后预测；另有真实Sequential+Dropout+Adam fixture。Bundle导出到调用者指定的新目录，包含train.py、entry.py、easyai_runtime.py、source-map、ProgramIR、环境说明、命令说明及逐文件SHA256/bundleHash。拒绝覆盖已有目录或symlink；不依赖Easy-AI包import。辅助模块随PyInstaller目录构建复制为资源。环境说明明确torch/torchvision/matplotlib版本尚未实测，未安装训练依赖。

辅助模块只定义后续运行合同与独立导出模式：标准库事件/CSV/产物文件、取消请求、路径保护与原子写入。测试实际执行这些标准库操作和entry的故意NameError子进程；它们不是真实训练。应用模式不创建第二份journal。尚未实现/验收M3 RunService、Supervisor、快照/SSE或真实训练链。

独立审查：由独立只读worker复现并关闭4项问题：Axes折线错误方法、模型名撞生成局部变量/内置函数、逻辑路径缺outputs前缀、前缀归一化后的256字符边界不一致。修复后独立定向15 PASS；此前41项lower/emit/compile定向PASS。新增测试覆盖全部生成局部绑定的保留名、跨层路径解释、AST防注入、层参数真实改变代码、仅epoch改变不重写模型、确定性hash/map、完整导出与拒覆盖。没有降低测试或安全门。

执行环境变量（没有修改HOME）：`UV_CACHE_DIR=/workspace/.uv-cache UV_PYTHON_INSTALL_DIR=/workspace/.python XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache`。

实际命令与结果：

- `pnpm contracts`：PASS，重新导出Python权威ProgramIR/CompileRequest/CompileResponse schema及TS。
- `node scripts/update-golden.mjs`：PASS，仅生成并AST解析源码，未执行训练代码。
- `uv run --project services/backend pytest -q services/backend/tests/test_lowering.py`：16 PASS。
- worker的`.venv/bin/python -m pytest tests/test_emission.py -q`：11 PASS。
- `uv run --project services/backend pytest -q services/backend/tests/test_compilation.py`：15 PASS。
- 首次全检查发现runtime目录Ruff配置查找不同导致格式门FAIL；已显式统一使用backend/pyproject.toml并格式化，未放松规则。

M1锁限制续记：父级此前审查是源码/测试设计的有限审查，未宣称父级独立重跑；本执行器Linux新marker锁已有实际子进程证据。旧空lock仍只读拒绝且无迁移入口；持久marker使旧应用降级打开只读；原子发布依赖目标文件系统支持os.link；Windows锁分支NOT RUN。不得从Linux证据推出跨平台支持。

NOT RUN/仍阻塞：真实torch/Matplotlib计算、真实MNIST、训练环境安装、SSH/硬件、Windows运行、桌面e2e新运行。本地桌面sandbox失败与已知远端desktop job失败保持原结论，远端失败原因未知；未重试被Forbidden的Actions读取。门槛A未达到，门槛B未达到。

下一项：先取得可用桌面sandbox环境及失败CI job日志以闭合M0；M3可先实现不依赖torch的协议/状态/快照，但真实训练前必须提供已有健康Python训练解释器、兼容torch/torchvision/matplotlib与本地已准备数据绝对路径，或明确授权在独立训练环境安装。默认不下载数据、不改教师共享环境。真实SSH另需目标/凭据授权。本阶段不建立PR、Release或部署。

最终验证：`pnpm check` PASS；`pnpm test` **11 TS +82 Python PASS**（保留1条上游Starlette/AnyIO弃用警告）；`pnpm build` PASS（Vite、Electron TS、PyInstaller目录构建）。本次新build后执行`services/backend/.venv/bin/python /tmp/easyai-m2-frozen-smoke.py`：从`/tmp`启动真实冻结sidecar，以token认证POST完整Blockly示例编译，返回代码与golden逐字一致，两个helper资源与源码逐字一致，stdin EOF后进程exit0，全部PASS。冻结sidecar实测证明纯编译可工作，不证明生成训练程序已运行。

`services/backend/.venv/bin/python`用`importlib.util.find_spec('torch')`检查应用环境：False。`git diff --check` PASS。计划仍为116185字节、SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原需求及README hash保持不变。提交前`git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0`确认main仍为计划基线，开发分支仍为起点967cec；本阶段改动尚待正常提交/推送，最终完整SHA及推送差异在检查点回执给出。未读取Actions状态或创建PR/Release。

M2功能检查点完整SHA：`6fdd7c004bbbf380844efc49fb025a2cd1185f04`。`git push origin HEAD:refs/heads/codex/demo-v0.0.0`成功；之后`git ls-remote`核验开发分支等于该SHA，main仍为`5323f86232529efcfb52131168ad049f01b219f3`。功能提交后工作区干净；本段仅补充推送证据，不改变已测试代码。本次远端CI结果NOT VERIFIED，不自动轮询此前拒绝的API。
