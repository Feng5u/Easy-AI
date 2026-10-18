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

## M2 父级独审续修与M3只读环境计划

起点`9f7f8bb7aba6b71bc3cc1d74fdd13c1f5eae8523`。父级独审指出2项P2后，本轮先修复对应M2行为，未正式推进M3实现或训练。

定向RED命令：`uv run --project services/backend pytest -q services/backend/tests/test_compilation.py -k 'all_active_semantic or final_utf8'`，真实结果5 FAIL +1 PASS：默认示例缺body-0-axis/body-1-axis semantic span，4类超限ASCII/UTF-8逻辑名未拒绝。该RED未执行torch。

修复1：显式SHOW_TICKS=true生成实际`Axes.tick_params`语义行，并保留该axis来源；图像网格对应sample_ax同样显式执行。false仍关闭刻度。新增两份真实Blockly fixture全部活动语义块集合与semantic span集合比对（不限于golden逐字一致），另测试全部四个axis的true/false真实代码效果。更新golden代码与映射，IR语义未改。

修复2：编译器和独立Runtime统一为最终文件名保留最长受支持后缀`__<16位hash>__epoch-10000`的31个ASCII字节，PNG文件名主体最多220个UTF-8字节，每级目录组件最多255字节，原256字符逻辑路径上限继续保留。合理逻辑名完整保留，实际名仍加入hash/阶段；超限拒绝、没有截断或删除防覆盖后缀。原“folder/+237个x”放行测试改为跨多个合理目录组件的原256字符边界；危险单组件改为明确拒绝，并新增实际物理文件边界验证，未放松门限。Runtime还在创建目录/文件前检查真实目标的NAME_MAX与PATH_MAX预算（本Linux为255/4096），再执行既有路径/链接保护与原子不覆盖发布。epoch受合同1–10000约束。

GREEN：`uv run --project services/backend pytest -q services/backend/tests/test_compilation.py` **25 PASS**；ASCII和中文名称均实际原子落盘并读回最终255字节组件文件（包括epoch10000），超限在outputs目录创建前拒绝。独立只读worker重跑同命令25 PASS，确认两项P2关闭；父级最终审查仍待结论，不将worker复核视为父级审批。

受影响全量：`pnpm check` PASS；`pnpm test` **11 TS +92 Python PASS**（保留同一上游弃用警告）；`pnpm build` PASS。目录打包明确只复制两个helper源码文件，避免把本地__pycache__作为资源；此构建脚本修改后单独Prettier检查与重新build。实际生成的训练程序仍未导入或执行。

M3只读准备见[独立CPU训练环境安装计划](m3-training-environment-plan.md)。对应用3.11.17、已有裸3.11.17、默认3.12.14、系统3.13.5执行`-I -B -c`标准库spec/metadata探测，均无torch/torchvision；未找到健康训练解释器。只读核对官方CPU索引、官方TorchVision矩阵及PyPI元数据，候选Python3.11.17 +torch2.10.0+cpu +torchvision0.25.0+cpu +matplotlib3.10.8 +numpy2.4.2；这不是实测兼容通过。计划含索引声明的两个wheel SHA256、完整传递依赖带hash锁定方式与待执行命令、所需空间未知说明，以及32训练/16测试合成IDX的范围。没有下载wheel、生成完整训练依赖锁、创建训练venv、安装或训练；应用setup/锁文件没有混入训练依赖。M3标准库协议只列测试设计，没有新增实现。

准确阻塞/状态：读取`https://pytorch.org/get-started/previous-versions/`被网络代理以`Tunnel connection failed: 403 Forbidden`明确拒绝，未重试该目标或绕过拒绝；独立官方CPU索引及PyPI元数据读取成功。训练依赖实际安装仍为**待用户确认、未执行**，不是安装失败或未知执行结果。wheel可下载性、本地hash与实际CPU导入/训练、真实Matplotlib计算均NOT RUN；空间与完整传递依赖图未知。计划不是安装批准，后续须取得明确范围才执行。

门槛A/B仍未达到，M0桌面FAIL与此前远端desktop失败保持原结论；Actions API读取Forbidden不重试，无新CI结果声明。下一项为父级复核本轮M2修复及用户确认独立训练依赖安装范围；未授权前仅继续不依赖torch的设计/测试准备。

构建脚本调整后的`pnpm exec prettier --check scripts/python-task.mjs`与`pnpm build`均PASS；`services/backend/.venv/bin/python /tmp/easyai-m2-frozen-smoke.py`再次PASS（/tmp下真实冻结sidecar认证编译、golden一致、helper源码资源一致、EOF exit0）。本轮训练环境计划本身未执行安装命令。

## M3 后端协议小切片与已授权CPU真实执行

本阶段起点为`504cedf1d64fac573764324bb772cf8f4b37fe88`。父级先授权不依赖torch的协议切片，随后转发用户2026-10-18 09:02:11 UTC对既定CPU安装/合成IDX范围的批准（下载≤2GB、磁盘≤5GB、单次测试≤30分钟）。父级对504cedf两P2的最终复核为源码/冻结产物的有限关闭，不称父级独立重跑；该结论到达且真实依赖/算子探测通过后，才执行生成Bundle。此授权不扩展到GPU、付费、新SDK、学校环境、真实MNIST下载或SSH。

后端切片已实现：

- `ProjectService.snapshot`与save/close共享门，读取已保存原始字节并检查revision。RunService再校验runnable与ProgramHash，生成新UUID运行根、冻结快照/ProgramIR/代码/map与bundleHash，保存显式RunConfig；同Idempotency-Key同请求返回同runId，冲突请求拒绝；单客户端全局活动任务互斥。启动前重核快照、代码、辅助文件与配置，不从编译预览直接启动，不允许修改后快照悄悄执行。重启不自动重跑、不靠PID误杀。
- Supervisor启动选定训练Python中的真实entry.py，stdout/stderr并发排空，普通日志保持来源；严格识别最小事件负载，拒绝伪造runId/seq/process_exited、重复key、超限/截断/非法指标与重复终态。执行journal单写sourceSeq，应用journal单写seq并按sourceSeq去重；完整坏行failclosed，半尾行恢复信息明确，写入异常后要求关闭重开。约64KiB行上限和真实UTF-8边界已测。
- POSIX独立session/process group，取消文件原子不覆盖、宽限后TERM/KILL，确认退出且双管道排空后才写唯一process_exited；晚取消不改既有终态。只清理受管组，不杀无关进程；逃离组仍持管道时显式CLEANUP_PENDING，不假称已清理。Windows仅直接子进程路径，未实测进程树，不作跨平台保证。
- RunService成功需exit0＋完成事件＋连续完整epoch数/完成负载＋全部预期PNG/权重及真实size/hash；Supervisor的COMPLETED本身不等于训练SUCCEEDED。应用从事件重建CSV和artifacts.json。认证GET状态/POST取消/SSE重放已接入可显式配置的RunService；after seq、终态尾部补发、15秒心跳和断开退出独立于renderer。

这是内核服务切片：尚未把Main路径selection/data/env绑定与正式运行创建HTTP/IPC接齐；默认sidecar不会任意开放路径启动入口，没有生产mock Runner。尚未接renderer调试UI、退出确认和异常应用崩溃身份恢复。缺少持久退出证据的旧运行保持disconnected/身份未知并阻止冲突新运行，不自动归为失败/取消。M3.1–M3.4整体仍不勾选，M0和A/B门不改变。

独立模块与审查：EventJournal worker先交24 PASS，Supervisor worker交23 PASS（真实标准库fixture进程、大管道、协作/强制取消、孙进程清理与无关进程存活）。随后交叉只读审查：确认Journal基础行为；发现并实际复现RunService重启不补已有终态的P1、logs/metrics目录symlink外写P2，以及新只读runtime源FIFO阻塞P2；均已修。恢复定向先RED 1FAIL+1PASS，再GREEN；路径替换定向outside无写入；FIFO以O_NONBLOCK打开再fstat，并在有界独立子进程中实际验证拒绝。最后worker独立重跑Journal26 PASS、确认FIFO项关闭；前轮62项纯协议测试PASS。新增success epoch/完成负载防御门，不能仅靠产物集合宣称成功。

真实CPU安装/执行的完整来源、锁、预算、失败过程、指标与产物hash见[M3执行回执](m3-cpu-execution-evidence.md)。关键证据：

- 官方wheel实体240,772,699 bytes；含首次解析中断流量的保守计费上界508,745,232 bytes，低于2GB。解析器遇历史非法版本字符串后保留已核验wheel、跳过非PEP440版本；对之前未精确持久化的JSON流量保守预扣250MB，不冒称精确网络计量。锁通过离线uv完整解析、逐wheel SHA256与CPU来源审计；21项必要依赖无CUDA/新框架。
- 安装前保守磁盘峰值估计2,982,200,172 bytes；实际安装/测试自有目录有界监测，测试后逻辑字节1,986,724,165，低于5GB。最初uv把`--only-binary`和`--no-build`视为互斥导致参数错误、安装未执行；修为仅only-binary后离线安装成功，未退回源码构建。复用既有Python3.11.17，无应用/系统/教师环境安装。应用环境实际find_spec(torch)仍False。
- 真实CPU小张量反向、torchvision NMS、NumPy桥和Agg/Pillow解码PASS。integration-001揭示venv入口resolve成裸Python的问题，已保留选定venv绝对入口并新增真实venv回归；integration-002完成epoch与PNG后发现PyTorch拒绝dot前缀权重临时文件，已改atomic_target为非dot且保留suffix，原子/拒覆盖不变。首次修正误落JSON同名临时行，被回归拦住并撤回；integration-003保留失败，004与正式005真实通过。不覆盖旧运行。
- 正式005：runId `7b584e0b-e0ba-4a0e-9f23-f282cefd0e61`；32/16本地合成IDX、1epoch、batch8、download=False；真实loss 2.3290645480155945、合成test_accuracy0.125；8/8参数张量实际变化，三张PNG实际解码、state_dict实际weights_only加载、CSV/13规范事件/4产物、exit0均PASS。约15.55秒。这个数值没有MNIST效果含义。
- 正式命令：`EASYAI_TRAINING_PYTHON=/workspace/easy-ai-training-cpu/.venv/bin/python EASYAI_TRAINING_TEST_ROOT=/workspace/easy-ai-training-cpu/integration-005 UV_CACHE_DIR=/workspace/.uv-cache UV_PYTHON_INSTALL_DIR=/workspace/.python pnpm test:integration` → **1 PASS**。普通setup不安装训练依赖；新命令缺显式选定解释器/新测试目录时明确NOT RUN，普通测试中的该项为SKIP。
- 关闭重开实际005运行：SUCCEEDED、13连续事件和4产物恢复、重复读取不增点、未重新执行。保留失败002的冻结source-map把真实保存错误第217行准确定位训练根training，未借用新版代码行号。

最终受影响全量命令：`pnpm check` PASS，`pnpm test` **11 TS +156 Python PASS、1显式集成SKIP**（同一上游弃用警告保留），`pnpm build` PASS。标准开发缓存环境变量保持前述配置，无HOME/安全开关修改。新构建后`services/backend/.venv/bin/python /tmp/easyai-m2-frozen-smoke.py` PASS：冻结sidecar从/tmp认证编译、golden和helpers一致、EOF exit0。`git diff --check` PASS；计划原件仍116185bytes/hash dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43，原需求/README hash未变。

准确剩余状态：M0本地桌面启动FAIL（sandbox条件不足），既有远端desktop失败原因仍未知；Actions读取Forbidden未重试，无新远端CI成功声明。Windows训练/树清理、真实MNIST、SSH、学生UI完整闭环均NOT RUN；硬链接支持前提、未知进程身份保持保守。A未达到，B未达到。下一项先交父级复核本协议切片与真实执行回执，再补Main绑定/正式入口/调试UI，并取得可用桌面环境与失败CI日志；不把CPU单轮通过当作发布批准。

## M3 Main/UI接续前的持久化独审修复

起点完整SHA `60cc92e44377448739cf109bfaed708a2624ce96`。父级要求先处理两项只读独审发现，再接Main/UI。环境断连通知后仅进行一次实际命令核验：2026-10-18 09:26:46 UTC，pwd/HEAD/status与已落盘回归文件读取均成功；HEAD60cc，新增测试可读，无重复写入者/挂起命令。此为命令实际返回证据，不以inProgress状态当重连证据。

1. 取消持久化：worker以真实文件、在journal fsync后/catalog更新前注入OSError，确认catalog仍CREATED、完整日志已CANCELLED；重启错误回退CREATED。3项RED（另有FAILED/SUCCEEDED终态）。修复规则为应用journal的完整状态事件是事实、catalog为缓存；启动先折叠事件，终态禁止倒退/冲突。非终态保守单调，旧CREATED日志不降低已RUNNING缓存；即使cache为CREATED，已有执行证据而无退出记录仍保留RUNNING/disconnected，拒绝重启，不凭PID杀任务。没有为复现启动训练，start装失败哨兵。
2. 本地持久文件：四类FIFO（catalog、snapshot、config、bundle）各用独立标准库子进程、3秒timeout真实复现阻塞，RED4FAIL+1PASS，测试子进程由subprocess.run杀死回收。这是具有本机store写权限者替换文件的健壮性问题，不是远程未认证或普通Blockly输入漏洞。统一有界普通文件入口：O_NONBLOCK/O_NOFOLLOW→fstat REG→大小门；catalog16MiB、snapshot5MiB、bundle1MiB、config64KiB、生成源码/辅助文件8MiB。二进制产物hash改为流式有界读取，不读进整个应用内存。项目原先5MiB+1前缀读取语义保留并拒绝FIFO。

定向GREEN11 PASS；独立worker只读重跑11 PASS，确认上述两项与不降低未知运行状态。相关持久化/RunService回归通过；初版折叠曾将RUNNING降回CREATED，被既有回归发现后修正，未删除或降低测试。完整`pnpm check` PASS；`pnpm test`为11 TS+165 Python PASS、1显式训练SKIP；未运行额外真实训练、未安装新依赖。本阶段之后才继续冻结Main/API/renderer合同并分配独立模块。

本续修`pnpm build`亦PASS；尚未重跑真实训练，模型/数据/生成训练主体未变。M0与A/B状态保持。

持久化修复已正常提交并推送为 `db4ff73af93f852787f844bb9c30f0509eeadb57`；推送后开发远端等于该SHA，main仍为计划基线。

## M3 Main绑定、正式入口与基础调试UI

起点 `db4ff73af93f852787f844bb9c30f0509eeadb57`。先冻结Python权威DTO与Main/preload接口，再独立分工后端与renderer，单一集成者汇合。新增Main原生目录/解释器角色绑定、工程创建/打开/保存、正式RunService入口、SSE恢复、冻结源码/双路日志/登记PNG读取；renderer只通过受限桥接调用，没有token/端口/HTTP或任意路径入口。项目创建保留既有data，训练仍download=False，应用环境find_spec(torch)仍None。详细实现、真实命令、失败及边界见[m3-main-workflow-evidence.md](m3-main-workflow-evidence.md)。

独立审查发现并修复两个可复现P2：SSE error与abort同时发生的孤立Promise拒绝；import probe leader先退出却遗留持pipe孙进程和drain线程。后者先RED，修复后独立9 PASS确认专用组及线程清理；Electron相关独立11 PASS。另补renderer崩溃/销毁清订阅和EOF停止有界失败，未强杀清理owner。Windows分支仍未验证。

实际 `pnpm check` PASS；`pnpm test` **27 TS PASS / 2显式CPU SKIP，186 Python PASS / 1显式CPU SKIP**；`pnpm build` PASS。新增可重复 `node scripts/test-frozen.mjs` PASS：真实冻结sidecar从临时cwd认证选择/创建/编译，golden、模板/helpers逐字一致、EOF exit0。不是Electron窗口验收。旧冻结smoke也PASS。

复用用户已授权的CPU环境、既有32/16合成IDX和1epoch/batch8工程，未新增下载/安装。MainWorkflow跨真实认证sidecar运行：`81d607f1-aef0-423b-9904-21fc8731639b` SUCCEEDED，13连续事件、exit0、真实loss2.3290645480155945/合成accuracy0.125、3PNG内容hash一致、源码/map与冻结编译一致、重复key同runId、数据hash未变，测试17.76秒PASS。原生picker回调是测试注入，不声称真实对话框已运行。

正式取消测试首次在本执行器不可见的`/proc/<pid>/task/<pid>/children`检查处FAIL；finally实际取消、日志保留。未猜PID或提权。后续测试不再依赖不可用外部/proc，生产取消门和原有真实进程树测试不变；`f66c2068-56b5-4b47-b343-0a4009235bb6`真实runtime_started后显式取消、唯一process_exited、CANCELLED、空活动列表、EOF exit0及新sidecar恢复均PASS（18.40秒）。这次Main集成没有外部训练PID观察证据，亦无完成epoch声明。新增运行后训练目录约1.99GB，既有保守累计下载约509MB，各测试远低于30分钟；数据/权重/绑定保存在仓库外。

M0桌面仍FAIL、远端desktop失败原因未知且Actions Forbidden未重试；新Electron窗口/原生对话框/实际点击关闭行为、真实教师MNIST人工运行、Windows树清理均NOT RUN。M4三workspace/Monaco/自动保存与历史、M5–M8仍未交付。A未达到、B未达到。下一项为父级复核本检查点，并提供安全沙箱桌面执行环境、实际失败CI日志及准备好的真实MNIST数据路径后闭合M0/M3；默认不下载，不改main，不建PR/Release或部署。

本轮功能/测试/证据完整SHA：`60914354dad0ccffa0e22749163ec680858dfdd3`。`git push origin HEAD:refs/heads/codex/demo-v0.0.0`成功，`git ls-remote`实际核验开发远端等于该SHA，main仍为`5323f86232529efcfb52131168ad049f01b219f3`；功能提交后工作区干净。本段后续仅补充此推送回执，不改变已测试代码。最终训练目录逻辑字节`1988485353`（<5GB）。计划116185字节、SHA256及原需求/README hash均保持；本轮无新远端CI结果声明。

## M4 编辑闭环实现检查点（桌面验收未完成）

起点 `e13ce3f05d8685507c5b23365410c5ad4e0f831b`。父级对前两项持久化P2及Main/SSE/probe作源码/回归设计的有限关闭，明确未独立执行该检查点的27TS/186Python/CPU测试，相关结果仍为作者执行证据；随后授权在M0沙箱阻塞下继续不依赖桌面启动的M4实际功能。项目定位为**华为 ICT 参赛 demo**。本轮先核对缺项、冻结ProjectEditor与Main接口，再独立分工积木编辑器和Monaco，单一集成者负责App/后端与提交；没有重做既有编译器。

- M4.1 实现：真实Blockly三常驻workspace与分区toolbox覆盖原21类；切页resize、ResizeObserver/监听器/dispose；语义/坐标保存与选择事件分开，导入批次不触发自动覆盖。注册、改名、注销、删除/Undo、复制新ID默认未注册与Undo分组；同placement next连接约束、字段长度限制。开始加载前扫描格式/ID/500块/64层，再用真实headless loader试载；未知/不能无损载入的数据不进入可编辑模式。浏览器ESM与Node CJS的不同导出实际构建发现后修复，原fixtures --check仍逐字通过。
- M4.2 实现：FieldSymbolRef只保存稳定ID，按三个workspace动态重建显示索引；注册/名称/删除/Undo刷新；loader角色由dataset引用/SPLIT推导，训练字段不列测试loader；失效引用保留原ID并警告。CE可选，MSE/BCE目录保留禁用说明且UI选择回调拒绝，遗留序列化值仍留给Python诊断，不转换任务。
- M4.3 实现：固定应用依赖`monaco-editor@0.57.0`，可见时才从本地lazy assets加载，只读Python、多个离散span高亮、semantic优先且最窄来源点击、脚手架低亮；旧RunSource/map复制冻结。卸载释放model/editor/mouse/observer，最后model移除由Monaco自身WorkerManager关闭owned worker。worker/字体/CSS全部本地资源，没有CDN或eval。
- M4.4 实现：800ms防抖与手动保存；单次在途保存响应不能覆盖期间的新编辑，后续用新revision继续保存；冲突保留草稿、暂停自动保存，允许导出未保存稿。Main仅用原生对话框选择导入源/目标与导出路径，renderer不提交路径；新建空白/示例工程、导入保留block ID而创建新projectId、不覆盖已有目标或data。上次项目目录保存在应用私有状态中，重启读回三个workspace/UI；不持久化本次Python/data选择ID。历史分页按projectId恢复，旧运行的源码/产物与当前编辑分开。有效只读工程能改变本地查看tab/代码显隐，不标脏、不写原件。关闭时有未保存内容确认；backend退出不再通过reload丢弃活草稿。

安全样式适配：Main每次index响应产生独立32字节style nonce，CSP仅将该nonce用于样式；script-src self、connect-src none、四项Electron隔离及sender主frame检查保持。构建仅适配固定哈希Blockly两处和Monaco一处style创建点，hash/数量/必要模块缺失均拒绝构建；无全局document猴补、unsafe-inline或unsafe-eval。Monaco明确不使用shadowDOM/contextmenu/hover，未对全库任意配置作CSP保证。Blockly媒体也以固定self assets提供，未开放任意路径。真实浏览器CSS/worker呈现仍NOT RUN。

独立审查及实际修复：

1. 独立复现超限只读文件的内存前缀被误当完整原件导出（6,291,490→5,242,881字节）。现>5MiB只读导出在创建目标前明确拒绝，预览最多64KiB，源文件始终保留；真实6MiB回归确认目标不存在且原件逐字不变，独立6 PASS。没有扩大大小上限或补造缺失内容。
2. 独立源码发现只读tab被edit写入保护一起拦住，修为独立本地viewTab/viewCode，再仅在可写时保存UI意图。独立新增真实React DOM回归3 PASS：只读切页不dirty/save；799ms不保存/800ms开始；pending期间新层不丢并以新revision再保存；冲突保持草稿、暂停重试且导出当前稿。画布由组件stub隔离，未假称JSDOM拖拽或production Runner。
3. 另一只读审查者对Monaco生命周期/映射/nonce重跑8 PASS，确认冻结旧map、资源清理和样式专用适配。积木/引用/manager真实headless及工厂生命周期13 PASS；这不是canvas DOM实际拖拽。父级新检查点复核待结论，不将worker重跑写成父级执行。

实际完整命令（沿用前述workspace缓存变量）：

| 命令 | 结果与范围 |
| --- | --- |
| `pnpm check` | PASS；严格TS/mypy、ruff/格式、Python权威合同漂移、原真实Blockly fixture漂移均通过 |
| `pnpm test` | **55 TS PASS / 2显式CPU SKIP；192 Python PASS / 1显式CPU SKIP**，同一上游弃用警告未隐藏 |
| `pnpm build` | PASS；真实Vite/Electron TS/PyInstaller；保留>500kB lazy chunk警告，未抬高门限。初始入口约250kB，Blockly lazy约661kB、Monaco lazy约2.70MB，性能门尚未桌面实测 |
| `node scripts/test-frozen.mjs` | PASS；临时cwd真实冻结sidecar认证示例编译/golden、空白创建、原字节导出、模板/helpers资源一致与EOF exit0 |
| `pnpm exec vitest run packages/block-library/workspace-manager.test.mts packages/block-library/symbols.test.mts apps/desktop/electron/editor-workflow.integration.test.mts apps/desktop/electron/workflow.test.mts` | 18 PASS；从空白起用真实Blockly API创建数据/模型/训练、稳定ID选择、Main→真实sidecar保存/Python编译；再新增Linear层，代码与来源map真实改变；导入/导出不覆盖，未训练 |
| 应用环境`-I -B -c`标准库`find_spec('torch')` | None；应用仍不含torch |

首次普通`pnpm add`因默认home目录不存在而未安装；设置已有XDG目录后固定Monaco安装成功，无HOME/系统权限修改。没有新增训练安装、真实数据下载或CPU训练，也没有SSH。训练目录仍`1988485353`字节；机器配置、数据、权重、用户工程均未提交。原计划116185字节/SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`，README/原需求hash保持。

剩余与下一项：M4实际Electron canvas/Monaco呈现、从空白人工拖拽到训练、原生导入导出/关闭对话框与跨平台行为均NOT RUN；本轮未重跑原已知沙箱失败，也未降低沙箱。M0桌面FAIL、远端desktop失败原因未知、Actions API Forbidden未重试。真实教师MNIST人工小样本、训练PID外部观察、Windows树清理仍缺证据；A/B均未通过。下一项先由父级复核此实现，并在支持安全沙箱的桌面环境执行M4阶段`pnpm test:e2e`及人工闭环。M5实际SSH仍需目标/凭据/已有数据授权，M6受控安装与M7/M8未完成；编译/协议可继续独立推进，不以本次组件通过宣称完整demo完成。

M4功能完整SHA：`78bda2a537353ff70f1fd710f8704b1971d6ca6d`，包含上述已测代码与回归；本段及本轮阶段进度独立文档提交，不改变测试对象。提交前在线开发远端仍为起点`e13ce3f05d8685507c5b23365410c5ad4e0f831b`，main仍为计划基线；两个本地提交将仅一次正常推送开发分支，最终远端完整SHA、工作区与main差异在最终回执核验。不读取Actions，不建PR/Release或部署。

## M4 clean-export 续修与 M5.1 身份门检查点（M5 未验收）

本轮起点完整 SHA `2040a05c7235472d329f9c05e003b144c04c4b3e`，工作区原先干净；checkout仍为`/workspace/Easy-AI`、`codex/demo-v0.0.0`，origin仍为T1doo/Easy-AI，main仍`5323f86232529efcfb52131168ad049f01b219f3`。父级允许在桌面阻塞下继续离线M5独立开发；明确本轮不重复M4测试、不安装/训练/配置凭据/连接SSH。父级随后要求优先修复clean export；仅新增并运行该缺陷单项，未重跑M4套件。

M4修复完整 SHA `459b088c85b82a52e914c984b5366c639f4a8688`：原App无论dirty都提交ProjectDocument，导致干净工程被重新序列化而提示导出原件。现在只有dirty才提交草稿；clean调用无参数，由Main→真实sidecar读取源字节。新增真实React→Main→sidecar定向回归，原件特意调整根字段顺序、tab缩进及双换行；导出与原件逐字一致、源文件不变。作者单项1 PASS/3 SKIP，独立审查者同项1 PASS/3 SKIP，限定范围关闭P2。首次测试fixture相对路径错误FAIL，改正仓库内路径后通过；没有削弱断言。

M5功能完整 SHA `b18062197fde48c1a4936fe3e6b6b318abf33fac`。本次仅交付M5.1后端身份门及公开DTO基础，**不等于M5.1完整交付或M5验收**：

- Python权威SshEndpoint规范化host/port，HostKeyObservation/Confirmation生成JSON Schema、TS、声明镜像。凭据不属于DTO；认证probe仅做握手取公钥，显式确认绑定已观测host/port/algorithm/public bytes与10分钟内挑战，SHA256指纹，最多32未确认/512信任记录，超限/过期拒绝。已知密钥变化直接阻断，没有覆盖/轮换接口、AutoAddPolicy、用户SSH配置或agent读取。
- 单跳Paramiko Transport核心：probe始终关闭；验证当前连接公钥后才允许调用显式密码/私钥对象认证，认证前再次读信任记录并核对公钥，密码fallback=False。关闭/异常/取消/握手与认证deadline清理当前拥有的transport/socket；SDK异常只返回通用代码。密码或私钥不落盘；没有加载真实私钥或调用真实认证。Paramiko4.0.0从M0已锁定安装，本轮没有新增依赖。
- 已认证sidecar API新增`POST /api/v1/connections/probe`及`/connections/trust-host-key`，只处理endpoint/短期挑战，不接受认证材料。SSH校验异常单独脱敏，误带额外password字段也不回显输入，其他路由继续委托原FastAPI校验handler。当前不是计划完整连接profile API；无连接UI/Main桥接、密码/私钥选择、conda探测、SFTP/远端监督/重连/取消/同步实现声明。
- 信任记录存于应用私有子目录中的OpenSSH公钥行，不修改用户`~/.ssh`。独立审查发现初稿只保护最终文件：初始化后将信任目录替换为symlink可重定向确认写入（P1，离线复现）。修为校验父链及初始化inode，POSIX每操作打开目录FD并用flock跨实例互斥，读/临时文件/replace/unlink全部dir_fd锚定，普通文件/大小限制仍在。新增初始化后、发布前目录替换回归；独立18 PASS关闭，另在最终replace入口注入更晚替换，outside无写入，操作最终拒绝。该更晚窗口最多发布至原锚定目录，不会写到外部symlink目标。**非POSIX信任存储显式SSH_TRUST_PLATFORM_UNVERIFIED；Windows行为尚未实现等价句柄保护，不宣称Windows M5可用。**

实际命令与结果（沿用既有UV/XDG workspace缓存变量，未更改HOME）：

| 命令 | 实际结果 |
| --- | --- |
| `pnpm exec vitest run apps/desktop/src/App.test.mts -t 'exports clean'` | 1 PASS / 3 SKIP；作者及独立审查者各执行一次，限新增缺陷单项 |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_ssh_identity.py` | 最终20 PASS；socket.create_connection装失败哨兵，合成PUBLIC wire bytes，无私钥生成/真实SSH；覆盖未知/变化/认证前复核、并发确认、过期/上限、FIFO/symlink/根替换、取消、握手/认证超时、错误脱敏与API鉴权。上游Starlette弃用warning保留 |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_contracts.py` | 29 PASS；合同相关定向回归 |
| `pnpm contracts`、`pnpm check` | PASS；新合同生成/漂移、TS/mypy、ruff/格式、原Blockly fixtures。首次check发现新增测试unused Path import FAIL，移除后最终通过 |
| `node scripts/python-task.mjs build` | PASS；仅重建PyInstaller sidecar，不重跑桌面/M4 build测试；脱敏修改后重建一次 |
| `node scripts/test-frozen-ssh.mjs` | PASS；真实冻结sidecar从临时cwd启动，401鉴权、422非法host/额外字段不回显、lazy Paramiko打包导入、过期确认拒绝、stdin EOF exit0。只调用本机sidecar HTTP，没有向SSH端点拨号 |

初稿上限测试曾FAIL（把尚未过期的1个挑战加32误当32总数），修正测试时钟使旧挑战到期，生产32上限未降低。目录P1修复独立复核18项；后加两项timeout/key-object使作者最终20项，未把20写成独立执行结果。整体`pnpm test`及M4/Electron套件本轮NOT RUN，遵照父级避免重复；没有本轮完整套件通过声明。

CI精确边界：父级新增独立邮件证据，M4 HEAD `2040a05c7235472d329f9c05e003b144c04c4b3e` 的CI run `39118961613`于2026-10-18 10:23:09 UTC报告desktop failed、check succeeded。只有job级结果，失败步骤/根因未知，不能归因为本地sandbox。仅静态对照既有workflow及startup.spec.ts，未发现足以确认根因的明显不一致；Actions既有Forbidden未重试、未换通道，没有远端全通过声明。

原件仍116185字节，SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原需求hash `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README hash `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`保持。未新增训练、下载、数据/机器配置/私密材料，未改老师环境或main，未建PR/Release/部署。

下一项：继续不依赖SSH凭据的连接profile/UI合同与现有课程环境只读探测协议，随后M5.2–M5.4；实际网络验证前最小条件为明确SSH目标host/port、预先独立核验的SHA256主机指纹、用户允许的认证方式与短期凭据输入方式、只读课程Python/数据路径、允许上传/运行的专用远端目录及显式范围授权。本轮这些真实动作未执行，属于待授权条件而非工具拒绝。TCP连接10秒、握手10秒、认证15秒有界；系统DNS解析遵循OS resolver，未实现/承诺硬DNS截止。CIFAR10本地数据preflight缺口仍真实存在（编译支持不等于运行支持），留待M6.1补齐；不改D10或假称全21能力已验收。M0/M4真实桌面、教师MNIST、Windows进程清理、完整M5–M8仍未验收，A/B均未通过。推送前开发远端仍为本轮起点；本轮提交仅正常推送开发分支，最终远端与干净工作区以回执为准。

最终增补独立复核：另一审查者只读核对SSH validation分支与冻结smoke，实际定向`test_authenticated_probe_api_accepts_no_credentials_and_confirmation_is_bound_to_probe`为1 PASS/19 deselected，确认password字段名和输入标记均不回显；其未运行冻结smoke，冻结结果仍仅作者执行证据。此增补仅进度文档，不改变功能测试对象。

## M5.1 主机身份正常 UI 与作用域协议续接（认证/远端执行未验收）

本轮起点 `c6d29e437cae5cfda7b60a8a1d71e29d4efedc9d`，同一`/workspace/Easy-AI`、单写入者、工作区原先干净。父级授权本轮继续连接目标/首次指纹确认/密钥变化拒绝的正常UI与有界协议；仅代码及内存/本地合成测试，不真实SSH、不使用或生成真实私钥/密码、不保存真实连接凭据、不安装/下载/扩大网络权限。起点远端开发分支等于c6d29e4，main仍为基线。功能完整 SHA **`48ae79c33b84cc8b34843e94cc64f5961dda996a`**。

先处理父级静态发现的权限P2，再继续UI。原HostKeyStore mkdir默认模式受umask影响，root/known_hosts只验类型与大小，未验owner与group/other写权限；不安全的已有目录可允许其他用户换普通文件而不触发inode/symlink门。没有真实跨用户攻击复现，也不声称默认安全机器已受利用。本次产品代码：缺失目录每级用已验证父目录FD创建0700，临时/正式文件0600；信任root要求当前euid且无022，信任文件同样要求当前euid/无022，持有文件FD读前后检查并与发布路径inode对照。逐级O_NOFOLLOW打开并保留祖先FD，检查owner/mode，操作结束再复核FD权限；祖先仅信当前用户、uid0或内核文件系统根的owner（本容器根映射为65534），无022；可信owner的sticky临时目录作为祖先允许，trust root本身不允许共享。已有不安全目录/文件一律拒绝，**不chmod/chown自动修复**。仅任务临时夹具中调整mode/umask；错owner使用fstat元数据模拟，未chown任何真实对象。独立审查28 PASS关闭本POSIX权限边界；最终增加umask002参数例，作者覆盖000/002。非POSIX仍明确failclosed，不虚报Windows支持。

UI与合同：正常App的“SSH 主机身份设置”打开ConnectionPanel，当前工程会话内填写host/port；只做预认证主机检查，明确不登录、不上传、不运行，没有用户名/密码/私钥输入或保存路径。unknown展示实际规范目标、算法、完整SHA256指纹，必须勾选独立渠道核对再确认；changed展示原指纹并拒绝，无覆盖按钮；trusted仅表示公钥匹配，明确尚未认证或检查远端环境。目标不写便携工程或localStorage，切工程按projectId重建，离页/后端未就绪时卸载。重新检查使用新requestId，不自动拨号重试。

Main/preload只增加三个固定身份IPC（probe/confirm/cancel），仍由原mainFrame/sender/origin门注册，不暴露HTTP、token、端口、路径或通用调用；原四项Electron隔离、CSP、安全资产协议保持。Main校验字段/UUID/host/port并保存当前请求，规范化DNS大小写/尾点/IDNA与IPv6/IPv4后把同一目标交Python；确认只使用Main记录的challenge和当前显示的指纹。每次响应前后复核当前projectId及backend实例；切项目、dispose、取消或新目标使旧操作失效，迟到resolve/reject不能用于确认。正常run订阅清理与整个workflow dispose分开，避免订阅本地日志误取消身份检查；既有单订阅取消回归定向通过。e2e的桥键精确预期同步增加connections，未删除隔离断言，未运行e2e。

Python权威新增IdentityRequest/ProbeRequest/ConfirmRequest/Result及生成Schema/TS镜像；`/connections/identity/{probe,cancel,confirm}`有项目/请求/目标绑定。SshIdentityService共享LocalWorkspace锁，切工程或关闭时失效；最多一个物理在途probe，取消后仍在退出则拒绝并发新probe；每请求ID最多开始一次，64项/600秒retired表，超限拒绝、不无限增长，取消先于注册也留下墓碑。完成结果仅在仍为当前项目/操作且未取消时可用，旧挑战丢弃。公开确认与切工程在同一锁中排序，不能给取消后的旧结果新授信；已完成的显式信任不会因稍后取消被自动撤销。UI25秒等待门主动失效并发取消，Main HTTP仍为原30秒门；不把RPC取消回执当作OS DNS已结束，DNS硬截止仍缺。后端异常取消清理通过线程池执行，避免在API事件循环同步争锁。原预认证内部API保留，但renderer桥仅访问新作用域接口。

独审过程中新增并关闭目标绑定P2：初稿Main只核project/request，fake Backend返回另一host/port仍可被接受；真实SshClient当前固定请求目标，因此这是离线协议防错复现，非已证实网络攻击。Main现保存并比对规范目标；backend接收observation立即比对并清理错目标挑战，confirm持久化前再次比对。独立9 Main /34 Python PASS，错host/port不能确认且无信任落盘，IDNA/IPv6/IPv4正例通过。另一审查者对组件生命周期及新App正常入口独立5+1 PASS，未启动Electron/SSH；没有把组件mock说成生产Runner或真实网络握手。

实际定向命令与结果（UV/XDG缓存变量沿用，不改HOME）：

| 命令 | 实际结果与边界 |
| --- | --- |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_ssh_identity.py` | 最终 **35 PASS**，保留Starlette弃用warning；含权限、原身份门、单在途/取消先到/迟到/跨目标跨工程/错误目标不落盘/API确认。socket.create_connection有失败哨兵；只有合成PUBLIC bytes，没有私钥/真实认证。独立执行先28后34，最终新增umask002一例为作者结果 |
| `pnpm exec vitest run apps/desktop/src/ConnectionPanel.test.mts apps/desktop/electron/identity-workflow.test.mts` | **14 PASS**（5 React DOM +9 Main）；组件API及Main Backend使用明确测试替身，不等于整体真实Electron→SSH链。独立分别5与9 PASS |
| `pnpm exec vitest run apps/desktop/src/App.test.mts -t 'normal SSH identity'` | **1 PASS /4 SKIP**，作者与独立审查者各一次；真实React入口→打开身份面板→检查→关闭取消，画布仍测试stub。没有重跑旧M4项 |
| `pnpm exec vitest run apps/desktop/electron/workflow.test.mts -t 'one active subscription'` | **1 PASS /3 SKIP**；因本轮清理拆分补相关既有M3回归 |
| `pnpm contracts`、`pnpm check` | PASS；生成合同/漂移、TS、mypy29源文件、ruff/格式、原真实Blockly fixture均通过；新增测试最后参数化后单独ruff check/format --check亦PASS |
| `pnpm build` | PASS；新Main/renderer Vite构建与PyInstaller完成；保留原lazy chunk大小warning，不调高门限 |
| `node scripts/test-frozen-ssh.mjs` | PASS；真实冻结sidecar临时cwd，本机HTTP鉴权/严格DTO/脱敏/Paramiko导入/新scope取消与无当前工程确认拒绝/EOF exit0；未调用有效SSH probe，没有出站SSH |

初次权限续修把symlink根改为逐级O_NOFOLLOW时，旧回归因错误类型从ValueError变为NotADirectoryError而FAIL；保持拒绝条件并统一SSH_TRUST_PATH_INVALID后GREEN，不降低测试。过程中未有真实连接、凭据配置、训练/安装/数据下载。整体`pnpm test`、旧M4套件、`pnpm test:e2e`均本轮NOT RUN，遵照父级定向验证；真实Electron/Windows/远端行为未验。M4 CI run39118961613在2040a05 HEAD的desktop failed/check succeeded边界保持，失败根因未知；未重试Actions Forbidden或换通道。

原计划仍116185字节，SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原v0.0.0 hash `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README hash `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`均实际复核未变。没有更改依赖/lock、网络权限、系统或既有真实目录安全权限，私密材料/运行数据未入库。推送前远端仍为c6d29e4；仅正常推开发分支，最终完整HEAD/远端相等与干净工作区在最终回执核验，main保持基线。

下一独立功能为M5.2现有课程环境只读发现/probe的合同与离线验证，及M5.1真正用户认证/连接profile的后续接入；本轮尚没有完整连接profile持久化、认证UI、conda/SFTP/远端监督/断线续读或远端取消，不宣称M5验收完成。真实SSH仍待明确目标/独立指纹/允许认证方式及执行范围授权；此类动作本轮未请求执行，非工具拒绝。Windows安全信任存储仍拒绝，DNS硬截止未实现；M0/M4实际桌面、真实MNIST与M5–M8剩余项仍缺证据，A/B均未通过。

## M5.2 只读环境发现与固定探测核心（真实认证/远端未验）

起点完整 SHA `40e25c7fbfcd160ce33f8a62dcf6f2c2e9c8876a`，同一checkout、单写入者、起点工作区干净。父级明确授权本轮M5.2合同和合成transport/protocol验证，禁止真实SSH、用户凭据、远端脚本部署、安装/下载/训练；本轮按此范围执行。功能完整 SHA **`df4eac390fd473dbb110b3e2b30a86cc78325581`**，不是M5完整验收。

已实现Python权威EnvironmentScope/Request/Discovery/Probe/Catalog/Report/Result及9个生成Schema/TS镜像。范围绑定projectId、connectionId、endpoint及已验证主机指纹，环境descriptor是会话内后端生成ID、默认只读，发现不等于可用；目录600秒过期、重新发现废弃旧ID。有限非交互PATH/miniconda3/anaconda3/opt位置探测，或明确conda绝对位置；只读取`conda info --json`、`conda env list --json`，最多4个候选/64个环境，未知元数据字段不传到命令。无conda时返回空未探测目录，也支持明确Python入口，不自动安装conda。conda选择使用`run -p <prefix> --no-capture-output python -I -B -c <固定源码>`，不使用activate或自由shell字段。所有动态远端路径独立POSIX引用；Windows本地conda适配不在此Linux SSH核心中，未声称可用。

`runtime/probe.py`为标准库启动的固定源码，配置仅有nonce/device/可选Dataset绑定的有界JSON stdin；没有项目可编辑Python或远端probe.py上传。它在选中Python中逐个真实import torch/torchvision/matplotlib并读版本，实际查询CUDA/MPS可用性，no_grad中执行一个极小卷积，不训练。可选MNIST/FashionMNIST/CIFAR10只读test split、ToTensor和一个样本，始终download=False；返回真实shape/dtype/label或明确失败。缺torch时设备状态是unknown（None），不伪造“没有GPU”。MPL/XDG/TORCH/PyTorch kernel/CUDA缓存指向进程临时目录，-B及dont_write_bytecode阻止包字节码写入；不安装、升级、下载或写教师数据。临时缓存隔离只获合成验证，真实依赖及远端临时文件清理尚未验，未声称零文件副作用或远端退出已确认。

报告默认严格拒绝：stdout64KiB/stderr32KiB，UTF-8/完整JSON、重复key/NaN/噪声/未知报告字段/不一致状态拒绝；nonce、device、数据集名称/远端根、conda sys.prefix及明确Python sys.executable逐一绑定。包装器/别名报告不同解释器时不默许，需选择可核对的实际入口。报告列出各项失败和固定修复建议；就绪是此处能力检查结果，不等于已训练或发布许可。当前兼容基线仍是已验证Python3.11；其他Python可报告但不宣称兼容就绪，不自动修改教师环境。无Dataset请求时dataReady=None，不能当作训练数据已通过。三种Dataset的合成payload测试只证明调用download=False和结构协议，**不补足CIFAR10本地RunService预检缺口或真实数据验收**。

EnvironmentService最多一个在途操作；64项/600秒retired请求表，取消先到也留下墓碑；工程/连接/目标切换、取消、失效scope和迟到回执不可发布目录/报告，错误后关闭专用探测会话并清空目录。逻辑操作预算20秒，每条命令预留适配器3秒setup/drain及2秒join，剩余不足不执行；执行后再核scope/截止时间。SshProbeTransport仅消费已认证且仍匹配已知公钥的专用VerifiedSshSession，每次开channel前重新验active/authenticated/key/pin，不与训练会话共享。双路管道交错有界读取，分段stdin，必须接收EOF、读完双流并拿到有效退出状态才成功；ACK阻塞受watchdog控制，失败关闭专用连接，worker未确认回收明确CLEANUP_UNCONFIRMED并阻止复用。底层session.close本身仍依赖SDK/OS能返回；逻辑预算不是未验证的跨系统绝对实时承诺。

远端固定命令还要求`/usr/bin/timeout --signal=TERM --kill-after=2s`及`/usr/bin/env`，不提供无超时兜底；真实目标是否具备这些工具NOT RUN，不自动安装。关闭channel只表示本地连接关闭，不代表远端进程已退出；本轮没有远端PID/退出或超时工具实测证据。官方Paramiko文档和本机已锁4.0.0源码核对了exec ACK等待/双流/退出状态行为，conda官方文档核对-p与no-capture-output；没有据latest文档升级任何依赖。

关键依赖边界：**本轮没有注册环境执行公开API或UI环境列表**。M5.1正常身份UI目前只有预认证握手且会关闭连接，真实认证session manager/凭据生命周期尚未接入；新核心必须由将来认证管理器提供不可选的scope guard和已认证会话，不能用“已确认指纹”冒充“已登录”来开放执行。核心模块及固定probe资源已纳入冻结包，未放生产mock、假日志或预制硬件报告。下一项先补真实会话管理的代码/离线合同，再安全接入本核心及M5.3，不让未认证renderer获得通用命令能力。

独立审查发现并修复：明确Python初稿未核对报告executable，合成另一解释器仍可被标ready（P2）；初稿closed无received EOF可被当作成功；20秒预算未计传输额外等待，合成时钟到23秒才拒绝；CUDA_CACHE_PATH初稿遗漏。现分别精确绑定入口、无EOF拒绝/EOF先于status继续等待、预留5秒及不足不发命令、增加CUDA临时缓存。服务审查者只读重跑28 PASS，通道/脚本审查者21 PASS，关闭本轮缺口；所有复现是合成协议或源码检查，没有实际SSH/torch/硬件或跨用户攻击声明。

实际命令（沿用既有UV/XDG缓存变量，不改HOME）：

| 命令 | 结果与范围 |
| --- | --- |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_environment_service.py services/backend/tests/test_environment_transport.py services/backend/tests/test_environment_probe_payload.py services/backend/tests/test_ssh_identity.py` | **85 PASS**，28服务+13传输+8固定payload+36相关身份回归；2.80秒，保留Starlette弃用warning。合成版本均标synthetic，训练包真实import及网络拨号装失败哨兵；无真实torch/SSH |
| `pnpm contracts`、`pnpm check` | PASS；生成合同/漂移、TS/mypy32源文件、ruff/格式、原Blockly fixtures。首次check因runtime用错格式配置FAIL，改用既有backend pyproject配置格式化后最终通过，未修改门限 |
| `node scripts/python-task.mjs build` | PASS；仅PyInstaller backend构建，环境核心显式hidden-import、固定probe data resource加入；无依赖/lock变化，不重复旧桌面套件 |
| `node scripts/test-frozen-ssh.mjs` | PASS；固定probe资源逐字对照，已有M5本机sidecar鉴权/DTO/取消/拒绝确认及EOF exit0；没有调用有效SSH probe或执行环境payload |
| PyInstaller `ZlibArchiveReader`检查`build/easyai-sidecar/PYZ-00.pyz` | PASS：environment_service/environment_transport/domain.environment均在包内；冻结probe.py与源字节一致，未执行探测 |
| 应用Python `-I -B -c`仅`find_spec('torch')` | None；应用环境仍不含torch，未import训练包 |

没有执行整体pnpm test、旧M4测试、Electron或Windows/真实远端探测；也没有CPU训练、数据/包下载、用户凭据使用、SFTP或远端脚本部署。原计划116185字节、SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`，原v0.0.0 hash `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`及README hash `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`均实际核对未变。公开仓库没有真实目标配置、凭据、数据或硬件报告。

推送前开发远端仍为本轮起点40e25c7，main仍`5323f86232529efcfb52131168ad049f01b219f3`；仅普通开发分支推送，最终完整HEAD、远端一致与工作区在最终回执核验。M4 CI run39118961613在2040a05 HEAD的desktop failed/check succeeded边界保持；本轮远端CI未知，不重试Actions Forbidden或换通道。真实Electron/Windows/SSH、M5–M8剩余、M0/M4桌面及真实MNIST仍缺证据；A/B均未通过。本轮真实远端动作未请求执行，属于原授权范围外的NOT RUN，不是工具拒绝或结果不明。

## M5.1 认证会话与 M5.2 正常环境入口接线（离线阶段，2026-10-18）

起点完整 SHA `9bb92c533f3adcbce76ac8f6879945b696924e1a`，同一 Easy-AI checkout / `codex/demo-v0.0.0` / T1doo origin，起点工作区干净；单一集成者写入，两位既有审查者只读。功能完整 SHA **`7dfaed4beeee1fd2b024fa36ea71cd94936a2c61`**。父级本轮只授权最小认证会话管理器、正常环境入口及离线合成验证；设计先由后端/界面审查者接受，再实现。没有真实 SSH、用户密码/私钥、远端部署、环境安装、数据下载或训练。

Python ConnectionManager 只在工程内当前 trusted identity 的一次性、固定十分钟授权门通过后开始认证。新握手的实际 endpoint/fingerprint 必须与 grant 一致，密码发送前再次核 pin；信任指纹不等于已认证。密码认证成功、当前工程/代次/请求仍有效才签发后端生成 connectionId，认证 lease 固定最长 300 秒，查询/探测不续期；认证尝试 25 秒逻辑门。认证取消前到、目标/工程切换、超时及迟到成功均不发布 lease。旧 auth/connection/request/TTL 回调只作用于自身身份，不能关闭新 lease。SDK connect/auth/close 在共享 workspace 锁外执行；退役 owner 持有会话直至 SDK close 和环境 worker 都确认为 quiescent，未退出时继续 BUSY。底层 DNS/SDK 退出仍受 OS/SDK 行为限制，不承诺硬 DNS 截止或关闭即代表远端进程退出。

密码不进入 operation、公共响应、生成合同、日志或磁盘；内部输入采用 SecretStr、exclude/repr=False，专用 Paramiko 日志在握手前禁用且 hexdump=False。成功/失败/取消后清除已锁 Paramiko 4.0 AuthHandler.password/private_key 和 saved_exception 的引用，保留 authenticated/auth_event；清理失败拒绝成功且 close 不标 quiescent。异常在 except 外重新抛固定错误，原 SDK exception/traceback 不进入 Future 的公开异常 context。Main 清空入参槽和 request body 的密码引用，React 使用无状态密码 input，提交同步清 DOM、finally 清局部引用。此为引用生命周期约束，不声称能擦除不可变字符串、IPC/fetch/SDK 内部缓冲或 Python/JS 堆的全部副本；未提供“记住密码”、密钥 UI、通用 getter 或自动重认证。

正常 App → ConnectionPanel → AuthenticatedPanel → Main 固定 IPC 已接通。Main 取自身已确认身份快照补 expectedFingerprint，核工程/backend/认证结果的 endpoint、fingerprint、requestId、connectionId、username；认证 current 前后门保护环境发现与 probe。环境请求只允许固定 DTO，ID 必须来自本 lease 最新目录；报告再核 scope、环境 ID、nonce===requestId、设备/可选 dataset 及选中解释器/prefix。无自由 shell/fetch/path 代理。UI 认证后显式发现，再选择环境并显式只读探测；目录显示“尚未探测”，报告分开标环境/数据就绪，小张量或缺包按真实报告展示。默认 CPU、不检查数据；可选现有数据检查仍 download=False。输入目标变化、取消、工程切换、面板卸载、backend 失效均清上下文；身份请求 key 强制状态隔离。会话轮询单飞，迟返/超时不恢复 UI，不自动登录。关闭认证/环境检查仅表示本地失效和请求清理，不声称远端进程已经退出。

独立审查发现并修复的缺口：旧 flat `/connections/probe` 与 `/connections/trust-host-key` 绕过 scope（已删除，常驻回归验证 404）；环境 nonce 原仅检查 UUID（改为等于请求 ID）；环境 cancel 原等待 HTTP 后可能误关后续操作（改为同步失效、迟返不改新状态）；身份 probe 原在 scope/重放检查前关闭 lease（移到检查成功后的共享锁内回调，旧 ID/外工程 422 后 live lease 保持）；已认证时父面板文案冲突、身份 prop 变化可能保留 React 状态（改静态身份说明并加请求 key）。这些是离线协议/源码发现，未声称实际远端攻击或真实 Electron 验收。

实际命令与结果（UV/XDG 缓存沿用 `/workspace`，不改 HOME）：

| 命令 | 结果与证据范围 |
| --- | --- |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_connection_manager.py services/backend/tests/test_ssh_identity.py services/backend/tests/test_environment_service.py services/backend/tests/test_environment_transport.py services/backend/tests/test_environment_probe_payload.py` | **101 PASS**，3.10 秒；11 manager/API、41 identity/SDK、28 environment service、13 transport、8 payload；保留 Starlette 弃用 warning。全部 synthetic PUBLIC keys、内存 SDK/通道，装网络失败哨兵；包含真实 FastAPI → manager → 既有 environment core/adapter → 合成 channel；并非真实 SSH/torch。独立审查最新 manager+identity **52 PASS** |
| `pnpm exec vitest run apps/desktop/electron/session-workflow.test.mts apps/desktop/electron/identity-workflow.test.mts` | **21 PASS**；12 session +9 identity。Main 边界是真实实现，Backend 为定向合成替身 |
| `pnpm exec vitest run apps/desktop/src/AuthenticatedPanel.test.mts apps/desktop/src/ConnectionPanel.test.mts` | **10 PASS**；真实 React/JSDOM，5 auth/environment +5 identity；API 为合成替身。独立四份联合 **31/31 PASS** |
| `pnpm exec vitest run apps/desktop/src/App.test.mts -t 'normal SSH'` | **2 PASS /4 SKIP**；真实 App 正常入口 → 身份 → 密码 DOM 先清 → 认证 → 显式发现 → 关闭 exact lease；API/canvas 仍测试替身。作者与独立审查者各一次；未跑旧 M4 套件 |
| `pnpm contracts`、`pnpm check` | 最终 PASS；新增3公共合同与镜像，TS、mypy34源文件、ruff/格式、合同漂移、原真实 Blockly fixtures 全通过。首次 check 缺 UV_CACHE_DIR 因只读 HOME 缓存 FAIL；随后并发格式化期间 check 格式 FAIL、新 App 测试 mock 字面类型 FAIL 均修正后通过，不改变门限。一次根目录 `uv run ruff` 找不到工具，改用已存在 backend .venv 工具，未安装依赖 |
| `pnpm build`、最终 `pnpm --filter @easyai/desktop build` | PASS；Main/renderer/PyInstaller；最后请求 key 修改后重建桌面产物。保留现有 chunk 大小 warning，未调高门限 |
| `node scripts/test-frozen-ssh.mjs` | 最终 PASS；真实冻结 sidecar 临时 cwd、本机 HTTP 鉴权/严格 DTO/脱敏/旧路由404/scoped cancel/confirm/无当前工程认证拒绝/无 lease 环境拒绝/EOF exit0，未发有效 SSH probe 或运行环境 payload。新增 auth smoke 初稿把管理器 SshFailure 状态误期望422而 FAIL；按既有固定503映射纠正断言，错误码/无回显仍精确检查 |
| PyInstaller `ZlibArchiveReader` 检查及固定资源比对 | PASS：connection_manager、environment_service、ssh_identity、domain.connections 均在包内；probe.py 与源码逐字相同；应用 Python find_spec('torch') 为 None，无训练包安装/import |
| `git diff --check`、原件 hash/字节及远端基线检查 | PASS；未变依赖、lock、安全权限、配置或用户数据 |

原计划仍 **116185 字节**，SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原 `docs/v0.0.0.md` hash `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README hash `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852` 均实际复核未变。推送前 origin 开发分支仍为起点9bb92c5，main仍为 `5323f86232529efcfb52131168ad049f01b219f3`；仅正常推开发分支，最终 HEAD/远端一致及工作区在最终回执核验。

**NOT RUN / 剩余边界：**整体 pnpm test、旧 M4 suite、真实 Electron/E2E、Windows 安全信任存储/桌面、真实 SSH/认证/conda/硬件/数据、小张量真实训练依赖，以及远端取消/退出/重连/SFTP/训练监督均未验。本轮远端 CI 未查询，结果未知；M4 run39118961613 在2040a05 HEAD的 desktop failed/check succeeded 历史证据保持，失败根因未知，不重试 Actions Forbidden 或换通道。没有 main 写入、强推、发布、PR、部署、付费或安全权限修改。本轮真实远端动作未请求执行，属于授权外 NOT RUN，并非新的工具拒绝/结果不明。M5 仍未整体验收，A/B 均未通过。

下一项按计划继续 M5 的认证 profile/SSH 上传、远端执行和取消/断线续读的合同与离线闭环设计；真实验证前仍需明确获准目标、独立核验指纹、认证方式与执行范围，以及既有 Linux 工具/课程解释器和数据条件。不自动安装/下载/配置老师环境；不把当前只读入口当成完整远端训练或 v0.0.0 发布。

## M5.3/4 远端运行协调合同与离线核心（尚无真实 SSH 执行适配）

起点 SHA `548477c89b464ebfaf7201a04f27c70b9d3d574c`，Easy-AI 原 checkout / T1doo origin / `codex/demo-v0.0.0`，工作区干净。功能完整 SHA **`84ad8b315f13bd9ef4ade3ce7a1845c615cb9b1f`**。父级授权继续最高价值独立代码切片，仅代码、合成 transport 与本机标准库进程夹具；本轮未连接 SSH、未使用用户凭据、未上传/执行远端代码、未训练或下载。先核对计划13.3–13.6/M5与既有 ManagedSupervisor、RunService、EventJournal：复用现有本地进程监督与 EventJournal.ingest，未重写训练器或旧 UI。

本轮增加 `domain/remote_run.py` 的3个 Python 权威合同及生成镜像、`runners/ssh.py` 的 SshRunCoordinator 和严格 RemoteRunTransport **Protocol**、`security/remote_cache.py`。**没有具体 Paramiko/SFTP runner、portable 远端 supervisor、公开运行 API 或新 UI**；接口中的 stage/start/inspect/read/cancel 目前只有测试适配。不是完整 M5.3、真实 SSH 可运行链或远端 exactly-once 证明。

- 不可变运行身份绑定稳定 targetId、用户名、规范 endpoint/host 指纹、工程/runId、远端 runRoot、launchId、program/code/bundle/config 四个 hash。`identity_from_config` 从既有权威 RunConfig 计算 canonical config hash，不接受 renderer hash 覆盖或本机 ~ 展开。connectionId 不充当稳定 targetId；checkpoint 只记上次 lease ID 以拒绝复用。显式 attach 必须通过当前认证 guard、同原用户名/项目/目标/指纹，并使用新的 connectionId；重启也不允许复用旧 ID。无凭据保存、自动认证或续期。
- 单一 target 缓存/写入锁持有整个生命周期，已有身份不匹配不合并、不覆盖；本切片尚不提供归档后新任务策略。stage 端口约定仅完整 hash 验证及原子发布成功才 ACK，具体远端实现仍待做。启动先 O_EXCL+fsync 独立 start-intent，再 fsync checkpoint，然后才允许一次 start 调用。消费后 ACK 丢失、超时、控制器重建或 inspect NOT_FOUND 都只检查，不重发 start、不重置为可启动。marker 已落盘但 checkpoint 未更新的崩溃窗口保守恢复 unknown/STARTING；即使 start 实际尚未调用，也不自动补发。这是控制器 at-most-once 的保守代价，不是跨机器 exactly-once。
- 连接状态与执行状态分离。断连或 lease 失效保留原执行状态和不确定启动/取消意图；close 只关闭 I/O，不取消脱离通道的执行。cancel pending 先落盘；恢复先核完整 owner 身份、inspect/补读，终态已到则保留原 COMPLETED/FAILED/CANCELLED，并将取消意图 resolved；仍运行才向同 launch 幂等请求取消。cancel ACK 本身不产生 CANCELLED；迟到旧 lease 响应在 guard 后被拒绝。
- events/stdout/stderr 各有 generation、字节长度、SHA256；读取固定 stream 枚举与有界 offset/length，不开放通用路径读取或 shell。每个 chunk 核 owner/stream/generation/offset/整个已读前缀 hash，检测轮转、截短和前缀改写；每次最多64KiB，单 stream 上限128MiB。向 adapter 传每 I/O 至多5秒的 timeout，协调操作逻辑预算20秒，晚回结果不接受；真正硬截止/退出仍须未来 adapter/OS 实现，未作硬 DNS 保证。错误路径把 binding 转 retiring，在锁外 close；ready 必须 close 已成功返回且无在途 I/O。关闭失败即使 quiescent=True 仍保留 owner/写锁、拒新绑定，不自动重试或弃置。
- 原始字节先保留，JSONL 仅解析完整 LF 记录；半 UTF8/半行不独立 decode、不丢尾；日志按 bytes 给增量 decoder。只公开 checkpoint 已提交长度，hash 失败回滚当次追加，拒绝字节不作为已验日志展示。重启验证已提交缓存前缀 hash，仅重放已提交事件边界。规范事件复用 EventJournal 连续 sourceSeq/同序去重与冲突拒绝，fsync 在 checkpoint 提交前；崩溃后可以重读，不重复指标。终态要求 sealed 最终三流长度/hash全部读到、唯一末尾 process_exited 与 exitCode 一致；COMPLETED 另需 pipeline_completed/exit0/无错误。它只表示执行退出，**artifactsVerified 恒 False，没有 SUCCEEDED 或同步 ready**；产物 manifest/文件路径/size/hash验证与下载仍是后续门。
- 缓存使用 POSIX 逐级 directory FD/O_NOFOLLOW、uid/no022 与固定根 inode、文件 owner/mode/regular 检查；新目录700/文件600，不 chmod/chown 修补已有目录。受信 sticky 临时祖先与已核 host-key store 的策略一致。它防止不安全共享目录/文件重置启动许可，不声称能防御同 UID 任意删除全部状态。Windows安全存储尚未实现，明确拒绝，不声称支持。

父级顺带指出的认证 TTL 健壮性已修：`ConnectionManager._expire` 提前触发时按**原绝对期限剩余 TTL**重排，连接 ID 精确隔离；旧/新 timer 回调都不能关闭后续 lease，不延长原五分钟期限。

两位既有审查者仅只读设计/实现/定向验证，单一集成者写入。独审发现并复现后关闭：未静止 adapter 失败后仍可重入（转 retiring+前后 quiet 门）；被最终 hash 拒绝的日志仍可被公开读（提交边界+回滚+恢复验证）；可写目录/checkpoint 允许重置启动（逐级权限门+独立 marker）；marker fsync 崩溃窗口永久打不开（保守 unknown）；close 抛异常但 idle 时丢失 owner（done/succeeded/quiet 三门）；read Protocol 缺 timeout（签名补齐）；fresh lease 原仅为上层约定（现持久拒同 connectionId）。全部为合成/本机协议复现，没有远端攻击或真实 SSH 验收声明。

实际命令与结果：

| 命令 | 结果与范围 |
| --- | --- |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_ssh_run_coordinator.py services/backend/tests/test_connection_manager.py -k 'coordinator or early_lease'` | 最终 **36 PASS /11 deselected**，0.67秒；35新协调器用例+1提前TTL用例，未重复上一轮101套。修复新缺陷后有针对地重跑；两位独立审查者最终亦36/11。覆盖启动 ACK 丢失/NOT_FOUND/重启/marker窗口/同target互斥、身份与hash变化、取消先到/ACK超时/完成竞态、旧lease迟返、未静止/close失败、日志前缀/截短/轮转/hash拒绝、UTF8半行、序号/封存/退出证据、可写缓存与symlink拒绝、权威config hash和逻辑超时 |
| 同一测试内2个实际 ManagedSupervisor 夹具 | 本机标准库子进程真实输出中文日志、断开只关测试 I/O 后仍运行、显式新lease恢复补日志、实际 wait/退出事件、取消只影响所持进程组，旁侧独立进程保持存活；不 import torch、不执行生成训练、不声称真实 SSH 断线或远端进程清理 |
| `pnpm contracts`、`pnpm check` | PASS；3新增合同/镜像/漂移、mypy37源文件、ruff/格式、TS、原Blockly fixtures。新代码首轮mypy缺annotation曾FAIL，补齐后最终通过；未修改门限或依赖 |
| `git diff --check`、原件 hash、开发分支/main远端检查 | PASS；原 README/规格/计划未改，依赖/lock/CI工作流/安全权限未变，机器配置/凭据/运行数据未入库 |

本轮 **NOT RUN**：整体 pnpm test、旧101回归/M4 suite、build/冻结包重新验证、真实 Electron/E2E、Windows、真实 SSH/SFTP、远端 `--start/--serve`、实际数据/torch/硬件/训练、实际远端取消/重连、产物下载及校验。此次纯核心未接应用运行入口，因此不以旧构建替代新实现验收。远端 CI 未查询/结果未知；既有 M4 run39118961613 在2040a05 HEAD的 desktop failed/check succeeded 历史边界不变，原因未知，未重试 Actions Forbidden 或绕路。没有新的工具拒绝或结果不明；真实远端动作是授权外 NOT RUN。

原计划116185字节、SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原v0.0.0 hash `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README hash `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`实际复核未变。推送前 origin 开发分支仍起点548477c，main仍 `5323f86232529efcfb52131168ad049f01b219f3`。仅正常推开发分支；完整最终 HEAD/远端/工作区在最终回执核验，无main写入、强推、Release、PR、部署或新增权限。

下一最高价值切片仍在M5.3：实现固定 portable owner 的原子 claim/独立 session/heartbeat/封存证据与受控 SFTP Bundle stage，按上述冻结合同接真实适配前先做离线进程/文件协议验证；随后才接运行 API、日志/产物下载与UI恢复。稳定连接profile/私钥入口、数据绑定也仍未完整。真实验证须先获准具体目标、独立指纹、认证方式与执行范围，不自动安装/下载或改教师环境。M5整体与A/B均未验收，未升级支持声明。

## M5.3 portable owner 与共用监督核心（本机打包进程验证，非真实 SSH）

起点 SHA `1259b3eb2972b23ac374f0f84be2b926e1888092`，同一 Easy-AI checkout / T1doo origin / `codex/demo-v0.0.0`，起点干净。功能完整 SHA **`fc979c5f406f2aa1cc8256057e79a5f07832e705`**。父级继续授权真正缺少的监督器或适配代码，仍只代码/离线协议/本机标准库进程；本轮选择 portable owner，不同时扩展 SFTP/API/UI。没有真实 SSH/SFTP、远端上传/执行、用户凭据、训练、数据下载或教师环境配置。设计先独审，两位既有审查者只读复核，单一集成者写入。

新增 `runtime/supervisor.py` 和 `portable_journal.py`，并将原 ManagedSupervisor 算法抽取到唯一 `easyai/runtime/managed.py` 标准库核心；本地薄 wrapper 继续注入原 EventJournal，导出 Bundle 复制同一 core 源码，没有两份监督算法。Bundle 的固定10个文件包含 owner/core/journal/entry/train/source-map/IR/说明，hash 覆盖新辅助文件；已接 PyInstaller data 资源和 source/frozen 布局 fallback。没有 MNIST 专用 owner、生产 mock runner 或预制指标。

owner 的固定 CLI 为 `--start/--serve/--inspect/--cancel --run-dir <abs>`。每个命令独立检查 POSIX 逐级 nonsymlink/uid/no022、普通有界文件、JSON重复键/非有限数、完整运行身份、canonical configHash、Bundle文件集合/hash/codeHash、固定解释器/运行根及每文件8MiB/总32MiB边界；code目录还必须恰好只含7个已哈希文件，拒绝额外模块/包/pyc，避免同目录导入绕过hash门。`-I`下只有完整校验后显式加载同目录标准库 core/journal，不依赖 Easy-AI/FastAPI/Paramiko/Pydantic 或远端 HTTP。

`--start` 先独占/fsync remote-launch 身份及 stream generations，再用当前 sys.executable 派生独立 session 的 `--serve`，stdin DEVNULL、stdout/stderr重定向专用 owner 日志，不靠调用 CLI/SSH channel 存活。serve 再独立验证并取得持久 serve claim 与 kernel owner 锁，训练 spawn 前已落盘；重复 start 只返同身份，已有 claim/未知或过期 heartbeat 不触发重启，直接重复 serve 也不能再创建 child。ACK 只是身份收据，不是运行成功；owner 尚未建状态或已失去 heartbeat 时 inspect 返回未知，不能宣称训练停止。inspect 按同主机 monotonic heartbeat 检查3秒窗口；sealed后保持状态字节、heartbeat及三流generation/最终长度/hash不变。

实际子进程仍运行 Bundle 中的通用 entry/train，解释器与选定环境保持一致；cache路径限制到本次run目录，不安装/下载或修改共享环境。cancel CLI 只持久化完整identity请求；只有持 Popen 的 owner 能调用共用核心取消自己创建的进程组，不接受任意PID/PGID/命令/信号。错误身份/损坏取消记录不触发误取消；完成后的 cancel 不改变终态。三流按固定size前缀计算hash，实际wait、双路drain与日志fsync后才seal；core的exit事件/状态/done处于同一RLock事务，owner在snapshot上下文内取流前缀，避免完成竞态产生“未sealed却含退出事件”。关闭I/O与执行停止仍严格区分。

训练Popen真实未能创建child时新增监督器专属 `process_spawn_failed` 事件（fixed code+spawnFailed=True），没有伪造process_exited或exitCode；RemoteRunObservation只允许 FAILED+sealed+spawnFailed=True+exitCode=None，协调器核唯一匹配spawn事件。成功spawn后的终态仍必须真实wait/exitCode及末尾唯一process_exited。已更新权威Event合同/镜像、RunService恢复、Main固定事件白名单与技术事件展示；child可发事件白名单不含此新事件。COMPLETED仍只是执行结果，`artifactsVerified`恒False；本轮未实现或声称产物manifest/文件同步就绪。

portable journal有严格64KiB/finite/epoch类型与范围/单写sourceSeq门，新文件和日志目录按平台能力fsync；write/fsync不确定后置墓碑，拒绝再次append，不重复序号。日志flush/fsync/close失败转管理fault，不能仅线程异常后仍报COMPLETED。所有新目录/文件只在应用管理的run内创建，不chmod/chown修补既有目录；Windows本地core保留原分支，portable owner只宣称POSIX/Linux代码路径，真实平台验证仍缺。

独审真实本机复现并修复三项：未列manifest的code/tempfile.py可被导入（严格目录内容门，增加3类额外模块/包拒绝回归）；log fsync失败被线程异常吞掉（转runtime_error/fault，实际exit0也FAILED）；done/state/日志各自采样发生完成竞态（core一致snapshot，真实journal门控回归证明exit append中snapshot不能穿越）。另修作者发现的错误身份cancel会经finally触发cleanup误取消，现仅身份完全匹配才请求取消。上述均为本机标准库/合成故障复现，不是远端攻击或实际SSH验收。

实际命令（沿用既有UV/XDG workspace缓存，不改HOME）：

| 命令 | 结果与范围 |
| --- | --- |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_portable_owner.py services/backend/tests/test_supervisor.py` | 最终 **45 PASS**，6.26秒（20 portable +25 core）。两位独立审查者最终各45 PASS。真实基础Python无Easy-AI/Pydantic/Paramiko/torch依赖；真实owner/stdlibchild，重复/并发start、重复serve、claim未知不接管、coordinator→test-only本机CLI→owner丢ACK/新lease恢复/取消/日志补读、完成后取消、foreign cancel拒绝、完整Bundle tamper/hash/未哈希模块拒绝、2MiB stderr与Unicode、坏协议本地/portable一致失败、封存稳定、日志fsync故障、原子snapshot、journal不确定写入门。不是全套测试 |
| 同上真实spawn失败用例 | 仅在测试专有的serve进程设置OS RLIMIT_NPROC=0，实际Popen收到OS拒绝；无Popen模拟成功/假退出码，无主机/教师环境改动。唯一spawn失败事件，coordinator接受FAILED/exitCodeNone且产物未验。受限core源码为明确测试夹具后重新计算manifest，不进入生产Bundle |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_run_recovery.py services/backend/tests/test_run_state_recovery.py services/backend/tests/test_run_service.py services/backend/tests/test_compilation.py` | **45 PASS**，1.49秒，保留Starlette弃用warning；因共用core/Bundle/event恢复变化而跑受影响路径，含无假exit恢复与冻结资源布局fallback。没有训练或旧M4套件 |
| `pnpm exec vitest run apps/desktop/electron/events.test.mts` | **6 PASS**；新spawn失败事件可通过固定解析且不制造exitCode，未启动Electron |
| `pnpm contracts`、`pnpm check` | 最终PASS；Event/RemoteObservation/Checkpoint镜像、TS、mypy38源文件、ruff/格式、合同漂移与原Blockly fixtures均通过。旧Bundle精确集合测试起初因新增3文件FAIL，更新为完整10文件精确集合并保留全部hash/确定性/禁止覆盖断言后通过；大stderr新夹具起初少换行把completion藏在普通日志后FAIL，修夹具遵守协议后通过，不放宽协议门 |
| `node scripts/python-task.mjs build` | PASS，最新共用core/journal源修改后重建PyInstaller；未重复桌面build/旧桌面suite |
| `node scripts/test-frozen-ssh.mjs` 与 PyInstaller archive检查 | PASS；probe/owner/journal/同源managed四份资源逐字一致，共用core+wrapper字节码在包内；既有M5本机HTTP鉴权/DTO/拒绝未认证/EOF退出。未调用有效SSH或在远端运行owner；应用Pythonfind_spec('torch')仍None |
| `git diff --check`、原件hash/字节、分支/远端检查 | PASS；没有依赖/lock/CI/安全权限变化，没有凭据、机器配置或运行数据提交 |

**新的CI证据（父级邮件级，非本执行器绕路查询）：**起点完整SHA `1259b3eb2972b23ac374f0f84be2b926e1888092` 的 run **39126092935** 于 **2026-10-18 12:10:15 UTC**完成，**check succeeded / desktop failed，各2 annotations**。只有job级，具体失败步骤未知，不能归因本地sandbox，也不是全CI通过。此前M4历史边界保留；本轮最终commit的远端CI未查询、结果未知，没有重试被拒Actions或换渠道。

本轮 **NOT RUN**：整体pnpm test、旧101回归、旧M4/真实Electron/E2E、Windows实测、真实SSH/SFTP、远端上传或执行、实际训练/数据/torch/硬件、远端断网/恢复/取消清理、产物下载/最终权重核验。测试本机CLI transport只存在tests，stage表示预先明确构建的本机夹具，不代表SFTP原子部署成功。owner源码可组合且本机验证通过，**真实网络适配、公开运行API与UI仍未接**；M5整体与A/B均未验收。真实远端动作为授权外NOT RUN，没有新的工具拒绝或不明结果。

原计划仍116185字节、SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原v0.0.0 hash `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README hash `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`均复核未变。推送前开发origin仍1259b3e，main仍 `5323f86232529efcfb52131168ad049f01b219f3`；只正常推开发分支，最终HEAD/远端一致及工作区在最终回执核验，无main写入/强推/Release/PR/部署。

下一最高价值切片是基于已核身份/短时认证的具体SSH/SFTP transport：仅固定Bundle原子stage、固定owner命令、受控三流/manifest读取与完整scope guard，先离线文件/transport夹具核验，再接运行API/UI和artifact hash同步。真实SSH全链路仍须明确获准目标/独立指纹/认证与执行范围，不能自动配置或修改教师环境。
