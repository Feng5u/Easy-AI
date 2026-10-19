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

## M5.4 受控只读 SFTP 产物同步（本机接口夹具，非真实 SFTP）

起点完整 SHA `6695d67f6422abfacaa405ca280b57754b8d9d56`，`/workspace/Easy-AI` / T1doo origin / `codex/demo-v0.0.0`，起点干净；功能完整 SHA **`47738aa2d2ea07053736a123b7a964377803374e`**。按父级续令选取“具体产物读取与本地原子同步”这一项，接既有 owner/协调器而不重复状态机；没有把此切片说成 M5.3 上传/启动适配已完成。仅常规代码、本机文件/标准库子进程与合成 SFTP API 夹具；没有真实 SSH/SFTP、远端上传/执行、用户凭据、安装、数据下载或训练。

owner 现在先原子写入并 fsync `remote-artifacts.json`，才发布 sealed status。权威 ArtifactManifest 合同及生成的 schema/TS 镜像包含完整 identity、owner euid、最后 sourceSeq、最终事件流 SHA256 和所有 artifact_created 原始记录；超量或清单落盘失败不能宣称 sealed。清单只是来源收据，远端 syncState/输出文本不构成下载指令或本地就绪证据。执行 COMPLETED 与 `artifactsVerified=False` 的原有门保留。

`SshRunCoordinator.artifact_snapshot` 在锁内先核缓存已提交前缀，再复制 sealed checkpoint 和已持久化 journal；冻结 Bundle 的 canonical manifest/hash/codeHash 及 source-map 内容 hash 绑定到本次运行，稳定 block IDs 核 producer、contributors 与 event.blockId。新 `SftpArtifactSync` 逐项比对清单与全部产物事件（顺序、完整字段、ID/path 唯一、不能省略/追加），拒绝来源错配及非封存快照。应用通过 `ConnectionManager.artifact_sync` 获内部服务，前后核同一个仍有效的 lease、project、username、endpoint、host fingerprint；没有新增 renderer/HTTP/IPC 的任意路径读取入口。

具体 Paramiko 适配通过已有 fresh-pin/auth 门 `open_probe_channel`，先设 timeout，再固定请求 `sftp` subsystem 并构造 SFTPClient；不用 from_transport 另开未守卫 channel，不调用 get/prefetch 或远端命令/写接口。环境探测与同步共用真实 VerifiedSshSession.io_lock；物理 worker 未静止、关闭未确认时，环境操作/另一次同步和新会话均不能绕开 owner。watchdog 超时/取消只关闭自己的 I/O/session，不取消 detached owner、不杀远端 PID、不重新 start。迟返 worker 仍持物理门与本地 cache writer，失效 lease/取消后不能发布迟到索引。

读取仅限两个固定控制记录与已验证 artifactId 所对应的 outputs 路径；拒绝绝对路径、..、反斜杠/驱动器、空或点组件、控制字符、symlink、非普通文件、不安全 UID/mode、缺失属性、声明长度与 EOF 不符。每级 lstat、handle stat 及读后路径/大小/时间属性复核，数据逐次最多64KiB，核实际总量与内容 SHA256。边界为清单64KiB、最多256产物、单产物按原计划100MiB、总256MiB，PNG8MiB且限制尺寸/总像素并核完整 chunk/CRC/IEND；source-map 独立允许8MiB，不能被清单64KiB上限误拒。模型 pt/pth 只保存原始字节，绝不 torch.load/pickle 执行；文本仅有界 UTF-8，不执行远端输出指令。

本地 POSIX 私有 cache 逐级目录 FD/uid/no022/nofollow 核验，固定 kernel writer lock 不删除未知锁/目录。永久完整 identity marker 和现有 index 身份门防止跨 run/launch 接管；随机600 `.part` 经大小/hash/格式/fsync 后发布内容寻址 blob，复用已有 blob 也重新核验。远端 SFTP/channel 成功关闭后，才在有效 lease 守卫内原子提交 ready index；失败可留下未索引的已验 blob，不冒充 ready。按 opaque artifactId 读回，每次重新核 blob/hash/PNG，不单信 index 的 ready。取消线性化点为最终共享锁内的 guard：边界前取消拒提交；通过该点并完成提交后，迟到取消不能把已提交成功改为失败。精确 replace 入口取消回归覆盖此竞态。

能力边界：SFTPv3 没有 O_NOFOLLOW，lstat/open 之间无法对恶意 sameUID 并发替换给出原子保证；私有 owner 目录、读前后属性与内容 hash 提供当前约束，不宣称解决该协议能力边界。本机 cache 的实现/实测为 POSIX，Windows 仍未验。当前只同步 sealed 产物，运行中的持续产物同步、完整最终必需产物成功门及公开运行 API/UI 尚未实现。

独立只读审查发现并修复：跨身份 index 被覆盖、SDK 关闭失败却已有 ready、合法大 source-map 被64KiB误拒，以及最后 guard/replace 瞬间取消导致返回失败但已就绪。两位审查者均未写实现文件或联网，单一集成者写入。首轮新夹具/实现曾 FAIL（错误包装与容器根 UID anchor、测试 import/ACK 时序及清单夹具未同步修改），修复并保留严格拒绝门后下表最终通过；没有放宽安全测试。一次命令误写不存在 `test_ssh_client.py` 导致 **ERROR/no tests ran**，随后按实际 `test_ssh_identity.py` 路径执行下表，不计前者为测试成功。

实际命令（沿用既有 UV/XDG workspace 缓存，不改 HOME）：

| 命令 | 最终结果与范围 |
| --- | --- |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_remote_artifacts.py services/backend/tests/test_portable_owner.py services/backend/tests/test_connection_manager.py services/backend/tests/test_environment_transport.py services/backend/tests/test_ssh_identity.py` | **134 PASS**，10.10秒，Starlette弃用warning；含43新增产物用例、owner及受影响共享会话/认证/探测门。覆盖清单/来源/块ID、遍历/链接/FIFO/权限、size/hash/PNG、原子缓存/跨身份/锁保留、raw模型分块、关闭失败、cancel/lease/timeout停滞与gate、最终提交竞态 |
| 上述43用例中的组合验证 | 真实本机基础Python启动 detached owner 和标准库非训练 child，生成明确的结构PNG夹具；启动 ACK 丢失→新lease coordinator恢复→完整snapshot→本地 SFTP API fixture→文件读回。start一次/重连start零次，实际日志及来源hash校验，artifactsVerified仍False。不是实际网络/SFTP E2E或科学结果 |
| 独立只读验证 | 审查者一 **63 PASS**（43 artifact+20 owner）；审查者二 **48 PASS/12 deselected**（43 artifact+5 exact lease accessor），此前另25 env/manager通过。范围分别记录，不能累加冒充不同用例总数 |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_compilation.py services/backend/tests/test_ssh_run_coordinator.py` | **61 PASS**，0.87秒，Starlette弃用warning；因owner Bundle/协调器snapshot变化执行受影响编译与持久协调门 |
| `pnpm contracts`、`pnpm check` | PASS；权威 ArtifactManifest 镜像、mypy39源文件、ruff/格式、TS、合同漂移、原Blockly fixtures。首轮mypy consumer返回类型和ruff lambda曾FAIL，已修，无依赖/锁/工作流变更 |
| `node scripts/python-task.mjs build` | PASS；最新 owner/SFTP 服务源码重建后端冻结包，未重复桌面 build |
| `node scripts/test-frozen-ssh.mjs`、PyInstaller PYZ模块检查、应用 Python torch探测 | PASS；owner/probe/journal/core资源逐字核对，既有本机HTTP鉴权/DTO/拒绝有效SSH前操作/EOF退出；remote_artifacts、remote_run、connection_manager在包内，torch仍不存在。未调用真实SFTP下载 |
| `git diff --check`、原件字节/hash、分支/远端核验 | PASS；原文件不变，无凭据/机器配置/数据入库 |

本轮 **NOT RUN**：整体pnpm test、真实Electron/E2E、Windows、真实SSH/SFTP/远端上传或owner执行、远端断网恢复及进程清理、实际数据/torch/训练/硬件、最终真实PNG/权重验收、运行中产物持续同步。没有新增工具拒绝或结果不明；真实远端动作按本轮授权范围不执行。远端CI未查询，当前commit结果未知；继续保留父级提供1259b3eb2972b23ac374f0f84be2b926e1888092/run39126092935的check succeeded/desktop failed（job级、各2annotations、具体失败步骤未知），不重试被拒Actions、不绕路、不宣称全CI通过。

原计划116185字节，SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原v0.0.0 hash `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README hash `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`实际复核不变。推送前 origin 开发分支仍6695d67，main仍 `5323f86232529efcfb52131168ad049f01b219f3`；只正常推开发分支，最终完整HEAD/远端/工作区在回执核验。没有main写入、强推、部署、Release、PR、新增付费/权限或Feng5u原仓库写入。

下一项仍为 M5.3 受控 Bundle 原子 SFTP stage 和固定 owner 命令/三流网络适配（start未知必须只inspect，不重发），然后接 scoped run API/UI、运行中同步与最终产物门；稳定profile/私钥和数据绑定仍未完整。实现继续按代码与本地协议夹具推进；真实验证需另有具体目标、独立指纹、认证与执行范围授权，不能自动安装/下载或改教师环境。**M5整体与A/B均未验收。**

## M5.3 Bundle 原子 stage 与固定 owner SSH 适配（离线端组合，非真实服务器验收）

起点完整 SHA `bc368c0ecc3b4bb45ea3ecd4e5e49cf0771a23df`，同一 `/workspace/Easy-AI`、T1doo origin、`codex/demo-v0.0.0`，起点干净。功能完整 SHA **`c136d595982f48cb1e93dbd73068ecf2a6947242`**。按父级续令实现上传和命令适配，仍仅生产代码、离线合成 SSH/SFTP API 端与测试专有本机标准库进程；没有真实连接/上传/远端执行、用户凭据、torch、训练或数据下载。单一集成者写入，两位既有审查者只读设计、实现与定向验证。

`RemoteBundle.freeze` 在受保护的本地目录 FD 下读取固定文件，强制同目录已持久化 `run-config.json` 和 `remote-identity.json` 严格等于本次权威 config/identity；不接受仅凭调用方重算的 hash 改目标。固定10个 hashed Bundle 文件加 manifest/config/identity 共13文件，核精确集合、完整 canonical bundle/config/hash、codeHash、每文件8MiB/总32MiB、普通文件/uid/no022/nofollow，code目录拒额外模块/包。Python/run/data/environmentPrefix 均过远端路径门，解释器与运行根另拒空/点段。通过后冻结 bytes，不再在网络操作中重读可能被编辑的本地源文件。compiler 的 `runtime_sources` 成为 export 与真实性验证共用的唯一 helper 来源；篡改 owner/helper 即使重算 manifest 和持久快照，也不能作为当前打包 helper 执行。

新增生产 `OwnerSshTransport` 实现原协调器 `stage/start/inspect/read/cancel/close/quiescent` port，未重复运行状态机。`ConnectionManager.owner_transport` 只提供内部 factory，同 lease/project/username/endpoint/fingerprint 及项目 epoch 守卫贯穿操作；从持久 coordinator checkpoint 决定是否有初次 stage/start 权限，unknown/acknowledged 接续默认禁止这两个动作。实际 VerifiedSshSession 的共同 io_lock 与 transport busy gate 在整个物理 worker、SDK 清理期间持有，环境探测/产物同步/新 transport 不能并发绕过；watchdog 返回未知不代表 worker 已静止，关闭只断 I/O，不取消 detached owner、不发 PID/PGID kill。

stage 先用本次选定的绝对 Python 执行固定 UID-only 标准库代码，严格核 nonce/platform=linux/int uid 的单一 JSON；不探测凭据、不安装。SFTP 检查已有父链、目录 uid/权限/非链接，不能自动创建或修补教师目录。每个随机 launchId 对应唯一 `.easyai-stage-<launchId>` 同级暂存目录，因此跨会话/进程重试也至多留下该 intent 的一个 partial；已存在 partial 直接拒绝，不合并、递归删除或另造随机目录。新目录700，文件使用 Paramiko `wx`（WRITE+CREATE|EXCL），仅对刚创建的 handle 设置600；分块≤64KiB写入，再逐文件 readback/EOF/size/完整 bytes/hash/精确 code 集合校验。最终只用标准 SFTP rename 的“目的必须不存在”语义，绝不调用 posix_rename、删除目的或覆盖 fallback。已有 runRoot 只能完整核验同一冻结身份与文件后接纳；合法运行日志/outputs/未知根目录文件保留，代码额外文件仍拒。rename 已执行而 ACK 丢失时，新 lease 只核原 runRoot 并接纳，不第二次 rename 或写入。

远端协议底层 SSH exec 必须是字符串，因此仅将固定结构 argv 交给 shlex.join；没有任意 shell、renderer argv、扩展变量、pipeline、PTY 或通用执行入口。外层固定 `/usr/bin/timeout`，内部固定选定 Python `-I -B`、已验证 owner 路径、action/run-dir/expected-identity 参数。每次 owner 命令前核完整冻结控制文件与 Bundle；stdout 精确一个有界 JSON，stderr有界，要求双流EOF和真实 exit_status=0，合法 EOF 先于 status 时等待至 deadline，不误拒。SDK 原始错误/输出不进入公开异常。

owner 的 `--expected-identity` 对 start/serve/inspect/cancel 全部必填，摘要来自本地冻结的完整身份，canonical ASCII JSON/sort/separators 与应用一致，覆盖中文路径、launch/config/user/endpointFP。校验在任何 claim/write/spawn 前，start 派生 serve 继承同摘要；不能临执行时改信远端身份。原启动 receipt/持久 claim/heartbeat/封存与取消所有权门继续使用，未知启动不清 marker。transport 在可能 exec 前不可逆置 start latch；协调器原有持久 intent 约束跨 lease 只 inspect，不因新 adapter 重发 start。

三流只接受固定名称，绑定已 inspect 的 identity/generation/观察长度；严格 offset/length/CHUNK 与源文件普通类型/uid/大小门，核固定 launch receipt 的严格身份及 stream keys/generation。首次非零 offset 接续仅计算一次本地实际前缀 SHA256，随后按流/世代增量 hash，避免每个分块从0重读造成平方级流量；最终长度/hash仍由协调器校验，不能信服务器给的摘要或日志中的指令。新 lease/迟到结果失效时不交付 stage/observation/chunk 的成功结果。

能力边界仍明确：标准 SFTPv3 没有 O_NOFOLLOW 或可用的持久 fsync 保证，读前后属性/hash/受保护目录不能消除恶意 sameUID 并发替换，也不构成真实服务器崩溃耐久验收。失败 partial 保留、可能已发布但 ACK 未知的 runRoot 只读核验；不清理未知内容。当前代码/私有本地 FD cache 实测为 POSIX/Linux，Windows 仍未验。新 expected-identity 协议只接纳符合当前打包 helper 的冻结 Bundle；不自动改写或重启旧的未知运行。

独审发现并复现 EOF-before-exit-status 被立即拒绝，已修等待协议并加回归。作者进一步补持久 authority 门、双流输出上限、readback/身份替换/清理失败与 prefix 增量测试。一次测试夹具把 RUNNING 当成已有 stdout 的证据而 FAIL；现在等待该已观察日志前缀再核 UTF8，没有改生产状态门。独审发现 stderr_limit 分支未加入参数表（当时实际37，不能报38）；补枚举后单独1 PASS，随后最终新增 scope 为下表35（32 owner+3 factory），不将旧 artifact5 或重复运行叠加为新增数量。首轮ruff因unused import/测试变量 FAIL，修正后最终 check PASS，未降低门限。

实际命令与结果（沿用既有 UV/XDG workspace 缓存）：

| 命令 | 最终结果与范围 |
| --- | --- |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_owner_transport.py services/backend/tests/test_connection_manager.py -k 'owner_transport or owner_factory'` | **35 PASS /17 deselected**，3.57秒；32个离线 adapter/snapshot 用例+3个新 manager factory 用例。两位独审最终分别35/17（3.51/3.49秒），无新具体P1/P2 |
| 上述实际本机组合夹具 | fake SSH exec 端解析并严格断言固定 argv，随后仅在本机运行测试专有、重新计算 manifest 的标准库 child；无真实 socket。包括 Unicode/空格/引号/分号/命令替换字符路径、原子非覆盖 stage、真实 owner start/inspect/cancel、半UTF8字节读取、消费 start 后丢ACK→新lease coordinator只inspect且start总1次、实际child继续运行/正常结束，artifactsVerified仍False。不冒充真实网络/SFTP/训练 |
| 同一新增 scope 的拒绝/资源回归 | 本地 config/identity 缺失或不等、伪造 helper+重算 manifest、extra module/symlink/权限、目录冲突逐字保留、上传中断只留唯一 partial、rename消费后ACK丢失只adopt、stage后identity换掉阻止start、readback坏不rename、UID nonce/noise/platform、stdout/stderr超限/缺EOF/晚status、坏generation/越观察长度、stalled worker保留gate、SDK+physicalclose失败不quiescent、首次resume后实际读取[10,1,1]证明不重读旧prefix |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_portable_owner.py services/backend/tests/test_remote_artifacts.py services/backend/tests/test_compilation.py` | **89 PASS**，7.55秒，Starlette弃用warning；因为本轮强制owner新参数和Bundle唯一helper来源变化而运行的受影响20 owner+43产物组合+26编译回归。不是完整旧套件或新增89项；后续authority改动仅涉及新freeze，已在新增scope完成复核，未重复无影响旧套件 |
| `pnpm check` | 最终PASS；mypy41源文件、ruff/格式、TS、原Blockly fixtures与schema漂移。没有新增DTO字段、依赖/lock/CI权限变更，不为凑数重生成合同 |
| `node scripts/python-task.mjs build` | PASS；authority加固后重新构建最新后端包，未重复桌面build |
| `node scripts/test-frozen-ssh.mjs`、PYZ源码检查 | PASS；四份runtime资源逐字一致，既有本机HTTP鉴权/DTO/拒绝有效SSH前操作及EOF退出；owner_transport/remote_bundle/manager模块在包内，递归核冻结代码含最新 SNAPSHOT_MISMATCH 门；应用Python仍无torch。未触发有效SSH或SFTP |
| `git diff --check`、原件字节/hash、工作区/远端核验 | PASS；无机器配置/凭据/运行数据提交，原 README/规格/计划不变 |

本轮 **NOT RUN**：整体pnpm test、无影响旧SSH身份/监督核心/桌面套件、真实Electron/E2E、Windows、真实SSH/SFTP服务器、真实上传或远端owner、远端断线/取消/清理/崩溃耐久、实际数据/torch/训练/硬件、完整最终产物成功门。命令端是本机接口兼容夹具，不代表目标服务器/环境支持声明。本轮无新工具拒绝或不明执行；不在授权范围内的真实远端动作明确不执行。远端CI未查询，最新head结果未知；既有run39126092935 job级 check succeeded/desktop failed/各2annotations、具体步骤未知的证据边界不变，不重试被拒Actions或绕路。

原计划仍116185字节、SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原v0.0.0 hash `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README hash `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`实际复核未变。推送前origin开发分支仍bc368c0，main仍 `5323f86232529efcfb52131168ad049f01b219f3`；只正常推开发分支，完整最终HEAD/远端一致与干净工作区在回执核验。没有main写入、强推、部署、Release、PR、新增付费/权限或Feng5u原仓库写入。

下一项是把已有认证/环境、冻结配置、协调器和真实适配组成 scoped 运行服务/API，再接UI中的日志/恢复/取消与产物；仍缺稳定profile/私钥、数据绑定、运行中产物同步及完整成功门。必须补Windows本地cache与明确目标的真实兼容验收；实际SSH/数据/训练仍须另有具体范围授权，不自动配置教师环境。**公开运行API/UI尚未接，M5整体与A/B均未验收。**

## 2026-10-18 — M5 共享运行服务/API 与桌面接线（离线组合通过，M5/A/B 未验收）

代码提交：`d4b3e5f7bd475c9ace555675b68c4bdef68800f3`，父提交 `59034d7b58707fba3e65f1a46c48a64c7bd1eb60`。本轮保持同一环境、单一写入者；两名既有代理只读审查，无并行写实现。进入本轮时开发分支远端与父提交一致，远端 main 为计划基线 `5323f86232529efcfb52131168ad049f01b219f3`。本 checkout 的本地分支为 codex/demo-v0.0.0 和 work，没有本地 main，origin fetch 配置仅跟踪 main；因此远端开发分支与 main 的证据取自 `git ls-remote origin refs/heads/codex/demo-v0.0.0 refs/heads/main`，不冒称不存在的 origin 开发跟踪引用已核对。

已实现原计划 873、1092–1099、1302–1305 行对应的共享 RunService 接入切片：本地和 SSH 共用 run ledger、项目并发排他、opaque runId、幂等记录及唯一 application journal/seq。SSH 协调器注入同一 journal，运行日志、源码、产物、历史和 SSE 均由共同 API 提供，GET/SSE 不建立 SSH 或隐式恢复。当前打开工程以外的运行读接口拒绝，SSE 每轮复核作用域并补齐末尾事件。执行状态、服务器连接状态、取消状态及同步状态分别保存；COMPLETED 只是执行完成，完整产物证明通过才允许产品 SUCCEEDED。本地既有 epoch/model/figure 成功策略提取为共同策略，没有降低必需产物门。

新增 `POST /projects/{projectId}/run-bindings`，只从当前 lease、后端保存的短期只读探测证据、已保存 revision/programHash、IR 实际数据集及指定 runBase 生成不可变绑定。探测要求现有 train/test 两个 split 均可读，始终 download=False；绑定和启动重新核原始探测期限，不靠 renderer 声称通过。启动 body 仅接受 runner=ssh、bindingId、expectedRevision/programHash，幂等键独立 header；不接受 shell、Bundle、任意 Python/data/runRoot 或凭据。后端生成独立 config/target/launch/run 身份，冻结实际编译结果、源图和当前 helper 后才允许 I/O。同 key 重试先查原有记录，包括绑定过期、已断开或应用重启后，不消耗新启动。

`POST /runs/{runId}/resume` 必须显式提供新认证 lease，并匹配持久的原 host/port/user/fingerprint；由既有 coordinator、OwnerSshTransport 和 SftpArtifactSync 实施固定命令、远端目录保护及产物校验。未知 start 永不重新执行。本轮使选定设备进入权威 RunConfig，明确 CPU 不再被自动 CUDA/MPS 选择覆盖，选定加速器缺失会报错。Conda executable/prefix 成对冻结，UID 与 owner 使用同一 `conda run -p ... --no-capture-output <python>` 参数，后台 serve 继承并核对原 prefix。直接调用本地启动入口不能执行 SSH 条目。应用依赖未增加 torch，未安装/下载任何训练环境或数据。

Main/preload 增加固定 bind/resume 通道和 ssh start 严格字段白名单，认证 scope 与 backend generation 前后复核。桌面可显式选择 SSH，先只读探测现有环境和数据，再绑定已保存工程后运行；编辑、版本/hash 改变、session 失效或期限到期会撤销当前绑定，迟到结果不回填。运行面板显示持久目标摘要、配置/实际设备、取消请求与确认、服务器连接和同步；重新认证后可显式恢复读取。process_exit 不会提前结束产物同步；COMPLETED+syncing 继续补尾，未验证产物不显示运行成功。关闭会话只关闭连接，不能声称远端进程已停止。

独立审查发现并修复：

- 待绑定时 authority 改变导致 busy 永久锁住：同步清 busy，并测试旧 Promise 不能回填。
- 已知尚未发起的运行取消后永久占项目：在 consuming start marker 的同一锁边界持久化 `cancelledBeforeStart` 证明，只有 not_attempted/无 observation/无 marker 才能本地 CANCELLED；恢复遇到 marker 反证直接拒绝。marker 已发出或 ACK 未知的运行仍必须取得真实 owner 退出证据。checkpoint 写失败回滚内存，重试不能确认未持久的取消。
- 可变 cache index 同 ID 指向其他合法 blob：每次 image/完整成功核验将 index 记录与冻结事件完整比较（仅 syncState 归一），随后复核 blob 大小/hash/PNG。重启先核保存快照、冻结 Bundle、source-map/事件证据，索引逐项一致后才认 ready；降低 IR 必需产物也被拒。
- SDK.close 阻塞绕过总退出时限：每 core 保留一个专属退休线程，退休与 worker 共用 3 秒总预算；超时明确 REMOTE_CLEANUP_UNCONFIRMED，继续保留 core/运行锁，后续重试复用原退休线程。未清理完成不能释放为新 owner。

两名只读审查者最终未发现剩余明确 P1/P2。后端审查者独立定向复跑 8 PASS（4 API、1 关闭预算、3 取消/索引），另以临时文件确认 IR 篡改拒绝及构造失败后锁可再开；后续作者增加消费 start 后丢 ACK 的 API 组合及 Conda 参数回归。只读源审不代表运行真实 Electron/Windows/SSH。

实际命令均在 `/workspace/Easy-AI`。Python 由 services/backend/.venv 提供；pnpm 的 Python 子命令统一使用 `UV_CACHE_DIR=/workspace/.uv-cache UV_PYTHON_INSTALL_DIR=/workspace/.python XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache`：

| 命令 | 最终结果与证据范围 |
| --- | --- |
| `pnpm contracts` | PASS；生成 RemoteBinding/RemoteBindingRequest/RemoteRunStartRequest，更新 Run/RunConfig/RemoteRunCheckpoint 镜像 |
| `pnpm test` | **PASS：Vitest 94 PASS/2 SKIP；pytest 450 PASS/1 SKIP**，后端29.19秒，仅既有 Starlette 弃用 warning。跳过项仍未验，不算通过 |
| `pnpm check` | PASS；TS、mypy44源文件、ruff/格式、合同漂移、实际 Blockly fixtures 与前端格式检查 |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_run_service.py services/backend/tests/test_remote_run_api.py services/backend/tests/test_owner_transport.py` | 50 PASS，9.16秒；包含后续新增两个定向用例。与全套有重合，不另加为新增数量 |
| `test_remote_run_api.py` 5用例 | HTTP→正式 ConnectionManager/OwnerSshTransport→coordinator→真实 portable owner→本机标准库专有 child→SFTP cache→日志/PNG API。合成探测元数据，不导入真实 torch、不使用 socket。验证白名单、绑定过期/错 hash、项目排他、幂等、应用重启无自动认证、显式新 lease只inspect、离线取消等实际退出、跨项目404、消费start丢ACK后start总1次、图片索引替换拒绝 |
| 上述 API 中的成功门 | 专有 child 无训练、epoch 指标或必需 model/全套图表，只写一个结构测试 PNG；正常退出后 **COMPLETED/sync error/artifactsVerified=false**。PNG可以独立ready并经opaque ID读回，不冒充 MNIST 效果或完整 SUCCEEDED |
| `pnpm build` | PASS；桌面 Vite + PyInstaller。Vite既有大chunk提示，无Electron启动。末次后端小修再以 `node scripts/python-task.mjs build` 重建 |
| `node scripts/test-frozen-ssh.mjs` | PASS；冻结资源逐字相等、本机HTTP鉴权、环境/身份拒绝、新 scoped run DTO 路由及 secret 输入不回显、EOF退出0。无有效远端操作 |
| `git diff --check`、原件 byte/hash | PASS；计划116185字节，SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原规格 SHA256 `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`；README SHA256 `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`。三原件均未改 |

中途 FAIL 已保留原因：未带 workspace cache 环境的 pnpm Python 子命令因默认 `/home/agent/.cache/uv` 只读而失败，改用上述既有缓存后通过；双 split 旧断言、合同生成漂移、unused import/返回类型、测试关闭时机及锁测试错误传 store 子目录已修后通过。没有放宽安全门或降低测试。最后完整套件包含全部450项后端测试。

CI 独立证据来自父级：`59034d7b58707fba3e65f1a46c48a64c7bd1eb60` 的 [run39130472267](https://github.com/T1doo/Easy-AI/actions/runs/39130472267) 于13:13:19 UTC结束，check succeeded、desktop failed，各2 annotations；失败步骤与根因尚无日志证据。只读检查 `.github/workflows/ci.yml` 可见 desktop 在 Windows 执行 persistence pytest、desktop build、test:e2e；当前 checkout 无可访问对应CI日志，不把Linux sandbox问题归为Windows根因。此前 Actions API Forbidden 仍受尊重，没有重试或绕路；本次新提交 CI 状态未知，本机通过不等于 CI 通过。

**NOT RUN / 未验收**：真实 SSH/SFTP、真实目标上传/远端 owner、硬件/torch/实际数据与训练、真实服务器断线取消及崩溃耐久、Windows客户端/cache、本机真实 Electron/E2E。原 Electron sandbox 拒绝未重试、未关闭 sandbox；原 Actions 拒绝未重试。当前 SSH 私有本地 cache 仍为 POSIX 实现，不能宣称 Windows SSH 可用；SFTPv3同UID替换/持久fsync能力边界不变。持久连接profile/私钥、运行中持续产物同步、目标平台兼容与真实完整产物/训练验收仍待完成。M5整体、A、B 均保持未验收，不自动进入发布。

本轮无新增付费/权限/凭据、部署、Release、PR、main写入、强推或Feng5u原仓库写入。下一项：先处理 Windows SSH cache/受支持平台及剩余 M5 合同；要验证真实环境须先取得明确目标、只读/写入目录、现有解释器和数据、允许命令及取消/清理范围。CI 根因需要获准可读的具体失败日志；当前失败步骤未知。编译、协议和离线兼容工作可继续，不以缺真实授权为理由捏造训练或阻断独立开发。

## 2026-10-18 — 父级独审 P2：工程切换与运行 API 的 TOCTOU 修复

代码提交 `b51c0e7c482f1d34f70a8d396d4013516a166617`，父提交 `3a324b0c7eace992f995716fd66091bbd686fc30`。父级独审指出旧 api.py 332–378 的 run_store 检查与后续 await/to_thread 动作分离，SSE 的检查与事件读取/交付同样分离。作者在旧提交增加有界同步屏障，先让A工程检查通过、暂停请求、切换B、再放行，实际复现 cancel 返回200并将A的CREATED运行改成CANCELLED；不是推测或真实远端事故。原94/450通过没有覆盖此窗，不能据此宣布该片验收。

此次只改4个后端源模块与2个测试文件，保持单写入者，两个既有代理未写文件。没有实施 Windows cache，也没有改 UI、合同镜像、依赖、CI或安全权限。修复采用后端不可变 RunScope(runId/projectId/generation)：open（含已有/新建/只读工程）、_register 与 close 推进工程代次，A→B→A也不能复活旧请求。

- api.py：run_store 在workspace模式只取得scope，删除冗余的未受保护get；状态、源码、日志、产物清单和PNG由 read_run 在工作线程前后核scope，并在 await 恢复后、交付前再次核scope。旧工程的失败响应也重新核代次，不能返回旧错误内容。没有workspace的独立RunService测试入口保留原get存在性检查。
- SSE：每批读取与最终事件补尾走同一scope，批读取后及每条yield/heartbeat前核代次；失效后关闭流，不继续交付剩余批。HTTP头已发出时流结束，不伪称仍可改成404。
- 历史接口：只允许当前工程，返回成功或错误前均核捕获的代次；活动ID接口仍用于Main全局退出确认，不借此暴露旧Run配置。
- 取消：本地在workspace提交守卫内进入RunService/本地supervisor；SSH先取得真实coordinator锁，再进入workspace scope守卫并持久提交。释放core/workspace锁后才发布状态；不在持workspace锁时等待core。工程切换若先赢，旧取消返回404且不写取消证明；取消若先持守卫提交，随后工程切换不能撤销已合法提交的动作。此为提交线性化边界，不承诺取消此前已提交的请求。

独审另外实复现旧历史路由切B仍200返回A配置，以及run_store冗余get抛旧工程错误的路径；均纳入同一P2修复。独立审查最终确认该P2关闭，未发现新增锁反转。检查涵盖WS→RS本地路径、core→WS远端路径、读取释放内部锁后再核scope，以及清理先释放WS再等待后台线程。

实际命令/最终结果（工作目录 `/workspace/Easy-AI`，沿用既有 UV/XDG workspace缓存）：

| 命令 | 结果与精确范围 |
| --- | --- |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_run_scope_race.py -x`（旧代码） | **FAIL**，第一项即复现上述检查后切换仍取消A；保留为缺陷证据，不算修后结果 |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_run_scope_race.py services/backend/tests/test_remote_run_api.py services/backend/tests/test_local_api.py services/backend/tests/test_local_workspace.py services/backend/tests/test_project_editing.py services/backend/tests/test_ssh_run_coordinator.py` | **84 PASS**，12.07秒；修复主路径后的受影响窗口，未重复旧450/94矩阵 |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_run_scope_race.py`（最终含错误门） | **25 PASS**，2.76秒；6个检查后切换、10个worker返回后交付（含ABA）、2个SSE批读取后切换/ABA、1个历史、1个本地提交边界、1个ASGI首事件交付后切工程丢弃余批、4个旧错误窗口。仅测试自有文件，无训练进程/SSH/socket |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_run_scope_race.py services/backend/tests/test_remote_run_api.py -k 'scope or delivery or sse or history'` | **23 PASS /4 deselected**，2.70秒；包含新SSH取消提交屏障：断言真实core锁已持、workspace锁未持，切换工程能完成，恢复后404、checkpoint未取消、无owner exec。还包含一个既有binding scope用例，与其他结果重合不加总 |
| 独审定向窗口 | 首次scope窗口23 PASS/4 deselected（2.69秒）；错误门补齐后独跑4 PASS/21 deselected（0.58秒），明确回复“该scope P2已关闭”。未运行大矩阵 |
| `services/backend/.venv/bin/ruff check services/backend/src services/backend/tests/test_run_scope_race.py services/backend/tests/test_remote_run_api.py`、6个修改Python文件 `ruff format --check`、`services/backend/.venv/bin/mypy services/backend/src` | PASS；mypy44源文件。中途缺Event import和unused test import修正后通过，没有降低规则 |
| `node scripts/python-task.mjs build`、`node scripts/test-frozen-ssh.mjs` | PASS；最新PyInstaller包、本机鉴权/严格DTO/脱敏拒绝/EOF退出0。不是原生Windows或真实SSH验收 |
| `git diff --check`、原件hash | PASS；README、原规格和116185字节计划hash仍与前轮完全一致，无原件覆盖 |

本轮 NOT RUN：旧完整450后端/94前端矩阵、无改动前端/合同再生成、真实Electron/E2E、Windows、真实SSH/SFTP、数据上传、torch/训练和硬件。未请求/重试 Actions API，旧desktop CI具体失败步骤/根因仍未知，新提交CI状态未知。无新拒绝或不明执行；没有main写入、强推、部署、Release、PR、付费或凭据变更。

Windows缺口保持：remote_artifacts顶层fcntl、remote_cache明确POSIX、coordinator/Bundle对本地dir_fd/O_NOFOLLOW/目录fsync的直接依赖不能只换flock解决。最小设计是安全本地目录/文件/身份/内核锁/发布接口分层，保留POSIX门，再实现原生Windows handle/reparse/ACL/身份与发布语义；Linux可做接口与拒绝合同测试，Windows原生锁、NTFS ACL/junction、替换竞态、崩溃耐久与冻结桌面必须实际验证。修复scope后再按父级审查结论接续，**M5整体、A、B继续未验收**。

## 2026-10-18 — M5 本地 SSH 存储接口与受支持平台最小切片

代码提交 `e3b9f454fbb6c807b362edcb8daf5661f149281f`，父提交 `ee3671686e88034e24698381e09e05dc3baa8932`。开始前父级原审查者已对 ee36716 源码独立复核，确认原 scope P2 关闭且未见残留明确P1/P2；该确认是源码审查，不把旧450/94、主路径84与最终专项25相加。进入本轮时工作区干净；同一环境单写入者，既有代理只读审查。

本轮实现的是 **平台存储接口/早期能力拒绝，不是 Windows SSH backend**。新增 LocalDirectory/LocalWriterLock 合同与现有 POSIX 实现，集中目录身份、单文件名组件、受保护普通文件、永久 artifact writer lock、非覆盖发布、替换、文件与目录 fsync。Bundle 冻结、coordinator缓存及artifact cache都消费目录接口，移除这些调用者中的直接dir_fd/O_NOFOLLOW/fsync和artifact模块顶层fcntl导入；fcntl只在POSIX writer_lock建立时加载。**coordinator仍使用既有 ProjectLock 作为owner锁**，不冒称所有锁都已迁移至LocalWriterLock。远端Linux supervisor和SFTP远端路径检查保持原协议，不把客户端本地路径规则施加给远端。

POSIX门保持/加强：逐级目录FD、UID与no022、NOFOLLOW/NONBLOCK、普通文件、handle/path身份复核、拒绝父目录替换；固定文件名拒绝绝对路径/drive/冒号/分隔符/点组件/控制字符。非覆盖发布使用link，不覆盖已有目标；可替换记录先验证源与现有目标，拒绝symlink/非普通文件。临时文件先flush+文件fsync，发布后目录fsync；flush失败不返回成功收据，可能已发布的状态保持不确定，不能据此重试start。永久kernel writer锁不unlink、不换inode，关闭释放内核所有权。不会chmod修复已有不安全目录/文件。

require_local_cache 在创建远端binding和prepare前运行，未实现的客户端平台返回 `REMOTE_CACHE_PLATFORM_UNVERIFIED`，不落新Run/目录、不进行SDK stage/exec。桌面对该固定错误说明“当前客户端平台尚未支持安全的SSH本地存储”，不误导用户重试环境/数据。未实现Windows原生文件/ACL/锁或持久化，没有用Path.resolve、chmod、getattr忽略缺失flags等弱降级替代安全门。POSIX能力分支也不是macOS产品支持声明。

只读独审确认无明确P1/P2，独跑存储21项与API拒绝1项共22 PASS，指出上述ProjectLock迁移边界，已据实记录。作者另外验证marker目录flush失败后恢复为unknown、只inspect、不再次stage/start；这是POSIX接口故障注入，不是断电耐久或Windows验证。

实际命令（`/workspace/Easy-AI`，pnpm Python子任务沿用既有workspace UV/XDG缓存）：

| 命令 | 最终结果与范围 |
| --- | --- |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_ssh_run_coordinator.py services/backend/tests/test_owner_transport.py services/backend/tests/test_remote_artifacts.py services/backend/tests/test_remote_run_api.py` | **121 PASS**，14.04秒；迁移后受影响的协调器/adapter/产物/API窗口。后续仅增加platform拒绝及marker故障用例，分别定向补测，不重复整个窗口刷数 |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_local_ssh_storage.py services/backend/tests/test_remote_run_api.py -k 'storage or unverified or native_lock'` | **22 PASS/6 deselected**，0.87秒；21存储合同+1API早期拒绝。实际POSIX文件/FIFO/symlink/权限/目录替换、两个有界标准库子进程的kernel锁排他与释放、永久inode、不覆盖和fsync顺序/失败；新解释器证明Easy-AI模块不在导入时直接加载fcntl。Python标准库/第三方在POSIX上的条件import不等于Windows依赖证明 |
| 上述API拒绝测试 | 仅注入“nt能力不可用”的provider，不模拟Windows文件系统。断言无新增binding、Run、目录、channel调用、stage/exec，不能称Windows实际通过。POSIX专属fixture在非POSIX明确跳过，不为Windows通过数 |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_ssh_run_coordinator.py -k 'storage_marker_flush_failure or crash_after_start_marker'` | **2 PASS/37 deselected**，0.12秒；新目录flush收据失败+原marker/crash回归。远端假端点没有实际进程/SSH，start总0；恢复unknown只inspect |
| `pnpm exec vitest run apps/desktop/src/AuthenticatedPanel.test.mts` | **8 PASS**，1.11秒；包含新增平台拒绝说明/清binding/恢复控件用例。不是旧94前端矩阵重跑 |
| `pnpm check` | PASS；mypy44源文件、ruff/格式、TS、合同与真实Blockly fixtures漂移。没有新DTO/依赖/lockfile/CI权限变更 |
| `pnpm build`、`node scripts/test-frozen-ssh.mjs` | PASS；最新桌面Vite与后端PyInstaller；既有大chunk提示，冻结HTTP鉴权/DTO/拒绝和EOF退出0。没有启动实际Electron或有效SSH |
| `git diff --check`、三原件hash | PASS；README、原v0.0.0、116185字节原计划均未变，hash与前轮一致 |

中途FAIL：首次新解释器测试一律阻止fcntl，误伤Linux标准库subprocess的条件import；改为精确阻止Easy-AI模块在平台门前直接import，随后通过。另有unused test import已删除。没有为通过而取消文件安全校验或允许Windows降级。

本轮 **NOT RUN**：旧450/94全矩阵、scope25/84重复运行、原生Windows、实际Electron/E2E、真实SSH/SFTP/上传、数据/torch/训练/硬件、断电或目标服务器崩溃耐久。旧desktop CI失败根因仍未知，新提交CI未知，未重试被拒Actions或绕路；无新工具拒绝/不明执行。没有main写入、强推、发布、PR、付费/凭据/权限变更。

下一项是实现并原生验证Windows LocalDirectory backend，包括受持handle的目录身份与reparse拒绝、owner/DACL、native kernel锁、源/目标保护发布、崩溃恢复收据和PyInstaller资源/ABI；既有ProjectLock也须在该平台的同一保护边界内实测。Linux只能继续做调用合同、故障门与POSIX回归；不能将当前能力注入或Windows跳过项算作原生支持。**Windows SSH仍不可用，M5整体、A、B均未验收。**

## 2026-10-18 — M5 Windows 原生存储实现与待执行的 NTFS 验证门

代码提交 `56a8d26f55c4bd1b00e0c24732117137d50debba`，父提交 `a4609dc60060d13e34f751fd2dd4615d2e86678d`。开始/提交前核对开发分支 `codex/demo-v0.0.0`、origin `https://github.com/T1doo/Easy-AI.git`；远端开发分支仍为父提交，远端 main 仍为计划基线 `5323f86232529efcfb52131168ad049f01b219f3`。保留前轮文件，只接续既有 WIP；单写入者，既有代理只读审查。本切片不是 M5 或 Windows 支持验收。

新增真正调用 Windows API 的实验后端 `security/windows_store.py`，不是 POSIX 别名：显式 x64/Windows 固定宽度 ABI；读取当前 token SID，不提权；仅本地固定 NTFS 且有 persistent ACL；从卷根逐组件持有目录 handle，Native RootDirectory 相对打开，拒绝 reparse/junction、非普通文件、delete pending、不同卷和文件身份变化。GetSecurityInfo 检查 owner/DACL，拒绝 NULL/未知 ACE、不受信主体的危险写入/替换权限，既有不兼容 ACL 直接拒绝，不修 ACL 或 chmod。Windows 单组件名称拒绝路径逃逸、ADS、DOS 设备别名及尾点/空格。当前保守信任边界仅当前 SID、SYSTEM 和 Administrators；真实系统目录 owner/ACL 是否满足也必须由原生执行给出证据，不能假定所有 Windows 安装均兼容。

文件 HANDLE→CRT fd 在每个结果上有唯一所有者，非继承，转换前失败 CloseHandle、转换后失败只关 CRT fd。Native 发布分别使用不覆盖 hard-link 与 replace rename；检查源/已有目标，文件 flush→原生发布→文件 flush→目录 FlushFileBuffers，返回值与 IO_STATUS_BLOCK 都必须明确成功。未确认、pending 或 flush 失败不发成功收据、不回退路径操作。**真实 NTFS 目录 FlushFileBuffers 能否成立尚未执行；若失败就是能力阻塞，不吞错或以文件刷盘代替目录收据。**

永久 LockFileEx 内核锁不 unlink，不靠 PID/过期文件恢复。Windows owner lock 先完整写入并发布与既有 ProjectLock 相同 MAGIC，再在锁内读取；旧空锁拒绝。LocalDirectory 增加 owner_lock，POSIX 分支继续委托原 ProjectLock；coordinator 消费同一目录的 owner lock。EventJournal 新增可选借用 LocalDirectory，使用该目录打开/身份核验/内核 owner lock/刷盘，mutex 与 writer lock 下 seek EOF 后追加；coordinator 自建 journal 已接入。旧无 directory 的本地 API 路径保持既有实现。

**生产 factory/require_local_cache 仍只允许 POSIX，Windows 默认拒绝完全保留。** 实验 backend 仅测试显式注入，未给用户添加绕过开关。检查 RunService 后确认仍有前置缺口：root.resolve、`.runs.lock` 的旧 ProjectLock、catalog 的 ProjectService.atomic_write，以及 RunService 注入的 application EventJournal 尚未使用受保护 WindowsDirectory。不能仅因私有 coordinator journal 已迁移便开启 Windows；这些路径的保护/发布、原生 ACL/身份替换竞态、崩溃耐久、冻结 ABI 都仍待完成。Linux 注入与字节布局断言不等于实际 Windows 调用验证。

新增六项 Windows 专项测试：真实 NTFS 文件身份/非覆盖与替换/CRT 所有权/目录刷盘、受保护 journal 重开与排他、legacy marker 拒绝、有限标准库子进程跨进程锁排他及 kill 后释放、测试自有 junction 拒绝、真实本地缓存配合原有合成端点的 lost-ACK 恢复只 inspect 不二次 start。无真实 SSH/网络/训练；junction 使用固定 mklink /J 和受限测试路径，不启用 symlink 权限、不改 ACL。Linux 明确 skip，Windows 上 ACL/卷/flush 不成立则 FAIL，不转换为 skip。该测试集还没有覆盖全部原生替换/断电/ACL攻击矩阵。

既有 Windows CI job 新增 native readiness（3分钟）、PyInstaller（4分钟）、冻结 HTTP/资源 smoke（2分钟），总 job 仍15分钟、contents:read、未加 runner/权限/付费。native gate 与冻结构建在非取消时分别尝试；smoke 只在冻结构建成功后执行，即使 native gate FAIL 也不把独立冻结检查隐藏。新增 hidden-import 确保实验模块进入冻结包，**本机 Linux 包含该模块不证明 WinDLL/CRT 原生冻结 ABI 已通过**。push 仅触发现有授权的有界免费 CI；本机没有查询或重试被拒 Actions API，结果未知。

独审发现并实修：根 handle 校验失败曾泄漏；owner lock 错 MAGIC 后重复路径核验可能阻止 fd 清理；NtSetInformationFile 返回0但 IOSB失败曾可能误报成功。现在根统一 `_keep`，锁清理直接关闭 owned fd，所有 Native 完成收据严格核双方。独审独跑39合同 PASS，确认此前P2关闭、未发现新的明确P1/P2。新增 native 恢复测试的错误预期也经独审 POSIX复现后纠正：新 lease inspect 正常应恢复 RUNNING/acknowledged，start/stage 保持各1；没有人为制造二次失败来满足错误断言。审查不等于 Windows 执行。

实际命令（工作目录 `/workspace/Easy-AI`；pnpm Python子任务设置 `UV_CACHE_DIR=/workspace/.uv-cache UV_PYTHON_INSTALL_DIR=/workspace/.python XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache`）：

| 命令 | 最终结果与范围 |
| --- | --- |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_windows_storage_contract.py services/backend/tests/test_windows_native_store.py services/backend/tests/test_event_journal.py services/backend/tests/test_ssh_run_coordinator.py services/backend/tests/test_remote_artifacts.py services/backend/tests/test_remote_run_api.py` | **155 PASS /6 SKIP**，10.98秒；39纯策略/ABI/调用故障与所有权合同，加受影响 journal/coordinator/artifact/API 回归。6项全部是 Windows 原生用例，在 Linux 未执行，不能算支持通过 |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_windows_storage_contract.py services/backend/tests/test_windows_native_store.py`（最终小修后） | **39 PASS /6 SKIP**，0.09秒，与上述窗口重合，不加总；含返回0但 IOSB failed/pending 的8分支和错MAGIC清理fd回归。Linux实际文件仅证明资源所有权，不是 Windows 内核锁 |
| `pnpm check` | **PASS**；严格 mypy45源文件、ruff/格式、TS、合同/Blockly fixture漂移与Prettier。未改DTO/依赖/lockfile/UI |
| `node scripts/python-task.mjs build`、`node scripts/test-frozen-ssh.mjs` | **PASS**；Linux PyInstaller明确分析 experimental hidden import；冻结 HTTP 鉴权/严格DTO/脱敏拒绝/资源逐字比对/EOF退出0，无有效远端操作 |
| `git diff --check`、三原件 byte/hash | **PASS**；计划116185字节 SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原规格 `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`；README `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`。均未覆盖 |

中途FAIL：首次 pnpm check 未带既有workspace缓存，uv尝试只读默认目录而失败；设置上述缓存后严格mypy发现动态 CRT 返回 Any，显式int转换后完整check通过。直接从仓库根执行mypy未加载后端strict配置的早先PASS不作为strict证据。未放宽规则或安全门。

**NOT RUN / 阻塞状态**：当前执行器是 Linux；原生 Windows NTFS/ACL/多进程/异常退出/junction/冻结 ABI 等待新增 Windows CI 实际执行，结果 **pending/unknown**，不是被拒后绕路。旧desktop CI具体失败步骤/根因仍未知；原 Actions Forbidden 与 Electron sandbox 拒绝均未重试、未绕过。真实 SSH/SFTP/上传/数据/torch/训练/硬件、实际 Electron/E2E、断电耐久未运行；没有安装训练环境或用合成结果冒充训练。旧450/94完整矩阵和无改动桌面构建未重复。

下一项：先取得新增 Windows CI 的实际可读步骤证据并处理原生失败；同时将 RunService 全局锁/catalog/application journal 纳入同一 Windows 保护边界并补齐替换/崩溃测试。在这些证据具备前默认门继续关闭。无 main 写入、强推、部署、Release、PR、Feng5u写入或新权限/凭据/付费；**M5整体、A、B均未验收，不能宣称 demo v0.0.0 已完成。**

## 2026-10-18 — M5 RunService 持久化与共享 journal 最小端到端保护片

代码提交 `99035e670bd529db8b027835fc676799772f05e2`，父提交 `5a34286f15641ef5923209f2fb2303c564f22773`。父级对前片仅有限接受默认关闭的实验后端，明确155 PASS/6 SKIP不等于Windows验收。本轮在指定执行器实际成功执行pwd/Git/读取/测试；开始HEAD及远端开发分支均为父提交、工作区干净，远端main仍为计划基线 `5323f86232529efcfb52131168ad049f01b219f3`，没有声称一个仍断开的环境已恢复。单写入者，既有独审代理只读、未写仓库。

RunService 现在在 POSIX 默认持有 LocalDirectory 根目录，通过同一后端取得 `.runs.lock` owner lock；catalog 读取使用受保护 fd、身份及前后metadata复核和16MiB限额，拒绝symlink/FIFO/被替换记录。catalog 使用新临时文件→文件flush→后端publish replace→目录flush，不再调用 ProjectService.atomic_write。发布/刷盘抛错后进入 `RUN_STORE_WRITE_UNCERTAIN`，拒绝继续get/persist/core而不把内存状态当已提交；关闭再重开才能从实际磁盘事实恢复。文件已replace但目录flush失败时不谎称回滚，重开也不能把STARTING降回可重启CREATED。

每个run及其logs目录由RunService持有，EventJournal借用logs目录，不关闭借用者；同一root/owner lock/目录 provider 传入RemoteRuns.core→SshRunCoordinator。目录缓存与journal初始化在RS RLock下串行，不重复采纳句柄。关闭先确认远端worker/transport静止，再关core的自有目录，随后共享journal及writer lock、全局owner lock、logs/run/root目录；真实I/O仍busy或SDK关闭未确认时继续保留owner锁。若本地supervisor清理未确认，同样不抢先释放持久化资源。

Windows普通本地应用启动仍沿用既有路径模式，**没有把POSIX能力门粗暴接到全部启动**。内部可显式注入WindowsDirectory用于原生专项；生产factory与Windows SSH gate未开启，未具备受保护store的RemoteRuns.core明确返回 `REMOTE_CACHE_PLATFORM_UNVERIFIED`，没有远程弱降级。新增一项真实Windows RunService专项覆盖catalog/shared journal/排他/取消未启动run/重开，但此执行器为Linux，该项与原6项均明确SKIP。

独审实际复现了两类准备写入问题，均随本轮修复：最初prepare在检查后仍path-based导出，替换runs根为symlink时outside曾写13文件；中途改为held导出后，导出结束关闭run句柄到重新采纳同名run之间，普通空目录替换仍能被采纳并写6文件。最终LocalDirectory增加独占 `new_child`，RunService统一 `_export_bundle` 从独占claim起立即缓存并持续持有同一run目录，编译导出只借用该对象、只关闭自有code子目录。local/remote prepare均经该入口，bundle、新run子目录、snapshot/config/identity初始非覆盖发布及metrics/artifact派生视图写入都走受保护目录；替换目录不接收任何新文件。CLI独立导出保留原来显式新目录路径行为，不冒称本轮保护所有任意用户导出目标。

独审还复现recover已开core/shared journal后替换根再抛错：旧cleanup会再写disconnected缓存失败，跳过RS清理、泄漏锁/journal并盖掉原错。现在内部 `retire_transport` 关闭路径不依赖落盘；public disconnect仍保留原持久行为。retire仍执行真实SDK close和quiescent验证，core.close仍先取得busy并核retiring.ready，RemoteRuns仍有界join，不以“忽略所有异常”释放未知I/O owner。原夹具复核保留原始OSError且core/journal/runs锁/目录全部关闭，无退休线程未捕异常；初始化P2确认关闭。最终run-claim P2独立6 PASS（本地4窗口、remote2窗口），审查确认关闭且未发现剩余明确P1/P2或新增锁反转；不将审查结论扩大为原生Windows支持。

实际命令（`/workspace/Easy-AI`；pnpm Python子任务沿用 `UV_CACHE_DIR=/workspace/.uv-cache UV_PYTHON_INSTALL_DIR=/workspace/.python XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache`）：

| 命令 | 最终结果与范围 |
| --- | --- |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_run_storage.py services/backend/tests/test_run_service.py services/backend/tests/test_remote_run_api.py services/backend/tests/test_run_scope_race.py services/backend/tests/test_event_journal.py services/backend/tests/test_local_workspace.py services/backend/tests/test_ssh_run_coordinator.py services/backend/tests/test_local_ssh_storage.py services/backend/tests/test_windows_storage_contract.py services/backend/tests/test_windows_native_store.py -x` | **202 PASS /7 SKIP**，14.98秒；最终源码受影响持久化/API/scope/owner/ABI窗口，7项均需原生Windows，在Linux未运行。不是旧完整450/94重跑 |
| 上述 `test_run_storage.py` 20项 | 真实POSIX root/logs/run普通目录与symlink替换、catalog file-flush/publish/replace后目录fsync失败及poison、初始化JSON/symlink/FIFO拒绝、journal open失败资源清理、全局排他、借用顺序、重开STARTING不重启，以及“nt能力选择”只注入的本地启动/远程拒绝合同。后者不是Windows文件系统模拟；与202重合，不加总 |
| 上述remote API新专项 | 合同/正式prepare→真实受保护root/catalog/shared journal/coordinator组合；合成Owner消费start丢ACK后持久unknown，重开无认证/无inspect/无start，显式新lease只inspect恢复且stage/start各1。另有remote root symlink/run普通目录替换、recover已开core后换根清理。无真实SSH/socket/训练；其他既有API用例的自有标准库child仍不是MNIST效果 |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_compilation.py services/backend/tests/test_portable_owner.py` | **47 PASS**，5.97秒；补充编译bundle/CLI新目标非覆盖及portable owner资源回归，真实标准库测试进程，无torch/训练。与独审/其他窗口不合并报总通过数 |
| `pnpm check` | **PASS**；strict mypy45源文件、ruff/格式、TS、合同/实际Blockly fixture漂移、Prettier。无DTO/依赖/lockfile/UI/CI权限变动 |
| `node scripts/python-task.mjs build`、`node scripts/test-frozen-ssh.mjs` | **PASS**；Linux PyInstaller与冻结HTTP鉴权/严格DTO/脱敏拒绝/portable资源逐字/EOF退出0，无有效远端操作，不能称Windows冻结ABI验证 |
| `git diff --check`、原件byte/hash | **PASS**；计划116185字节，SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原规格 `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`；README `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`；均保留原样 |

中途FAIL如实记录：原平台门测试把只有name的os替身保留到fixture teardown，新持有根目录close因此AttributeError；改为只在拒绝请求期间使用monkeypatch context，原无binding/目录/Run/stage/exec断言均保留。目录创建改为受保护句柄后，测试记录了创建和journal打开两个logs handle，原“恰好1个”断言改为验证所有handle已关闭；持续claim后，journal-open故障注入点从旧child移到实际new_child，仍要求抛原错及全部释放。独审上述实际路径/清理缺陷经源码修复和原复现实证关闭，没有跳过安全测试或降低成功门。

CI新事实由父级提供：前版 `a4609dc60060d13e34f751fd2dd4615d2e86678d` 的 [run39135362749](https://github.com/T1doo/Easy-AI/actions/runs/39135362749) 于14:19:48 UTC结束，check success、desktop failed；失败步骤与根因未知。当前/前片新增Windows native CI结果仍unknown，未向被拒Actions端点重试或换路。没有把Linux本机PASS或WindowsSKIP冒充CI成功。

剩余缺口/NOT RUN：Windows实际NTFS目录flush、真实owner/DACL及替换竞态、跨进程/异常退出和冻结ABI待有界Windows CI原生证据；当前内部native RunService专项未执行。Windows完整SSH链仍受默认门拒绝，RemoteBundle/SftpArtifactSync等默认factory的原生贯通及目标兼容还未验收，既有Windows本地路径模式不是本轮安全后端支持声明。跨应用离线文件篡改、真实断电耐久、真实SSH/SFTP/上传/环境/数据/torch/训练/硬件、实际Electron/E2E未运行；不动用户PC，不安装训练环境、不下载数据、不重试旧sandbox拒绝。无main写入、强推、PR、部署、Release、Feng5u写入、新权限/凭据/费用。

下一项：由父级独审此代码片并取得可读的Windows实际步骤证据，再推进默认关闭的原生factory全链及剩余M5合同；未具备证据前不开放Windows SSH。**M5整体、A、B继续未验收。**

## 2026-10-18 — 父级精准 P2：POSIX new_child 的 sync 后首次采纳

代码提交 `7a894ae3191e691da881924918ea802ddb6a7fb1`，父提交 `5828421927ad625662ab0fa7e89af2e1f0bdd6ab`。保持前片其他代码冻结，仅改remote_cache.new_child并新增test_directory_claim.py。父级最终裁定本片仅保留这一新增P2：旧顺序mkdir成功→父目录sync→按名称首次打开child，sync期间把新run目录rename走并放回同名0700普通空目录，会采纳替代目录。owner_lock的path-based ProjectLock为沿用旧实现，本轮未修改，不将其包装为新增回归或扩大修复范围。

先在父提交真实执行可控Event闩锁：工作线程mkdir后停在父sync，主线程确认子inode变化，rename保留原目录、原名建立普通空目录，再放行sync。`services/backend/.venv/bin/pytest -q services/backend/tests/test_directory_claim.py` **2 FAIL，0.11秒**，直接调用返回了替代目录；真实RunService.prepare也返回成功，替代目录已有ENVIRONMENT.md、README.md、bundle.json、code、logs、snapshot、run-config.json及派生视图等。测试无SSH/训练/系统权限动作，仅自有tmp文件；源码推导与这次实际复现明确区分。

修复为mkdir后立即取得child句柄，**sync前持有该身份**；sync后核同一child及parent，失败关闭child，不在sync收据后重新按名首次采纳。原两项回归 **2 PASS，0.07秒**，要求替代目录为空且无ledger/supervisor。独审独跑同两项 **2 PASS，0.07秒**，确认该sync窗口P2关闭，未修改仓库。Windows `_child` 已持创建handle跨sync并比对新打开对象identity，本轮仅源码核对，未改Windows、未执行原生API。POSIX mkdir本身不返回handle；本次不宣称mkdir/open是原子系统调用，或能防御同UID任意删除替换全部状态，既有平台和威胁边界不扩大。

实际后续命令（`/workspace/Easy-AI`）：

| 命令 | 结果与范围 |
| --- | --- |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_directory_claim.py services/backend/tests/test_local_ssh_storage.py services/backend/tests/test_run_storage.py services/backend/tests/test_run_service.py` | **55 PASS**，2.09秒；含上述2项，不另加总，未重跑202/450/94矩阵 |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_remote_run_api.py -k 'root_swap or shared_protected or initialization_failure'` | **4 PASS /7 deselected**，0.87秒；真实持久化配合合成端点，不是原生Windows/真实SSH验收 |
| `node scripts/python-task.mjs check` | **PASS**；strict mypy45源文件及后端/runtime ruff与格式。沿用workspace UV/XDG缓存，无安装 |
| `node scripts/python-task.mjs build`、`node scripts/test-frozen-ssh.mjs` | **PASS**；Linux冻结后端与HTTP/资源/EOF退出0，无有效远端操作。构建日志在执行器自有 `/tmp/easyai-directory-claim-build.log`，不提交二进制/运行数据 |
| `git diff --check`、原计划hash | **PASS**；原计划仍为116185字节、SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`，原件不变 |

本轮没有新CI证据。现有获准记录仍仅能确认前版a4609dc/run39135362749的check success、desktop failed，具体失败步骤/根因未知；新native/desktop CI未知，未查询被拒Actions端点或换路。原生Windows、真实Electron、真实SSH/数据/训练均NOT RUN；Windows SSH gate保持关闭，A/B不变。没有main写入、强推、PR、发布、费用/凭据/安全权限变化。

### 下一功能只读定位（未实施，待父级独审）

重核原计划第2.1、12.3.1、13.1、15.2、M3.3/3.4、M5.1及19.3/19.4后，建议下一最小功能片回到 **M5.1非敏感连接概要保存/选择及稳定targetId**，不继续泛化安全包装。现有ConnectionPanel的host/port、AuthenticatedPanel的username只是React会话状态；LocalWorkspace.bind_remote仍每次 `target_id=str(uuid4())`，没有第15.2要求的GET/POST/PATCH connections持久摘要。身份确认→密码会话→只读环境probe→绑定→受控owner执行/重连的代码已存在，前轮有离线组合证据，但不能用其替代至少一次真实SSH。

建议切片行为：用户保存服务器别名/host/port/username等非敏感概要→重开应用仍能选择同一targetId→选择只填配置，不连接/认证/执行→仍显式核指纹、输入会话密码和probe→运行绑定引用该稳定target。复用现有存储与manager，不新增通用命令/第二套执行器；活动运行引用的endpoint身份不可原地改写，旧运行快照不跟随修改。密码/口令/私钥内容不持久化，不开放“记住密码”；私钥认证本身仍是M5.1另一未完成项，不用此小片冒称全M5.1完成。

可立即开发的本地原功能也有两项明确缺口：本机环境检查目前只在start中执行，界面“检查与编译”只做编译；完整Bundle在后端可导出，但桌面“导出当前工程”仅导出JSON。这些可在后续独立小片交付，不能据此跳过M3真实数据人工闭环或提前进入M6/M7发布。CIFAR10本机preflight仍明确不支持，属于D10/M6.1尚待补齐的真实运行缺口。

验收条件分开：已有M3 CPU/真实参数更新及Main链证据使用明确批准的32/16合成IDX，只证明真实执行，不是真MNIST效果；门A仍需老师已准备真实MNIST的获准绝对路径及本机CPU人工小样本运行/产物/映射证据，不擅自下载或重跑训练。M5实际验收另需获准Linux目标、独立指纹、会话认证方式、现有解释器/数据及专用上传/执行/取消范围。Windows native/desktop是客户端平台与包的独立验证条件，不能用上述Linux/mock结果代替，也不能把它们全部混称为“等真实数据”。这些动作本轮未执行，未新获授权，不动个人电脑或教师共享环境。

## 2026-10-18 — A 用户功能：运行产物/错误定位到旧运行的只读 Blockly 快照

代码提交 `662647d1d908fcdfc9355259f8dff80563b7cc41`，父提交 `a4e48f4b925c332fe6ced02bd6ffb49277b63d3e`。父级先复核关闭前片精准sync P2（55包含2，未相加），随后优先要求可演示A。开始工作区干净、指定执行器命令可用；提交前远端开发分支仍等于父提交，main仍为 `5323f86232529efcfb52131168ad049f01b219f3`。本轮单写入者，独审只读，无后端/合同/依赖/CI变更，不扩展M5配置功能。

先只读核实A条件：仅扫描已授权项目与独立训练根、排除venv/wheels/cache等、限制深度和目录数量；项目扫描173目录、训练根960目录，未触发1200目录上限。只找到integration-001～005的32训练/16测试合成IDX，读取header确认2051/2049与28×28；未发现可确认的真实MNIST原件，不把有限扫描说成全机器绝对不存在。既有训练Python和torch2.10.0+cpu/torchvision0.25.0+cpu/Matplotlib3.10.8元数据仍在，未导入这些包、未运行训练。integration-005/Main-integration-001/cancel回执仍可读，明确标记合成数据、原生picker注入、无Electron窗口。当前DISPLAY/Wayland未设置，X11 socket目录不存在，Xvfb/xvfb-run不存在；只核条件，不启动/安装桌面或重试原sandbox拒绝。

发现并交付的是独立A代码缺口，对应计划2.1、10.3、M3.4和M4.3/4.4：旧实现产物“来源”与runtime_error按钮只设置ID并高亮旧代码，没有显示该运行快照里的积木。现在这些入口以及旧代码行点击均打开独立的只读Blockly快照，按快照和旧source-map定位数据/模型/训练标签页与积木，同步高亮旧代码；同一来源重复点击也会重新导航到正确页。提供“关闭快照，返回运行结果”，卸载自有workspace/监听器/observer，不修改或保存当前工程。

新增RunSnapshot组件及纯capture/lookup：克隆旧snapshot、复制旧map，只遍历实际Blockly inputs.block/shadow与next结构建立旧ID→页索引，完全不接收当前App project。旧代码缺span或span超出旧代码范围时可以显示快照块但明确不猜代码行；ID不存在、重复ID、页映射冲突、旧schema/library不支持或revision不一致均明确提示，不用当前同ID替代。当前工程改名、删除、重建同ID块不会改变旧视图。未知/不支持版本保留旧代码，不强行加载Blockly。

复用现有ProjectEditor/WorkspaceManager，只读时注册/改名/删除/Undo均拒绝；新视图忽略变更回调。两编辑器useId生成独立tabpanel/aria-controls，避免旧快照和当前工程DOM ID碰撞。只读定位执行workspace highlight/center，不调用BlockSvg.select，避免Blockly全局selected状态影响当前工程。ProjectEditor及Monaco继续按需加载，按React best-practices复核生命周期、依赖、可访问性和只读交互，没有为技能引入新UI框架。

RunDashboard按runId建立独立内部组件；旧source/image/event晚回调不能进入新运行。source响应须匹配该run的工程ID/revision/programHash/codeHash才载入副本。独审发现get/cancel/resume返回Run仍可能被错DTO回填，现用共同7字段身份核验后才setRun/onRunUpdate；仅有React key不足以拒绝当前请求返回错对象。定向回归还实测resume catch的错误被重读effect清空，已移除该effect的动作错误清空，保留错误跨readGeneration；合法owned重读允许，foreign通知禁止。独审最终17/17 PASS，确认该P2及错误吞没关闭，未发现本片其他明确P1/P2；不是父级或真实桌面完整验收。

实际命令（`/workspace/Easy-AI`，pnpm Python静态子任务沿用既有workspace UV/XDG缓存）：

| 命令 | 结果与精确范围 |
| --- | --- |
| `pnpm exec vitest run apps/desktop/src/RunSnapshot.test.mts apps/desktop/src/App.test.mts apps/desktop/src/runEvents.test.mts packages/block-library/workspace-manager.test.mts` | **38 PASS**，2.27秒；包含新增17项，不把独审17或先前13再加总。当前改名/删除/重建同ID，三标签页及重复导航，旧版本/revision/缺span/错页/超界map，只读操作与关闭，artifact/error/code入口，切run晚source/image/event，source错hash及get/cancel/resume错DTO |
| 新17项使用的真实/替代边界 | 真实React DOM、真实ProjectEditor/WorkspaceManager及真实Blockly序列化加载，只有SVG宿主绘制使用headless handles；Monaco在JSDOM走真实安全只读fallback。非真实Electron/原生选择器/SVG浏览器绘制验收。3行“old…code”只作UI映射夹具，无模拟训练指标/生产mock |
| `pnpm exec vitest run apps/desktop/src/monaco-controller.test.mts apps/desktop/src/monaco-mapping.test.mts` | **6 PASS**，0.239秒；旧图多span/最窄语义源/只读controller/释放回归；不与上项或历史全套刷总数 |
| `pnpm check` | **PASS**；TS/strict mypy45源文件/ruff/格式/合同及真实Blockly fixture漂移/Prettier。后端未改，无全后端矩阵重跑 |
| `pnpm --filter @easyai/desktop build` | **PASS**；Electron Main TS及Vite静态assets，保留既有>500KB chunk提示；未启动Electron。后端未改，不重复PyInstaller/冻结HTTP窗口 |
| `git diff --check`、三原件byte/hash | **PASS**；计划116185字节、SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原规格 `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`；README `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`；均未覆盖 |

中途FAIL保留：首轮TS指出readonly span数组不能传给mutable props，CodeView的只读spans输入改为readonly类型，未复制另一套合同。首轮组件10PASS/3FAIL因测试误写model.class，实际真实fixture是model.define，纠正类型断言后13PASS，名称/当前工程字节不变等断言保留。新增DTO测试37PASS/1FAIL精准揭示resume错误被effect清空，修源码后最终38PASS；没有删此测试或禁止合法重读来刷通过。

当前交付的是A的可见源码定位功能，不是A通过。真实MNIST原件/获准数据路径与CPU人工小样本运行、真实安全桌面窗口/原生选择与点击/关闭重开历史仍缺实际证据。已有历史API/保存快照/数据回放代码不等于真实桌面人工验收；本轮组件测试也不替代该证据。原生Windows存储/desktop CI依然unknown，旧a4609dc/run39135362749的check success/desktop failed且步骤未知边界保持；未查询或绕过被拒Actions，未重试Electron sandbox。

本轮NOT RUN：训练/数据下载/新环境安装、真实SSH/SFTP/硬件、实际Electron/E2E、Windows原生、完整旧450/94矩阵。Windows远程gate关闭不变，无个人电脑操作、main写入、强推、PR、Release、部署或新增费用/凭据/安全权限。下一项由父级复核此A功能片，并先取得真实MNIST与安全桌面条件；在外部条件未具备时可接M5.1非敏感配置保存/稳定targetId，但不得据此绕过本地训练先后顺序或降低A/B。**A、B及M5整体均未验收。**

## 2026-10-18 — A 可见本机环境与数据预检；新 CI 失败事实

本片源码提交完整SHA：`6183136fdcc2653ba0be9e7e747abb77fa4b7092`，父提交`9abdfebb90a5ab961cd12c21fbeae8b479e3d66b`。父级有限接受前片快照定位后，明确优先授权本片。前片RunSnapshot/RunDashboard/WorkspaceManager源码保持冻结。M5.1概要方案仍未实施，不把它替代A产品闭环。

核实此前只有start内`preflight_data`/`probe_python`，UI“检查与编译”仅projects.compile，没有训练前可见本机预检。现新增“检查本机环境与数据”显式入口：已选Python/data、已保存工程、本机模式下可用；分别显示环境依赖与数据检查、所选路径标签及实际解释器/包版本。缺IDX明确“未下载数据”，依赖缺失不报成代码错误；未能从已保存工程编译出数据集时单独解释。不会自动选择环境、执行训练、安装包或下载，数据头/长度通过不等于真实MNIST来源或学习效果。

Python定义LocalPreflightRequest/Result并生成合同；Main精确四字段、UUID/正revision白名单，preload只暴露固定local.preflight，不收任意path/命令。后端复用已有选择角色授权、固定导入probe和IDX头/长度验证；探测前捕获工程代次/已保存revision，释放工程锁后执行，单个probe互斥防止堆积，结果仅信息而非run grant。数据与环境检查各自返回固定错误allowlist，不泄露子进程stdout/stderr；start原复检仍保留。App以工程ID/revision、Python/data选择ID、dirty/ready为key，卸载后generation隔离旧成功/错误/finally；响应四项请求身份必须一致，切ssh也卸载，不触发编译/训练。

独审实复现初版P2：worker返回后HTTP await恢复前切到B仍交付旧报告。已增加API请求开始捕获代次、await成功/异常后同步复核原代次及revision，新增交付屏障project/ABA/revision回归。独审12/12 PASS，确认此P2关闭，未见剩余明确P1/P2；测试均用合成probe seam而非真实torch。前端独审源码亦无新增明确P1/P2；其首跑三文件23PASS/1FAIL为旧App mount未等lazy可见，失败单项复跑1PASS/9SKIP。最终mount改为最多50轮act+setImmediate+20ms虚拟时钟、真实visible-tab出现即停，原assert及799/800ms保存门保留；作者及独审最终App10/10 PASS。没有固定sleep或降低桌面安全测试。

实际命令（cwd `/workspace/Easy-AI`；UV/XDG缓存沿用workspace，未安装依赖）：

| 命令 | 结果与范围 |
| --- | --- |
| `pnpm exec vitest run apps/desktop/src/LocalPreflight.test.mts apps/desktop/src/App.test.mts apps/desktop/electron/workflow.test.mts` | 作者一次 **24 PASS**，2.31秒，含组件8/App10/桥接6。最终仅测试mount等待调整后重跑`pnpm exec vitest run apps/desktop/src/App.test.mts`为**10 PASS**，2.18秒；独审同最终文件10PASS，2.04秒。重合不加总；保留独审首跑23/1及后续单项事实 |
| 新组件/正式App测试边界 | 真实React DOM→MainWorkflow→认证开发sidecar→实际固定import子进程，显式选择应用Python（无torch），实际返回ENVIRONMENT_IMPORT_FAILED与DATASET_MISSING_NO_DOWNLOAD、runs为空。不是训练；其余正确依赖/晚回调报告为标明test版本的seam。覆盖项目/Python/data/dirty实际App key、组件revision、错DTO、零自动调用、重复点击单flight。画布为既有组件测试stub，无Electron/SVG交互声明 |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_local_preflight.py services/backend/tests/test_local_workspace.py services/backend/tests/test_local_api.py services/backend/tests/test_run_scope_race.py` | **50 PASS**，5.54秒；含新增12项，早前9/12/25及独审12均重合不加总。覆盖授权/角色、只读原件、缺失/畸形/symlink数据、依赖失败、probe并发、worker内与HTTP交付后切换/ABA/revision；既有Starlette弃用warning保留 |
| `UV_CACHE_DIR=/workspace/.uv-cache UV_PYTHON_INSTALL_DIR=/workspace/.python XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache pnpm check` | **PASS**，TS、strict mypy45源文件、ruff/格式、合同/真实Blockly fixture漂移、Prettier。最后测试等待只改测试helper并已Prettier/编译执行通过 |
| 同缓存 `pnpm build` | **PASS**，Electron Main TS、Vite静态assets和Linux PyInstaller；构建日志在执行器`/tmp/easyai-local-preflight-build.log`，既有chunk大小提示保留，无Electron启动 |
| `node scripts/test-frozen.mjs` | **PASS**，重建冻结sidecar从临时cwd启动、认证与资源/golden编译、预检无token401/任意路径额外字段422、EOF退出0。不是Windows ABI或真实训练；实际预检结果端到端见开发sidecar组件测试 |
| `git diff --check`、原件字节/hash | **PASS**；计划116185字节，SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原规格`5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README`befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`不变 |

其余中途失败如实保留：首次TS因测试DesktopAPI缺新local方法FAIL，更新测试桥接；新集成测试误调不存在workflow.invalidate，改用已有dispose。首轮组件实际HTTP尚未结束便断言（19PASS/1FAIL并act警告），改为act内await实际请求Promise；App新测试一次误写“导入工程”按钮名（23/1），纠正为实际“导入JSON工程”；另旧lazy mount间歇FAIL按上文有界真实可见等待解决。strict mypy曾拒绝dataset Literal set传set[str]，显式声明names:set[str]后PASS。没有删失败用例、跳过保护或降低断言。

**CI当前状态纠正**：父级通过已读通知邮件提供：`5a34286`的run39137171929（14:43:23 UTC）check failed/desktop failed；`9abdfebb90a5ab961cd12c21fbeae8b479e3d66b`的[run39140446024](https://github.com/T1doo/Easy-AI/actions/runs/39140446024)（15:27:23 UTC）也为check failed/desktop failed，通知附3/4 annotations，原文未取得。旧a4609dc的check success仅是旧历史，不能沿用作当前绿灯，更不能被本片本机PASS覆盖。

已在安全检查点只读核对9ab提交及工作区CI/setup/python-task/锁版本/E2E配置；check=Ubuntu、desktop=Windows，配置核对无法确定实际失败步骤或根因。执行器未发现这两run的已有步骤日志/annotation文件；未重试曾拒Actions端点、未换路取Actions、未触发workflow重跑。准确待提供证据：上述run的check和desktop首个失败step名称/exit信息、对应错误日志与annotation原文。新local bridge需同步E2E精确键白名单已补（仍检查node未暴露/sandbox/webSecurity等原门），但该新增键不存在于9ab，不能解释9ab失败。没有将远端失败归咎sandbox、Windows平台门或已修P2。当前片远端CI结果尚未知，正常开发提交不代表失败CI已修复。

NOT RUN：真实MNIST/训练/新环境安装/数据下载、实际Electron/E2E/原生picker及SVG交互、SSH/SFTP/上传/硬件、原生Windows/NTFS或冻结ABI、历史450/94或38/6整套重复。真实数据路径和安全桌面仍待条件；Windows远程生产gate保持关闭，M5整体/A/B继续未验收。未操作个人电脑、未动main、未强推、未创建PR/Release/部署或新增费用/凭据/安全权限。下一项：父级独审本片并取得上述精确CI失败日志；可独立授权开发不被缺数据/桌面阻塞，但不得把外部验收记成通过。

## 2026-10-18 — M5.1 非敏感服务器概要与稳定 targetId

源码完整SHA：`92601983d1079f388b305f7b3cbde7f5be29cc0a`，父提交`c9a25e42235649487e08b0ec46a05d75964d289d`。父级有限接受预检片并明确授权本片；保持原预检/快照实现与计划裁决，不将本片当成M5整体或A/B验收。

交付：正常App的SSH入口现在可保存/列出/选择服务器概要、编辑概要、刷新列表。仅持久化alias、规范化host/port、username、独立UUID targetId与revision；未持久化password/privateKey/privateKeyPath/passphrase/token或认证lease。选择只填入锁定的目标配置，不触发probe/auth/SSH或训练；指纹检查、确认、密码认证、环境检查仍分别显式操作。修改须带expectedRevision，冲突保留输入，不自动重试；编辑后的记录需要显式重新选择。App/组件generation隔离项目切换后的旧list/save成功和错误；字段更新期间有界busy，不丢草稿去接受旧响应。既有密码输入清理/lease期限/指纹与平台门保持，没有新增真实SSH授权。

Python唯一合同生成Profile/Input/Update/TargetReference，并给短期认证请求/结果增加成对可选targetId/targetRevision；旧协议会话可兼容，但新远端bind必须引用已保存profile。认证前、认证后和每次lease使用复核profile的revision、endpoint、username；Main也核回传target身份。新bind/start沿用同一stable targetId，不再逐次随机生成。旧RunConfig与RemoteRunIdentity从不修改；历史重连继续按冻结的project/endpoint/username/fingerprint核认证，不能用当前概要改变旧run目标。暂时添加的“旧target UUID必须等于新profile UUID”比较已撤回，避免旧随机UUID记录失去原来的显式重连；原冻结身份安全比较保留逐字不降门。

API新增GET/POST `/api/v1/connections`、PATCH `/api/v1/connections/{UUID}`；Main精确字段/类型/ID白名单，backend严格拒绝额外字段，base route也脱敏422以免回显拒绝的凭据值。配置仅位于应用私有状态根connections.json，不进可移植工程。列表/保存会创建或使用持久kernel锁文件，因此也不宣称这些操作文件系统零写。catalog最多128条且读写统一128KiB编码字节限制，受保护regular-file读取、坏版本/重复ID/坏JSON/symlink/FIFO拒绝，互斥下读取最新revision并原子发布；没有将Linux验证扩展成原生Windows耐久支持。

父级要求的前片术语澄清：本机预检“只读”指不写工程或数据、不创建训练Run；复用的固定probe可能写既有probe-cache/Matplotlib缓存。前片24前端/50后端作者窗口和App10回归互有重叠，不累计为新增通过数。本片没有重跑这些旧矩阵为等待凑报告。

独审发现并关闭三类P2：

- 合法长UTF8字段可让catalog写到读取上限之外。现create/update共享写前字节门，拒绝时原文件/revision不变。初次只接通create、遗漏update原多行atomic_write调用；独审实际25PASS/2FAIL指出缺口，随后接通update `_write(catalog,before_publish)`，仅原两失败项独立复跑2PASS、0.62秒，未隐藏失败。
- replace成功后目录fsync等报错时，旧lease/binding仍可能生效。现在通过大小/版本/活动身份门后，发布前定向撤权；不确定写入后旧授权不能启动。lease及start还重新核当前保存的profile。实际回归post-publish注入错误、外部catalog改动均拒旧binding且无新Run。
- Main在PATCH await后全局invalidate会误关后来建立的B。现Main在发请求前仅撤销A旧operation，迟返无副作用；后端publication同样仅撤销A的auth/lease/bindings，无关B保持有效。前端deferred A→B认证→A返回与后端真实manager合成会话定向用例通过。

活动Run引用的目标endpoint/username变更409拒绝；改alias可生成新revision但不改旧config/identity。副作用是撤销该目标的旧认证能力，不停止或重写已冻结任务。稳定绑定重复生成、重启读取、revision冲突、活动拒绝和旧快照原样保留均有定向证据。独审最终无剩余明确新P1/P2；这是有限代码审查，不是SSH网络/桌面/Windows验收。

实际命令（cwd `/workspace/Easy-AI`；沿用workspace UV/XDG缓存，无安装依赖）：

| 命令 | 最终结果与精确范围 |
| --- | --- |
| `pnpm exec vitest run apps/desktop/src/ServerProfiles.test.mts apps/desktop/src/ConnectionPanel.test.mts apps/desktop/src/AuthenticatedPanel.test.mts apps/desktop/src/App.test.mts apps/desktop/electron/workflow.test.mts apps/desktop/electron/session-workflow.test.mts` | **51 PASS**，2.77秒；含新概要组件7、profile IPC1、session2及既有相关回归。真实React→Main→认证开发sidecar执行元数据CRUD并关闭/重启，targetId与记录一致，零probe/auth；其他认证/会话均明确合成fixture，不是真实SSH |
| `services/backend/.venv/bin/pytest -q services/backend/tests/test_connection_profiles.py services/backend/tests/test_connection_manager.py services/backend/tests/test_remote_run_api.py` | 最后完整作者窗口 **47 PASS/1 FAIL**，8.64秒；仅新B会话测试的fixture账号与FakeSession固定账号不一致。保持FakeSession原账号/密码断言，将两profile改为synthetic-user后，单跑`...test_remote_run_api.py::test_updating_profile_a_does_not_retire_unrelated_b_lease` **1 PASS**，0.45秒；独审同项1PASS、0.39秒。其余47不重复跑；不伪称一次48全绿。remote API沿用测试自有标准库子进程；新增freeze用例仅真实prepare，begin拦住，非SSH或训练 |
| UUID路由修正后 `services/backend/.venv/bin/pytest -q services/backend/tests/test_connection_profiles.py` | **13 PASS**，0.74秒；与上窗口重合不加总。涵盖保存重开/规范化/412、凭据拒绝不回显、坏/未来/重复/非regular存储保护、UTF8写界、目标引用拒绝 |
| 同缓存 `pnpm check` | **PASS**；TS、strict mypy46源码、ruff/格式、合同/真实Blockly fixture漂移、Prettier。UUID路由限缩后又仅`node scripts/python-task.mjs check` PASS，源码46不变 |
| 同缓存 `pnpm build`，UUID路由限缩后 `node scripts/python-task.mjs build` | **PASS**；Main TS/Vite及Linux PyInstaller，保留既有chunk大小提示。日志分别`/tmp/easyai-connection-profiles-build.log`、`/tmp/easyai-connection-profiles-build-final.log`，未提交二进制或启动Electron |
| `node scripts/test-frozen.mjs` | **PASS**；最终冻结资源/鉴权/golden编译/EOF退出0；新增真实HTTP概要创建201、规范化/GET、PATCH同ID升revision、旧revision412和凭据字段422不回显。不执行有效SSH/训练 |
| `node scripts/test-frozen-ssh.mjs` | 最初 **FAIL**：新增无路径约束PATCH使旧禁用`/connections/probe`等返回405而非原404。将PATCH路径限缩UUID转换器（UUID参数→str传service），没有放宽原拒绝断言；重冻结后 **PASS**，原strict DTO/脱敏/平台与scope拒绝及EOF退出0。不是此前远端CI失败根因证据 |
| `git diff --check`、原件字节/hash | **PASS**；计划116185字节，SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原规格`5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README`befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`均不变 |

其他失败/修正原样交代：首轮TS指出Backend method union缺PATCH及旧测试桥接缺CRUD，补齐固定接口，未开放renderer通用请求；ruff曾报测试多余Path import，移除。UTF8更新测试先未填完剩余空间，改为合法小记录填满后再断言扩容拒绝；随后确实抓到update漏接。前端作者首轮50PASS/1FAIL（旧App未先选择profile即查指纹区）；下一轮15PASS/2FAIL、独审29PASS/2FAIL分别揭示对非spy作调用次数断言、真实初始list尚未结束便点disabled保存。改为vi.fn包装保留0认证断言，并在act内await实际list、确认create1次再await真实保存；独审仅原两项复跑1PASS/9SKIP与1PASS/6SKIP，均重合不加总。B后端fixture先为profile用户名不符而SSH_TARGET_REFERENCE_STALE，改同profile后仍被FakeSession原用户名门拒绝；最终统一synthetic-user，未改生产认证或测试安全断言。

CI保持：已知`5a34286`/run39137171929和`9abdfebb90a5ab961cd12c21fbeae8b479e3d66b`/[run39140446024](https://github.com/T1doo/Easy-AI/actions/runs/39140446024)的check与desktop均FAIL；当前源码CI结果未知。本轮没有允许的新错误日志来源，未重试/换路Actions、未触发workflow重跑。仍缺两个job首个失败step及exit/错误日志、annotation原文；本机通过和本轮冻结路由修复不能覆盖或解释旧远端失败。

NOT RUN：真实SSH/SFTP/上传/训练/数据下载、新训练环境或桌面安装/SDK协议接受、个人电脑操作、实际Electron/SVG/原生picker/E2E、Windows/NTFS/冻结ABI、旧整套450/94及38/6/预检24/50矩阵。Windows远程生产gate关闭，真实MNIST/安全桌面条件仍缺，M5整体/A/B继续未验收。无main写入、强推、PR、部署、Release、新费用/凭据/安全权限。下一项：父级独审本片，继续取得精确CI日志与外部验收条件；本片不自动扩大网络授权。

## 2026-10-18 — M6.2 FigureInspector 最小用户闭环

源码完整SHA：`1452bbd4d8f80ff738c76629a1e3f2a12a03cac3`，父提交`42832d6b2461688439b771c2e722e6478590be4e`。父级有限接受M5.1并明确授权本片；M5.1/预检/后端源码保持冻结，没有改编译器、schema、manifest或生成第二套图表JSON。本片只覆盖布局/尺寸/定位，不称M6完整交付。

选择实际figure或其panel/样式等子块时，右侧显示FigureInspector；布局五选项与尺寸三选项直接读取现manifest。网格对应现Python编译顺序，格子按钮定位真实panel稳定ID并复用原代码高亮/标签页路径；选panel后仍保留所属figure面板。空格子只提示，没有自动创建/删除/重排块，没有图像渲染器或模拟训练图。修改只对现workspace的figure LAYOUT/SIZE调用Blockly字段API，经已有序列化→草稿/保存/编译路径生效。

WorkspaceManager先沿panels输入与next链读取全部物理panel，不依赖getAllBlocks顺序；校验目标类型、manifest值、容量后才改字段。一次应用两字段使用同一Blockly事件组并恢复外层group，一次Undo/Redo完整还原。跨页应用先同步切到实际figure所在workspace并通知受控tab，避免在data页编辑隐藏training figure后撤销错工作区。新布局容量检查包含停用块，拒绝时所有字段、连接、ID、序列化原样不变；仅改SIZE不误当缩容。只读工程/历史SnapshotCode中的UI控件禁改且manager方法再次拦截；仍可查看/定位旧panel，不写当前工程或旧快照。

独审实证P2及修复：初版把disabled panel当网格占位，但Python Decoder跳过disabled再继续next，后面的启用panel会前移。现运行网格只按启用panel连续排列，完整物理链单独列出并保留停用ID供定位；画布/围绕管线停用时明确不生成图像。缩容仍按全部物理panel保护，遵守父级“含停用块容量检查”要求，没有为了显示一致去改变编译器。真实fixture链首停用、第二物理panel启用时，UI首格是第二panel，其Python source-map对应的add_subplot确为grid[0]。此P2独审关闭；跨页Undo边界同样由源码导航和回归关闭，最终两路独审未见本窗口剩余明确P1/P2。

实际命令（cwd `/workspace/Easy-AI`；pnpm Python静态子任务沿用workspace UV/XDG缓存，无安装依赖）：

| 命令 | 结果与精确边界 |
| --- | --- |
| `pnpm exec vitest run apps/desktop/src/FigureInspector.test.mts apps/desktop/src/RunSnapshot.test.mts packages/block-library/workspace-manager.test.mts` | **47 PASS**，2.30秒；含新22项、旧snapshot17和manager8，不累计独审重复用例。新22含15布局/尺寸组合、跨页双字段单次Undo/Redo、停用块缩容全序列不变、无效值/只读/无操作保护、真实DOM字段修改和panel定位、历史SnapshotCode只读、真实保存重开/确定性编译 |
| 新真实保存重开链 | 真实Blockly序列化fixture编辑→测试自有临时目录→正式ProjectService.save→close→新ProjectService.snapshot→Python权威compile；revision 1→2，workspaces深比较相同，code/programHash/codeHash/sourceMap逐一一致，AST可解析；明确2×2/large生成对应gridspec/figsize、disabled首panel保留但启用后继映射grid[0]。仅应用Python生成/解析源码，未导入torch、未执行生成训练代码 |
| 新UI/只读测试替身边界 | 真实React DOM、ProjectEditor、WorkspaceManager及真实headless Blockly。只有SVG宿主resize/setVisible/setReadOnly为空替身，select记录ID；这不证明真实SVG选择/缩放/编辑器禁用。CodeView在JSDOM走既有安全只读fallback，SnapshotCode一行注释仅为标明的UI映射夹具。实际旧快照原对象和序列化不变、manager配置方法不写、子图按钮调用旧来源导航 |
| 独立只读审查 | 前端独跑新文件 **22/22 PASS**，2.27秒；后端/语义独跑 `pnpm exec vitest run apps/desktop/src/FigureInspector.test.mts -t 'runtime grid skips disabled|real Blockly edits survive'` **2 PASS/20 skipped**，1.23秒。这些均与47重合，不相加；不宣称桌面或训练验收 |
| 同缓存 `pnpm check` | **PASS**；TS、strict mypy46既有后端源码、ruff/格式、合同/真实Blockly fixture漂移、Prettier。后端无修改，未重跑Python整套或冻结ABI |
| `pnpm --filter @easyai/desktop build` | **PASS**；Main TS/Vite静态assets，保留既有>500KB chunk提示。日志在执行器`/tmp/easyai-figure-inspector-build.log`，未启动Electron；静态CSS使用固定data-columns规则，没有inline style/CSP放宽 |
| `git diff --check`、原件字节/hash | **PASS**；计划116185字节、SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原规格`5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README`befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`均原样保留 |

中途失败如实保留：新测试helper最初漏闭括号，Prettier/TS/Vitest解析FAIL、0用例执行；修正测试语法后21PASS/1FAIL，失败是JSDOM没有提供既有CodeView需要的ResizeObserver。补与旧快照测试相同的宿主替身后最终47PASS；没有改CodeView生产逻辑或弱化只读/序列化/编译断言。独审发现disabled网格偏差后修改生产显示逻辑并加实际Python映射回归，没有修改Python跳过停用块规则；实际SVG行为仍明确NOT RUN。

CI状态不扩大：已知5a34286/run39137171929及9abdfebb90a5ab961cd12c21fbeae8b479e3d66b/run39140446024的check与desktop均FAIL；当前提交CI未知。未重试/换路被拒Actions或触发重跑，仍缺首个失败step/exit、错误日志及annotation原文。本地47/构建/静态PASS不覆盖远端失败。上片51前端、47后端PASS/1FAIL后该项单独PASS的原口径保持，没有重跑或包装为原窗全绿。

NOT RUN：真实训练/SSH/SFTP/上传/数据下载/新环境或桌面安装/SDK协议、个人电脑、实际Electron/原生picker/SVG/Monaco/E2E、原生Windows/NTFS/冻结ABI、前片整套矩阵。没有修改main、强推、PR、发布/部署/Release、新费用/凭据/安全权限。Windows远程生产gate仍关闭，真实MNIST与安全桌面条件仍缺，A/B、M5整体及M6整体均未验收。下一项：父级独审本片与继续取得精确CI日志和外部验收条件；后续M6样式/数据源等剩余用户功能另片处理，不以布局编辑冒充全图表验收。

## 2026-10-18 — 原 M6 字段覆盖核实后接 M7.1 最小用户向导

源码完整SHA：`2b7d4891d1b4af4ecb015b96453c497184791c26`，父提交`b991cafb190a2c60469947dd4274bbfe0be7071e`。父级有限接受前片，并条件授权：现有Blockly字段若已覆盖子图类型/数据源/样式，应给证据转原M7向导，避免重复实现。本片没有改FigureInspector/WorkspaceManager/编译器/后端/manifest/合同或新增图表配置源；未重跑前片47。

条件核实：manifest的viz.panel/data_source/title/legend/axis字段已由registerBlocks生成真实dropdown/text/checkbox和statement连接，Python lower_figure/emit已消费这些字段。先实际执行只读Node heredoc审计（`node --input-type=module`，真实Blockly workspace与应用Python子进程），修改scatter、来源、标题/颜色、坐标轴，保留图例，单组Undo恢复，正式ProjectService保存/重开后的code/hash/map一致，PASS。为使证据持久可审，新增单项`packages/block-library/viz-fields.test.mts`，另逐一断言Python IR chart/source/title/color/axis/legend以及完整workspaces不变。这里证明现有字段能力，不等于真实SVG鼠标操作或PNG渲染验收，也不表示全部M6安装/数据集能力已完成。

转入原M7.1（计划项目/服务器/环境/data向导），新增GettingStarted：工程、运行位置、环境/数据、代码检查、训练/历史五个导航入口，仅从当前App状态派生展示，不缓存另一份工程/预检状态，不执行任何选择/检查/保存/训练。欢迎提示保留已有工程/数据、只读工程不可训练；“已选择”明确不代表预检通过，代码检查通过也不代表环境检查通过。服务器绑定提示只有当前project/revision/programHash/connection且无dirty时才成立，启动仍须原正式复检。远端步骤明确先显式身份/认证/环境数据检查，保存并通过代码检查后再绑定。真实数值教程、完整错误报告与M7其他任务尚未实现，不把此片称M7整体完成。

实际修复的M7.1界面差距：原SSH模式仍显示本机Python/data选择器，易让学生以为服务器数据也需本地副本。现在这两项与LocalPreflight只在本机模式挂载；服务器模式显示已有服务器Python/数据绑定（若有）及显式配置入口，说明使用服务器现有环境/数据、不要求本地副本、不自动上传，不安装/升级老师环境。本机说明解释已有训练Python与MNIST/raw相对目录。切换运行位置只是既有会话UI选择，不保存工程或自动连接。

导航使用固定栏目ID和可聚焦标题，focus/scroll不改变草稿。独审建议的键盘可用性补强也已完成：显式打开服务器配置后聚焦其region，避免用户从环境区点按钮却错过上方新面板；按工程ID标记焦点请求，跨工程不采纳旧请求。打开配置会复用已有非敏感概要list，可能使用已有本地锁文件，不能称文件系统零写；本片向导本身无持久化/新增网络操作。没有改服务器身份/认证安全逻辑。

实际命令（cwd `/workspace/Easy-AI`；UV/XDG沿用workspace缓存，无新依赖）：

| 命令 | 结果及边界 |
| --- | --- |
| `pnpm exec vitest run apps/desktop/src/GettingStarted.test.mts apps/desktop/src/App.test.mts packages/block-library/viz-fields.test.mts` | **16 PASS**，2.65秒，含Guide4、App11、已有viz字段证据1。不是前片47/22或M5.1 51的重跑/累计。覆盖欢迎/只读/服务未就绪、已选择不冒充通过、dirty不能显示旧编译成功、服务器无本地副本要求、忙碌时禁开配置、实际App导航focus及SSH分支 |
| 新App真实DOM定向断言 | environment/compile/server三个目标获得焦点；SSH不显示本机选择按钮；配置入口仅listProfiles1次。pick/preflight/start/probe/auth/discover/save均0调用；没有自动选择替代环境、编译或执行训练。本机/服务器原有运行门没有改动 |
| 新viz字段证据边界 | 真实headless Blockly修改5个字段、保留legend，正式ProjectService save/close/open，权威Python编译/IR/code/codeHash/programHash/sourceMap/workspaces一致，单组Undo原序列化恢复。只解析/生成代码，不导入torch或执行生成训练程序；字体/图像/渲染/网络不是该项证明范围 |
| 独立只读复核 | `pnpm exec vitest run packages/block-library/viz-fields.test.mts` **1 PASS**，1.06秒；`pnpm exec vitest run apps/desktop/src/GettingStarted.test.mts` **4 PASS**，927ms；`pnpm exec vitest run apps/desktop/src/App.test.mts -t 'beginner guide'` **1 PASS/10 skipped**，1.04秒。均与16重合，不相加。源审未发现本窗口新明确P1/P2，焦点建议关闭 |
| 同缓存 `pnpm check` | **PASS**；TS、strict mypy46既有后端源码、ruff/格式、合同/真实Blockly fixture漂移、Prettier。后端没有修改，未跑旧后端矩阵 |
| `pnpm --filter @easyai/desktop build` | **PASS**，Main TS/Vite静态assets；保留既有chunk大小提示，日志`/tmp/easyai-getting-started-build.log`。向导CSS静态，不放宽CSP，未启动Electron或重建未改后端 |
| `git diff --check`、原件字节/hash | **PASS**；计划116185字节、SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原规格`5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README`befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`均原样保留 |

中途失败：首轮TS拒绝新测试末行把void matcher结果与false比较；同轮实际15PASS/1FAIL还指出测试误找“未通过预检”，但该操作根本未执行预检。将错误断言改为实际服务器设置提示，保留所有0执行调用断言，并增服务器region焦点断言后最终16PASS；没有修改生产预检结果或降低训练门。随后只明确服务器绑定须先保存/编译的说明文本，静态检查/构建通过。原始失败不归因生产环境或旧CI。

CI继续保留失败边界：已知5a34286/run39137171929、9abdfebb90a5ab961cd12c21fbeae8b479e3d66b/run39140446024的check和desktop均FAIL；本片及近期提交CI未知。未访问/换路此前被拒Actions端点、未触发重跑；仍缺两job首个失败step/exit、错误日志及annotation原文。不能用本机16/check/build或先前47覆盖远端失败。

NOT RUN：真实Electron/SVG/Monaco/原生picker/E2E、训练/SSH/SFTP/上传/下载MNIST或其他数据、新环境/桌面安装/SDK协议、个人电脑、Windows/NTFS/冻结ABI、前片47/51及旧后端整套矩阵。无main写入、强推、PR、发布/部署/Release、新费用/凭据/安全权限。Windows远程生产gate关闭，真实MNIST/安全桌面条件仍缺；A/B、M5/M6/M7整体均未验收。下一项：父级独审此最小向导，再按原M7.2友好错误或M7.3本地七主题与真实数值卷积交互独立接续，不提前扩v0.0.1。

## 2026-10-18 — M7.2 最小工程操作友好错误与启动确认丢失恢复

源码完整SHA：`bc4e5199b155f6714ef64f4b1f232008a80deec1`，父提交`f1ecaf7866167b404d43ea359ec8ae631f1744d7`。父级接受M7.1后授权先核实App裸String(reason)入口，实施最小阶段/建议动作/折叠技术详情。本片只改App与纯展示FailureCard及对应测试；没有改后端、合同、编译器、Blockly数据、Main IPC或训练协议。原计划M7.2完整运行时NameError规则/注册对象解释/报告导出和M7.3教程尚未实现；RunDashboard、LocalPreflight等其余错误入口仍待后续迁移，不称M7.2或M7整体完成。

实际缺口：本地服务连接、工程恢复/打开/新建/导入/导出/保存、环境数据选择、编译、启动和历史读取原来直接拼接异常。现在各操作显式传入固定阶段；卡片给出对应建议和既有工程/运行位置/检查/历史导航。导航与向导共用focus/scroll函数，零训练/认证/安装/选择器/自动重试。现有结构化编译诊断的积木定位保留，不建立第二套映射。保存失败仍保留ProjectDraft并暂停自动保存，原手动保存和导出当前工程能力未改。

隐私边界：技术详情默认折叠，仅含固定stage和通过instanceof得到的Error/TypeError/RangeError/Unknown类别。不拼接任何原始message/stack/cause/自定义name，不调用未知对象toString；因此也不显示异常中的主机、用户名、绝对路径、口令/token或任意私密字符串。这里是固定安全摘要，不冒充完整脱敏报告，也未自动上传原始日志。正常工程名/用户已选择的路径和其他既有视图没有重新定义为报告或改写。

启动异常采用“启动运行未确认”，保留原幂等intent，不说任务已失败/已停止。前端独审发现P2：历史导航只移动焦点，原历史缓存无法发现服务已登记但响应丢失的任务。已加显式“刷新运行历史”只读按钮，回第一页并触发原list effect；原valid清理门丢弃旧刷新/旧页/旧工程迟到响应。读取成功仅清除history阶段错误，保留save/start等其他操作卡。新测试模拟start已登记后抛异常：导航不读、用户显式刷新后出现RUNNING记录、start总计1次且原activeRun门阻止再次启动；没有自动重发、终止或修改运行状态。

实际命令（cwd `/workspace/Easy-AI`；Python任务沿用`UV_CACHE_DIR=/workspace/.uv-cache UV_PYTHON_INSTALL_DIR=/workspace/.python XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache`）：

| 命令 | 结果及边界 |
| --- | --- |
| `pnpm exec vitest run apps/desktop/src/FailureCard.test.mts apps/desktop/src/App.test.mts apps/desktop/src/GettingStarted.test.mts` | 最终 **31 PASS**，2.81秒，FailureCard11、App16、向导4。真实React DOM App/卡片，画布沿用既有测试替身；不是Electron/原生桌面验收。覆盖固定阶段、默认折叠、敏感message/cause/name/stack与toString不读取、工程/编译错误导航零执行、丢启动确认后的只读恢复、旧刷新迟到失败隔离、成功刷新清除已恢复的读取错误；既有草稿冲突/导出等App回归通过 |
| 独立只读审查 | 两位审查者，无编辑。前端先发现上述P2，修复后独跑FailureCard **11 PASS**、App `-t 'friendly\|uncertain start'` **3 PASS/11 skipped**；最终小补另独跑App `-t 'history refresh'` **2 PASS/14 skipped**。安全审查独跑草稿冲突 **1 PASS/10 skipped**、后独跑App `-t 'uncertain start'` **1 PASS/13 skipped**。都是与最终31重合，不相加；有限源码范围未见未关闭明确P1/P2 |
| 同缓存 `pnpm check` | **PASS**，TS、strict mypy46既有后端源码、ruff/格式、合同/真实Blockly fixtures漂移、Prettier。日志`/tmp/easyai-friendly-check.log`；后端无改动，未跑旧后端整套或训练 |
| `pnpm --filter @easyai/desktop build` | **PASS**；Main TS/Vite静态assets，保留既有>500KB chunk提示。日志`/tmp/easyai-friendly-build.log`；未启动Electron、未放宽CSP、未重建未改后端 |
| `git diff --check`、`git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0`、`sha256sum`、`wc -c` | **PASS**；开发前工作区干净、远端dev为父SHA，main仍`5323f86232529efcfb52131168ad049f01b219f3`。原计划116185字节/hash `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原规格`5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README`befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`均保留 |

本窗口没有测试FAIL；先25PASS，补历史刷新隔离后30PASS，补恢复错误清卡后最终31PASS，窗口相互重合不累计。独审P2已由实际恢复测试关闭，不隐藏其原始发现。正常开发分支源提交与本证据提交一并推送；最终完整证据SHA/远端一致性见执行器交付记录。

CI阻塞仍保持：5a34286/run39137171929、9abdfebb90a5ab961cd12c21fbeae8b479e3d66b/run39140446024的check与desktop均FAIL，本片CI未知。此前Actions读取被拒，未重试被拒操作、未换路、未触发重跑；仍需要失败job首个失败step/exit、错误日志与annotation原文。本地31/check/build不覆盖远端FAIL。

NOT RUN：真实Electron/SVG/Monaco/原生picker/E2E、训练/真实MNIST/SSH/SFTP/上传/数据下载、新训练或桌面环境安装/SDK协议、个人电脑、Windows/NTFS/冻结ABI、前片后端整套矩阵。Windows远程生产gate仍关闭，A/B、M5/M6/M7整体仍未验收。没有main写入、强推、PR、发布/部署/Release、新费用/凭据/安全权限。本片未遭新拒绝或未决外部写入。下一项：父级复核本最小片后接续M7.2其余运行时友好错误/报告或明确授权的M7.3本地教程；同时取得精确CI失败日志及真实桌面/训练/SSH所需最小条件。

## 2026-10-18 — 父级独审P2：历史错误归属隔离修复

源码完整SHA：`3a7be94a35e391c807ec74fb70e8323b63b80b68`，父提交`75afb6ab8f72d8c11cad5f47b5ef8f820ebec94f`。本轮只处理父级独审指出的精确P2，暂缓RunDashboard/M7.3。此前“历史成功仅清history错误”的实现仍有缺陷：历史失败先无条件覆盖主error，之后成功只看见history便清空，导致未解决的start/save/export提示丢失。此前本地31PASS和两位有限独审没有覆盖这个失败→恢复交错，不能作为无此缺陷的证明。

先复现后修复：新增参数化3项真实App DOM回归，各自先产生启动确认丢失/保存/导出失败，再显式刷新历史失败→显式刷新成功。首次在失败阶段断言主提示已消失，**3 FAIL/16 skipped**，1.10秒，`/tmp/easyai-history-ownership-red.log`。调整回归使完整两次刷新都执行后才断言，再跑原生产逻辑仍 **3 FAIL/16 skipped**，1.14秒，`/tmp/easyai-history-ownership-red-complete.log`，确认恢复后提示亦丢失。两次是同三项复现，不累计，没有弱化保留提示断言。此为执行器模拟服务/IPC异常的UI事故复现，不代表真实用户或训练事故。

最小修复只增加独立historyError状态：历史读取成功、失败均不再写主error，自己的卡片显示在历史区域；成功只清自己的读取错误。acceptSession清除旧工程的historyError，既有effect valid清理继续隔离旧工程/旧刷新迟到响应。主操作error、ProjectDraft、自动保存暂停、启动幂等intent与所有训练门保持原逻辑，不因只读刷新消除未解决的操作提示，不自动重试启动/保存/导出。这里没有扩展为其他主操作之间的通用错误队列。

实际命令与结果（cwd `/workspace/Easy-AI`）：

| 命令 | 结果/边界 |
| --- | --- |
| `pnpm exec vitest run apps/desktop/src/App.test.mts -t 'history failure then recovery\|history refresh\|uncertain start'` | 修复后 **6 PASS/13 skipped**，1.36秒。含新3项交错、已有旧刷新迟错隔离/读取恢复2项及丢ACK显式刷新1项。新3项同时检查失败/成功时原操作提示均在、读取错误只在失败时在、start总调用至多显式1次；保存片再推进4秒仍只save1次、草稿画布仍1块、autosave仍暂停。未重跑此前完整31 |
| 两位独立只读复核 | 前端独跑同6项 **6 PASS/13 skipped**，1.35秒；安全独跑 `-t 'history failure then recovery'` **3 PASS/16 skipped**，1.09秒；均与根6重合不相加。两位确认前次审查遗漏此失败覆盖路径，本轮P2关闭；未编辑或访问Actions |
| `pnpm --filter @easyai/desktop check`；`pnpm exec tsc -p tsconfig.tests.json`；`pnpm exec prettier --check apps/desktop/src/App.tsx apps/desktop/src/App.test.mts` | **PASS**，应用/Main TS、测试TS及两改动文件格式；日志`/tmp/easyai-history-ownership-check.log`。后端/合同/fixtures未改，无必要重跑旧后端或完整pnpm check |
| `pnpm --filter @easyai/desktop build` | **PASS**，静态桌面assets，既有>500KB chunk提示保留；日志`/tmp/easyai-history-ownership-build.log`。没有实际Electron启动、CSP/权限放宽或后端重建 |
| `git diff --check` | **PASS**；只改App及对应测试，原计划/原规格/README未改。开发前工作区干净，HEAD为父证据SHA |

CI状态按父级新邮件证据去旧：`f1ecaf7866167b404d43ea359ec8ae631f1744d7` 的run39144759022（2026-10-18 16:24:52 UTC）check/desktop仍双FAIL，链接 https://github.com/T1doo/Easy-AI/actions/runs/39144759022 。这是父级已核邮件证据，本执行器未访问被拒Actions端点、未触发重试，也未取得新根因。与更早5a34286/run39137171929及9abdfebb90a5ab961cd12c21fbeae8b479e3d66b/run39140446024双FAIL分开记录；75afb6a/本修复片CI未知。仍需首个失败step/exit、日志与annotation原文，本地6/TS/build不能覆盖远端失败。

NOT RUN：此前31全窗、后端整套/训练/SSH/SFTP/上传/数据下载、真实Electron/SVG/Monaco/原生picker/E2E、安装/SDK协议、个人PC、Windows/NTFS/冻结ABI。无main写入/强推/PR/发布/费用/凭据/安全权限变化；没有新拒绝或未决外部操作。下一项先由父级复核本P2修复，保持下一功能冻结；真实验收与CI日志阻塞仍在，M7.2/M7整体未验收。源与证据按正常开发分支提交推送，最终远端完整SHA见交付。

## 2026-10-18 — M7.2 RunDashboard安全操作错误与结构化异常保留

本片主源码SHA：`7fb252ed9090296c46e813da8ebd82acffe6f0b4`；最终来源ID守门源码SHA：`2664d59903b442b88f42f21e81888e7bbbe8ff40`，起点父证据`cd18ea8cc0caf3baee6e045787b03acb23986a81`。父级复核关闭历史错误归属P2后明确授权本片。只改桌面FailureCard/RunDashboard/runEvents与新RuntimeErrorCard及测试，没有改后端、协议/合同、编译器、环境依赖或运行权限。下一段完整NameError后端frames/hash精细映射/符号解释/脱敏报告和M7.3仍未实现，不把本片称M7.2/M7整体验收。

操作错误迁移：订阅（同步抛错及回调error）、快照读取/身份不符、结果读取、停止、接续和图片均复用安全FailureCard。订阅回调任意message不直接展示，连接状态仍由RunSummary显示；其他异常不读取String(reason)/message/name/stack/cause。固定阶段提示保留“停止请求未确认”“接续读取未确认、不会重新启动任务”“读取失败不会因此将训练判为失败”。现有自动只读poll/SSE重连保持，不新增自动操作重试；卡片按钮只focus/scroll到运行标题，不调用start/cancel/resume/auth/install。停止、接续、图片、source、read、subscription各独立错误状态，读取或快照恢复不吞停止/接续提示，图片失败也不覆盖停止未知；新run仍由key隔离，原imageRequest、mounted/active和运行身份校验保留。

训练异常走独立路径，不降为通用Unknown：runEvents保留校验后的exceptionType、variableName、file、正安全整数line与message，并深拷贝原始完整Event（含原payload及额外frames若有）。保持runId/序号过滤与最多20条；后端既有持久事件/原始stderr未删除或改写。RuntimeErrorCard对NameError/MemoryError/ValueError/TypeError/RuntimeError显示固定规则中文摘要和安全代码，未知异常明确无专用规则。NameError提示检查旧运行对象定义/注册，若代码检查通过则可能是生成器缺陷，不一概责怪学生；没有自动替换变量或调用LLM。卡片不打印任意原始message、异常名、变量名、路径或ID，只允许固定类别及精确train.py/有效line进入技术摘要。原始诊断保留在本地记录而非被丢弃；原有只读终端日志仍是原始日志视图，不能把本片宣传为全日志脱敏器，没有新增报告复制、上传或外发。

定位复用既有旧RunSource与captureRunSnapshot/locateRunBlock，后端source原有实际codeHash校验和前端7项运行身份门未改。此片仅按事件blockId定位，不声称按异常行号精细映射。摘要明确“沿用事件来源，尚未按此行号细化”。提交前自查发现SnapshotCode原视图会打印request.blockId，因此补最终守门：useMemo捕获当前冻结来源，只有ID确实属于有效旧快照才启用按钮，回调再次核对再转交location.blockId。外来事件私密ID不会经点击进入快照；正常NameError定位仍走旧模型工作区/旧代码，不查当前编辑工程。没有改旧SnapshotCode显示规则或引入新权威映射。

实际命令（cwd `/workspace/Easy-AI`）：

| 命令 | 结果与边界 |
| --- | --- |
| `pnpm exec vitest run apps/desktop/src/RunSnapshot.test.mts apps/desktop/src/runEvents.test.mts apps/desktop/src/FailureCard.test.mts` | 最终 **47 PASS**，1.96秒，Snapshot27、runEvents9、FailureCard11。此为修改的相关文件窗口，非此前App31/错误归属6或M6旧47重跑/累计。覆盖7个操作/连接失败隐私、动作仅focus且start0、cancel/resume至多显式1、旧source身份/迟回/只读、结构化NameError安全解释+旧模型定位、完整原事件不被后续调用方篡改、未知/prototype异常名及私密字段不入卡、source/read恢复不吞cancel/image、外来ID禁导航 |
| 独立只读审查 | 前端独跑安全/NameError **8 PASS/17 skipped**、原事件保留 **1 PASS/7 skipped**，后补恢复隔离 **1 PASS/25 skipped**、未知字段 **1 PASS/8 skipped**，最终ID守门/正常NameError **2 PASS/25 skipped**；安全审查`-t 'structured'` **2 PASS/31 skipped**。各窗口与最终47重合，不相加。均无编辑，有限源码审查未见未关闭新增明确P1/P2 |
| `pnpm --filter @easyai/desktop check`；`pnpm exec tsc -p tsconfig.tests.json`；`pnpm exec prettier --check apps/desktop/src/FailureCard.tsx apps/desktop/src/RunDashboard.tsx apps/desktop/src/RuntimeErrorCard.tsx apps/desktop/src/runEvents.tsx apps/desktop/src/runEvents.test.mts apps/desktop/src/RunSnapshot.test.mts` | **PASS**，应用/Main TS、测试TS及格式；日志`/tmp/easyai-dashboard-check.log`。后端/合同/fixture未改，没有重跑旧后端整套/完整pnpm check |
| `pnpm --filter @easyai/desktop build` | **PASS**，静态桌面assets，保留既有>500KB chunk提示；日志`/tmp/easyai-dashboard-build.log`。没有实际Electron启动、CSP/权限放宽或后端重建 |
| `git diff --check`；`git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0`；原件hash/字节 | **PASS**；起点工作区干净且远端dev=cd18ea8，main仍`5323f86232529efcfb52131168ad049f01b219f3`。计划116185字节/hash `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`，原规格`5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README`befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`保留 |

中途失败保留：首轮相关35项34PASS/1FAIL，原测试仍查带ID的“查看源积木 cnn”；为避免卡片展示任意ID改为固定“定位旧运行积木”，测试只更新按钮查找，旧模型tab/旧代码/只读断言均保留。第二轮44项43PASS/1FAIL，新增图片失败测试误用既有deferred helper没有的reject；改为图片API mockRejectedValue路径后44PASS，未改生产图片协议或降低隐私断言。再补恢复隔离和恶意类型后46PASS，最终来源ID守门回归后47PASS；这些窗口重合，不累计。后两次静态/构建重跑由新增来源守门生产修改触发，不扩大验证结论。

CI仍按已核证据保留：f1ecaf7866167b404d43ea359ec8ae631f1744d7/run39144759022（16:24:52 UTC）check/desktop双FAIL；更早两次双FAIL不覆盖，本片及近期修复CI未知。未访问被拒Actions端点、未触发重试、没有新根因证据；仍需首个失败step/exit、日志及annotation原文。本地47/TS/build不能覆盖远端失败。

NOT RUN：原App31/归属6整窗、后端整套/训练/真实MNIST/SSH/SFTP/上传/数据下载、真实Electron/SVG/Monaco/原生picker/E2E、环境安装/SDK协议、个人PC、Windows/NTFS/冻结ABI。Windows远程生产gate仍关闭，A/B、M5/M6/M7整体未验收；无main写入/强推/PR/发布/新费用/凭据/安全权限变化。没有新拒绝或未决外部写入。正常开发分支推送主源码/守门/本证据三提交，最终完整远端SHA见交付。下一项先父级复核本最小M7.2片，再接续完整运行时规则/报告或M7.3；真实验收和CI日志阻塞仍在。

## 2026-10-18 — §16.3 结构化traceback与旧运行精确定位

源码完整SHA：`b2384572da7d39d864951d95775284f5afbe777a`，父提交`7267b2b5a6b00b2ff6f6c4bda8a0f5a98eb956c4`。父级有限接受上片后，明确授权固定runtime→后端实际旧代码/frame校验→精确旧快照导航；同时要求修正旧迟到事件测试已失效的message断言。本片没有重新实现卡片、增加任意Python入口或启动真实训练。§16.3变量/注册对象解释、独立原始错误入口与脱敏报告尚未完成，不能称完整M7.2验收。

固定runtime：entry与RunContext.report_failure共用failure_payload，保留NameError.name、message及最多末16个frame的filename/lineno/function，附framesTruncated。StackSummary使用lookup_lines=False，不为此读取frame指向的源码；原始stderr traceback照旧保留。只读取固定runtime模块相邻train.py，最多8MiB+1计算hash，附generatedFile/generatedCodeHash，不打开事件或frame提供的路径；过长frame路径记缺失、函数与message限制长度。生成文件身份不再按basename认定。新资源只进入后续新bundle；旧事件仍保存在原journal中。

后端新增只读派生RunViews.events：先取原事件，对runtime_error调用既有source校验旧snapshot、bundle中文件digest、实际生成codeHash与真实source-map；预期生成文件由不可变RunConfig.runRoot/code/train.py计算（SSH为PurePosixPath，仅字符串比较，不连接目标）。要求runtime生成文件/hash相符，再从最内层filename精确等于本次文件的frame取合法行号；不接受外部同名train.py或仅库frame，不使用未经验证的事件blockId猜位置。Python既有locate_line按最窄semantic优先，其次明确标示scaffold；映射行须在旧代码内、origin须属于decode旧snapshot。无span、坏frame、hash/文件身份/来源未核实均precision=none且origin/line为空。不会读取当前编辑工程替代旧来源，也不把scaffold宣传为语义精确命中。

SSE在既有scoped_read/deliver及逐次scope门内使用派生视图，附payload.applicationLocation(version/runId/eventSeq/codeHash/precision/reason/origin/line)。不改Event顶层schema、事件类型或游标；应用派生字段覆盖子进程同名声称，原journal一字不改，包含同名原字段的回归亦核对原记录不变。正常无异常批次不新增来源文件读取；SSH路径仍仅注册本地缓存读取，不新增远端I/O。前端解析固定metadata，明确none/无效metadata不回退coarse事件ID；旧无metadata客户端记录保留兼容来源。Dashboard核run/hash/workspace/实际旧快照成员后才启定位，按钮与回调共用diagnosticBlock。摘要区分最窄语义、脚手架和无法精确定位，不直接显示任意reason、变量、路径或原异常。原始终端日志仍未脱敏，本片不是全界面隐私净化。

父级测试补强已完成：旧run迟到事件改注入NameError并断言无RUNTIME_NAME_ERROR和无新增alert，保留旧source/image未显示及新快照来源断言，不再以已隐藏的message作为隔离证明。

独审发现并关闭P2：坏bundle.json结构使既有_verify_snapshot对{}抛KeyError、对[]抛TypeError，令新事件视图无法按约定降级。先新增真实owned store回归，修前manifest组 **2 FAIL/1 PASS/12 deselected**，0.28秒，`/tmp/easyai-traceback-manifest-red.log`，原journal仍在。最小修复在manifest/files索引前核两者均dict，否则固定ValueError BUNDLE_MANIFEST_INVALID，使视图返回none/SOURCE_UNVERIFIED。没有catch所有Exception或绕过源校验。另前端独审建议补workspace矛盾防御；首次只补回调时新回归 **7 PASS/1 FAIL/26 skipped**，指出按钮仍启用，随后共享helper统一按钮/回调后通过。

实际命令（cwd `/workspace/Easy-AI`；UV/XDG沿用workspace缓存：`UV_CACHE_DIR=/workspace/.uv-cache UV_PYTHON_INSTALL_DIR=/workspace/.python XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache`）：

| 命令 | 结果及边界 |
| --- | --- |
| 同缓存 `uv run --frozen --project services/backend pytest services/backend/tests/test_runtime_diagnostics.py services/backend/tests/test_emission.py services/backend/tests/test_run_views.py services/backend/tests/test_run_service.py services/backend/tests/test_run_scope_race.py -q` | 最终相关矩阵 **72 PASS**，5.32秒，1项既有Starlette/AnyIO弃用警告。含新增15诊断、旧emission/views/service/scope；不是旧后端全套。专用stdlib fixture真实运行固定entry、真实NameError/非零退出/帧函数/NameError.name，未导入torch或执行训练。覆盖最内层自身frame、最窄semantic、外部同basename不能替代自身帧/仅外部或library不可猜、runtimehash错、生成文件身份错、缺frame/坏line/boolline、坏origin/无span、scaffold精度，原事件不变 |
| 新15最终防御补断言 | 同缓存 `uv run --frozen --project services/backend pytest services/backend/tests/test_runtime_diagnostics.py -q` **15 PASS**，1.63秒，与72重合不加。真实ProjectService→RunService.prepare→手工专用异常事件→cancel CREATED使SSE有界结束→认证FastAPI SSE，核derived origin/eventSeq及原journal不变；未启动子训练进程。实际旧code/source-map/{}、[]、files非dict损坏后均none/SOURCE_UNVERIFIED。此末次还保留子进程伪造同名metadata原字段、确认传输派生来源覆盖而journal原字段不变 |
| `pnpm exec vitest run apps/desktop/src/RunSnapshot.test.mts -t 'backend .* location\|switching run rejects late\|artifact and runtime-error\|structured NameError'` | 最终 **10 PASS/24 skipped**，1.58秒。新7种semantic/scaffold/none/错hash/seq/外origin/workspace+加强的late隔离、正常旧runtime来源/NameError导航。没有重跑上片47或App31 |
| `pnpm exec vitest run apps/desktop/src/runEvents.test.mts` | **9 PASS**，215ms，实际修改reducer字段后覆盖事件序号/run过滤、状态/指标、原结构化记录与安全摘要。与Snapshot10为不同文件；不累计独审重跑 |
| 两位独立只读审查 | 后端初跑新11 PASS并发现上述manifest P2，修复后独跑real_old_run组 **5 PASS/10 deselected**，0.65秒，确认P2关闭、认证SSE/原记录不变。前端最终独跑metadata/late **8 PASS/26 skipped**，确认workspace/hash/ID共同守门，无明确未关闭新P1/P2；未编辑或执行真实训练/SSH |
| 同缓存 `pnpm check` | **PASS**；TS、strict mypy47源码、ruff/格式、合同/真实Blockly fixture漂移、Prettier，日志`/tmp/easyai-traceback-check.log`。没有因自由payload metadata新增或改写顶层协议/导出schema |
| `pnpm --filter @easyai/desktop build`；同缓存 `node scripts/python-task.mjs build` | 均 **PASS**；桌面静态assets保留既有chunk提示，后端PyInstaller onedir构建成功。日志`/tmp/easyai-traceback-desktop-build.log`、`/tmp/easyai-traceback-backend-build.log`。没有启动Electron或安装新依赖 |
| `node scripts/test-frozen.mjs` | **PASS**；实际冻结sidecar从临时cwd启动，runtime资源字节一致、鉴权/原生选择API/工程创建/黄金编译、EOF exit0。日志`/tmp/easyai-traceback-frozen-smoke.log`。不是实际原生picker/Electron/训练/Windows ABI或冻结diagnostic全链验证 |
| `git diff --check`、原件SHA/字节、远端基线 | **PASS**；计划116185字节/hash `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`，原规格`5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README`befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`保留。起点工作区干净，origin dev=7267b2b，main仍`5323f86232529efcfb52131168ad049f01b219f3` |

其他中途失败如实保留：一次忘带任务缓存变量的`node scripts/python-task.mjs check`因默认/home/agent/.cache/uv只读FAIL；改用既有workspace缓存后另一次check指出刚改runtime需按仓库100列格式化，格式修正后strict检查与最终pnpm check通过。未申请额外文件权限或绕过拒绝。初窗口新11+旧emission12为23PASS，后扩受影响view/service/scope矩阵为72PASS，不累加；前端wrong-workspace单项FAIL已如上保留，没有降低禁定位断言。

CI边界不变：已核f1ecaf7866167b404d43ea359ec8ae631f1744d7/run39144759022（16:24:52 UTC）check/desktop双FAIL，更早两次双FAIL保留；本片CI未知。未访问被拒Actions端点、未触发重试，仍缺首失败step/exit、日志及annotation原文。当前本地检查不能覆盖远端失败。

NOT RUN：真实Electron/SVG/Monaco/原生picker/E2E、训练/真实MNIST/SSH/SFTP/上传/数据下载、新环境安装/SDK协议、个人PC、Windows/NTFS/冻结ABI、上片47/原App31/后端全套。Windows远程生产gate保持关闭，A/B、M5/M6/M7整体未验收。无main写入/强推/PR/发布/部署/Release/新费用/凭据/安全权限。源与本证据按正常开发分支推送，最终完整证据/远端SHA见交付。下一项先父级独审本精确定位切片，再按原§16.3接冻结符号解释/注册对象与脱敏报告，或父级明确安排M7.3；不提前扩v0.0.1，真实验收与CI日志阻塞仍在。

## 2026-10-18 — 已提供CI原日志后的四组跨平台最小修复

源码SHA：`273e7527b7336a9fc2b930a0934da5b7df576cae`，基线`d651a496fc2a2fd34ac1755556bbd06d73990032`。父级转交用户f1ecaf7/run39144759022完整首错日志后，立即优先修复；不再把旧日志缺失作为等待。符号/报告新功能WIP完整留在`/workspace/Easy-AI`，本片在`/workspace/Easy-AI-ci`独立git工作树/正常开发分支实现和验证，复用原应用venv，仅用PYTHONPATH指向此源码，没有新建/同步环境或安装依赖，单一集成者。原工作区WIP尚未验收、不包含在本CI提交。

四组分别核实，未改workflow/runner ACL或关安全门：

1. **CRLF**：固定f1ecaf7与当前test_project_persistence.py原断言相同，Windows日志真实b'True\\r\\n'对b'True\\n'不等。仅readline.replace(CRLF,LF)后严格等于True+换行；仍核live contender不能owned、kill/exit后的重新获取与save revision2，无删测试/Windows skip。
2. **FIFO catalog契约**：原路径RunService._read_store→LocalDirectory.open_file→check_file为REMOTE_CACHE_FILE_UNSAFE，其他snapshot/config/bundle仍read_regular→FILE_NOT_REGULAR。修前catalog真实回归 **1 FAIL/4 deselected**，0.39秒，`/tmp/easyai-ci-fifo-red.log`。只按场景参数化预期，不统一/放宽生产错误码；3秒子进程timeout、必须拒绝且FIFO不改写均保留。
3. **Windows frozen第116行422**：`git show f1ecaf7:scripts/test-frozen-ssh.mjs`与当前同一请求`POST /connections/identity/cancel`，预期仍200。模拟HostKeyStore平台不可用真实TestClient复现422，body为固定SSH_TRUST_PLATFORM_UNVERIFIED，而不是猜路径/Node版本；冷cancel与祖先policy合并red **2 FAIL/80 deselected**，0.57秒，`/tmp/easyai-ci-reproduce.log`。根因LocalWorkspace.identity()/connections()为无活动操作的控制请求提前构造HostKeyStore。现在SshClient接收惰性store factory并用锁缓存成功实例；真正_open在任何dial之前验证store，Windows平台门未动。冷cancel仍进入原SshIdentityService，保留取消先于probe注册的tombstone，不能用no-op丢该保证。冷confirm/auth/session/environment/close保持原状态码/作用域/脱敏拒绝；新valid probe仍平台拒绝且socket禁止，未连接offline.invalid。原冻结脚本完全无diff，未接受422假成功。
4. **Windows native祖先**：日志owner SID精确对应Microsoft TrustedInstaller，首拒发生在C:\\ anchor，未进入junction。新增该**完整SID仅not final祖先**的owner/ACE信任；应用leaf原政策、未知/近似S-1-5-80、危险写ACE/reparse/identity检查均保留，未改DACL或系统权限。官方语义来源：[Microsoft文件与注册表权限说明](https://learn.microsoft.com/en-us/archive/msdn-magazine/2008/november/access-control-understanding-windows-file-and-registry-permissions)。纯policy反例与coldstore合并red如上；修后policy通过不代表后续Windows native关卡已验。生产Windows远程默认门仍关闭。

实际命令（CI树源码，应用解释器仍`/workspace/Easy-AI/services/backend/.venv/bin/python`；Python测试设置`PYTHONPATH=/workspace/Easy-AI-ci/services/backend/src`）：

| 命令 | 结果及边界 |
| --- | --- |
| 该解释器`-m pytest services/backend/tests/test_project_persistence.py services/backend/tests/test_persistence_files.py services/backend/tests/test_ssh_identity.py services/backend/tests/test_connection_manager.py services/backend/tests/test_windows_storage_contract.py services/backend/tests/test_windows_native_store.py -q` | **115 PASS/7 SKIP**，2.65秒，1项第三方弃用警告；Linux policy/ABI通过，7个Windows原生测试按平台未执行，不能当原生PASS |
| cwd `services/backend`，同解释器`-m pytest -q` | **610 PASS/8 SKIP**，40.19秒，1项Starlette/AnyIO弃用警告；源基线已含前片诊断15，不能与f1旧592PASS/1FAIL窗口直接混称。collection发生在末项并发回归加入前，故不宣称610包含该新项。真实训练集成及Windows native未执行，未用新skip隐藏关键失败 |
| 同解释器`-m pytest services/backend/tests/test_ssh_identity.py -k 'cold_cancel or concurrent_readers' -q` | 最终 **2 PASS/41 deselected**，0.49秒；cold route保留200/confirm422/auth503/sessionnull/environment503/close200、密码不回显、随后匹配工程的旧request仍retired，新request在平台门拒且禁止socket；8并发reader仅factory1次且返回同实例，无dial。cold与610重合，不能相加 |
| 独立只读复核 | 安全独跑cold/installer **2 PASS/80 deselected**，0.40秒，并另实际8并发核factory；测试审查独跑persistence/FIFO **13 PASS**，1.36秒。均与上述窗口重合，不累加；无新明确未关闭P1/P2，未编辑/安装/SSH/Actions |
| 原venv `python -m ruff check .`、`ruff format --check .`、`mypy src`（cwd CI树/backend） | **PASS**，84 Python文件格式与strict mypy47源码；日志`/tmp/easyai-ci-python-check.log`。隔离树不带原WIP合同，验证对应本源码SHA |
| 原venv `python -m PyInstaller --noconfirm --onedir --name easyai-sidecar --hidden-import easyai.services.environment_service --hidden-import easyai.security.windows_store --paths src`加原python-task.mjs完全相同resource add-data清单与main.py | **PASS**，Linux冻结构建，日志`/tmp/easyai-ci-frozen-build.log`；已有venv只读复用，无uv同步/新env writer |
| `node scripts/test-frozen-ssh.mjs`、`node scripts/test-frozen.mjs`（CI树） | 均 **PASS**、EOF exit0。重新冻结的实际sidecar保留取消200、原错误码、鉴权/严格DTO/租约拒绝、资源字节、选择API/工程/黄金编译；日志`/tmp/easyai-ci-frozen-ssh.log`、`/tmp/easyai-ci-frozen-basic.log`。仅合成输入/本机loopback，无outbound SSH，不宣称Windows冻结通过 |
| `git diff --check`、原件hash/字节 | **PASS**；plan116185字节/hash `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`，原规格`5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README`befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`保持 |

另一次补测试命令误在backend cwd使用重复services/backend相对路径，append/format均报不存在且未写文件；随后正确路径加入并发回归并定向通过，未改生产保证来过测试。无隐藏FAIL：原用户日志四组、catalog red、cold/ancestor red均保留，Linux结果不能覆盖原Windows红。

最新已知远端仍是**d651a496fc2a2fd34ac1755556bbd06d73990032/run39147472362于17:00:51 UTC失败**（父级通知desktop4/check3 annotations，仅摘要，不能推断等同f1四根因）。f1ecaf7/run39144759022原完整日志中的四根因才是本片依据。Node20 action弃用/ubuntu迁移通知不是已证实根因。未重试被拒Actions端点、未重跑旧job；正常dev push后新SHA的既有有界CI自动执行，结果待新证据，不能预称绿。

本片不改main、强推、PR、部署/发布/Release、费用/凭据/安全权限；未实际Windows原生/NTFS/Windows冻结ABI/桌面/真实训练/SSH/数据下载/个人PC。真实资源条件未获授权前仍不执行。接下来优先读取新SHA CI结果、必要时修后续原生问题；原符号/报告WIP保留后继续其定向验证。完整B剩余代码、实际验证与外部条件另见`docs/remaining-critical-path.md`，代码预算是条件化低置信滚动估计，不是新交付日期或缩减B。

## 2026-10-18 — §16.3 冻结符号解释、原始错误入口与本地安全报告

源码完整SHA：`9f417561c75c49c163752a3ad21a76f4b4fc79d8`，基线`407da99effa8a46b492b79cc362f77025b5c7210`。父级要求同一实例继续并在CI等待期间完成原16修改/5新文件WIP的定向验证；这些WIP已先在CI快进前后以binary diff和5文件SHA逐字节核验保留，再完成本片实现、测试与独审后提交，未覆盖用户工作。未扩展v0.0.1，未把M7或B整体签成完成。

后端以已校验的旧RunSource.snapshot重建现有Python registry，返回无名称的对象摘要（固定kind/role/注册状态/旧blockId/workspace）和引用检查状态；不会使用当前工程替代。仅经原hash/frame/映射验证的NameError进入固定registered/unregistered/not_matched/ambiguous/unavailable解释；无可信映射不猜对象，registered及not_matched明确可能为生成器/依赖问题，不自动改引用或归罪学生。旧来源损坏时对象解释及计数降级不可用，原journal保持不变。

新增DiagnosticReport Python权威合同及生成schema/TS/declaration，固定12字段：版本、local_safe_summary、固定诊断code、runId/eventSeq/codeHash/projectRevision、precision/nameState/referenceCheck与两项对象数量。没有原始异常、用户名称、blockId、路径、host、用户名、密码或frame。认证只读GET `/api/v1/runs/{run_id}/diagnostics/{event_seq}/report`复用run_store/scoped_read/deliver门；真实HTTP barrier测试涵盖切换工程以及离开又返回ABA，迟到交付404，owned报告仍可读。不会上传或后端写报告文件。

Main与预览共用safeReport严格12字段白名单、枚举/计数/身份检查。renderer仅传runId/eventSeq，不能传任意报告或路径；只有显式导出才打开native SaveDialog。dialog后再次GET核scope、同报告与reportEpoch；项目open/create/import或dispose使旧请求过期。仅绝对native目标、writeFile flag=wx/mode0600，拒绝覆盖文件/链接；取消无写入。新Windows测试夹具用owned目录junction，避免要求Windows文件symlink特权；实际Windows行为仍待CI，本机仅Linux结果。

UI对象检查使用旧快照ID+workspace成员门，显示中性类别/角色/编号与注册状态，不显示任意名称或ID；打开时focus到对象标题，定位打开只读旧模型。卡片解释只显示固定nameState规则。报告默认无请求，必须显式预览，核run/seq/hash/revision后再显示固定JSON，导出另一次点击；报告错误独立，不改训练状态。新增“查看原始错误（仅本地）”按钮才挂载原结构化记录及私密内容提示，可收起；原文不进入报告，切换run清理原文与迟到预览。此功能不是全界面日志隐私清洗，也不认证恶意子进程。

实际命令，cwd `/workspace/Easy-AI`；应用现有`.venv`与workspace缓存复用，没有新环境writer：

| 命令 | 结果及边界 |
| --- | --- |
| `services/backend/.venv/bin/python -m pytest services/backend/tests/test_diagnostic_report.py services/backend/tests/test_runtime_diagnostics.py services/backend/tests/test_run_views.py services/backend/tests/test_run_scope_race.py -q` | **58 PASS**，5.63秒，1项第三方Starlette/AnyIO弃用警告；日志`/tmp/easyai-report-backend-final.log`。含新8报告/解释、原15帧定位、旧view/scope及新2报告ABA；真实owned文件、真实认证HTTP与线程barrier，无训练或outbound网络。不是旧CI610全套重跑 |
| `pnpm exec vitest run apps/desktop/electron/diagnostic-report.test.mts apps/desktop/electron/workflow.test.mts apps/desktop/src/RunSnapshot.test.mts apps/desktop/src/runEvents.test.mts apps/desktop/src/FailureCard.test.mts` | **92 PASS**，2.55秒；日志`/tmp/easyai-report-targeted.log`。包括Main23安全报告与原workflow7、Snapshot42（新8）、reducer9、FailureCard11。拒私密字段/错误run/seq/hash/revision、原始错误单独opt-in、旧对象只读定位、不自动报告/导出、取消/过期/授权失效/内容变化不写、已有文件与链接内容不变。JSDOM/headless Blockly与native callback替身不算Electron实测 |
| 独立只读审查 | 后端报告/scope独跑 **10 PASS/25 deselected**，1.05秒；Main报告 **23 PASS**，285ms。前端新8项 **8 PASS/34 skipped**，1.28秒。窗口与上述58/92重合不累加，均无编辑/安装/Actions；有限源码审查无明确新增未关闭P1/P2 |
| `UV_CACHE_DIR=/workspace/.uv-cache UV_PYTHON_INSTALL_DIR=/workspace/.python XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache pnpm check` | **PASS**，TS/Main/测试TS、ruff/85文件格式、strict mypy47源码、合同生成漂移、真实Blockly fixtures、Prettier；日志`/tmp/easyai-report-check.log`。原WIP首次strict mypy两项返回dict推断失败已用显式dict[str,str]修正，没有关闭类型检查 |
| `pnpm --filter @easyai/desktop build`；同缓存`node scripts/python-task.mjs build` | 均 **PASS**，桌面静态assets与Linux PyInstaller onedir；日志`/tmp/easyai-report-desktop-build.log`、`/tmp/easyai-report-backend-build.log`。保留既有>500KB chunk提示，未启动Electron或修改CSP/权限 |
| `node scripts/test-frozen.mjs` | **PASS**，实际重新冻结sidecar从临时cwd启动，资源字节/鉴权/选择API/工程创建/黄金编译与EOF exit0；日志`/tmp/easyai-report-frozen-smoke.log`。不冒充冻结报告正向全链或原生SaveDialog/Windows ABI |
| `git diff --check`；原件SHA/字节 | **PASS**。plan116185字节/hash `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`，原规格`5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README`befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`保持 |

中途测试失败如实保留：首轮新后端7项6PASS/1FAIL，测试误把runtime source seq=1当journal最终seq=1，实际已有CREATED事件，report正确拒绝非runtime事件。夹具改用ingest返回的实际seq，缺失/非runtime请求仍404；修后7PASS，补坏图降级后新8并入58通过。没有通过放松report序号/类型门修测试。

CI精确绑定：本轮只调用既有`github_get_commit_combined_status`读取**407da99effa8a46b492b79cc362f77025b5c7210**，调用成功但`statuses: []`，没有可判定的check/desktop结果；不等于无workflow或绿。未访问/重试被拒Actions日志接口，未绕行或重跑job。上述空列表仅为状态接口当时的返回。随后父级通过已核认证通知邮件提供精确新结果：**407da99effa8a46b492b79cc362f77025b5c7210 / run39149608836于17:28:37 UTC结束，check SUCCESS（1m51s），desktop FAILURE（1m25s，2 annotations）**，来源 https://github.com/T1doo/Easy-AI/actions/runs/39149608836 。因此407整体CI已知未通过，不再状态未知；check成功也不替代desktop失败。缺剩余desktop首错步骤正文，根因未知，不能套用旧四根因或把d651旧失败当新结果。父级对273e752/407da99四项已独审有限接受；本执行器现有status接口未暴露失败步骤，不另走被拒Actions端点/日志或重复跑同SHA。Windows native/冻结的具体分项仍不能推断通过，不重跑同型本地矩阵冒充新平台结果。

NOT RUN：真实Electron/SVG/Monaco/原生picker和SaveDialog/课堂E2E、Windows/NTFS/冻结ABI、真实训练/MNIST/SSH/SFTP/上传/数据下载、环境安装/SDK协议、个人PC。Windows远程生产gate继续关闭。没有新拒绝或未知外部写入；407状态现已由父级认证通知明确为check绿/desktop红；剩余desktop失败正文缺失，既有Actions拒绝边界保持。正常dev分支源码+证据与状态更正提交一次推送，最终完整证据/远端SHA见交付；不改main、不强推、无PR/Release/部署/费用/新凭据/安全权限。后续新功能SHA的CI待验，407剩余desktop首错正文待证据，同时推进原M7.3本地教程/数值卷积或按父级安排独立冻结模块，完整B剩余见remaining-critical-path.md。

## 2026-10-18 — 父级P2：安全报告完整排他发布

源码SHA：`1eabc62ec6b1200614116d9d0ea894c77cccc576`，基线`4077a2d071f9c83ee9fa23372f84bcee51c4c70a`。父级在workflow.mts原L471–475指出直接writeFile最终路径wx只排他创建、不保证完整发布。M7.3当时仅只读核对、无待写内容，先完成此最小修复。

修前新增真实临时文件注入部分ENOSPC，**1 FAIL/1 PASS**，213ms，`/tmp/easyai-report-atomic-red.log`；最终目标真实遗留`{"reportVersion":`，不是凭假设改写。现在复用现有LocalWorkspace._create_file的“先完整落盘、再排他发布”约束：同目标父目录创建私有mkdtemp、wx0600打开report.partial、完整writeFile→sync→close，核暂存目录/普通文件BigInt dev/ino且inode非零，再checkCurrent(epoch)，最后fs.link至不存在的最终目标。link不支持则拒绝，没有rename/copy覆盖fallback；**任何路径都不unlink最终目标**。清理仅匹配本次目录/文件身份的暂存项，不recursive rm、不清除无法核实或已替换项；清理异常不吞原写入/发布错误，也不撤销已成功发布。最后stat→link仍存在同UID并发窗口，本地导出不是恶意同UID进程安全沙箱；未借此扩大Windows支持或权限。

独审中发现并关闭暂存替换P2：首版仅cleanup核身份，sync后替换staged会把replacement bytes发布。补发布前同一身份/类型门及成功写后替换回归；独审原sync后替换夹具复验为拒绝、目标不存在、替换文件保留。没有通过无条件unlink清理未知内容。

实际命令（cwd `/workspace/Easy-AI`）：`pnpm exec vitest run apps/desktop/electron/atomic-report.test.mts apps/desktop/electron/diagnostic-report.test.mts apps/desktop/electron/workflow.test.mts`最终 **38 PASS**，377ms，`/tmp/easyai-report-atomic-final.log`（新8+原23+workflow7，不与前片92累加）；含部分写失败/原目标无半份并可同路径重试、其他写入者目标保留、完成暂存后发布冲突、sync失败、替换暂存+原error保留、scope写后失效、完成暂存替换拒绝、unsupported link不降级。独审新两项各1PASS/7skipped，原sync替换夹具另验，无剩余本P2。`pnpm --filter @easyai/desktop check`、`pnpm exec tsc -p tsconfig.tests.json`、`pnpm --filter @easyai/desktop build`、`git diff --check`均 **PASS**；日志`/tmp/easyai-report-atomic-check.log`及`/tmp/easyai-report-atomic-build.log`。只Main文件实现变化，未重跑后端/冻结/训练矩阵。

合同数目经Python `DiagnosticReport.model_json_schema(by_alias=True)`、schema properties、safeReport keys和独审独立枚举确认仍为**12字段**（前段12记载正确，不改成13）：reportVersion、scope、code、runId、eventSeq、codeHash、projectRevision、precision、nameState、referenceCheck、objectsTotal、registeredTotal。schema生成有**8 required + 4 defaults**（reportVersion=1、scope=local_safe_summary、两counts=null）；TS对应四项optional表示Pydantic可补默认的输入形态，认证GET使用完整model_dump(by_alias=True)响应始终包含全部12项，safeReport有意只接受完整响应、不补缺字段。未改变权威合同/生成器或降低白名单。

NOT RUN：Windows实际hard-link/NTFS/原生SaveDialog/Electron、断电后目录持久性、真实训练/MNIST/SSH/下载。407da99/run39149608836仍check SUCCESS/desktop FAILURE，2 annotations，剩余步骤正文未知，未盲猜或重试被拒接口；后续SHA CI分别待新证据。原件/README保持，无main/强推/PR/发布/部署/费用/凭据/权限变化。修复及本证据正常开发分支推送后续接M7.3，不因CI等候停独立功能。

## 2026-10-18 — M7.3 离线七主题与真实数值卷积教学纵切

源码完整SHA：`3cc9a0c2f016ea7ed51165967b5f4d49f9679bb4`，基线`960f95fae6c71dcd8c04ea3b10f488a4db90bcc8`（其源码`1eabc62ec6b1200614116d9d0ea894c77cccc576`已先关闭报告原子发布P2并正常推送）。父级要求先读全文§16.5/M7.3，复用现有编译与映射，完成教程入口→本地真实交互→关联积木/只读代码；没有重做训练链或用假指标。一个写入者，两个独审仅只读。

本地` tutorials/zh-CN/ `七篇精简Markdown覆盖Dataset/DataLoader、batch/epoch、卷积/池化/Flatten、loss/accuracy、训练/测试模式、设备/环境、错误/输出。静态catalog含relevantBlockTypes，21项manifest helpKey均有关联；通过Vite raw import随桌面assets打包，不加载任意文件/网址。仅文本与标题的React Markdown子集，不执行HTML、不创建外链或第四计算工作区。说明区分train_loss/test_accuracy、正式10轮与quick子集、固定seed的边界、默认不下载数据、只读代码、教师环境、CIFAR本机预检未闭合等现有能力。

`ConvolutionLab`固定5×5输入1～25、可编辑3×3核，每项有限[-10,10]；单通道互相关stride1/padding0/bias0，不翻核，明确非完整模型/训练引擎。九个合法窗口随前后按钮或输出格选择，实时计算九项输入×核、求和与全部3×3输出；核改变立即全量重算，无效/空值隐藏旧结果，重置不改工程。纯算术单元测试全1输入/全1核全部窗口=9，改一个核项后=10；非对称核检验不翻转，固定输入九项/完整输出与小数运算有独立预期，不生成曲线。

App有显式离线教程入口，所选真实Blockly积木有“查看此积木教程”入口；本工程关联积木采用固定manifest标签和稳定ID，遍历有界500项，导航只改视觉tab/选中状态、不edit或保存工程。代码仅消费已有Python CompileResult.sourceMap，要求非dirty、同revision且目标有映射；只读CodeView复用既有semantic高亮，不在JS生成代码、不自动compile/start。无工程/无块仍可读教程/计算；旧或未核实编译不猜代码。

教学副本调用原native选择目录+原项目创建服务，创建独立projectId而非替换原文件。dirty/saving/busy/activeRun/启动恢复未完成时禁用；创建入口再次核门，picker后核同draft引用/value且未dirty，取消不create。启动恢复门避免status已ready但current()未结束时先建新副本被迟到restore覆盖；不提供静默丢弃草稿。真实owned目录集成验证从教程入口、移动窗口到Main/FastAPI/Python实际编译，再定位Conv2d/显示其真实生成代码，整个阅读导航无save/start、原JSON字节不变，最后在新目录真实创建MNIST教学副本并清除旧代码视图。没有torch导入、训练或数据下载；SVG host/picker仍为替身，不能算真实Electron验收。

独审关闭两项P2：设备初稿无条件说CUDA→MPS→CPU，实际emit.py只在device=auto自动选择，显式绑定不可用会阻断。文案现明确auto与显式设备、不静默回退，workers/pin_memory实际值称运行记录，不冒称全写RunConfig。另一项tutorialTargets在停用块上continue丢失其next启用链；新增真实fixture red **1 FAIL/9 skipped**，857ms，`/tmp/easyai-tutorial-disabled-red.log`，随后先遍历next、只跳当前停用块与inputs，对齐Python decoder，独审原fixture ReLU layer-1仍可定位。

实际命令（cwd `/workspace/Easy-AI`；涉及原应用环境时使用`UV_CACHE_DIR=/workspace/.uv-cache UV_PYTHON_INSTALL_DIR=/workspace/.python XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache`）：

| 命令 | 结果及边界 |
| --- | --- |
| `pnpm exec vitest run apps/desktop/src/convolution.test.mts apps/desktop/src/TutorialPanel.test.mts apps/desktop/src/App.test.mts apps/desktop/src/RunSnapshot.test.mts` | 最终 **88 PASS**，4.16秒，`/tmp/easyai-tutorial-targeted.log`：数值12、教程内容/DOM/安全/停用链10、App23（原19+新4）、Snapshot43（原42+真实Blockly帮助1）。相关文件窗口，不与前片92、Main38或后端610累加。App真owned文件/Main/HTTP/Python编译器链如上；坏HTML只作为文本、全部manifest help覆盖、dirty/陈旧/缺失map代码禁用、kernel重算/无效无旧结果、取消不create、草稿仍按原800ms保存都受检 |
| 独立只读审查 | 数值 **12 PASS**，160ms；新App3 **3 PASS/19 skipped**，2.15秒；关闭设备与disabled两项 **2 PASS/8 skipped**；最终disabled/恢复门 **2 PASS/31 skipped**，1.05秒，另实际原fixture复验。均与88重合不累加；无编辑/安装/Actions/真实训练或SSH。有限源码审查无剩余明确新增P1/P2 |
| 同缓存`pnpm check` | **PASS**，TS/Main/测试TS、strict mypy47、85 Python文件格式、ruff、权威合同/真实Blockly fixture漂移、Prettier；日志`/tmp/easyai-tutorial-check.log`。本片未改后端/合同/依赖，没有重跑后端610或构建新训练环境 |
| `pnpm --filter @easyai/desktop build` | **PASS**，1.23秒静态assets，原>500KB chunk提示仍在，`/tmp/easyai-tutorial-build.log`。`rg -l '自动模式（auto）\|5×5 输入与 3×3 核\|Dataset 与 DataLoader' apps/desktop/dist/assets/*.js`命中index-CvX6AFyV.js，证明本地内容进入bundle，不代表已验安装包/Electron |
| `git diff --check`；`sha256sum 'docs/v0.0.0 plan.md' docs/v0.0.0.md README.md`；`wc -c 'docs/v0.0.0 plan.md'` | **PASS**；plan116185字节，SHA `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原规格`5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`，README`befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`不变 |

其他中途FAIL保留：首次App新3项 **2 PASS/1 FAIL/19 skipped**，测试未等待实际HTTP编译就点击仍禁用的代码按钮；改为await实际compile返回且断言runnable、按钮启用，没有降低映射断言或改生产编译流程。新restore门首次整窗 **87 PASS/1 FAIL**，状态已创建但漏接按钮/入口；补双门后最终88PASS，日志`/tmp/easyai-tutorial-restoring-red.log`。初数值/教程20与App3均被最终88覆盖，不累计。

NOT RUN：原阶段命令`pnpm test:e2e`及真实Electron/Blockly SVG/Monaco Worker/CSP/原生picker/课堂修复流；此前Electron sandbox拒绝边界仍保留，不重试或放宽系统权限。Windows/NTFS/冻结ABI、安装包资源、真实MNIST/10轮训练/SSH/取消重连/数据下载/包安装/个人PC均未执行。M7.3代码与定向纵切完成，不等于M7阶段或完整B验收。最新已获精确CI仍407da99/run39149608836的check SUCCESS/desktop FAILURE（2 annotations），剩余步骤正文未知；后续960f95f及本次最终新SHA CI未获证据，不套旧失败、不重复同SHA或绕被拒Actions日志。无新拒绝/未决写入、无main/强推/PR/Release/部署/费用/新凭据/权限变化。正常dev分支推送源码+证据后，下一项按原关键路径补M6.3受控安装合同/计划与M8打包骨架，先冻结独立合同，真实资源动作仍需具体授权条件。
## 2026-10-18 — M6.3 离线计划、确认 UI 与受控任务合同

源码完整 SHA：`b33adf7496114fe7260dd456b6ab74ba2038bc39`；基线 `b4c9cb9b6bb323d4b4468b1032e7696f726a7cea`。本片按原计划 §14 的组/单包、InstallPlan/fingerprint、确认、owned InstallJob/日志/取消/复检要求推进，由单一集成者写入、两位已有 worker 只读独审。合同与资源说明见 `docs/install-contract.md`。**本片不等于 M6.3 全部完成，生产执行通道明确关闭。**

交付 17 包/4 组固定目录及明确 importName（含 sklearn、PIL、cv2、skimage、pytorch_lightning），5 组 Python 权威 DTO/schema/TS，5 条固定认证 API 与 5 条固定 IPC，App 显式入口、单包/组多选、同一路径生成计划、未知版本/体积/阻塞提示、明确网络确认、查询/取消及固定隐私错误。读取/规划不创建训练目录、不导入 torch、不调 subprocess/network、不接收任意命令/路径/索引；teacher-existing 始终只读。

后端分配受控根下 UUID 新环境路径；UI 当前只提供新环境名称，不借用教师环境。easyai-cpu 的单包也展示完整既有 Linux x86_64 / CPython3.11 CPU 锁定闭包，来源+lock hash、基线 fingerprint、canonical planHash、十分钟 TTL；可选包未解析、平台不符或版本冲突阻断确认。体积明确为 wheel 下载/解包元数据估计，不当完整磁盘大小。确认严格要求两个布尔 true、同计划 hash，复核基线/来源；会话幂等 job，最多64计划。确认只登记 AWAITING_EXECUTION / INSTALL_EXECUTION_NOT_ENABLED，executionEnabled=false，无 execute API、无新环境创建。

内部 executor/inspector 接缝仅测试：owned marker/UUID/prefix、内核 lease 后再次核计划/基线，跨独立服务实例冲突阻断；取消等待适配器证明停止，unknown 保留 reservation/lease，关闭只发信号不谎称结束；固定生命周期日志最多128条。精确版本、nonce/prefix、Python3.11、核心 imports/tensor 合同全部满足才可 verified=true。fixture executor 只写 inventory JSON，**不是实际安装、导入或 tensor 执行证据**。无生产 inspector/provisioner/caller。取消/失败不承诺回滚、仍需复检；持久账本/重启恢复/真实日志/可选解析/远端安装仍缺。

实际命令（cwd `/workspace/Easy-AI`；pnpm check/PyInstaller 使用既有 `UV_CACHE_DIR=/workspace/.uv-cache UV_PYTHON_INSTALL_DIR=/workspace/.python XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache`，不创建/安装训练环境）：

| 命令 | 实际结果与证据 |
| --- | --- |
| `services/backend/.venv/bin/python -m pytest services/backend/tests/test_install_service.py services/backend/tests/test_local_api.py services/backend/tests/test_local_workspace.py -q` | **36 PASS**，2.99秒，1条第三方弃用 warning；`/tmp/easyai-install-backend-final.log`。其中新合同23项包括离线/no writer、严格输入/隐私、阻塞/TTL/hash/drift、HTTP确认取消、owned夹具执行/复检/未知停止/跨实例lease/日志上限；不是实际安装集成 |
| `pnpm exec vitest run apps/desktop/electron/install-workflow.test.mts apps/desktop/electron/workflow.test.mts apps/desktop/src/PackageManager.test.mts apps/desktop/src/App.test.mts` | **52 PASS**，5.17秒，`/tmp/easyai-install-targeted.log`；新Main14、原workflow7、包管理UI7、App24。包含真实Main/FastAPI计划→确认→取消且 training-environments 未创建；双击/陈旧响应/错误不自动重试、teacher只读、入口隐藏保留状态且不改工程 |
| 同缓存 `pnpm check` | **PASS**，TS/Main/测试TS、strict mypy49源文件、88 Python格式、ruff、权威合同/真实Blockly fixture漂移、Prettier；`/tmp/easyai-install-check.log`。首次因新测试 unused Path import **FAIL**，删除无用导入后完整重跑通过，未降低检查 |
| `pnpm --filter @easyai/desktop build`；同缓存 `node scripts/python-task.mjs build` | 均 **PASS**，静态构建1.43秒，PyInstaller16.76秒；`/tmp/easyai-install-desktop-build.log`、`/tmp/easyai-install-backend-build.log`。保留已有chunk大小提示；未构建安装包或运行Electron |
| `node scripts/test-frozen.mjs` | **PASS**，`/tmp/easyai-install-frozen-smoke.log`：新目录/来源/lock字节进入资源、临时cwd下冻结sidecar实际计划/确认/取消、execution仍关闭；原资源/native-selection API/project create/认证golden编译及EOF exit0仍通过 |
| `node scripts/test-frozen-ssh.mjs` | **PASS**，`/tmp/easyai-install-frozen-ssh.log`：原认证/严格DTO/隐私错误/scoped取消确认/lazy Paramiko/EOF exit0；合成输入，无外连SSH |
| 独立只读审查 | 后端先21 PASS、后来严格布尔新增2 PASS/21 deselected；前端/Main21 PASS。无剩余明确新增P1/P2，均与上面定向窗口重合，不累加。独审可选建议已明确SUCCEEDED是执行/复检合同，不冒称真实安装 |
| `git diff --check`；`sha256sum 'docs/v0.0.0 plan.md' docs/v0.0.0.md README.md`；`wc -c 'docs/v0.0.0 plan.md'`；`git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` | **PASS**；原件116185字节、SHA `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原规格 `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852` 不变。提交前远端dev=b4c9cb9、main=`5323f86232529efcfb52131168ad049f01b219f3`，无他人分支推进；最终正常push后再次核对 |

修前另发现 Pydantic Literal[True] 在当前严格模型仍接受整数1；新增精确输入测试 **2 FAIL/21 deselected**，`/tmp/easyai-install-consent-red.log`，改 before validator 要求 value is True 后23项通过，生成schema无漂移。原失败保留，不把初步18/21、独审窗口和最终36/52重复累计。没有为真实执行编造成功曲线或效果。

NOT RUN：实际 pip/conda/SDK 安装或许可、依赖联网解析、真实新环境/安装后import/tensor probe、教师共享环境修改、持久任务恢复、远端安装、数据下载、真实训练/MNIST、真实SSH/SFTP、Electron/原生picker/课堂E2E、Windows/NTFS/冻结ABI、个人PC。没有新增授权或尝试被拒动作。既有Electron sandbox及Actions日志拒绝边界保持，不绕路、不改安全权限、不重复同SHA CI。最新精确已知 CI 仍 `407da99effa8a46b492b79cc362f77025b5c7210` / run39149608836：check SUCCESS、desktop FAILURE（2 annotations），失败正文未知；本片新SHA CI **待证据**，不套旧根因。

下一项：在上述关闭的生产门后补实际 provisioner/executor/probe 与持久恢复，或推进独立 M8 打包骨架；真实执行需一次性owned目标、明确来源/下载预算及展示具体计划后的执行授权。常规代码可继续，不以这些实测条件阻断编译/合同。完整B仍未验收；无main/强推/PR/Release/部署/费用/新凭据或权限变化。

## 2026-10-18 — M6.3 受管进程与持久任务保守恢复

源码完整 SHA：`8881b581bfef7cd644571aa93627b662edbeafee`；基线 `3fbdd02e42ee63be4dfad8cd8d4af1ff81fbf03d`。父级有限接受上一片离线合同后，要求继续实际后端代码缺口，本轮实现最小进程/持久恢复纵切，不止重复合同。单一集成者、已有 worker 只读独审。未执行依赖安装/下载，生产入口仍关闭、executionEnabled=false、无HTTP execute。

| 原要求 | 本轮实际代码与剩余边界 |
| --- | --- |
| owned隔离新环境创建 | **代码仍缺**：新环境UUID/受控prefix/名称/计划已有，实际conda provisioner尚未实现，execute对newEnvironment仍拒绝INSTALL_PROVISIONER_NOT_ENABLED。没有创建真实环境或借教师环境 |
| 计划执行 | 新增内部ManagedInstallCommand，直接复用已有ManagedSupervisor/ManagedProcess，不再写一套Popen。OfflineWheelInstaller有固定目标Python `-I -B` + isolated pip/require-hashes/only-binary/no-index/已有本地wheelhouse/锁副本的代码，复制前重核来源hash；authorized默认false、无生产调用者。正向测试只捕获并compile固定脚本，**真pip未执行**。新环境provision、可选包解析及授权生产接线仍缺 |
| 日志/取消 | 复用现有持久EventJournal、独立POSIX进程组、取消升级、两管道排空；可选rawlog每stdout/stderr文件1MiB上限，满后继续排空；训练默认未改。包输出OS级重定向stderr，不能伪造stdout完成协议。已知非零退出=FAILED，未知停止保留lease/reservation。Windows安装进程适配器拒绝，未冒称支持 |
| 退出后真实reprobe | 新增固定ManagedInstallInspector独立目标Python，读完整锁定metadata版本、实际torch/torchvision/matplotlib imports、小CPU卷积及nonce/sys.prefix；本轮只在**既有应用venv子进程做负向只读探测**，实际torch缺失、tensor=false。成功链仍为真实stdlib子进程写合成inventory→原复检合同，不能算真实安装/训练Python成功。生产inspector没有接线，正向真实训练环境仍未验 |
| 重启恢复 | 确认、执行意图、VERIFYING、取消与终态写入每job EventJournal；执行意图fsync成功后才起进程，写失败关闭服务写入。进程重启可按已知jobId查询：未执行确认作废；未知INSTALLING/VERIFYING/CANCEL_REQUESTED恢复为STOP_UNCONFIRMED并隔离，不自动重放/杀旧PID。取得环境锁后重读其他持久意图，预先打开的第二实例也不能把app死亡后的flock释放当作子进程停止。**仍缺**活安装子进程重连、未知停止安全解除/重建、UI历史列表/保留策略；最多64持久目录，不做自动清理。不宣称完整安装恢复或断电目录项持久性 |

父级指出的TTL时序已修：环境锁后_fresh可能耗时，现在其后再次核TTL；写前记录后、最终executor调用前再核一次，跨期不启动。新增耗时inspector跨TTL和落盘跨TTL回归。新增复检barrier下取消，报告即使全部通过也不得发布verified。独审另复现P2：progress140次填满128日志后cancel只改内存，持久末条仍INSTALLING。现将状态写入与日志上限解耦，原fixture及新回归均确认CANCEL_REQUESTED落盘。额外独审接受跨实例持久意图门，无遗留明确新增P1/P2。

实际命令（cwd `/workspace/Easy-AI`；检查/打包使用原应用缓存 `UV_CACHE_DIR=/workspace/.uv-cache UV_PYTHON_INSTALL_DIR=/workspace/.python XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache`，不安装新依赖）：

| 命令 | PASS / FAIL / NOT RUN及证据 |
| --- | --- |
| `services/backend/.venv/bin/python -m pytest services/backend/tests/test_install_process.py services/backend/tests/test_install_service.py services/backend/tests/test_supervisor.py services/backend/tests/test_event_journal.py services/backend/tests/test_local_api.py services/backend/tests/test_local_workspace.py -q` | 最终 **103 PASS**，3.77秒，1条第三方弃用warning；`/tmp/easyai-install-execution-final.log`。新16项包含真实stdlib子进程/退出与取消、2.5MB双流限额/协议防混淆、write-ahead失败不启动、两处TTL/barrier取消、严格完整记录拒绝篡改、重启确认作废/未知停止隔离/跨实例锁消失保护、固定pip捕获、负向真实子进程probe。旧合同/共享supervisor/journal/API/workspace窗口均保留，不与上一片36累计 |
| `pnpm exec vitest run apps/desktop/electron/install-workflow.test.mts apps/desktop/src/PackageManager.test.mts` | **21 PASS**，2.19秒；`/tmp/easyai-install-execution-ui.log`，未改协议生成schema，实际Main/sidecar离线确认取消仍通过。UI改为明确本机持久状态、不自动恢复执行、当前仅显示本次打开任务 |
| 同缓存 `pnpm check` | **PASS**；TS/Main/测试TS、strict mypy50源文件、90 Python格式、ruff、合同和真实Blockly fixture漂移、Prettier；`/tmp/easyai-install-execution-check.log` |
| 同缓存 `node scripts/python-task.mjs build`；`pnpm --filter @easyai/desktop build` | 均 **PASS**；`/tmp/easyai-install-execution-build.log`、`/tmp/easyai-install-execution-desktop-build.log`。新内部适配器列为PyInstaller hidden-import，未引入torch应用依赖或执行模块安装。保留既有chunk提示，不是安装包/真实桌面验收 |
| `node scripts/test-frozen-install-recovery.mjs` | **PASS**；`/tmp/easyai-install-execution-restart.log`。临时cwd下真正启动冻结sidecar→确认202→EOF退出0→同storageRoot用新token/新进程重启→认证GET旧jobId返回CANCELLED/RESTART_CONFIRMATION_EXPIRED、verified=false、changesPossible=false，training-environments仍不存在；没有installer/conda |
| `node scripts/test-frozen.mjs`；`node scripts/test-frozen-ssh.mjs` | 均 **PASS**；`/tmp/easyai-install-execution-frozen.log`、`/tmp/easyai-install-execution-ssh.log`，原资源/认证golden compile/离线计划确认取消/SSH严格DTO及scoped取消/lazy Paramiko/EOF0门不降低，无出站SSH |
| 独立只读审查 | 初新11 PASS/0.29秒；满日志/写前失败/落盘TTL3 PASS/12 deselected/0.04秒；额外跨实例持久门1 PASS/15 deselected/0.04秒，均与最终103重合不累计。另真实2MiB stderr复验限额1MiB。没有worker编辑、真实pip/安装/训练/SSH |
| `git diff --check`；`sha256sum 'docs/v0.0.0 plan.md' docs/v0.0.0.md README.md`；`git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` | **PASS**；plan SHA `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`、原规格 `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`不变。提交前远端dev=3fbdd02、main=`5323f86232529efcfb52131168ad049f01b219f3`；提交后正常推送并复核 |

中途 **FAIL**：首次旧23项为22 PASS/1 FAIL，`/tmp/easyai-install-process-first.log`；旧跨实例测试在unknown之后才创建第二实例，新增恢复门已在confirm提前拒绝，原测试未能走到kernel锁。把第二实例建立提前至writer开始前，保留实际kernel锁冲突断言；另加恢复后confirm拒绝、预先实例在kernel lease消失后仍被持久门阻断，未删除或弱化保护。首次34项与中途102项被最终103覆盖，不累计。独审满日志取消复现先于修复，已如实记录。

NOT RUN：真实pip/conda依赖安装/下载/SDK许可、真实owned新环境provision、已安装torch的正向复检/卷积、真实MNIST训练/数据下载、真实SSH/重连、Windows安装进程/NTFS/冻结ABI、Electron原生对话框/课堂E2E、安装包发布/个人PC。无新拒绝或未决外部写入；既有Actions日志与Electron sandbox拒绝继续保留，没有绕路重试。最新精确已知CI仍407da99/run39149608836的check SUCCESS/desktop FAILURE（2 annotations，失败步骤正文未知）；本片新SHA CI另待证据，不套旧失败根因。

下一项按原M6.3继续受控conda新环境provision与授权生产接线，或推进独立M8包装；代码/可控进程测试可继续，真实安装必须另有一次性owned目标、来源/下载范围及具体计划确认。常规开发分支提交推送；无main/强推/PR/Release/部署/新增费用、凭据或安全权限。本片不是M6.3全验收，更不是完整B。

## 2026-10-18 — M6.3 新owned目录创建/半成品隔离与pip配置P2

源码完整SHA：pip修复 `3cd868d677a2d9f7a149145fad5787827dee5b5e`；创建流程 `de9be266cf2236083637495da1f83959abf669e0`；基线 `736b984b57861499f66f40a9b490080eb1f6bbb5`。父级要求接续新owned创建代码，同写入者保全工作期间先修父级独审pip P2，再完成独占FS创建→bootstrap→原安装/终检流程；生产API始终没有execute入口、executionEnabled=false。

**实际边界**：本片实现了受控UUID目录创建器与内部bootstrap adapter接线，**真实conda bootstrap adapter仍缺**；当前adapter合同要求接受已有空prefix。没有调用conda/venv/pip去创建实际Python环境；合成目录、标准库子进程与inventory JSON只证明生命周期/保护链，不证明真实依赖安装、import成功或张量效果。

OwnedCreation在应用根下建立独占environment-creations/UUID claim，绑定规范UUID、jobId、planHash和根dev/ino；使用原ProjectLock，锁后重核来源/基线/TTL与其他持久执行意图，write-ahead成功后才mkdir精确训练prefix。已有路径、旧claim、symlink、根或prefix身份替换均拒绝，绝不删除、覆盖、采用未知目录。bootstrap已停止且新nonce/sys.prefix/Python3.11通过，才写两字段owned marker；先在prefix内写独立origin并fsync目录。随后复用原executor、日志/取消、完整postprobe门，最后才发布ready；require_ready还必须读到同job/hash的持久SUCCEEDED/verified。取消/失败保留目录及日志；unknown继续持有lease/reservation，不以PID或锁文件推定停止。

独审实测关闭missing-claim **P2**：bootstrap成功但installer失败时，移走claim目录曾使partial被当作legacy owned接纳。现在新job的内部持久payload记录creationRequired=true（API DTO/schema不变；read_install_job兼容旧记录），缺claim时prefix origin或任一同environmentId新创建日志均拒绝legacy接纳；有claim还核origin、ready、prefix身份及持久终态。独审原fixture及“claim与origin同时移走、ledger仍在”均拒绝。origin的目录fsync用于先于owned marker的本地顺序，不把本片签成跨目录/断电恢复保证。legacy兼容只在没有新创建证据时适用。

父级pip **P2**：isolated仍读global/site/PIP_CONFIG_FILE，no-index不移除find-links配置追加候选，还可能读install.target/prefix。子进程现在在import pip前清除全部继承PIP_*并强制PIP_CONFIG_FILE=os.devnull；固定本地wheelhouse、require-hashes和目标Python不变，另核精确owned marker。现有base Python实际pip版本26.2.1的参数解析红绿测试：未修preamble时读入synthetic远程find-links与outside target；同一污染global/site/指定配置及环境变量，修后仅固定本地find-links、无target/prefix/extra index。只调用parse_args，不调用install.run、候选获取或网络，不改宿主配置。其他训练pip版本仍需兼容验证；测试机无既有pip时明确SKIP，不能冒称通过。官方依据：[pip配置及devnull语义](https://pip.pypa.io/en/stable/topics/configuration/#pip-config-file)，[isolated定义](https://pip.pypa.io/en/stable/cli/pip/#cmdoption-isolated)。

实际命令（cwd `/workspace/Easy-AI`；check/PyInstaller沿用 `UV_CACHE_DIR=/workspace/.uv-cache UV_PYTHON_INSTALL_DIR=/workspace/.python XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache`）：

| 命令 | 实际结果/证据与范围 |
| --- | --- |
| `services/backend/.venv/bin/python -m pytest services/backend/tests/test_install_process.py -k polluted -q` | **1 PASS/16 deselected**，1.25秒，`/tmp/easyai-pip-config-boundary.log`；实际pip26.2.1只读解析红绿，如上；包含在最终窗口，不累加 |
| `services/backend/.venv/bin/python -m pytest services/backend/tests/test_owned_creation.py services/backend/tests/test_install_process.py services/backend/tests/test_install_service.py services/backend/tests/test_local_api.py services/backend/tests/test_local_workspace.py -q` | 最终 **73 PASS**，3.86秒，1条第三方弃用warning，`/tmp/easyai-owned-final.log`。新创建20项、进程17、原合同23及API/workspace13；其中真实stdlib子进程在合成prefix写文件并退出，另真实取消30秒等待子进程并核process_exited/partial保留/无marker，均没有训练环境创建。其余含精确marker、来源/指纹变化、bootstrap身份、最终复检取消、unknown保锁、claim缺失、inode替换、symlink外写拒绝、半成品不可用/ready不单独授信 |
| 同缓存 `pnpm check` | **PASS**；strict mypy51源文件、92 Python格式、ruff、TS/Main/测试TS、合同与真实Blockly fixture漂移、Prettier；`/tmp/easyai-owned-check-final.log` |
| 同缓存 `node scripts/python-task.mjs build` | **PASS**；`/tmp/easyai-owned-build.log`。PyInstaller实际包含新创建模块依赖，不安装新依赖或torch |
| `node scripts/test-frozen.mjs`；`node scripts/test-frozen-install-recovery.mjs` | 均 **PASS**；`/tmp/easyai-owned-frozen.log`、`/tmp/easyai-owned-restart.log`；冻结资源/认证golden编译/离线计划确认取消/EOF0，以及新内部持久metadata下真进程退出再重启查询旧job、确认作废、不创建训练环境，验证旧记录兼容与资源路径。未重跑未改的真实桌面/SSH/训练矩阵凑数字 |
| 独立只读审查 | 初新15 PASS/0.14秒并复现missing-claim P2；关闭后 **19 PASS/0.13秒**，无剩余明确新增P1/P2。与最终73重合，不累加；最终第20项是另补真实stdlib取消用例。worker未编辑、安装、创建conda/venv或联网 |
| `git diff --check`；`sha256sum 'docs/v0.0.0 plan.md' docs/v0.0.0.md README.md`；`git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` | **PASS**；plan仍116185字节/hash `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原规格 `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`不变。推送前远端dev=736b984、main=`5323f86232529efcfb52131168ad049f01b219f3`，无他人分支推进；最终普通dev push后复核 |

中途FAIL如实保留：首55项 **52 PASS/3 FAIL**，`/tmp/easyai-owned-targeted.log`；半成品确已被拒绝，但缺marker抛原始FileNotFoundError，新增测试要求固定ValueError，现_owned统一转INSTALL_ENVIRONMENT_FORBIDDEN，不放宽保护。首次check **FAIL**，`/tmp/easyai-owned-check.log`，新test多余Path import，删除后完整检查通过。旧55/59与独审窗口均被最终73覆盖，不累计。两个独审P2修前复现如上，不把早期通过当完整安全通过。

**CI最新证据更正**：父级核实认证邮件，`736b984b57861499f66f40a9b490080eb1f6bbb5` / **run39154349633** 于 **18:31:16 UTC completed，check SUCCESS、desktop FAIL，各2 annotations**，来源 https://github.com/T1doo/Easy-AI/actions/runs/39154349633 。中间3fbdd02/run39153498677曾双失败，但非最新；407da99仅历史。邮件没有失败步骤正文，根因未知，不能归因旧四类或本轮pip P2。未重跑同SHA、绕Actions拒绝或扩大权限；本片新SHA CI仍待独立证据。

NOT RUN/仍缺：真实conda bootstrap adapter、已授权生产执行接线、实际环境创建/依赖下载安装/新SDK或许可、真实目标pip版本全矩阵、正向训练环境import/tensor、未知停止安全解除/存活安装重连、任务历史保留UI、远端安装、数据/训练/MNIST、SSH/SFTP、Windows/NTFS/安装进程、真实Electron/原生picker/课堂E2E、安装包/发布/个人PC。没有盲解锁或删除未知目录，无新拒绝/未决外部写入。下一项优先实现并核审真实conda bootstrap适配器的固定命令与配置边界（仍不实际运行）及授权执行门，或按父级指定独立关键路径推进；完整M6.3和B均未验收。无main/强推/PR/Release/部署/费用/新凭据或安全权限。

## 2026-10-18 — M8 本机离线便携布局与冻结启动定位

源码完整SHA：`7b91c46bc4634065b253fab4c27714fb71ab8656`；基线 `866a2d6eb2b1dde11e4d5a5fe71705961d171189`。父级要求转向原M8交付，不再无限扩安装合同。读取原M8.2/M8.4、支持平台与remaining-critical-path后，发现electron-builder没有安装/锁定，Main也只找checkout/.venv，已有pnpm build只产出Vite与PyInstaller。未尝试联网安装新工具/接受协议；保留builder缺口，复用已有Electron44.9.0缓存与PyInstaller做实际本地目录产物。单写入者，已有worker独审，无额外writer。

新增 `pnpm package` / `package:verify` / `package:notices` 与6项独立Node打包测试（也接入pnpm test）。仅同宿主Linux x64，核Electron固定版本、ELF64/x86_64、12项源/frozen辅助资源hash一致后复制。输出必须不存在；不覆写、递归删除或修改缓存/系统，不运行安装器/签名/发布。复制只允许普通文件/目录，拒绝symlink与特殊文件，保留可执行位但不附加setuid。仅纳入编译assets/Main/preload、冻结sidecar/全部_internal、白名单离线文档、七教程及示例JSON；不复制checkout/.venv本体、数据、运行或机器绑定。manifest最后生成，记录全部相对文件、bytes/SHA256/mode，校验额外内容、损坏、缺失/陈旧资源与路径遍历；它不是数字签名或来源认证。

Main新增 backendLocation：packaged只执行resources/backend/easyai-sidecar（Windows路径骨架.exe），args=[]，不回退开发Python/PATH；开发模式保留原venv/-m。startBackend仅多一个Main内部argv参数，原鉴权token仍只经stdin，健康检查、EOF/退出等待不变，Renderer不能选择命令。原sandbox/contextIsolation/webSecurity等设置未动。electron-builder.json是dir目标/resource/notice配置骨架、publish=null，无实际builder执行证据。

**独审P1修复**：首产物保留入口名electron，Electron44.9.0按basename判app.isPackaged=false，会选错开发后端。原test-portable只传true掩盖条件，不能算窗口启动通过。核[官方固定版本源码L855–882](https://raw.githubusercontent.com/electron/electron/v44.9.0/shell/browser/api/electron_api_app.cc#L855-L882)后，产物内排他link复制入口为easyai、核原inode后只unlink本次复制的electron，缓存保持不动；manifest/verify/builder.executableName/文档同步。新fixture核产物有easyai且无electron、缓存仍有electron。原本地产物保全为 `dist/easyai-0.0.0-linux-x64-pre-review`，不是交付候选；未设ELECTRON_FORCE_IS_PACKAGED或降sandbox。独审有限接受关闭，无剩余明确新增P1/P2。真实Electron运行仍NOT RUN。

最终本执行器产物：`/workspace/Easy-AI/dist/easyai-0.0.0-linux-x64/`，入口`easyai`，约**344 MiB**，**312文件**。manifest `/workspace/Easy-AI/dist/easyai-0.0.0-linux-x64/package-manifest.json`，SHA256 **`5f26ba7bb27917e717faec81c69d98ea97e3e39064ac4490b3e65fcc012fd937`**。此目录被gitignore，不进入源码提交；未上传或发布。resources/backend含独立Python冻结环境，resources/offline含teacher-setup/release-checklist/更新的developer-guide/install-contract、七教程和示例，resources/notices保留现有许可材料与未完成说明；Electron LICENSE/LICENSES.chromium.html保留根目录。许可inventory共**50项（JS依赖图7，应用Python环境43，含dev包）**，缺许可文本的easyai-backend明确列出；项目自身许可证未声明，精确冻结/native/system库义务未审全，**legalReviewComplete=false / distributionReady=false**。不擅选项目许可证，不宣称已有分发授权或完整SBOM法律审核。

实际命令（cwd `/workspace/Easy-AI`）：

| 命令 | PASS / FAIL / NOT RUN与证据 |
| --- | --- |
| `pnpm test:package`（`node --test scripts/package.test.mjs`） | 最终 **6 PASS**，`/tmp/easyai-package-fixtures-final.log`；临时fixture验证白名单、入口名/缓存、冲突保全、资源漂移先拒绝、symlink/无完成manifest、篡改/多文件/遍历、版本/架构。非Linux x64明确SKIP，此实现不冒称其他平台可用 |
| `pnpm exec vitest run apps/desktop/electron/backend-location.test.mts apps/desktop/electron/backend.test.mts` | **6 PASS**，968ms；`/tmp/easyai-package-launch.log`，固定packaged Linux/Win/mac路径映射只是代码测试、不是这些OS支持证据；原开发启动协议/失败处理仍通过 |
| `pnpm --filter @easyai/desktop build` | **PASS**；`/tmp/easyai-package-desktop-build.log`；静态assets/Main编译，既有chunk提示保留。复用上一片已建PyInstaller且逐项hash核source，不重复重冻/训练矩阵凑数字 |
| `pnpm package`；`pnpm package:verify` | 最终均 **PASS**，312文件；`/tmp/easyai-package-build-final.log`、`/tmp/easyai-package-verify-final.log`。实际复制缓存Electron+冻结backend、离线文档与许可；不联网或接受新协议 |
| `node scripts/test-portable.mjs` | **PASS**；`/tmp/easyai-package-smoke-final.log`。先核最终manifest/入口名，再加载**包内编译的Main backendLocation/startBackend**，给不存在checkout路径，用resources内真实冻结exe及独立临时state/project完成认证创建/实际golden Python编译、catalog执行关闭、EOF exit0。无依赖checkout/.venv启动；仍在同一宿主且由Node测试驱动，**不是无Node干净机、真实Electron窗口或app.isPackaged运行态验收** |
| `pnpm package:notices` | **PASS**；`/tmp/easyai-package-notices.log`，离线准备`dist/package-notices`供未验builder配置引用，拒绝覆盖。未运行/安装electron-builder |
| 原缓存同 `pnpm check` | **PASS**，`/tmp/easyai-package-check-final.log`；TS/Main/测试TS、strict mypy51、92 Python格式、ruff、合同/Blocklyfixture漂移、Prettier。只改打包/Main定位及文档，无后端业务变更，未重跑73/103等历史窗口 |
| 独立只读审查 | 初fixture6 PASS/386ms并指出basename P1；修后入口fixture **1 PASS/219ms**，与最终6重合不累计；未执行Electron/安装/训练/SSH，有限审查无剩余明确新增P1/P2 |
| `git diff --check`；`sha256sum 'docs/v0.0.0 plan.md' docs/v0.0.0.md README.md`；`git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` | **PASS**；原plan116185字节/hash `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`、原规格 `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`不变。推前dev=866a2d6、main=`5323f86232529efcfb52131168ad049f01b219f3`，最终普通dev push后再核 |

首版6项/复制/包内后端smoke曾通过，但未覆盖P1，不能据此称初包可启动；此次保全后重建和复验是因该实质新修复，不叠加计数。本轮没有新增工具拒绝或未知外部写入。electron-builder未安装/锁定且无本轮新依赖安装授权，**实际builder dir/NSIS/安装器NOT RUN**，仅配置与notice输入就绪；既有Electron sandbox拒绝仍不重试、不使用--no-sandbox/特权修复；真实桌面/干净机、Windows/NTFS、macOS/MPS、课堂/性能/签名/许可证完整审核、SSH/MNIST/数据下载/训练、真实conda bootstrap/安装、活安装重连/unknown安全解除/个人PC均NOT RUN。资源复制不替代M8.2“至少一个平台包在干净目标机真实运行”。

最新已核CI仍父级认证的 `736b984b57861499f66f40a9b490080eb1f6bbb5` / run39154349633，18:31:16UTC completed，check SUCCESS、desktop FAIL，各2 annotations；失败步骤正文缺失，根因未知，不能套旧四类或归因本轮打包。866a2d6及本轮新SHA无可判定CI证据；不重跑同SHA或绕被拒Actions端点。下一项优先取得剩余desktop精确首错证据、完成真实安全桌面/干净机验证，并在明确工具依赖/许可证授权后补electron-builder实际构建；并行独立原M5/M6代码缺口继续保留，完整B未验收。无main/强推/PR/Release/部署/费用/新凭据或权限变化。

## 2026-10-18 — M5 私钥认证的正常用户入口（合成验证）

源码完整SHA：`8b58fd3befeb25d6a1a02955cea0f4397d7806ba`；基线 `d6bab57f2af80eb26d880c0fd855d23b532917cb`。按父级明确范围补私钥入口；单一写入者，既有worker独立只读审查。没有读取、配置或上传真实用户密钥，没有实际SSH、agent扫描、环境安装或训练。代码入口说明见 `docs/private-key-auth.md`。

UI明确选择密码/私钥，口令可空；Main原生picker独占选择路径，Renderer仅能提交既有项目/身份/目标scope及口令，不能提交任意路径。Main限定普通非链接文件、64KiB、fd身份/大小/mtime、严格UTF-8，finally关闭fd并清零临时Buffer。取消picker、项目/后端变化和迟到返回不能发送凭据或发布会话。新增固定鉴权HTTP路由、内存SecretStr输入DTO（不导出为可持久化合同）；公开连接method增加private_key，继续沿用原独立host确认、单用grant、target/revision、pin、deadline、cancel tombstone及五分钟lease。接续运行只扩method枚举，保留project/user/endpoint/fingerprint约束。私钥不进工程/概要/报告/日志，SDK handler继续释放秘密引用；不可变字符串、HTTP/IPC及SDK内部内存不能保证硬擦除。

**独审P2修复**：初版64KiB文件界限不能约束OpenSSH bcrypt成本，267字节合成容器可声明rounds=0xffffffff；原超时不能强杀工作线程内的KDF。只读审查以禁用decoder的spy验证，不实际运行高成本KDF。修后在SDK前解析并校验单key/容器边界，只允许none/空KDF或aes256-ctr/cbc+bcrypt、盐16–64字节、rounds 1–64，且只选择对应算法一个decoder。0/65/0xffffffff在decoder前固定拒绝，实际合成加密Ed25519可往返。原running/BUSY门保持到工作线程退出；仍不宣称硬实时crypto取消，不降强度/重写用户密钥。有限独审关闭此P2，无剩余明确新增P1/P2；其3 PASS窗口与最终测试重合，不累加。

实际命令（cwd `/workspace/Easy-AI`，使用既有锁定缓存）：

| 命令 | PASS / FAIL / NOT RUN与证据 |
| --- | --- |
| `services/backend/.venv/bin/python -m pytest services/backend/tests/test_private_key_auth.py services/backend/tests/test_connection_manager.py services/backend/tests/test_ssh_identity.py services/backend/tests/test_ssh_run_coordinator.py -q` | 最终 **111 PASS**，5.20s、1条第三方弃用warning；`/tmp/easyai-key-backend-final.log`。覆盖内存合成RSA/加密Ed25519、KDF成本前置拒绝、固定错误/秘密排除、HTTP鉴权与严格DTO、取消/host变化阻断、SDK handler释放、私钥lease接续运行。socket外连禁用 |
| `pnpm exec vitest run apps/desktop/electron/private-key-workflow.test.mts apps/desktop/electron/session-workflow.test.mts apps/desktop/src/AuthenticatedPanel.test.mts` | **27 PASS**，1.15s；`/tmp/easyai-key-main-ui-final.log`。临时非真实key文件、原生picker注入、无身份不选取/发送、选择中取消及project变化、非普通/大文件/编码格式拒绝、UI显式选择/口令清空/迟到结果丢弃；不是实际窗口picker |
| `pnpm check` | **PASS**；`/tmp/easyai-key-check-final.log`。TS/Main/测试TS、strict mypy52文件、94 Python格式/ruff、合同及真实Blocklyfixture漂移、Prettier |
| `node scripts/check-contracts.mjs` | **PASS**；`/tmp/easyai-key-contracts.log`。仅公开AuthenticatedConnection的method合同同步生成；秘密输入不加入导出工程合同 |
| `node scripts/python-task.mjs build` | **PASS**；`/tmp/easyai-key-frozen-build.log`。既有PyInstaller重冻应用后端，新模块经实际import纳入；未安装工具或训练依赖 |
| `pnpm --filter @easyai/desktop build` | **PASS**；`/tmp/easyai-key-desktop-build.log`，既有bundle体积提示保留 |
| `node scripts/test-frozen-ssh.mjs` | **PASS**；`/tmp/easyai-key-frozen-ssh.log`。真实冻结sidecar的SSH鉴权/DTO/固定错误/取消与scope/环境拒绝/lazy Paramiko，新私钥route合成请求验证且无outbound SSH；EOF exit0 |
| `git diff --check`；原件bytes/hash；`git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` | **PASS**。plan116185字节及SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`、旧规格 `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`均未改；推前dev=d6bab57，main=`5323f86232529efcfb52131168ad049f01b219f3`，普通dev push后另核 |

中途FAIL如实记录：首baseline命令误指不存在test_ssh_client.py，exit4/未执行测试，改正确test_ssh_identity.py。新测试初4 PASS/1 FAIL因API Local fixture缺runs=None；修后路由才被真实覆盖。check先后暴露可选method TS比较、fixture Ruff重名/未用import、struct.unpack Any返回strict mypy、UI literal类型，均修正并由最终check覆盖。后端倒数一次110 PASS/1 FAIL是SDKcleanup合成Transport.auth_timeout=0，与实际connect设置预算不符；测试设1模拟真实初始化，生产保护未放宽。旧109/110及独审窗口不与最终111累加。

NOT RUN/范围限制：真实用户密钥、真实SSH/远端训练/数据上传/运行中远端同步/重连、实际原生picker/Electron窗口、Windows/NTFS/干净机、环境安装/数据下载/MNIST/训练/个人PC均未执行。既有sandbox及Actions端点拒绝不重试、不绕过。旧M8便携目录仍对应7b91c46且**不含本轮功能**，未重打包、上传或发布；许可/精确来源绑定、干净Windows及distributionReady/legalReviewComplete仍未验收。源码/静态build不等于完整M5、M8或B通过。

最新精确CI证据仍父级认证的 `736b984b57861499f66f40a9b490080eb1f6bbb5` / run39154349633（18:31:16UTC completed，check SUCCESS、desktop FAIL，各2 annotations），失败步骤正文缺失、根因未知；本片新SHA无可判定CI证据。不重跑同SHA/绕拒绝/猜根因。下一项沿原M5补数据上传/运行中远端同步的受控代码与合成测试，真实SSH及训练需明确最小条件授权；同时等待desktop首错证据。无main/强推/PR/Release/部署/费用/新凭据或权限变化，无本轮新增拒绝或未决外部写入。

## 2026-10-18 — CIFAR10 本机结构预检与安全构造阻断

源码完整SHA：`a292187c2f8be0529da60633d344357d2fab7e34`；基线 `146c9b38ae7765bd755c2fa61d330e266d6e5697`。按父级新指示继续原D10/§9.1/M6.1数据前置，读取原计划与现有MNIST本地读取、编译/start/环境报告路径；不下载/解压数据、不安装包、不读取真实数据、不执行训练或pickle。单写入者root，既有worker独立只读设计/代码审查。

交付：Main授权data selection→保存工程编译IR→CIFAR固定目录/七文件双split初检→固定未就绪报告→本机start同门拒绝。文件仅读2字节前缀，检查非链接普通文件、fd/路径身份、size/mtime、重复inode、粗大小；不会把貌似protocol2的恶意reducer执行或转成READY。新增CIFAR_FORMAT_INVALID/SAFE_PROBE_REQUIRED固定错误与UI说明。合成fixture为稀疏文件且故意含恶意字节，不是CIFAR数据。编译输出合同实测CIFAR双split、三通道Conv、2048而非MNIST1568、download=False。未改原编译语义：plan§460只要求角色/输入格式/类别一致，撤回一度拟加的“MNIST/Fashion同名”约束；最终lower源码无差异，测试只补CIFAR与IDX格式混用拒绝。

**准确未完成/阻塞**：冻结训练profile torchvision0.25.0官方CIFAR10构造在download=False时仍先全train/test MD5，再pickle.load批次/meta；官方固定版本 https://raw.githubusercontent.com/pytorch/vision/v0.25.0/torchvision/datasets/cifar.py 。直接构造目标与本轮禁止不可信pickle、原计划§9.1禁止全数据散列预检无法同时满足，**该动作未执行，是安全设计/计划兼容裁决待定，不是新增工具拒绝或执行结果不明**。当前七文件初检不足以证明完整性/shape/dtype/label；完整布局也始终data.ok=false/SAFE_PROBE_REQUIRED，不能开始本机CIFAR训练。原远端probe同类构造风险同步阻断为unsafe_format_blocked/ok=false/空sample摘要，公开DatasetCheck合同及生成物同步；无正向远端data binding。生成Bundle原CIFAR调用依然未验，不能把本片当作任意pickle运行授权。详见 `docs/cifar10-preflight.md`；未自换数据格式、许可、哈希白名单或反序列化器冒称官方适配器通过。下一步先落实安全解析/执行与原全哈希限制的兼容方案、独审后再闭合官方构造；真实数据/环境/桌面另需明确条件，当前不用以下载或修改共享环境解除这个代码设计阻塞。

**独审P2及修复**：新data checkpoint可抛PROJECT_REVISION_CONFLICT，却被数据ValueError处理吞掉，旧选择Python探测仍启动一次，最后scope才拒绝；独审仅用合成probe计数复现1次。修后catch先核scope、解释器前再核scope，revision/ABA立即退出。独审新增2 PASS/12 deselected/0.30s，原复现重新跑返回冲突、probe调用0，关闭P2；相关初42 PASS窗口与最终120重合不累计，有限独审无剩余明确新增P1/P2。

实际命令（cwd `/workspace/Easy-AI`）：

| 命令 | PASS / FAIL / NOT RUN与证据 |
| --- | --- |
| `services/backend/.venv/bin/python -m pytest services/backend/tests/test_cifar_preflight.py services/backend/tests/test_local_preflight.py services/backend/tests/test_local_workspace.py services/backend/tests/test_lowering.py services/backend/tests/test_compilation.py services/backend/tests/test_environment_probe_payload.py services/backend/tests/test_environment_service.py -q` | 最终 **120 PASS**，2.09s、1第三方弃用warning；`/tmp/easyai-cifar-backend-final.log`。固定布局/缺split/meta/异常格式/超限/链接/FIFO/别名/取消、鉴权HTTP selection及start未建Run、实际编译文本契约、无远端CIFAR构造调用、stale checkpoint不探测。全为合成文件/模块，不是训练 |
| `pnpm exec vitest run apps/desktop/src/LocalPreflight.test.mts apps/desktop/electron/backend.test.mts` | 最终 **11 PASS**，2.11s；`/tmp/easyai-cifar-ui-final.log`，包含结构未就绪UI说明及原React→Main→真实本机sidecar检查链，不是Electron窗口/真实数据 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache node scripts/check-contracts.mjs`；同环境变量 `pnpm check` | **PASS**；`/tmp/easyai-cifar-contracts.log`、`/tmp/easyai-cifar-check-final.log`。复用既有缓存且强制offline，无依赖解析联网/安装；TS/Main/测试TS、strict mypy53、96Python格式/ruff、合同/真实Blocklyfixture漂移、Prettier |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache node scripts/python-task.mjs build`；`pnpm --filter @easyai/desktop build` | 均 **PASS**；`/tmp/easyai-cifar-frozen-build.log`、`/tmp/easyai-cifar-desktop-build.log`。实际重冻应用后端与编译桌面，新模块/远端probe纳入；既有bundle体积提示保留，不是新便携包或窗口启动 |
| `node scripts/test-frozen-ssh.mjs` | **PASS**；`/tmp/easyai-cifar-frozen-ssh.log`，既有冻结路由/鉴权/strict DTO/固定错误/cancel与scope/环境拒绝/lazy Paramiko、EOF exit0；仅合成请求无outbound SSH |
| `git diff --check`；原件bytes/hash；`git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` | **PASS**。原plan116185字节/hash `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`、旧规格 `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`不变；推前dev=146c9b3、main=`5323f86232529efcfb52131168ad049f01b219f3`，最终普通dev push后另核 |

中途FAIL/修正：首次未设UV_CACHE_DIR的合同生成因默认`/home/agent/.cache/uv/CACHEDIR.TAG`只读失败，没有依赖安装或合同产出；改用已存在本执行器workspace缓存并强制offline后成功，不是绕过审批拒绝。首UI **9 PASS/1 FAIL** 是原错误文案断言仍要求“IDX”，而固定missing错误现在同时用于CIFAR，改为准确通用文案断言，新增CIFAR未就绪说明由最终11覆盖。后端首117、后118及独审42/2与最终120均不叠加；P2修前复现不隐去。pnpm check最终通过，无降低门或删测。

NOT RUN：官方CIFAR安全构造/完整性及样本摘要正向验收、真实CIFAR/MNIST训练/指标、数据下载/环境安装、真实SSH/上传/重连、原生picker/桌面/Windows/干净机/个人PC；M6或B未验收。旧M8本地产物固定7b91c46，不含私钥及本片新功能，未重打包上传发布；distributionReady/legalReviewComplete仍false。最新精确CI仍父级认证736b984b57861499f66f40a9b490080eb1f6bbb5/run39154349633（check SUCCESS、desktop FAIL各2annotations），新SHA暂无可判定证据，首错缺失/根因未知，Actions与sandbox既有拒绝不重试、不绕过。无本轮新增拒绝/未决外部写入，无main/强推/PR/Release/部署/费用/凭据/权限变化。

## 2026-10-18 — 完整代码 Bundle 的桌面导出入口

源码完整SHA：`90dd6a905452011b33d73fa0642e85b3dc2b9ad7`；基线 `d2ac2bf2ba5562a85276a2a856f894a8a1cda492`。父级明确保持CIFAR门并继续独立原功能；先核D12/§8代码导出/§12.3.1/M2.4/M6.4/TST34及现有export_bundle，确认后端生成器存在但桌面仅工程JSON。复用原导出器，不重写编译器、训练入口或环境writer；单写入者root，既有worker只读独审。

新增“导出已保存代码 Bundle”：只允许当前已保存、可编译且revision匹配的工程，单独保留原JSON草稿导出。固定Main channel只接projectId/revision/programHash；路径仅由Main原生选择已有父目录，Renderer不能提交路径。picker前后和回执前核session、epoch、backend；取消picker不写，revision/ABA/backend变化不发送导出。后端从saved snapshot重新实际编译、核hash，再复用持有目录身份的local_directory、新UUID独占子目录及排他文件写入；不合并/覆盖已有目录。沿用原POSIX能力门，不新增Windows不安全路径回退。

Bundle含train.py、5个辅助模块、source-map、program.ir、README/ENVIRONMENT及本次可移植project.easyai.json保存快照；snapshot也入hash清单。共用导出器在内容同步后才用临时manifest排他发布bundle.json；返回仅7个公开字段、目录basename和三hash，无本机路径。清单不是数字签名。磁盘/身份/同步错误不返回成功，不自动递归删除；开始写入后没有强制取消，服务中断或返回身份失效可能留下完整/部分目录，UI明确提示保留检查、重试创建新目录。不是事务性目录回滚，不用目录存在当作完成。见 `docs/code-bundle-export.md`，teacher/developer/release/remaining同步。

实际命令（cwd `/workspace/Easy-AI`）：

| 命令 | PASS / FAIL / NOT RUN与证据 |
| --- | --- |
| `services/backend/.venv/bin/python -m pytest services/backend/tests/test_bundle_export.py services/backend/tests/test_compilation.py services/backend/tests/test_local_workspace.py services/backend/tests/test_local_api.py services/backend/tests/test_local_ssh_storage.py services/backend/tests/test_run_service.py services/backend/tests/test_ssh_run_coordinator.py -q` | 最终 **119 PASS**，7.27s、1第三方warning；`/tmp/easyai-bundle-backend-final.log`。覆盖鉴权/严格DTO、保存快照与全部文件hash、原件/sentinel不变、stale revision/hash/current无输出、父链接/目标冲突拒绝、写入失败保留部分目录且无manifest/Run；共用bundle改动额外核本地RunService及SSH协调合成回归。初67被119覆盖不累计；无训练/真实SSH |
| `pnpm exec vitest run apps/desktop/src/App.test.mts apps/desktop/electron/bundle-export.test.mts apps/desktop/electron/workflow.test.mts` | 最终 **36 PASS**，4.59s；`/tmp/easyai-bundle-ui-final.log`。UI savedcompiled/cancel/dirty/不启动Run，Main fixedargs/nativepath、revision/backend/ABA和foreignreceipt拒绝，以及真实Main→鉴权sidecar→Python编译→独占目录文件的导出链。没有Python/data选择、生成代码执行或Electron窗口 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache node scripts/check-contracts.mjs`；同环境变量 `pnpm check` | **PASS**；`/tmp/easyai-bundle-contracts.log`、`/tmp/easyai-bundle-check-final.log`，新BundleExportResult三生成物；TS/Main/测试TS、strict mypy53、97Python格式/ruff、合同/真实Blocklyfixture漂移、Prettier。复用锁定缓存，未安装或联网解析 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache node scripts/python-task.mjs build`；`pnpm --filter @easyai/desktop build` | 均 **PASS**；`/tmp/easyai-bundle-frozen-build.log`、`/tmp/easyai-bundle-desktop-build.log`；冻结后端和桌面实际编译，原bundle体积提示保留。不是重新打便携包或真实窗口 |
| `node scripts/test-frozen-ssh.mjs` | **PASS**；`/tmp/easyai-bundle-frozen-ssh.log`，冻结路由/鉴权/strictDTO/固定错误/cancel与scope/环境拒绝/lazyParamiko，EOF exit0；无outboundSSH。新增exportHTTP正向链在源码sidecar中实际验证，不把该SSH smoke称作冻结export正向证据 |
| 独立只读复核 | 无新增明确P1/P2；实际临时目录smoke核11个文件hash/snapshot/receipt/原文件不变、无Run。最终另跑写失败 **1 PASS/5 deselected/0.26s**，部分目录保留且manifest不存在；与作者窗口重合不累计。未编辑或执行生成代码 |
| `git diff --check`；原件bytes/hash；`git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` | **PASS**；原plan116185字节/hash `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`、旧规格 `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`未改。推前dev=d2ac2bf、main=`5323f86232529efcfb52131168ad049f01b219f3`；普通dev push后另核 |

中途FAIL：首UI组合 **35 PASS/1 FAIL**，`/tmp/easyai-bundle-ui.log`，新增测试对fixture原plain unsupported函数使用spy断言；改为显式vi.fn包装后最终36通过，没有修改生产保护/删测。早期Main11与独审smoke不叠加。新增Python测试2个未用import由ruff check --fix在执行前清除，随后完整check通过。无本轮新增审批/工具拒绝或未决外部写入。

NOT RUN/仍缺：TST34在已有训练第三方库环境脱离应用实际执行导出代码；真实MNIST/CIFAR/学习效果、nativepicker/Electron窗口、Windows/干净机/课堂、环境安装/数据下载、真实SSH/数据上传/运行中远端同步；旧便携产物固定7b91c46不含私钥/CIFAR结构/新Bundle入口，未重新打包上传发布，distributionReady/legalReviewComplete仍false。本片完成代码导出入口及受控文件链，不等于M6.4或B整体验收。

CIFAR状态不变：父级已向用户请求仅冻结官方adapter自带完整性检查的窄化例外，答复未到前不解除SAFE_PROBE_REQUIRED/unsafe_format_blocked。原§9.1L664只限制预检全数据散列，不被扩成禁止独立完整性校验；文件来源信任不能靠目录名/2字节/选目录或MD5单独建立，普通子进程/-I不是恶意pickle沙箱。本轮不继续无限解析器研究或执行任何真实构造。下一独立原功能是M5显式数据上传的受控任务/协议与合成测试、运行中远端产物同步；真实网络另需明确范围。最新精确CI仍父级认证736b984b57861499f66f40a9b490080eb1f6bbb5/run39154349633（check SUCCESS、desktop FAIL，各2annotations），新SHA无可判定证据，失败正文/根因未知；既有Actions/sandbox拒绝不重试或绕过。无main/强推/PR/Release/部署/费用/新凭据/权限变化。


## 2026-10-18 — M5 显式数据上传最小闭环（合成 SFTP）

源码完整SHA：`13625edc01d70d35923871f794256bdbb87461b5`；基线 `18255a555ecbfc9982dbf9147f44a0ce872a12b8`。按父级明确范围沿原D14/§13.3/M5补上传，不与运行中远端产物同步混合；root单一写入者，既有worker独立只读审查。先核原计划、README、原规格、现有SFTP/session/目标及路径规则，未覆盖用户工作；功能说明见 `docs/data-upload.md`。

已实现 Main原生目录选择→绑定当前已保存project/revision、认证lease/profile/host及预算的只读计划→明确布尔true确认→受控后台任务/字节进度/取消→远端两轮回读SHA256及最后完成manifest。Renderer只传selectionId，不能提供本地/远端任意路径或命令；目标固定应用管理目录的新UUID slot。预览仅元数据，不做数据全散列或Dataset构造；256文件/256MiB源数据/100MiB单文件/120秒硬上限，枚举及manifest也有界。拒绝链接/特殊文件、不安全权限、隐藏项/常见key文件；这是文件边界保护，不是内容脱敏器。标准SFTP非覆盖rename，不覆盖教师目录，不隐式上传、不自动Run或绑定Dataset，dataReady始终false。

取消响应不是完成证明：只关闭本任务channel；未知清理保留I/O门及CLEANUP_PENDING，不释放给新任务。已完成终态不因worker退休/项目失效降级。Main在confirm异步请求前保留owned意图，失去ACK仍可读取/取消；停止先到后端则写内存tombstone，迟到confirm不会spawn。失效计划不能借owned记录恢复新写授权。SDK异常只映射自有固定错误类型，伪装合法前缀也不回显；取消watcher的close异常同样捕获，无原始异常stderr。

独审曾指出并复现P2：整数1被当确认、未知channel关闭误报CANCELLED并早放门、终态线程竞争降级、SDK合法前缀异常泄漏；均修复并由针对测试覆盖。最终只读复核确认ACK/提前取消边界，无剩余明确新增P1/P2；其backend1 PASS/20 deselected及Main/UI2 PASS/5 skipped与作者窗口重合，不累加。独审不代表真实SDK/服务器验收。

实际命令（cwd `/workspace/Easy-AI`）：

| 命令 | PASS / FAIL / NOT RUN及证据 |
| --- | --- |
| `services/backend/.venv/bin/python -m pytest services/backend/tests/test_data_transfers.py services/backend/tests/test_remote_artifacts.py services/backend/tests/test_owner_transport.py services/backend/tests/test_connection_manager.py services/backend/tests/test_local_ssh_storage.py services/backend/tests/test_local_api.py services/backend/tests/test_cifar_preflight.py -q` | 最终 **159 PASS**，10.67s，1第三方弃用warning；`/tmp/easyai-transfer-backend-final.log`。临时本地源+API兼容合成SFTP，禁socket外连；含真实鉴权HTTP→workspace→上传worker链、完整回读/marker、拒绝/损坏/取消/未知清理/终态竞争/提前取消tombstone/异常脱敏，以及旧artifact/owner/lease/CIFAR门回归 |
| `pnpm exec vitest run apps/desktop/electron/data-transfers.test.mts apps/desktop/src/DataUpload.test.mts apps/desktop/src/App.test.mts apps/desktop/electron/workflow.test.mts apps/desktop/electron/session-workflow.test.mts` | 最终 **53 PASS**，4.23s；`/tmp/easyai-transfer-main-ui-final.log`。固定IPC/严格scope与预算/原生选择注入/预览确认/真实字节DTO/终态校验/失ACK取消与迟到完成丢弃；不是实际窗口picker |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache node scripts/check-contracts.mjs`；同环境变量 `pnpm check` | **PASS**；最终`/tmp/easyai-transfer-check-final.log`。新增5DTO各3生成物，TS/Main/测试TS、strict mypy58、103Python格式/ruff、合同/真实Blocklyfixture漂移、Prettier；复用锁定缓存，无新依赖安装或联网解析 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache node scripts/python-task.mjs build`；`pnpm --filter @easyai/desktop build` | 均 **PASS**；`/tmp/easyai-transfer-frozen-build.log`、`/tmp/easyai-transfer-desktop-build.log`。实际重冻后端并编译桌面，既有大chunk提示保留；不等于便携重打包或窗口启动 |
| `node scripts/test-frozen-ssh.mjs` | **PASS**；`/tmp/easyai-transfer-frozen-ssh.log`。冻结路由/鉴权/strict DTO/固定错误/scoped cancel/lease与环境拒绝/lazy Paramiko，EOF exit0；合成请求，无outbound SSH；不冒称冻结上传正向验收 |
| `git diff --check`；`wc -c 'docs/v0.0.0 plan.md'`；`sha256sum 'docs/v0.0.0 plan.md' docs/v0.0.0.md README.md`；`git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` | **PASS**。plan116185字节/SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`、旧规格 `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`不变。推前dev=18255a5，main=`5323f86232529efcfb52131168ad049f01b219f3`；正常dev push后再核 |

中途FAIL如实保留：初新backend4 PASS/6 FAIL为合成Channel缺recv_stderr接口，补齐fixture后通过；早期ruff压缩语句/未用import与后续变量导入、mypy未注解/变量复用、生成DTO可选字段TS收窄及测试literal类型由check检出修正。UI请求计数guard一度放错catch被TS发现，移回poll。Main/UI曾52 PASS/1 FAIL：invalidate后的owned记录错误地也可用于新confirm，生产改为仅fresh plans可确认，owned只读/取消；测试未知ID使用全新UUID。独审发现的生产P2按上述修复，未降门或删测。旧156/157/158 backend、52/53及独审窗口均不与最终159/53累加。

NOT RUN/剩余：真实SSH/上传/服务器SFTP兼容性、真实用户目录/个人PC、实际native picker/Electron窗口、Windows/NTFS/干净机、真实数据/训练/环境安装/数据下载均未执行。当前计划/任务仅会话内存最多各16，无重启历史恢复、按manifest补缺文件、未知清理解除；部分专用目录保留，不自动删除/覆盖。SFTP v3无O_NOFOLLOW/openat/可靠fsync，不能保证抵御恶意同UID并发或崩溃耐久。源码及合成闭环不等于完整M5/B。下一独立项是运行中远端产物同步；持久历史/补传仍保留缺口。

CIFAR窄化完整性例外仍待用户答复，SAFE_PROBE_REQUIRED/unsafe_format_blocked未解除；上传SHA256不提供pickle来源信任。旧M8便携产物固定7b91c46，不含本轮及此前私钥/CIFAR/Bundle新入口，未重打包、上传或发布，distributionReady/legalReviewComplete仍false。Bundle文档澄清snapshot原样保留用户字段、导出器不主动收集数据/密钥，但不是秘密清洗器。

最新精确CI为父级认证 `d2ac2bf2ba5562a85276a2a856f894a8a1cda492` / [run39158015941](https://github.com/T1doo/Easy-AI/actions/runs/39158015941)，19:18:44 UTC，check SUCCESS、desktop FAIL，各2 annotations；无失败步骤正文，根因未知。本轮新SHA无可判定CI证据。既有Actions端点与Electron sandbox拒绝均不重试、不绕过，无本轮新增拒绝/未决外部写入。无main/强推/PR/Release/部署/费用/新凭据或权限变化。


## 2026-10-18 — 父级独审上传初始化 P2 修复

源码完整SHA `c3e43414827060c0a865560f1babcf8bbe1253a6`，基线 `cc7af38150efaa1346703eedb920a59b69a9c8d8`。父级只读独审确认：原实现data先mkdir后owner写入，取消/断线可留下无marker共享根，使新UUID上传也永久拒绝；这超出“单任务partial”的已知限制。修复只改初始化：独占 `.data-init-<transferId>` 完整写owner并回读，重核parent与authority后标准非覆盖rename发布data根；未知data根仍拒绝，旧暂存不认领、不删除。发布后ACK丢失也只留下完整可验证共享根，不宣称当前任务完成。

实际命令 `services/backend/.venv/bin/python -m pytest services/backend/tests/test_data_transfers.py -q`：**27 PASS**，1.33s，1第三方warning，`/tmp/easyai-transfer-init-fix.log`；新增5点覆盖mkdir后、半owner、owner回读、publish前/后的取消/中断，新UUID可完成且旧残留字节不变，既有未知目录sentinel拒绝仍通过。`UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm check` **PASS**，`/tmp/easyai-transfer-init-check.log`。独立只读针对复核 **5 PASS/22 deselected/0.21s**，与27重合不累计，确认关闭该P2，无新增明确问题。没有实际SSH/用户数据上传、新依赖或训练；仅后端两文件变动，不重跑无关UI/构建冒充新增证据。

工作区仅此修复和对应文档，正常dev提交推送；main与原件不改。SFTP真实兼容性、同UID恶意/崩溃耐久、重启恢复补传仍NOT RUN/未完成，CIFAR门与既有工具拒绝不变。下一项继续独立运行中产物同步，设计已由既有worker只读复核，尚未计为交付。


## 2026-10-18 — M5 运行中登记产物增量同步与独立暂停/恢复

源码完整SHA **`de9a0c2a1f53a894840da617330571653be21506`**；基线 **`4c318b12b4c61abb128b54d905d2efcf9996e621`**（此前上传初始化P2源码c3e43414827060c0a865560f1babcf8bbe1253a6已正常dev推送，父级及worker复核关闭）。按父级范围复用现有session/run identity、coordinator、manifest及安全remote cache；root单一写入者，既有worker只读设计/代码复核。说明见 `docs/live-artifact-sync.md`。

新owner仅在登记产物集合增长或sealed时，先排他发布内容寻址不可变manifest，再在owner-status引用digest/sourceSeq/eventsSha256；最多256次增长加最终1份、每份64KiB/256产物、总产物256MiB。coordinator从已提交原始JSONL前缀（含换行）核收据，不重序列化Event算hash；新receipt不可回退。客户端下载当前冻结收据及完全一致的已登记记录，核run/launch/host、bundle/source map和size/hash；不枚举任意服务器文件，不复制模型/数据目录。运行中只同步固定PNG/文本快照，增长日志仍走旧游标，单个登记model留最终sealed。旧无收据owner仍按原sealed协议，不改正在执行bundle。

增量cache按内容hash验证复用、拒绝旧sourceSeq覆盖新索引、已有记录元数据不可替换；不完整/损坏新文件保留旧index，未经提交不ready。Run新增可选字节状态，UI按秒显示本轮实际收到/核验/总量，已核验缓存可复用而收到0字节；无伪指标/剩余时长。运行中PNG ready仍syncState=pending、artifactsVerified=false，最终权重/图像和退出证明不放宽。新HTTP固定pause/resume路由与Main opaque runId，沿RunScope/generation提交门；暂停只关闭本次SFTP，不发送训练cancel/重发start，训练状态/日志继续读取。未知channel/取消watcher未退场则保留物理gate、cleanup_pending且禁止恢复。恢复发生在旧_sync返回前的竞争由保留该调用取消意图处理；切run的迟到UI回执丢弃。断线单列连接/同步状态，保留真实执行事实，需重新认证并显式接续，不自动新session或重跑。

实际命令（cwd `/workspace/Easy-AI`）：

| 命令 | PASS / FAIL / NOT RUN与证据 |
| --- | --- |
| `services/backend/.venv/bin/python -m pytest services/backend/tests/test_remote_run_api.py services/backend/tests/test_remote_artifacts.py services/backend/tests/test_portable_owner.py services/backend/tests/test_ssh_run_coordinator.py services/backend/tests/test_owner_transport.py services/backend/tests/test_connection_manager.py services/backend/tests/test_local_ssh_storage.py services/backend/tests/test_data_transfers.py -q` | 最终 **229 PASS**，29.22s，1第三方弃用warning；`/tmp/easyai-live-backend-final.log`。合成API兼容SFTP/禁socket，真实鉴权HTTP→RunService/coordinator→测试自有stdlib owner→原始前缀/immutable manifest→本机cache→PNG预览，训练未结束即ready；暂停/恢复退场barrier、读取旧清单不扩权、hash去重、model延后、半文件/旧index保全、scope切换及上传P2回归。结构PNG是fixture，不是训练/科学图表 |
| `pnpm exec vitest run apps/desktop/src/RunSnapshot.test.mts apps/desktop/electron/workflow.test.mts apps/desktop/src/App.test.mts apps/desktop/src/runEvents.test.mts` | 最终 **87 PASS**，5.32s；`/tmp/easyai-live-ui-final.log`。字节显示、文件暂停/恢复不调用训练cancel/resume、切run迟到回执、固定两route/ID与路径拒绝、原历史/运行UI回归；不是Electron窗口 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache node scripts/check-contracts.mjs`；同环境变量 `pnpm check` | **PASS**；`/tmp/easyai-live-contracts.log`、`/tmp/easyai-live-check-final.log`。Pydantic权威生成新Progress与Run/Observation/Checkpoint合同；TS/Main/测试TS、strict mypy58、103Python格式/ruff、合同/实际Blocklyfixture漂移及Prettier。既有锁定缓存，无依赖安装或联网解析 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache node scripts/python-task.mjs build`；`pnpm --filter @easyai/desktop build` | 均 **PASS**；`/tmp/easyai-live-frozen-build.log`、`/tmp/easyai-live-desktop-build.log`。实际重冻后端并编译桌面，原大chunk提示保留；未重打包便携目录或运行窗口 |
| `node scripts/test-frozen-ssh.mjs` | **PASS**；`/tmp/easyai-live-frozen-ssh.log`，固定route/auth/strictDTO/错误/scope/lease拒绝/lazy Paramiko，EOF exit0，无outboundSSH；不是冻结版正向SFTP验收 |
| 独立只读复核 | 初设计确定原始前缀、receipt先发布、单调index、独立暂停及终态门；代码针对 **5 PASS/59 deselected/2.91s**。最终移除mutable status重读、owned watcher join针对 **2 PASS/49 deselected/0.16s**，有限范围无明确新增P1/P2。与作者测试重合不累计，未编辑或实际SSH |
| `git diff --check`；`sha256sum 'docs/v0.0.0 plan.md' docs/v0.0.0.md README.md`；`git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` | **PASS**；原plan116185字节/hash `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`、旧规格 `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`、README `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`不变。推前dev=4c318b12b4c61abb128b54d905d2efcf9996e621，main=`5323f86232529efcfb52131168ad049f01b219f3`；普通dev push后另核 |

中途FAIL/边界修复如实记录：首次check运行runtime Ruff默认格式与项目config不同，改显式项目配置后通过；随后strict mypy检出optional observation、必填function恒真判断、fd writer变量类型复用，均修复。初UI **50 PASS/1 FAIL** 是新增测试对不存在cancel mock做spy断言，补明确vi.fn后通过。首pause/resume E2E恢复后仍pending，定位到用户可在旧取消调用返回前恢复，使旧分支误退出worker；修复保留cancel意图并加确定性退场barrier。扩大回归曾 **226 PASS/1 FAIL**：restart后cancel场景等待complete超时，最后CANCELLING/disconnected/syncerror，未保留精确throw栈，**不能宣称已完整定位该次根因**。后续设计修正移除新收据对mutable heartbeat的冗余SFTP重读（legacy sealed仍exact status），以已提交receipt+raw前缀/记录集合为权威，新增“不读mutable heartbeat”回归；restart/pause针对2 PASS。自审还补取消close watcher加入worker finally join，避免其晚于gate释放；阻塞close新测及最终229通过，独审确认边界。旧104/48/124/67、UI51/86及针对窗口不与最终229/87累加；没有删测、放宽终态或用重跑同SHA CI掩盖失败。

NOT RUN/剩余：真实SSH/SFTP SDK兼容、用户远端产物/数据下载、torch/训练/真实MNIST与学习效果、安装/下载、个人PC、native picker/Electron窗口、Windows/NTFS/干净机/课堂、跨进程断电与持久恢复均未执行。本轮新代码仍需真实目标机与长运行验收，不以一次合成回归消除此前未完整定位失败的全部不确定性。实时进度/暂停意图不构成重启恢复协议；上传持久历史/manifest补传/未知清理解除继续另列缺口。SFTP v3无nofollow/openat/fsync，恶意同UID替换和崩溃耐久不作保证。完整M5/M8/B未验收。

CIFAR完整性窄化例外仍待用户答复，SAFE_PROBE_REQUIRED/unsafe_format_blocked保持。旧M8便携包仍7b91c46，不含后续私钥/CIFAR/Bundle/上传/本片，未重打包上传发布，distributionReady/legalReviewComplete=false。最新已核CI仍父级认证d2ac2bf2ba5562a85276a2a856f894a8a1cda492/[run39158015941](https://github.com/T1doo/Easy-AI/actions/runs/39158015941)（19:18:44UTC，check SUCCESS/desktop FAIL，各2annotations），步骤正文缺失、根因未知；新SHA无可判定CI证据。既有Actions端点/Electron sandbox拒绝不重试不绕过，无新增拒绝或未知外部写入。下一项先由父级复核本片及CI精确首错，继续原剩余受控安装/恢复与真实验收依赖；无main/强推/PR/Release/部署/费用/新凭据或权限变化。


## 2026-10-18 — M5 同步固定诊断与重启取消定向故障注入（旧根因仍 UNKNOWN）

源码完整SHA **`00d969e2310d36fcc08b5f1039e4f17c5f0fac82`**，基线 **`cfddfb8dfee6938bf630fc07771c871f2415f5c5`**。按父级明确授权最小补诊断与定向验证，不扩安装/上传恢复，不执行真实SSH/下载/安装，不重跑大矩阵。root单写、既有worker独立只读审查；`docs/data-upload.md`原“运行中同步仍缺”滞后说明同步修正。

**旧失败准确状态：UNKNOWN，未关闭。** 原窗口226 PASS/1 FAIL，测试 `test_restart_is_inspect_only_fresh_auth_and_cancel_waits_actual_owner` 在test_remote_run_api.py原391行等待syncState=complete，wait_for原276行8秒后AssertionError；会话保留的末态为CANCELLING/disconnected/syncerror，remote.executionState=RUNNING、cancelState=acknowledged、artifactsVerified=false，字节0/0/0。没有底层失败阶段/异常栈；原始失败日志被后续同名命令覆盖，**证据已丢失，不能事后补造原件或恢复不存在的栈**。后续229绿、新注入或新诊断均不能完整归因该次旧失败，更不能以其他测试通过全验放行。此前确定的pause/resume旧调用返回竞争单独修复，不能冒充旧226P1F唯一原因。新协议移除mutable heartbeat重读、watcher join分别有独立边界测试，也不回溯当作该次已证根因。

交付：Pydantic权威新增ArtifactSyncFailure固定stage/code，Run.artifactSync分failure与cleanupFailure。snapshot/event_prefix、receipt_read/digest/records、cache_open、artifact_read/verify/commit、completion、channel/cache/watcher cleanup及真实core.poll有自有阶段；不能判断者SYNC_UNKNOWN/unknown，不解析合法字符串前缀。SDK只按异常类型归类IO/UNKNOWN，未读取或保存其str、secret、path、外部payload或栈。首失败与清理失败分别保留。规范应用日志新增artifact_sync_failed固定DTO事件，限定application、无sourceSeq/block、严格payload/枚举，runtime伪造拒绝。仅失败变化写入既有单写journal并持久化；实时字节不刷日志；显式新同步清当前诊断但历史事件保留。执行终态、auth/gate/manifest/hash/required artifacts门不放宽。

新增两个重启取消注入（receipt_read、cache_commit）可各自得到与旧会话同类CANCELLING/disconnected/syncerror，但固定stage不同；只证明**相同表象可由不同已知故障产生**，不证明旧根因。规范事件无合成secret/path；移除注入、重新认证显式接续后CANCELLED+synccomplete，未再发start，历史失败保留。原无注入重启测试仍原断言通过。其余定向覆盖digest/records拒绝、原始事件前缀、watcher阻塞退场、vendor合法前缀不泄漏、application-only事件。

**独审P2及修复**：本片初把sftp/channel/cache任意close异常都标channel_cleanup，独审只注入本地_Cache.close在实际释放后抛错，索引已发布却误标SSH通道失败。修后按资源新增cache_cleanup；failure/cleanup分开、不混淆已发布索引事实。新增参数化回归明确cache close失败可index存在，而channel close失败无index；未改变已有清理/物理门和训练状态策略。独审针对 **1 PASS/60 deselected**（`/tmp/easyai-cache-cleanup-review-bvQsHw.log`），确认该P2关闭、未发现新增明确P1/P2；此前独立12 PASS/66 deselected/3.52s与作者窗口重合不累计。此P2也是本片问题，非旧226P1F的追认解释。

实际命令（cwd `/workspace/Easy-AI`；验证命令均唯一日志名，shell `set -o noclobber` 防覆盖）：

| 命令 | 结果与保留原件 |
| --- | --- |
| `services/backend/.venv/bin/python -m pytest services/backend/tests/test_remote_artifacts.py services/backend/tests/test_remote_run_api.py -k 'fixed_sync_failure or receipt_event_prefix_failure or cancel_interrupt_worker or restart_is_inspect_only or restart_cancel_sync_fault or sync_diagnostic_event' -q` | 最终 **14 PASS/65 deselected**，5.42s、1第三方warning；`/tmp/easyai-diag-target-1792355628978-370186.log`，SHA256 `c57c2ccf90dce0a40ed1117141af7bd761717fef8cc6e9b0166fc2d18dd20f8f`。仅合成SFTP/自有stdlib child，禁止socket外连，不是训练/真实服务器证据 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache node scripts/check-contracts.mjs` | **PASS**；最终生成`/tmp/easyai-diag-contracts-1792355628978-370186.log`；Failure/Progress/Run/Event各3生成物，不手工维护双份合同 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm check` | **PASS**；`/tmp/easyai-diag-check-1792355660653-28e6f8.log`，SHA256 `af0ee9f3ffba3f13a2def63e89e3009e959fd5a24ae4ec6a855800fb2a4c996f`。TS/Main/测试TS、strict mypy58、103Python格式/ruff、合同/真实Blocklyfixture/Prettier；既有锁定缓存，未安装新依赖 |
| 独立复核命令 | `pytest tests/test_remote_artifacts.py -k 'fixed_sync_failure_stages and cache_cleanup' -q`，1 PASS/60 deselected，日志SHA256 `65d4ed981f668c036754cfb9de7b7b3bf2c8767866221232ab410d981d18b59d`。此前独立12项日志`/tmp/easyai-diag-independent-Cc0QnH.log` SHA256 `98d73a54aa1739c2f771fa9d51421314f081aa07471d633ce263543ec5637041`。不叠加为独立总量 |
| `git diff --check`、原件hash、`git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` | **PASS**。plan116185字节/hash dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43、旧规格5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190、README befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852未改。推前dev=cfddfb8，main=5323f86232529efcfb52131168ad049f01b219f3；普通dev push后另核 |

本片FAIL原件全部保全（均为合成内容，未把原始日志放公开仓库）：

- `/tmp/easyai-diag-target-1792355354176-86467b.log`：8 PASS/1 FAIL/50 deselected，cache commit注入错误地patch Protocol而非实际Posix实现；修测试注入目标，无生产门放宽。SHA256 `f2fdd551e7d9ef68b1b95c5c61fd70b39c89d73b2006453b1edf522cefd0f4db`。
- `/tmp/easyai-diag-target-1792355392353-754e86.log`：10 PASS/2 FAIL/65 deselected，新重启fixture漏接reopened._ssh_client，被No network socket stub拦截，未发生外连；补合成client。SHA256 `9222bc07bfb27cee40db91ded7ae5b529ac457380cce1c3496b20d4ddd4ee0ab`。
- `/tmp/easyai-diag-target-1792355419975-19fbff.log`：10 PASS/2 FAIL/65 deselected，**本片实现遗漏Event.type新枚举**，journal.append ValidationError使诊断错误转owner_poll/INVALID且syncState卡syncing；补枚举及application-only严格payload校验，并让仅core.poll标owner_poll，其他未定异常unknown。该根因有本片源码/定向证据，不回溯套旧226P1F。SHA256 `201a1bf2bb9e7f29375a874e5e8d761e70b6e46ca92692aade2ea8198e1c48af`。
- 修后12 PASS日志`/tmp/easyai-diag-target-1792355477805-421b53.log`、13 PASS日志`/tmp/easyai-diag-target-1792355524688-9597e0.log`均保留，被最终14覆盖范围、不累加；对应SHA256 `27d4d6929dcb5145a5e6b78e3d4851733a7ade7115ea99a569f8a208e94c6d88`、`472a9d14ac7fe348fb89fed3bd26cdc94347eb9b46bf16ce2a90089e148cc1e7`。

NOT RUN：全套/大矩阵、构建/冻结smoke（本片无打包验收）、真实SSH/SFTP/用户文件下载、桌面/Windows/干净机、环境安装/数据下载/训练/个人PC。CIFAR裁决仍待答、保护门不变；旧便携包仍未含本片，未重打包或发布。上传重启恢复/manifest补传、安装真实接线和真实验收依赖不混入；完整M5/B未验。旧UNKNOWN需后续精确证据，不由绿灯关闭。最新精确CI仍父级认证d2ac2bf/run39158015941，check SUCCESS/desktop FAIL、首错未知；本片无新CI判定，既有Actions与sandbox拒绝未重试/绕过。无本轮新工具拒绝、未知外部写入、main/强推/PR/Release/部署/费用/凭据/权限变化。


## 2026-10-18 — 父级诊断独审 P2：清理超时不得覆盖首错

源码完整SHA **`af0a3d74f5456c2a69acd5f010e60d305f50bc07`**，基线c564ebe128d1c156f6730de4cd2a36062c700db3。上传恢复尚未代码改动时，父级指出提前CLEANUP_UNCONFIRMED分支无条件写DEADLINE/CANCELLED并固定watcher阶段。先加确定性barrier：receipt/artifact读取已抛OSError，随后channel/cache close阻塞过deadline；修前 **2 FAIL/61 deselected**，确实把SYNC_IO_FAILED误覆盖DEADLINE。失败原件 `/tmp/easyai-diag-first-cause-red-1792355861715-1070bf.log` SHA256 `a05854925dd046a3099baf66138feca7ba6f2d89f3731c62d930d5c028987f8a` 保全。

最小修复只改诊断：首错记录与提前读同mutex，已有failures优先保留，不用等待超时覆盖已发生的IO错误；close_owned仅在锁内登记/清除资源阶段，实际close仍锁外，区分channel/cache清理；watcher关闭与join单独跟踪，无足够证据阶段保留unknown。CLEANUP_UNCONFIRMED控制结果不变，未知静止继续持有物理gate，不因诊断新字段放行；取消/训练/索引提交门未降低。

实际命令：`services/backend/.venv/bin/python -m pytest services/backend/tests/test_remote_artifacts.py -k 'first_failure_survives_deadline or cancel_interrupt_worker or fixed_sync_failure_stages' -q`，最终 **11 PASS/52 deselected/0.86s**，日志 `/tmp/easyai-diag-first-cause-final-1792355931836-f68d2d.log`，SHA256 `37c9c4cd69d39ea43ea002a3943a2066600174c3844111ca32e2d1cd4b641eb4`。此前修后11项日志 `/tmp/easyai-diag-first-cause-green-1792355892861-359b42.log`保留但不累计；同时间戳 `/tmp/easyai-diag-first-cause-check-1792355892861-359b42.log` 的offline workspace缓存 `pnpm check` **PASS**（之后成功路径两处close也包同一已检查helper，最终11再次覆盖）。未重跑大矩阵/构建。独立只读两个barrier+旧watcher **3 PASS/60 deselected/0.60s**，`/tmp/easyai-first-cause-review-P3MfbH.log` SHA256 `b6f2d417b187e9d05748d187ec450c124ffb2b762b3684fc788bef5a775e1181`，确认关闭此P2、无明确新增P1/P2；与作者窗口重合不累计。

旧226P1F特定根因仍UNKNOWN且原日志丢失，不把本次确定P2回溯当成它的已证原因。新验证均唯一noclobber文件，红/绿原件保全，无SDK原文/path/secret诊断。真实SSH/下载/安装/训练/桌面仍NOT RUN，CIFAR门不变，无新工具拒绝或未知外部写入。正常dev push，main和原件不改。接续原任务仍为上传本机持久恢复→显式重新选源/目标确认→只读inspect→同slot缺失文件补传；不自动网络或接管未知partial。


## 2026-10-18 — M5 上传持久历史与同slot缺失文件恢复（合成纵向闭环）

源码完整SHA **`84a7cd52e14129c44a3070023c462f940b6ebfc3`**；基线 `0c10ee07caf88177df2f2b25ffb6496822d3b591`。在既有显式上传之上，接通私有intent持久化→重启仅本机历史→新认证/主动重选源→只读inspect→新60秒计划明确确认→同slot仅发送缺失完整文件。单一集成者写入；复用既有worker独立只读审查，无新writer。不是M5/B完整验收。

持久记录固定应用私有目录、排他writer lock，先登记attempt再任何远端写；不存本机源绝对路径/selectionId/session/凭据，不写工程。相对文件名、hash和远端目标概要也属可能私密的元数据，见data-upload.md。上限16slot×16attempt，满额/未知记录/不确定持久化均拒绝，无自动淘汰/清理。新slot也先暂存完整intent再非覆盖发布。恢复绑定原project/target revision/endpoint/user/pin/home/UID，重新全SHA核原manifest；只读检查全文件而非信任complete marker。未知/冲突内容拒绝保留，精确known-attempt partial只识别不认领/读内容/覆盖/删除；不做任意字节续传。写前重核missing集合，最终全文件回读与marker收口。进度区分本次sent/reused；dataReady始终false，仍须独立Dataset probe/绑定，CIFAR保护门不变。

独审复现并关闭一项P2：旧wait_idle仅等job，在途prepare仍持SDK gate却先释放ledger，第二实例可取得writer lock。确定性屏障先红后绿：close发planning取消，wait_idle在workspace mutex外有界等待planning/job/SDK，超时保留writer lock；传输保留probe quiescence和cleanup_pending证据，未知不接管。没有用取消请求代替已静止回执。既有清理中job仍返回BUSY，不改变错误合同。

最终实际命令与结果（日志在执行器/tmp，合成内容未提交公开库；均唯一noclobber，不覆盖失败）：

| 实际命令 | 结果 / 日志 |
|---|---|
| `services/backend/.venv/bin/pytest services/backend/tests/test_data_transfer_recovery.py services/backend/tests/test_data_transfers.py -q` | **40 PASS/7.13s**；`/tmp/easyai-recovery-tests-1792357020069-3be862.log`。重启构造无网络、重选源/同目标/manifest、只读拒绝、unknown/冲突/marker伪完成、missing-only不改已有文件/partial、writer lock/篡改、planning关闭超时、持久化失败零远端写、inspect后源变化零调用及HTTP鉴权/历史/inspect/completed复用 |
| `pnpm exec vitest run apps/desktop/electron/data-transfers.test.mts apps/desktop/src/DataUpload.test.mts` | **9 PASS/2 files**；`/tmp/easyai-recovery-main-ui-1792357020069-3be862.log`。固定IPC、history不授写权、同slot新attempt、原生重选/只读核验/明确确认、旧授权失效 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm check` | **PASS**；`/tmp/easyai-recovery-check-1792357020069-3be862.log`；TS/Main/testsTS、strict mypy60、106Python格式/ruff、合同生成一致、真实Blockly fixtures、Prettier |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache XDG_CACHE_HOME=/workspace/.cache pnpm build` | **PASS**；`/tmp/easyai-recovery-build-1792357020069-3be862.log`；Main TS/Vite与PyInstaller，无新依赖；保留既有chunk大小提示，无Electron启动 |
| `node scripts/test-frozen.mjs` | **PASS**；`/tmp/easyai-recovery-test-frozen.mjs-1792357020069-3be862.log`；临时cwd实际冻结sidecar、资源/选择API/工程/黄金编译、受控包计划取消（execution仍关闭）与EOF exit0；不是冻结恢复正向全链 |
| `node scripts/test-frozen-ssh.mjs` | **PASS**；`/tmp/easyai-recovery-test-frozen-ssh.mjs-1792357020069-3be862.log`；冻结鉴权/strict DTO/固定拒绝/scoped cancel/lease/环境拒绝/lazyParamiko、EOF exit0，无外连SSH |
| 独立只读恢复集与两项补充守门 | **11 PASS/4.04s**，`/tmp/easyai-upload-owner-fix-review-9AWCJ8.log`；新增持久化失败及源变化 **2 PASS/11 deselected/0.24s**，`/tmp/easyai-upload-two-gates-review-K4s8eg.log`。合计范围与作者40重合不累计。P2关闭，无明确新增P1/P2 |
| `git diff --check` / 原件hash / `git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` | **PASS**；推前dev=0c10ee07caf88177df2f2b25ffb6496822d3b591、main=5323f86232529efcfb52131168ad049f01b219f3；正常开发分支提交，随后push再核。plan116185字节/hash dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43，旧规格5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190、README befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852均未改 |

失败与中间验证不隐藏、不累计：新恢复测试初稿10 ERROR系持久记录硬链接临时名删除改变ctime，采样顺序错误；改先remove/sync再采样。随后9 PASS/1 FAIL系writer lock原始BlockingIOError未归固定BUSY，已修。两次check FAIL系fixture导入shadowing的Ruff F811/F401，改别名后成功。planning红测1 FAIL确证提前释放；首次绿窗口37 PASS/1 FAIL是新检查遮盖既有BUSY码，调整检查顺序后38PASS，追加两项最终40PASS。所有原始日志保全，hash如下。

- `/tmp/easyai-recovery-build-1792357020069-3be862.log` SHA256 `ddd971fe7fe16d275addc3f00cb00a491002f2affd51ddb1721982ef63f26863`。
- `/tmp/easyai-recovery-check-1792357020069-3be862.log` SHA256 `aacb8c37ca0ed0c0340e5e61be4fd5f65f9dd8f3069869d74fe690a2fcbab5b8`。
- `/tmp/easyai-recovery-main-ui-1792357020069-3be862.log` SHA256 `2c29d1f9f56f8692aad2da1fd87692bc960fb85eb320165703c1845ec7070ca4`。
- `/tmp/easyai-recovery-test-frozen-ssh.mjs-1792357020069-3be862.log` SHA256 `22f2385a15cb8225eeb616e9ba80946a0d2640aa5451f6b05058ec08c85ebc44`。
- `/tmp/easyai-recovery-test-frozen.mjs-1792357020069-3be862.log` SHA256 `598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。
- `/tmp/easyai-recovery-tests-1792357020069-3be862.log` SHA256 `2abf9f621b5481574c2d9effecee3564f5f728bb519000c859a21ccf28c68b8e`。
- `/tmp/easyai-upload-owner-fix-review-9AWCJ8.log` SHA256 `fcab03affec201173435461d56ea6cd777c965956a28b2d8d1987cbaf0fabf21`。
- `/tmp/easyai-upload-planning-green-20261018-unique1.log` SHA256 `f2757546e3b35b502c9c206618b480b1bf9272c706edfa1cb1b1778374a963b4`。
- `/tmp/easyai-upload-planning-green-20261018-unique2.log` SHA256 `17a0c69e71f113c416d803ac931d52eb7c75718362fcc4740d9ec72fd360f4e7`。
- `/tmp/easyai-upload-planning-red-20261018-unique1.log` SHA256 `686a5ad8ace221065ec315996a249bb67c4554282f92ea694cac4246eb6affbe`。
- `/tmp/easyai-upload-recovery-baseline-1792356344439-e6afb6.log` SHA256 `5c05af19d63fdb4af46d905a373a01e6d47bbe025c1dc9c52f7883b386daf8dd`。
- `/tmp/easyai-upload-recovery-check-1792356571403-725a8d.log` SHA256 `8c5e8c5e8f720f484c5b7e17b983a0348c30298ab3765beee18509ccf60c421b`。
- `/tmp/easyai-upload-recovery-check-1792356643407-9673fc.log` SHA256 `43754785d399b6bf269ef6dd0f8286b6e1c344bce65d7ab0507b4ddc91fe0b63`。
- `/tmp/easyai-upload-recovery-check-1792356731026-44e6aa.log` SHA256 `aacb8c37ca0ed0c0340e5e61be4fd5f65f9dd8f3069869d74fe690a2fcbab5b8`。
- `/tmp/easyai-upload-recovery-contracts-1792356344439-e6afb6.log` SHA256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。
- `/tmp/easyai-upload-recovery-new-1792356472024-365e84.log` SHA256 `f789d3b792867a0154b1dcf084abcd24e9aa5c337388a6df4046c4d970a33165`。
- `/tmp/easyai-upload-recovery-new-1792356501925-bb412f.log` SHA256 `5becc483d8ccfeea2df1408360306fb337381dc10f5e3498eb0b4e33bc58d1e7`。
- `/tmp/easyai-upload-recovery-tests-1792356571403-725a8d.log` SHA256 `1c0c4f7f4670321a696c84d1fc7f410545649db0458b579af136a0c4ad304d6d`。
- `/tmp/easyai-upload-recovery-tests-1792356731026-44e6aa.log` SHA256 `9b51b32f55956c45f35a9235510f4366b083f688330ac1b18a93c3e9aa1ac02d`。
- `/tmp/easyai-upload-recovery-ui-1792356643407-9673fc.log` SHA256 `1da2a72bbd1b12b94276ae10b01aad49425d3777d6b6cee575ed8bd8232b094b`。
- `/tmp/easyai-upload-two-gates-review-K4s8eg.log` SHA256 `ca89921a236f4c5e4e2361f61baada16ced4d70cfdec493a937dcb3de2282af3`。


旧226 PASS/1 FAIL的确切根因仍 **UNKNOWN**，原始日志丢失，不重建或用本轮绿灯/新P2回溯关闭。NOT RUN：完整大矩阵、真实SSH/SFTP及跨进程/目标机故障、真实用户数据/原生picker/Electron/Windows/干净机、训练环境安装/下载/训练/个人PC。旧344MiB便携目录仍source7b91c46，不含本片，未重打包/发布；distributionReady/legalReviewComplete均false。既有Actions读取/桌面sandbox拒绝未重试或绕过，最新父级认证CI仍d2ac2bf2ba5562a85276a2a856f894a8a1cda492/run39158015941：check SUCCESS、desktop FAIL各2annotations，无step body/rootcause，不推断本片CI。无新工具拒绝、未知外部写入、main/强推/PR/Release/部署/费用/凭据/权限变化。

下一项仍按原M5收口：盘点与准备正常test:ssh入口及目标机验证的最小授权条件；真实服务器、环境安装接线/训练、CIFAR裁决不能由合成绿灯放行。旧UNKNOWN需新精确证据而非猜测。


## 2026-10-18 — 原M5阶段 `pnpm test:ssh` 显式集成入口（真实执行仍NOT RUN）

源码完整SHA **`ac477dd4dc5dbcca6821a4e9251d3219907e3e1e`**，基线 `3af519b65c3dae1100e40afc124b86178048638f`。父级有限接受上传恢复后，按原计划1294–1305行补缺失阶段命令；不扩合成矩阵、不把frozen-ssh称为真实验收。单写入者，既有worker只读独审。原计划/main不改。

新增package脚本→Node固定锁定venv入口→Python集成驱动；无需安装、无自动skip，Python用-I/-B避免环境优化关闭assert。仓库外私有显式目标配置，同fd核owner/mode/regular/大小/稳定身份；新localRoot、规范UUID runBase、隔离账号严格布尔attestation、可信pin、已有Python/MNIST路径、exact操作清单、明确时区窗口及maxSeconds+30秒清理余量。默认不执行，只有--execute且stdin有界凭据可进入产品服务；不配置/保存新凭据，不打印SDK/路径/secret。配置声明不替代真实授权。

真实模式代码复用现有LocalWorkspace/ConnectionManager/pin确认/环境与Dataset probe/DataTransfers/编译器Bundle/owner start幂等/resume/日志/RunViews图像hash/精确owned取消；没有另造训练脚本或假链。小型协议文本上传独立于既有MNIST数据，quick1epoch成功路径、显式断开并新认证恢复同owner、日志EOF及唯一runtime_started/process_exited、epoch证据/图像内容核验；第二个最多2epoch full模式run须实际取消。观察不到RUNNING、取消输给完成、缺环境/数据、同步/清理不明一律FAIL。start回执丢失时从新私有产品ledger取owned IDs，不静默重试、不删远端输出。详见ssh-acceptance.md。

独审指出并关闭两P2与配置fd风险：LiteralTrue原先接受1，改before is True；原只有主线程窗口check，改workspace._verify→身份/lease→上传/owner/artifact实际I/O guard含后台，并补start前复核；配置原分两次stat/open，改同fd核权限和identity。SDK在途调用、已启动远端进程不承诺窗口硬实时停止，窗口过期不再发新网络cancel，未知owner留证据且FAIL。有限独审无新增明确P1/P2。

| 实际命令 | 结果 |
| --- | --- |
| `env -u EASYAI_SSH_TEST_CONFIG pnpm test:ssh` | **预期NOT RUN / NOT_CONFIGURED，exit2**，不是PASS；`/tmp/easyai-ssh-entry-normal-1792357674266-225181.log`。无配置、无工作区/凭据/网络。pnpm的ELIFECYCLE非0提示保留 |
| `services/backend/.venv/bin/pytest services/backend/tests/test_ssh_acceptance_entry.py -q` | **7 PASS/0.60s**；`/tmp/easyai-ssh-entry-entry-1792357674266-225181.log`。本地配置缺失/默认与check不execute/权限与exact scope/窗口过期不读凭据/Node退出状态、严格True与实际fd非私有拒绝、产品身份callback窗口门；无mock SSH通过 |
| `MYPYPATH=services/backend/src services/backend/.venv/bin/mypy --strict services/backend/integration/ssh_acceptance.py` | **PASS**；`/tmp/easyai-ssh-entry-types-1792357674266-225181.log`。集成驱动不在src常规mypy路径，因此单独strict检查 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm check` | **PASS**；`/tmp/easyai-ssh-entry-check-1792357674266-225181.log`；108Python ruff/format（含integration）、strict mypy60生产源、TS/Main/tests/合同/真实Blocklyfixture/Prettier |
| `services/backend/.venv/bin/pytest services/backend/tests/test_remote_run_api.py -k 'public_start_real_owner_cached_reads or consumed_start_lost_ack or ssh_cancel_scope_commits' -q` | **3 PASS/15 deselected/3.59s**；`/tmp/easyai-ssh-entry-product-protocol-1792357674266-225181.log`。复用既有产品HTTP/coordinator/本机stdlib合成owner fixture定向核幂等/日志/已消费start丢回执显式resume/取消scope；不是新入口真实正向链，非SSH/torch验收 |
| 独立 `pytest services/backend/tests/test_ssh_acceptance_entry.py -q` | **7 PASS/0.62s**，`/tmp/easyai-ssh-entry-review-9YCWmP.log`。与作者重合不累计；只读独审，无真实SSH/训练 |
| `git diff --check`、原件hash、`git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` | **PASS**；推前dev=3af519b65c3dae1100e40afc124b86178048638f、main=5323f86232529efcfb52131168ad049f01b219f3。正常开发分支提交，随后push再核 |

中间失败保留：首次从仓库根直接mypy未配置MYPYPATH，控制台23项包含模块解析/未typed辅助函数；按源路径strict检查后剩4项实际错误（Optional code和同名binary/text output变量），原件 `/tmp/easyai-testssh-types-20261018-unique1.log` 保留，修正后strict PASS。后续唯一日志，不覆盖或重建。入口数字1/窗口/fd缺陷由独审本地复现与新守门收口，不把通过当真实SSH证据。

- `/tmp/easyai-ssh-entry-check-1792357674266-225181.log` SHA256 `79ef6c192c3f60411c73a59c727796deed1c08f85079ab69ad7ed25d3fd4cffa`。
- `/tmp/easyai-ssh-entry-entry-1792357674266-225181.log` SHA256 `916ddb13211334b25780438aacd2191905839a229597c7e4ea25b2520859b345`。
- `/tmp/easyai-ssh-entry-normal-1792357674266-225181.log` SHA256 `45bbbba0dbb398a3178bef425ab0d1cfe3a25391cdd5428881cb47d70fec61d0`。
- `/tmp/easyai-ssh-entry-product-protocol-1792357674266-225181.log` SHA256 `ad9b00a1dffd145b6d7d022d56af450ff22a74da4af69c485d5caa8604a6a65b`。
- `/tmp/easyai-ssh-entry-review-9YCWmP.log` SHA256 `5aca16efb287fb5b13d535f45123318879a523ba8807605bb8e3c3006ce4db0b`。
- `/tmp/easyai-ssh-entry-types-1792357674266-225181.log` SHA256 `5d4b6d285b77932e3d08212c3b4974d0a803f98ec60408ac6ccf6a063fa6c19e`。
- `/tmp/easyai-testssh-types-20261018-unique1.log` SHA256 `eff1dca7a1a6ab3fd6b4f3096b68a48acecff18ee86d91f12534f310d6e0a0db`。


NOT RUN：配置后的真实 `pnpm test:ssh --execute`（准确目标未提供且未获真实执行窗口）、真实SSH/上传/启动/断线恢复/取消/产物核验、训练/安装/下载/新凭据、Electron/Windows/干净机/构建重打包/全套大矩阵。原plan116185字节SHA dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43、旧规格5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190、README befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852未改。CIFAR待用户裁决；旧226 PASS/1 FAIL根因UNKNOWN且原始日志丢失，不借本轮关闭。既有Actions读取/sandbox拒绝未重试/绕过，CI最新精确认证仍d2ac2bf/run39158015941 check SUCCESS/desktop FAIL，首错未知。本片无新拒绝/未知外部写入/main/强推/PR/Release/部署/费用/凭据/权限变化。

下一项/真实阻塞：M5至少一次真实全链目前 **未授权且未执行**，不是失败后重试。需隔离Linux目标与账号范围、可信独立指纹、既有训练Python/课程MNIST、受保护runBase父目录、明确上述操作起止窗口、可信stdin凭据注入和私有新localRoot；不要求在公开仓库填写。文档与本地门可独立推进已完成，后续未经新实质授权不连接。源码不等于M5/B通过。


## 2026-10-18 — 父侧SSH入口静态竞争P2修复；M6.3生产接线审计

修复源码完整SHA **`2d2850e8f75ae39b224be15cde09e3d09aeb1f0b`**，基线 `7433d1761a8678e0af68213a54c171fa6b7b93ca`。父侧暂不签收旧入口，指出ConnectionManager.wait_idle只等session/environment，不等RemoteRuns旧worker；旧worker可在0.5秒轮询或finally中，快速新认证后resume触发REMOTE_RUN_BUSY。先提取原入口相同控制序列，加现有产品/本机stdlib合成owner的确定性disconnect-finally屏障，旧逻辑实际进入RemoteRuns.begin而 **1 FAIL/18 deselected**，固定首错REMOTE_RUN_BUSY；原件保留，不是推测。

最小修复：RemoteRuns.wait_worker_exit只快照同run先前worker，gate外最多join3秒，重入gate核同owner未被替换/线程确实退出/同步清理已静止。超时BUSY、owner替换或未知清理拒绝；不stop/retire/unlock、不重start或重认证，不改变begin/core.attach的所有权门。入口仅一次新认证，尚未发resume前等待，再复核窗口，最后一次resume。屏障回归先做0.01秒超时，确认旧thread/owner保留且start计数1，再释放实际旧worker，恢复后认证仍1、start仍1。

| 实际命令 | 结果 |
| --- | --- |
| `services/backend/.venv/bin/pytest services/backend/tests/test_remote_run_api.py -k acceptance_resume_waits -q` 修前/后 | 原始 **1 FAIL** `/tmp/easyai-ssh-worker-red-20261018-unique1.log`；修后 **1 PASS/18 deselected/1.81s** `/tmp/easyai-ssh-worker-green-20261018-unique1.log`，不累计到最终窗口 |
| `services/backend/.venv/bin/pytest services/backend/tests/test_remote_run_api.py services/backend/tests/test_ssh_acceptance_entry.py -k 'acceptance_resume_waits or entry or configured or attestation or window_reaches' -q` | **8 PASS/18 deselected/2.44s**，`/tmp/easyai-ssh-worker-target-1792358046734-85016e.log`；仅1个屏障及既有7入口门，不扩大合成矩阵 |
| `MYPYPATH=services/backend/src services/backend/.venv/bin/mypy --strict services/backend/integration/ssh_acceptance.py` | **PASS**；`/tmp/easyai-ssh-worker-types-1792358046734-85016e.log` |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm check` | **PASS**；`/tmp/easyai-ssh-worker-check-1792358046734-85016e.log`。TS/Main/tests、108Python格式/ruff、strict mypy60、合同/Blockly fixtures/Prettier |
| 既有worker独立只读barrier | **1 PASS/18 deselected/1.24s**，`/tmp/easyai-ssh-worker-review-Lq25cg.log`；关闭此P2，无新增明确P1/P2；重合不累计 |
| `git diff --check` / `git push origin HEAD:refs/heads/codex/demo-v0.0.0` / `git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` | **PASS**，修复已普通push并核dev=2d2850e8f75ae39b224be15cde09e3d09aeb1f0b，main=5323f86232529efcfb52131168ad049f01b219f3不变；审计/本条进度随后独立文档提交 |

- `/tmp/easyai-ssh-worker-red-20261018-unique1.log` SHA256 `a05f7851ef624c49567e28707a2d38f97f448a1f95b56e79d89abd189f55b989`。
- `/tmp/easyai-ssh-worker-green-20261018-unique1.log` SHA256 `65675d5bb2bce9409f955cf0a3c6d2b75a4f655c2d54350d241f50186f9c5eeb`。
- `/tmp/easyai-ssh-worker-target-1792358046734-85016e.log` SHA256 `fbbe534875b2932f157a4c1e56980b697ffa631f54031de049248da2b4b74585`。
- `/tmp/easyai-ssh-worker-types-1792358046734-85016e.log` SHA256 `5d4b6d285b77932e3d08212c3b4974d0a803f98ec60408ac6ccf6a063fa6c19e`。
- `/tmp/easyai-ssh-worker-check-1792358046734-85016e.log` SHA256 `79ef6c192c3f60411c73a59c727796deed1c08f85079ab69ad7ed25d3fd4cffa`。
- `/tmp/easyai-ssh-worker-review-Lq25cg.log` SHA256 `cd7b21d37005571e98f070a70e1b94dfa55f86f1999e1763aadc0aabc224fb41`。


随后按原M6.3完成只读接线审计，交付 `docs/install-production-wiring.md`：缺真实CondaBootstrap、LocalWorkspace未注入ManagedInstallInspector、confirm仅AWAITING_EXECUTION未调度execute、现有close先关journal不足以承接并发worker。这些是代码缺口，不以缺真实环境宣称代码完工。最小顺序为可信现有conda/离线bootstrap来源合同→固定argv/既有owner下CondaBootstrap→inspector与唯一worker接线/静止关闭→能力及计划合同/Main/UI。记录bootstrap来源/hash/体积缺口、执行能力false/网络字段语义、锁覆盖包与未解析包、教师环境只读、应用venv无torch、未知保留lease及禁止自动恢复。此处仅方案，没有启用安装代码。

NOT RUN：真实SSH/新入口execute/下载/安装/conda创建/训练/新凭据/许可接受/全套大矩阵/构建重打包/桌面/Windows/干净机。准确真实执行目标与窗口未提供，**未授权且未执行**；未来安装另需一次性owned目标、具体可信launcher/bootstrap及wheel来源/许可/预算确认，不把已有开发授权当执行许可。CIFAR待裁决、旧226 PASS/1 FAIL根因UNKNOWN且原始日志丢失，不由此P2回溯关闭。plan116185字节hash dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43、旧规格5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190、README befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852未改。既有Actions读取/sandbox拒绝未重试/绕过，无新拒绝/未知外部写入/main/强推/PR/Release/部署/费用/凭据/权限变更；无本片新CI判定。完整M5/M6.3/B仍未验。

下一项为按最小方案冻结可信conda bootstrap/来源合同，再做受控本地adapter和唯一worker生产接线；真实执行门保持关闭。方案不替代尚未实现的adapter或真实纵向验收。

本片M6.3接线方案亦经既有worker独立只读核对，四项代码缺口与现状一致，无重大事实误述；没有启用安装或把内部接口当真实安装完成。


## 2026-10-18 — M6.3 四项生产接线（默认禁用；真实安装NOT RUN）

源码完整SHA **`446afaada4e41dd42f8e20e9e81a1f1b598938a0`**；基线 `14f03fa8d4fbaef8e702bd8c13f6a3edf0c71587`。按父级明确授权，实现已审最小方案中的四项代码缺口；不因缺真实目标停在方案。单一集成者，复用既有worker独立只读审查。范围仅本机Linux x64 CPU/应用owned目标/既有CPU锁覆盖包，不把本片当完整M6.3/B。

先只读核精确官方conda25.9.1 tag：main_create125–149区分已有conda环境（可remove）与已有non-environment目录（确认后继续）；misc支持本地file+SHA256，install纯explicit分支绕solver。支持准确25.9.1，固定empty-prefix/claim前置与返回核验、无force/clone/删除；来源不齐/版本不符保持拒绝。官方25.9.x CLI页标题dev4仅参数参考，裁决用tag。链接及完整权限/私有配置合同见 `docs/install-runtime-configuration.md`，未虚构实际launcher/hash/来源/体积，没有获取安装器/依赖或运行conda。

实现结果：

- 新InstallRuntime/CondaBootstrap读取**缺失即无能力**的私有配置；同fd核配置，launcher实际hash/身份、显式完整模块树hash、离线bootstrap档案、既有wheel来源、预算/时效绑定runtimeFingerprint→planHash。执行前与kernel lease后重核。来源文件逐级受保护祖先，拒绝链接/不安全可写目录；不把版本字符串当来源信任。
- base Python用-I/-S/-B与受核moduleRoot，禁.pth；准确版本/模块路径先核。固定私有Context配置搜索路径覆盖CLI再次初始化；offline/纯@EXPLICIT/file SHA256/no-default-packages/copy、禁external plugins/更新/notices/共享注册。ManagedProcess新增inherit_environment默认true，既有训练默认不变；安装命令用false及白名单HOME/tmp/cache/pkgs/envs，避免继承PIP/CONDA/PYTHON/proxy/LD配置。沿用ManagedInstallCommand/ManagedSupervisor owner，不另造writer或自由命令入口。
- LocalWorkspace注入既有ManagedInstallInspector，confirm在mutex内先持久登记同job唯一worker，再只调原execute；确认重放不spawn。每job cancel token供inspector使用；close在workspace锁外，先取消包括planning/probe，再用从mutex获取前开始的总等待预算等worker静止；未知保留journal/lease，不提前释放物理门。restart仍只读隔离旧任务。
- executionEnabled从固定false改为**默认false且具体主机/具体plan的能力**，未配置没有worker/环境创建；不是全局true。合同生成新增runtimeFingerprint/bootstrapBytes/diskBudgetBytes/executionSeconds，来源已在本机的计划requiresNetwork=false/downloadBytes=0，真实解包占用未知保留null。UI展示来源/预算，并区分“明确确认执行”与“仅登记”，17包中未锁可选项继续block。没有创建实际配置或启用本机真实安装。

独审实证并关闭三个P2：1）leaf保护不涵盖0777非sticky祖先，现复用既有逐级目录策略及回归；2）旧close等planning mutex前未设取消/计入deadline，现先发close请求/全owner取消，mutex获取亦有界、未知保留，Inspector后再核scope；3）runtime.snapshot全树hash可跨close，现保存plan前最终核scope，snapshot专用屏障拒绝迟到enabled计划。原前两项纯stdlib独审实证在消息中，未编造其本地原始日志。支持精确tag的私有Context wrapper亦经独立核源；最终未发现新增明确P1/P2。

| 实际命令 | 结果与范围 |
| --- | --- |
| `services/backend/.venv/bin/pytest services/backend/tests/test_install_runtime.py services/backend/tests/test_install_service.py services/backend/tests/test_install_process.py services/backend/tests/test_owned_creation.py services/backend/tests/test_supervisor.py services/backend/tests/test_compilation.py -q` | **121 PASS/12.55s**，`/tmp/easyai-install-final-tests-1792359074247-2bafe8.log`。9个新runtime门/既有安装和创建生命周期/继承默认及进程组取消/编译与runtime资源回归。HTTP→唯一worker正向只复用已标注的synthetic inventory、claim/ready与复检合同；固定conda命令仅compile/capture，**不执行真实adapter/conda/pip/安装/torch**。真实stdlib子进程只核环境白名单 |
| `pnpm exec vitest run apps/desktop/src/PackageManager.test.mts apps/desktop/electron/install-workflow.test.mts` | **22 PASS/2 files**，`/tmp/easyai-install-final-ui-1792359074247-2bafe8.log`；新增enabled主机仍需具体plan/checkbox确认，默认分支、固定IPC、源码sidecar协议仍覆盖；不启动Electron或原生picker |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm contracts`，同缓存 `pnpm check` | 合同生成及 **check PASS**，`/tmp/easyai-install-final-check-1792359074247-2bafe8.log`；TS/Main/tests、110Python ruff/format、strict mypy61、合同/真实Blocklyfixture/Prettier。最终后续仅更新两个模块docstring说明已接生产worker，并定向ruff check/format PASS，无行为改动 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache XDG_CACHE_HOME=/workspace/.cache pnpm build` | **PASS**，`/tmp/easyai-install-final-build-1792359074247-2bafe8.log`；Main TS/Vite/PyInstaller，保留既有chunk提示，无新依赖或真实安装；构建后仅上述docstring文案更新，无行为改动 |
| `node scripts/test-frozen.mjs` | **PASS**，`/tmp/easyai-install-final-test-frozen.mjs-1792359074247-2bafe8.log`；实际冻结后端临时cwd资源/选择API/工程/黄金编译、默认安装plan/登记/取消（execution仍false）、EOF exit0 |
| `node scripts/test-frozen-install-recovery.mjs` | **PASS**，`/tmp/easyai-install-final-test-frozen-install-recovery.mjs-1792359074247-2bafe8.log`；实际重启冻结后端持久job读取/旧确认失效；没有环境、安装器或安装正向链 |
| 既有worker只读独审 | runtime **8 PASS/6.41s** `/tmp/easyai-install-runtime-review-jU5zZI.log`；补迟到snapshot/命令捕获/唯一worker **3 PASS/6 deselected/3.37s** `/tmp/easyai-install-final-gate-review-o2Cd5h.log`，范围重合不累计。关闭三个P2，源码/官方接口核对无明确新增P1/P2 |
| `git diff --check` / 原件hash / `git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` | **PASS**。推前dev=14f03fa8d4fbaef8e702bd8c13f6a3edf0c71587、main=5323f86232529efcfb52131168ad049f01b219f3；源码/文档普通dev提交，随后push核对 |

失败与中间窗口如实保全，不与最终累加：初稿mypy1项records类型缺注解/Ruff lambda，修正；既有60项第一次58PASS/2FAIL/5teardown为新close正确拒绝unknown lease及持久失败路径，修正close安全关闭的固定错误处理，强化旧fixture明确expect pending且保留journal/lease，不放宽执行门。新runtime初稿6PASS/1FAIL是Headers.update错误参数；其后7PASS/1FAIL是测试误期望200而产品原契约202，改断言。包含旧60的中间窗口67PASS/1FAIL同202误断言，未改产品状态；最后9runtime/121综合通过。所有文件唯一noclobber，不覆盖失败。

- `/tmp/easyai-install-final-build-1792359074247-2bafe8.log` SHA256 `20580bda83df6c27d0e80ad85831f84bea62f4d1a9dfd4078725a6f29eb5612f`。
- `/tmp/easyai-install-final-check-1792359074247-2bafe8.log` SHA256 `0ba42ea8d706375620f36169cc55b8ed1bdcdc915708fd2bc1d5c578fe6e6fbf`。
- `/tmp/easyai-install-final-gate-review-o2Cd5h.log` SHA256 `2330fe8b057ddbaadc3a3d3c8059bdc56c326c3355fa89b99c7f275c2417be46`。
- `/tmp/easyai-install-final-test-frozen-install-recovery.mjs-1792359074247-2bafe8.log` SHA256 `46986004fa5ba8e2972c26335394e67612cf6f7b4021c7a00a6cfbc9f57cc1c8`。
- `/tmp/easyai-install-final-test-frozen.mjs-1792359074247-2bafe8.log` SHA256 `598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。
- `/tmp/easyai-install-final-tests-1792359074247-2bafe8.log` SHA256 `3c982fd57e313a104fa9907d1a5042e1873de6ef2346c1bd8aaba5740df046f7`。
- `/tmp/easyai-install-final-ui-1792359074247-2bafe8.log` SHA256 `712367ce59b6be8eeef357f5c34300e849258269082314002072b234092da0ec`。
- `/tmp/easyai-install-runtime-review-jU5zZI.log` SHA256 `233d1d856e1a757a55ffe2d3ab84c24497f297021d477af9c33bb0aa5f014687`。
- `/tmp/easyai-install-wiring-baseline-20261018-unique1.log` SHA256 `f638066495cdf56861265ea846d68b5cc20ebfabd61c19b9215a5935647eebe7`。
- `/tmp/easyai-install-wiring-baseline-20261018-unique2.log` SHA256 `dd45a33bbf343ce3963a4921662bf94fa4561201cd5859ba0477a04b6e968f34`。
- `/tmp/easyai-install-wiring-check-1792358840639-93b4a9.log` SHA256 `0ba42ea8d706375620f36169cc55b8ed1bdcdc915708fd2bc1d5c578fe6e6fbf`。
- `/tmp/easyai-install-wiring-new-20261018-unique1.log` SHA256 `4fe979b5865f11039fa2cc6d709638b7aa04efcbd082308d89155dd4f248321c`。
- `/tmp/easyai-install-wiring-new-20261018-unique2.log` SHA256 `6f3eeddc77e9c1853e3febd1f916f33c6db7015e6869430fe4f4a0bab37094d1`。
- `/tmp/easyai-install-wiring-new-20261018-unique3.log` SHA256 `d1b57cd7859067a3929e0ed721995bdec8fa0509c64ffd137132a3bb28c0a74b`。
- `/tmp/easyai-install-wiring-new-20261018-unique4.log` SHA256 `c6e3f9790bff1ca7a8ff6259410d3654b79807390b46f175403d080ab1022eea`。
- `/tmp/easyai-install-wiring-tests-1792358840639-93b4a9.log` SHA256 `0403b3124c691934d5a46abe5613c202fae59d3a283b6e61ffa3917cc0b93b3e`。
- `/tmp/easyai-install-wiring-types-20261018-unique1.log` SHA256 `0681ab94e73d171c0d806d1c114f40e382d2c54ab6ff28b18427906aa08fc3f2`。
- `/tmp/easyai-install-wiring-ui-1792358840639-93b4a9.log` SHA256 `4921881ad8eb2a1124ef80286cddfd8d543280f6a15ab6992321f959c445dc52`。


NOT RUN：真实CondaBootstrap/pip、依赖/缓存/数据下载、环境创建/安装/实际正向imports/tensor、训练/新凭据/许可接受、真实SSH/桌面/Windows/干净机/全套大矩阵/重打便携包/发布。私有真实launcher及模块/bootstrap/wheel来源、许可与一次性owned目标/预算授权未提供，**未授权且未执行**，没有“已安装后重试”的不确定外部动作。默认能力仍关闭；本片是四项源码接线完成与受控验证，不是实际兼容/安装验收。

plan原件116185字节hash dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43、旧规格5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190、README befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852均未改。CIFAR仍待用户裁决，旧226PASS/1FAIL根因UNKNOWN且原始日志丢失，不回溯套新P2；既有Actions读取/sandbox拒绝未重试/绕过。旧source7b91c46便携目录未含本片、未重打包/上传，distributionReady/legalReviewComplete仍false；无本片新CI判定。无新工具拒绝/未知外部写入/main/强推/PR/Release/部署/费用/凭据/权限变化。

下一项是父侧复核四项源码接线与精确支持合同；随后真实验收只有在上述具体来源/目标/许可/预算授权齐备后可进行。可选包解析、安装历史/保留策略、未知停止安全解除、活安装重连、远端安装仍是独立剩余代码范围；M5真实SSH、完整M6.3/B仍未验。


## 2026-10-18 — M6.3 probe owner 静止证明 P2 修复

源码完整SHA **`a26873148e1a77dd0a1d67b7684afc5bf14c1785`**；基线 `c6049a668cec141c73d74b0260b2aad0df51817a`。按父级明确指出的bootstrap/final probe异常错误沿用上一条安装命令quiescent=True问题修复，单一集成者、既有worker独立只读审查，没有真实bootstrap/pip/安装/probe/训练或新增来源配置。

- 每次探测独立ProbeReceipt，绑定实际supervisor、精确prefix与本job取消token；命令完成不代表下一次探测完成。ManagedProcess的静止证明同时要求关闭、leader已退出以及reader/monitor/cancel线程均已结束；close不因logical done就关闭journal。未知cleanup保留真实owner引用、lease、receipt和journal，不写ready，不自动退休/解除隔离。
- 执行前baseline probe也纳入同job：先持kernel lease并写持久执行意图，再探测；未知失败不释放lease。已知静止的过期/漂移仍保持原AWAITING_EXECUTION及异常合同；WAL后TTL过期仍按既有FAILED合同。没有放宽原测试断言。
- 独审另实证同prefix可连续未知probe产生多个live owner，现于独立probe gate下登记并拒同prefix新dispatch；没有dispatch的拒绝只证明本次静止，不移除旧receipt。其他prefix及取消token独立；close明确取消全部receipt。无job的planning/confirmation未知probe也阻止close和同prefix重入。未知停止安全恢复仍未实现，保守保持隔离。
- 文档同步probe生命周期，并修正install-contract中已过时的“没有生产调用者”表述；本片没有增加执行能力或授权。

| 实际命令 | 结果与证据 |
| --- | --- |
| `services/backend/.venv/bin/python -m pytest services/backend/tests/test_install_probe_ownership.py services/backend/tests/test_install_process.py services/backend/tests/test_install_service.py services/backend/tests/test_owned_creation.py services/backend/tests/test_supervisor.py services/backend/tests/test_install_runtime.py -q` | **99 PASS/12.10s**，`/tmp/easyai-install-probe-final-20261018-unique2.log`。覆盖baseline/bootstrap/final未知probe真实stdlib线程屏障、同prefix拒重入/其他prefix独立、真实ManagedSupervisor对象reader门，以及既有安装/创建/runtime/supervisor回归。新探测屏障禁止Popen，未执行真实probe/安装；既有supervisor测试仅运行受控stdlib子进程。 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm check` | **PASS**，`/tmp/easyai-install-probe-check-20261018-final1.log`；TS/Main、ruff/format111Python文件、strict mypy61、合同/真实Blocklyfixtures/Prettier。 |
| 既有worker独立只读专项 `pytest services/backend/tests/test_install_probe_ownership.py -q` | **5 PASS/0.36s**，`/tmp/easyai-reader-close-fixed-review-F9kUZg.log`。分阶段2PASS、4PASS审查范围重合，不累计；无新增明确P1/P2。未编辑/未启动Popen或真实probe。 |
| `git diff --check` / 原件hash / `git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` | **PASS**。推前dev=c6049a668cec141c73d74b0260b2aad0df51817a；main=5323f86232529efcfb52131168ad049f01b219f3；计划116185字节及三份原件hash不变。源码与本证据分别普通开发分支提交后push。 |

保留失败原始记录：最初bootstrap/final屏障在旧行为下**2 FAIL**，初修**2 PASS**；首轮旧回归**84 PASS/3 FAIL**是移动baseline WAL后stale/TTL旧合同变化，改产品状态处理后**87 PASS**；新增baseline/重入/runtime后**98 PASS**。check第一轮unused Path导入FAIL，第二轮mypy状态窄化FAIL，移除无用导入并显式restore_awaiting变量后PASS。追加reader门首轮**98 PASS/1 FAIL**为测试argv=[]被构造器拒绝，改非空never-executed占位并禁Popen后最终99PASS。独审同reader夹具失败也保留，不覆盖、不计最终通过。所有本片日志唯一noclobber。旧226PASS/1FAIL的根因仍UNKNOWN且原始日志丢失，不能用本片P2回溯关闭。

- `/tmp/easyai-install-probe-red-20261018-unique1.log` SHA256 `0d6e1d604d09bf32ce93b88cbe29df7195d0a56aa60dac8091ed16d0174ee476`。
- `/tmp/easyai-install-probe-green-20261018-unique1.log` SHA256 `681442d18fe79aa9977e74c72ecfd3ea874c886cbbbfd09b3f3397ebbc1bcb15`。
- `/tmp/easyai-install-probe-regression-20261018-unique1.log` SHA256 `c03e79394e69d93ad6de879b4029051a9617453adfc4ba0e6fd5f6648e9f6d62`。
- `/tmp/easyai-install-probe-regression-20261018-unique2.log` SHA256 `5bd84046e22825bb8d2ffbfef5f7bb48cde1923e8f6f2d1a285f01b3aab31d8f`。
- `/tmp/easyai-install-probe-regression-20261018-unique3.log` SHA256 `5573c34d94624cabdfa2cc994499afdf08cf5845d4312ce436b893beadc3bc19`。
- `/tmp/easyai-install-probe-final-20261018-unique1.log` SHA256 `2dfa0eb7f7b7a9ae4eaecb937e19f2eb59c44ba000ec942a933b84e3f0a3db42`。
- `/tmp/easyai-install-probe-final-20261018-unique2.log` SHA256 `af4a7f8a21910d2d64e623aa8ef51bbd183f08be1d19db5b2819d429196eae1a`。
- `/tmp/easyai-install-probe-check-20261018-unique1.log` SHA256 `1c50ecac91fa6925a79d92c1510103de1d9fa746f2cb33204dbb29bc965fad0d`。
- `/tmp/easyai-install-probe-check-20261018-unique2.log` SHA256 `a4cfa684bd59bcf678e615052da637b4741a731cdb6f97bd7dd3e7e4ff66622a`。
- `/tmp/easyai-install-probe-check-20261018-unique3.log` SHA256 `05c07384dda101ad0c17860188e09d3c8445565b3c797ed2010e7541d5a17580`。
- `/tmp/easyai-install-probe-check-20261018-final1.log` SHA256 `05c07384dda101ad0c17860188e09d3c8445565b3c797ed2010e7541d5a17580`。
- `/tmp/easyai-install-probe-review-PnDLT3.log` SHA256 `cdafb4497d6e45a437ba3d7241f79c167ef117065ae2165e4955a12246a5e19f`。
- `/tmp/easyai-probe-prefix-review-iCSWeT.log` SHA256 `192d4360198de472118c06b36693efa7b9549d6a22d809713dcac70bc60b16e0`。
- `/tmp/easyai-reader-close-review-FHRvK2.log` SHA256 `0f9fd5627449bc140db60548c12eb415ad85b6d3679e69fe6df6a734dc3f3d6f`。
- `/tmp/easyai-reader-close-fixed-review-F9kUZg.log` SHA256 `48bc2bf7aee35b3cf04baf9cad1c249913112b1265affa04e2074b3da5da5372`。


NOT RUN：真实CondaBootstrap/pip/环境创建/安装/实际正向imports与tensor、下载/训练、真实SSH/新凭据/许可接受、全套大矩阵、重建冻结后端/重打便携包、Electron桌面/Windows/干净机/发布。本片仅后端生命周期修复，已做相关回归与check；现有冻结后端及旧source7b91c46便携目录不包含本片，不能当本片验收产物。默认能力仍关闭。真实来源/许可与具体一次性owned目标、预算及执行窗口尚未提供，**未授权且未执行**；没有外部安装结果不确定的动作。

plan116185字节SHA256 dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43，旧规格5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190，README befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852保持。CIFAR待裁决；旧226PASS/1FAIL保持UNKNOWN；既有Actions读取/sandbox拒绝未重试或绕过。无本片新CI结论；无main/强推/PR/Release/部署/费用/凭据/安全权限变化、无新工具拒绝。

下一项：父侧复核本P2和独审证据；可继续安装历史/保留策略及未知停止的显式安全恢复代码。真实安装/SSH需独立具体授权；完整M5/M6.3/B仍未验收。


## 2026-10-18 — M6.3 ML白名单可选闭包与来源接线（无真实安装）

源码完整SHA **`4ed030db5770fcd559120c1c3f24d7cf5a8d635c`**；基线 `d2735b8fc2e3f6f33aca1be8b4efcb5bc1a931de`。按父级原14.3/14.5新授权优先补完整ML组，不转去安装历史，不增加writer；沿用单一集成者/既有独审worker。原始README/旧规格/计划及核心CPU sources/lock保留。完整合同与来源主记录见 `docs/install-ml-sources.md`、`packages/training-profiles/easyai-ml-sources.json`。

来源只读核验：精确PyPI发行scipy1.17.1、pandas3.0.1、scikit-learn1.8.0、joblib1.5.3、threadpoolctl3.6.0，选择Linux x86_64 CPython3.11/py3-any wheel记录。实际读取JSON与PEP658 `.metadata`，与发行/索引声明的metadataSHA256核真实元数据字节，再核Name/Version/Requires-Python/Requires-Dist。未请求wheel或sdist。记录真实URL/filename、发行SHA/size、metadataSHA和原始发行JSON captureSHA，不编造hash或体积。新增闭包声明下载56036031字节；wheel本体未下载/核实际字节，未来仍由原archive对operator本地文件核SHA/bytes/身份。元数据中当前yanked=false及vulnerabilities=[]仅为捕获结果，非持续安全或许可审查。

- 固定图匹配无extras的PEP508目标markers：scipy要求NumPy>=1.26.4,<2.7；pandas Python3.11要求NumPy>=1.26及dateutil>=2.8.2；sklearn要求NumPy>=1.24.1/scipy>=1.10/joblib>=1.3/threadpoolctl>=3.2。复用核心NumPy2.4.2/dateutil2.9.0.post0及其已锁six，不升降核心。Windows/emscripten tzdata marker不属于本Linux合同；doc/test/build/excel等extras不选。
- 新补充sources/lock与固定选择函数按用户请求根取闭包：scipy不带pandas；pandas不带sklearn；sklearn带scipy/joblib/threadpoolctl；ML全选走同一计划器。固定补充锁与manifest须完全相符；constraintsHash绑定两对来源/锁，planHash包括具体闭包/来源预算。17卡现在8卡可解析、其余9卡继续INSTALL_DEPENDENCIES_UNRESOLVED；不按展示卡片宣称支持。新增unpackedBytes=null，ML计划installedBytes=null，拒绝虚构解包占用。
- runtime核心快照仅核核心本地来源；具体ML计划额外核选中closure真实本地wheel/hash/字节，纳入runtimeFingerprint与原bootstrap/磁盘/时间预算。默认缺配置仍false；来源漂移/不足或预算不符拒绝，不因catalog core capability启用ML。既有fixed OfflineWheelInstaller只把选中补充pin加入原核心lock副本，原no-index/require-hashes/only-binary、私有源/owner/WAL/lease/cancel/probe门不变。
- 独审指出未选ML import也可能拖垮核心probe，已收窄：metadata版本inventory列已知distribution但不import；baseline/规划仅原核心3模块，final receipt从本计划闭包显式映射所需import，sklearn不是猜名；未选pandas不导入，未知module拒绝。完整版本/import与原tensor门均通过才可verified/ready，未降低未知probe隔离。
- PyInstaller/离线package资源allowlist加入两份ML数据，冻结后端校验四文件和含ML的默认禁用计划。这里只重建本地冻结后端，没有重打旧portable目录。Main原生source picker仍缺，目前只有operator私有manifest，已在产品状态文档保留。真实ABI/import/tensor与安装未验。

| 实际命令/动作 | PASS/FAIL/NOT RUN及边界 |
| --- | --- |
| `services/backend/.venv/bin/python -m pytest services/backend/tests/test_install_ml.py services/backend/tests/test_install_probe_ownership.py services/backend/tests/test_install_process.py services/backend/tests/test_install_service.py services/backend/tests/test_owned_creation.py services/backend/tests/test_supervisor.py services/backend/tests/test_install_runtime.py -q` | **106 PASS/12.62s**，`/tmp/easyai-ml-regression-20261018-final1.log`。7新增metadata/closure、单选与全组选中/预算/漂移/固定命令/选中import失败拒绝门；其余为原安装/probe/创建/supervisor/runtime回归。新ML用命令捕获/合成inventory，不执行实际ML import或安装；既有stdlib子进程不冒充训练。 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm check` | **PASS**，`/tmp/easyai-ml-check-20261018-final1.log`；TS/Main/tests、ruff/format113Python、strict mypy62、合同/真实Blocklyfixture/Prettier。无公开合同DTO/schema变化。 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache XDG_CACHE_HOME=/workspace/.cache pnpm build` | **PASS**，`/tmp/easyai-ml-build-20261018-unique1.log`；Vite/TS/PyInstaller，已有chunk提示保留，无依赖安装/下载；最终源码与来源资源已包含。之后仅文档补充，无行为/资源变化。 |
| `node scripts/test-frozen.mjs` | **PASS**，`/tmp/easyai-ml-frozen-20261018-unique1.log`；临时cwd启动真实冻结后端，四份来源/锁比对、core与完整ML计划（仍禁用）、选择API、工程/黄金编译/EOF exit0；未确认实际执行安装。 |
| `node --test scripts/package.test.mjs` | **6 PASS**，`/tmp/easyai-ml-package-resources-20261018-unique1.log`；合成离线复制fixture覆盖新增资源/拒覆盖/完整清单/漂移，不生成真实便携包。 |
| 独审 `pytest services/backend/tests/test_install_ml.py -q` | **7 PASS/0.30s**，`/tmp/easyai-ml-import-review-HcWSJn.log`；早一轮6PASS范围重合，不累加。最终未发现明确新增P1/P2。 |
| 独审限定HTTPS JSON/.metadata再核 | **5发行全部PASS**，`/tmp/easyai-ml-metadata-review-z02tgjlr.json`；无redirect、两域/2MiB/15s界限，10个元数据请求，wheel SHA/字节/URL与METADATA SHA/依赖/版本均一致，5个发行captureJSON SHA未变。无wheel请求/安装/真实probe。 |
| `git diff --check` / `git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` / 原件hash | **PASS**；推前dev=d2735b8fc2e3f6f33aca1be8b4efcb5bc1a931de；main=5323f86232529efcfb52131168ad049f01b219f3；后续正常dev提交推送及远端核对。 |

初稿记录如实保留：新6专项首次即6PASS；ruff终端初查发现unused Path和两项单行格式，移除unused并格式化，无产品/测试门放宽。初版回归105PASS/checkPASS；独审建议后加receipt选中import合同，第7专项及最终106PASS，不能把早/晚窗口累加。所有文件日志唯一noclobber，无覆盖失败；主捕获命令逐项终端输出与来源文件及独立联网复核相互支持，不伪造未保存的原始请求日志。

- `/tmp/easyai-ml-new-20261018-unique1.log` SHA256 `1749ffae266aad4292b5e5dafdd61881dc9ea0c13ae040ae1afd2c90c44504b2`。
- `/tmp/easyai-ml-new-20261018-unique2.log` SHA256 `c83b7dc3b345d26077afae1610805229398ba3a4a9402906460838c0f056f594`。
- `/tmp/easyai-ml-regression-20261018-unique1.log` SHA256 `2a4a12d2de37674addb256df3b22f3dfa6e67ba4cad22febadff8dfc2303dca6`。
- `/tmp/easyai-ml-regression-20261018-final1.log` SHA256 `f73cf2cb4c59ec24a54dd085637a52ae0a61bdd0be5895530c04abadaab5dd53`。
- `/tmp/easyai-ml-check-20261018-unique1.log` SHA256 `d85a01ed609e6b3275957460a595e1632515dfe4bba3f214695c7470c847789c`。
- `/tmp/easyai-ml-check-20261018-final1.log` SHA256 `d85a01ed609e6b3275957460a595e1632515dfe4bba3f214695c7470c847789c`。
- `/tmp/easyai-ml-build-20261018-unique1.log` SHA256 `f117a562eb025e1ec30d0deefd3ccbf6c2d3980df9ebfc2dde2a5ff604c268eb`。
- `/tmp/easyai-ml-frozen-20261018-unique1.log` SHA256 `598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。
- `/tmp/easyai-ml-package-resources-20261018-unique1.log` SHA256 `e9664dfdbe3902a94545a9581194acc8927a09f9b6d0ac580eb2faa4da549610`。
- `/tmp/easyai-install-ml-review-q3Z6L2.log` SHA256 `2f0f8bcb5a0ec38f5ba3702a4491e165c19cdf8f271153bb0fb582c1f6593e39`。
- `/tmp/easyai-ml-import-review-HcWSJn.log` SHA256 `86bbfb0c34fc84fb07816d3bbc6992a59067bb59898d8dcccd3a895fd96e0cd1`。
- `/tmp/easyai-ml-metadata-review-z02tgjlr.json` SHA256 `757487ed67964ec47c666893059fc0e8fa699c2d8d0fb8b99ec4f894eb85a8ff`。


NOT RUN：wheel/sdist/模型/数据下载、真实conda/pip/环境创建/安装/ML实际imports/ABI/tensor正向/训练、真实SSH、新许可接受/凭据、Electron原生picker/桌面/Windows/干净机/全套大矩阵、真实portable重打包/发布。上述安装执行仍缺可信本地来源及许可、具体一次性owned目标/预算/窗口独立授权，**未授权且未执行**，不存在不确定外部安装结果。代码元数据可解析不等于M6.3或B验收。Main原生source picker仍缺；余9卡精确unsupported，后续逐组核发行/闭包，不能猜锁。

核心sources SHA256 `2628fc7071ca97301e1069dd8bcf20de72eefdeed5e065969c497cf4f89641c5`、核心lock `f30a1d2eb86b13a7ae8a708e3356fade92e8dd942f746616a66376f281d8641b`均未改。计划116185字节SHA256 dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43，旧规格5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190，README befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852不变。旧portable source7b91c46不含本片；distributionReady/legalReviewComplete仍false。CIFAR待裁决、旧226PASS/1FAIL根因UNKNOWN且原始日志丢失不回溯关闭。既有Actions读取/sandbox拒绝未重试/绕过；无本片新CI判断；无main/强推/PR/Release/部署/费用/凭据/安全权限变更，无新拒绝/未知外部写入。

下一项：父侧复核ML来源合同/实际元数据/选择闭包与默认执行门；其余可选组仍需逐项可信元数据/核心兼容裁决，无法核实继续unsupported。Main来源选择入口与真实安装/SSH的独立实测门仍待完成，不把本片可解析性当真实安装完成。


## 2026-10-18 — M6.3 CV固定解析：scikit-image可解析，OpenCV native门保留

源码完整SHA **`c512f5649c8e8e09e4ca9b6883af66b045fe302d`**；基线 `1d526f9f5284144f84814f4a285acc6a98e450ec`。按父级原14.3/14.5 CV授权，复用原来源选择/计划/installer/probe链；没有转外围历史/保留策略、增加writer或以测试数推算完成率。原始README/规格/计划及核心、ML来源/锁均保留。合同见 `docs/install-cv-sources.md`；主来源 `packages/training-profiles/easyai-cv-sources.json`。

2026-10-18只读PyPI精确发行JSON/独立PEP658 METADATA（禁redirect、限定pypi.org/files.pythonhosted.org、15秒/2MiB），核真实metadata字节SHA、Name/Version/Requires-Python/Requires-Dist，并交叉核发行filename/URL/SHA/bytes/yanked/当次漏洞记录。选scikit-image0.26.0/imageio2.38.1/tifffile2025.10.16/lazy-loader0.6；四文件声明下载14279559字节，另复用已审SciPy1.17.1的35349300字节。与ML合选SciPy去重。没有下载wheel/sdist、数据/模型、安装或接受许可。发行wheel SHA为注册表声明值，不能冒称实际核验wheel内容；未来仍须operator本地实际archive/hash/bytes/身份门。全部解包占用未知，CV计划installedBytes=null。

- scikit-image的无extras运行图要求NumPy>=1.24/SciPy>=1.11.4/NetworkX>=3/Pillow>=10.1/imageio>=2.33且!=2.35.0/tifffile>=2022.8.12/packaging>=21/lazy-loader>=0.4，复用核心NumPy2.4.2/Pillow13.0.0/NetworkX3.6.1/packaging26.3与ML SciPy1.17.1。imageio只取NumPy/Pillow运行依赖，tifffile只NumPy，lazy-loader只packaging；不选data/doc/build/test/ffmpeg/codec等extras，不下载样例。固定tifffile允许Python3.11，不为最新包升级Python。
- OpenCV精确候选5.0.0.93 `cp37-abi3-manylinux_2_28_x86_64`，发行声明73783032字节与METADATA均已核；Python3.11生效NumPy>=2，当前2.4.2在Python元数据约束内。但官方README只说明桌面与无GUI headless包的区分/GUI依赖链，不能可靠证明具体目标GUI/系统动态库要求已满足。本轮禁止下载wheel查看ELF、真实probe或系统安装，目标系统库证据未提供，故**INSTALL_NATIVE_REQUIREMENTS_UNVERIFIED**。候选只入unsupportedPackages证据，不入锁/可执行闭包/可执行预算；catalog targetVersion=null，计划同时保留原UNRESOLVED并拒确认。CV全组也阻挡，绝不换headless/contrib、改NumPy核心或接管cv2。此为明确unsupported，非工具动作被拒绝，也没有未知执行结果。
- helper沿用原authority，按选择合并ML与CV固定图/锁，跨组依赖去重，六份来源/锁绑定constraintsHash→具体闭包/大小/runtime预算→planHash。具体CV源仍由原runtime核本地真实hash/字节、身份和预算；只选core/ML不要求CV wheel。原固定no-index/require-hashes/only-binary安装器、同一owner/lease/WAL/probe/未知停止门不变。无公开DTO/schema变化。
- 显式映射scikit-image→skimage、opencv-python→cv2、lazy-loader→lazy_loader；metadata版本inventory不因此导入，core-only不import CV，final仅所选闭包模块。未选pandas/sklearn/OpenCV不附带导入或安装；原精确版本/import/CPU tensor门仍在。没有宣称实际CV import/ABI兼容。
- 17卡当前9卡可解析，余8卡未支持（含OpenCV native blocker）；不是CV全组或完整M6.3/B完成。Main原生source picker仍缺，目前仅operator私有manifest；没有新增实际来源配置。PyInstaller/离线resource allowlist加CV两文件，离线文档allowlist补runtime/ML/CV合同以保留引用可读；未重打旧portable。

| 实际命令/动作 | 结果与范围 |
| --- | --- |
| `services/backend/.venv/bin/python -m pytest services/backend/tests/test_install_cv.py services/backend/tests/test_install_ml.py services/backend/tests/test_install_probe_ownership.py services/backend/tests/test_install_process.py services/backend/tests/test_install_service.py services/backend/tests/test_owned_creation.py services/backend/tests/test_supervisor.py services/backend/tests/test_install_runtime.py -q` | **111 PASS/12.43s**，`/tmp/easyai-cv-regression-20261018-unique1.log`。5新增CV metadata/markers/core兼容、单选/合选/全组OpenCV阻挡、固定锁/AST probe映射、选中本地来源/预算与漂移；其余为既有安装相关回归。新CV捕获/合成来源禁止实际Popen/CV导入/安装；既有stdlib子进程只证owner合同。其后仅import排版、文档/离线文档allowlist改变，无行为修订，不为数字重跑。 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm check` | 最终 **PASS**，`/tmp/easyai-cv-check-20261018-final1.log`；TS/Main/tests、ruff/format114Python、strict mypy62、合同/真实Blocklyfixtures/Prettier。随后仅package文档allowlist补3项，并定向Prettier PASS。 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache XDG_CACHE_HOME=/workspace/.cache pnpm build` | 最终 **PASS**，`/tmp/easyai-cv-build-20261018-final1.log`；Vite/TS/PyInstaller，包含格式修正后的最终后端与CV资源；既有chunk提示。未安装/下载依赖。后续仅离线文档复制allowlist，无后端或资源改变。 |
| `node scripts/test-frozen.mjs` | **PASS**，`/tmp/easyai-cv-frozen-20261018-unique1.log`；实际冻结后端临时cwd启动、六文件比对、core/ML/scikit-image默认禁用计划、OpenCV native blocker与未知体积、选择API/工程/黄金编译/EOF exit0。未确认真实安装。 |
| `node --test scripts/package.test.mjs` / `pnpm exec prettier --check scripts/package.mjs` | 最终 **6 PASS**与格式PASS，`/tmp/easyai-cv-package-resources-20261018-final1.log` / `/tmp/easyai-cv-package-format-20261018-unique1.log`；合成allowlist复制覆盖CV资源及离线合同引用/拒覆盖/漂移/清单，不生成真实便携包。早一轮6PASS范围重合不累计。 |
| 独审 `pytest services/backend/tests/test_install_cv.py services/backend/tests/test_install_ml.py -q` | **12 PASS/0.40s**，`/tmp/easyai-cv-ml-review-8QeoCK.log`；与集成回归重合不累计。来源、markers/闭包/预算/显式import/unsupported门无新增明确P1/P2；没有编辑文件。 |
| 独审限定JSON/.metadata再次核验 | **5发行全部PASS**，`/tmp/easyai-cv-metadata-review-8p8iyg5c.json`；发行SHA/字节/URL与METADATA SHA/版本/依赖全部匹配，captureJSON SHA未变。OpenCV supported=false，没有因元数据匹配解除native门。无wheel请求/安装/真实probe。 |
| `git diff --check` / `git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` / 原件及核心/ML hash | **PASS**；推前dev=1d526f9f5284144f84814f4a285acc6a98e450ec，main=5323f86232529efcfb52131168ad049f01b219f3；普通dev提交后push并核远端。 |

初稿5个CV专项首次5PASS。初次check **FAIL**仅install_process.py import行需要ruff排版；格式修正后check PASS，无测试或执行门放宽。第一次构建已PASS但早于该排版，最终重建PASS并仅对最终产物跑冻结检查。所有中间日志以唯一noclobber保留，不将多窗口结果累加，不覆盖失败。

- `/tmp/easyai-cv-metadata-capture-20261018-unique1.log` SHA256 `a363747741bb0402d1cf588b917ac3f17f89233392f827c842b70efcd8b56745`。
- `/tmp/easyai-cv-new-20261018-unique1.log` SHA256 `298bc9ad8b9c84af926c34ad8aa487152193d43e8bd22bc298879acb78df3351`。
- `/tmp/easyai-cv-check-20261018-unique1.log` SHA256 `643e3e588f925a77901c68928e9549e77ebb51832c009cc00ed72dbcb73ee392`。
- `/tmp/easyai-cv-check-20261018-final1.log` SHA256 `579d7a59a9a3491a792d03865e912d944d46d313ead69531b753b11aa4443de8`。
- `/tmp/easyai-cv-regression-20261018-unique1.log` SHA256 `bd6ab77b9cd3d4b7dd0ee95c4795f675aafebb6cd12001dc00bea779179deed1`。
- `/tmp/easyai-cv-build-20261018-unique1.log` SHA256 `7ec5ed0031d4bceb38a0c80029e26826627e0e95585a61ce2a093f4a3e6c602e`。
- `/tmp/easyai-cv-build-20261018-final1.log` SHA256 `3db182660a47de1fed9c4685a3f0e1e8391455bccad015b6d6f36bd7f82379b1`。
- `/tmp/easyai-cv-frozen-20261018-unique1.log` SHA256 `598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。
- `/tmp/easyai-cv-package-resources-20261018-unique1.log` SHA256 `15585416d158e5c29179bcf177bdba2be404eeec9f60a0281d41c6a25938de05`。
- `/tmp/easyai-cv-package-resources-20261018-final1.log` SHA256 `8221c38905c89c54273dda3df80a72f4518f47fca25796ad6ce7991e75a43f26`。
- `/tmp/easyai-cv-package-format-20261018-unique1.log` SHA256 `17aa973d3f004560237d9a95171210b0671deff23d61628eecf7322ff5938f20`。
- `/tmp/easyai-cv-ml-review-8QeoCK.log` SHA256 `eca6a5c460e7aadc57acfc8052b467af80ac8212d0ea7ae79073684021d90a15`。
- `/tmp/easyai-cv-metadata-review-8p8iyg5c.json` SHA256 `79cf1dab6222108a9e4e8d2257c607a7a283bd0a93f72e0d8dc1c5beefa37f2e`。


NOT RUN：wheel/sdist/模型/数据下载、真实conda/pip/安装/环境创建、scikit-image或cv2真实import/ABI/tensor正向/系统库安装、训练/真实SSH、新许可/凭据/网络权限、Electron原生picker/桌面/Windows/干净机、全套大矩阵、重打实际portable/发布。真实安装仍缺可信本地来源/许可及具体owned目标/预算/窗口，**未授权且未执行**；OpenCV另缺精确发行系统库清单与目标验证证据，保持unsupported，不是待自动重试。没有不确定外部安装结果。

核心sources SHA2562628fc7071ca97301e1069dd8bcf20de72eefdeed5e065969c497cf4f89641c5、核心lock f30a1d2eb86b13a7ae8a708e3356fade92e8dd942f746616a66376f281d8641b、ML sources2077c40f335d19027245e31e0f1cfb867c33257a2997332ee408d9f9490a76f9、ML lock c2a5de84967d110330d476098efd63acfce233ccea93bb8bad25ee44beef9403均未改。计划116185字节SHA256 dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43，旧规格5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190，README befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852保持。旧portable source7b91c46未含本片；distributionReady/legalReviewComplete仍false。CIFAR待裁决；旧226PASS/1FAIL根因UNKNOWN且原始日志丢失不回溯关闭。既有Actions读取/sandbox拒绝未重试或绕过，无本片新CI判断。无main/强推/PR/Release/部署/费用/凭据/安全权限变更，无新工具拒绝/未知外部写入。

下一项：父侧复核CV闭包和OpenCV明确unsupported边界；随后Main来源选择仍待补，余可选卡逐组核元数据/约束及许可，不能猜锁或用卡数冒称真实安装。完整M5/M6.3/B仍未验。


## 2026-10-18 — Main原生离线来源选择/核验预览/明确登记

源码完整SHA **`afa8f65c771d8905168bf417b82009392ef109dc`**；基线 `9bb093d64bfcc0c6d71de2762d6c2f0ef570712a`。按父级明确转向Main来源入口，不再逐包扩卡；复用原OfflineConfiguration/InstallRuntime/InstallPlan/唯一worker，无新包解析器或安装器。单一集成者、既有worker独立只读审查。产品合同 `docs/install-source-picker.md`；未实际登记真实来源/取得新执行授权。

先核Main全树main/workflow/preload/bridge/包管理：基线只有工程/数据/Python/私钥等native选择与catalog/plan/job入口，无等效安装来源选择。基线 `git grep -n -E 'install-source|installSources|chooseSources|confirmSources|install-runtime|showOpenDialog' 9bb093d64bfcc0c6d71de2762d6c2f0ef570712a -- apps/desktop/electron` 仅原showOpenDialog命中，日志 `/tmp/easyai-source-baseline-audit-20261018-unique1.log`；结合完整读Main路由后才新增固定入口。

- 正常包管理入口选择可信操作者准备的私有JSON清单：Main原生openFile+固定JSON filter，renderer仅packageIds，不接受路径/命令/index或授权字段；既有sender/mainFrame/sandbox/CSP门保持。取消不调用后端确认、不改当前配置。Main本次backend/epoch/id/hash收据与迟返后验，换backend/dispose/新选择后旧结果不能冒作当前成功。
- 两条鉴权HTTP来源preview/confirm及四个Pydantic权威生成合同；请求错误固定码、不回显私有路径，预览只含basename/实际SHA/bytes/模块树hash/源档案与wheel合计、解包未知、磁盘预算/命令时限/原授权截止和预览期限。原private manifest/launcher/module/bootstrap/wheelhouse的hash/bytes/身份与保护祖先合同复用，没有仅选文件就信任/执行。
- 单内存收据不跨重启，60秒且不超过authorizationExpires，另用monotonic限时；绑定清单真实SHA/身份、全部已核来源、现配置字节/身份、app根身份、具体包闭包与预算。确认重读来源/权限/身份/预算/expiry和现配置，漂移/过期/关闭拒绝，不自动重试。实际写私有临时文件fsync→原子固定配置发布→目录fsync；重放成功收据不重复写。发布结果不明标COMMIT_UNCONFIRMED，当前会话来源写入停止，先核现配置。
- **登记一律executionAuthorized=false**，不从所选清单搬迁true，不默认启用；UI确认前明确告知。预算/时限/authorizationExpires原值及时间含义保留，不延长。登记只改固定应用配置，外部来源原件不写。源真实性/许可/实际主机执行授权仍独立操作者门，之后重新生成原InstallPlan并另行明确确认；此任务没有执行安装。配置真实身份进入runtimeFingerprint，使替换/登记后的旧plan stale。
- UI显示原生选择、核验明细与预算、严格明确确认；源确认成功清旧plan/checkbox、刷新能力，由原按钮重新生成计划，不自动安装。teacher-existing只读方案不开放此CPU来源按钮。源错误/取消不伪称登记成功，不输出原始路径错误。
- 独审实证并关闭跨实例P2：原只看本service缓存，先打开的B看不到A后来durable INSTALLING且持环境lease。现配置提交持内核.install-source.lock并用原read_events/read_install_job新读INSTALLING/VERIFYING/CANCEL_REQUESTED；安装execute写INSTALLING WAL也短持同一锁，持久意图可见后才释放并进行baseline/bootstrap/install。消除“检查后另一writer才登记”的窗口，不串行整个不同环境安装。未知持久意图保持阻挡。跨实例readonly规划probe不当安装writer/静止证明，各服务保留自身owner；旧配置计划由fingerprint拒绝。Main confirm await后亦补epoch/backend/receipt后验。
- 新合同文档纳入原离线docs allowlist；只重建冻结后端，本片未重打旧portable。9/17解析卡、OpenCV native unsupported、CIFAR及所有真实验收边界未改变。

| 实际命令 | 结果与证据 |
| --- | --- |
| `services/backend/.venv/bin/python -m pytest services/backend/tests/test_install_source_selection.py services/backend/tests/test_install_runtime.py services/backend/tests/test_install_service.py services/backend/tests/test_install_probe_ownership.py services/backend/tests/test_owned_creation.py services/backend/tests/test_install_process.py -q` | **87 PASS/11.64s**，`/tmp/easyai-source-regression-20261018-unique1.log`；来源/旧安装生命周期相关回归。最终仅将source提交的assert改成显式拒绝条件（优化模式也保留门），再跑来源专项**13 PASS/0.48s** `/tmp/easyai-source-new-20261018-final1.log`。范围重合不累计。私有manifest均小型合成真实文件/hash，禁止实际Popen/conda/probe/install；原std子进程测试仅证进程合同。 |
| `pnpm exec vitest run apps/desktop/electron/install-source-workflow.test.mts apps/desktop/electron/install-workflow.test.mts apps/desktop/src/PackageManager.test.mts` | **35 PASS/3 files**，`/tmp/easyai-source-ui-20261018-final1.log`；Main正常选择/取消/renderer路径命令授权越权/换backend/迟返，UI核验预算/新明确确认/旧plan失效/错误隐私；原安装MainUI合同不降级。原生picker用注入回调，无Electron窗口。 |
| `pnpm exec vitest run apps/desktop/src/App.test.mts -t 'package'` | **1 PASS/24因过滤未运行**，`/tmp/easyai-source-app-entry-20261018-unique1.log`；普通包管理面板打开/隐藏保留与只读入口。不是App全套或桌面E2E通过。 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm contracts` / 同缓存 `pnpm check` | 合同生成PASS；最终 **check PASS**，`/tmp/easyai-source-check-20261018-final2.log`；TS/Main/tests、ruff/format116Python、strict mypy63、合同/实际Blocklyfixture/Prettier。source请求内部路径不入renderer输入合同。 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache XDG_CACHE_HOME=/workspace/.cache pnpm build` | 最终 **PASS**，`/tmp/easyai-source-build-20261018-final1.log`；Vite/TS/PyInstaller包含最终代码及新source模块，原chunk提示保留，无下载或依赖安装。之后仅一处文档措辞精确化，无源码/资源改动。 |
| `node scripts/test-frozen.mjs` | **PASS**，`/tmp/easyai-source-frozen-20261018-unique1.log`；实际冻结后端临时cwd，新来源route鉴权、私有合成无效清单拒绝/无路径回显/不生成配置，原六份来源资源/core/ML/CV禁用计划/OpenCV门/工程/黄金编译/EOF退出。没有真实正向来源或安装。 |
| `node --test scripts/package.test.mjs` | **6 PASS**，`/tmp/easyai-source-package-docs-20261018-unique1.log`；合成离线复制/新增合同文档allowlist/拒覆盖/完整清单/漂移，未生成真实便携包。 |
| 既有worker独审来源/锁序/收据 | 后端来源 **13 PASS/0.46s** `/tmp/easyai-source-backend-review-DXmnAN.log`；Main **11 PASS/176ms** `/tmp/easyai-source-main-review-Z5P6OC.log`。覆盖范围与上表重合不累计。最终无新增明确P1/P2；未编辑文件/真实source配置/下载/安装/probe。跨实例初始实证为消息中std线程/JSON门结果，未伪造不存在的原始日志。 |
| `git diff --check` / `git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` / 原件及所有core/ML/CV来源锁hash | **PASS**；推前dev=9bb093d64bfcc0c6d71de2762d6c2f0ef570712a，main=5323f86232529efcfb52131168ad049f01b219f3；源码与证据普通dev提交后push核对。 |

中间FAIL保留：初次check因两处旧API测试mock未补新方法/生成的packageIds tuple需按权威合同类型收窄而FAIL，补mock及类型后PASS，未将新方法改成可选以隐藏错误。来源第一轮**10PASS/1FAIL**是合成cross-instance测试错误注入enabled runtime触发旧唯一worker，写好的模拟INSTALLING随后被worker改写；测试已全局禁Popen，无真实source执行。改为无runtime的仅登记器再写受控持久意图，增加writer在配置锁期间不得发WAL测试后**12PASS**；加鉴权HTTP及固定错误隐私后**13PASS**。新Main/UI首次35PASS；最终窗口重复范围不累计。首次build已PASS，后续安全条件由assert显式化后最终重建再测冻结产物。所有日志唯一noclobber，无覆盖失败/放宽执行或测试门。

- `/tmp/easyai-source-baseline-audit-20261018-unique1.log` SHA256 `2a43c90d3343123eaf57c4bd511539a1a32794ae84896ac3da5317eb93efc989`。
- `/tmp/easyai-source-contracts-20261018-unique1.log` SHA256 `3afb0b9bfa755e4057fd0660122df77ea5ab794990f17751dc9da3d90ea5c978`。
- `/tmp/easyai-source-check-20261018-unique1.log` SHA256 `0efe0470d6c5212ec4b1196e7d842d54ac3b8ca95603dc83eca76f97751cda45`。
- `/tmp/easyai-source-check-20261018-unique2.log` SHA256 `95d0939927ab51e2812dc998c369fd396f986f2baf6c48f08c5009a286d0399b`。
- `/tmp/easyai-source-check-20261018-final1.log` SHA256 `95d0939927ab51e2812dc998c369fd396f986f2baf6c48f08c5009a286d0399b`。
- `/tmp/easyai-source-check-20261018-final2.log` SHA256 `95d0939927ab51e2812dc998c369fd396f986f2baf6c48f08c5009a286d0399b`。
- `/tmp/easyai-source-new-20261018-unique1.log` SHA256 `b69be1195d82451036bfcb79ac2ac952a7643f50278b22e1f6ee1b1b97eff95b`。
- `/tmp/easyai-source-new-20261018-unique2.log` SHA256 `5d8d78f124073188f022cb94462b8308cee04f152b7769103e3dc78c15a9fd5a`。
- `/tmp/easyai-source-new-20261018-final1.log` SHA256 `2dc33e2036db3b53b52b384dec7ac85f04164d88131705725acefdea1cafa664`。
- `/tmp/easyai-source-regression-20261018-unique1.log` SHA256 `e0aa44ec579d43c51f09aa0910f94b7546989e60cba52b73f8fe87ac86b67719`。
- `/tmp/easyai-source-ui-20261018-unique1.log` SHA256 `85fd8ce121e805178f190d2388026f1ecf730abebf3c24d7999244710ea0490c`。
- `/tmp/easyai-source-ui-20261018-final1.log` SHA256 `785f010543c53a2d1b5414d8215c58a69fff43bd4e95bfbbe06a43ea59266bea`。
- `/tmp/easyai-source-app-entry-20261018-unique1.log` SHA256 `431db664eb446398394b241869d545491d17a4b999289b127d0db1f2e5632708`。
- `/tmp/easyai-source-build-20261018-unique1.log` SHA256 `0ee4e5cc8266db1a4ed15cf1030ff38ad02b915096a0746f4a0a12e64ced963b`。
- `/tmp/easyai-source-build-20261018-final1.log` SHA256 `5a73cc7644fcaf43fe72f3cb2a701343e1a9f209a6d5d59b89673b0de7041030`。
- `/tmp/easyai-source-frozen-20261018-unique1.log` SHA256 `598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。
- `/tmp/easyai-source-package-docs-20261018-unique1.log` SHA256 `55cf7fa1883c31e75b89413eb3ec663399c45eae86c84f6200a81e8e63f332d1`。
- `/tmp/easyai-source-backend-review-DXmnAN.log` SHA256 `13164ad36269e8dc865448f9f35d79a9509e1b88cd4d16a7f7001c271559c170`。
- `/tmp/easyai-source-main-review-Z5P6OC.log` SHA256 `ed923e6132b0bb592286e55a09c3867ff4a064581bc68bda4ad40a7aab18544a`。


NOT RUN：真实Electron原生来源对话框/实际主机来源登记或信任授权、launcher/conda/pip/安装/下载/环境创建/真实imports/ABI/tensor正向/probe/训练/真实SSH、凭据/新权限/许可接受、Windows/干净机/全套大矩阵/重打实际portable/发布。真实来源、许可及具体一次性owned目标/预算/窗口的独立执行授权未提供，**未授权且未执行**；没有不确定外部安装结果。原生窗口仍受既有sandbox拒绝限制，未重试/绕过；本片只交付实现与定向合成验证，不冒充原生/真实安装验收。

计划116185字节SHA256 dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43、旧规格5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190、README befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852保持。core/ML/CV六份来源与锁全部未改（hash与上片相同）；卡数仍9/17，OpenCV系统库未核保持unsupported，不换headless。CIFAR待裁决；旧226PASS/1FAIL根因UNKNOWN且原始日志丢失不回溯关闭。旧portable source7b91c46未含本片，distributionReady/legalReviewComplete仍false；既有Actions读取/sandbox拒绝不重试或绕过，无本片新CI判断。无main/强推/PR/Release/部署/费用/凭据/安全权限变更、无新工具拒绝或未知外部写入。

下一项：父侧复核原生来源选择/预览/明确登记与独立执行授权边界、跨实例WAL交接门；真实原生窗口与来源/安装验收仍需具体目标和独立授权，完整M5/M6.3/B未验。此片不再把“Main来源入口未实现”作为代码缺口；仍不支持自动发现/信任任意原始二进制或不经操作者清单的自由路径安装。


## 2026-10-18 M6.3 普通面板安装历史与只读报告

源码完整SHA `528b9b21aa8e8629a8938099ccc64f0d80fb5445`，基于已接收的 `91482b57e630be5aa1c38aa21799345c89e36e24`；普通开发分支 `codex/demo-v0.0.0`，origin=T1doo/Easy-AI。推前只读 `git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` 确认dev仍91482b57、main仍5323f86232529efcfb52131168ad049f01b219f3。本地未配置origin远端跟踪ref，`git rev-parse HEAD origin/codex/demo-v0.0.0` 对第二参数失败；使用实际ls-remote确认，没有猜测远端状态或重设已有用户配置。源文件和已有工作保留，本片未重写原计划/规格/README。

交付[安装历史合同](install-history.md)：沿用原持久账本64项上限，新增固定鉴权GET列表/报告、Main固定IPC及普通包管理面板自动发现/刷新/查看报告，不需预知jobId。报告区分最后持久记录和本次观察，当前实例实际登记存活worker、重启历史、外部实例记录及停止未确认；历史verified不冒充当前环境健康，currentEnvironmentVerified恒false。只读报告只展示原有生命周期摘要与变更/复检标记，无完整安装器原始输出归档声明。不向历史报告接回执行、取消、重连或自动清理按钮。

恢复旧AWAITING_EXECUTION仍作废；旧执行未知保持STOP_UNCONFIRMED隔离。新读取不取得日志writer、不修复部分尾行、不按旧PID发信号、不接管foreign job、不改内存执行状态、不释放unknown owner/reservation/lease。每任务读取上限4MiB/512完整记录，身份/序号校验继续有效。目录在第65项拒绝；未新增保留策略/自动清理/无限分页/新安装worker。合同从Python生成TS/schema。

独审发现并已修复P2：原_saved_jobs先list(Path.iterdir)再检查64，拒绝前可能枚举整个目录；合成2000项复现。改os.scandir上下文+islice65，历史读取与启动恢复新增测试均消费65项即拒绝并关闭迭代器。既有只读审查worker独立复核通过，无新增明确P1/P2，没有新建worker。

| 实际命令 / 范围 | 结果 |
| --- | --- |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm contracts` | PASS；新增History/Report合同，原InstallJob DTO不变。 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm check` | 最终PASS；TS/Main/tests、ruff/format117Python、mypy63、合同/实际Blocklyfixtures/Prettier。 |
| `cd services/backend; .venv/bin/pytest -q tests/test_install_history.py tests/test_install_service.py tests/test_install_runtime.py tests/test_install_source_selection.py tests/test_event_journal.py` | 77 PASS / 10.40s；新历史6项包含纯读文件hash/ino/size、过期等待/成功/失败/未知、活线程/foreign实例/heldlease、界面读取无副作用、上限和鉴权；其他为原执行/source/journal回归。 |
| `pnpm exec vitest run apps/desktop/electron/install-history-workflow.test.mts apps/desktop/electron/install-workflow.test.mts apps/desktop/src/PackageManager.test.mts` | 27 PASS / 3files；固定GET、非法路径/自由参数拒绝、普通历史入口/过期确认只读及原安装/sourceUI。初次同范围也27PASS，不累计。 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache XDG_CACHE_HOME=/workspace/.cache pnpm build` | PASS；TS/Vite/PyInstaller，保留既有chunk提示，无新依赖安装。随后仅修正面板旧介绍文案，`pnpm --filter @easyai/desktop build` 最终PASS；后端与资源不变。 |
| `node scripts/test-frozen-install-recovery.mjs` | PASS；实际冻结sidecar两次进程启动/关闭，GET列表发现任务、只读报告、重复读取不改视图、旧等待确认失效；无训练环境创建/安装/probe。 |
| `node --test scripts/package.test.mjs` | 6 PASS；新增历史合同离线文档allowlist，拒覆盖/清单/漂移检查，未重打实际便携包。 |
| 既有worker独立只读复查 | 历史5PASS、Main1PASS；P2修复新增1PASS/5deselected，不与上表重叠累计。最终无新增明确P1/P2。 |
| `git diff --check` / 原件及core/ML/CV六份hash | PASS；字节/hash与上一片完全相同。 |

保留中间FAIL：新历史首轮4PASS/1FAIL，因为测试调用优雅close把模拟INSTALLING写为CANCEL_REQUESTED，期望的崩溃原记录不成立；改为仅关闭合成journal fd模拟进程丢失（断言无worker/lease/executing）后5PASS，再补边界测试纳入77PASS。check首轮因App mock的limit字面量扩大number导致TS失败，改为64 as const，未放宽合同。一次format命令在backend目录误用重复相对路径，uv先因默认/home/agent/.cache只读退出，未格式化/下载；随后用已存在.venv/bin/ruff正确路径成功。所有重跑用新noclobber日志，未覆盖失败或降低测试门。

日志原件在本执行器，SHA256如下：
- `/tmp/easyai-install-history-build-20261018-unique1.log` SHA256 `ac648f5bb0f5d3aa6340a5d1198a81adc348e786413df22b99b8bebd62d9daa8`。
- `/tmp/easyai-install-history-check-20261018-unique1.log` SHA256 `c50f83b83ec246bf8b380e45332327ce6556eab3f30bf41a61c6959f8a8fd3f7`。
- `/tmp/easyai-install-history-check-20261018-unique2.log` SHA256 `5b9546205d04c670ac61ad7a8bff82dc39bae1a167cdd98bbbe8937bece75271`。
- `/tmp/easyai-install-history-contracts-20261018-unique1.log` SHA256 `3afb0b9bfa755e4057fd0660122df77ea5ab794990f17751dc9da3d90ea5c978`。
- `/tmp/easyai-install-history-contracts-20261018-unique2.log` SHA256 `3afb0b9bfa755e4057fd0660122df77ea5ab794990f17751dc9da3d90ea5c978`。
- `/tmp/easyai-install-history-desktop-final-20261018-unique1.log` SHA256 `b8e2b86b2bf1927a8d3b07bb61130c69818cf38fc36a1e1af185a5e8dbde2ba8`。
- `/tmp/easyai-install-history-frozen-20261018-unique1.log` SHA256 `f440c15b1e2f24b53b29c78fb20698b3b895e395785e070baa6738dc6549c172`。
- `/tmp/easyai-install-history-main-review-QWLQ05.log` SHA256 `5eec8a8fe088810a3aeadd7442a15da7e5ed6cba781d8614c5a631922887fc9d`。
- `/tmp/easyai-install-history-new-20261018-unique1.log` SHA256 `5fe456a7f80e3edc0c2dd152c84cce899c79468acea3d46c45f7c443e1f2ed85`。
- `/tmp/easyai-install-history-new-20261018-unique2.log` SHA256 `09709a7254a6b75745892059f0e1cbc33ee00378cfff46809d5c01974e0d1a53`。
- `/tmp/easyai-install-history-package-20261018-unique1.log` SHA256 `624c115c5502a9345c53f277b2133c8324cb624f4999954d80dbafce688d47df`。
- `/tmp/easyai-install-history-regression-20261018-unique1.log` SHA256 `003008d08920731d48ffd90465f879846e9e06b59f2c3014c5135c0380428e55`。
- `/tmp/easyai-install-history-review-1JvYZc.log` SHA256 `7507cd7e05f5ecd5c920e4a798876dab01ffe4a2e66541ed96ac7064785972f1`。
- `/tmp/easyai-install-history-ui-20261018-final1.log` SHA256 `f784c5fc9a35ad1c6bb535ca58ab36d5542a53f88b8146a7a6e6a5a8179af0be`。
- `/tmp/easyai-install-history-ui-20261018-unique1.log` SHA256 `aa53c2bed4196baec42c039567f56cb7498cb0719394c5f3bb0b88e06f5982f2`。
- `/tmp/easyai-history-enumeration-fix-review-w2vMiu.log` SHA256 `3911bdbfb7a36d4b8af0c3652e36017568f51e9ea0bfdbbe2f318588f430fa52`。

NOT RUN：真实安装/probe/bootstrap/pip/训练/下载/import/tensor验收、实际来源或执行授权更改、真实SSH、原生Electron窗口、Windows/干净机/大矩阵/发布。具体真实来源/许可/owned目标/预算/窗口的独立执行授权仍未提供，未授权且未执行；无不确定外部安装结果。既有原生窗口与Actions读取拒绝不重试、不绕过，无本片CI判断。普通面板历史代码缺口已补，真实原生课堂验收不等于定向UI测试。

计划116185字节SHA256 dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43、旧规格5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190、README befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852保持。core/ML/CV六份来源与锁未改；9/17卡可解析，OpenCV仍因native要求未核unsupported，不换headless。CIFAR待裁决；旧226PASS/1FAIL根因UNKNOWN且原始日志丢失不回溯关闭。旧portable source7b91c46未含本片，distributionReady/legalReviewComplete仍false。无main/强推/PR/Release/部署/费用/凭据/安全权限变更，无新的工具安全拒绝或未知外部写入。

下一项：父侧复核历史读取不接管/不解隔离及报告健康边界；仍缺保留管理、存活安装重连与停止未知的显式安全解除。真实M5/M6.3/B条件与既有阻塞不因本片消失。源码与本证据仅普通开发分支提交推送，推后再次核对远端及工作区。


## 2026-10-18 父独审P2补修：持久空目录占槽与原子登记

父侧未签收上一片，准确指出：_saved_jobs跳过合法空UUID目录，但confirm只检查内存_jobs；63有效目录+1首事件前崩溃空目录恢复为63内存任务，新确认可创建第65目录，后续history/report/启动统一拒绝。此前“无新增P1/P2”仅是当时专项结果，不能视为完整配额证明。本补修源码完整SHA `b238e58bb01bc6a2f10f8454e1bebea82f2660bf`，基于 `2cdd7d5ad60da842e52bddae9107c90214592063`。

改前先用单实例确定性复现：63个合成FAILED记录，第64个确认在独占mkdir后、EventJournal首事件前注入OSError；保留合法空目录，关闭合成journal fd模拟进程丢失，再启动恢复。新增测试期望confirm拒INSTALL_JOB_LIMIT，改前实际未抛错，**1 FAIL/6 deselected**，原始失败日志保留。无真实安装、probe、网络、worker或环境创建。

修复抽出_ledger_slots，共用bounded scandir65及合法目录校验，空目录计占槽。confirm在既有 `.install-source.lock` 共享短提交锁内重新核持久总槽数>=64即拒；额度检查、独占mkdir及首条持久事件位于同锁区间，完成后释放再走原有内存登记/唯一worker流程。未新增锁框架、保留策略、自动清理或未知目录删除。额度与锁忙拒绝不置persistence_failed，原幂等确认仍先返回原任务，不消耗新槽。历史纯读仍不取得提交锁、不修尾或释放未知lease。

新增竞争测试：63持久空目录，两个服务竞争最后一项；首服务在既有锁内暂停首记录，第二服务确认拒INSTALL_SOURCE_BUSY且未登记/未毒化；首提交完成后共64目录，第二再确认拒INSTALL_JOB_LIMIT，历史与重启继续可读，未知空目录全部保全。独审只读复查锁序、占槽/预留原子区间、空目录保全和quota拒绝状态；新两项 **2 PASS/6 deselected/0.48s**，未发现新增明确P1/P2，交父侧再次核验。

| 实际命令 | 结果 |
| --- | --- |
| `cd services/backend; .venv/bin/pytest -q tests/test_install_history.py -k crashed_empty` | 改前1 FAIL，expected INSTALL_JOB_LIMIT DID NOT RAISE；不回改失败日志。首次新增测试写入命令因cwd误用重复路径失败，随后pytest未选中测试exit5/6deselected，另留unique1日志；改正路径后unique2才是有效复现。 |
| `cd services/backend; .venv/bin/pytest -q tests/test_install_history.py tests/test_install_service.py tests/test_install_runtime.py tests/test_install_source_selection.py tests/test_event_journal.py` | 改后 **79 PASS/10.76s**；含新增两项与原有注册/来源/执行/只读账本回归，禁止Popen/连接的历史fixture继续有效。 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm check` | PASS；TS/Main/tests、ruff/format117Python、mypy63、合同/实际Blocklyfixtures/Prettier。 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache XDG_CACHE_HOME=/workspace/.cache pnpm build` | PASS；包含修复的PyInstaller sidecar及桌面；无下载/依赖安装，既有chunk提示。 |
| `node scripts/test-frozen-install-recovery.mjs` | PASS；冻结sidecar实际重启、普通历史发现/报告与旧确认过期回归；此命令不声称冻结产物覆盖63+1故障注入，该边界由新增确定性pytest证明。 |
| 既有worker独审新两项 | 2 PASS/6deselected，与79项重叠不累计。 |
| `git diff --check` / `git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` / 原件hash | PASS；推前dev=2cdd7d5ad60da842e52bddae9107c90214592063、main=5323f86232529efcfb52131168ad049f01b219f3。 |

唯一noclobber日志及SHA256：
- `/tmp/easyai-install-slot-build-20261018-unique1.log` SHA256 `dc904e08010c55e78febbc5b8adedab7000de88a5646c6fc7742ea1bc4e5fbb0`。
- `/tmp/easyai-install-slot-check-20261018-unique1.log` SHA256 `5b9546205d04c670ac61ad7a8bff82dc39bae1a167cdd98bbbe8937bece75271`。
- `/tmp/easyai-install-slot-frozen-20261018-unique1.log` SHA256 `f440c15b1e2f24b53b29c78fb20698b3b895e395785e070baa6738dc6549c172`。
- `/tmp/easyai-install-slot-regression-20261018-unique1.log` SHA256 `51a1f5a188fe55ca4140224e094a7126bb00c26c3c6e5c169aa7e26b05164ebc`。
- `/tmp/easyai-install-slot-repro-20261018-unique1.log` SHA256 `058f36dceefc76919263c786f6ca168e7702f03f04b8ead0dfe5917cd3df3f26`。
- `/tmp/easyai-install-slot-repro-20261018-unique2.log` SHA256 `61ec846657e365269d966f55fd615c155d6339889f63bfc7496141def447d80c`。
- `/tmp/easyai-install-slot-review-TDF6l4.log` SHA256 `cae2423a8c1aa91b2ddd147e5aafdb59583e7c60349212a5744f9f1195e1eb64`。

NOT RUN：真实安装、probe、bootstrap/pip、训练、下载、SSH、原生Electron/干净机/Windows/真实安装验收、全套大矩阵/新CI查询/重打旧portable/发布；未授权且未执行。既有原生与Actions拒绝没有重试或绕过；无不确定外部执行。原计划116185字节及hash dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43、旧规格/README和core/ML/CV六份来源锁未改。CIFAR待裁决、OpenCV未核unsupported、旧226PASS/1FAIL根因UNKNOWN及旧portable source7b91c46均保留；完整M6.3/B未验。

工作区只含本次修复与证据；普通开发分支提交推送，推后核对dev完整SHA/工作区/main。无main、强推、PR、Release、部署、费用、凭据或安全权限变更。下一项为父侧重核此配额P2；不把“暂不签收”视为执行授权扩大。


## 2026-10-18 M8.2 正式 electron-builder Linux x64 纵切

父侧有限签收e11798c350bb1029c995c0bb520a7d12bdec4e1e并关闭持久占槽P2后，转原M8.2，不扩安装历史。实际包对应完整源码 **`5ab7a92e410650509785bf381d5bb4df8dab8399`**（首接线1f0f590、独占每次输出257c059，均保留于提交链）。本证据提交另有一处仅测试fixture修正：mode从实际lstat读取，避免POSIX 0644写死影响Windows文件语义；10项重跑PASS，无产品代码/配置/包资源变化，未冒称Windows运行通过。

交付[electron-builder合同](electron-builder.md)。从正规npm注册表读取版本/engine/license/integrity，精确新增electron-builder26.15.3（MIT），锁文件有完整npm integrity与传递图；原应用/Node/Electron直接版本不变。官网默认docs当前标next v27，稳定入口https://www.electron.build/v26/；files/extraResources概念查官方docs/contents，本地26.15.3自带configuration.d.ts/API/源码逐项核对，未使用next专属选项。

真实`pnpm package:builder`调用build API，固定Linux x64 dir+tar.gz、publish=never+配置null、不签名、不原生依赖重建、不换Electron/FFmpeg、不改sandbox。根electron-builder.json为固定基础选项、保留原io.easyai.desktop appId；默认app路径未准备，包装入口只绑定经原stagePortable资源/ELF/版本/allowlist/notices门的独占stage与output。dist/index.html+assets及flat生产Main/preload进入ASAR，sidecar完整onedir含_internal在resources/backend，offline/notices在resources下，许可证保留于产品根。旧产物/缓存不覆盖；每次用SHA前缀+时间戳独立输出，失败目录保留。初始验证选择compression=store约束CPU，归档体积据实记录。

目录旧构建残留dist-electron/electron/**/*.test.mjs已发现，最终files不收该nested树，并拒tests/maps。独审另发现P2：dist/.env.local会被dot=true收进ASAR，旧verifier仅拒精确.env；纯合成新增测试改前FAIL保留。现基础files和extraResources同时排除.env*与machine.local.json，ASAR校验同步拒所有.env后缀。最终真实构建前以独占xb写入仅“SYNTHETIC_BUILDER_PRIVACY_FIXTURE_ONLY”的dist/assets/.env.local，成功包实际排除该文件；finally核内容后仅删除自己的测试文件，无真实秘密/用户文件读取或覆盖。测试与源码均无真实私密材料/密钥。

### 实际产物（本地未发布）

- 目录：`/workspace/Easy-AI/dist/easyai-builder-5ab7a92e4106-1792364458569-linux-x64/artifacts/linux-unpacked`。
- tar.gz：同artifacts下`easyai-0.0.0-linux-x64.tar.gz`，**152688685字节**，SHA256 **`7445fb3e57d35393d48ebcd5f08dd52266e6c04728ab341bd0f50e5b31326b78`**。
- builder-manifest.json：输出根目录，SHA256 **`345a18f63253fe67b068e0df847734abd972aa7a7a6e4e8e9c53ae5f837aa76f`**；289输出文件记录，完整sourceCommit、builder/Electron版本、path/bytes/hash/mode；清单不是数字签名或可信来源证明。
- Python标准库tarfile只读扫描归档、不解包：287 regular files逐项bytes/hash/mode匹配linux-unpacked，无extra/missing/link/special/traversal；stage/合成.env.local未进入归档。
- `distributionReady=false`、`legalReviewComplete=false`；所有产物留本执行器ignored dist，未上传、发布、部署或创建Release/PR。

### 命令及真实结果

| 实际命令 / 检查 | 结果 |
| --- | --- |
| `pnpm view electron-builder version engines license dist.integrity --json` | PASS，26.15.3 / Node>=14 / MIT，根开发依赖精确版本与锁文件integrity。 |
| `XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache pnpm add -Dw --save-exact electron-builder@26.15.3 --ignore-scripts` | PASS；正常开发依赖+254/-2，4条既有式deprecated传递依赖警告保留；pnpm自动可选peer重绑定记录在锁，不伪称整个图无变化。没有新增lifecycle allowlist。 |
| 同XDG目录 `pnpm install --frozen-lockfile --offline --ignore-scripts` | PASS，锁无重新解析，已有store重用；确认精确开发安装可重现，不下载训练依赖。 |
| `XDG_CACHE_HOME=/workspace/.cache electron_config_cache=/workspace/.cache/electron node apps/desktop/node_modules/electron/install.js` | PASS。peer重绑定使新Electron物理目录缺dist，Electron44无postinstall，pnpm rebuild electron为noop；使用仓库原setup同一官方installer与已存在缓存恢复原44.9.0，不换版本、不启动窗口。 |
| `node --test scripts/package.test.mjs scripts/package-builder.test.mjs` | 最终 **10 PASS/642ms**；资源漂移/排除/拒覆盖/完整性+ASAR私密文件、extra/tamper/path traversal/release claims。9PASS中间结果与独审不累计。测试fixture最后改为读取实际mode，保留严格比较，不放宽门。 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm check` | 最终PASS；TS/Main/tests、ruff117Python/mypy63、合同、实际Blocklyfixtures与Prettier。之后仅上述fixture mode取得方式修正并Prettier+10项PASS，无产品代码变化。 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache XDG_CACHE_HOME=/workspace/.cache pnpm build` | PASS；实际TS/Vite/PyInstaller，既有chunk警告，不安装训练内容。 |
| `CSC_IDENTITY_AUTO_DISCOVERY=false XDG_CACHE_HOME=/workspace/.cache pnpm package:builder`（合成privacy fixture finally清理） | 最终PASS，真实electron-builder26.15.3生成本表dir/tar.gz，ASAR入口与stage逐字节比较，sidecar内置全部resourcePairs对源码hash比较，289记录完整性通过；源5ab7a92。 |
| `pnpm package:builder:verify dist/easyai-builder-5ab7a92e4106-1792364458569-linux-x64` | PASS；完整文件集合、bytes/hash/mode、ASAR入口/开发及私密文件拒绝、false门。 |
| `node scripts/test-frozen.mjs dist/easyai-builder-5ab7a92e4106-1792364458569-linux-x64/artifacts/linux-unpacked/resources/backend` | PASS；直接运行实际包内冻结sidecar，在temp cwd完成鉴权、资源/17卡离线计划、禁执行登记/取消、项目创建、原黄金MNIST代码编译及EOF exit0。未实际训练/import/probe/SSH；不是Electron窗口或干净机。 |
| Python stdlib `tarfile.open(...,'r:gz')` + `hashlib.file_digest`（实际inline脚本） | PASS；287文件hash/bytes/mode与manifest linux-unpacked记录完全相同；拒绝任何link/special/extra/缺失/路径越界，不解包。 |
| 既有worker独立只读源码/产物复查 | 初始两组9PASS消息；隐私P2修复4PASS/745ms `/tmp/easyai-builder-privacy-fix-review-lAQZcS.log`；最终包289记录verify、tar287逐项匹配、ASAR关键入口/私密fixture排除与source/hash/false门PASS消息。后两项实际包审查未提供另一个原始log文件，按消息证据记录，不捏造文件；未重新package或启动窗口/安装/probe。 |
| `git diff --check` / `git ls-remote origin refs/heads/main refs/heads/codex/demo-v0.0.0` / 原件与来源锁hash | PASS；推前远端dev=e11798c350bb1029c995c0bb520a7d12bdec4e1e，main=5323f86232529efcfb52131168ad049f01b219f3；普通dev push后再次核对。 |

首次依赖命令默认/home/agent/.local/share/pnpm目录不存在而失败，未安装；改为工作区合法XDG目录后成功，无权限提升或绕拒绝。首次实际包装在stage preflight发现新peer Electron dist/version缺失而FAIL、未调用builder，失败目录和日志保留；官方installer正常恢复后独立新目录重跑。中间257c059候选已实际完成，144625879字节、SHA8108b3f9c77faf2ea81bd13b0b924f3b6070199c49391ba7140dbb4cd1e63e7c；它不包含最终隐私过滤/canonical配置修正，不作为交付候选。最终5ab包独立重建，无覆盖中间产物或失败日志。

tar.gz首次真实builder自动取得官方`electron-userland/electron-builder-binaries`固定`7zip@1.0.0`工具集（构建工具，不随应用发布），缓存`/workspace/.cache/electron-builder/7zip@1.0.0/7zip-linux-x64.tar.gz` SHA256 `d151bb44b2a9d9bfc52813ce4cac042916394a0ab8a56bd5d221a5dc9ef8d5d7`，与26.15.3内置checksums精确相符；无自由下载URL/脚本替换/新费用权限或需确认条款出现。正式builder流程不是完全离线复制；旧pnpm package离线流程保持独立。新许可明确接受、签名/部署/发布仍需另行授权，未执行。

唯一noclobber日志SHA256：
- `/tmp/easyai-builder-archive-20261018-unique1.log` SHA256 `ade44ac1c19b5289441b3bdb08dc39d790afb83672fa6bcf4c2a8127cac0d7f2`。
- `/tmp/easyai-builder-build-20261018-unique1.log` SHA256 `b6d0d4792ebf306b0cdafcbd85358c2be398eddbcd4b3313f617de297223a899`。
- `/tmp/easyai-builder-check-20261018-final1.log` SHA256 `5b9546205d04c670ac61ad7a8bff82dc39bae1a167cdd98bbbe8937bece75271`。
- `/tmp/easyai-builder-check-20261018-unique1.log` SHA256 `5b9546205d04c670ac61ad7a8bff82dc39bae1a167cdd98bbbe8937bece75271`。
- `/tmp/easyai-builder-dependency-20261018-unique1.log` SHA256 `2d5d739f90ca435e406a1e3ec65b425c159ec6aee3938aaf9618851ca2a18bd3`。
- `/tmp/easyai-builder-dependency-20261018-unique2.log` SHA256 `d8a2294223e509a93cdf9f7635795bb43d93e4195886cbbb192cc590d9026704`。
- `/tmp/easyai-builder-electron-20261018-unique1.log` SHA256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。
- `/tmp/easyai-builder-electron-20261018-unique2.log` SHA256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。
- `/tmp/easyai-builder-lock-20261018-unique1.log` SHA256 `061536f492c75a59453142577e85ea5ea03df74d8d72d220b378a65a9e22842c`。
- `/tmp/easyai-builder-package-20261018-final1.log` SHA256 `f93db63ba258805bf15257ffe778a1b3526051c71eef22a0170c39ec9ea07f3f`。
- `/tmp/easyai-builder-package-20261018-unique1.log` SHA256 `5f9105b8e591c5aa3d96455ce597c4e71801ad6167ae6629abb6ff39c72aa084`。
- `/tmp/easyai-builder-package-20261018-unique2.log` SHA256 `013478821109783afa9146d843821c5548a7f12d140c97bc149591e686aa634f`。
- `/tmp/easyai-builder-privacy-fix-review-lAQZcS.log` SHA256 `5eea1e59480bd39ed6aa13730b65bc0e37a3c8c1c8a55ef3e57d0deb5fab6c84`。
- `/tmp/easyai-builder-private-repro-20261018-unique1.log` SHA256 `56309c1c83a79348315cd41456a0f577eed4995386abff086b00c015907de3e8`。
- `/tmp/easyai-builder-sidecar-20261018-unique1.log` SHA256 `598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。
- `/tmp/easyai-builder-tests-20261018-final1.log` SHA256 `9af6b78547c5efd83671ac9ecb6b9d93b073780912a81033e6b02321b08e54eb`。
- `/tmp/easyai-builder-tests-20261018-final2.log` SHA256 `167f8d6666ead3407e9eb93a996f4827789b11d5d4d83fc3f3daf62ae4e3be8b`。
- `/tmp/easyai-builder-tests-20261018-final3.log` SHA256 `cb645f0eae6091cc2bea656db761d25a40ee93b4b3b035bc7e40f5d03b610794`。
- `/tmp/easyai-builder-tests-20261018-final4.log` SHA256 `4dec6a2f705b700a273b134af420ea79e628508529e780463cabdafa14239784`。
- `/tmp/easyai-builder-tests-20261018-unique1.log` SHA256 `b90490dcb0e20cec305677aa776b9419ccbc14ed87b45a8a3f1a9acabb175312`。
- `/tmp/easyai-builder-verify-20261018-unique1.log` SHA256 `4fbf4cd56d24c9333dbbded7edb1de4a753f0600daa8691e7f1e8cb148936176`。

NOT RUN：真实Electron原生窗口/沙盒运行、无Node/开发Python干净目标机编辑及连接已备训练环境、Windows/macOS/跨平台包/签名/安装升级卸载/课堂恢复/性能矩阵、真实安装/probe/bootstrap/pip/训练/数据模型下载/真实SSH、新CI读取或发布。原生sandbox与Actions端点已有拒绝仍不重试/绕过；不是本片新拒绝。未出现待确认新条款/费用/安全权限；无不确定外部写入。实际产包+HTTP/编译smoke不等于完整M8.2/M8/B，平台真实可用性仍需目标机验收。

原计划116185字节SHA dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43、旧规格5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190、README befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852及core/ML/CV六份来源与锁全部未改。旧portable source7b91c46保持，其package-manifest SHA5f26ba7bb27917e717faec81c69d98ea97e3e39064ac4490b3e65fcc012fd937，新builder产物独立，不冒充旧portable更新。CIFAR待裁决、OpenCV native未核unsupported、旧226PASS/1FAIL根因UNKNOWN及真实M5/M6.3条件仍保留。

下一项为父侧核对正式builder依赖/布局/包证据与隐私P2收口；后续M8.2目标机/原生窗口验收需已有阻塞解除或明确可用目标条件，不自动发布或扩权限。没有main/强推/PR/Release/部署/付费/凭据/安全权限变更。工作区证据提交后仅正常开发分支push并核远端完整SHA。


## 2026-10-18 父独审输入封闭P2补修及M8.2/TST33条件盘点

父侧暂不签收5ab7a92e410650509785bf381d5bb4df8dab8399：旧stage整树采用现成dist/Main/backend/tutorials，output inventory会自动认可额外普通文件。该静态可达性成立，**不是发现旧包已泄露真实秘密**。本轮只关闭批准输入集合缺口；不宣称任意秘密排除或秘密扫描。

最终实际新包对应完整源码 **`5b3df8d565f75a1f5cdeaf4e2f9300ce04bee17f`**。提交链保留28bb7ca/f768d4e/562f7ce/83974d2/56861fc的中间修正与失败证据；最终产品代码/配置没有在产包后修改。普通开发分支codex/demo-v0.0.0，origin=T1doo/Easy-AI，推前远端dev=5f85d252d9c89f7856c520526054597a31e70301、main=5323f86232529efcfb52131168ad049f01b219f3。

### 本范围实际变更

- 正式builder不再调用旧stagePortable采纳ambient dist。新package-inputs在独占目录从指定完整commit的Git archive导出源码，git ls-tree仅允许普通tracked文件，拒source symlink/submodule；ignored/untracked源码不暴露给tsc/PyInstaller。构建前与封存前再核HEAD/clean及普通untracked，保留用户工作，拒绝而不重置。Vite关闭publicDir递归复制。
- 教程只批准七个TUTORIAL_FILES路径，实际集合出现任何额外文件就拒；非黑名单名extra-lesson.md可证明。docs/示例仍按明确单文件集。应用、sidecar、notices均在新目录产生，Python的dist/work/spec与数据路径单独绑定；不采用旧构建/缓存输出为新输入。Electron按已锁44.9.0官方archive/checksum新解压，不采用installed dist。
- Node工具在快照真实node_modules按frozen lock、offline、ignore-scripts安装，复用已登记store，354 reused/0 downloaded。应用构建venv也用原uv.lock在快照新建、offline/frozen同步43个应用依赖；无torch/训练依赖。UV_PROJECT_ENVIRONMENT显式固定绝对新路径并去VIRTUAL_ENV，前置要求目标不存在，完成核目录非link且realpath匹配。原应用venv只提供已存在Python基线，不作为同步目标；没有共享训练环境操作。编译器/标准库/已锁第三方依赖仍是信任边界，非完全hermetic声明。[uv官方目标路径说明](https://docs.astral.sh/uv/concepts/projects/config/#project-environment-path)支持此次覆盖门，不执行危险外部环境复现。
- 干净生成结束才封存approved-inputs.json，app/backend/offline/notices/vendor五个固定组，完整sourceCommit与vendor archive hash、每文件path/bytes/hash/mode。仅对新payload声明data0644/已有执行位0755归一，去特殊位；不改系统/helper安全权限。stage前后核集合并只复制登记文件，builder后再核stage；输出资源和ASAR必须与先前批准输入逐项对应。output inventory不能自动批准额外文件。vendor仅声明已证实的electron→easyai及LICENSE复制/改名变换，官方default_app.asar原批准记录保留。
- builder manifest v2内含批准收据；旧v1包和raw证据保留，旧PASS不再被解释为输入封闭证明。旧pnpm package复制入口只保留兼容，未冒称获此输入封闭门。未新增包装目标、安装器、发布、签名、远端或训练功能。

### 最终新包与独立证据

- 输出根：`/workspace/Easy-AI/dist/easyai-builder-5b3df8d565f7-1792365720449-linux-x64`；dir为`artifacts/linux-unpacked`。
- tar.gz：`artifacts/easyai-0.0.0-linux-x64.tar.gz`，**152691264字节**，SHA256 **`008a7d991e49111b27b85ca932206361635026b7aadd8c67f8d566bdb6620254`**。
- builder-manifest.json SHA256 **`a9d3b42f6d7111589091a450a3cb6d8b8835c7da5c1ca54a7c974baa2c505aa1`**；289条输出记录，批准输入组计app33/backend137/offline18/notices58/vendor72。
- 原批准收据：`dist/builder-inputs-5b3df8d565f7-1a18e621-3e77-4cb9-a04a-952a13be7c60/approved-inputs.json` SHA256 `d0dd59167606acec53c1cf4baeca2aa28caa3da18a83c88e3b71337c3d7f585c`；亦嵌入builder manifest。Electron archive SHA256 `ecced7ecb55697f92ca870939c5988557faa8acd8c222c232cae5913d318c8b9`，来自注册精确版本并校验，非自猜URL。
- tar标准库只读审计287 regular files逐项匹配unpacked bytes/hash/mode，无额外、缺失、link/special/traversal，不解包。独审独立重复通过；stage/source/.venv等不进入归档。
- 最终distributionReady=false、legalReviewComplete=false，无发布、上传或正式交付宣称。

| 实际命令 / 范围 | 结果 |
| --- | --- |
| `node --test scripts/package.test.mjs scripts/package-builder.test.mjs scripts/package-inputs.test.mjs` | 最终 **20 PASS/871ms**；七教程集合、五组普通名字bonus-object.bin追加后拒绝、原收据不变/不stage、登记文件修改/删除、output inventory自行追加additional-reading.json仍拒、固定Git tree不含ignored core.private.mts/untracked ordinary-extra.mts且原件保留、UV外部目标参数被固定新路径覆盖并拒既有目录；原完整性测试保持。 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm check` | 最终PASS；TS/Main/tests、ruff117Python、mypy63、合同/实际Blocklyfixtures/Prettier。 |
| `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache XDG_CACHE_HOME=/workspace/.cache CSC_IDENTITY_AUTO_DISCOVERY=false pnpm package:builder` | 最终PASS。真实从Git快照生成tsc/Vite/PyInstaller新输出，Node与应用依赖均offline/frozen，新vendor与来源校验；真实builder dir/tar.gz，289记录与批准闭集通过。该命令包含实际干净build，不用旧pnpm build结果冒充。 |
| `pnpm package:builder:verify dist/easyai-builder-5b3df8d565f7-1792365720449-linux-x64` | PASS，v2输入/输出两层、五组闭集与ASAR bytes/metadata。 |
| `node scripts/test-frozen.mjs dist/easyai-builder-5b3df8d565f7-1792365720449-linux-x64/artifacts/linux-unpacked/resources/backend` | PASS；实际包内sidecar temp cwd鉴权、资源/离线计划、禁执行登记取消、工程创建/黄金编译、EOF exit0；没有训练/probe/SSH。 |
| Python stdlib tarfile/hashlib.inline脚本（只读） | PASS，287文件逐项bytes/mode/hash匹配，没有提取或执行归档。 |
| Python ast.literal_eval读取实际Analysis-00.toc（只读） | PASS；61个easyai源文件均在固定Git快照，7个namespace无源路径占位符，无原工作区源码路径fallback。不是所有系统/第三方依赖hermetic证明。 |
| 既有worker独立只读复查 | 最终三组20PASS、v2 verify289记录PASS、tar287逐项PASS；输入源与UV目标P2均已复核关闭，本范围未发现剩余明确P1/P2。与上表重叠不累计；未同步环境、重建、启动窗口或probe。 |
| `git diff --check` / ls-remote / 原件与锁hash | PASS；原计划116185字节及原规格/README/core/ML/CV六份来源锁未改，main未改。 |

中间结果全部保留、未降低门：首轮17PASS/1FAIL为ASAR statFile需去leading slash，修后18PASS，再补固定Git tree19PASS、UV目标门20PASS。unique1真实包严格FAIL是builder把新生成文件600归一644；已明确新payload规范模式后再封存，未跳过mode检查。unique2在tsc前被pnpm **ERR_PNPM_UNSAFE_TASK_RUN_STATE_PATH**拒绝符号链接node_modules任务状态根；停止该被拒方案，保护未关闭/未重试该symlink状态。改为正常新目录frozen安装，unique3因错误空store而offline cache miss失败，按原.modules.yaml实际store修正后354包重用且零下载。unique4严格FAIL为错误假设builder会删default_app.asar，实际保留该原vendor文件，修预期而非批准新未知文件。unique5的56861fc中间包曾成功，但随后静态独审指出继承UV_PROJECT_ENVIRONMENT覆盖目标的P2；实际父变量未设且日志明确新snapshot .venv，无外部环境改变证据，补绝对目标/非link/新目录门后以新source重新构建最终包。没有用危险共享环境做复现。

额外source审计首轮把TOC中的7个namespace字符串'-'错当源文件路径而FAIL，修只读解析后61个实际源文件全在快照；两个日志均保留，不改包。独审自写tar检查首轮遗漏正常顶层目录而FAIL，修路径解析后独立287文件PASS，原产物未改。上述不被混为真实产品执行失败，也不隐藏原始FAIL。

唯一noclobber日志SHA256：
- `/tmp/easyai-input-closure-archive-20261018-final1.log` SHA256 `feeecd0a4875116949b9befa071abed002425773c6049e5a4aae99c397d22bf0`。
- `/tmp/easyai-input-closure-check-20261018-final1.log` SHA256 `5b9546205d04c670ac61ad7a8bff82dc39bae1a167cdd98bbbe8937bece75271`。
- `/tmp/easyai-input-closure-check-20261018-final2.log` SHA256 `5b9546205d04c670ac61ad7a8bff82dc39bae1a167cdd98bbbe8937bece75271`。
- `/tmp/easyai-input-closure-check-20261018-final3.log` SHA256 `5b9546205d04c670ac61ad7a8bff82dc39bae1a167cdd98bbbe8937bece75271`。
- `/tmp/easyai-input-closure-check-20261018-unique1.log` SHA256 `5b9546205d04c670ac61ad7a8bff82dc39bae1a167cdd98bbbe8937bece75271`。
- `/tmp/easyai-input-closure-package-20261018-final1.log` SHA256 `d1ea764ef52397a4417aabecdc02ffdcb8419a49f74b9b76b997c9fb328b9797`。
- `/tmp/easyai-input-closure-package-20261018-unique1.log` SHA256 `0a1da4acf4756a4cf539d201c48a86664ec139ff0e1597a2c907d245990a46b4`。
- `/tmp/easyai-input-closure-package-20261018-unique2.log` SHA256 `17146ad9f5990bf3a0a9577a4845a7b7ad8535df2657f041d71d054926e9b1a6`。
- `/tmp/easyai-input-closure-package-20261018-unique3.log` SHA256 `71f3d0b75aecd0580e219e82f88461cde6a6d3cf2e43b0ada200dffaa88252ab`。
- `/tmp/easyai-input-closure-package-20261018-unique4.log` SHA256 `927aad24ad29fb1fc58607280ce471b2170afa35f564580a6c6bc402706e076c`。
- `/tmp/easyai-input-closure-package-20261018-unique5.log` SHA256 `2e67e1358893f46d070d7f084ae853f6fcd7b0ce37d4ec23d0249806856a869a`。
- `/tmp/easyai-input-closure-sidecar-20261018-final1.log` SHA256 `598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。
- `/tmp/easyai-input-closure-source-audit-20261018-final1.log` SHA256 `2cb71f967d643d1b1cf7e88ec2f22ca42a41e73d43a47b210d1345d5b87b8967`。
- `/tmp/easyai-input-closure-source-audit-20261018-final2.log` SHA256 `9ad2726f4ad09dcb83f35095e90ef3ffe7e8ccda64dec8723b691d3866e91cd8`。
- `/tmp/easyai-input-closure-tests-20261018-final1.log` SHA256 `989493b342fff8ed4b12a17a58937879ab521aa9729b26ad1400bd389011f073`。
- `/tmp/easyai-input-closure-tests-20261018-final2.log` SHA256 `8c9869c3fcf282701b760ff22b67eb45f600cee36d3af1d0e7851de2fe5db42d`。
- `/tmp/easyai-input-closure-tests-20261018-unique1.log` SHA256 `7ee5e60bb68a4f2db7fd184d5161368ae0d1140d78023cdda93399feb41dfe4a`。
- `/tmp/easyai-input-closure-tests-20261018-unique2.log` SHA256 `56208e63386e663a9cc7d177593383c7633866eb71871defcca76a0a6c665b76`。
- `/tmp/easyai-input-closure-tests-20261018-unique3.log` SHA256 `b501f3095f80a05201fe4852b375166a40659eeefae3b170c0f8059d00d69c36`。
- `/tmp/easyai-input-closure-verify-20261018-final1.log` SHA256 `09f82e0e00a8fb2f03306b11d3f521aac2cf8c1f7afd5feb7c7853e616dd8f42`。
- `/tmp/easyai-package-inputs-review-oKDTW3.log` SHA256 `82119414703564526f899916cd4c5057d1b0c4e8b37d8ede7a09d08d48b772c0`。
- `/tmp/easyai-snapshot-input-review-I9Rkz9.log` SHA256 `4f90a26387759c1b539a6ae8930e3f4cfa7c1ca3222bd2a3fbb1f0587aa91e69`。
- `/tmp/easyai-final-venv-tests-review-98E52V.log` SHA256 `82343f988b0720edab35e77314b10b96d62018fdf43b173aca3685c4c7692980`。
- `/tmp/easyai-final-builder-verify-review-eLQvqm.log` SHA256 `6244dc12639f4679f09c6f84fcb49458a24a7b1b28be0cb6f0c6b6e7205fa44f`。
- `/tmp/easyai-final-tar-prefix-review-4HTDn1.log` SHA256 `97835e2d88f1c9108a46ec9fd61a3f02ea61b198d5e1e088ffc5a001a815ff53`。
- `/tmp/easyai-final-tar-review-EVwke5.log` SHA256 `434db534b842aeb4aebf39f3836fdf861827ca7880773d436622f97733c8e722`。

### 停止包装外围后的真实剩余条件

已把[release-checklist.md](release-checklist.md)补成M8.2/TST33最小目标条件表：需要保留原Electron sandbox的干净图形目标、明确OS/架构/可写测试目录和操作/采证渠道，客户端无开发Node/Python/本机torch；以及明确授权的隔离SSH目标/账号/可信指纹、已准备训练Python与真实数据、运行/取消/断连/恢复预算及窗口。当前云机Linux x86_64、UID1000，无DISPLAY/WAYLAND_DISPLAY/XDG_SESSION_TYPE且有开发Node/Python，不能充当该干净桌面。没有本片可用的独立图形目标/转移交互渠道或授权SSH条件，实际启动/编辑/Blockly/Monaco/原生picker/已备环境远端运行仍NOT RUN。原生sandbox已有拒绝没有重试、no-sandbox或其它绕过。

尚缺代码也明确列出，**不称只差环境**：17卡中8未支持pytorch-lightning/opencv-python/nltk/spacy/sentencepiece/transformers/gensim/hanlp的兼容依赖/许可/锁与复检闭包（OpenCV native未核不换headless，语料/模型不自动下载）；InstallPlanRequest.targetId仍literal local，无远端安装计划/owned边界、来源预算传输、远端锁/受管执行WAL/取消重连与未知停止隔离/复检回读闭环。已有远端训练与同步不等于远端安装。Windows host storage生产门、历史保留管理/未知停止显式安全解除等旧缺口仍存在。本轮仅盘点这些范围，遵循父侧本次指令停止包装外围开发；既有常规代码开发授权不受此盘点改变。

NOT RUN：真实桌面/干净目标机/TST33远端运行、Windows/macOS/系统安装签名/升级卸载、真实训练环境安装/probe/训练/数据模型下载/真实SSH、新CI端点读取、发布或部署。无新许可接受/费用/安全权限/凭据变更。没有不确定外部安装/写入；uv实际操作限新构建应用venv，训练环境和老师环境未操作。此轮pnpm目录拒绝及其安全替代已准确记录；不是自动审批reviewer拒绝，未禁用保护。既有桌面与Actions拒绝不绕过。

旧5ab tar仍SHA7445fb3e57d35393d48ebcd5f08dd52266e6c04728ab341bd0f50e5b31326b78、manifest仍345a18f63253fe67b068e0df847734abd972aa7a7a6e4e8e9c53ae5f837aa76f，完整保留。旧portable source7b91c46的manifest仍5f26ba7bb27917e717faec81c69d98ea97e3e39064ac4490b3e65fcc012fd937。原计划SHA dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43、旧规格5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190、README befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852及所有core/ML/CV来源锁均不变。CIFAR待裁决、旧226PASS/1FAIL根因UNKNOWN且raw丢失不回溯关闭。

下一步仅父侧复核本P2收口与上述验收条件/真实代码范围。源码与证据正常开发分支push后核对远端完整SHA与干净工作区；不改main、不强推、不建PR/Release、不发布不签名。M8.2/TST33/B均未被本地生成包替代。


## 2026-10-18 23:41 UTC — M6.3 Lightning 可选 DL 闭包（元数据与合成合同切片）

源码提交 **`2688906853d2d1a110d2d4cba928044fb43e2c49`**，起点HEAD/远端dev `a999c9d02ed992b8dbfb221d3e037f10197bf5c3`；origin仍 `https://github.com/T1doo/Easy-AI.git`，main仍 `5323f86232529efcfb52131168ad049f01b219f3`。起点既有包装源码/产物保留，无覆盖用户改动。本片遵循父级停止包装外围的范围，只把新增来源锁与文档纳入既有资源封装和冻结测试，不生成新electron-builder包。

### 实现与边界

依据原14.3/M6.3，pytorch-lightning固定2.6.6、CPython3.11/Linux x86_64，与现有torch2.10.0+cpu、torchvision0.25.0+cpu和核心21锁配合。新增14轮子元数据及hash锁（5909314注册表下载字节，未测解包，installedBytes=null），展开torchmetrics/lightning-utilities/PyYAML/tqdm及核心fsspec[http]的aiohttp传递闭包。单项Lightning与DL全组都是35个去重来源；混合ML/CV无重复、拒绝可选清单覆盖核心。精确版本/来源/锁hash纳入plan，复用既有来源登记、预算和固定离线hash安装器。最终复检除选定模块还要求fsspec.implementations.http；未选择DL不增加其导入，版本/import/tensor任何失败仍verified=false。

官方只读采集实际命令：`services/backend/.venv/bin/python /tmp/easyai_dl_metadata_20261018.py`；`services/backend/.venv/bin/python /tmp/easyai_dl_pin_metadata_20261018.py`。只请求pypi.org版本JSON/simple PEP691及files.pythonhosted.org的.whl.metadata（PEP658并校验索引metadata hash），随后用固定版本JSON重新核对filename/url/hash/bytes/yanked/漏洞响应；**wheel请求0，训练环境安装/真实import/ABI/probe/tensor执行0**。临时采集根`/tmp/easyai-dl-metadata-20261018/`，请求URL/字节/hash见requests.json和pinned-requests.json；已提交sources保存精确上游URL、版本JSON/metadata SHA、Requires-Dist/Python/许可声明。许可声明不是接受，legalReviewComplete/distributionReady未变。不启用其他extras/语料/模型或升级核心。

详见[install-dl-sources.md](install-dl-sources.md)。17卡当前10卡有元数据解析闭包，仍7卡未支持（OpenCV native未核与六张NLP卡）；真实安装、远端安装等原缺口不因本片消失。默认executionEnabled=false，来源登记仍不得授予执行权限。

### 实际验证

- PASS：`services/backend/.venv/bin/pytest -q services/backend/tests/test_install_dl.py`，**12 passed**。有界合成fixture强制禁止Popen与连接；覆盖元数据完整约束/extra、单项/全组去重、缺失来源与预算、离线命令捕获、核心覆盖/锁漂移、已有版本冲突、未选择不导入及5种最终检查结果。
- PASS：`services/backend/.venv/bin/pytest -q services/backend/tests/test_install_dl.py services/backend/tests/test_install_ml.py services/backend/tests/test_install_cv.py services/backend/tests/test_install_service.py services/backend/tests/test_install_runtime.py services/backend/tests/test_install_process.py services/backend/tests/test_install_source_selection.py services/backend/tests/test_install_probe_ownership.py`，**91 passed**；Starlette/anyio deprecation warning保留。
- PASS：`UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm check`（TS/Python/合同/fixtures/格式）。
- PASS：`UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache XDG_CACHE_HOME=/workspace/.cache pnpm build`；仅应用/sidecar构建，非训练环境安装。
- PASS：`node scripts/test-frozen.mjs`，临时cwd真实冻结sidecar资源逐字节/8文件constraints hash、DL单项/全组35来源/版本/禁执行计划、黄金编译及EOF退出0；没有真实训练/probe。
- PASS：`pnpm test:package`，**20 passed**；仅既有包装保护回归，无新分发产物。
- PASS：独立只读审查`/root/m0_m1_review`，12定向测试与32种选择组合核对无重复包/核心不变/单hash，未发现阻断P1/P2；审查未联网/下载/安装/执行探测。
- PASS：`git diff --check`，计划116185字节、SHA dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43；旧规格5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190、README befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852与core/ML/CV六文件hash全部保持原值。
- FAIL（已修正、记录保留）：unique1新测试创建命令在backend cwd重复了backend相对路径，创建/pytest找不到目标exit4；随后绝对目标创建。unique2为11pass/1fail，缺失来源实际按现有安全门抛FileNotFoundError，测试误期望ValueError；改为精确FileNotFoundError，unique3全通过，没有放松生产门或吞错。一次只读元数据字段打印误用license键KeyError，确认实际字段licenseExpression；一次旧包manifest检查误用package-manifest.json不存在，按既有文档实际builder-manifest.json核对，无重建/写包。

### CI、产物与待满足条件

release-checklist和remaining-critical-path已对齐父级认证邮件的同一检查点：**d2ac2bf2ba5562a85276a2a856f894a8a1cda492 / run39158015941 / 2026-10-18 19:18:44 UTC completed，check SUCCESS、desktop FAIL，各2 annotations**。失败步骤正文与根因仍未知，本片HEAD CI未知；Actions端点先前拒绝仍不重试/绕过/扩大权限，不猜根因。

旧5b3源码包tar SHA `008a7d991e49111b27b85ca932206361635026b7aadd8c67f8d566bdb6620254`、builder manifest `a9d3b42f6d7111589091a450a3cb6d8b8835c7da5c1ca54a7c974baa2c505aa1`、旧portable manifest `5f26ba7bb27917e717faec81c69d98ea97e3e39064ac4490b3e65fcc012fd937`保持不变；这些旧包不含本片DL新增资源，不能当本片分发包。

NOT RUN：真实wheel下载/训练环境安装/许可接受/实际ABI/import/tensor/probe/训练、真实SSH/图形桌面/原生picker/干净目标机、Windows/macOS原生验证、新CI读取或重跑、发布/部署/PR/Release。无未决外部安装写入；没有本片新拒绝动作。之前Electron sandbox及Actions拒绝保持，未绕过。真实纵向验收仍缺明确隔离目标、可信来源与许可/预算执行授权、已备环境/数据/指纹及测试窗口，详见release-checklist最小条件表；本片不请求扩权。

下一项：父级复核本元数据闭包后继续剩余M6.3支持卡及远端受控安装原代码缺口；真实安装/桌面/SSH需先具备明确条件。本片正常dev push并核对远端完整SHA/clean，不改main/强推。旧CIFAR裁决及226PASS/1FAIL根因UNKNOWN、raw丢失的历史记录不回溯关闭。

日志SHA256（唯一文件，失败未覆盖）：
- `/tmp/easyai-dl-build-20261018-unique1.log` SHA256 `8539a18744775e55cdb5b05a0c02f11ca9accfac31c84fbc37f1ae4232bf0315`。
- `/tmp/easyai-dl-check-20261018-unique1.log` SHA256 `9df741d13114dfa27ba3885fc8b8b0455394b0bc3c1c3597432ad57cd1f6e375`。
- `/tmp/easyai-dl-frozen-20261018-unique1.log` SHA256 `598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。
- `/tmp/easyai-dl-metadata-20261018-pinned1.log` SHA256 `f74076efce10c3af1cb01f9510c1f091612681fdd76d07431fc52b2a62b9b292`。
- `/tmp/easyai-dl-metadata-20261018-unique1.log` SHA256 `e857d7719019a5bd91b1bb179f0e3940926b3ced4e71152738b2ffa2c90eb7c6`。
- `/tmp/easyai-dl-new-20261018-unique1.log` SHA256 `e6183a8e812d0793423b42ef1c4be1686e71b5e89c597623ff9f13c9ce0c7d4c`。
- `/tmp/easyai-dl-new-20261018-unique2.log` SHA256 `b4684564bffb1ab8300fafbdc7956c0b9cb9f948ce595816c0e9fdf82de866df`。
- `/tmp/easyai-dl-new-20261018-unique3.log` SHA256 `0c6588152ada0022a8322b793a7abd224cd2741941040f48c5d593d12938d0e6`。
- `/tmp/easyai-dl-package-tests-20261018-unique1.log` SHA256 `060fe3cf1f1f910489fb9a3ffe177822639b146e932d255107e6035c7f2a24f3`。
- `/tmp/easyai-dl-regression-20261018-unique1.log` SHA256 `cba03d6e3e5713b3dae703c04de8cde3f3b0f5c6f46ac3aa429f6d184bdc2252`。
- `/tmp/easyai-dl-review-heEt45.log` SHA256 `3afefb101be7acd5b37312522beae453bf030d360c6ba6e5daea458da7638d0b`。
- `/tmp/easyai-dl-metadata-20261018/requests.json` SHA256 `22e9fdbe896516187174315b5ae102059c111bd8f923e85b50e3cc05aa520ed9`。
- `/tmp/easyai-dl-metadata-20261018/pinned-requests.json` SHA256 `604f4d8fecb0981c8fa6e206591fd7559d6de6d257f7c4e3b49d9adc38eab14c`。
- `packages/training-profiles/easyai-dl-sources.json` SHA256 `3440d2f85a804f7dbf61b160ce932dd462b23c09cc0754275fd14c3b815ab0a7`。
- `packages/training-profiles/easyai-dl-linux-cp311.lock` SHA256 `3d541537ad5d6628503bfa78c6c8ab8eb078fa1f88b2fcc8612f4dbff43e378c`。


## 2026-10-19 00:22 UTC — M6.3 远端 owned 安装产品纵切（代码/受控协议）

源码 **`ba395c7cfe38ce023f67e64bd50cffbc50d3442f`**；起点/此前远端dev **`1ee530735bc91a77029e04dd32ea6030651969e0`**。origin仍T1doo/Easy-AI，main仍`5323f86232529efcfb52131168ad049f01b219f3`。先全文核原14节与现有SSH/InstallJob/owner/锁；设计冻结[remote-install-design.md](remote-install-design.md)后，单一集成者，既有m2_emit只实现固定stdlib helper/其测试，m0_m1_review独立只读审查，未另建并行writer。

### 产品闭环与安全边界

复用同一InstallService的计划/确认、唯一worker、WAL、lease、取消、最终精确版本/import/tensor及历史；InstallRegistry只路由目标适配，conda bootstrap/pip/probe源码生成器与本机共用，不是另建解析/安装框架。Main→API只引用保存targetId/当前projectId/connectionId，后端按targetRevision、endpoint、可信fingerprint、username和项目重验。私有operator配置提供固定root与已备来源，prefix只能root/training-environments/后端UUID。teacher-existing只读，根外、非owned或旧部分环境拒绝；新环境独占分配不覆盖。

远端snapshot只读实际uid/root/prefix inode、来源hash/字节/module tree、METADATA基线及statvfs可用容量，绑定计划来源/基线/constraints/身份/预算，缺失/冲突/容量不够拒绝。只用已在目标的批准离线来源，不上传/下载包或数据；installedBytes未知保持null。临时helper+ManagedProcess/PortableJournal无需在远端安装Easy-AI/FastAPI。helper启动用-I/-S/-B，固定离线conda/pip及真实probe源码只在未来独立获准的owned目标内执行。

私有恢复策略先fsync，再记INSTALL_REMOTE_RESERVING WAL，之后才发reserve；reserve ACK未知也保留实际本机lease和CANCEL_REQUESTED。远端flock/持久claim与phase intent/index/last-phase/last-writer先于spawn；相同phase只inspect不重发start。SDK close未知保留实际channel+共享I/O gate，adapter操作锁覆盖整个cleanup回收。未知owner保持隔离，不按PID杀、不删除旧锁/部分目录、不以channel关闭当停止。

重新认证同一保存目标后，只inspect/cancel/release，不继续剩余安装。恢复从同job私有快照定位原claim，即使operator策略删除或授权过期，也不把快照变成新执行权（强制false且policy_guard禁止新操作）。quiet phase不是安装成功，收口失败/取消仍needsReprobe=true；已收口终态幂等保持。last-writer阻止失败续装继承旧ready；新建与已有owned都须本轮最终真实复检和静止收口后标ready。目标概要任何编辑含alias会改变revision，未收口安装按原active-conflict门阻止编辑，复用有界只读账本而不反向取得registry锁。UI已接目标/根/来源/容量/确认、已有owned ID、任务取消、历史打开与远端停止核验状态。

这不是只放开targetId或计划展示。实际命令链及默认关闭门已接；详细最低条件、持久状态和边界见[remote-install.md](remote-install.md)。**本轮无真实SSH/安装/ABI通过声明。**

### 实际命令与证据

- PASS：`UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm check`，最终final2：TS、Python Ruff/mypy（66源文件）、Pydantic生成schema/TS漂移、真实Blockly fixtures与格式均通过。
- PASS：`services/backend/.venv/bin/pytest -q services/backend/tests/test_remote_install.py services/backend/tests/test_remote_install_protocol.py services/backend/tests/test_remote_install_owner.py services/backend/tests/test_install_transport.py services/backend/tests/test_install_service.py services/backend/tests/test_install_runtime.py services/backend/tests/test_install_process.py services/backend/tests/test_install_probe_ownership.py services/backend/tests/test_install_history.py services/backend/tests/test_install_source_selection.py`，源码提交后final2 **113 passed**；Starlette/anyio既有deprecation warning保留。这是共享安装生命周期的定向回归，非扩大平台矩阵或完成百分比。
- PASS：`services/backend/.venv/bin/pytest -q services/backend/tests/test_remote_install.py services/backend/tests/test_connection_profiles.py`，新增概要编辑门 **19 passed**，不与上述重叠项累加。独审该门 **1 passed / 5 deselected**，无新增阻断。
- PASS：`pnpm exec vitest run apps/desktop/src/PackageManager.test.mts apps/desktop/electron/install-history-workflow.test.mts apps/desktop/electron/install-source-workflow.test.mts`，**25 passed**。保持原teacher只读、明确确认、幂等与来源门，新增远端目标绑定/来源本机登记禁用验证。
- PASS：`UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache XDG_CACHE_HOME=/workspace/.cache pnpm build`，最终final2；仅应用/冻结sidecar构建，非训练环境安装。
- PASS：`node scripts/test-frozen.mjs`，源码SHA提交后final2：包括新增helper资源原文、现有来源锁、默认禁执行计划、认证黄金编译及临时cwd EOF退出0。
- PASS：`pnpm test:package` **20 passed**，仅既有保护回归；没有生成新electron-builder包或扩展包装外围。
- PASS：独审最终远端4文件 **38 passed /1.95s**，无新明确P1/P2；只用合成协议/标准库子进程，不联网/SSH/安装。真实helper↔client互操作在新建4阶段与已有owned续装2阶段实际走dispatch、文件hash/容量、claim/flock、ManagedProcess和退出proof；**fixture明确把bootstrap/pip/probe argv替换为stdlib打印合成报告，绝不执行依赖命令或据此宣称真实tensor/ABI**。
- PASS：`git diff --check`；原plan116185字节/SHA dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43、旧规格5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190、README befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852及core/ML/CV/DL八个来源/锁hash均未改变。

独审与互操作发现的回执job/plan/nonce不统一、stdin无__file__、SDK cleanup过早放gate、cleanup并发释放别人的gate、reconcile改坏成功历史、新建未allocate/未owned阶段verify、旧ready继承等问题均已修并保留复现/回归。另以WAL+私有恢复策略和reservation未知lease封闭了预留ACK窗口；没有伪造source容量/停止proof或降低现有测试。

中间FAIL真实保留：首次Ruff未用backend100列配置/未用函数定义或unused import、mypy Any返回/TypedDict动态key等已修；旧local runtime monkeypatch引用被提前import捕获导致2回归失败，恢复构造时导入后通过；UI新增目标select使旧测试误选首select，改为精确环境方案aria-label而未改teacher只读生产门；本机/远端文案保留各自语义。互操作初次fixture strict datetime、wheel五字段协议不匹配修正（生产target按五字段投影，未放宽helper）；fake channel在stdin未发完时即EOF的错误fixture已修。后续测试引号收集错误及取消恢复对未owned新建partial误要求marker的问题已修；release仍只在静止proof与claim/inode匹配时收口，existing真正run/serve仍严格owned。各失败日志见下，不覆盖、不合并成虚假首轮全绿。

### 执行器中断与保全

一次工具连接故障发生于阶段verify补丁读取：`exec-server transport closed/disconnected; failed to resume exec-server session: recovery timed out after 25s`。不是安全审批拒绝。当时patch结果未知，暂停写入；有界只读pwd恢复成功后，核原/workspace/Easy-AI、HEAD1ee530、全部WIP与已有进程，未停止未知python或删除锁。备份 `/tmp/easyai-remote-install-recovery-20261019-0001` 保存tracked.patch、untracked源码与日志，共23文件及preserved-files.json。只读确认阶段补丁未写入后仅执行一次修复；未换环境/创建并行writer。后续检查/构建/测试均已实际恢复完成，无待确认的外部安装写入。

### 仍未完成 / 下一项

NOT RUN：真实SSH连接/安装包或数据上传、wheel/语料/模型下载、训练环境安装、许可接受、真实import/ABI/tensor/训练、真实远端网络/重启故障验收、图形桌面/native picker/干净目标机、Windows/macOS原生矩阵、新CI读取/重跑、发布/部署/签名/Release/PR。执行默认关闭；最低条件须以后明确隔离目标/已准备来源与可信launcher、许可/预算/窗口及认证指纹后才可提供。没有新凭据/权限/收费；教师/共享环境未操作。既有Electron sandbox及Actions拒绝未重试/绕过。

现有CI仍只知父级认证邮件的d2ac2bf2ba5562a85276a2a856f894a8a1cda492/run39158015941，2026-10-18 19:18:44 UTC completed，check SUCCESS、desktop FAIL各2 annotations；失败正文/根因与本轮HEAD CI未知。旧5b3 builder tar仍008a7d991e49111b27b85ca932206361635026b7aadd8c67f8d566bdb6620254、builder manifest仍a9d3b42f6d7111589091a450a3cb6d8b8835c7da5c1ca54a7c974baa2c505aa1，旧portable仍5f26ba7bb27917e717faec81c69d98ea97e3e39064ac4490b3e65fcc012fd937；这些旧包不包含本片远端能力，不当本片新分发包。

17卡仍10卡元数据闭包/7卡未支持（OpenCV native及NLP六卡）；CIFAR裁决、Windows、任务保留管理/未知停止显式安全解除、正式数据训练和完整课堂/干净平台包等仍有实际代码或证据缺口，不能称全部只差环境。旧226PASS/1FAIL raw丢失根因UNKNOWN不回溯关闭。下一项由父级复核本受控纵切后接原M6.3剩余支持卡/原计划缺口；真实正向远端安装另须具体授权窗口。

本片只正常开发分支提交推送，最终证据SHA与远端/clean核对见最终回报；main/远端原仓库无写入、不强推、不建PR/Release。M6.3完整真实验收与B未被本片合成链替代。

唯一日志/恢复清单SHA256（失败保留）：
- `/tmp/easyai-profile-install-guard-review-kuXJFZ.log` SHA256 `81f6ed9823d6162a07b0ba94685dc50f5a10fda8f7637539e82e13a45ddcd3c6`。
- `/tmp/easyai-remote-install-build-20261019-final1.log` SHA256 `edb04f69f5cef5b63ffad8123813214b6667ae8d174267721b3c4b0478872e99`。
- `/tmp/easyai-remote-install-build-20261019-final2.log` SHA256 `fbc00805a4140227c04ef741940ffea46ebeaac3fcc4ee37823f52425e501694`。
- `/tmp/easyai-remote-install-build-20261019-unique1.log` SHA256 `b4b0014ec7012b6d9ad795b6d734054feb78b3e84a27c53bb76bf464fbf19a26`。
- `/tmp/easyai-remote-install-check-20261018-unique1.log` SHA256 `83c25934436cd4f444b0c9e72609c6e0dcf71733f83c63bedf79e5bf89ead8b7`。
- `/tmp/easyai-remote-install-check-20261018-unique2.log` SHA256 `9fde7b3055ae6b3db19e09a3cdf1565b00326cb22b35f2d8a61c873c491e7539`。
- `/tmp/easyai-remote-install-check-20261018-unique3.log` SHA256 `4e832bf48d41d8adc11372a05cdc9d4bbe481b7839dfc6b92e1cf0d955123d22`。
- `/tmp/easyai-remote-install-check-20261018-unique4.log` SHA256 `8f3379feed518898dd1f9c4374481fb4fce70855bbe1a78a7b093eca35215a1c`。
- `/tmp/easyai-remote-install-check-20261019-final1.log` SHA256 `c42bd4df1916148541e1f0f0341c6c525fc308786650e029608cdf52c46e75fc`。
- `/tmp/easyai-remote-install-check-20261019-final2.log` SHA256 `c42bd4df1916148541e1f0f0341c6c525fc308786650e029608cdf52c46e75fc`。
- `/tmp/easyai-remote-install-check-20261019-unique1.log` SHA256 `351964c23fd230bcdd8dfd57149a249f137650baefed17f380e06dd594aedbfc`。
- `/tmp/easyai-remote-install-check-20261019-unique2.log` SHA256 `6865b6771518732005ad23b3a0357826242db0ad3348b453eb693655d8a6b406`。
- `/tmp/easyai-remote-install-check-20261019-unique3.log` SHA256 `c42bd4df1916148541e1f0f0341c6c525fc308786650e029608cdf52c46e75fc`。
- `/tmp/easyai-remote-install-final-review-39yTZJ.log` SHA256 `d82e72a44198f03799fb3e0d3fa65f76a877c023fe47c63d07e85562dbc4981a`。
- `/tmp/easyai-remote-install-frozen-20261019-final1.log` SHA256 `598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。
- `/tmp/easyai-remote-install-frozen-20261019-final2.log` SHA256 `598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。
- `/tmp/easyai-remote-install-integration-20261018-unique1.log` SHA256 `31aea369e724e06e40899f30e41b4d08322eb801791b7267f074241d775f0735`。
- `/tmp/easyai-remote-install-integration-20261018-unique2.log` SHA256 `a63aa347137643b6ccc9ff195062a6e15c194133bf2b9922959a5a43d8e06217`。
- `/tmp/easyai-remote-install-integration-20261018-unique3.log` SHA256 `a7210b0bf1f2d9500a0118669d52bed826809cb9c97ddcfc6b16c350f1699b77`。
- `/tmp/easyai-remote-install-mypy-20261018-unique1.log` SHA256 `a9a8ac01048fb79eaa5eba94d31ddd87f7f69be21a284fcf9045d215bc53f0d8`。
- `/tmp/easyai-remote-install-mypy-20261019-unique1.log` SHA256 `e01191578d3a3bac202cef72aec747f3048def999e4a0906368a5b91b8849682`。
- `/tmp/easyai-remote-install-package-tests-20261019-final1.log` SHA256 `0e5c30dba5f2066b214258cc38f9c812f391dc62eb3e0bce395ab508d1053a04`。
- `/tmp/easyai-remote-install-profile-guard-20261019-final1.log` SHA256 `0943f5eb45c231d9ba23b595b26c207bb3d996bc857663200ae7d761ae3f613a`。
- `/tmp/easyai-remote-install-protocol-20261019-unique1.log` SHA256 `e6e710dffd84bddeec51eb01cdcb9daa77fa48ede0c0633275b0700b0002cb97`。
- `/tmp/easyai-remote-install-protocol-20261019-unique2.log` SHA256 `b3ee9ab94a43604bad195397c0c55d3bcb2647c8dc28657045063e57cd78c221`。
- `/tmp/easyai-remote-install-protocol-20261019-unique3.log` SHA256 `b336bfbb42d8a55315e2f7350d4a6528e0fd95453f81c1e21f96f9ae7c5d2932`。
- `/tmp/easyai-remote-install-regression-20261018-unique1.log` SHA256 `1ba6eaf38459f9eda132315d9d7da652faf88e113a25d5b5cfc2c25a167a1ee1`。
- `/tmp/easyai-remote-install-regression-20261019-final1.log` SHA256 `c9ab1245b8b8f407ff9cda6909920636405fb9d02b14e663b91bad890c07a284`。
- `/tmp/easyai-remote-install-regression-20261019-final2.log` SHA256 `b1fb05cc00ff11eaf4759f2ef5fba79293d96f64b1cf56a8c3692ed4faa6e8ab`。
- `/tmp/easyai-remote-install-regression-20261019-unique1.log` SHA256 `23e5124ae3493e1f51d57774f2e328139bdde911326a68e8718287a999eddd3c`。
- `/tmp/easyai-remote-install-review-AweUt1.log` SHA256 `ffcbb10fd620312ebbe610b07ec434d165efbc0422917a94152843a371f3bc56`。
- `/tmp/easyai-remote-install-targeted-20261019-unique1.log` SHA256 `4017c3c13f672e5daee6714727151ea5564147ce4872cf2104ce55b5fa4c9330`。
- `/tmp/easyai-remote-install-targeted-20261019-unique2.log` SHA256 `7da8c91faead82643e98200be866d54475dcd4d1a1f2c46fa0404ed715fdaf55`。
- `/tmp/easyai-remote-install-targeted-20261019-unique3.log` SHA256 `865b1b882aaee701eed31233e2b639a7faf7989b649618837d0e222405868ac8`。
- `/tmp/easyai-remote-install-targeted-20261019-unique4.log` SHA256 `c90968dd4b677914f6cd1dc48d510d3050263cad4251e699beea0d71c5df3de7`。
- `/tmp/easyai-remote-install-ui-20261018-unique1.log` SHA256 `f4aeecd89b2d3a7297c726126b9f37ab9607c7160f65d33f18ea1196def44b5a`。
- `/tmp/easyai-remote-install-ui-20261018-unique2.log` SHA256 `21860a6d3ba2165c2886fb7159ac8fa9459a2e8154c84b186a041be34def57b2`。
- `/tmp/easyai-remote-install-ui-20261019-final1.log` SHA256 `e6cef87ec0c9d888e03ebb002a3fa50226a60f5b4b7a6503854b7492490bba79`。
- `/tmp/easyai-remote-install-ui-20261019-unique1.log` SHA256 `e4f11f44db66c3a8a749bf05ba5c186535ef92d77167696cca8ce2c9f2d4ac22`。
- `/tmp/easyai-remote-install-wal-20261019-unique1.log` SHA256 `58e99ac9b1f322176945f5e93f4030ebb22f5ecf25bf579e8e866a44af7d531b`。
- `/tmp/easyai-remote-install-recovery-20261019-0001/preserved-files.json` SHA256 `6988123dac38d834f61f92da99732ea342dcf5661dceaa7c956d86e97cb18be7`。


## 2026-10-19：远端 owned 安装三项 P2 修复（代码与合成验证）

本节更正上一片的收口状态：父级复核发现三个具体 P2，故 `ba395c7cfe38ce023f67e64bd50cffbc50d3442f` / 证据 `3616826e28cef2d2ce4fd874f1bb81a6fcf17d94` 尚未签收；此前独审未发现问题不等于这三项不存在。原 FAIL 与历史记录保留。本轮源码完整 SHA：`b691f141fc4a8e3071cbcf82dd4c4903eb9ccd85`，基于上述证据提交；没有重做计划或改变 D01–D14。

### 修复与确定性证据

1. writer 交接：父 RPC 在仍持有 writer flock 时用 pass_fds 传递同一 open-file description；子 owner 验证 FD 权限及锁文件 inode，父子只关闭各自 FD，不 LOCK_UN、不重新竞争、不重试未知启动。RED1 用真实标准库子 helper 的退出 barrier 强制子先执行且父仍持锁，旧实现稳定 INSTALL_WRITER_BUSY/unknown；修复后实际子退出码0、完成事件与静止收据通过，相同 phase 仍只启动一次。另核错 inode 拒绝及子 FD close 不解父锁。
2. 已落盘取消：serve 在实际 ManagedProcess.start 前核对同 job/plan/phase 的取消。独占 serve claim + writer 所有权下未派发才记 dispatched=false、cancelled、quiescent=true、events=[]；不虚构进程退出。RED2 的哨兵证明旧代码实际启动了本不应运行的标准库子命令；修复后哨兵不存在。运行中取消先于 done 判断，未知停止仍隔离。
3. cleanup 生命周期：认证 lease 按 launcher 保存实际 InstallSshTransport，Registry 重建 target 不丢原 SDK cleanup owner。重取 adapter、切换 launcher 与 retiring 都可非阻塞 reap；必须 cleanup thread done 且真实 channel.closed 才释放本 owner 的 I/O gate。RED4 经过真实 Registry→ConnectionManager→transport、合成 SDK 延迟 close，旧实现下一次 reconcile 稳定 INSTALL_REMOTE_BUSY；修复后自动核验取消并 needsReprobe。原操作并发回归及终态 reconcile 回归保留，另核 retiring 自动 reap 不释放其他操作持有的 gate。

### 实际验证命令与结果

所有命令在 `/workspace/Easy-AI` 执行，输出经 `set -o noclobber` 保留到唯一日志；未删除/覆盖失败日志。

- FAIL（修前预期复现）：`services/backend/.venv/bin/pytest -q services/backend/tests/test_remote_install_owner.py -k detached_child_finishes`，RED1 1 failed；`... -k persisted_cancel_before_serve`，RED2 1 failed。准确命令选择同名测试；均为标准库合成子进程。
- FAIL（fixture 错误）：RED3 首次 Registry 测试缺少 threading 导入而 NameError；补导入后 RED4 才证明真实 P2，不把 RED3 当 P2 证据。RED4 实际命令：`services/backend/.venv/bin/pytest -q services/backend/tests/test_remote_install.py -k reuses_session_cleanup`，1 failed/6 deselected。
- PASS：`services/backend/.venv/bin/pytest -q services/backend/tests/test_remote_install_owner.py services/backend/tests/test_install_transport.py services/backend/tests/test_remote_install.py`，首轮 40 passed。
- PASS：`services/backend/.venv/bin/pytest -q services/backend/tests/test_remote_install_owner.py services/backend/tests/test_install_transport.py services/backend/tests/test_remote_install.py services/backend/tests/test_remote_install_protocol.py services/backend/tests/test_connection_manager.py services/backend/tests/test_install_service.py services/backend/tests/test_install_process.py services/backend/tests/test_install_runtime.py services/backend/tests/test_install_history.py services/backend/tests/test_install_source_selection.py services/backend/tests/test_install_ml.py services/backend/tests/test_install_cv.py services/backend/tests/test_install_dl.py services/backend/tests/test_install_probe_ownership.py`，164 passed /15.32s，1 条已有 Starlette anyio alias 弃用 warning。
- PASS：`UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm check`；包含 Ruff、100列格式、严格 mypy 66源文件、TS/合同/真实 Blockly fixtures 一致性及 Prettier。
- PASS：`UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache XDG_CACHE_HOME=/workspace/.cache pnpm build`，冻结 sidecar 重建；`node scripts/test-frozen.mjs`，更新 helper 资源原文、默认禁执行计划、认证黄金编译/临时 cwd、EOF exit0 通过。helper SHA256 `65dc8805cdfb3285f558c15a07ffa62304543f1b8dae964d441eed85040657cd`。没有生成新 electron-builder 包。
- PASS：独立只读 reviewer 相关四文件 41 passed /2.42s，加 FD/retiring 三项 3 passed /33 deselected；未发现明确阻断 P1/P2。仅本地合成 SDK/标准库子进程，没有依赖命令、SSH 或源码代改。
- PASS：`git diff --check`；plan 仍116185字节、SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；README、原规格及 core/ML/CV/DL 八个来源/锁 SHA 均与上一片相同。

### 工作区、远端与未完成门

开始 checkout 为 `codex/demo-v0.0.0`、HEAD `3616826e28cef2d2ce4fd874f1bb81a6fcf17d94`，仅已有两份新增 P2 测试 WIP，均保留并纳入修复。origin 为 `https://github.com/T1doo/Easy-AI.git`；只读 ls-remote 确认开发分支同 HEAD、main 仍 `5323f86232529efcfb52131168ad049f01b219f3`。本地不存在 origin/codex/demo-v0.0.0 追踪 ref，未把它误报为远端差异；随后以 ls-remote 直接核准。源码提交后工作区 clean、远端仍旧证据 SHA；本证据提交后正常推送开发分支并再核最终完整 SHA/clean/main，结果见最终回报。

NOT RUN：真实 SSH/安装/wheel 下载/数据上传、真实 import/ABI/tensor/训练、桌面/native picker/干净目标机、Windows/macOS、新 CI 查询或重跑、发布/Release/PR。默认执行门保持关闭，无新凭据/权限/付费、无教师共享环境写入。此前 Actions/Electron sandbox 拒绝没有重试或绕过。当前 HEAD 的云 CI 结果仍 UNKNOWN，不以本地通过宣称云 CI 通过。既有 7 卡未支持、CIFAR 裁决、Windows、未知停止安全解除等原计划缺口仍在，B 验收未完成。下一项：父级复核本三项 P2 后接原 M6.3 剩余代码与验收；真实远端正向门须先明确隔离目标、已准备来源、可信 launcher、许可/预算/窗口与认证指纹。

本轮日志 SHA256（包括失败与 fixture 错误）：
- `/tmp/easyai-owner-handoff-20261019-build1.log` SHA256 `e1fd233b3973f2a4e864b04aeb3c63a412486d30637b27c491b4fc765eb9f6a0`。
- `/tmp/easyai-owner-handoff-20261019-check1.log` SHA256 `c42bd4df1916148541e1f0f0341c6c525fc308786650e029608cdf52c46e75fc`。
- `/tmp/easyai-owner-handoff-20261019-diff1.log` SHA256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。
- `/tmp/easyai-owner-handoff-20261019-frozen1.log` SHA256 `598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。
- `/tmp/easyai-owner-handoff-20261019-green1.log` SHA256 `5b6198b1c0cee4ad2ac9c8f7ff1eee4e39365d5a3f14386031c0924f13c182c8`。
- `/tmp/easyai-owner-handoff-20261019-red1.log` SHA256 `914a1cdbf693c0dccdb7ee50f34235e26358d979ca8acb699e77f342867aad2b`。
- `/tmp/easyai-owner-handoff-20261019-red2.log` SHA256 `d800d670128996f52b26605da70a7d77b27e1a5b2c62f3e5452b4cf5f3725ba4`。
- `/tmp/easyai-owner-handoff-20261019-red3.log` SHA256 `308d4dc55c71d2a2be12c3f26f61ae360ae3b4a2487b3c9a20831833ba628f15`。
- `/tmp/easyai-owner-handoff-20261019-red4.log` SHA256 `542b30f5f582eae73a3e350cbcb430c554d5e5bd4b151f7c971c738af95051d7`。
- `/tmp/easyai-owner-handoff-20261019-regression1.log` SHA256 `0715a852add139b656c0a414a426c3873adb7e9b0b47c1537e78673b8142b052`。
- `/tmp/easyai-owner-handoff-review-CWLKO1.log` SHA256 `2972e2d48c593979cda048564306c1717f86a90219cdcc7529f2bf8057853e73`。
- `/tmp/easyai-owner-fd-extra-review-5nYOUb.log` SHA256 `f3e61ab22787d76858807cfaf77577f577d38e9833bf7d3bd189df5efcd5c00d`。


## 2026-10-19：终态原子发布 P2、同 phase 收口与最新 CI 双失败

父侧已只读签收前三项 P2（源码 b691f141fc4a8e3071cbcf82dd4c4903eb9ccd85）；本轮按新增指示修独立的 status.json 并发发布 P2，并覆盖完整收据已可见、serve 尚持 writer 锁的正常收口窗口。基线 HEAD/远端开发分支均 `e454f97044f84f20347b10f3807220727f2dac1f`，工作区开始 clean；本轮源码完整 SHA `ac0e0a460c39da7a575e378605d0811a75986498`。单一 writer，无真实 SSH/安装或新 CI 日志请求。

### 行为与确定性证据

- 原 status 经 O_EXCL 创建最终名字后再写入；RED1 在 open 返回写入前用 Event 屏障暂停 serve，并发 inspect 稳定 JSONDecodeError。失败日志保留，未用 sleep 猜概率。
- 现两个 status 发布路径（预取消未派发、实际子进程收口）共用 publish_status：同目录随机私有临时文件完整写入、flush/fsync，Linux libc renameat2(RENAME_NOREPLACE) 一次原子发布，再 fsync 父目录。不覆盖已有未知/损坏收据或符号链接，没有普通 rename 覆盖 fallback。不支持该能力则 fail closed；仅移除本次随机临时名字。原 owner/private/nlink/stamp 读取约束未放宽。helper SHA256 `e0d242c72a3a5f64c641cad17a6a0f84cca066b9b8afcf13638072e42ede3b13`。
- 两个确定性屏障覆盖文件尚空、512 KiB 合成收据已 flush 但尚未 fsync。publish 前 inspect 均 unknown/non-quiescent，不暴露空/部分 JSON 或过早终态；发布后才得到完整收据。另保留先前真实标准库子命令的退出、取消与同 phase 不重复启动回归；合成大事件不当真实训练指标。
- 收据已完整可见但 serve 尚持 writer FD 时，verify/release 仅在同 job/plan/phase 已有静止收据条件下最多等2秒获取原 flock，每次等待及实际获锁后重验 claim、last-phase、intent；通过实际 flock 后才操作。Event 屏障强制正常窗口，两个动作均有界等待后成功。另强制最后一次验证后/获锁前意图变化，必须 INSTALL_PHASE_MISMATCH，不进入受保护操作。unknown phase 不启用等待，不生成静止或 release 证据；超时仍拒绝，不重新执行、不删锁。

### 实际命令与结果

在 `/workspace/Easy-AI`，所有日志使用唯一名称、noclobber 保留：

- FAIL（修前真实复现）：`services/backend/.venv/bin/pytest -q services/backend/tests/test_remote_install_owner.py -k inspect_during_status_creation`，1 failed /32 deselected，JSONDecodeError；RED1。
- PASS：`services/backend/.venv/bin/pytest -q services/backend/tests/test_remote_install_owner.py services/backend/tests/test_remote_install_protocol.py services/backend/tests/test_install_transport.py services/backend/tests/test_remote_install.py`，最终 **53 passed /2.66s**；finaltests2。范围包括新发布/等待门及原远端 helper/client/transport 回归，没有扩展真实平台矩阵。
- PASS：`UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm check`；后续最终 runtime/test 新增通过 `services/backend/.venv/bin/ruff check --config services/backend/pyproject.toml runtime/install_owner.py services/backend/tests/test_remote_install_owner.py`（finalruff2）与相同配置格式化。后端合同/TS/锁文件未改。
- PASS：`UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache XDG_CACHE_HOME=/workspace/.cache pnpm build`（build1）；最终 source 后端以 `UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache XDG_CACHE_HOME=/workspace/.cache node scripts/python-task.mjs build`（build3）重建；`node scripts/test-frozen.mjs`（frozen3）核资源原文、默认禁执行登记/取消、认证黄金编译/临时 cwd、EOF exit0 通过。
- FAIL（中间保留）：frozen1 检出构建期间更新 helper 文件头说明导致资源原文不一致；不是安装/ABI 错误。build2 后 frozen2 曾通过；随后新增成功获锁后意图重验，故又以 build3/frozen3 验最终 source，没有把旧构建冒充最终构建。未生成新 electron-builder 包。
- PASS：独立只读审查，第一次专项6 passed /30 deselected；最终加强后6 passed /35 deselected。确认原子不覆盖/unsupported failclosed、等待重验及 unknown 保留，无明确阻断 P1/P2。两次均本地合成、未代改源码/执行 SSH/安装/Actions。
- PASS：`git diff --check`，原 plan 仍116185字节、SHA256 dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43；README/原规格/core、ML、CV、DL八个来源锁 hash 仍与上一节相同。

### 最新 CI 实证与独立只读初核

父侧提供：`e454f97044f84f20347b10f3807220727f2dac1f` / [run39181255841](https://github.com/T1doo/Easy-AI/actions/runs/39181255841)，2026-10-19 **00:34:06 UTC**，check 和 desktop 均在 `pnpm install --frozen-lockfile` 失败；前 `3616826e28cef2d2ce4fd874f1bb81a6fcf17d94` / [run39180535293](https://github.com/T1doo/Easy-AI/actions/runs/39180535293)，**00:24:34 UTC**，也同安装步骤双失败。d2ac2bf/check SUCCESS、desktop FAIL 已是历史；release-checklist 与 remaining-critical-path 已更正，不能仍称最新只有 desktop 红。

只读源码/本地已有日志核对（`node --input-type=module` 的逐 importer specifier 审计、cat/rg/git diff、pnpm --version/node --version）：工作流、root packageManager/engines 和本地元数据均 Node24.19.0、pnpm11.25.0；root/desktop 共16项直接依赖 specifier 与源 lock importer 相同，源 lockfileVersion9.0、本地 installed lock 与源 lock 同 SHA256 `886aa7c3d4943909de165f313ac3eaae1260e0b4cd2849995cd960ddc40e046c`。两失败 SHA 之间 package.json、desktop manifest、lock、workspace、.npmrc、workflow 无差异，本轮也未改这些输入。工作流是 ubuntu-latest/windows-latest clean runner，本地是 warm Linux workspace；本地 pnpm fallback wrapper 另设 pnpm_config_pm_on_fail=ignore，CI workflow 未声明该变量。仅记录差异，不推测其为根因。既有本地日志 ERR_PNPM_NO_OFFLINE_TARBALL 属于另一次离线 builder 输入检查，不冒充 CI 错误正文。

**准确 CI 安装错误正文/根因仍 UNKNOWN。** 对上述 Actions run 获取安装错误日志这一动作受既有访问拒绝约束，本轮未重试接口、换路、扩大权限、联网安装或盲重跑；不是一个待确认已经发出的新请求。若要进一步修 CI，需要父侧提供这两次准确安装错误正文；不凭步骤名假修 lock mismatch。当前 source/最终证据 SHA 的 CI 结果尚未知，本地 check/build PASS 不替代云 CI。

### 工作区、远端与下一项

源提交后工作区 clean；只读 ls-remote 显示远端开发分支仍基线 e454f97044f84f20347b10f3807220727f2dac1f，main 仍 `5323f86232529efcfb52131168ad049f01b219f3`。本证据提交后仅正常 push 到 origin 的 codex/demo-v0.0.0，再核最终完整 SHA/clean/main，最终回报为准。未写 main/Feng 原仓库、无强推、PR、Release 或部署。

NOT RUN：真实 SSH/安装/下载/数据上传、训练环境 import/ABI/tensor/正式训练、真实桌面/原生 picker/干净目标机、Windows/macOS 实机、CI 日志读取或主动重跑。无新增凭据/权限/付费。默认执行门与此前 Actions/Electron sandbox 拒绝保持；7卡/CIFAR/Windows等原缺口仍在，B 未完成。下一项：父侧复核本发布及收口 P2，再继续原 M6.3；CI 修复待准确错误正文。真实正向远端门仍须隔离目标、可信 launcher/预备来源、许可/预算/窗口与认证指纹的具体授权。

本轮日志 SHA256（中间 FAIL 原样保留）：
- `/tmp/easyai-status-publication-20261019-build1.log` SHA256 `02ac2115186317df05cf42ffcb77dacd9c1cb8dd8d6ad634794d8bdc1be97c5f`。
- `/tmp/easyai-status-publication-20261019-build2.log` SHA256 `f918eac67b19120a0996506146d4551659b36ab6dcf3f42bf43f926d3de5d3e1`。
- `/tmp/easyai-status-publication-20261019-build3.log` SHA256 `77dce3242f69a26ea7bf9b783f307c0b2d69280f2d3b221690ff764e81d0a8e3`。
- `/tmp/easyai-status-publication-20261019-check1.log` SHA256 `c42bd4df1916148541e1f0f0341c6c525fc308786650e029608cdf52c46e75fc`。
- `/tmp/easyai-status-publication-20261019-ci-source-audit1.log` SHA256 `e4d093d73d8daa39ee22646921a95c48901a6e51c1fe7fa8b5c1d819add1505f`。
- `/tmp/easyai-status-publication-20261019-finalruff1.log` SHA256 `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`。
- `/tmp/easyai-status-publication-20261019-finalruff2.log` SHA256 `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`。
- `/tmp/easyai-status-publication-20261019-finaltests1.log` SHA256 `ccd7b535d71b867ae0a5ae3b584ec8c7ca8811d4c8e0c0e63516893dcd3eeeca`。
- `/tmp/easyai-status-publication-20261019-finaltests2.log` SHA256 `1a7ad76ccce124e5512311191543964683987ec553691baa16659c907c39fd86`。
- `/tmp/easyai-status-publication-20261019-frozen1.log` SHA256 `499b57ad292aaae9305fdb0b52339e50fcdd8d3735ca879df489b2e38baca0f0`。
- `/tmp/easyai-status-publication-20261019-frozen2.log` SHA256 `598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。
- `/tmp/easyai-status-publication-20261019-frozen3.log` SHA256 `598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。
- `/tmp/easyai-status-publication-20261019-green1.log` SHA256 `7b711c4d0208685ff6f99ae699d22f356a56d1c643de7e7d260b2f150080bb81`。
- `/tmp/easyai-status-publication-20261019-green2.log` SHA256 `beb266fcc9eef9623f0a4927b2d6e44f71076cec2a6a847a4e2ab38d0f96e108`。
- `/tmp/easyai-status-publication-20261019-green3.log` SHA256 `34ede81a169a7dbbbc1d87342c0eca427479b1b63a955349ce2d498eee6e2a99`。
- `/tmp/easyai-status-publication-20261019-red1.log` SHA256 `e16c755193ae6719c149dc98b9a034184f1c918a14c7ec942be66d792ed498a6`。
- `/tmp/easyai-status-publication-review-ZsgNcg.log` SHA256 `804802130b505cdc042f4c825e00c68da8841919e0bb711eab8fd3e811fbe92f`。
- `/tmp/easyai-final-lock-revalidation-review-yviUys.log` SHA256 `1ae7b6c3c9ffac75206a11a478dfef45290dcbc685d93e689f09e66657fb6d27`。


## 2026-10-19：existing-owned final-probe → mark-ready 收口遗漏 P2

父侧已复核关闭 ac0e0a460c39da7a575e378605d0811a75986498 的 status 原子发布与 verify/release 等待，又指出已有环境在 final-probe 后没有 creation.verify，直接调用 target.mark_ready，遗漏同一 writer 收口窗口。本轮仅修此分支，未重开外围。开始 checkout codex/demo-v0.0.0 / HEAD `950308c7e42a29d49c8b3384f9bf9b678bc78a90`，工作区 clean。源码完整 SHA `b873a004f5a8dc5321be30177a3e6ae3047cab3c`。

修复：mark-ready 加入现有 settling_owner 门，与 verify/release 相同，仅在同 job/plan/phase 静止收据下最多等2秒取得原 flock；每次等待、实际获锁后重验 claim、last-phase、intent。原 owned/inode/预算/授权检查不变，不删除锁，不重复执行命令，unknown 不开启等待。helper SHA256 `59bdebc76ae2a01479512dc6628589e6628bbd6f93437bf56897c7de411867c5`。

实际回归使用现有 InstallService→RemoteInstallTarget→helper/ManagedProcess 互操作链：先完成新建的4阶段，再对已有 owned 环境走安装+最终 probe 的2阶段。仅在已有环境 final-probe 的 status 已发布、serve 仍持 writer FD 时用 Event 屏障暂停真实 helper；实际 target.mark_ready 必须进入等待才放行 owner。旧实现确定性捕获 `('mark-ready', 'INSTALL_WRITER_BUSY')`；修复后同任务 SUCCEEDED/verified=true/needsReprobe=false、租约释放，ready 可读且总阶段数仍6，无重发。bootstrap/pip/probe 命令源码仍只捕获并明确替换为标准库打印合成报告；不当真实依赖/ABI/tensor/训练证据。原 unknown phase 回归追加 mark-ready，保留直接拒绝、不等待、不收口。

实际命令与结果（/workspace/Easy-AI；唯一日志/noclobber，FAIL保留）：

- FAIL（修前预期复现）：`services/backend/.venv/bin/pytest -q services/backend/tests/test_remote_install_protocol.py -k existing-owned-closeout`，1 failed /1 deselected，1.77s；red1 含准确 INSTALL_WRITER_BUSY。
- PASS：`services/backend/.venv/bin/pytest -q services/backend/tests/test_remote_install_protocol.py services/backend/tests/test_remote_install_owner.py services/backend/tests/test_install_transport.py services/backend/tests/test_remote_install.py`，55 passed /3.74s；green1。
- PASS：最终加强 verified/reprobe/lease 断言后 `services/backend/.venv/bin/pytest -q services/backend/tests/test_remote_install_protocol.py`，2 passed /1.43s；protocol-final1。
- PASS：`UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm check`，TS/合同/fixtures、Ruff/格式、mypy 66源文件等通过。
- PASS：`UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache XDG_CACHE_HOME=/workspace/.cache node scripts/python-task.mjs build`；源码提交后 `node scripts/test-frozen.mjs`，原文资源、默认禁执行登记/取消、认证黄金编译/临时 cwd、EOF exit0 通过。未做新 electron-builder 包或扩无关矩阵。
- PASS：独立只读审查9 passed /35 deselected、0.88s，覆盖实际 existing-owned probe/mark-ready 屏障、unknown 拒绝、原子发布边界，无新增明确阻断问题；未代改源码/SSH/安装/Actions。
- PASS：git diff --check；plan 仍116185字节、SHA256 dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43，README/原规格未变；来源锁、manifest/lock/CI配置无改动。

工作区/远端：源码提交后工作区 clean；预推送只读核远端开发分支仍950308c7e42a29d49c8b3384f9bf9b678bc78a90，main仍5323f86232529efcfb52131168ad049f01b219f3。证据提交后仅正常推开发分支、再核最终 SHA/clean/main，见最终回报。未写main/Feng、无强推/PR/Release/部署。

NOT RUN：真实 SSH/安装/上传/下载/依赖 import/ABI/tensor/训练、真实桌面/原生picker/干净机、Windows/macOS、CI日志请求或主动重跑。当前 source/证据 SHA 的 CI 结果 UNKNOWN；最新已知 e454f97044f84f20347b10f3807220727f2dac1f/run39181255841 与3616826e28cef2d2ce4fd874f1bb81a6fcf17d94/run39180535293 均为 pnpm install --frozen-lockfile 步骤双失败，准确安装错误正文/根因仍 UNKNOWN。既有 Actions 日志访问拒绝没有重试/换路，需要父侧提供准确正文才能继续定位。真实执行门/原计划缺口与B未完成状态不变。下一项父侧复核此有限 P2 后续原 M6.3，不把本合成回归称完整验收。

本轮日志 SHA256：
- `/tmp/easyai-existing-ready-20261019-build1.log` SHA256 `9b80f6521854897c5cc00c7b7660631d7f0f62c5642c8dba54a046485c09d4ca`。
- `/tmp/easyai-existing-ready-20261019-check1.log` SHA256 `c42bd4df1916148541e1f0f0341c6c525fc308786650e029608cdf52c46e75fc`。
- `/tmp/easyai-existing-ready-20261019-frozen1.log` SHA256 `598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。
- `/tmp/easyai-existing-ready-20261019-green1.log` SHA256 `3bada9d170c9aeb03627ee9b0eb9d9816cabed95ecb224007f76c36e4369e535`。
- `/tmp/easyai-existing-ready-20261019-protocol-final1.log` SHA256 `b7f8336f049bf5c200bf2bd7d571241e78b1a0d0214b388833883d38af823e1b`。
- `/tmp/easyai-existing-ready-20261019-red1.log` SHA256 `f154a77d30264cd443812e526cf52e3d681f2efaad882d5cc177edf451202b1e`。
- `/tmp/easyai-existing-ready-review-tNx0IT.log` SHA256 `e9f1f2b5598cb26d49c4fd46238f9dc6a79e55cf9dc7e86fb9895c04b19b5e75`。


## 2026-10-19：原14.3 NLP有限固定来源、闭包计划与复检

父侧已有限签收 fcf5e4db724adec2d49f8a96f3d02f51c144187b（55与独审9重叠不累加）；真实M6.3/B未验。本轮基线即该完整SHA，开始工作区clean，开发分支codex/demo-v0.0.0；原计划baseline仍5323f86232529efcfb52131168ad049f01b219f3，沿用已有实现，无覆盖/回退用户工作。源码完整SHA **`0f8e675dbaf35f5025dc1965565e76855e935838`**。单一集成者；独审仅只读核查/测试。

### 官方元数据裁决与实际接线

24次有界只读请求仅为pypi.org发行JSON/Simple JSON与files.pythonhosted.org的.whl.metadata，逐一核固定版本JSON SHA、索引声明PEP658 SHA、wheel URL/文件名/SHA/注册表字节/yanked、Python/完整Requires-Dist与当次漏洞投影。未请求任何wheel/archive本体。原始响应、requests.json和raw-sha256.json在`/tmp/easyai-nlp-metadata-20261019`，捕获脚本`/tmp/easyai_nlp_metadata_20261019.py`及`/tmp/easyai_nlp_capture_20261019.py`保留；源码仅保留来源字段与拒绝裁决，不搬入无关发行描述或漏洞PoC。

- **sentencepiece 0.2.2**：cp311 Linux x86_64 manylinux_2_27/2_28 wheel，注册表1394242字节，SHA256 `1416b92f2f010333786fe6306ed2631121d5ea492219b0841e967b6765e64107`；默认Requires-Dist为空，不启用numpy/protobuf/test extras。只可说明元数据适合固定Python/CPU profile，不声称native ABI实测。解包体积未知、installedBytes=null。核心21加本包为22个去重来源。
- **nltk 3.10.3**：[固定JSON](https://pypi.org/pypi/nltk/3.10.3/json)当次返回未撤回`GHSA-8mgp-746c-j5xp`（aliases含CVE-2026-81726/PYSEC-2026-3740），fixed_in空；明确`INSTALL_KNOWN_PACKAGE_VULNERABILITY`，本片不擅自豁免/选旧版。未宣称所有历史NLTK版本已审查。
- **spacy 3.8.16、transformers 5.20.1、gensim 4.4.0、hanlp 2.1.5**：已核顶层JSON/PEP658及固定Python；已出现的核心NumPy/SciPy/CPU torch约束接受既有pins，没有证实相应直接冲突。完整传递闭包（thinc等、hub/tokenizers等、smart-open等、downloader/transformers等）尚未核完，保持`INSTALL_NLP_CLOSURE_UNREVIEWED`，不冒称版本不兼容。模型/语料与未选extras均不获取。

新增`easyai-nlp-sources.json`/`easyai-nlp-linux-cp311.lock`只有SentencePiece进入packages与可执行闭包，另五候选仅在rejectedCandidates保留证据。NLP_ROOTS→原wheels去重/lock_bytes→constraintsHash（原八文件加NLP两文件）→planHash与过期重核→按选择来源/缺失/hash/字节预算→原唯一OfflineWheelInstaller及共享远端适配→选中sentencepiece import/精确版本/原CPU tensor复检全部接线；不是仅卡片文字。全NLP组选含不支持卡即blocked、总体体积unknown，单选支持子集才可解析。

SourceSelection按具体拒绝code返回，避免把NLTK或闭包未核误报OpenCV native；UI有对应阻止说明。来源确认仍落executionAuthorized=false，默认executionEnabled=false；不新建解析器/安装器，不改核心锁或开门。PyInstaller资源/原包资源清单纳入NLP两文件；冻结测试核十文件hash、22包计划与NLP整组拒绝。许可声明仅元数据，legalReviewComplete/distributionReady未变。

当前17卡为**11卡元数据闭包/6卡unsupported**：OpenCV native+NLP五卡。install-nlp-sources.md、原安装合同/当前清单/critical-path已更新，历史DL文档明确其当时状态；实际安装及完整B仍NOT RUN。

### 实际命令与证据

在`/workspace/Easy-AI`执行；唯一输出日志/noclobber保存，失败不删除不覆盖：

- PASS：`services/backend/.venv/bin/python /tmp/easyai_nlp_metadata_20261019.py`（六latest发行只读发现）及`services/backend/.venv/bin/python /tmp/easyai_nlp_capture_20261019.py`（六pinnedJSON+Simple+PEP658）；metadata两日志，WHEEL_REQUESTS=0。
- FAIL（中间实现/fixture，不伪称产品首轮全绿）：首个inline编辑脚本在查找python-task.mjs add-data缩进时ValueError，先核准已完成源码/目录改动及尚未执行的资源改动才补缺失部分；`edit-failure1.log`明确为工具输出转录而非原始重定向。新NLP测试首轮3 failed/30 passed：未注入runtime却测preview、引用不存在download_bytes字段、未mkdir app；独审首轮也6PASS/3FAIL。均为测试fixture错误，未降低生产门或断言；原日志保留。独审另指出冻结hash预期遗漏NLP两文件，在运行最终冻结测试前补十文件及NLP HTTP断言。
- PASS：`services/backend/.venv/bin/pytest -q services/backend/tests/test_install_nlp.py services/backend/tests/test_install_ml.py services/backend/tests/test_install_cv.py services/backend/tests/test_install_dl.py`，**33 passed /0.69s**（targeted2）。含6候选markers/已知pin兼容、单选/混组/整组blocked、来源缺失/预算/登记禁授权、源/锁漂移使计划过期、同一固定离线命令/精确lock、选中import捕获、版本/import/tensor失败门。所有NLP测试Popen/socket均拒绝，合成inventory不是训练证据。
- PASS：`services/backend/.venv/bin/pytest -q services/backend/tests/test_install_service.py services/backend/tests/test_install_source_selection.py services/backend/tests/test_install_history.py services/backend/tests/test_remote_install.py services/backend/tests/test_remote_install_protocol.py services/backend/tests/test_remote_install_owner.py services/backend/tests/test_install_transport.py`，**99 passed /4.72s**（regression1）。远端仅合成SDK/标准库子进程，不真实SSH/依赖执行。上述33/99与独审重叠部分不累加为独立能力证据。
- PASS：`pnpm exec vitest run apps/desktop/src/PackageManager.test.mts`，**13 passed**；`pnpm test:package`，**20 passed**。只原包装保护回归，无新electron-builder产物。
- PASS：`UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm check`（check2最终），TS/合同/fixtures、Ruff/格式、mypy66源文件、Prettier通过。
- PASS：`UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache XDG_CACHE_HOME=/workspace/.cache pnpm build`；`node scripts/test-frozen.mjs`（frozen1），实际冻结sidecar资源原文、十文件constraintsHash、NLP单卡计划与组blocked、默认禁执行登记/取消、认证黄金编译/临时cwd/EOF退出0通过。未启动Electron或依赖安装。
- PASS：独立只读核六候选原始JSON/PEP658与所有来源字段、24请求无wheel；64可选组合无重复/核心替换。失败三fixture修后独立重跑**3 passed/6 deselected**，确认新freeze逻辑/脚本语法，无剩余明确P1/P2；测试与本轮回归重叠，不累加。独审不联网、不安装、不代改。
- PASS：git diff --check；原plan仍116185字节/hash dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43，README/原v0.0.0与core/ML/CV/DL八来源锁hash均未改；pnpm-lock、uv.lock、CI配置未改。NLP来源SHA256 `85ad6c5f96947b502d5c85949983358e69f8440642c265f0a9dc43c8a6137227`，NLP锁SHA256 `d05b0c5316934a9a363c2da5e2b7844eceb3893bd92aa4526ef89827dd27663c`。

### 远端、阻塞与下一项

源提交后工作区clean；预推送只读ls-remote确认origin开发分支仍fcf5e4db724adec2d49f8a96f3d02f51c144187b、main仍5323f86232529efcfb52131168ad049f01b219f3。证据提交后仅正常push开发分支并核最终完整SHA/clean/main，最终回报为准。未写main/Feng原仓库、无强推/PR/Release/部署/新凭据/权限/条款。

NOT RUN：wheel/语料/模型/训练数据下载，训练环境安装、真实NLP或训练import/ABI/tensor/训练，真实SSH/上传/安装故障矩阵、桌面/native picker/干净目标机/Windows/macOS、新CI日志查询或主动重跑。真实执行最小条件仍须具体隔离owned目标/已备可信来源、平台/launcher、许可/预算/窗口与认证身份后另核；本轮没有发出这些外部写入。

CI准确安装错误正文/根因仍UNKNOWN：最新已知父侧证据e454f97044f84f20347b10f3807220727f2dac1f/run39181255841和3616826e28cef2d2ce4fd874f1bb81a6fcf17d94/run39180535293在pnpm install --frozen-lockfile步骤双失败。本轮source/证据SHA的云CI结果未知；既有Actions日志访问拒绝未重试/绕路，需要准确正文才可进一步定位，不按步骤名假修锁。Electron sandbox拒绝同样未重试。旧226PASS/1FAIL raw丢失根因UNKNOWN及其他原计划缺口不回溯关闭。

下一项由父侧复核此有限NLP子集；剩余四卡完整固定闭包、NLTK候选安全裁决、OpenCV native以及原M6.3/M7/M8代码/真实验收门继续保持未完成，不承诺六卡全开或仅差环境。

本轮日志与元数据审计SHA256（含FAIL原样/明确转录标识）：
- `/tmp/easyai-nlp-20261019-build1.log` SHA256 `887f795e5d3cbc1f173fbd7a7be4909fb4c2eee3059703b6beddbeb2e97c8f5a`。
- `/tmp/easyai-nlp-20261019-check1.log` SHA256 `33d638c44f61709c5fea38251066696a5a89ca3d3d4d8bf8ffb532d282f23af2`。
- `/tmp/easyai-nlp-20261019-check2.log` SHA256 `33d638c44f61709c5fea38251066696a5a89ca3d3d4d8bf8ffb532d282f23af2`。
- `/tmp/easyai-nlp-20261019-edit-failure1.log` SHA256 `81a2c9615d513e8843ceb96a2f6832c178f94e6fe267d0255944eff6130ce66f`。
- `/tmp/easyai-nlp-20261019-frozen1.log` SHA256 `598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。
- `/tmp/easyai-nlp-20261019-package1.log` SHA256 `63bf8c270ed8af045a69294c1e506c5cdf8c47c41dfeb34e1de108b5a6114ecd`。
- `/tmp/easyai-nlp-20261019-regression1.log` SHA256 `348157e7b9b20b105bd5ee89e8374dbc6f2f3d6f4a536d836e309e5265805084`。
- `/tmp/easyai-nlp-20261019-targeted1.log` SHA256 `6e0f2e3191d5e1985365e77c30ce05de912279339e5e914016352111a435b0f3`。
- `/tmp/easyai-nlp-20261019-targeted2.log` SHA256 `12c5944a5b6972773f1ef0adaaf3d73cfcac9059f4b8c693e093373ed61b2995`。
- `/tmp/easyai-nlp-20261019-ui1.log` SHA256 `70710e06bf250913deef59418caadeb878cef69fe696a56992149ece5ff17d04`。
- `/tmp/easyai-nlp-metadata-20261019-capture1.log` SHA256 `94bc45b866762e719b72c36030f79d33e3a6549bf17cfa5ee6fbbd285bf2e332`。
- `/tmp/easyai-nlp-metadata-20261019-discovery1.log` SHA256 `078cf22797c676ced7cb55dc65434d65367fe596180d6fdb598e650107f274e5`。
- `/tmp/easyai-nlp-review-Y6Rwks.log` SHA256 `22419ad2aee6eb4f547945e0dd6af48487762af0089c7970863f2345c3ffd71e`。
- `/tmp/easyai-nlp-fixed-review-BUmplQ.log` SHA256 `af78d42bcd3e878c33a59d206755284f6e3eb054295e645f1cd8b6894a770bed`。
- `/tmp/easyai-nlp-metadata-20261019/requests.json` SHA256 `0750244f832d41acba03d27a6019067785c2bfc395867f64d9b3031bf4bd2190`。
- `/tmp/easyai-nlp-metadata-20261019/raw-sha256.json` SHA256 `a3a4f96191fef335e8fa7a4173b7644c225e05c547b08d7aacc718562f30fcb8`。
- `/tmp/easyai_nlp_metadata_20261019.py` SHA256 `81d74cc3bd8c3159dff00553e471b4710ee5ed7ab383d5b0af90a2bbdda4f2be`。
- `/tmp/easyai_nlp_capture_20261019.py` SHA256 `98434a06b6b769744295624d120564d25717e0fb6901863c5a8722564431a1c2`。


## 2026-10-19：原14.3剩余四NLP卡默认闭包整批裁决与原链交付

父侧有限接受0f8e675dbaf35f5025dc1965565e76855e935838/5cb7757859dc3c4bfa7c2a083de9aa7e679b0c99的SentencePiece元数据接线。本轮按要求一次完整裁决spaCy/Transformers/Gensim/HanLP，不拆统计小片。开始HEAD/远端开发分支均`5cb7757859dc3c4bfa7c2a083de9aa7e679b0c99`、工作区clean，单一集成者；原计划baseline/main仍5323f86232529efcfb52131168ad049f01b219f3。源码完整SHA **`467a2018194ae131789f45cd62a56ffdc0783950`**。

### 批次结论、预算与能力边界

- **spaCy3.8.16**：43可达节点（止于既有固定闭包锚点），无当前声明约束冲突；新thinc8.3.13/blis等默认闭包完整。复用原DL的tqdm/idna，实际原planner计划60wheel，核心21以外59656447字节，总300429146字节。
- **Transformers5.20.1**：27可达节点，无当前声明约束冲突；hub2.2.0/tokenizers0.23.3/safetensors0.8.0/hf-xet等默认闭包完整，无其他extras。复用固定pyyaml/tqdm/idna，实际计划43wheel，核心外25866254字节，总266638953字节。
- **Gensim4.4.0**：完整5节点=本包/NumPy/原SciPy/smart-open8.0.4/wrapt2.5.1。实际计划25wheel，核心外63473279字节（包括不在核心21里的既有可选SciPy），总304245978字节。不能把新候选3wheel的28123979字节冒充整个计划增量。
- **HanLP2.1.5**：明确`INSTALL_BINARY_WHEEL_UNAVAILABLE`。直接依赖hanlp-common0.0.23、hanlp-downloader0.0.25、hanlp-trie0.0.5固定JSON的全部artifact只有sdist，没有目标wheel；原安装器仅binary，不下载/构建源码或换版本。已核可达33记录加3个二进制阻断节点，阻断之后没有伪称完整可安装闭包；总体download/installed体积仍未知。不是CPU/NumPy约束冲突。

三新库联合实际计划72wheel/387209225字节；加原SentencePiece为73wheel/388603467字节。所有数据为可信注册表wheel下载元数据，未下载本体，不含bootstrap/完整环境占用，解包量及installedBytes均null。核心NumPy2.4.2、torch2.10.0+cpu与原core/ML/CV/DL八来源锁完全不改。NLP源48package（SentencePiece+47新增）保留完整默认Requires-Dist、markers、pinnedJSON/PEP658/文件hash/字节、当次yanked/漏洞与许可投影；97184字节，保留原100000上限。

NLTK3.10.3安全阻断不变（父侧已核PyPI/OSV last_affected3.10.3；不降级绕过、不声称逐版复现）。当前**14/17卡仅为元数据闭包/计划能力**；OpenCV native、NLTK与HanLP仍unsupported，不签实际安装或B。

### 实际实现与离线行为裁决

三根进入NLP_ROOTS/显式distribution→import映射/原wheels闭包、NLP hash lock、原constraintsHash/planHash过期门、选择来源/预算、同一OfflineWheelInstaller与共享远端lock生成器、精确版本/选中imports/原CPU tensor复检。未新建运行时resolver或安装器。Gensim按选择加载既有ML provider；spaCy/Transformers加载DL provider复用少量固定pin。只选Lightning才展开core fsspec[http]；Transformers普通fsspec依赖不额外引入aiohttp。512个可选根组合核去重、核心不替换、闭包可达与该extra门。

来源登记仍executionAuthorized=false；默认执行门关闭。原--no-index/--only-binary=:all:/--require-hashes、固定本地来源与清PIP配置未改变。HanLP具体code映射及UI阻止文案替代旧“闭包尚未核完”，全NLP组含NLTK/HanLP仍blocked/总量unknown。源/锁漂移会使已确认计划失效。API合同/应用依赖/核心锁不变。

发行PEP658描述证据：spaCy模型通过独立download命令或模型包安装、随后spacy.load；Transformers明确指定模型pipeline会下载/缓存；HanLP示例将import与hanlp.load(pretrained)分开且依赖downloader；Gensim元数据未保证plain import零联网。这些不能反推plain import必下载，也不能证明其零联网。固定probe只做选中普通imports、版本与tensor，AST测试无pipeline/from_pretrained/load/download调用；未新增模型选择、加载、下载、服务、语料或预训练API能力，未接受新条款或权限。

**没有网络隔离声明。** pip离线参数不约束第三方import中的native/网络行为，私有HOME/超时/取消也不等于封网。独审最初建议OFFLINE_IMPORT_UNVERIFIED时已澄清：这是“不能保证零egress”的真实执行门，不能把未import本身当作元数据闭包不成立（SentencePiece同样未import）。本片三包只签元数据/计划能力，实际import/native ABI/无下载行为一律NOT RUN；未来执行须在具体来源/目标/许可/预算/窗口内另验。未靠环境变量伪造隔离，也未开放系统权限。

### 元数据读取、原文保全与中间错误

本批共**214**个有界官方JSON/PEP658请求（210主图+4补充JSON）；只允许pypi.org JSON/Simple与files.pythonhosted.org的.whl.metadata，未请求wheel/sdist/模型/语料。开发审计脚本不进入应用运行时。`/tmp/easyai-nlp-four-20261019`保留112个文件的清单（随后生成preserved-files.json），包括pinnedJSON/PEP658原文、48条来源对应记录（SentencePiece原件另见上一批目录）、最终默认图、3个sdist-only原JSON与审计记录。latest/Simple响应在捕获时核对并保留请求hash，未把未存全文的索引响应宣称为完整原文备份。

中间审计错误保留：Gensim单根候选扫描遇到smart-open历史16个发行artifact的非法Requires-Python `>=3.5.*`，这是开发工具解析错误，不是当前包冲突。联合图已获取并核验smart-open8.0.4及wrapt；后续仅离线从联合已核图提取Gensim完整5节点、逐边校验，另读4个JSON保存三个sdist-only证据和历史坏字段证据，没有降级/绕过拒绝。初版NLP测试只接受cp311而漏合法旧CPython abi3 tag，targeted1为1FAIL/44PASS；修为packaging.tags精确目标集合，仍明确拒绝cp312/Windows负例，原失败日志保留。

### 实际命令与PASS/FAIL

所有命令在/workspace/Easy-AI；唯一日志/noclobber，失败不覆盖：

- PASS（含上述明确审计错误行）：`services/backend/.venv/bin/python /tmp/easyai_nlp_four_graph_20261019.py`，210 JSON/metadata，主图/联合结果保留；`services/backend/.venv/bin/python /tmp/easyai_nlp_four_finish_20261019.py`，4 JSON、最终三完整图与HanLP阻断证据。`services/backend/.venv/bin/python /tmp/easyai_nlp_four_integrate_20261019.py`仅把已核记录/边写入固定来源、锁与原链，未执行候选包。
- FAIL（测试漏abi3）：`services/backend/.venv/bin/pytest -q services/backend/tests/test_install_nlp.py services/backend/tests/test_install_ml.py services/backend/tests/test_install_cv.py services/backend/tests/test_install_dl.py`，targeted1 **1 failed/44 passed**；targeted2修后45PASS，追加覆盖后targeted3 **50 passed/1.81s**。包括512组合、三根所需ML/DL来源缺失/预算/登记禁授权、同一精确锁/离线命令、plain-import-only AST、每根版本/import/tensor失败门。NLP测试拒绝Popen/socket真实调用，合成inventory不当真实ABI证据。
- PASS：`services/backend/.venv/bin/pytest -q services/backend/tests/test_install_service.py services/backend/tests/test_install_source_selection.py services/backend/tests/test_install_history.py services/backend/tests/test_remote_install.py services/backend/tests/test_remote_install_protocol.py services/backend/tests/test_remote_install_owner.py services/backend/tests/test_install_transport.py`，**99 passed/5.41s**；仅合成SDK/标准库子进程，不真实SSH或包执行。
- PASS：`pnpm exec vitest run apps/desktop/src/PackageManager.test.mts`，**13 passed**；`pnpm test:package`，**20 passed**，原保护回归，无新builder包。
- PASS：`UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache pnpm check`，TS/合同/fixtures、Ruff/格式、严格mypy66源文件、Prettier；`UV_OFFLINE=1 UV_CACHE_DIR=/workspace/.uv-cache XDG_CACHE_HOME=/workspace/.cache pnpm build`。
- PASS：源提交后`node scripts/test-frozen.mjs`，实际冻结sidecar原文资源/十文件constraintsHash、三根60/43/25的HTTP计划/正确预算与默认禁执行、NLP组拒绝、认证黄金编译/临时cwd/EOF退出0。未启动Electron或训练环境。
- PASS：独立只读NLP **26 passed/1.35s**（与50定向重叠，不累加）；48条来源原始pinnedJSON/PEP658/文件hash/大小/完整Requires-Dist、三sdist-only证据核对，三库联合pins一致，无剩余明确P1/P2；未联网/import/安装/代改。当前NLP合同/清单旧“仅SentencePiece/11卡/四卡未核”已统一更正。
- PASS：git diff --check；原plan116185字节/hash dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43、README/旧规格与core/ML/CV/DL八来源锁hash均未改；pnpm-lock/uv.lock/CI配置未改。NLP来源SHA256 `3a781aa307fa9e3a934752887321445c51f7de514c8b722a9342aca7887e024e`，NLP锁SHA256 `061e82c755d932675f1359f26dbea69bdc3a27fcd5ca7e5135a1ac52fd73ee29`。

### 远端差异、真实门与下一项

源提交后工作区clean；预推送ls-remote开发分支仍5cb7757859dc3c4bfa7c2a083de9aa7e679b0c99，origin仍https://github.com/T1doo/Easy-AI.git，main仍5323f86232529efcfb52131168ad049f01b219f3。本证据提交后仅正常推codex/demo-v0.0.0并核完整最终SHA/clean/main，最终回报为准；无main/Feng写入、强推、PR、Release或部署。

NOT RUN：wheel/sdist/模型/语料/数据下载、安装/源码构建/真实NLP或训练import/ABI/tensor/训练、零egress实测、真实SSH/上传/服务器故障/桌面/native picker/干净目标机/Windows/macOS、新CI日志读取或主动重跑。没有新增凭据/收费/权限/条款，未改教师共享环境或执行门。下一项父侧复核本整批裁决后继续原M6.3/M7/M8剩余项；OpenCV native、NLTK候选安全与HanLP二进制来源保持具体unsupported，真实M6.3/B未验，不称全部仅差环境。

CI准确安装错误正文/根因仍独立UNKNOWN：最新已知e454f97044f84f20347b10f3807220727f2dac1f/run39181255841及3616826e28cef2d2ce4fd874f1bb81a6fcf17d94/run39180535293同pnpm install --frozen-lockfile步骤双失败。本轮源码/证据SHA云CI结果未知。对错误正文的既有Actions访问拒绝未重试/换路，需父侧提供准确正文，不按步骤名猜lock修复；既有Electron sandbox拒绝也未重试。旧226PASS/1FAIL raw丢失根因UNKNOWN不回溯关闭。

本批日志/脚本/元数据清单SHA256（FAIL及纠正均保留）：
- `/tmp/easyai-nlp-four-20261019-build1.log` SHA256 `eb838303b667491af70dc3518537497cd539b6b2a33d1582485470b0cb56b3e2`。
- `/tmp/easyai-nlp-four-20261019-check1.log` SHA256 `33d638c44f61709c5fea38251066696a5a89ca3d3d4d8bf8ffb532d282f23af2`。
- `/tmp/easyai-nlp-four-20261019-discovery1.log` SHA256 `fbabbd9de1daa803a6191f595194aead7e5261c12fb665bbd59b2b5b0db25ae8`。
- `/tmp/easyai-nlp-four-20261019-finish1.log` SHA256 `37fa7a7c42fb96caab0b73972fb36516c71dde6766d6b2b336eba8b1349d0ae5`。
- `/tmp/easyai-nlp-four-20261019-frozen1.log` SHA256 `598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。
- `/tmp/easyai-nlp-four-20261019-integrate1.log` SHA256 `3bffe6802698afe299a577e9601d20418a68b4f946a7ce1056307decc1b68b4b`。
- `/tmp/easyai-nlp-four-20261019-package1.log` SHA256 `96025f674b59712162499bdc075f2027d719082bcdae289b39124160705aa715`。
- `/tmp/easyai-nlp-four-20261019-regression1.log` SHA256 `a03e9410918581e1ccd6022f81dceb413683cd2d1cf3259f8d491786bf167669`。
- `/tmp/easyai-nlp-four-20261019-targeted1.log` SHA256 `e50b47abffe95328d8057b3beeca4a1d25bbd5674314b3bf599d065e6debfa8b`。
- `/tmp/easyai-nlp-four-20261019-targeted2.log` SHA256 `e658bc78ab8dc3ad20432fd0c5f191521be56af24c467f74a19523911bb6477d`。
- `/tmp/easyai-nlp-four-20261019-targeted3.log` SHA256 `eca99486b913c06a4ff2da7b9018a51e98a9ccb3039f8bc272ff16f9865ffc37`。
- `/tmp/easyai-nlp-four-20261019-ui1.log` SHA256 `d980540120b720eed0f2a3f9a6723613ff22d8a3152489aae29cfeb98dddd4cf`。
- `/tmp/easyai-nlp-expanded-review-cqNPbl.log` SHA256 `1b62398230dbae646cdebb2b3778443ebceb0e9dff086a5ec08d675f2a524cde`。
- `/tmp/easyai_nlp_four_graph_20261019.py` SHA256 `08a0a3c8aaf85294e5d0ad57a4f7fbaf03cc64efbbc34c626608541ee16c6a51`。
- `/tmp/easyai_nlp_four_finish_20261019.py` SHA256 `0b46bd73991e082d8baa39f653549e34c8f59b6406075f78e6f605425fdcf8e1`。
- `/tmp/easyai_nlp_four_integrate_20261019.py` SHA256 `cd5a1b37b3fad7543dc6ca44c8296f13da3dbdb89120d395eef2b4f6c6f37898`。
- `/tmp/easyai-nlp-four-20261019/requests.json` SHA256 `d1f0ebe12e257ffd540e6223bcff580ab7d0981cdd70ac32bfa5f987cf1a7129`。
- `/tmp/easyai-nlp-four-20261019/additional-requests.json` SHA256 `61cc186e25ff48e51220c14f8c6dd2bdff3041e85a621c2712e6ba113373468c`。
- `/tmp/easyai-nlp-four-20261019/final-decisions.json` SHA256 `7c87494e3fcec039c792b3382c44b5a3ff82b358f2de7fb4d8db5a32614223e2`。
- `/tmp/easyai-nlp-four-20261019/invalid-historical-requires-python.json` SHA256 `1cbd2d837115a0ad60a5324c1b19f5426189ceb0dc5510876a419a7cdc6f796a`。
- `/tmp/easyai-nlp-four-20261019/preserved-files.json` SHA256 `00054a629e46330a5eefa5bccf71435ce641e20caf46634220ea1a67f2788d31`。

## 2026-10-19 M0–M8 有界收口（仅文档）

接受的产品源码为 `467a2018194ae131789f45cd62a56ffdc0783950`，上一证据/本轮起始 HEAD 及远端开发分支均为 `1e345b954f745ac5154f211dcc7200d6527db78b`。本轮不新增产品代码、测试替身或包装；按原计划重新区分代码已有待实测、具体未支持与明确后续设计，完整 A/B 均未通过。

更新 `docs/remaining-critical-path.md` 的 M0–M8 盘点，并同步发布清单、CIFAR 与远端安装文档。§5.5 的保留/清理管理移出本期欠账；§12.6 的未知身份人工检查不扩大为强制解锁需求；存活安装观察/取消/释放链已有，真实链未验。撤回包含已实现与超范围工作的旧25–50/6–18小时估工。仍保留 CIFAR 官方安全构造未完成、OpenCV native/NLTK/HanLP三卡未支持、Windows生产门关闭、真实验收和许可未完成等限制，不称全部只差环境。

实际只读/文档命令（cwd `/workspace/Easy-AI`）：`pwd`、`git status --short`、`git rev-parse HEAD`、`git remote -v`、`cat AGENTS.md`、`cat docs/remaining-critical-path.md`、`cat docs/release-checklist.md`、`rg -n '7 张|7张|下一步|方案|明确' docs/remote-install.md docs/cifar10-preflight.md`、`tail -45 docs/implementation-progress.md`、`git log -3 --format='%H %s'`、`git show-ref refs/remotes/origin/codex/demo-v0.0.0 refs/remotes/origin/main`、Python pathlib文档定向编辑、`git diff --check`、`git diff --stat`、Python pathlib/hashlib原件校验、`git ls-remote origin refs/heads/codex/demo-v0.0.0 refs/heads/main`。

PASS：原plan116185字节，SHA256 `dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43`；原规格21815字节/hash `5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190`；README3629字节/hash `befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852`。`git diff --check` PASS；原工作区clean，无用户改动被覆盖。预推送远端开发分支为上列起始HEAD，main仍 `5323f86232529efcfb52131168ad049f01b219f3`。

独立只读审查已核原plan/现有代码与文档，指出上述旧欠账误分类；本次具体文档另作最终只读复核。测试/build/新CI读取或重跑、真实Electron/SSH/安装/import/训练/数据/包下载、新builder包：NOT RUN（仅文档，无需重复已接受的定向测试）。此前CI安装FAIL、226PASS/1FAIL原始日志缺失根因UNKNOWN等历史记录全部保留，没有转为PASS。

准确阻塞：①CIFAR窄例外于2026-10-18 19:18 UTC既已提出、仍待答，保持SAFE_PROBE_REQUIRED，不重问或绕过；②Actions错误正文读取此前被拒绝，本次未重试/换路；最新已知e454f97044f84f20347b10f3807220727f2dac1f/run39181255841和3616826e28cef2d2ce4fd874f1bb81a6fcf17d94/run39180535293在同pnpm安装步骤双失败，准确正文/根因UNKNOWN，需父侧提供正文；当前源码CI未知；③此前sandbox动作拒绝继续有效，不降安全，需要可保留sandbox的桌面与已有训练数据/环境；④真实SSH/owned安装缺明确目标/可信指纹/预算/窗口及相关执行授权，未尝试。下一项仅在相关输入到齐后恢复对应有界工作；当前停止新增开发并保存成果。不建PR/Release、不部署、不改main/Feng仓库/安全权限，不新增费用或凭据。

最终独立只读复核 PASS：五份收口文档的范围和证据分类无明确P1/P2；未把元数据闭包、合成测试或旧包当A/B。正常提交与推送仅限 `codex/demo-v0.0.0`；提交后的完整SHA与远端一致性在最终回报提供，不能自嵌本提交hash。

## 2026-10-19 Windows CI 已知脚本策略失败的有界修复

用户提供run39181255841 Windows日志：锁文件与供应链校验通过后ERR_PNPM_IGNORED_BUILDS electron-winstaller@5.4.0。该正文解除Windows这一项根因未知，未授权Actions接口；另一个Linux job原因仍UNKNOWN。起始HEAD/远端开发分支均`66c4570ccec7590bfa9621eb0ff33d6a8ea87bd2`、工作区clean，单一写入者。main仍`5323f86232529efcfb52131168ad049f01b219f3`。

检查精确锁和本机package/script：builder→app-builder-lib的Squirrel peer→winstaller5.4.0。实际install为node ./script/select-7z-arch.js，仅复制包内7z架构文件；未运行。当前Windows CI只构建/测试桌面，无Squirrel目标，正式builder限定Linux dir/tar.gz。pnpm11.25实际policy只读allowBuilds，旧onlyBuiltDependencies许可迁移并收窄为electron@44.9.0:true；winstaller@5.4.0:false，strictDepBuilds:true。未改变锁/依赖/CI，未新增脚本执行许可，未全局放开或approve-builds。完整裁决、命令和失败说明见docs/ci-build-policy.md；当前发布/关键路径清单同步更正，历史FAIL保留。

PASS：`pnpm config get allowBuilds`、`pnpm config get strictDepBuilds`；隔离git archive+新配置，在`/workspace/easyai-pnpm-policy-7onsg4ra`执行`CI=true XDG_CACHE_HOME=/workspace/.cache pnpm install --offline --frozen-lockfile --store-dir /workspace/.local/share/pnpm/store`，354复用/0下载/1.2s，锁及供应链通过。原node_modules记录实际store，所以一次从错误空store失败后只改到此已知本地store；首失败ERR_PNPM_NO_OFFLINE_TARBALL @playwright/test保留，不联网补。隔离真实winstaller vendor无7z.exe/dll，modules状态规则精确。临时无害file依赖负例真实pnpm install --offline被strict以ERR_PNPM_IGNORED_BUILDS拒绝且marker未出现，证明未知脚本仍失败；不当Windows证据。

FAIL：`pnpm --filter @easyai/desktop check`自动依赖核验尝试默认/home/agent/.local/share/pnpm创建ENOENT，未进入TS；未提权或重试此路径。PASS：隔离已安装目录直接`node node_modules/typescript/bin/tsc --noEmit -p apps/desktop/tsconfig.json`及`node node_modules/typescript/bin/tsc --noEmit -p apps/desktop/tsconfig.electron.json`。PASS：`node --test scripts/package-builder.test.mjs` 5项；`git diff --check`。独立只读复核pnpm11.25实际policy、精确依赖与hook/当前目标，未发现明确P1/P2，无新增脚本许可。

NOT RUN：Windows新CI/原生桌面、Squirrel安装器、hook执行、候选包/数据下载、训练/SSH/受控安装、新builder包。只正常推开发分支触发既有一次工作流，不主动重跑旧SHA、workflow_dispatch或读取被拒Actions接口。CIFAR既有待答、安全sandbox/桌面/SSH/安装目标预算授权未变，A/B未通过。下一项父侧合法渠道确认本修复SHA的Windows install及后续阶段；Linux仍单独确认正文和结果。最终完整提交SHA、push与clean/main核对在回报提供。

本轮日志SHA256（FAIL保留）：
- `/tmp/easyai-pnpm-policy-buildertest-20261019.log`：`abee3290462caa1a7cc8285419d82abe4d6c221e65994ae06463252fb0991ca6`。
- `/tmp/easyai-pnpm-policy-install-20261019.log`：`3fd0edb29cc11ade955aab30dbd6d701018a12bff3e980d5a036492c89cad362`。
- `/tmp/easyai-pnpm-policy-install-store-20261019.log`：`68dff657548c5596e358268b183aafd20194613b31c4ddf16ebb9a76de49996a`。
- `/tmp/easyai-pnpm-policy-strict-negative-20261019.log`：`afa407526c7cde54fd7d8ab14d59d1e12c11b77077d0d9cefdc0d54f1c2759ca`。
- `/tmp/easyai-pnpm-policy-tscheck-20261019.log`：`a164a71af9b231bfdda437823abe01d11476b128be0f1036c3d3076472abdf8e`。
- `/tmp/easyai-pnpm-policy-tscheck-direct-20261019.log`：`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。

## 2026-10-19 run39195428530 后续失败的本地复现（无产品改动、不触发新CI）

父侧通过允许的run/jobs元数据确认：两个`pnpm install --frozen-lockfile` PASS，原安装阻塞解除；check的setup/check PASS，pnpm test FAIL；desktop的Project persistence、Experimental NTFS readiness、Freeze backend、Frozen backend HTTP/resource gates全部PASS，随后`pnpm --filter @easyai/desktop build` FAIL、e2e skipped。未提供两个失败正文；未访问此前被拒日志接口或替代绕行。实验NTFS阶段成功不自动开放Windows生产门。

单一写入者；起始精确HEAD及远端开发分支`a62b48ac04e9c9fd434f9217d78679ebe1a2fa7a`，工作区clean，main仍`5323f86232529efcfb52131168ad049f01b219f3`。本地当前平台Linux，暖缓存/既有环境，不能冒充Windows或clean CI。

实际命令（cwd `/workspace/Easy-AI`）与结果：
- PASS：`CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache pnpm install --offline --frozen-lockfile --store-dir /workspace/.local/share/pnpm/store`，Already up to date，803ms，锁/供应链通过，无下载。
- PASS：`CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache UV_CACHE_DIR=/workspace/.uv-cache UV_OFFLINE=1 pnpm test`，exit0；Vitest39文件PASS/1文件skip，334PASS/2skip；pytest924PASS/8skip/1warning，74.98s；Node包保护20PASS，938ms。跳过项不充当真实桌面/Windows/SSH证据，警告原文保留。未用缩小测试范围代替原命令。
- PASS：`CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache pnpm --filter @easyai/desktop build`，exit0；tsc及Vite8.3.4，767模块，Vite928ms；保留大于500KiB chunk警告，未调整安全或warning阈值。仅生成开发dist，不是新builder包。
- PASS：`git diff --check`；源码/锁/工作流未变。本次只补证据文档，不推送，避免无修复地触发下一CI。

独立只读复核当前build入口`tsc -p tsconfig.electron.json && vite build`、相对配置、URL资源加载与nonce adapter的Windows分隔符规范化，未发现可确定Windows缺陷；不根据平台或步骤名猜测路径/CSP/依赖根因。严格脚本策略保持原修复；不关闭任何安全门。

准确阻塞/最小缺失正文：Linux check job的`pnpm test`中第一个失败suite/test名称、expected/actual或pytest traceback及最终各runner摘要/退出码（若进程直接退出则其错误/信号段）；Windows desktop build步骤首个实际错误及前后20–30行、最终退出码；若TS需完整错误号/文件行号，若Vite需首个插件/模块/cause。用户已有正文只覆盖上轮安装错误，不能推断本轮原因。当前两个CI阶段FAIL，原因UNKNOWN；本地未复现且没有实质修复，因此不盲推新CI。NOT RUN：Windows本地复现/E2E、Actions日志读取/重跑、新打包、真实训练/SSH/受控安装；CIFAR限制未变，但不阻止独立诊断。

本地完整日志SHA256：
- `/tmp/easyai-ci-followup-install-20261019.log`：`1b449d2fc7c7617eb08451638870c85310ec821225a6b49051835f3b3b291a9e`。
- `/tmp/easyai-ci-followup-test-20261019.log`：`d863116fe7f4a28d3e7240d62bd233cec1cf2a2bee8bd1a16f1548d4afd79b73`。
- `/tmp/easyai-ci-followup-desktopbuild-20261019.log`：`1813320c0343741d367acea834e8b23ac1d9f9a5f481a491af9cfc6eebeab3f6`。

本节及相关清单只作本地证据提交，保持远端a62b48ac04e9c9fd434f9217d78679ebe1a2fa7a，不push，不请求/重跑CI。下一项取得上述最小失败正文后按实际错误恢复有界修复；最终报告给出本地完整证据SHA和未推送差异。

## 2026-10-19 Linux暂停发布竞争及Windows模块解析歧义修复

本轮继续单一写入者。起始本地`b97d8c11fde784bad545192b374b02d64b4feabf`（仅证据提交，未推送），远端`a62b48ac04e9c9fd434f9217d78679ebe1a2fa7a`；无用户WIP。父侧新增截图/正文是诊断证据，不是Actions接口许可。

原CI失败保留：run39195428530 Linux `tests/test_remote_run_api.py::test_running_png_sync_pause_resume_keeps_training_owner_and_rejects_retired_scope`断言RUNNING且syncState应pending、实际syncing；teardown ValueError REMOTE_CLEANUP_UNCONFIRMED；原摘要1failed/923passed/8skipped/1warning/1error，92.49s。不是SVG title children警告导致测试失败。Windows实际首错误为Vite transformed767modules后MISSING_EXPORT：SnapshotCode不由src/RunSnapshot.ts导出，RunDashboard的./RunSnapshot.js导入失败，exit1。当前Linux本地全绿不能抹掉这两项CI FAIL。

根因及最小修复：
- 产品 `_sync` 先发布artifactSync.paused，随后另一次发布syncState.pending，API可观察两字段不一致。`_sync_progress`现于同RunService ledger锁内将活动syncing→pending与paused一并提交，保持status_changed journal/views/persist；迟到暂停不降级已提交的complete/error。`_sync`最初syncing发布也在gate内检查当前owner/paused/stop，避免迟到启动覆盖暂停。不引入core checkpoint锁反转，不放宽清理确认、session物理静止、身份/训练取消门。
- 测试不是改宽断言：真实SftpArtifactSync在异常后join实际owned worker并确认quiescent，强制“传输已清理→发布暂停”的合法调度；worker在paused发布后被Event屏障保持，API严格读paused/pending。旧产品确定复现1FAIL（1.46s）。测试原先断言失败绕过resume_return.set，4秒等待超过close3秒预算，诱发附带cleanup ERROR；最外层finally现无条件释放全部Event，原清理门不改。新增迟到paused针对complete/error的低层回调回归，明确不冒充真实成功训练。
- Windows case-insensitive路径把RunSnapshot.tsx与runSnapshot.ts在.js→.ts/.tsx扩展名替换时混淆；真正SnapshotCode在.tsx中。仅将组件重命名RunSnapshotCode.tsx并更新生产/类型/测试3处引用，纯模型runSnapshot.ts保留。未改Vite解析/屏蔽导出错误；前后casefold+stem静态比较确认基线冲突、最终无冲突。

命令与证据（cwd /workspace/Easy-AI）：
- PASS：原单用例`services/backend/.venv/bin/pytest -q services/backend/tests/test_remote_run_api.py::test_running_png_sync_pause_resume_keeps_training_owner_and_rejects_retired_scope`，原时序本地1PASS/2.71s；只前移retired屏障也1PASS/2.79s，未当复现。加入实际worker join确认后同命令 **FAIL 1failed/1warning/1.46s**，精确syncing!=pending，无teardown ERROR；日志分别保留。
- PASS（首次产品修复、终态独审补强前）：`services/backend/.venv/bin/pytest -q services/backend/tests/test_remote_run_api.py`，19PASS/14.75s。独审指出通用paused→pending会降级终态P2，已修为仅syncing→pending并加complete/error回归后再跑完整测试；不以首轮通过代替最终结果。
- PASS：`CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache UV_CACHE_DIR=/workspace/.uv-cache UV_OFFLINE=1 pnpm check`，TS/合同/fixtures/Ruff/格式/mypy66文件/Prettier；最后终态guard微调后又实际`ruff check`及`ruff format --check`两修改Python文件PASS。
- PASS：`CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache pnpm exec vitest run apps/desktop/src/RunSnapshot.test.mts apps/desktop/src/FigureInspector.test.mts`，67PASS/3.37s。
- PASS：`CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache pnpm --filter @easyai/desktop build`，exit0，767模块，Vite1.31s，保留chunk>500KiB警告；这是Linux开发构建，不是Windows或新打包验收。
- PASS：Python pathlib/defaultdict与git ls-tree HEAD的casefold/stem比较，原RunSnapshot.tsx/runSnapshot.ts冲突，最终源树无同stem冲突。`git diff --check`PASS。

独立只读review已确认真实双状态窗口及测试屏障遗漏；终态P2修复后复核无剩余明确P1/P2，保持journal/persist与锁序，无新增权限/脚本许可。最终全量测试结果随后补记。正常推送开发分支一次（连同此前未推证据提交），仅让既有push工作流验证实质修复；不workflow_dispatch/重跑/读取被拒接口。当前Windows新结果仍NOT RUN/待父侧核实，不能标PASS。NOT RUN：真实SSH/训练/数据/受控安装、新builder包/发布；CIFAR限制未变，Windows生产storage门未开放。main无写入。

最终PASS：`CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache UV_CACHE_DIR=/workspace/.uv-cache UV_OFFLINE=1 pnpm test`，exit0；334前端PASS/2skip，924后端PASS/8skip/1warning（74.14s），20包保护PASS（864ms）。67定向UI与334全量重叠，不累加。警告保留，未增加skip或放松原断言。完整日志SHA256：
- `/tmp/easyai-sync-race-before-20261019.log`：`2d927b52450262347dd67a5cf24ce3dcf8e4db0a016fdf01bd20b53e0b75e6fb`。
- `/tmp/easyai-sync-race-barrier-before-20261019.log`：`46c2fe42034044cf220a914a34a8d8b004250cd5814c09e7ed64458e67134ceb`。
- `/tmp/easyai-sync-race-deterministic-before-20261019.log`：`c46087728a85664bd9e1719eb7bd6cedb0369555edc66bf6610344da8b5800b8`。
- `/tmp/easyai-sync-race-after-20261019.log`：`aa797140827a5a8bc0d4665d0ec155902bcecd0b26d0addf7ccdc7315c427657`。
- `/tmp/easyai-dual-ci-casefold-20261019.log`：`5c8450ed6f9cc774024cd6a718d9afd909a7198917eef0c3e0b411a9cdeab85c`。
- `/tmp/easyai-dual-ci-check-20261019.log`：`33d638c44f61709c5fea38251066696a5a89ca3d3d4d8bf8ffb532d282f23af2`。
- `/tmp/easyai-dual-ci-ui-20261019.log`：`1bbc5b31e22715f141c2e9882fa880e568e8d54c5fc5f5106a523c6a84b9cd57`。
- `/tmp/easyai-dual-ci-build-20261019.log`：`32c6cbe3fc5b20614e99270341403d2b8d38135f7110d39a99a7c80d2ab9e0a1`。
- `/tmp/easyai-dual-ci-fulltest-20261019.log`：`58239ec7aad70ce548bd1a1ccbf4da69949b796a5b632e8c89ca8128ad15fdda`。

预提交原件校验PASS：plan仍116185字节/SHA256 dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43；README与旧规格未改。仅正常提交推送codex/demo-v0.0.0，最终完整SHA/远端clean/main核对由最终回报提供；新CI由父侧既有合法渠道核实，本线程不读取被拒接口。

## 2026-10-19 Windows E2E入口有界排查（本地证据与确定断言修正，未推送）

父侧已通过允许的run/jobs元数据核实run39198400814：Windows安装、后端前置、desktop build全部PASS；pnpm test:e2e FAIL。Linux pnpm test PASS，build当时运行中，最终结果本线程未知。旧两处确定问题已解，不将新E2E FAIL归因于旧窗口或模块解析；完整B仍未验。

起始HEAD/远端均`62c0b4cc137201b3b6b791474bb5c7e100d61731`，工作区clean，单一写入者，main仍`5323f86232529efcfb52131168ad049f01b219f3`。只读检查playwright.config.ts、startup.spec、preload、Main/backend/backendLocation、setup和CI入口。E2E无globalSetup/webServer/fixed-port；backend绑定127.0.0.1:0，Main开发路径按here解析仓库、Windows使用.venv/Scripts/python.exe；真实启动必须保留sandbox、受控协议、Main stdin token及EOF关闭。未找到可确定的端口或Windows路径缺陷，不凭推测改动。

确定独立问题：`tests/e2e/startup.spec.ts`精确桥接键名仍是旧7项，真实preload已含dataTransfers/packages共9项。仅期望数组增加这两项，保留精确toEqual、node=require不可见、sandbox=true、无--no-sandbox和正常关闭；不扩大产品权限或放宽断言。当前Windows首次失败是否在此处仍UNKNOWN，可能更早；不声称修复已使E2E通过。

实际非GUI验证（cwd /workspace/Easy-AI）：
- 首审计工具FAIL：`node /tmp/easyai-e2e-bridge-audit-20261019.cjs`尝试旧TypeScript API绝对目录require，TypeScript7包无该入口，MODULE_NOT_FOUND；工具错误日志保留，未下载/换依赖。改用已有实际tsc输出preload.cjs，不再依赖此API。
- 确定基线FAIL：`node /tmp/easyai-e2e-bridge-audit-v2-20261019.cjs baseline`，VM执行实际编译preload，只模拟contextBridge注册；所有IPC调用立即抛错，未调用IPC。git show HEAD取旧断言，实际9项/期望7项，exit1。
- PASS：同脚本无baseline参数，当前精确9项期望与实际9项顺序相同；没有启动Electron/浏览器，不能代替真实contextIsolation/sandbox断言。
- PASS：`CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache pnpm exec playwright test --list`，仅枚举1项测试，无launch；`node node_modules/typescript/bin/tsc --noEmit -p tsconfig.tests.json`，exit0。
- PASS：`CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache UV_CACHE_DIR=/workspace/.uv-cache UV_OFFLINE=1 pnpm exec vitest run apps/desktop/electron/backend.test.mts apps/desktop/electron/backend-location.test.mts apps/desktop/electron/security.test.mts`，14PASS/1.05s，仅既有非GUI准备测试；真实Python后端stdio/health/EOF，平台路径单元及安全配置，不代表Windows。
- PASS：`git diff --check`；独立只读review无新增P1/P2，确认真实9项及安全断言保留，建议待首错误后再决定push。

NOT RUN：Electron/浏览器GUI、pnpm test:e2e实际执行、Windows本地复现、Actions日志接口/替代路径/重跑、新CI、新包、训练/SSH/安装。此前浏览器/sandbox与日志读取拒绝继续有效，本轮未尝试，不关闭安全门。CIFAR及真实资源授权不变。最小缺失证据为该测试首个错误块、文件/行号、expect差异或Playwright call log；若启动超时，只需launch/firstWindow/backend-status对应错误段，不要求全部日志或新权限。

将这项确定修正及证据本地提交，暂不push，避免尚无本次首错误依据时触发CI。下一项按新正文确定剩余失败位置，保留修复接续同一开发分支；最终回报列本地SHA与未推送差异。

本轮审计脚本/日志SHA256：
- `/tmp/easyai-e2e-bridge-after-20261019.log`：`2aea6024e358a2d95abb1127a0588c2e0078da215beb11e1dfcce32d248d83bc`。
- `/tmp/easyai-e2e-bridge-after-v2-20261019.log`：`0bbbbc28f3cd6df9ad71404980e7281753a42116a958e9bcb0cd95c6712e5dc2`。
- `/tmp/easyai-e2e-bridge-before-20261019.log`：`2aea6024e358a2d95abb1127a0588c2e0078da215beb11e1dfcce32d248d83bc`。
- `/tmp/easyai-e2e-bridge-before-v2-20261019.log`：`1364bb8aee3d451f0dc0cd2f56f35a9b5fb510a14973b688c9d7cc8418a57801`。
- `/tmp/easyai-e2e-list-20261019.log`：`aacdfced54ed9c95893c2f0e21f8051496396435bacea53735758249369a0cb1`。
- `/tmp/easyai-e2e-preparation-20261019.log`：`432353d7e5b517268e2728b00a48aae0739752427bf2ee0526c14847fe11c6d7`。
- `/tmp/easyai-e2e-tscheck-20261019.log`：`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。
- `/tmp/easyai-e2e-bridge-audit-20261019.cjs`：`1296f08835399f6f357c021c23b837857e2ac68420376db9ddc373e7cabef0ae`。
- `/tmp/easyai-e2e-bridge-audit-v2-20261019.cjs`：`56b3e04e475aee5ecfbf789993e641ffdf2dee2d9ff4adf29b42f96d55d9a8ac`。

## 2026-10-19 明确正文后的 Main ready 环及 fresh-resume owner 等待修复

起始本地/远端均`547f3428feb5797d39524a6262329e14b74371de`，工作区clean，单一写入者；main仍`5323f86232529efcfb52131168ad049f01b219f3`。指定保存环境恢复ready后继续，未新建写入者或覆盖已有工作。

输入证据及关联边界：用户Windows正文确认startup.spec第5行electron.launch 15000ms超时，Electron44.9.0 PID1940已启动、Node inspector listening/connected/attached，没有到九项bridge断言；未附runId，不归到特定run。父侧Linux文本附件明确test_consumed_start_lost_ack_explicit_fresh_resume_never_restarts：unknown/disconnected公开后fresh resume 422REMOTE_RUN_BUSY（应202）；原1FAIL/923PASS/8skip/1warning/86.32s，与上一paused/syncing用例不同。当前允许的GitHub jobs元数据独立确认run39198968754两个job分别在pnpm test及test:e2e失败；步骤结果不等于正文归属。没有访问此前被拒日志接口或替代路径。

实现及因果详见docs/startup-ready-and-resume-fences.md：固定官方Electron44.9.0 init→appCodeLoaded→NodeBindings.JoinAppCode→后续原生CDP handler，与本机Playwright1.64.1 loader延后ready形成等待环；Main顶层await改为非阻塞调用异步startDesktop。ready前scheme/single-instance保留；窗口、Main IPC sender、安全偏好、sidecar、退出清理主体保留。固定脱敏phase日志和通用失败对话框，无自动退出、延长timeout、--no-sandbox、版本变更或跳过E2E。scripts/main-bootstrap-probe.mjs及main-bootstrap.test.mts只用于非GUI模块顺序回归：实际临时编译Main+真实pinnedPW loader+显式nativeReady/backendReady屏障，不冒充Electron/Windows真实安全结果。

Linux在LocalWorkspace.resume_remote初核后，释放workspace锁调用已有wait_worker_exit（默认最多3秒）；再核require_run/currentproject/runner/settled，重新取manager，由原begin核当前认证与thread/retiring/physical静止/freshlease/identity门，initial=False不重复start。未知状态公开不等于worker退出，未删BUSY/清理门、不主动retire/unlock、不添加sleep。确定_publish后屏障下旧代码严格422FAIL（1.08s），新4调度valid/cleanup_busy/project_changed/auth_closed严格通过：202恢复、BUSY、当前工程404RESOURCE_NOT_FOUND、无认证422均符合原错误合同；负例无inspect/start替换，start与fixture-starts仍1，最外finally释放屏障。

实际命令和中间结果（cwd /workspace/Easy-AI，FAIL全部保留）：
- FAIL：原产品+确定worker屏障的`services/backend/.venv/bin/pytest -q services/backend/tests/test_remote_run_api.py::test_consumed_start_lost_ack_explicit_fresh_resume_never_restarts`，1FAIL/1.08s，精确422REMOTE_RUN_BUSY。首轮新增4例曾2FAIL/2PASS：测试漏SessionControl导入和把工程切换原404误写422；纠正用例后4PASS/3.16s，不改产品拒绝行为。
- FAIL（确定旧顺序）：`node --experimental-vm-modules scripts/main-bootstrap-probe.mjs /workspace/Easy-AI/apps/desktop/dist-electron/main.mjs`的before2日志，未兑现ready时Main评价不完成，严格false!=true。首probe缺process.env、随后缺ready emit参数与跨realm对象prototype比较均为VM夹具问题，日志分别保留，修正夹具不改产品断言含义。
- PASS：修复后同probe（after3），入口先完成，ready前无窗口/sidecar，ready后安全window一次、sidecar一次、受控视图加载；`pnpm exec vitest run apps/desktop/electron/main-bootstrap.test.mts`（同下XDG环境），1PASS/986ms，实际tsc临时输出，未启动Electron。
- PASS：`CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache UV_CACHE_DIR=/workspace/.uv-cache UV_OFFLINE=1 pnpm check`，TS/Ruff/mypy66/合同/fixtures/Prettier；`CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache pnpm --filter @easyai/desktop build`，exit0，Linux开发构建，保留大chunk警告，不是新builder包。
- FAIL：同XDG/UV环境`pnpm test`第一轮，335个前端测试中1FAIL/334PASS/2skip，App DOM clean noncanonical export在mount的visible-tab断言为null，尚未跑后端。随后单独`pnpm exec vitest run apps/desktop/src/App.test.mts`25PASS/4.28s；未改该模块、加等待或放宽断言，首失败根因仍UNKNOWN，不因重跑通过抹除。
- FAIL：第二轮完整pnpm test前端335PASS/2skip；后端1FAIL/926PASS/8skip（77.26s），旧acceptance wait替身不接受默认seconds的TypeError。已让替身与真实签名seconds=3一致，严格断言验收助手及API两次观察为[存活,已退出]，首轮仍真实短等待BUSY/owner不换/start1，再release+join，第二次静止复核；不是跳过真实API等待。
- PASS：最终`services/backend/.venv/bin/pytest -q services/backend/tests/test_remote_run_api.py`，22PASS/15.30s，含lost-ACK四调度、暂停原子发布、验收助手二次等待。最终完整pnpm test结果随后补记，未仅跑选中用例当全量。

独立只读审查分工均已完成，保持单写入者：Windows复核固定源码环、实际Main/PW loader的非GUI回归、生命周期/脱敏错误处理与安全门；Linux复核锁外join、等待后scope/auth复核、old owner/fresh lease/start门及更新替身，均无本范围剩余明确P1/P2。未重复外部/GUI动作。

NOT RUN：本地Electron/浏览器或Windows实机E2E、真实SSH/训练/数据/受控安装/新打包；此前浏览器与日志接口拒绝未重试，未新增权限、费用、凭据、教师环境变更或CIFAR例外。测试用vm --experimental-vm-modules只用于独立Node子进程，不给Electron追加开关。下一项仅正常开发分支push一次让现有CI验证本修复；不dispatch/重跑/读取logs。完整A/B未通过。

最终完整PASS：同上XDG/UV环境第三轮`pnpm test` exit0，前端335PASS/2skip（40文件PASS/1文件skip），后端927PASS/8skip/1warning（75.51s），Node包保护20PASS（875ms）；1项新VM测试与4项参数测试已包含在全量中，不叠加计数。Linux desktop build767模块/1.81s；pnpm check PASS。此前App DOM首轮失败未改代码、根因仍UNKNOWN，后续25项及完整前端通过不追溯抹除；旧替身TypeError经匹配真实API签名与加强两次状态断言修复。

PASS：原plan116185字节及SHA256 dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43、旧规格及README字节/hash均不变；pnpm-workspace/pnpm-lock/uv.lock/package/CI未改，git diff --check PASS。预push远端仍547f3428feb5797d39524a6262329e14b74371de，main仍5323f86232529efcfb52131168ad049f01b219f3。

本轮日志与非GUI回归脚本SHA256（含夹具错误、产品复现与纠正）：
- `/tmp/easyai-main-ready-after-20261019.log`：`6368d1a666e83bcac409730cdc118f8b288b5bb0cb468f5a74ccdaf44bdc5e2c`。
- `/tmp/easyai-main-ready-after2-20261019.log`：`fb45140743c39789fd63ef7a617c91c015b9a0446e1fb2ed5ef72653aeab1a1e`。
- `/tmp/easyai-main-ready-after3-20261019.log`：`e7bc35c1fbdf239c7ce635bba41d9e3f1be773e2ac46d9f8a59d27a9191c76ca`。
- `/tmp/easyai-main-ready-before-20261019.log`：`192343e8d8a0290d9f41fc45b836aad85e68657e60430a9f65eda173da44453d`。
- `/tmp/easyai-main-ready-before2-20261019.log`：`171251168907db0250693bd1e530c037de446055a361926ba5e70184d6d4fa67`。
- `/tmp/easyai-main-ready-compile-20261019.log`：`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。
- `/tmp/easyai-main-ready-regression-20261019.log`：`d1508cf5f790bfe3bde7a1e8ca669f6db1530a6d07bdee00506232e64b9a1d65`。
- `/tmp/easyai-resume-fence-after-20261019.log`：`f022348f68d973f5451c2a8b9814dfd0c961bc9974a408305b7da71635f92054`。
- `/tmp/easyai-resume-fence-after2-20261019.log`：`dff7d2d2d5938f5841a042ae2a32c837ee02733d546b48bc077c6cb294a44fc0`。
- `/tmp/easyai-resume-fence-before-20261019.log`：`7ad5fc046cf551f70d2249f528ce9ff89b3f6a926a95db26775b6fd484e44e28`。
- `/tmp/easyai-ready-resume-api-final-20261019.log`：`bc9dce12794307d45aeb6706bf8051d260d7e766a7454a8bea0129900dafce9b`。
- `/tmp/easyai-ready-resume-app-target-20261019.log`：`d72178c1a78c91b684fdb037674aa9ea474bf7b71d834d68d68cea5305fcdb39`。
- `/tmp/easyai-ready-resume-build-20261019.log`：`b2bd1f27b61830baa5435568be00c295b9a652a52b4b2f61dd19da675b2e9aeb`。
- `/tmp/easyai-ready-resume-check-20261019.log`：`33d638c44f61709c5fea38251066696a5a89ca3d3d4d8bf8ffb532d282f23af2`。
- `/tmp/easyai-ready-resume-format-20261019.log`：`13cd11ca20573e5f4c821f82ecf4e2205618b8bec1289a3693b18b463b710388`。
- `/tmp/easyai-ready-resume-test-20261019.log`：`abaadc90aa5ba204ed877d4e13fcedb827900dc1270dfcde21219db7fc7a75f2`。
- `/tmp/easyai-ready-resume-test2-20261019.log`：`d6c5815d31f24e02209c4bf48d0ef6abcdab0c43c1372deaabfc8d2eba6622f5`。
- `/tmp/easyai-ready-resume-test3-20261019.log`：`76432fea19c300ebf22b6b17819cfbc9ad1de102a0c34e66c509dd7c0cd86170`。
- `scripts/main-bootstrap-probe.mjs`：`25bd9f6f73941df568746963b10f7a1365d1b9d579c9371f60a31aaf7d5b6115`。

所有检查后正常提交并仅push codex/demo-v0.0.0一次；自然CI及完整最终SHA由最终回报提供。新Windows实际launch/正常关闭及云Linux结果待CI，不由VM/本地PASS替代。无未授权外部调用、main/原仓库/强推/PR/Release/部署。


## 2026-10-19 Windows 应用 venv 严格 ready 身份修复

起始本地/远端开发分支均 `fb7ddb632aab5635c02bc609b46d335af5f32f6a`，工作区clean；main仍 `5323f86232529efcfb52131168ad049f01b219f3`。单一集成写入者，现有独审worker只读复核，没有覆盖用户工作。父侧新正文对应 [run39211585475](https://github.com/T1doo/Easy-AI/actions/runs/39211585475)：Linux完整SUCCESS；Windows launch/firstWindow已经成功，startup.spec.ts:12期望“本地服务已就绪。”，5000ms内13次观测为“本地服务启动协议不匹配。”。旧FAIL保留；该错误未附ready字段或类别，不把源码发现当唯一实测根因。

固定uv0.12.23/CPython3.11.14源码确认Windows venv redirector会创建继承stdio的真实解释器并等待；严格child.pid与os.getpid可能不同。详见[windows-application-python.md](windows-application-python.md)及官方源码链接。只对Main固定应用venv/-m easyai.main直接使用pyvenv.cfg home/python.exe，并以CPython的__PYVENV_LAUNCHER__保留应用venv语义；有界读取配置，要求3.11 CPython/system-site=false/绝对home，去除继承Python路径覆盖，拒绝配置异常，不回退PATH、不改训练环境。冻结--onedir入口不变。ready验证提取为可独测函数，仍精确三字段/端口/版本/实际child PID，不接纳转发PID/BOM/额外stdout；只增加固定错误类别，不输出原始stdout、路径或令牌。health鉴权、EOF清理、安全窗口/IPC门均保留。

新增实际应用prefix/base_prefix/import/PID/变量消费测试与真实继承stdio转发进程负例；Windows CI在build后E2E前执行同样非GUI测试。冻结普通及SSH smoke补上精确三字段/端口/PID断言。没有安装/下载依赖、真实训练、SSH或修改教师环境；本轮PyInstaller是现有应用依赖的独立临时--onedir后端构建，不是发布包或部署。

实际命令（cwd /workspace/Easy-AI）：
- PASS：`CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache UV_CACHE_DIR=/workspace/.uv-cache UV_OFFLINE=1 pnpm exec vitest run apps/desktop/electron/backend.test.mts apps/desktop/electron/application-python.test.mts apps/desktop/electron/backend-ready.test.mts`，最终25PASS/2.17s。Linux真实后端health/EOF与转发PID负例通过，Windows配置语义用纯函数固定输入验证，不冒充Windows实机。
- PASS：同上环境 `pnpm check`，TS/Ruff/mypy/合同/fixtures/Prettier全部通过。
- PASS：`CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache pnpm --filter @easyai/desktop build`，exit0，842ms，保留已有大chunk警告。
- PASS：`node scripts/python-task.mjs build /workspace/easyai-app-python-frozen-l4x6yi61`，16.39s，独立临时目录；随后 `node scripts/test-frozen.mjs /workspace/easyai-app-python-frozen-l4x6yi61/dist/easyai-sidecar` exit0，严格ready PID/schema/端口、鉴权、资源、工程创建/编译、离线安装计划门及EOF退出通过。Linux冻结结果不等于Windows通过，也未执行安装。
- 完整 `pnpm test` 在相同XDG/UV离线环境执行，最终结果见下补记；定向25项包含在完整前端计数中，不重复相加。

独立只读审查完成：无明确剩余P1/P2；固定应用venv选择、有界配置、case-insensitive环境清理、严格PID/鉴权/EOF、转发负例和冻结门均保留。信任已准备应用venv配置，不宣称验证任意Python。实际Windows非GUI与E2E仍须本次自然CI，Linux结果不能替代。前轮App DOM一次失败仍根因UNKNOWN，后续通过不抹除。

PASS：原plan116185字节/SHA256 dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43；旧规格21815字节/SHA256 5808fb59fb32917ef92d6a516609d51adecc8830fa1bb736222b43f1a134b190；README3629字节/SHA256 befb23b8349800a6ca578e74029b6fbbf7f038bff9672e718b848117d432d852，均未改变。锁文件/依赖/版本/生产storage门未变，git diff --check PASS。

NOT RUN：本地GUI/浏览器、Windows实机、真实SSH/训练/数据/安装、完整A/B、新builder发布包。未访问被拒Actions logs/artifacts或浏览器路径，未新增权限/费用/凭据/主分支/上游写入，无PR/Release/部署。本轮只有正常开发分支push一次及自然免费CI；最终完整提交SHA/远端一致性和新CI元数据由最终回报提供。

最终完整 `pnpm test` exit0：前端358PASS/2skip；后端927PASS/8skip/1warning（最终时长见原日志）；Node包保护20PASS。没有新增失败，不叠加定向25项。当前Windows实测结果仍NOT RUN/待CI。

本轮日志SHA256（本地证据，未提交日志内容）：
- `/tmp/easyai-app-python-target2-20261019.log`：`8c089917857eedc89e9cd7a87c2cc32a583510360f71d661c55d7a6b52c66d11`。
- `/tmp/easyai-app-python-check-20261019.log`：`33d638c44f61709c5fea38251066696a5a89ca3d3d4d8bf8ffb532d282f23af2`。
- `/tmp/easyai-app-python-build-20261019.log`：`2b7aab8b8f5f95725cef7839532eab845be2494783bcd600bf2a2eb3160c8f9f`。
- `/tmp/easyai-app-python-test-20261019.log`：`33a97a0a60c8e49eff3c4b11a40a6b22514789397a3d420bedc547d4f1b72d8a`。
- `/tmp/easyai-app-python-frozen-build-20261019.log`：`140bbeaf0d42b87696eddcc77a37bcd03c03e825bf5c7a0df9ceae7f15f04295`。
- `/tmp/easyai-app-python-frozen-test-20261019.log`：`598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。


## 2026-10-19 a4de782 真实未签名候选更新

父侧独立确认 `a4de782a5efa717868d7180eee18d60e71dfb16a` 的CI39213624352 Linux/Windows全部SUCCESS，包括真实Windows启动E2E；无明确P1/P2。接续原M8候选范围，不把CI当完整A/B。起始HEAD/远端均该SHA、工作区clean，main仍5323f86232529efcfb52131168ad049f01b219f3；核工作流仅check/build/E2E，无候选打包/upload步骤。现有最新完整v2候选仍旧5b3df8d565f75a1f5cdeaf4e2f9300ce04bee17f，因此实际构建最新候选，没有重复全量测试。

PASS实际命令（cwd /workspace/Easy-AI）：
- `CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache UV_CACHE_DIR=/workspace/.uv-cache UV_OFFLINE=1 CSC_IDENTITY_AUTO_DISCOVERY=false pnpm package:builder` exit0；原Git固定快照+offline frozen依赖+tsc/Vite/PyInstaller+electron-builder流程，实际dir/tar.gz而非README。354Node复用/下载0、新独立应用venv43包，无训练依赖；现有Electron44.9.0校验来源和7zip工具未变。
- 同XDG环境 `pnpm package:builder:verify dist/easyai-builder-a4de782a5efa-1792393988003-linux-x64` exit0；v2批准闭集、ASAR、资源、vendor完整性通过，输出296记录。
- `python /tmp/easyai_candidate_audit_20261019.py` exit0；tar294普通文件逐项bytes/mode/hash/集合相同，无link/special/越界/重复；受限秘密特征扫描294unpacked文件零命中（非任意秘密保证/PYZ未解包）；实际Analysis-00.toc核64easyai源均在固定快照、7namespace占位符，应用依赖清单无torch/torchvision/tensorflow。
- `node scripts/test-frozen.mjs dist/easyai-builder-a4de782a5efa-1792393988003-linux-x64/artifacts/linux-unpacked/resources/backend` exit0；包内真实sidecar严格ready PID/schema/端口、Bearer鉴权、资源/工程/黄金编译、离线计划/显式登记取消/禁执行、EOF exit0，无GUI/训练/SSH。

实际tar.gz152781550字节，SHA256 `4733c8bd71f1b32836069fa0670843c0db8b98411200feb5ce42f2306b3ee0b9`；路径、builder manifest/批准输入/source.tar/vendor/依赖锁hash和未验清单见 [candidate-a4de782.md](candidate-a4de782.md)。候选旁已有candidate-audit.json、candidate-provenance.json、candidate-handoff.md；这些收据在封存应用之外，不修改归档。初次口头计数295已纠正为审计实际294，无产物变化。全程无产品代码或依赖变更，无构建失败，原有chunk/缺author等警告保留。

NOT RUN：本包真实Electron/干净机TST33/平台安装包、正式MNIST十轮/SSH/训练环境安装/数据模型下载/签名发布部署；完整A/B不通过。法律审查/项目许可证、系统native义务与正式支持仍缺，两个ready标记保持false。已有sandbox/日志访问拒绝不重试，无新增费用/凭据/权限/教师环境操作。原计划、旧规格、README及锁hash均未变。只追加证据提交于开发分支本地，不为文档再push触发一轮完整CI；最终HEAD/远端差异、独审结论和日志hash随后补记。

独立只读审查PASS：独立verify296记录、tar294文件全项bytes/hash/mode/集合通过；558个tracked Git archive文件与固定提交逐字匹配，无本范围明确P1/P2。审查不重建/联网/GUI/SSH/训练。证据日志SHA256：
- `/tmp/easyai-candidate-a4de782-build-20261019.log`：`9c7c6934774d042da433c969abe95703c1c36c96b5b9e6b699e64488cb5a89c3`。
- `/tmp/easyai-candidate-a4de782-verify-20261019.log`：`bc62fb43d72d7e5da9314449e1793a335d43ff538fbb6e927a16f88e0ca49170`。
- `/tmp/easyai-candidate-a4de782-audit-20261019.log`：`2e4bea775c013b02ed72aecf7fffb055816a1a325fb793783eaf61f534dd6c6d`。
- `/tmp/easyai-candidate-a4de782-frozen-20261019.log`：`598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。
- `/tmp/easyai-candidate-a4de782-independent-verify-gKAuKP.log`：`2bcb392594d0486dfbe8cda08816af01c90eb71da8c6c17f80e1f27a4390e864`。

本轮证据本地提交，不push：候选产品源码/远端保持a4de782a5efa717868d7180eee18d60e71dfb16a；证据HEAD完整SHA和clean核对由最终回报给出。后续可随实质工作统一推送，不额外触发CI。


## 2026-10-19 接续原计划：Windows x64 未签名候选与包内安全启动

父级要求实际接续，不把真实数据/SSH/干净机缺失当全部开发终点。恢复指定环境后起始HEAD `b05a375eb490c6c69828cbbb03fca3a5cc34b3f4`，远端 `a4de782a5efa717868d7180eee18d60e71dfb16a`，工作区clean；原a4de782 Linux真实候选及b05证据保留，main仍 `5323f86232529efcfb52131168ad049f01b219f3`。核原plan§4/§18 M8.2与真实代码发现builder仅Linux，Windows CI只有开发态启动，尚无Windows候选。因此承接该明确原产品欠项，不新增外围需求，不宣称训练验收通过。

实现见[windows-candidate.md](windows-candidate.md)：原same-host Git archive/clean/HEAD、offline/frozen依赖、新应用venv/PyInstaller --onedir和五组批准输入不变，Windows x64新增dir+ZIP，无安装器。Windows pnpm使用官方action已登记PNPM_HOME下固定11.25.0 JS入口和Node argv/shell:false；错版本或入口拒绝。保留默认ASAR integrity：发现锁定builder即使signAndEditExecutable=false仍先写PE；不关完整性，而从封存原始input/vendor/electron.exe核bytes/mode/hash后在独立temp重放唯一已知integrity变换，严格比较EXE全字节与其余vendor闭集，拒绝输出inventory自行批准。Linux原路线/模式门保留。

ZIP/tar标准库审计只读精确集合/大小/hash，Windows核readonly而非伪称POSIX exec位；拒绝盘符/ADS/反斜杠/越界/设备名/末尾点空格/大小写别名/重复/links/special/加密/额外目录。有限秘密特征零命中不等于任意秘密/PYZ/native安全。CI原Windows开发检查保留，新增包保护→实际打包→ZIP审计→包内PID/auth/resource/EOF→同sandbox/原timeout的packaged Electron E2E（严格app.isPackaged+ASAR），再只上传ZIP与三收据、retention1day/450MiB上限、不上传source/input/venv/数据。完整PE verifier所需原始vendor不在短期上传中，此限制明确披露。发布/许可ready均false，不接受新条款/付费/签名材料。

实际命令（cwd /workspace/Easy-AI；没有为数字重跑完整套件）：
- PASS：`CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache node --test scripts/package-builder.test.mjs`，8项/1.10s，实际合成PE保留默认integrity、严格接受唯一重放/拒任意EXE变化和篡改原始vendor；不是Windows实机。
- PASS：同XDG环境 `pnpm test:package` 第一轮25项/1.03s，最终ZIP设备名/目录类型门和输出cap补充后第二轮25项/1.08s；其中一个Node入口运行6组Python标准库ZIP负例，不重复累加为总数。Windows已有Linux-only portable旧测试仍按原scope，不跳过新候选关键门。
- PASS：`CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache UV_CACHE_DIR=/workspace/.uv-cache UV_OFFLINE=1 pnpm check`，TS/Ruff/mypy66/合同/fixtures/Prettier。新增脚本另做`ruff check/format --config services/backend/pyproject.toml scripts/verify-candidate-archive.py scripts/test-candidate-archive.py`，无错误；Node语法与既有js-yaml实际解析workflow均通过。
- PASS：`services/backend/.venv/bin/python -I -` 加runpy只读加载新audit函数核旧a4de782候选，294文件及归档SHA256 `4733c8bd71f1b32836069fa0670843c0db8b98411200feb5ce42f2306b3ee0b9`保持。未提取/重建/覆盖旧包。
- PASS：独立只读四组包保护25项（与上述重叠不累加），复核PE、固定pnpm、ZIP、CI上传、packaged sandbox/timeout，无本范围明确剩余P1/P2。未联网/同步依赖/构建/Windows/GUI/训练/SSH。

本地NOT RUN：新的Windows实际包、packaged GUI；必须等自然CI的实际结果。未重试此前拒绝的日志/浏览器接口；父级现可自行读取新CI正文，本线程仅允许的run/jobs元数据观察。没有数据/模型下载、训练环境/教师共享环境改动、真实SSH/训练、发布/上架/签名/PR/Release/主分支写入。完整A/B仍未通过；主路径正式训练与SSH所缺最小条件仍在release-checklist，独立M8候选工作不冒充它们。

本轮日志SHA256：
- `/tmp/easyai-win-candidate-builder-test-20261019.log`：`8333a4249a7918b6684597b2981f8ca2347fea196aaa0bfc35c52215315a8c44`。
- `/tmp/easyai-win-candidate-package-test-20261019.log`：`8820924ec3e52d3420f99dc3d3a4634b0e5f47983dea8f98fcf032d1865426ee`。
- `/tmp/easyai-win-candidate-package-test2-20261019.log`：`282a1c0dcebaaea3b5083e6d3d0e1ca677303f00f69694bf34400a63f574c0c4`。
- `/tmp/easyai-win-candidate-check-20261019.log`：`33d638c44f61709c5fea38251066696a5a89ca3d3d4d8bf8ffb532d282f23af2`。
- `/tmp/easyai-win-candidate-review-cDGEKB.log`：`8705dcbd50d05b5fa63284cd8f8141a31850f34fc23ea97190a6fc13df7c5f66`。

最终完整SHA、正常dev push和自然免费CI/真实候选结果由最终回报补记；仅一次本实质功能CI，不主动dispatch/重跑。


本轮真实CI结果补记：正常提交/推送产品 `ca184beffeb5850adea499e08fb50619d6b01bc7`（含保留的b05证据），[run39221894722](https://github.com/T1doo/Easy-AI/actions/runs/39221894722) **Linux check SUCCESS / Windows desktop FAIL**。Windows原开发态startup E2E及前置native/frozen/venv检查成功；新增 `Packaging input and archive guards`（实际 `pnpm test:package`）FAIL，随后Windows实际构建、ZIP审计、包内sidecar、packaged Electron及artifact上传均SKIPPED。因此本轮尚无Windows候选，不能把已接线或本地25PASS当产物成功；原Linux a4de候选继续有效保留。

准确阻断：需要父级在已登录GitHub浏览器读取该步骤首个失败测试名、error/cause和首个堆栈（包括是否hookFailed/EPERM/EBUSY）。当前仅run/jobs元数据，无正文，根因UNKNOWN。独审再次只读复核无可从源码确定的Windows-only问题；ASAR读取try/finally关闭fd，没有证据归因句柄缓存；旧Linux-only六项按原scope跳过，不跳新Windows门。没有猜测修复、放宽/跳过保护或重跑CI，也不访问此前被拒logs/artifacts接口；父级可读正文，无需用户再搬。该阻断是实际Windows保护失败，不是真实训练/SSH缺资源；正文到达后接续精确修复并验证。此补记仅本地证据提交不再push触发CI，最终SHA/remote/clean由回报给出。


## 2026-10-19 Windows ASAR native分隔符确定修复（接续同一候选任务）

首错误正文仍未取得，但独审随后从固定ASAR3.4.1的lib/filesystem.js:listFiles确认确定P2：native path.join在Windows输出\dist\index.html；原builder入口检查要求/dist/index.html，后续隐私regex和批准集合也只识别正斜杠。这是源码证实且可独立修复的缺陷，不继续把“缺正文”当所有开发终点，也不声称它就是CI39221894722唯一/首个实测错误。保留刚提交的964c257证据，不回写旧FAIL。

新增实际ASAR fixture回归，只将锁定库listPackage的输出变为Windows分隔符形态，其余生产verifier、真实ASAR读字节不替换；要求合法包通过且dist/.env.local仍拒绝。旧代码 `node --test scripts/package-builder.test.mjs` 精确8PASS/1FAIL，BUILDER_ASAR_ENTRY_MISSING。随后仅在两个listPackage输出边界replaceAll反斜杠为/，保留所有入口、隐私、特殊ASAR、集合和字节断言。

PASS：`CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache pnpm test:package` 26项/1.17s。独立直接`node --test scripts/package.test.mjs scripts/package-builder.test.mjs scripts/package-inputs.test.mjs scripts/candidate-archive.test.mjs` 26PASS，P2复核关闭，无放宽安全门。独审首次`pnpm test:package`未设工作区XDG，pnpm自动状态修复试图创建/home/agent/.local/share/pnpm而ENOENT，未进入测试、未执行安装；停止该路径而直接运行同一Node脚本，原失败单独保留。并非Windows产品错误或全套测试结果。Prettier和git diff --check PASS，未改依赖/应用/协议/训练/SSH/旧候选。

本次是明确缺陷修复后的新源码正常push/自然CI，不是重跑旧run或为了数字重复全套。本地不具Windows执行条件，新的实际Windows候选结果仍须该新CI；当前本地仅四文件证据补记和两核心/测试文件改动，无用户WIP覆盖。
- `/tmp/easyai-win-asar-before-20261019.log`：`2de8446341a81a7502065167944bda168c3fededfe7ae073119bd4728d094dd9`。
- `/tmp/easyai-win-asar-after-20261019.log`：`21b9e1134ab24a4e4400a7eab7155017262f577f1c27184b2539e7584ed8fc8f`。
- `/tmp/easyai-win-asar-independent-20261019-unique1.log`：`a164a71af9b231bfdda437823abe01d11476b128be0f1036c3d3076472abdf8e`。
- `/tmp/easyai-win-asar-independent-20261019-unique2.log`：`e6c6d8163425b1ca96b8beed707fd66ab3f7df107e2513eff0e1e4d3478d6705`。


修复后的真实Windows结果：产品提交 `da5a1af18afd4115bf072273cc2b012a65cbee7e` 已正常推送，远端与产品SHA一致。[run39222623389](https://github.com/T1doo/Easy-AI/actions/runs/39222623389) **Linux check SUCCESS；Windows Packaging input and archive guards SUCCESS**，证明分隔符修复在实际Windows测试有效。随后 **Build unsigned Windows candidate (never publish) FAIL**，ZIP审计/包内PID与EOF/packaged Electron/上传全部SKIPPED；仍无已验证可下载Windows候选。旧run39221894722保护FAIL原样保留，不改写为通过。

当前准确阻断是该Windows构建步骤的首个异常/cause/堆栈缺失，构建失败原因UNKNOWN；不是训练环境或SSH条件。需父级通过其已登录GitHub浏览器读取该精确步骤，本执行器没有重试被拒logs/artifacts接口、没有重新跑失败run或猜测改门。独立已完成打包产品接线、26项保护/独审和真实Windows保护通过，下一项据构建正文做最小修复后完成实际候选，不将本段当开发完成。无新增训练环境/数据/SSH/费用/许可/签名/权限；旧Linux候选、b05证据、main及三原件保留。此结果补记仅本地提交，不为文档触发CI；最终HEAD/远端差异在回报提供。


## 2026-10-19 父级构建正文后：精确分发归档与嵌套runtime ZIP

起始HEAD `a3a09536154e725b016a666f4cb52c51923941c5`（未推证据，保全），远端产品 `da5a1af18afd4115bf072273cc2b012a65cbee7e`、工作区clean，单一写入者。父级授权已登录浏览器实际正文来自 https://github.com/T1doo/Easy-AI/actions/runs/39222623389/job/117961261322#step:16:244 ：PyInstaller COLLECT完成；builder26.15.3 Windows10.0.26100 win32/x64 Electron44.9.0，ASAR integrity成功，资源编辑/签名按配置跳过，building ZIP easyai-0.0.0-win-x64.zip、7zip-win-x64.tar.gz下载完成后，verifyBuilder:138抛BUILDER_ARCHIVE_MISSING。该错误本身不证明物理文件缺失或名字错；未读取被拒logs接口。

源码确认Node verifier与Python archive audit均对递归inventory endsWith('.zip')计数。PyInstaller实际后端自带_internal/base_library.zip（本地真实a4de候选已只读核到），即便顶层分发ZIP存在也length2误拒。给现有Windows真实ASAR/PE fixture加封存的base_library.zip、Python加同型真实ZIP成员fixture后，旧pnpm test:package确定23PASS/3FAIL，Node BUILDER_ARCHIVE_MISSING及Python CANDIDATE_ARCHIVE_MISSING。此确定复现不冒充原run磁盘inventory已取得。

最小修复：只在artifacts顶层选择分发.zip/.tar.gz，并严格要求唯一且精确匹配同一artifactName配置代入version/os/arch/ext（Windows builder os为win，Node平台为win32）；版本拒绝路径注入。Python审计同范围/名字。其余输出inventory、封存五组、PE重放、ASAR、路径/私密文件、readonly/mode、归档内容字节检查不变；nested ZIP不是豁免，仍是批准backend及外层归档必须逐字节相等的成员。新增missing/misnamed/额外同平台/异平台root档拒绝，以及更新输出inventory仍不能批准篡改base_library.zip；包构建增加打印builder实际返回artifact paths，不用猜文件路径或采用输出自证。

实际命令（cwd /workspace/Easy-AI）：
- FAIL（旧代码确定复现，原件保留）：`CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache pnpm test:package`，23PASS/3FAIL，非真实Windows运行。
- PASS（修复后）：同命令32PASS/1.60s；Node 32中一个入口运行Python8组标准库归档用例，不重复累加。无真实训练/安装或GUI。
- PASS：`services/backend/.venv/bin/ruff check/format --config services/backend/pyproject.toml scripts/verify-candidate-archive.py scripts/test-candidate-archive.py`；Prettier，git diff --check。
- PASS：独立四组Node保护32项，复核精确root命名、nested ZIP不豁免、负向拒绝和Linux命名兼容，无新增明确P1/P2；不构建/联网/GUI/写仓库。
- 真实旧Linux候选的新verifier及archive audit只读回归正在完成，结果下补记；不重建/覆盖旧包。

保全原件、b05/a3证据和已有a4de Linux候选；不更改main、依赖/版本/签名材料/凭据/系统权限/发布或费用，不训练/SSH/数据模型下载/训练环境安装。下一项正常开发分支push一次新修复自然免费CI；只有Windows实际候选与包内smoke成功才标完成。旧两次CI FAIL保留，不改为PASS、不rerun旧run、不凭本地32项冒充Windows。完整A/B仍未通过。

本轮日志SHA256：
- `/tmp/easyai-root-archive-before-20261019.log`：`c5f1b74480a6669cc885c187916658432b0869990be2ca7f34b0268720dddc7b`。
- `/tmp/easyai-root-archive-after-20261019.log`：`0fa7eaf0b8d0364828f7979b6c206b47c05004db371ac90c1f68e10a329e75f6`。
- `/tmp/easyai-root-archive-independent-1CpHxH.log`：`d1ea5f0872876d279b0b26775963c14077ac687835ac3bbcb6910fb35e8f83b1`。

PASS补记：`node scripts/package-builder.mjs --verify dist/easyai-builder-a4de782a5efa-1792393988003-linux-x64` exit0，296记录；固定应用Python -I/runpy加载audit函数只读核同目录exit0，294文件、原归档SHA256 4733c8bd71f1b32836069fa0670843c0db8b98411200feb5ce42f2306b3ee0b9 保持。`pnpm format:check` exit0。
- `/tmp/easyai-root-archive-linux-verify-20261019.log`：`2bcb392594d0486dfbe8cda08816af01c90eb71da8c6c17f80e1f27a4390e864`。
- `/tmp/easyai-root-archive-linux-audit-20261019.log`：`900b34fb1aaeecdce5d7030683d4ff3d1d77397664bfaef75a46a8229872e8e5`。
- `/tmp/easyai-root-archive-format-check-20261019.log`：`cbe9f0d2d90255e8d0e75efb8b65eb31c9f56a6a2fd881e2245b07403e38967f`。


实际新CI补记：修复提交/远端 `a5a958657e60fe14ac6150d6b568e0c45479c3e9`，[run39223971924](https://github.com/T1doo/Easy-AI/actions/runs/39223971924) Linux check SUCCESS、Windows Packaging input and archive guards SUCCESS，但Build unsigned Windows candidate (never publish)仍FAIL；ZIP审计/包内sidecar/packaged Electron/上传SKIPPED。本地/独审32项与实际Windows保护通过不证明候选构建成功，仍无已验证可下载Windows候选。

本执行器只读取允许的run/jobs元数据，无本次异常正文，不能沿用上一轮BUILDER_ARCHIVE_MISSING或宣称同因。父级需在其已登录GitHub浏览器读取该新run构建步骤的首error/cause/stack、前约20行阶段输出及新增EASYAI_BUILDER_REPORTED_ARTIFACTS真实返回路径。没有重试被拒logs/artifacts接口，也不再猜测修复或触发CI。先前已保留a3证据；本补记仅本地提交不push，remote仍a5a9586，main/原件/旧Linux候选和所有路径/私密文件/精确内容门不变。实际构建失败已确认，根因UNKNOWN，不是待授权/不确定执行；Windows候选与包内smoke均未标完成。下一步据新正文继续最小修复。


## 2026-10-19 父级新正文后：统一 ASAR native query 边界

起始HEAD `ae1df8ed80ecb2f0a36e7217088c0e96656ca8f5`（本地证据提交保全），远端 `a5a958657e60fe14ac6150d6b568e0c45479c3e9`，工作区clean。父级从已登录浏览器取得本轮首错：https://github.com/T1doo/Easy-AI/actions/runs/39223971924/job/117965651073#step:16:248 ：builder实际返回唯一ZIP路径easyai-0.0.0-win-x64.zip，PE临时expected.exe完整性更新后，statFile('dist/assets/ProjectEditor-BMohPCML.css') not found at verifyApprovedOutput:263。已越过旧ZIP选择，不能再归因归档缺失；本执行器未读被拒日志接口。

固定ASAR3.4.1源码确认statFile/extractFile直接调用getFile，不先normalize。Filesystem.getNode用native dirname，然后按path.sep切目录；Windows dirname('dist/assets/file.css')保留'/'，split('\\')把dist/assets当成单个键。旧fixture只有dist/index.html单层目录，未暴露查找语义。新增真实ASAR内nested CSS/worker夹具，并模拟锁定库native list/dirname/split查询（实际字节仍由库读取）。旧产品确定15PASS/1FAIL，nested worker not found at同一stat/closure调用。初版模拟全局normalize把绝对实体路径变成Windows路径而夹具ENOENT；已保留其日志，修模拟仅relative member queries、用captured原normalize保持实体路径在宿主可读，再取得上述有效旧代码复现，不冒充产品错误。

实现为一处小reader：list输出规范/供隐私/入口/集合策略；stat/read调用前用native path.normalize，显式followLinks:false，实体archive路径不变。全部六处用途（两次列表、元数据、闭集stat、批准字节、stale-app读）统一走该边界；不针对某个CSS路径补丁、不先失败再兜底查找、不忽略缺文件，也不改PE、ZIP命名/成员/hash/私密路径/readonly及其他保护。

实际命令（cwd /workspace/Easy-AI）：
- FAIL（有效旧产品复现）：`CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache node --test scripts/package-builder.test.mjs` before2，15PASS/1FAIL，精确nested-member not found；before1为上述夹具绝对路径错误，单独保留。
- PASS：同XDG环境 `pnpm test:package`，33PASS/1.89s，含真实nested读取、private拒绝、真实缺失成员拒绝、重建ASAR且刷新outer inventory仍拒绝CSS bytes篡改；断言stat/read均使用native member且followLinks:false。Python8组由其中一个Node入口运行，不重复累加。
- PASS：独立四组Node保护33项，review确认全部六处读统一、实体路径无变化，Windows模拟保留host normalize；无新增明确阻断P1/P2。未构建/联网/GUI/改文件。
- PASS：`node scripts/package-builder.mjs --verify dist/easyai-builder-a4de782a5efa-1792393988003-linux-x64`，296记录，原Linux候选archive SHA256 4733c8bd71f1b32836069fa0670843c0db8b98411200feb5ce42f2306b3ee0b9 保持。`pnpm format:check`、git diff --check PASS。

旧两次Windows FAIL保留；真实Windows候选和packaged smoke必须等本修复正常开发分支push一次自然免费CI。没有重跑旧run/全套数字测试，无main/force/发布/权限/凭据/许可/费用变更，无训练环境/数据模型/SSH/教师环境操作。旧Linux候选及所有未推证据保全，完整A/B不通过。最终SHA/remote/CI结果由回报补记。

本轮日志SHA256：
- `/tmp/easyai-asar-native-query-before-20261019.log`：`116b3142fdcd3bfd3d6ac5b652cc9267aed7f1c0131bb5d51254a330bc0ab1e6`。
- `/tmp/easyai-asar-native-query-before2-20261019.log`：`5a1d6709aa09130be5051ce26146ae774b3e6bb565189925d8c00c68458ae686`。
- `/tmp/easyai-asar-native-query-after-20261019.log`：`24c42d5b0cec9bb352f6095ce012890a052f7a2cad0da6e86a33370270b8b8e0`。
- `/tmp/easyai-asar-native-query-linux-verify-20261019.log`：`2bcb392594d0486dfbe8cda08816af01c90eb71da8c6c17f80e1f27a4390e864`。
- `/tmp/easyai-asar-native-query-format-check-20261019.log`：`cbe9f0d2d90255e8d0e75efb8b65eb31c9f56a6a2fd881e2245b07403e38967f`。
- `/tmp/easyai-asar-reader-independent-tcpe16.log`：`b11d27d3044f8b5774b159720e0a91ee9aaac2d0fdf838c2d46e13889db8d65f`。


## 2026-10-19 Windows 同对象 path 别名的测试模拟器修复

产品reader修复已推 `4c60e0554f7132ea833dbd3e6a9a63e8b9d47e63`，[run39225391404](https://github.com/T1doo/Easy-AI/actions/runs/39225391404) Linux SUCCESS，Windows在Packaging input and archive guards FAIL，尚未到构建。没有新首错正文，不宣称unique根因；本线程没有读被拒logs接口。

发现我新增模拟器的确定Windows-only缺陷：默认path对象即path.win32，覆盖path.normalize后再调用path.win32.normalize会递归。用实际path.win32同一对象在Linux独立复现旧shim RangeError（不把它冒充CI正文）。只改测试helper：覆盖前capture两个原函数，实体绝对路径用原hostNormalize，相对member用captured windowsNormalize；新增default/win32同对象回归，既核relative nested路径，也核绝对C:路径。产品candidateAsar代码、所有正负测试含缺失/private/bytes、PE/归档和sandbox门均不变，不跳测试，也不针对某个CSS特殊处理。

PASS：工作区XDG环境 `pnpm test:package`，34项/1.74s；独立直接四文件Node同34PASS，复核Windowsalias及stat/read代理原宿主normalize，未发现新增明确P1/P2。Prettier、git diff --check PASS。没有本地构建/GUI/Windows实机/数据/训练/SSH/依赖变更。该真实平台模拟器修复后正常新提交/自然CI一次，非重跑旧run或盲重试；实际Windows候选与packaged smoke仍须新结果。旧FAIL继续保留。
- `/tmp/easyai-asar-fixture-alias-before-20261019.log`：`b71e42736d2e9f6e9def7369d2af2ebd0a0e5679f3cf7ec749ebed35de3d6d1a`。
- `/tmp/easyai-asar-fixture-alias-after-20261019.log`：`1bf21ecfb69a68324712eb20548c45304e829cf7529de146678742246c59e749`。
- `/tmp/easyai-win-shim-independent-yga8mS.log`：`9f337c98e01a633ed972f75accb370efccf0631855df21023f7b678f8f610117`。


## 2026-10-19 Windows 包内后端500：保留元数据，执行器先做平台门

起始工作区 clean，HEAD/远端均 `9f2da69ad4741038f71b2c1c4eb2316fbc26cdb1`。实际 [run39225887922](https://github.com/T1doo/Easy-AI/actions/runs/39225887922) Linux SUCCESS，Windows guards/build/ZIP audit SUCCESS；生成 easyai-0.0.0-win-x64.zip，435175301字节，SHA256 140c2acaa6a4dea3537ebd85ac62134874c2621fa1720d7f7b88a050c0a870da。但步骤18 packaged backend FAIL，Electron与上传SKIPPED，未取得可下载/全部门通过的Windows候选。父级提供 [step18正文](https://github.com/T1doo/Easy-AI/actions/runs/39225887922/job/117971948200#step:18:14)：Response.json解析 Internal Server Error 失败；旧smoke丢弃stderr，具体端点/服务端堆栈未知。本执行器仅读允许的run/jobs元数据，未重试被拒logs/artifacts/browser接口。

独立审查找到确定P2：GET catalog/packages→LocalWorkspace.installs→InstallRegistry无条件构造InstallRuntime→protected→remote_cache目录所有权使用Windows不存在的geteuid。此源码和红绿证明确定缺陷，不声称短正文已唯一确定CI首错。新增实际FastAPI回归：模拟win32策略并禁止POSIX owner到达，旧产品目录500/直接构造AttributeError（2FAIL）；修复后目录401/200、17卡、executionEnabled=false，计划200且平台blocker，确认409 INSTALL_PLAN_BLOCKED，来源422 INSTALL_RUNTIME_NOT_AVAILABLE，零owner/config目录、零history。InstallRuntime本身也在文件操作前拒绝不支持平台。Linux x64原runtime所有权和配置保护不变；没有Windows安装启用或跨平台权限弱化。

新增smoke脱敏诊断：有限64KiB stderr tail，失败后等待EOF退出与pipe close再汇总，最多24固定file标签/行号及12白名单异常类别；不记录消息、源代码、任意basename/函数名、原始正文、路径、header/token。lastRequest只输出固定HTTP方法/路由/状态；动态项目ID归一。非JSON和任何500均FAIL，原PID/readiness/auth/resources/编译/EOF/exit0断言不变。两项Node回归含JSON500/非JSON500、未知路径、敏感内容不输出与bounded retention。CI原native lock步骤追加实际Windows平台元数据回归，不删除任何测试。

实际命令 cwd /workspace/Easy-AI：
- FAIL（旧产品有效红例）：`services/backend/.venv/bin/pytest -q services/backend/tests/test_install_platform_metadata.py`，2FAIL；同命令修复后2PASS。
- PASS：`services/backend/.venv/bin/pytest -q services/backend/tests/test_install_platform_metadata.py services/backend/tests/test_install_runtime.py services/backend/tests/test_install_source_selection.py services/backend/tests/test_install_service.py`，47PASS/10.09s，仅既有Starlette弃用warning。
- PASS：`CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache UV_CACHE_DIR=/workspace/.uv-cache UV_OFFLINE=1 pnpm test:package`，36PASS/1.94s。所有既有归档/ASAR/private/bytes/PE门保留。
- PASS：同环境 `pnpm check`，TypeScript、ruff、mypy66文件、真实Blockly fixtures、格式全通过。
- PASS：`node scripts/python-task.mjs build /tmp/easyai-win-metadata-frozen-mXMPxN`（新独占临时目录，无覆盖旧包）与 `node scripts/test-frozen.mjs /tmp/easyai-win-metadata-frozen-mXMPxN/dist/easyai-sidecar`，真实PyInstaller应用后端离checkout临时cwd完整HTTP/resources/golden compile/EOF exit0。无torch/训练环境/下载/SSH/GUI。
- PASS：独审只读复核当前diff并独立运行Python2PASS与Node2PASS，Windows元数据P2关闭，无新增明确P1/P2。`git diff --check` PASS。
- 环境命令记录：首次未带XDG的pnpm exec prettier在尝试创建不可写/home/agent/.local/share/pnpm时ENOENT；改用既有workspace XDG后成功，无权限提升/安装新增依赖。

新Windows实际构建及packaged Electron尚NOT RUN，下一步仅一次正常开发分支提交push自然免费CI，不重跑旧run。README/两原件/依赖锁hash均与原值相同；旧Linux候选保留。main仍5323f86232529efcfb52131168ad049f01b219f3，未触碰Feng5u/发布/PR/权限/凭据。完整A/B、TST33、正式MNIST/真实SSH/硬件/法律审核仍未完成。

本轮日志SHA256（私密本机路径不入候选）：
- `/tmp/easyai-win-install-metadata-before-20261019.log`：`9bd9e833016fa6ac5198baf2061039787de6508cba4fb04b7184c1dbe804f3b6`。
- `/tmp/easyai-win-install-metadata-after-20261019.log`：`637ffeef862a1602c5b30f71d20c1af54bc90b849e13c3e748cf136c5c7a0629`。
- `/tmp/easyai-win-metadata-python-20261019.log`：`cfaa2df95a9ee15a0f550e32906d54b757dcab4f8e5fb66a802a1df5c6e9c732`。
- `/tmp/easyai-win-metadata-package-20261019.log`：`0bba90d39933134d2f27c6bdd33806afd4a5393a986b7dc8d9a77b58622e72aa`。
- `/tmp/easyai-win-metadata-check-20261019.log`：`3919a4f049028b0f3e104bd46428c4c7a5dedfc258cdb574f4dc446a4217e25d`。
- `/tmp/easyai-win-metadata-frozen-build-20261019.log`：`ea708d8bb4b7e77186198d162498ddf0cdb752f6b6c7a34304411eb781aadb54`。
- `/tmp/easyai-win-metadata-frozen-smoke-20261019.log`：`598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。
- `/tmp/easyai-platform-metadata-review-20261019-unique1.log`：`b49bf5ffe8231ff7a04ad4f1c97ae4e3bad92b8a04fcf82d8facb7365dd33610`。
- `/tmp/easyai-frozen-diag-review-20261019-unique1.log`：`59b9a6bde9b3593336c993f2d870835a1523e91d10b8aa281457a2feeab7f02e`。


### 本次自然 CI 的实际结果与剩余阻塞

产品修复已提交并正常push `e8efb040650acde8d5e6e422bd549991281d25cf`，远端同SHA。一次自然 [run39227538152](https://github.com/T1doo/Easy-AI/actions/runs/39227538152) Linux job117977380853 SUCCESS（pnpm check/test/build全部通过）；Windows job117977380233 FAILURE。step8 Project persistence, native locks and install metadata FAIL；step9 NTFS、step10冻结后端、step11冻结HTTP/resources均SUCCESS。step12–20全部SKIPPED，没有新候选构建或新ZIP。新增Windows元数据回归尚未证实通过，旧500未宣称关闭。

中间播报曾依据最后已完成step9而误报step8通过，随后逐项元数据核对发现step8FAIL，已立即更正；本记录以逐项结果为准。独审追加只读核对新测试在真实Windows的模块替换/Path/关闭/无runtime路径，未发现可源码证明的新P1/P2；step8同时跑既有test_project_persistence，不能仅按step名称归因。实际首异常仍UNKNOWN。

准确阻塞：读取目标 https://github.com/T1doo/Easy-AI/actions/runs/39227538152/job/117977380233#step:8:1 的首失败pytest nodeid、expected/actual、traceback及FAIL/teardown ERROR区别。父级已登录浏览器可读取，已通过异步问题请求提供；该证据pending。本执行器未尝试此前被拒logs/artifacts/browser接口，仅读允许的run/jobs元数据；没有重跑CI或猜测产品改动。当前Windows这次FAIL已确认，非不确定执行或等待安装授权。

独立只读边界实验：把training-profile副本换成CRLF后，wheels(optional roots)确定拒绝INSTALL_DEPENDENCIES_UNRESOLVED，因为锁文件bytes必须等于批准的LF pins。实际本次Windows checkout EOL未知，此实验不等于CI根因，尚未改变Git EOL策略/任何锁bytes，也未因此新推CI。需要本次正文后决定最小修复。

工作区本补记前clean；main远端仍5323f86232529efcfb52131168ad049f01b219f3。保存本次证据仅本地docs提交，不push，避免无实质修复再耗CI。原README/计划/规格/锁hash、旧Linux包均保留。下一步是据该新正文定位最小修复，复核对应测试/独审后再一次自然CI；候选必须通过Windows包内backend与Electron启停再留存，完整A/B与发布门仍未通过。


## 2026-10-19 父级补齐422正文：固定受审profile字节的checkout EOL

起始HEAD c4c5b606b7f1e0b8a5708b778a489ef0a74b1ef4，工作区clean，remote e8efb040650acde8d5e6e422bd549991281d25cf；c4证据保全。父级从已登录浏览器取得 https://github.com/T1doo/Easy-AI/actions/runs/39227538152/job/117977380233#step:8:29 ：test_install_platform_metadata.py:42，认证GET catalog/packages返回422 expected200；此前401正确，后续plan未执行。命令uv run --frozen pytest -q tests/test_project_persistence.py tests/test_install_platform_metadata.py，实际1FAIL9PASS/1.49s，尚无响应JSON或serverstack。不再把整step归因旧持久化测试。

源码校验来源：InstallService.catalog总是wheels(OPTIONAL_ROOTS)，install_sources.wheels逐组比对锁file rawbytes == LF header+_pins；不等时抛INSTALL_DEPENDENCIES_UNRESOLVED，API ValueError handler把该固定码映射422。新增真实Git init/config core.autocrlf=true/add/checkout-index实验并调用同一HTTP入口，旧无attributes确定同样422且响应固定码INSTALL_DEPENDENCIES_UNRESOLVED（1FAIL2PASS）；区别于前轮纯byte实验，这次走真实Git checkout和生产catalog。实际CI自身EOL未取得，不声称该机唯一观察根因，但修复的是确定跨平台checkout缺陷。

最小修复只有.gitattributes固定/packages/training-profiles/*.json与*.lock为text eol=lf。十个既有文件未改byte，不修改严格parser/constraints hash算法、owner、平台或执行授权，也不把422改为成功。正例使用新policy在autocrlf=true仓库checkout，要求真实HTTP200/17卡/executionEnabled=false及十文件与原bytes一致；负例故意改MLpin，必须HTTP422固定依赖错误，零install-processes。测试无网络/凭据/训练环境/数据/教师环境操作。

实际命令 cwd /workspace/Easy-AI：
- FAIL（旧policy红例）：services/backend/.venv/bin/pytest -q services/backend/tests/test_install_platform_metadata.py，1FAIL2PASS；真实HTTP422 codeINSTALL_DEPENDENCIES_UNRESOLVED。
- PASS（与失败CI相同文件集合）：services/backend/.venv/bin/pytest -q services/backend/tests/test_install_platform_metadata.py services/backend/tests/test_project_persistence.py，11PASS/0.71s；仍不是Windows确认。
- PASS：services/backend/.venv/bin/pytest -q services/backend/tests/test_install_platform_metadata.py services/backend/tests/test_install_ml.py services/backend/tests/test_install_cv.py services/backend/tests/test_install_dl.py services/backend/tests/test_install_nlp.py，53PASS/2.13s。
- PASS：ruff check及format --check新测试文件；git diff --check；git check-attr显示两类文件text set、eol lf。
- PASS：CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache UV_CACHE_DIR=/workspace/.uv-cache UV_OFFLINE=1 pnpm test:package，36PASS/1.92s。
- PASS：只读独审运行真实Git checkout定向回归1PASS，核Windows prefix.as_posix()+末尾/参数，无新增明确P1/P2；未改文件/联网/构建。pnpm check与真实Linux frozen全smoke上轮e8已通过，本次未改产品Python/TS，不为数字重复整套本地构建。

原README/计划/规格/锁hash均相同；旧Linux候选保留；main仍5323f86232529efcfb52131168ad049f01b219f3。下一步一次正常开发分支push自然免费CI，实际Windows metadata/candidate/backend/Electron必须逐项核；当前均未假称通过，无Release/PR/main/force/部署/新权限/付费/凭据/安装。新状态待结果补记。

- `/tmp/easyai-catalog-eol-before-20261019.log`：SHA256 `9689e180872bd8d5e4b3d1047f90ffe56f1c1f60954edc20fad374f652ca87ae`。
- `/tmp/easyai-catalog-eol-after-20261019.log`：SHA256 `b44b4304bbef4fa72bc44e1569fa5789b0b4d692b95698a05bd8a5d7abdecab7`。
- `/tmp/easyai-catalog-eol-profiles-20261019.log`：SHA256 `ead3add28371ee891b8e47f036ccc4b676709b1c4f248108c6c955199b8944f9`。
- `/tmp/easyai-catalog-eol-package-20261019.log`：SHA256 `5a133717d9d08bdd15c2c98f59d94a382dc1c37d60ff26da4d6845ac29fa6dc9`。
- `/tmp/easyai-profile-eol-independent-m3GAh7.log`：SHA256 `b14e0dcca43e975b46b35445307c28b4ae77cf9ef06ecb6e3fdb2e0b81fc3f50`。


### 实际Windows复核：目录与checkout修复通过，新包内smoke仍失败

产品修复/远端完整SHA `4304d2d1756e77a6c80468737cfeff449a48201f`，正常push产生唯一新自然 [run39228433732](https://github.com/T1doo/Easy-AI/actions/runs/39228433732)。Linux check job117980313555 SUCCESS（pnpm check/test/build）；Windows desktop job117980313772 FAILURE。原失败step8现SUCCESS，实际Windows目录、blocked plan及真实Git autocrlf回归均通过，未将期望改422。step9 NTFS、10冻结backend、11冻结HTTP/resources、12desktopbuild、13PID/isolation、14开发E2E、15packageguards、16实际候选构建、17ZIP audit全部SUCCESS。严格原测试/门保留。

新实际ZIP easyai-0.0.0-win-x64.zip，435171827字节，SHA256 b625e8bd68c709d3a940ce36857ee378f52c3f877079c67bdd916477a07134eb（来自审计step名实际输出，非本地推算）。step18 Packaged backend PID, auth, resources and EOF FAIL；step19 packaged Electron、20 artifact留存均SKIPPED。因此没有通过全部门或已上传可下载的Windows候选；构建/审计成功不算smoke完成。

准确剩余阻塞：需要父级从已登录浏览器读取 https://github.com/T1doo/Easy-AI/actions/runs/39228433732/job/117980313772#step:18:1 的首异常/断言和新增FROZEN_SMOKE_DIAGNOSTIC整行，以定位本轮端点/状态/脱敏frame及异常类别。本执行器仅使用允许的run/jobs元数据，未重试此前被拒logs/artifacts/browser接口；该新正文证据pending。不能把当前FAIL继续叫作旧catalog500，原因UNKNOWN；没有猜改/放宽原门/重跑CI。已通过异步问题请求父级提供该新正文。

本轮结束检查：HEAD/远端产品4304d2d一致、工作区clean（本补记前）；远端main仍5323f86232529efcfb52131168ad049f01b219f3。原计划hash dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43、原规格/README/两个依赖锁hash与原值一致，旧Linux候选及c4证据保全。此补记只作本地docs提交不push，以免无实质新修复浪费CI。下一步据新正文继续最小修复和独审，再实际确认Windows packaged backend/Electron/上传。无main/force/PR/Release/部署/新权限或训练环境/数据/模型/SSH/教师环境变动；完整A/B、TST33、正式MNIST、真实SSH及法律审核仍未完成。


## 2026-10-19 父级新正文：编译HTTP200，golden checkout字节不一致

起始HEAD97ecda72f202aa6a32955ebd621f30be0840a308（前轮失败证据保全），工作区clean，remote4304d2d1756e77a6c80468737cfeff449a48201f。父级从已登录浏览器取得 https://github.com/T1doo/Easy-AI/actions/runs/39228433732/job/117980313772#step:18:386 ：包内offline package plan+explicit registration/cancel先PASS；FROZEN_SMOKE_DIAGNOSTIC lastRequest POST /projects/:id/compile status200，stderr truncated=false retainedBytes=0 frames/exceptions=[]。test-frozen.mjs:506 strictEqual ERR_ASSERTION，生成actual LF、checkout golden expected CRLF，非HTTP500。job2m57s，Electron/上传SKIP；原435171827字节ZIP及b625e8bd68c709d3a940ce36857ee378f52c3f877079c67bdd916477a07134eb审计成功记录保留。

确认协议：CodeWriter.code明确'\n'.join(lines)+'\n'，bundle export文本写入明确newline='\n'；codeHash以UTF8实际生成字节计算。三个tracked golden目前原字节均UTF8/LF；test-frozen与test-portable Node readFile保留原换行，原Pythontest_compilation.read_text却自动转LF，曾掩盖checkout差异。仅.gitattributes对golden/*.txt和*.json补text eol=lf（全部3文件，IR/source-map同类一并保护），不全仓库renormalize、不改原golden内容或原计划/规格。加强原Python比较为code.encode UTF8 == golden.read_bytes；smoke strictEqual不变。刷新工具改write_bytes UTF8（JSON末尾显式byte10），既避免Windows默认文本换行，也避免旧JS/Python双转义把JSON末尾写成literal backslash-n；执行新工具后3原golden仍完全无diff。

新增匹配回归：真实Git core.autocrlf=true init/add/checkout-index，实际Python编译真实Blockly fixture，原policy确定goldenCRLF vs compilerLF在byte64失败（1FAIL）。补LF policy后checkout原始bytes与生成code/codeHash一致，三份golden与原件byte一致，CRLF变体codeHash不同；没有对读取结果normalize。Windows CI原step8加入此回归和全部test_compilation，不跳任何旧测试。

实际命令 cwd /workspace/Easy-AI：
- FAIL（旧policy红例）：services/backend/.venv/bin/pytest -q services/backend/tests/test_golden_checkout.py，1FAIL，字节64 CR vs LF。
- PASS：services/backend/.venv/bin/pytest -q services/backend/tests/test_golden_checkout.py services/backend/tests/test_compilation.py services/backend/tests/test_project_persistence.py services/backend/tests/test_install_platform_metadata.py，39PASS/1.19s（仅既有Starlette warning）。
- PASS：workspace XDG/UV_OFFLINE=1 node scripts/update-golden.mjs；git diff --exit-code -- services/backend/tests/fixtures/golden，三原文件无diff。ruff check/format --check两Python测试通过；git check-attr三golden eol=lf。
- PASS：同XDG环境pnpm test:package，36PASS/1.68s；原打包/ASAR/路径/秘密/字节门未改。pnpm format:check和git diff --check结果补记。

原golden SHA256：mnist.py.txt dd8ca37bc3cd2feeec05982558f0fda8d0a95dc09a03df79e3304c849912f550；mnist-program.json c101b949a266a0a54c688e3434ecc6bf30181937ae91edc1a45100cbffb70854；mnist-source-map.json 3e700e144995967feb9adbb9b7b28abc3eb2540a474843c9118ab75dc37fc10a。README/原计划/规格/依赖锁hash和旧Linux候选保持；main未改。下一步独审后一次正常开发分支push自然CI，再实际检查packaged backend/Electron/上传，不把Linux通过冒充Windows确认，无发布/PR/main/force/新权限/凭据/付费/训练环境/数据模型/SSH/教师环境变化。

- `/tmp/easyai-golden-eol-before-20261019.log`：SHA256 `52f5f7025f2d8de1946db3e411e7cd21939530b066f14bc49c48fc6153a137e9`。
- `/tmp/easyai-golden-eol-after-20261019.log`：SHA256 `1174ab96ab892c797b7cd2d614b69309985c20af0647e1d35ab2490ef2c07e3e`。
- `/tmp/easyai-golden-eol-package-20261019.log`：SHA256 `8421381d6b6db55892a1e0e40f60a1834d6c39ed0e650819b4e561f3273d3320`。

独审补记：只读checkout+compiler回归28PASS，独立在内存生成3份golden与现有bytes完全一致（12734/13111/36689字节），未运行updater/构建/联网/修改文件，无新增明确P1/P2。pnpm format:check与git diff --check PASS。
- `/tmp/easyai-golden-eol-independent-hnkviG.log`：SHA256 `74f86a5293b707c7ac69da66c43b77971486ba38ed342ffe41236e3789edfb20`。
- `/tmp/easyai-golden-eol-format-20261019.log`：SHA256 `cbe9f0d2d90255e8d0e75efb8b65eb31c9f56a6a2fd881e2245b07403e38967f`。


### 实例连通性与本次golden修复CI实际状态

修复正常提交/push `7b095e72e8eb411bebbc21d8208d49899bf8b87c`，保留97证据历史。父级中途收到环境断连通知；在同实例 /workspace/Easy-AI 执行date -u/pwd/git rev-parse/git status/3日志sha256/git ls-remote，2026-10-19T09:22:19Z exit0，实际可执行；HEAD/remote同7b，工作区clean，红绿/独审日志可读，main仍5323f86232529efcfb52131168ad049f01b219f3。未重启未知进程、未换执行器/新写入者。

一次自然新CI [run39229460721](https://github.com/T1doo/Easy-AI/actions/runs/39229460721) Windows job117983628622 FAILURE：step8 Project persistence, native locks and install metadata FAIL（该步此次新增test_golden_checkout与test_compilation）；step9 NTFS/10backendfreeze/11frozenHTTPresources SUCCESS；step12–20全部SKIPPED，无新ZIP，未实际验证新golden政策下的包内后端/Electron。Linux job117983628196 check/test SUCCESS，写本段时build in_progress，最终结果另补。

剩余准确阻塞：需父级浏览器读取 https://github.com/T1doo/Easy-AI/actions/runs/39229460721/job/117983628622#step:8:1 首失败pytest nodeid、expected/actual、traceback及FAIL/teardown ERROR区别，已异步请求，证据pending。本执行器只读允许run/jobs元数据，未重试此前被拒logs/artifacts/browser接口；当前失败具体原因UNKNOWN，不因整模块新增测试猜作symlink权限/编码/路径或继续归因旧LF/CRLF，也不删新测试使后续构建运行。等待新正文后最小修复，无重跑CI/松门/新增权限/发布操作。

最终逐项元数据复核：Linux check job117983628196已SUCCESS，pnpm check/test/build全部通过；Windows仍step8 FAILURE，其后候选SKIP。此失败证据仅本地docs提交不push，避免无修复再耗CI；远端产品7b保持，工作区提交后clean。原件/锁/旧Linux候选未改，完整A/B和发布验收未通过。下一步取得本次step8首失败正文，保留现有测试门逐根因修复并独审，再有界自然CI。


## 2026-10-19 Windows写入持久化与受管源码LF合同系统核对

起始HEAD bd0fffb1d809d095a0ba94c64c91408f7cd819e8，工作区clean，remote7b095e72e8eb411bebbc21d8208d49899bf8b87c。父级新正文 https://github.com/T1doo/Easy-AI/actions/runs/39229460721/job/117983628622#step:8:53 ：test_final_figure_component_boundary_really_writes_files两个参数x*220/中*73+'a'在atomic_target rb重开→fsync Windows Errno9 Badfiledescriptor；test_bundle_can_export_managed_core_from_frozen_resource_layout导出managed.py LF vs预期源CRLF，index90。3FAIL36PASS/6.73s，desktop1m30s；golden不是本轮首错，不删除新增全compilation测试。

修复：runtime/easyai_runtime.py只将临时文件同步重开模式rb改r+b（不截断），仍序列化关闭后校验路径→fsync成功→hardlink排他发布，finally清临时文件。不跳fsync、不改原子/排他发布或物理边界、不吞异常。新增5case真实文件回归：Windows式可写sync合同（旧代码success确定EBADF红例）+实际os.fsync，成功字节完全保留且同步先于link；fsync EIO、link EIO、serializer异常均无目的产物且无temp；竞争者先创建目的文件则拒绝且保留对方bytes，临时文件清理。

系统审计范围：rg fsync/fdatasync遍历runtime与全部backend源，并追踪sync_file调用的descriptor来源。普通文件来源：runtime atomic_json、install_owner.write_file、supervisor、managed log/cancel、host_keys、project_lock、event_journal、workspace export/create、owned_creation、install_source_selection、remote_install/install_process、project_service及bundle/run_store/SSH checkpoint/stream/artifact/transfer cache均是w/x/xb/wb/w+b或O_WRONLY/O_RDWR（exclusive/update）；仅atomic_target为rb重开。目录fsync属于原POSIX目录保护或WindowsDirectory native flush合同，保持平台门/权限，无unsupported fallback，也未启用Windows production storage。此为源码审计，不冒充Windows硬件断电耐久性验证。

确定字节资产：runtime_sources导出四helper+managed源码会以UTF8/LF写出；freeze还逐字节校验runtime/probe/install_owner。新增LF属性只覆盖runtime/*.py（六个）、managed.py、packages/block-library/manifest.json、packages/package-groups/catalog.json、examples/mnist-cnn/project.easyai.json、packages/contracts/fixtures/blank.json；训练profile十份/golden三份原规则保留，不全仓库normalize或动用户原件。新增第二个真实Git core.autocrlf=true checkout回归，旧规则确定runtime CRLF vs原LF失败；新规则十一资产与源bytes一致，runtime_sources输出UTF8bytes与各自源码完全一致。所有原golden/资源/编译器字节断言保持，无normalize读取结果。

实际命令 cwd /workspace/Easy-AI：
- FAIL红例：services/backend/.venv/bin/pytest -q services/backend/tests/test_atomic_artifact_durability.py -k success，1FAIL4deselected，准确OSError EBADF；旧LF policy的test_golden_checkout.py -k packaged，1FAIL1deselected、byte81 CRvsLF。
- PASS：services/backend/.venv/bin/pytest -q services/backend/tests/test_atomic_artifact_durability.py services/backend/tests/test_golden_checkout.py services/backend/tests/test_compilation.py services/backend/tests/test_emission.py services/backend/tests/test_install_platform_metadata.py services/backend/tests/test_project_persistence.py，57PASS/1.25s，仅既有Starlette warning。
- PASS：workspace XDG/UV_OFFLINE=1 pnpm test:package，36PASS；所有既有ASAR/ZIP/private/hash等门保持。Windows step8只追加durability新测试，旧全部compilation保留。
- PASS：只读独审定向34PASS，无新增明确P1/P2，确认r+b不truncate、sync后排他发布与cleanup、asset范围准确。未改/联网/构建。
- 格式校验真实记录：首次ruff format runtime漏带backend配置，默认88列重排，pnpm check在仓库100列检查FAIL；用ruff format --config services/backend/pyproject.toml runtime/easyai_runtime.py恢复全部无关格式，最终runtime diff仅两注释和rb→r+b。该失败日志保留，正确配置后的check和最终独占freeze/smoke结果稍后补。

无训练环境/torch/数据/模型下载/SSH/教师共享环境操作，无main/force/PR/Release/部署/付费/凭据/新权限。main原基线、README/原计划/规格/依赖锁/原golden和旧Linux候选保持；runtime合法修复只进入新候选，不覆盖旧包。下一步最终检查后正常分支一次有界自然CI，实际Windows packaged backend/Electron/上传未通过前不记候选完成，完整A/B与发布门仍未完成。

- `/tmp/easyai-win-durability-before-20261019.log`：SHA256 `21e86e853032b41ae81153ef3e256354dcbf822d4f63b2516693b7339f24a09f`。
- `/tmp/easyai-runtime-assets-before-20261019.log`：SHA256 `80acacc92c83ab96f009b17ba05db0f9232177b5b07885eab7ce29b04960d77e`。
- `/tmp/easyai-win-durability-after-20261019.log`：SHA256 `7aac5826b710458601445a9330c1465e6934767622c483cf6343999578886d82`。
- `/tmp/easyai-artifact-sync-independent-xUsMcq.log`：SHA256 `fc8011a7055119a4a7adf9fbfd54a45c6341f471d7c65ff58351e0f199bbf42f`。
- `/tmp/easyai-win-durability-check-20261019.log`：SHA256 `72d9e2af13f6020279ea9ff151f0cf6dc53f0e0dffa447f78a550ac25dc68a0c`。
- `/tmp/easyai-win-durability-package-20261019.log`：SHA256 `f1ea8cf3b0e7b9420d7aeec0b624851e2cc12cbcfd7608adf283d8f60ff1ed9d`。

最终源码复核PASS：同workspace XDG环境pnpm check，TypeScript/ruff/mypy66源文件/真实fixtures/格式全通过。node scripts/python-task.mjs build /tmp/easyai-win-durability-final-Htyykw 与 node scripts/test-frozen.mjs /tmp/easyai-win-durability-final-Htyykw/dist/easyai-sidecar均exit0，最终bytes真实冻结后端完整资源/HTTP/项目/golden compile/EOF0通过。未覆盖旧artifact。README/两原件/两个锁和三golden复核原hash均一致，git diff --check PASS。
- `/tmp/easyai-win-durability-check-final-20261019.log`：SHA256 `007402ac25bb13866eac8671350b82013fe398484ae377f28365535c9d66eebb`。
- `/tmp/easyai-win-durability-final-build-20261019.log`：SHA256 `2a8a93991cf1b19f6e52ccd5c368c14eab214fd2f70d5b808df8adea8ed664f8`。
- `/tmp/easyai-win-durability-final-smoke-20261019.log`：SHA256 `598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。


### 本轮实际验收：Windows候选构建、包内backend/Electron与短期留存全部通过

修复源码与远端 `d4ddd7e02ead22d54ac4fea32c3706a733551fc4`，唯一自然新 [run39230592065](https://github.com/T1doo/Easy-AI/actions/runs/39230592065)。2026-10-19T09:33:34Z同实例只读命令exit0确认HEAD/remote同SHA、工作区clean、main仍5323f86232529efcfb52131168ad049f01b219f3。没有重启/换写入者。

Linux check job117987315485 SUCCESS：pnpm check/test/build全部SUCCESS。Windows job117987314931 SUCCESS：step8所有原持久化/锁/metadata与新增golden/compile/durability回归SUCCESS，原3个失败已在真实Windows验证关闭；9NTFS、10freeze、11frozenHTTP/resources、12desktopbuild、13applicationvenv PID/isolation、14devE2E、15packageguards、16实际unsignedcandidate build、17ZIP audit、18packagedbackend PID/auth/resources/编译/EOF、19packagedElectron sandbox/ASAR/normalshutdown、20artifact留存全SUCCESS。

实际产物easyai-0.0.0-win-x64.zip，435166382字节，SHA256 e0e96bf48beccc78c96c866a9be0f1a57ba589f8fe1c6372d477df1a9ce5a860，来自审计step名实际输出。Artifacts名称easyai-unsigned-win-x64-d4ddd7e02ead22d54ac4fea32c3706a733551fc4，步骤20确认上传成功，保留一天；含ZIP+builder manifest/provenance/audit。完整获取/证据范围/后续条件已写docs/candidate-windows-d4ddd7e.md。执行器仅访问允许run/jobs元数据，无被拒logs/artifacts/browser重试；没有在本地下载重验该包，不假称读取收据或TST33。上传是短期验证artifact，不是Release/发布。

当前目标“Windows实际候选、ZIP审计、包内后端与Electron smoke”已完成；旧失败证据全部保全，仍不等于完整v0.0.0 gateA/B。下一项TST33干净Windows11x64普通用户桌面和真实课堂UI（先下载核大小/hash、解压启动/退出/编译），当前执行器无该桌面，NOT RUN；不需torch/数据/SSH即可先做此项。正式MNIST十轮效果、真实SSH/断线取消重连/硬件矩阵/法律审核仍未完成，需相应隔离训练环境、数据、主机与明确授权条件，不自动下载安装或改教师共享环境。Windows production storage仍off，distributionReady/legalReviewComplete仍false。

本收据及最终进度仅本地docs证据提交，不push额外CI；remote产品保持d4。原README/计划/规格/依赖锁/golden与旧Linux候选保持。无main/force/PR/Release/部署/付费/新凭据/权限变化。下一阶段由父级统一监督排定，当前无代码故障日志阻塞，剩余为明确未验收条件。


## 2026-10-19 Windows宿主run/SSH本地存储selector与有界原生枚举（第一阶段门仍关闭）

起始HEAD dabd58a2f2d40e42ae79c2df85ff3b1eb587d398，工作区clean，remote d4ddd7e02ead22d54ac4fea32c3706a733551fc4；dabd证据保全。父级浏览器独立确认原候选CI完整SUCCESS、包内backend三条PASS/EOF0、Electron1PASS2.1s，artifact12176144515一天保留，初审无P1/P2/松门，原包/收据保留。

原计划需求引用：docs/v0.0.0 plan.md §3.3第156行优先Windows11x64客户端连接LinuxSSH；§13单跳Linux，M5.3运行/持久事件、M5.4重连/取消/同步，M8.2要求干净机可连接已备环境。源码确认当前生产缺口：remote_cache.require_local_cache拒非POSIX、local_directory只选_PosixDirectory、limited_names只接受该类型；RunService默认Windows只走旧普通本地持久化，已有native coordinator/run tests都直接storage=WindowsDirectory注入。故这是真实原产品缺口，不是另造外围任务，不等待数据/外部SSH才推进。

本阶段：内部WINDOWS_NATIVE_CACHE_VERIFIED=False（无env/API/renderer开启入口）保持产品门。新增windows_cache_enabled检查gate+nt+x64；local_directory在门允许后才lazy导入并创建真实WindowsDirectory，绝无POSIX替代。RunService在native门允许时使用同一默认selector，SshRunCoordinator默认原本就是该selector；local_workspace.bind_remote/remote_runs.prepare原require门自然接通。limited_names只允许实际WindowsDirectory的限量native枚举，仍验证前后身份，POSIX路径保持。

NativeWindowsApi.names现在固定64KiB缓冲、limit1..4096、最多limit+3调用、结果最多limit（limited_names1..1024）；记录解析校验长度/offset/UTF16/component，拒casefold重复和重复dot、不一致end receipt/结束携payload，越限明确拒绝，非等待枚举完整后再截断。已有ACL/reparse/volume/held identity/kernel locks/nativeflush/不覆盖publication逻辑未改。不是路径os.listdir替代或Windows权限修复。

匹配测试：Linux enum合同覆盖精确limit+真实end receipt/first restart、超限/重复dot/大小写别名/短record/奇UTF16长度/越界name；默认门关闭仍先拒绝。新增native集成文件只在Windows执行，临时开启内部gate，不注入storage factory/API：实际local_directory与limited_names+TransferSource inventory/open，默认RunService native ledger/shared journal/cancel/recovery，默认SshRunCoordinator lostACK→unknown→inspect恢复且start/stage只1次。SSH为固定内存synthetic transport，socket连接禁用，无外部认证/主机/训练；真实本地NTFS才是该测试证明对象。默认门仅待这些真实native集成通过后再审是否开启，不把测试注入当产品ready。

实际命令 cwd /workspace/Easy-AI：
- PASS：services/backend/.venv/bin/pytest -q services/backend/tests/test_windows_cache_selector.py services/backend/tests/test_windows_storage_contract.py services/backend/tests/test_run_storage.py services/backend/tests/test_windows_cache_integration.py，68PASS/3nativeSKIP（Linux，不作Windows通过）。
- PASS：同pytest追加test_ssh_run_coordinator.py/test_run_service.py的合同与回归集合，120PASS/5.70s。
- PASS：pytest -q test_data_transfers.py test_data_transfer_recovery.py test_remote_artifacts.py（路径均services/backend/tests/），103PASS/9.38s。
- PASS：workspace XDG/UV_OFFLINE=1 pnpm check，TypeScript/ruff/mypy66源文件/真实fixtures/format通过；git diff --check。
- PASS：独立只读48PASS/3nativeSKIP，无新增明确P1/P2，认可bounded enum/selector gate，未改/联网/构建；明确native acceptance仍待CI。

本阶段CI在原native NTFS步骤追加两测试文件，不删原测试、不启用产品门。下一步一次正常开发分支自然有界免费CI；若实际native集成失败，需新正文定位，不猜改/重复旧run；若通过再对下一阶段默认门/其它WindowsSSH路径做有证据的集成，不声明全部WindowsSSH已就绪。HostKeyStore等调用链还需后续系统核对，外部SSH/正式数据、训练环境、硬件和TST33仍独立未验收条件，不阻止当前代码推进。原计划/规格/README/锁hash保持、main仍5323f86232529efcfb52131168ad049f01b219f3；不改教师环境、下载/安装、main/force/发布/PR/权限/凭据/付费。

- `/tmp/easyai-windows-selector-targeted-20261019.log`：SHA256 `23e28de86117343db8ff3bcbdf563c97f93a533db3e6ab65896329f0e09ee322`。
- `/tmp/easyai-windows-selector-regression-20261019.log`：SHA256 `b2fca707d167ee60ab4daaa2165be809f73e5f7648e46b5ef1ec63a8b5ae528a`。
- `/tmp/easyai-windows-selector-consumers-20261019.log`：SHA256 `836cc82727a6c96d074cd14028b54d3952b1b75e5708309b27bf892498cb068d`。
- `/tmp/easyai-windows-selector-check-20261019.log`：SHA256 `7bb5b9eb40318a727256c7414127c5ca33b23bf440aa4e4841edbfc9e05a4201`。
- `/tmp/easyai-windows-selector-independent-JNkecT.log`：SHA256 `1451c283a421a17e8aa3e0ec493adeb2b1827ba77706f4e0ba77b0821c59afc3`。


### 第一阶段原生CI通过后：第二阶段验证产品默认selector

第一阶段源码/远端06c470cdb83e622e0cdabbf84359ce6a3ff3c4f2 / [run39232044136](https://github.com/T1doo/Easy-AI/actions/runs/39232044136) Linux job117992069835与Windows job117992069498均SUCCESS。Windows step9实际执行全部native合同及3项真实selector集成成功，step8、freeze/resources/devE2E/guard/build/ZIP/backend/Electron/retain全成功。ZIP435167246字节、SHA25636cace8fd194eb584181386da33783182cb91770910489ae58cc66518ccb3267，仅读允许jobs元数据，无logs/artifact拒绝接口重试，原d4包证据保全。

用户“保持默认门直到实际native集成通过”条件现在已满足。独审只读复核认为本地缓存selector启用无新增明确阻断点，建议限于该gate、native测试改断言真实default，再验证packaged启动；明确不代表Windows SSH全链ready。本阶段把WINDOWS_NATIVE_CACHE_VERIFIED=True（附证据run），删除nativeintegration fixture临时开gate，改为assert真实产品默认enabled。保留closed gate负例，另加ARM64拒绝负例；CI native步骤更名准确，不再称product gate off。没有新环境变量/API/renderer权限开关或OS权限增加。

本地PASS：services/backend/.venv/bin/pytest -q services/backend/tests/test_windows_cache_selector.py services/backend/tests/test_windows_storage_contract.py services/backend/tests/test_run_storage.py services/backend/tests/test_windows_cache_integration.py，69PASS3SKIP/0.85s；SKIP为Linux无法执行native，不冒充defaultWindows确认。第二阶段pnpm check结果稍后补记。第一阶段完整120/103回归和静态检查不因数字重复，第二阶段实际default需自然新CI。

明确后续代码缺口已只读定位：HostKeyStore在host_keys.py构造仍拒非POSIX，直接fcntl/dir_fd实现，故缓存启用不会绕过SSH主机信任或伪称完整Windows SSH。该部分需要继续受保护的native信任库适配，独立于正式数据/凭据/硬件；不把整体暂停在TST33或正式训练。当前范围/证据与边界另记docs/windows-cache-selector.md。原计划/规格/README/锁、旧候选、main不动，无发布/PR/强推/真实SSH/下载/训练依赖/共享环境变更。

- `/tmp/easyai-windows-selector-default-20261019.log`：SHA256 `23bc248547bc728b3bf6a02fa43a9efda2557c7395afe5d6dcc22be61a3b604f`。

第二阶段workspace XDG/UV_OFFLINE=1 pnpm check PASS，TS/ruff/mypy/fixtures/format全部通过；git diff --check PASS。下一步仅此默认selector变更正常push一次自然免费CI，核实际默认Windows与packaged startup，不重跑第一阶段。
- `/tmp/easyai-windows-selector-default-check-20261019.log`：SHA256 `7bb5b9eb40318a727256c7414127c5ca33b23bf440aa4e4841edbfc9e05a4201`。


### 第二阶段Windows默认路径通过；Linux已知负例前提修复与首错待核

第二阶段源码/remote f89831a15498e00db6da3d20891e9a4fe45c0b4a / [run39232654843](https://github.com/T1doo/Easy-AI/actions/runs/39232654843)：Windows job117994085200完整SUCCESS，step8 startup/metadata/compile与step9实际默认native selector集成/security contracts、原freeze/resources/devE2E/guards/build/ZIP/backend/Electron/retain全SUCCESS。无storage factory/API或gate临时开启注入，defaultcache actualWindows已验证。实际ZIP435167215字节，SHA256a869cd8a1a331b212f83f823982e8ad8ff2b6e5dfe032baa7bcc0caadbabba98。原d4和06c候选保留，本执行器未下载此包或读uploadreceipt，不把Windows成功夸成完整SSH。

Linux job117994084895 pnpm check SUCCESS但pnpm test FAILURE，后续build SKIPPED，整体CI失败。已请求父级浏览器 https://github.com/T1doo/Easy-AI/actions/runs/39232654843/job/117994084895#step:9:1 首测试名/异常，证据pending；未读被拒logs/artifacts接口，不假定唯一CI根因。

父级再次收到环境断连通知；同实例最小只读 date/git HEAD/status/日志sha/ls-remote 在2026-10-19T09:50:34Z exit0，实际可执行，HEAD/remote f898、工作区clean、日志可读、main不变；未重启未知进程或另开写入者，也未因通知重复测试。

独立源码核对发现两个确定旧夹具前提失效：test_local_ssh_storage.test_unverified_platform_refuses_before_any_local_or_native_access与test_remote_run_api.test_unverified_cache_platform_refuses_binding_and_prepare_without_staging只将capability.os.name=nt当未验证能力。新真实Windows能力已启用，这个前提不再成立；本地定向两例旧夹具确定2FAIL（首例转nativebackend、第二binding200而非预期422）。只在两负例各增加monkeypatch WINDOWSNATIVECACHEVERIFIED=False，明确未验证能力，不改产品/expected码/零storage/bind/staging/命令副作用断言。真实默认Windows正例仍已通过且保持。不凭该本地红例声称CI全部失败唯一根因。

匹配命令：pytest -q services/backend/tests/test_local_ssh_storage.py::test_unverified_platform_refuses_before_any_local_or_native_access services/backend/tests/test_remote_run_api.py::test_unverified_cache_platform_refuses_binding_and_prepare_without_staging（固定应用.venv），旧2FAIL；修复后pytest -q services/backend/tests/test_local_ssh_storage.py services/backend/tests/test_remote_run_api.py，43PASS/16.20s。ruff check/format --check两文件与git diff --check PASS。独审只读2PASS，确认不是松测试、保留全部负向断言，无新增明确P1/P2。此次无产品源改动，不为数字重复上一轮静态/构建。

下一步仅该确定夹具修复一次正常新提交自然CI，非重跑失败run或猜改产品。HostKeyStore独立POSIX门及before-dial信任存储验证继续保持，仍为下一项明确代码缺口，不等正式数据或外部SSH凭据才推进。本轮新CI结果另补，完整A/B、TST33、真实SSH/MNIST/硬件/法律审核仍未完成。原件、锁、旧候选与main不变，无发布/PR/main/force/新权限/付费/凭据/下载/训练环境/教师环境操作。

- `/tmp/easyai-windows-selector-unverified-before-20261019.log`：SHA256 `d278e55af62905366a25f09ddc11b63f0ac850af4c9abc1cef82ee4701d25d76`。
- `/tmp/easyai-windows-selector-unverified-after-20261019.log`：SHA256 `e62cca81e849d49993dffabbde5e2d26b2f1743459f4f4843b5c39a6232dac3d`。
- `/tmp/easyai-cache-negative-independent-I3Z63T.log`：SHA256 `ec25e3d8f9c376b631bdb960261bed46c270ea3da0832e862b39d1aca41b17bd`。


### 父级精确正文确认与最终全绿默认native缓存候选

父级浏览器补齐f898前轮Linux正文：test_local_ssh_storage.py197/198只os.name=nt注入，预期PLATFORM_UNVERIFIED实际WINDOWS_CACHE_NATIVE_PLATFORM_REQUIRED，remote_cache296→windows_store517→NativeWindowsApi160；test_remote_run_api.py735预期422 REMOTE_CACHE_PLATFORM_UNVERIFIED实际run-bindings200，同一旧前提。2FAIL944PASS11SKIP/113.17s，Windows完整SUCCESS3m13s并上传。与本地两红例精确吻合，现可确认原失败节点而非猜测；本执行器未重试logs接口。两行夹具修复af5正常push一次自然CI，不改产品码或负向断言。

最终源码/remote `af5a1f96509976f9474eee80b5852b66aea1cee6`，[run39233339421](https://github.com/T1doo/Easy-AI/actions/runs/39233339421) Linux job117996371304与Windows job117996371933均完整SUCCESS。Linux pnpm check/test/build SUCCESS；Windows step8 startup/metadata/compile等SUCCESS，step9实际生产default native selector集成/securitycontracts SUCCESS（无临时gate开启/存储factory/nativeAPI注入）；freeze/resources/devE2E/guards/build/ZIP audit/packaged backend/packaged Electron/retain全SUCCESS。旧Linux2FAIL已经通过正常真实CI关闭，不是跳测试。

新实际ZIP easyai-0.0.0-win-x64.zip，435167215字节，SHA2567ae7812c414dc5ed1a4d02c7d5e13db758c175c2333200ead0f11e4080bada21，来自audit step实际输出。Artifacts名称easyai-unsigned-win-x64-af5a1f96509976f9474eee80b5852b66aea1cee6，一天留存，step20上传成功。收据docs/candidate-windows-af5a1f9.md记录证据范围和获取，原d4成功候选/06c阶段/f898 Windows成功及全部失败历史保全；没有下载或假称本地重验该ZIP/读取manifest。仅读允许run/jobs元数据，无logs/artifacts/browser绕过。

本轮指定缺口完成：有界NTFS native枚举、require_local_cache/local_directory/limited_names/RunService默认selector真实接通，在实际native集成通过后才启用门，并再次实际验证product default和包内启动；ACL/reparse/volume/身份/锁/持久化均保持。父级独审与本地回归证据见上，不宣称真实外部SSH。

下一具体代码项仍是HostKeyStore独立POSIX门及native私有主机信任库适配，SshClient before-dial仍拒绝该未支持平台；原计划§13.2未知/变化key确认与保护必须保持。此代码工作独立于正式数据/外部SSH凭据，可继续推进，整体不暂停在TST33/十轮训练。完整Windows SSH、真实SSH/正式MNIST/硬件/TST33/法律审核与A/B仍未完成；未自动下载/安装/修改共享训练环境。无main/force/PR/Release/部署/新权限/付费/凭据。此最终证据仅本地docs提交不push额外CI，remote产品af5保持；main、原计划/规格/README/依赖锁与原golden未动，工作区提交后clean。


## 2026-10-19 HostKeyStore Windows原生信任存储第一阶段（独立默认门仍关闭）

起始HEAD dd6f062cb815abb4e318f64414a64be2b6fef87e，工作区clean，remote af5a1f96509976f9474eee80b5852b66aea1cee6；dd6证据保全。父级浏览器独立确认af5 CI39233339421全SUCCESS、artifact12177092913，源码独审nativecache无P1/P2/松门，切片接受，未把完整SSH标完成。

调用链确认：LocalWorkspace.ssh懒构造SshClient(store factory)；SshClient._open先获取/创建HostKeyStore再dial；HostKeyStore构造拒非POSIX。因此即便cache已默认native，Windows在任何外部握手前仍拒绝。原方案§13.2要求未知指纹明确确认、变化key阻断；本轮目标是其安全存储适配，不是绕过校验或真实外部SSH。

实现：独立WINDOWS_NATIVE_TRUST_VERIFIED=False，只有cache接受且该trust门接受才选择WindowsTrustStore；第一阶段默认拒绝保留。Native TrustStore只在既有受保护application state父下用WindowsDirectory.child创建末级root，(volume,128-bitfileid)钉住身份，单次bounded文件读和读前后verify_file；永久writer kernel锁后重新读catalog，公共TOFU确认逻辑决定payload，exclusive临时bytes→flush/sync/verify→原子publish，失败finally清temp。所有Native ACL/reparse/volume/身份/锁/flush保持。changed key维持硬拒、无新replacement入口；catalog原子替换必须由公共explicit-confirm策略触发。POSIX directory flock/dirfd保护与key parser保持，仅抽出rawbytes reader以共用解析。

开发校验真实记录：初始抽取POSIX helper漏把missing-file返回{}改bytes，测试27FAIL16PASS；修成b''后身份原43PASS。一次ruff报局部WindowsTrustStore导入遮蔽TYPE_CHECKING类型，改lazy alias后静态通过。这些失败日志保全，未push坏版本。

独审发现新P2：lock.close失败跳过directory.close并丢owner。修为所有owner总attempt、进程级保留不确定(owner,原chain快照,实际fd)、拒之后新store/transaction/read/write，绝不盲重试数字句柄；进程退出为恢复边界。首补修误抓descriptor而实际WindowsWriterLock字段fd，独审再次指出，已修真实fd并回归模拟fd先清空再抛。最终独立4PASS确认P2关闭；gate仍False。纯fake cleanup合同不冒充native接受。

测试：新增8项native实际文件语义（只Windows执行）：显式TOFU/错误fingerprint/重开/changed拒、竞争confirm不得覆key、永久kernel writer锁、sync/publish失败保留旧file并清temp、root替换拒绝、非规则known_hosts拒绝、Socket/Transport本地模拟握手仍走真实trust校验。仅合成Ed25519 public wire bytes，没有私钥生成/写真实trust/认证或外部socket，create_connection禁用。另有closed gate及lazy client before-dial拒绝、close不确定owner/全部cleanup尝试/之后零新打开合同。

匹配命令 cwd /workspace/Easy-AI：
- PASS：pytest -q services/backend/tests/test_ssh_identity.py（固定应用.venv），修复后43PASS/0.82s。
- PASS：pytest -q services/backend/tests/test_windows_host_keys.py services/backend/tests/test_windows_host_key_gate.py services/backend/tests/test_ssh_identity.py services/backend/tests/test_connection_manager.py，65PASS8nativeSKIP/1.21s；Linux不证明native。
- PASS：最终cleanup/gate/identity/connection集合68PASS/1.22s。
- PASS：workspace XDG/UV_OFFLINE=1 pnpm check，TS/ruff/mypy67源文件/fixtures/format通过；git diff --check。
- PASS：node scripts/python-task.mjs build /tmp/easyai-native-trust-frozen-JiZqzH；固定应用python -I scripts/verify-frozen-trust.py /tmp/easyai-native-trust-frozen-JiZqzH/dist/easyai-sidecar/easyai-sidecar（只读CArchiveReader，四信任/cache模块实际存在，不执行archive代码）；node scripts/test-frozen.mjs同backend目录完整HTTP/golden compile/resources/EOF0通过。CI packaged backend步骤添加同readonly模块门，再运行原smoke，不替代任何原断言。
- PASS：独审初44PASS8nativeSKIP发现P2，补修中2PASS指出fd字段不符，最终4PASS关闭P2；无关闭gate/校验绕过。仍须实际Windows接受后才可评估默认开启。

第一阶段CI保留所有原步骤，native步骤追加trust/gate/cleanup文件；产品默认门False。下一项独审最终增量后一次自然有界免费CI，以真实Windows文件语义结果为准；若失败据首正文最小修复，不盲重跑。说明见docs/windows-host-trust.md。原main/原件/锁/golden/旧候选保留；无外部SSH、真实信任/凭据写入、训练/数据/模型/共享环境、发布/PR/强推/付费/新权限变化。

- `/tmp/easyai-native-trust-posix-20261019.log`：SHA256 `70b58425d7201370c94320fc51529a49381a6e4fd754966554f2a21267482cea`。
- `/tmp/easyai-native-trust-posix-fixed-20261019.log`：SHA256 `56ae43fbb3ff0b487704406d367f68416988e722834dedde6fb5b879cd5c59c8`。
- `/tmp/easyai-native-trust-check-20261019.log`：SHA256 `2881776672bab2eac585cc998a4599ada587d9127fbb94b0f5401ad1044f3d72`。
- `/tmp/easyai-native-trust-final-check-20261019.log`：SHA256 `e580f738fb6f2a6bfe01cc5daae5d3e702f5220b2ad112eafff67fad6afa0a95`。
- `/tmp/easyai-native-trust-targeted-20261019.log`：SHA256 `cfc93c42fae4ca238b200e7ca92d9726ef45f98c99e19893d48346995608bf5b`。
- `/tmp/easyai-native-trust-cleanup-final-20261019.log`：SHA256 `83a6bcfcc1a8cb004f5910e6b133063a3d2ea98b593a3c972ac1b33f97723b9d`。
- `/tmp/easyai-native-trust-build-20261019.log`：SHA256 `5e782cb70f1756439d64b98e622f2d2095be0cf40d2ea596b4cebf056216185b`。
- `/tmp/easyai-native-trust-archive-20261019.log`：SHA256 `06cf684abaf7301dfe3527f0004569909e2844ed6b8e48f1627920c72a37d120`。
- `/tmp/easyai-native-trust-frozen-smoke-20261019.log`：SHA256 `598e651d8bfd55009c56cd315d848d8185d98d8ae4eb67c6d0dd2d14af4ed0c3`。
- `/tmp/easyai-native-trust-independent-jRTorb.log`：SHA256 `4425df8cae543967634a87a52089d85ab88f71822f6ac0660e1774cc345a5492`。
- `/tmp/easyai-trust-cleanup-independent-156WKn.log`：SHA256 `cdf8d13a3f141b449c7d92c9b86d6fd681de17445a1d661236b92f93860eafac`。
- `/tmp/easyai-trust-cleanup-final-independent-uVPhWk.log`：SHA256 `ebd938888ffaa2af3581cec946b9b58fbc84d3d34af429b416dd4a0ad79f1a12`。


## 2026-10-19 原生信任第一阶段接受与默认路径复验

第一阶段源码/remote `0254cce4b38f16843e8ecd070d1d52f4c96333b0`，CI39235525773 Linux job118003539047、Windows job118003538503均完整SUCCESS。8项实际NTFS信任测试及原cache/security门通过，四个模块入实际冻结sidecar的只读检查、包内backend与Electron原smoke均通过。实际ZIP435171846字节，audit SHA256 `a7ea1c527cff68dd08fcb76bc3eb50d732b6a50ad3ffcd7aeecdbfa43990097b`；上传成功、一天留存。未下载/本地重验ZIP；仅使用允许的run/jobs元数据。

独审确认本地信任门启用条件已满足，无新明确阻塞。第二阶段只把独立trust门置True，native8测试改为断言真实default True，移除临时gate注入；closed gate/before-dial/错误指纹/changed key/不确定cleanup拒绝均保留。原CI完整步骤保留。

PASS（cwd /workspace/Easy-AI）：`services/backend/.venv/bin/pytest -q services/backend/tests/test_windows_host_key_gate.py services/backend/tests/test_windows_trust_cleanup.py services/backend/tests/test_ssh_identity.py services/backend/tests/test_connection_manager.py services/backend/tests/test_windows_host_keys.py`，68PASS8nativeSKIP/1.21s；Linux不冒充NTFS接受。`CI=true XDG_DATA_HOME=/workspace/.local/share XDG_CACHE_HOME=/workspace/.cache UV_CACHE_DIR=/workspace/.uv-cache UV_OFFLINE=1 pnpm check` 全PASS；日志 `/tmp/easyai-native-trust-default-20261019.log`、`/tmp/easyai-native-trust-default-check-20261019.log`。下一项一次自然CI复验实际默认值。无外部SSH/真实信任或凭据写入/训练或数据下载/发布；完整SSH与A/B未完成。


### 原生信任默认路径最终实际CI收据

产品HEAD/remote `c28e955b7787ba1986fc40cd7aa13316f32d7e51`，[CI39236337416](https://github.com/T1doo/Easy-AI/actions/runs/39236337416) Linux job118006196540与Windows job118006196236全SUCCESS。Windows step9真实default native cache+host trust全PASS（没有临时开gate或native API/storage注入），原项目/锁/metadata、冻结backend/resources、开发E2E、打包保护、实际builder、ZIP审计、包内backend和Electron、上传均SUCCESS；Linux pnpm check/test/build全PASS。ZIP435171845字节，audit SHA256 `9b7e9c8bc4c75778dab872c088be800aa9600b247aca31b2b05871a1e9a3ff46`；候选收据docs/candidate-windows-c28e955.md。未下载或假称本地重验ZIP，只读允许run/jobs元数据；没有重试被拒logs/artifacts/browser端点。

独审c28e增量无新P1/P2，4PASS8nativeSKIP，日志/tmp/easyai-trust-default-independent-H27JfS.log（SHA25687536cf5f87874e5853f8e59b02343311b450e0f981f980a274143e452fcfc7c）。本地默认回归68PASS8SKIP日志SHA25682a35554dedf1abdd0c0fa630cba71770f349d6bacbd7e71525b327dc9b4e493；pnpm check日志SHA256e580f738fb6f2a6bfe01cc5daae5d3e702f5220b2ad112eafff67fad6afa0a95。

本阶段指定HostKeyStore原生私有持久化缺口已实际闭环：独立关闭门→真实NTFS接受→独审→默认开启→真实default及包内验证。未知key只允许显式指纹确认，changed key硬拒且没有替换入口，关闭门/before-dial/cleanup未知拒绝门保留。测试仅合成public wire bytes和本地模拟transport；不宣称包内真实SSH或完整Windows SSH完成。

下一项：实际Windows客户端到受控Linux SSH服务器的完整认证/取消/重连/路径安全验收仍NOT RUN，须先由父级明确最小授权目标、账户认证方式、主机指纹与私有state位置；正式MNIST/训练依赖/硬件/TST33/法律审查同样NOT RUN，不擅自下载或修改共享环境。源码与本地docs结案后正常差异仅docs证据提交领先remote，避免额外自然CI。main仍5323f86232529efcfb52131168ad049f01b219f3；原plan/规格/README/依赖锁/golden SHA保持。无main/force/PR/Release/部署/付费/新权限/真实凭据变化。


## 2026-10-19 M4/M7 真实桌面编辑与错误修复闭环

父级接受c28e默认信任接线后明确授权本UI切片。基线本地e400fd08974c6cf5f580cc317c01a562d8ddce62、remote c28e955b7787ba1986fc40cd7aa13316f32d7e51，工作区clean，main不变。已核现有ProjectEditor/WorkspaceManager/App/CodeView/Monaco加载/CSP和现有startup.spec.ts：产品已有删除、引用诊断定位、Undo、自动保存与恢复；原Playwright仅启动/沙盒/bridge/退出。没有凭空重做产品或另造runner。

扩展同一个现有Playwright场景，由原Windows CI开发态及实际packaged executable两次执行。使用独立临时工程和Electron标准--user-data-dir并断言实际app.getPath隔离，仅用测试进程替换原生目录picker返回该临时目录，限制title/properties，其余真实Main IPC/私有后端/Python编译器/Blockly/Monaco不注入。路径：新建MNIST示例→实际编译通过→打开真实Monaco并验证nonce/readonly与积木语义装饰→选train_data并删除→自动保存后真实REF_NOT_FOUND/DATASET_REF阻断→诊断源按钮定位data.dataloader→Undo恢复原Dataset ID→自动保存再编译通过→切模型页保存→正常退出重启→恢复三页/引用/代码显示状态再编译。完整工作区仅根数组按稳定ID规范后比较，保留块/字段/连接/坐标全等；真实编译全文Undo前后和重启后全等，不把Monaco虚拟可见行当完整code。

PASS：固定workspace XDG/UV_OFFLINE=1 pnpm check（/tmp/easyai-ui-check-20261019.log）；后续更新tsc -p tsconfig.tests.json PASS；playwright test --list发现原文件唯一扩展场景；git diff --check PASS。本地GUI NOT RUN：当前执行器没有显示服务或Xvfb，未安装或关闭sandbox。实际Windows开发态和打包态待本次正常提交自然CI，零自动重试。已有HostKeyStore证据e400随该正常开发push保留。

安全与范围：没有点击运行、选择训练环境/数据/SSH或凭据，不下载/训练，不改CSP/IPC/sandbox/编译器或产品边界。两个顺序实例/锁测试不冒充跨进程真实SSH；冻结模块清单只证明存在。真实SSH、正式MNIST、TST33与法律审核各自NOT RUN，完整A/B未完成，但不阻塞独立UI验证。


### M4/M7 首轮实际Windows FAIL（首错正文待父级，未盲重跑）

源码/remote `3e7a4c49d854578e657a1bccb6afe52b0e06dcc6`，[CI39237904291](https://github.com/T1doo/Easy-AI/actions/runs/39237904291)：Linux job118011369013 check/test/build完整SUCCESS；Windows job118011368851 step14 `Run pnpm test:e2e` FAIL，候选构建/ZIP审计/包内E2E/上传SKIPPED，因此本轮没有新Windows候选。此前原native cache/trust与冻结门仍SUCCESS。根因UNKNOWN：只有run/jobs状态，没有首失败断言/expected/received/traceback；已请父级从已登录浏览器读取该step。未重试原日志/下载/browser被拒接口，没有把一般继续推进当新授权。

独立只读复审发现可直接证明的测试P2（不宣称为上述CI首错）：锁定Monaco0.57.0 `esm/vs/editor/browser/controller/editContext/textArea/textAreaEditContext.js:536` 对domReadOnly&&readOnly明确setAttribute('readonly','true')，原测试要求空串。现保留只读门改检查DOM `readOnly===true`，产品无修改；固定环境 `pnpm exec tsc -p tsconfig.tests.json` 与prettier、git diff --check PASS。该确定修正先本地保留，未以未知首错盲触发新CI；父级补首错后继续有据修复与自然CI。原3e7a失败事实保全，不降低Monaco/CSP、完整恢复/编译、安全断言。

独审进入首轮前未发现明确产品P1/P2；根数组顺序误断言在push前已改为仅根按ID排序完整比较，不改产品。当前UI开发态未通过，实际打包UI NOT RUN；不复用c28e旧绿色声称此新链成功。最新可用旧候选仍docs/candidate-windows-c28e955.md。原件SHA保持、main不变，未执行训练/下载/SSH/凭据/发布。


### 父级补首错后继续：真实Blockly SVG缺少locale的初始化缺陷

父级授权云浏览器已读取原CI39237904291/job118011368851 step14首错：startup.spec.ts:113，创建示例后getByRole(complementary,“对象注册与引用”).getByRole(button,/^train_data/) not found，5000ms，step10秒；没有更深栈/Received/context正文。来源https://github.com/T1doo/Easy-AI/actions/runs/39237904291/job/118011368851#step:14:17。原FAIL保留；未重试日志接口。

追查确认examples真实模板train-dataset/train_data注册true，后端create保留extraState，snapshot取data根注册对象，picker参数一致；没有改模板/注册状态伪造按钮。新确定产品缺陷：从blockly/core导入不带Msg字典，真实Blockly.inject初始化WorkspaceSvg.setInitialAriaContext→updateAriaLabel在workspace_svg.ts:782无条件Msg.WORKSPACE_LABEL_MANY_STACKS.replace，因undefined抛TypeError。此前大量headlessWorkspace测试不走SVG，未覆盖。以现有Vitest+锁定JSDOM运行真实browserWorkspaceFactory（无Blockly/SVG API替身）精确复现，补locale后真实inject成功。该源缺陷解释创建后画布无法初始化，但在新Windows通过前不把它冒充旧CI唯一根因。

最小修复：WorkspaceManager导入锁定本地blockly/msg/zh-hans，在inject之前setLocale，namespace仅传string消息以兼容包的ESM/CJS类型声明；没有新网络/依赖/资产授权。现有workspace-manager.test补一项真实3页SVG初始化与中文region/零块figure aria回归，没有另造runner。该回归移除setLocale时同782.replace明确FAIL，恢复后与symbols共14PASS。开发中一处测试精确翻译预期误写“工作区”，库实际“Blocks工作区。”，改验证中文工作区语义；一次TS报synthetic default不满足string字典，改为明确string筛选，失败日志保留。

最终PASS：固定workspace XDG/UV_OFFLINE=1 `pnpm exec vitest run packages/block-library/workspace-manager.test.mts packages/block-library/symbols.test.mts`（14PASS）；`pnpm check`；`pnpm --filter @easyai/desktop build`（实际Vite含本地locale与原nonce插件）；git diff --check。JSDOM初始化不冒充实际Windows或CSP验收。Monaco只读语义修正e108保留，删除/错误定位/Undo/全部恢复断言不延时、不删减。下一项正常合并推送两修正，自然有界Windows dev/package CI，旧失败/原main/原件/候选保全，无训练/下载/SSH/凭据/发布。

- /tmp/easyai-browser-canvas-diagnostic-20261019.log SHA256 `8fddfc6a1888281402bafb34b1450cffcfef492ed1852c999441d552e80a7d7a`。
- /tmp/easyai-browser-canvas-locale-20261019.log SHA256 `9e1aa7ea6ef298f5b181e7bdc95358fa8e3864b6ea9ffea0bb99b40a9858dd78`。
- /tmp/easyai-svg-locale-red-20261019.log SHA256 `c2737668f25df50371b75cfaf952bae7edc60b906e5a9de998f37970c93b9113`。
- /tmp/easyai-svg-locale-final-tests-20261019.log SHA256 `c35e377978b7a8dbe11ea3c5a067795e96efff24c0974b60a9b1bf2da0ed10d7`。
- /tmp/easyai-svg-locale-check-final-20261019.log SHA256 `e580f738fb6f2a6bfe01cc5daae5d3e702f5220b2ad112eafff67fad6afa0a95`。
- /tmp/easyai-svg-locale-build-20261019.log SHA256 `de1f00a1c132cf8bdc8ed84df158a0cf14d59ece9c45e23fbb78d33da8756fff`。


### locale修复后第二轮实际CI（仍待新首错）

产品HEAD/remote `b71c8c7d8d85527e199517918b255f4d3ed5c3a1`，[CI39239060925](https://github.com/T1doo/Easy-AI/actions/runs/39239060925)：Linux job118015170294完整SUCCESS（含新增真实SVG regression、原check/test/build）；Windows job118015170748原项目/native cache+trust/冻结/backend/desktop build检查SUCCESS，step14开发E2E FAIL。实际候选构建/审计/包内E2E/上传SKIPPED，无新候选。旧首错不能替代本轮首错，不能假设仍train_data不存在或认定locale为旧CI唯一原因。

已请父级已登录浏览器提供本轮step14首失败断言、行号、expected/received和调用日志；该读取状态pending，本执行器既有logs/artifacts/browser拒绝限制不变，未重试/绕过，未盲重跑workflow或降低UI断言。指定源修复已由本地真实inject红绿、独审无P1/P2、实际Vite build和LinuxCI验证；完整Windows编辑闭环仍FAIL/未验收，packaged UI NOT RUN。下一操作仅据本轮实际首错定位并继续正常修复。

当前无真实训练/下载/SSH/凭据/发布变化；main/原件未动，工作区证据本地提交后clean，该结案证据不单独push触发CI。此前e108与e400已随正常源码push保留到远端。


## 2026-10-19 当前Monaco EditContext只读公共语义与真实输入验收

父级读取CI39239060925/job118015170748 step14首错：startup.spec.ts:128，Monaco容器toBeVisible已PASS，后续textarea.inputarea属性检查element not found/5000ms，非原train_data首错。来源https://github.com/T1doo/Easy-AI/actions/runs/39239060925/job/118015170748。Blockly语言初始化缺陷与红绿证据保留，不回退产品。

版本核实：锁定Monaco0.57.0 view.js依据effectiveEditContext创建NativeEditContext或TextAreaEditContext；当前Chromium支持native，nativeEditContext.js创建div，另有aria-hidden的IME textarea，不存在旧textarea.inputarea。两实现分别由native/screenReaderSupport.js:90–95和textArea/textAreaEditContext.js:131–137暴露role=textbox、aria-multiline=true，且aria-autocomplete直接由真实EditorOption.readOnly决定none/both。因此原私有textarea选择器不适用，上一轮e108属性值修正不足；没有产品可写缺陷证据。

本次仅修现有E2E：真实Monaco容器内唯一可访问textbox、multiline与readOnly派生公共ARIA状态；focus并断言实际聚焦，CtrlHome确认真实渲染首行，记录Monaco实际可见代码，键盘插入sentinel后两帧render屏障并确认逐行不变，再全选Delete、CtrlHome恢复viewport、同样确认实际渲染不变。不是扩大selector后跳过加载/只读门，不使用隐藏fallback替代此行为检查，不使用monaco实例私有属性、CDN/新runner、产品test hook或强制旧输入模式。原真实Monaco/CSP/定位/Undo/生成全文/工作区/保存重开断言均保留。

独审无明确P1/P2。PASS：固定workspace XDG/UV_OFFLINE=1 pnpm check（/tmp/easyai-monaco-editcontext-check-20261019.log）；prettier与git diff --check。本执行器无显示服务，真实键盘行为和完整Windowsdev/package验收仍NOT RUN，须看本次一次自然CI。无数据/训练/SSH/凭据/权限/CSP/sandbox变化。

- /tmp/easyai-monaco-editcontext-check-20261019.log SHA256 `e580f738fb6f2a6bfe01cc5daae5d3e702f5220b2ad112eafff67fad6afa0a95`。


### EditContext公共语义/行为断言后的实际CI结果

产品HEAD/remote `e03ac95540c5cd20c739c7289a199f65b3e447ee`，[CI39239859806](https://github.com/T1doo/Easy-AI/actions/runs/39239859806)：Linux job118017764812 check/test/build完整SUCCESS；Windows job118017764526原项目、native cache/trust、冻结与桌面build检查SUCCESS，step14开发态E2E FAIL，后续候选构建/审计/包内E2E/上传SKIPPED，无新候选。没有实际新首断言正文，不能据step状态声称只读行为已通过/失败，也不能沿用上一轮私有textarea首错。

已请求父级已登录浏览器读取本轮step14首断言、行号、Expected/Received与完整调用日志，状态pending；既有日志接口拒绝限制保持，未重试/绕过/盲重跑。锁定版本源码证明两EditContext公共textbox/ARIA路径，实际键盘行为仍待该首错进一步核验，完整编辑闭环未验收，packaged UI NOT RUN。独立审查本次diff无明确P1/P2，本地pnpm check PASS不替代Windows结果。

本地与remote产品源码一致、工作区clean；此证据单独本地提交不push额外CI，main仍5323f86232529efcfb52131168ad049f01b219f3。原件、旧候选和两轮失败保持。真实SSH/MNIST/TST33/许可未完成；未执行训练/数据下载/凭据/发布或改安全权限。


## 2026-10-19 收敛Monaco几何绘制与语义映射验收

父级已登录浏览器补CI39239859806/job118017764526 step14首错：startup.spec.ts:187，semantic装饰first() 14次解析到div.cdr.monaco-source-selected-semantic但hidden，5000ms；不再是输入textarea。来源https://github.com/T1doo/Easy-AI/actions/runs/39239859806/job/118017764526。本轮只读ARIA、真实输入/删除保持代码、nonce标签检查均已经越过，但完整流仍FAIL，旧结果保留。

统一源码审查发现确定的CSP渲染冲突：锁定Monaco decorations.js把whole-line的left:0;width:100%拼入HTML style，.cdr CSS只有absolute/height，style-src不允许属性式内联样式时空背景无宽；viewOverlays行高/位置、选择区、行号等也经同一viewLayer HTML入口，不能只给selected类补width并忽略其余CSP日志。规范依据https://www.w3.org/TR/CSP3/#directive-style-src-attr。

一次本地真实headless Chromium（已有系统二进制，Playwright chromiumSandbox:true）诊断未能启动：系统SUID sandbox helper配置不满足而SIGABRT；日志/tmp/easyai-csp-decoration-diagnostic-20261019.log。没有关闭sandbox、chmod/setuid/安装浏览器或重试替代安全选项；不能称本地真实浏览器验证通过，此为本地环境阻断、不阻现有Windows CI。

最小受控适配集中在已有style-nonce-adapter：固定viewLayer.js SHA256c0ce32a0030014328b6f9045e96a0163ae85bda0317c3db2e4e32c881e54e485及三个精确唯一sink，build源漂移拒绝。导入monaco-geometry只供该锁定renderer：在HTML解析前按opening tag/quoted attribute识别style并转私有索引，仅接受有限布局数值(px或0，width100%，幅度≤1e7)、固定absolute/isolate；拒任意背景/颜色/URL/重要性/未知属性/非法数值/marker/重复或非支持属性形式；parse时不存在style属性，再CSSOM写入同一布局值。保留替换/追加/失效行语义，失败前不替换旧内容。此函数不是通用HTML/CSS授权或清洗API，未暴露IPC；原CSP/nonce/bridge/sandbox与私有状态门不变，无unsafe-inline/eval。

E2E仍要求真实可见paint，并加强：由真实编译map消费的selected文本取得Dataset声明；真实Monaco行与非零背景矩形位于viewport，Y对齐、实际颜色正确；先选loader再点该代码行，反向导航必须回原Dataset ID。不是class存在代替映射，未删只读/源码/定位门。统一审查后续诊断、同data页Undo、根顺序规范化后的全部字段/位置/连接、保存重启，暂未发现新的确定误断言，保留严格检查。失败时立即附固定错误类别/CSP标志（不输出原异常/路径/凭据），避免首断言隐藏先前渲染错误。重启失败不再finally重复close已经关闭的旧app。

PASS（固定workspace XDG/UV_OFFLINE=1）：pnpm check；pnpm --filter @easyai/desktop build（真实Vite已命中三个受审sink）；pnpm exec vitest run apps/desktop/src/monaco-geometry.test.mts apps/desktop/src/monaco-controller.test.mts apps/desktop/src/monaco-mapping.test.mts apps/desktop/electron/style-nonce.test.mts packages/block-library/workspace-manager.test.mts packages/block-library/symbols.test.mts（25PASS，分别验证受限样式转换/失败原DOM不变、三sink/hash漂移、映射/生命周期与真实SVG/稳定引用，不冒充GUI）；git diff --check。独立只读安全审查未见P1/P2，另5PASS验证适配/几何合同（不相加刷总数）。当前实际Windows及packaged UI仍待一次正常CI，不改测试等待或屏蔽CSP。无训练/数据/SSH/凭据/OS权限/发布变化。

- /tmp/easyai-csp-decoration-diagnostic-20261019.log SHA256 `822be89ef62f06d8ee67810dbc8ad6875dd48623a47ca99048ca14f63fc9a3ba`。
- /tmp/easyai-monaco-geometry-unit-20261019.log SHA256 `46156a2278b006de1df27f24472b3ff0c0bc3b7496e1e3723b5da0d3bedec40d`。
- /tmp/easyai-monaco-geometry-check-20261019.log SHA256 `e580f738fb6f2a6bfe01cc5daae5d3e702f5220b2ad112eafff67fad6afa0a95`。
- /tmp/easyai-monaco-geometry-build-20261019.log SHA256 `5094bb6f9f558a7544c17857159356826ce2d87539d0764322b7186ae017eb6a`。
- /tmp/easyai-monaco-geometry-final-tests-20261019.log SHA256 `c61bcae2c1dd1715f322d7a59613cc7c374720cd0997e6e92300a0f8540b0e81`。
- /tmp/easyai-monaco-geometry-independent-d2s1U2.log SHA256 `4777309fb90dd5e448c873cd7a9ac82fc0f2764e571e3cb94e26c3e48f50180d`。


### M4/M7 指定真实编辑与错误修复切片最终接受证据

产品HEAD/remote `6e2be20efa54eb0c8253dc3f13bb37a29592f6b1`，[CI39241524644](https://github.com/T1doo/Easy-AI/actions/runs/39241524644) Windows job118023240831、Linux job118023241242全SUCCESS。Windows step14开发态完整E2E PASS，step19实际candidate executable设置EASYAI_E2E_PACKAGE后的同一完整E2E PASS；app.isPackaged/ASAR/沙盒/bridge、真实后端权威编译/持久化均验证。step17实际ZIP435253885字节、SHA25669c358da9e0db34efd67893e926b78112de3910b2a1115a6596e75d45e113e00，step18包内backend、step20上传留存SUCCESS；原项目/native cache+trust/冻结/保护门全保留SUCCESS。Linux pnpm check/test/build全SUCCESS。没有下载/本地独立重验ZIP，仅读允许run/jobs元数据与实际audit输出。

操作闭环：新建并打开示例副本→真实编译→本地Monaco只读ARIA/键盘插入+全选删除保持代码/nonce/CSP→Dataset真实语义行/paint尺寸颜色viewport对齐与代码点击反向定位→删Dataset→实际自动保存后编译REF_NOT_FOUND/DATASET_REF、阻止运行→点击源积木到DataLoader→Undo恢复原ID→再编译→完整code相同→切模型页保存→正常退出重启→三工作区块字段/坐标/连接/引用、tab/codeVisible/revision恢复再编译code相同。仅根数组按ID排序，无字段/位置忽略，无硬编码编译结果，无训练或数据。具体命令/路径/证据边界见docs/candidate-windows-6e2be20.md。

独立审查集中修复无P1/P2，实际25项本地针对性测试和独立5项不冒充WindowsGUI。此前Blockly缺locale、textarea私有假设与CSP装饰失败记录全保全；本轮实际两模式通过才标此切片闭环，非所有M4/M7或完整v0.0.0。冻结trust模块存在仍只证明入包，顺序key竞争/锁合同仍不是完整跨进程SSH验收。

环境断连通知后的真实恢复证据：2026-10-19T11:01:29Z同/workspace/Easy-AI执行date/git status/完整HEAD/日志SHA/git ls-remote exit0；HEAD与remote同6e2，工作区clean，既有本地check/build/测试命令在通知前已返回exit0，日志SHA不变。未另开写入实例、杀未知进程/删锁或重跑CI；CI状态没有被当作环境恢复证明。

main仍5323f86232529efcfb52131168ad049f01b219f3；原plan116185字节SHA256dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43、原规格/README/依赖锁保持。最终证据仅本地docs正常提交，领先remote产品一条，避免专为证据多跑CI，提交后工作区clean。下一项真实SSH/MNIST/硬件/TST33/许可各自NOT RUN，须各自最小目标/条件/授权，不以这些阻塞独立UI工作；完整A/B未完成。没有真实训练、下载、外部SSH、凭据/权限/共享环境改变或main/force/PR/Release/部署/付费。


## 2026-10-19 M4/DoD 从空白工程用真实工具箱构建CNN

父级接受6e2be20efa54eb0c8253dc3f13bb37a29592f6b1与CI39241524644有界编辑切片，无P1/P2；本地证据4b159e4d293bcd7fb729a8e955ea9f9d9c201c9c保留，remote原6e2、main不变。新指定目标是从空白工程真实工具箱拖入/连接/注册/引用→合法编译→层参数shape诊断→修复→保存重开，不等于已有示例修改流或全部M4/M7。已有editor-workflow.integration用newBlock/setFieldValue构图，属于真实backend但headless路径，不算鼠标UI，故不重复该程序构图当作本目标。

扩展现有Playwright runner（原CI dev/package均执行，无新runner）：新增blank-cnn场景，从backend“新建空白工程”并确认三页初始全空；通过实际treeitem工具箱、鼠标拖拽与Geras连接口，创建6data块/6model块/1train块，名称Prep/TrainData/TestData/TrainBatches/TestBatches/ToolboxCNN，通过原注册面板改名并注册，真实下拉选择对象引用与train/test角色。构建Conv(1→16,3,pad1)→ReLU→Pool2→Flatten→Linear3136→10，实际字段弹窗设数值，训练loop选该模型和两个loader但不启动训练。合法编译后验证实际代码含自建名称/Conv/3136→10，改变Linear IN_FEATURES=3135要求精确SHAPE_MISMATCH和原Linear ID定位，修复3136再编译code全等，保存正常关闭/重开后完整workspaces与code全等。

Canvas helper仅观察实际SVG DOM/路径/矩阵并发送mouse/wheel/keyboard/menu动作；没有调用Blockly创建/加载/设置字段/连接方法，没有给renderer注入最终图/模板/编译结果。物理连接坐标由锁定Geras实际notch path前缀和screenCTM读取，detached SVG path只测前缀长度，不挂入工作区；源码确认notch宽15、对应左右path，检查drop后新真实ID/连接层级，最终只读持久化JSON核对type/连接/字段和引用。使用滚轮实际平移SVG，未用JS强设workspace位置。

提取现有Electron launch/项目picker为共享夹具，旧示例编辑/Monaco/CSP/恢复场景全部断言保留；chromiumSandbox:true、15s启动超时、测试隔离userData与仅项目openDirectory选择保持。原生系统对话框由测试限定返回临时目录，没有验证真实OS dialog可操作，边界继续明确；不以它阻止其他UI验证。没有生产改动（当前未发现新产品缺陷）；新测试180s有界，原场景120s/runner workers1/retries0/原15min CI保留，无新增下载或云资源。

PASS：固定workspace XDG/UV_OFFLINE=1 pnpm check（/tmp/easyai-toolbox-check-final-20261019.log），playwright test --list确认现有2个场景，git diff --check。初始只读JSON的opaque contract类型导致TS错误，改用验证id/type后的官方Blockly序列化类型用于观察断言，未修改产品合同或编译器。独立只读审查3helper/test与夹具提取无明确P1/P2；静态与源码几何不能证明实际拖拽吸附/滚轮与SVG层次，待本次一次自然Windowsdev/package CI。已知本机系统sandbox不满足，未重试Chromium或禁用沙盒；GUI本地NOT RUN。

没有真实训练、torch安装、数据/模型下载、SSH或凭据配置；没有修改CSP/权限/主分支/原方案/共享环境或创建Release/PR/部署。M4空白CNN切片待实测，完整M4/M7、真实SSH/MNIST/TST33/许可及A/B继续分别未完成。

- /tmp/easyai-toolbox-tsc-20261019.log SHA256 `5cdfe869e9d6d14bd9e6c087c45c285ea6c100c6fb9af2542caedd61efacf49d`。
- /tmp/easyai-toolbox-tsc-final-20261019.log SHA256 `4c72d3435b13b80fad9c26990004eb020bed034ba91e7a8e941650bec367cb16`。
- /tmp/easyai-toolbox-check-20261019.log SHA256 `ab863fb4dce885f657836e4e6e9d3ddd3e81e626e0b1b77002999c1f9987f674`。
- /tmp/easyai-toolbox-check-final-20261019.log SHA256 `e580f738fb6f2a6bfe01cc5daae5d3e702f5220b2ad112eafff67fad6afa0a95`。
- /tmp/easyai-toolbox-list-20261019.log SHA256 `717c39f89010828fb59c9cce535f47b2c07edc6e2dda62209b6cfef445165164`。


### 空白CNN首次Windows实测：FAIL，等待首条断言证据

源码/remote `d7451d75f29b63dfac8bafb42b6667e8f2b7e16b`，保留上一证据提交4b159e4d293bcd7fb729a8e955ea9f9d9c201c9c。[CI39243887949](https://github.com/T1doo/Easy-AI/actions/runs/39243887949) Linux job118030992186的pnpm check/test/build全部SUCCESS；Windows job118030991821 step14 pnpm test:e2e为FAIL。前置项目持久化/native cache与trust安全/冻结backend/HTTP资源/desktop build/应用venv隔离门均SUCCESS，step15以后未完成，故本次无可接受新候选，空白CNN真实操作链仍未验收。不能仅凭此元数据推断失败场景、断言或产品缺陷；此前示例切片接受证据保持，不用本轮失败覆盖历史。

当前准确阻塞：需要父级在已登录GitHub页面读取该run/job/step14的首个失败测试名、test.step、Expected/Received、call log/源码行及若存在的EASYAI_TOOLBOX_RENDERER_FAILURES。已通过异步问题请求；该读取待父级，未取得结果。本执行器既有日志/artifact/browser API限制保持，未重试被拒操作、未绕过、未盲重跑CI、未修改测试门或禁用本地sandbox。未完成的实际包内操作不标PASS；独审无确定P1/P2及本地静态PASS不能代替WindowsGUI。

只读复核远端main仍5323f86232529efcfb52131168ad049f01b219f3，dev同d7451d75f29b63dfac8bafb42b6667e8f2b7e16b，原plan/规格/README及pnpm/backend uv依赖锁hash均与既有记录一致；后续只有本地docs证据提交，不为证据额外触发CI。下一项取得首条错误并按证据修复，再做一次正常开发提交的自然CI。真实SSH/MNIST/TST33/许可、完整M4/M7/A/B继续分别未完成。


### 空白CNN首错已取证，逐交互有界诊断

父级已登录云浏览器读取CI39243887949/job118030991821 step14：blank-cnn.spec.ts:16:1在“drag and connect preprocessing, register datasets and choose stable references”总180000ms超时，随后worker teardown30000ms超时；EASYAI_TOOLBOX_RENDERER_FAILURES []；1failed/1passed(3.7m)，另1error不属于test。无Expected/Received/locator栈。不是已定位的字段/拖拽产品缺陷，也不是旧Monaco失败。原FAIL与退出失败记录保留，父级继续浏览器取证，不要求用户搬日志，不重试既有受限接口。

先源审再做唯一一次正常提交的有界验证：本测试page默认交互/导航8s；Canvas每个外层动作及菜单打开、选项选择、名称提交、注册、实际mouse gesture各有15s test.step和BEGIN/PASS/FAIL固定标签，输出本临时fixture的实际SVG源/目标/scale/viewport几何。全场景180s不增，原场景和runner不削减。真实拖入/连接/字段编辑/权威编译与重开断言原样保留，没有图注入/模拟运行或训练。当前源审未找到可断言的具体拖拽/field/menu挂点，因此本轮是明确增加可观测性的诊断验证，不宣称修好产品操作。

源码明确普通action此前没有默认timeout，可能耗尽整个测试；Main正常退出遇dirty草稿会等待原生showMessageBox，原finally无界app.close可能掩盖首错，但尚不能认定上次实际发生了该dialog。现在观察native dialog仅输出dirty/active-run/shutdown-error/other固定类别并保留正常行为；仅已失败的测试cleanup精确匹配自身临时dirty标题+按钮才返回放弃草稿，正常成功关闭不替换确认。一次close链(含Main evaluate)12s有界，记录本测试创建的实际Electron PID/exit code/signal；只有实际code0且无signal才确认正常退出后删除自己的temp。失败cleanup不吞掉原错误，目录rm失败也不得覆盖原首错。正常close超时不再finally重复close；未确认退出则保留temp、不杀未知进程。

注意test.step/Promise.race超时本身不取消已派发CDP/退出请求：各interaction共享测试级AbortController，失败后禁止后续新交互，组合鼠标/输入提交之间检查abort，鼠标finally仅释放。close在超时abort后禁止晚返回evaluate再派新close。仍必须等待真实进程退出证据，FAIL日志不等于已静止，不启动并行/替代实例。

独立只读审查发现rm异常覆盖首错P2，已修；初审其余无确定挂点，修复后复核待返回。PASS：pnpm check（完整TS/ruff/mypy/contracts/fixtures/format），playwright test --list仍2场景，git diff --check。本机GUI仍NOT RUN，不绕过已知OS sandbox条件；Windows新诊断待本次正常CI，不盲重跑旧run。早先root tsc --noEmit缺项目只打印help exit1，已改用仓库pnpm check；观察dialog的TS overload初版失败，已用兼容真实重载的unknown[]转发修正并通过，所有本地失败日志保留。没有生产/安全门/依赖/原件/main/训练/SSH/权限/发布变化。

- /tmp/easyai-toolbox-bounds-tsc-20261019.log SHA256 `7ce8b2c5d6d32fae4a2f569194854eb61d6abef9344be8ef4494e21a525fac43`。
- /tmp/easyai-toolbox-bounds-check-20261019.log SHA256 `e284105680d2fcd4b8314e25bdc70fbcf92ef3e01bbc018434611fe556cbc6c0`。
- /tmp/easyai-toolbox-bounds-check-final-20261019.log SHA256 `e284105680d2fcd4b8314e25bdc70fbcf92ef3e01bbc018434611fe556cbc6c0`。
- /tmp/easyai-toolbox-bounds-check-verified-20261019.log SHA256 `e580f738fb6f2a6bfe01cc5daae5d3e702f5220b2ad112eafff67fad6afa0a95`。
- /tmp/easyai-toolbox-bounds-check-pass-20261019.log SHA256 `e580f738fb6f2a6bfe01cc5daae5d3e702f5220b2ad112eafff67fad6afa0a95`。
- /tmp/easyai-toolbox-bounds-list-20261019.log SHA256 `cba0ef52b51ecb00ca1372443c7837a9ba76c3ea9923b6f8a677baf99dd95eca`。

最终复核：独审指出平移/滚动迟返回需abort防线；当前scrollIntoView、mouse.move、wheel派发前均检查共享signal，已逐点复核，rm首错覆盖与此遗漏全部关闭，无剩余明确P1/P2。最后新增guard后tsc -p tsconfig.tests.json PASS；此前完整pnpm check PASS。仅本任务一个集成者，没有并行GUI/CI实例；下一次自然CI为诊断验证，结果仍待实际执行。

- /tmp/easyai-toolbox-bounds-abort-tsc-20261019.log SHA256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。


### 有界交互诊断CI结果：Linux/Windows FAIL，待页面首错

源码/remote `51b88075476f122966c8f685ad15a26dac78daf9`，[CI39245489686](https://github.com/T1doo/Easy-AI/actions/runs/39245489686)。Linux job118036273527 step8 pnpm check SUCCESS、step9 pnpm test FAIL，step10 build SKIPPED。Windows job118036273714 step8项目持久化、step9原生信任/NTFS安全、step10冻结后端、step11HTTP资源、step12build、step13应用venv隔离均SUCCESS，step14 pnpm test:e2e FAIL，step15—20打包/审计/包内验收/上传全部SKIPPED。没有新候选，没有将新增空白构建UI闭环标PASS。

准确待办/阻塞：父级已通过异步问题收到请求，在已登录页面读取上述Linux step9首条测试错误，以及Windows step14首个具体失败和最后EASYAI_TOOLBOX_ACTION BEGIN/PASS/FAIL、DRAG_GEOMETRY、native-dialog、PROCESS_EXIT/CLOSE证据。读取动作待父级结果；现有元数据不能证明新失败的测试名、行号、实际挂点或退出是否正常，不用运行时间推断修复有效。未重新请求受限日志/artifact API、未绕过、未盲重跑；当前不再发写入/GUI实例。

因出现新的Linux测试FAIL，授权范围内本地执行一次完整pnpm test以判定可复现性：exit0，Vitest43files PASS/1file SKIP、362tests PASS/2SKIP；Python950PASS/19SKIP/1warning；Node打包/归档36PASS。跳过项为原配置，未改测试/超时或用本地PASS覆盖CI FAIL。此前pnpm check、最后abort补丁tsc、2场景发现与diff-check均PASS；本机GUI仍NOT RUN。没有训练/数据下载/SSH/新权限/发布变化。

下一项仅按父级实际首错继续源证据诊断与修复，保持唯一集成者；旧失败/原退出超时保全，原main、文档、锁和已接受示例编辑候选保持。完整M4/M7、真实SSH/MNIST/TST33/许可与A/B继续未完成。本条证据仅本地docs提交，不为报告额外触发CI。

- /tmp/easyai-toolbox-bounds-local-test-20261019.log SHA256 `a05fb97a12eaa484523ad5f5ec4fd0555ffaaf5a06ea20c56027d1a502bc9243`。


### 实际首错闭合源码定位：画布wheel目标、退出句柄、真实IPC初始化

父级浏览器补齐CI39245489686实际错误：Windows job118036273714 step14两次physical drag PASS后，data.register preprocess Prep在Canvas.reveal抛“Canvas field was not reachable with actual scrollbar gestures”（canvas.ts101→register245→interaction19→blank99/89）。renderer[]，dirty dialog，实际owned process pid6676/code0/signalnull，但CLOSE_FAILED；1failed/1passed16.0s，不再180s/worker30s超时。实际预处理drag几何area{x158,y52.25,w539.5,h551}、target{x208,y92.25}、source{x170.800003,y59.150002,w193.600021,h50.400002}、scale0.800000012；转张量target{x385.999998,y355.450001}、source{x170.800003,y129.550003,w63.199997,h26.400009}，existingBlocks分别0/1。真实新增/连接门已PASS，不把模板预置坐标当实际位置，也不推断后续注册或编译已通过。

源码锁定Blockly13.4 core/scrollbar.ts：厚度15 CSS px，outerSvg通过insertAfter(workspace.getParentSvg())作为main SVG的兄弟，滚轮listener绑定main svgGroup。旧helper把wheel放background bottom-12，落在底部滚动条而非workspace，虽发送wheel却不进入onMouseWheel。方向已核：workspace.scrollX/Y减wheel delta，旧dx/dy正负方向正确，问题在事件目标。现在bounds交集实际panel/main background/browser viewport，排除真实.injectionDiv直属scrollbars和toolbox；reveal只在elementFromPoint命中实际main workspace的点发送真实mouse/wheel，仍最多4次手势，最后多测一次而非误判第4次结果；记录每次area/box/dx/dy，guard保留。drop后等待2rAF实际paint而非sleep。保持UI点击注册/字段编辑与所有图/ID/引用检查，没有Blockly程序注册/构图注入。

新增实际browserWorkspaceFactory SVG DOM事件路由回归（现有Vitest同runner）：scrollbar确为workspace外节点，其真实WheelEvent不触发workspace.scroll；同事件发main background恰触发一次。仅spy观察handler路由，不是实际GUI平移验收。初版错误猜注入容器类blocklyInjectionDiv被此测试准确挡住，锁定core/inject.ts实际类injectionDiv后通过，未让错误选择器进入CI。

退出报告源审：锁定Playwright1.64 ElectronApplication.process()经toImpl按guid查dispatcher，Close listener立即dispose，故close后再次app.process()可能在已移除对象lookup处抛错，与父级已确认code0后CLOSE_FAILED一致；未取得旧异常正文，不编造其message。现close前捕获同一真实ChildProcess，之后仅读它的exitCode/signal；exit0/无signal、单次12s关闭、failed dirty临时草稿边界、未确认退出保留目录、首错保全门保持，不把transport返回代替退出或额外kill进程。待真实CI确认报告。

Linux父级确证：job118036273527 step9 App.test.mts“real App DOM persistence lifecycle > exports clean noncanonical JSON byte-exact through real App, Main workflow and sidecar”，mount250 visible-tab null、调用343，1failed/361passed/2skipped，42filesPASS/1FAIL/1SKIP，单test1140ms、全Vitest11.92s，后端pytest未执行。原mount仅50轮setImmediate+fake20ms推进lazy commit，真实current() IPC未await，负载下可先耗尽fake窗口。现在临时包装同一fixture api.projects.current捕获实际Promise，在act中await真实返回，finally恢复原方法，保留lazy循环与可见断言及原测试timeout，无固定sleep、无mock已恢复session。初版复制API被既有late-preflight/project-change测试挡住，修正为同一live API，保留该红记录。

PASS：App组件/实际Main sidecar字节原样导出与真实SVG两文件34tests；完整pnpm check；git diff --check。独立只读复核4文件无明确P1/P2，真实DOM路由测试不冒充Windows操作通过。当前完整pnpm test仍运行，结束后记录；没有生产/合同/安全/CSP/依赖/原件修改。下一次仅本次有首因与本地回归支持的正常开发提交自然CI；旧run不盲重跑，真实空白CNN闭环仍待Windows dev/package，未完成M4/M7/A/B/SSH/MNIST/TST33/许可。

完整pnpm test exit0：TS362PASS/2SKIP，Python950PASS/19SKIP，打包Node36PASS；与完整check/独审一起通过后提交，一次自然CI。

- /tmp/easyai-toolbox-pan-restore-tests-20261019.log SHA256 `01cf09d93710ac039bae0a01125b6f0f6dfb88ab43b1a235c660278ecf0c6799`。
- /tmp/easyai-toolbox-pan-restore-tests-final-20261019.log SHA256 `a5c0b1190fa9fda2e3a8d88567c962e08911a4ce8a8e522e1d3612224ba053fd`。
- /tmp/easyai-toolbox-pan-restore-check-20261019.log SHA256 `e580f738fb6f2a6bfe01cc5daae5d3e702f5220b2ad112eafff67fad6afa0a95`。
- /tmp/easyai-toolbox-pan-restore-regression-20261019.log SHA256 `46724e3295f59fbcee3b5c707cb78d25344f44785416788565a6d9d6cc967257`。


### 画布/IPC/退出修复CI：Linux全通过，Windows首错待取

源码与remote `3660c544e4a6a2cbbd928a9e07a60113a413f8ef`，[CI39246877327](https://github.com/T1doo/Easy-AI/actions/runs/39246877327)。Linux job118040832261 check/test/build全部SUCCESS，原可见性与字节原样导出断言保留；不将单次成功称绝对消除全部异步风险。Windows job118040831757前置native安全/冻结backend/HTTP资源/build/venv隔离门均SUCCESS，step14 E2E FAIL，后续打包、审计、包内验收与上传未执行，仍无新候选。

已请求父级在已登录页面读取该Windows step14最后ACTION/REVEAL_GEOMETRY/DRAG_GEOMETRY、首错调用栈、PROCESS_EXIT/CLOSE_CONFIRMED/CLOSE_FAILED。当前读取待返回，准确挂点未知：不能从step失败推断Prep注册已过或仍失败，不能将source修复当真实GUI通过，也不能将旧已确认exit0借给新轮。未重试受限日志/artifact接口、未绕过、未盲重跑CI，停止依赖首错的修补。

工作区提交前复核dev remote同源码，main仍5323f86232529efcfb52131168ad049f01b219f3；原plan/原规格/README/pnpm与backend uv锁SHA全部与基线记录一致。当前仅本地docs证据提交，不触发另一次CI，旧失败与所有本地日志保留。下一项取得实际新首错并按源码证据修复。真实空白构建闭环、完整M4/M7、SSH/MNIST/TST33/许可/A/B仍未完成；本轮没有训练、下载、真实SSH、权限/凭据/共享环境/main/发布操作。


### 空白画布区域计算统一审查与本地真实SVG DOM回归

父级已登录页面取得CI39246877327/job118040831757 step14新首错：首个data.drag预处理流水线在Canvas.bounds抛“Canvas has no usable visible interaction area”（evaluate59→drag173→interaction19→blank90/89），尚无DRAG_GEOMETRY。renderer[]、pid2836/code0/signalnull、CLOSE_CONFIRMED；1failed/1passed15.5s。故退出句柄修复已有真实执行证据，而新区域算法回退到第一步，不能说注册已过。上次bounds在异常前没输出各原始矩形，哪个读数实际折叠区域未取得，不编造Windows scrollbar坐标。该旧FAIL保全。

本轮先统一源审而非再单点盲试：错误算法把horizontal/vertical scrollbar根SVG的top/left当成整块遮挡边界，并把无overflow裁剪语义的panel盒当强clip。锁定Blockly13.4 css明确scrollbar background opacity0/pointer-events:none，实际paint仅handle部分；根SVG viewport不是不可穿透的整个屏障，因此它的边界没有资格直接截断整个主工作区。新独立、只读且原样serialize进renderer的inspectCanvasGeometry测量main SVG/background/browser viewport/toolbox，保留48px最小区域门；scrollbar根与实际handle、transform/display、flyout、panel全部先输出为EASYAI_TOOLBOX_CANVAS_GEOMETRY再判断。缺main/toolbox/零尺寸仍拒绝，没有回退硬编码可用区域。

bounds在DOM滚动后等2rAF实际layout/ResizeObserver，不用固定sleep/放宽总时限。实际wheel仍只在elementFromPoint命中主workspace的点派发，drop目标在打开flyout前也必须实际命中同workspace；source必须visible，field点击仍受原Playwright接收事件门约束，不force。不能把粗frame矩形当作每一点可点击，实际hittest/动作/新增连接图门共同验证。保留4次wheel/8s动作/15s步骤/180s场景/12s关闭与abort/首错保全，原保存重开/图字段/ID/引用/权威编译/shape诊断/沙盒门未削减。

本地现有browserWorkspaceFactory真实3页SVG DOM场景回归PASS：未提供布局引擎的原JSDOM仍无可用区域；在实际DOM节点上提供受控getBoundingClientRect输入，父级此前main/toolbox矩形+根scrollbar viewport在原点(0,0)的计算不再把area折叠，viewport缩到80时仍仅27.75高（会被48px门拒绝）。这些屏幕矩形是明确的受控计算输入，并不是声称Windows旧bar实际坐标或本地GUI像素布局。真实WheelEvent路由回归继续证明兄弟scrollbar不触发workspace.scroll、main背景触发一次。

统一独立只读复核覆盖bounds/reveal/drag/field与后续完整路径：Geras notch/15偏移与screenCTM、drop后2rAF、flyout分类manifest顺序/各源单行默认高度、对象注册/名字blur与稳定引用、模型6块合法3136shape、3135精确诊断定位/修复与保存重开；未发现新的确定P1/P2或错误强约束。真实Windows拖拽、平移与可达性仍待CI，受控矩形测试不冒充实际GUI。没有调用程序化图/注册/参数注入。

PASS：完整pnpm check；真实SVG DOM/计算回归9tests；最后tsc -p tsconfig.tests.json/格式/diff-check。前次3660 CI Linux完整check/test/build已SUCCESS，后端/产品均无本轮改动，不额外重复950个未变Python测试。本机无Xvfb/DISPLAY、已有Chromium sandbox条件不满足，仅读本机工具/权限状态，未启动新GUI、禁用sandbox、改setuid或增加权限；本地实际GUI仍NOT RUN。下一次仅本轮明确修正非法几何假设、完整审查与回归后的单次自然CI；原run不重跑，原件/依赖/main/真实训练数据/SSH/发布边界保持。

- /tmp/easyai-toolbox-viewport-local-20261019.log SHA256 `bfd440de4bbd22c711398c49f3d4b16d393407d73e123e9c262b9f4e41005b9b`。
- /tmp/easyai-toolbox-viewport-check-20261019.log SHA256 `e580f738fb6f2a6bfe01cc5daae5d3e702f5220b2ad112eafff67fad6afa0a95`。
- /tmp/easyai-toolbox-viewport-regression-20261019.log SHA256 `922af7fe6c5ba3a51f1373c8eb129dce76bc104d2b9ef70baa2f767495e6801d`。
- /tmp/easyai-toolbox-viewport-final-tsc-20261019.log SHA256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。


### 统一几何审查后单次CI：Linux全SUCCESS，Windows新证据待父级

源码/remote `3dd9d04b60ef7aa51cd5bf34479508227b52566d`，[CI39248297720](https://github.com/T1doo/Easy-AI/actions/runs/39248297720)。Linux job118045533158完整check/test/build SUCCESS；Windows job118045532427前置native安全/冻结/backend/资源/build/venv隔离成功后，step14 pnpm test:e2e FAIL；后续打包验收未完成，无新候选。此次仅在统一源码审查和本地真实SVG DOM/受控矩形计算9PASS、check/tsc/格式/diff-check后提交的一次自然CI，未盲重跑旧run或开第二实例。

已请求父级登录页面读取该step实际首错、最后ACTION、门前CANVAS_GEOMETRY与REVEAL_GEOMETRY/DRAG_GEOMETRY及退出标志，当前待返回。新日志前置到区域门之前，但本执行器还没有取得这些实际数值；不能从单step FAIL推断是否通过bounds、Prep注册或后续字段，也不再以源假设代替实际矩形修补。停止进一步CI，先核新事实再决定修复。此前真实退出CLOSE_CONFIRMED仅属3660轮，不能冒充本轮退出结果。

边界：本机实际GUI因既有sandbox/无display条件仍NOT RUN，没有禁用沙盒或权限安装；真实SVG DOM受控计算不算像素布局/拖拽验收。原失败、字节原件、依赖锁/main、现有安全与验收门保持；本轮没有生产图注入/程序注册、训练、数据下载、SSH、发布或付费动作。当前仅本地证据docs提交，避免为报告额外触发CI。下一步所需的准确操作是父级读取上述Windows step14新几何和首错，状态待完成；完整空白CNN、M4/M7/A/B/SSH/MNIST/TST33/许可仍未验收。


### 实际zoom遮挡首错：统一字段命中与真实平移避让

父级浏览器读CI39248297720/job118045532427 step14：两次physical drag PASS，Prep注册header.click8000ms超时；字段visible/enabled/stable，但zoom-in sprites.svg所在g transform=translate(574,406)持续拦截pointer。canvas.ts271，reveal box{x629,y517.75,width63.20001220703125,height16}，dx19.20001220703125/dy0；renderer[]，pid8500/code0/CLOSE_CONFIRMED。故本轮已越过bounds且真实拖入/连接门返回，但此前reveal只看矩形进入viewport便完成，不能证明实际点击可达；原FAIL与正常退出证据保全。

统一修复reveal完成条件而非修改产品zoom：新只读fieldHitPoint在实测字段矩形3×3候选上查询elementFromPoint；editable控件必须命中字段自身子树，注册静态header/为连接准备的header可命中同一owner block路径。只有原完整viewport边距条件和实际命中点同时满足才返回全局坐标；若被遮挡，把字段center通过真实wheel平移到一个实测可命中的main-workspace点，至多4手势，控件原样保留。若部分字段可点，可选实测命中位置，绝不force click或修改DOM控件、程序选择/注册。保持诊断hit分类/矩形/原始viewport日志。

新clickField统一dropdown、number、SHUFFLE与注册：editable用真实字段locator在命中位置点击；静态header处用其真实owner block locator在同一物理点点击（相对当前bbox），避免只读文本/底层block path接收语义不符。所有click保留Playwright receives-events gate，bbox await后派发前检查共享abort。reveal所有消费者逐一接入，未留下旧默认center click；普通HTML inspector输入/checkbox、菜单option、tab、compile等继续原接收事件检查。

系统审查后续同类风险：固定zoom与兄弟scrollbars不属于field/owner，必须拒绝；editable不能把另一个同block字段当成功；root点击必须同owner header点而不是子block；pan点实际属于mainworkspace，wheel只平移且不触发选择；DOM/iframe坐标均为同renderer CSS viewport，relative position从当前receiver box换算；连接notch/main target命中门、实际注册/引用字段/模型参数/精确shape/修复/保存重开仍保留。4wheel/8s动作/15s步骤/180s场景/12s单次正常退出门未扩大。

本地实际browserWorkspaceFactory三页SVG DOM中，使用真实zoom-in image与workspace节点、父级字段矩形和明确受控elementFromPoint输入，回归全遮挡无命中、部分遮挡拒绝被盖center并选择真正可接收点、无遮挡接受。JSDOM无真实像素/命中引擎，以上只是分类计算回归，不冒充GUI避让成功；没有向E2E注入图或选中。新测试初稿局部document造成TDZ，单测与TS准确阻断，改fixtureDocument后通过；红日志保留。

PASS：完整pnpm check、现有SVG/geometry/命中9tests、diff-check；独立只读审查无明确P1/P2，并独立执行相同9PASS（不与本地9相加刷数）。本轮仅测试helper和测试场景改变，产品/安全/CSP/后端/依赖/原件不变。下一次仅本轮实际zoom首因支持的正常开发提交自然CI，旧run不重试；本机实际GUI仍NOT RUN，所有正式空白CNN/M4/M7/A/B、真实SSH/MNIST/TST33/许可未验收。无训练/下载/权限/共享环境/main/发布变化。

- /tmp/easyai-toolbox-occlusion-tests-20261019.log SHA256 `8b2ff81ace90a7e15198e942546c38a432c831bd600c82bf130bf25fa37bff4c`。
- /tmp/easyai-toolbox-occlusion-tests-final-20261019.log SHA256 `57717d185289e7530f84558d3ea32fae95d4176239fd8364fb8fb71bf824f495`。
- /tmp/easyai-toolbox-occlusion-check-20261019.log SHA256 `88a4326969cfae90aa6526cd8ad03eca9f029faf19b8e3159c253cef10e2aecc`。
- /tmp/easyai-toolbox-occlusion-check-final-20261019.log SHA256 `e580f738fb6f2a6bfe01cc5daae5d3e702f5220b2ad112eafff67fad6afa0a95`。
- /tmp/easyai-field-hit-independent-OUUlgg.log SHA256 `2e8f4fc1c92e8c1215ad78a96f0d385f9588be9a7d0ac17c153a91818a91f2f5`。


### 统一字段命中修复CI结果与取证边界

源码/remote `df1434114a470ef1d23e49459c5e96c772aaad5d`，[CI39249659748](https://github.com/T1doo/Easy-AI/actions/runs/39249659748)。Linux job118050049666 check/test/build完整SUCCESS；Windows job118050050131 step14真实开发态E2E FAIL，前置native安全/冻结/backend/资源/build/venv隔离成功，后续打包验收未执行，无新候选。

已请求父级在已登录页面读取该step首个错误、最后ACTION、REVEAL_GEOMETRY的hit/point与canvas几何、退出标志。动作待父级完成；现有元数据不能判断Prep/引用/数字/checkbox的哪个步骤失败或哪个门已通过，不能把源修复或旧轮CLOSE_CONFIRMED借为本轮证据。停止进一步修补和CI，先核此轮真实失败；没有盲重跑或重试受限日志/artifact/browserAPI。旧原始FAIL与本地红绿/独立日志均保留。

本轮统一实际命中修复、9项本地与独立回归以及完整check通过不冒充GUI成功。后续仍保留真实click/注册/引用/权威编译/shape/重开门，不以放宽测试换通过。当前只有本地docs证据提交，工作区提交后clean、领先remote一条，main/原件/依赖不变。完整空白CNN/M4/M7/A/B、真实SSH/MNIST/TST33/许可仍未完成；没有训练/下载/权限/凭据/共享环境/main/发布或付费变化。


### Inspector逻辑选择与Blockly焦点分离：实际事件红绿与完整回归

父级已登录浏览器读取CI39249659748/job118050050131 step14：`select object for registration Prep`动作PASS；随后canvas.ts299的Inspector精确原始ID断言失败（`:scope > small`元素不存在，5000ms），实际命中point{x676.4000091552734,y525.75}/receiver field。renderer[]、pid980/code0/signalnull/CLOSE_CONFIRMED。未取得当时完整focus事件时间线，不能武断声称是某一个具体focus瞬间；保留原FAIL。本轮先核实际Inspector源码：small确实是aside直接子元素，旧启动场景仍通过，不能只换selector就宣称修复。

源码证据：锁定Blockly13.4 FocusManager在HTML输入框获得焦点时对原BlockSvg调用onNodeBlur→unselect→真实Selected(null)，原WorkspaceManager无条件将它映射为React所选对象null。真实Gesture.doBlockClick另发公开Click(block)，原manager忽略。新增实际browserWorkspaceFactory/BlockSvg节点/FocusManager与HTML input.focus回归，等待真实Selected(null)事件送达屏障后，旧manager准确RED：预期原ID，实际null。修复后GREEN：保留Inspector逻辑对象直到明确workspace click/键盘焦点回到workspace root/删除原对象；实际block click选中真实存在ID，zoom click不修改图。非空Selected仍核actualblock。没有在E2E中程序化设置选择、注册、加载图或修改字段。

该本地测试仅真实SVG DOM与focus事件生命周期：挂载实际未render字段的BlockSvg根以避免JSDOM不实现的像素测量，不冒充实际Windows像素点击。早期探针缺global rAF、清理错误及仅setTimeout0未等事件队列的结果全部保留，不作为有效产品红绿；有效RED是actual-red日志，等待确切Selected(null)送达。初次完整check准确发现新测试Object.fromEntries的过宽类型断言，改为显式data/model/training对象后check PASS，没有压制TS错误。一次未带XDG前缀的prettier调用因/home/agent目录条件失败，随后只在既有workspace环境变量下执行成功；未升级权限或更改依赖锁。

Inspector原始ID/type保留真实值与原strong/small布局，增加命名只读output；三个E2E消费者统一按公开名称定位，保留精确原始ID/type断言，去除私有层级假设。审查实际注册输入、引用/数字/checkbox菜单与字段的DOM关系，继续真实用户操作及实际编译/图持久化门。blank场景新增只读64条有界focus/pointer/Inspector变更诊断，仅记录tag和测试blockID，不读输入/路径/凭据、不设置focus、不改DOM/图、不阻止事件。独立只读复核焦点逻辑与trace均无明确P1/P2，独立相关10项PASS；本地与独立数量不重复相加。

PASS命令（CI=true，XDG_DATA_HOME=/workspace/.local/share，XDG_CACHE_HOME=/workspace/.cache，UV_CACHE_DIR=/workspace/.uv-cache，UV_OFFLINE=1）：完整`pnpm test`：44文件PASS/1skip，363 TypeScript PASS/2skip，950 Python PASS/19skip，36 Node打包测试PASS；最终完整`pnpm check`：桌面/合同/E2E TS、Python lint/type、合同/实际序列化fixtures与格式全部PASS。`git diff --check` PASS。本机真实GUI仍NOT RUN（既有sandbox/无DISPLAY约束），没有禁用sandbox或绕过日志/artifact接口。下一步只为本轮明确源码缺陷及红绿回归推送一次自然CI；旧run不重跑，新的Windows真实注册/完整空白CNN仍待验收，不能以本地焦点测试替代。

提交前HEAD9cff87b1ccb21d86f88d1d75e8dbf39235cd4542，remote dev为df1434114a470ef1d23e49459c5e96c772aaad5d；前者是保留的本地证据提交。main仍5323f86232529efcfb52131168ad049f01b219f3；plan116185B及README/原规格/两个锁SHA与原记录完全一致。完整M4/M7、真实SSH/MNIST/TST33/许可/A/B仍未验收；无训练环境安装、数据下载、共享环境/权限/凭据/main/部署/发布变化。

- 有效RED `/tmp/easyai-inspector-focus-actual-red-20261019.log` SHA256 `628af8be5a05b2b7360ff38189b27e6fff231f8192934c22b244b14e52c76076`。
- GREEN10项 `/tmp/easyai-inspector-focus-final-20261019.log` SHA256 `67e9036dd9885dd3bd2b3cc59910e4e34728dea8f45f78ed655b606ac5ecd25e`。
- 独立10项 `/tmp/easyai-inspector-focus-independent-IUQW64.log` SHA256 `704b3c58c7bc9ab09de7bdfd091b1796129fdce7aa2a98188b8c608d156f2a51`。
- 最终check `/tmp/easyai-inspector-selection-check-final-20261019.log` SHA256 `e580f738fb6f2a6bfe01cc5daae5d3e702f5220b2ad112eafff67fad6afa0a95`。
- 完整test `/tmp/easyai-inspector-selection-regression-20261019.log` SHA256 `826982dfff9e3e73668e0d2ee7885550aaba6edca05280a8903c766e7919dd98`。


### Inspector焦点修复提交与单次CI：Linux成功，Windows待实际首错

源码与remote dev为`fef98b5ee46a1e2fa796ae6faa5f5915149e6f0b`，[CI39252719456](https://github.com/T1doo/Easy-AI/actions/runs/39252719456)。Linux job118060232079 check/test/build全部SUCCESS；Windows job118060231722前置native安全合同、冻结后端、HTTP/资源、桌面build与venv隔离成功，step14 `pnpm test:e2e` FAIL，后续打包/包内E2E/审计上传未完成，无新候选。只在明确源码缺陷、实际事件红绿、完整回归与独立审查后推送这一次自然CI，旧run未重跑。

已通过待答请求请父级在已登录页面读取该Windows step14的首个错误/调用栈、最后ACTION、前后新增SELECTION（inspected/active/targetBlock）、REVEAL_GEOMETRY及PROCESS_EXIT/CLOSE_CONFIRMED/CLOSE_FAILED。状态为待读取；元数据不足以说明Prep是否越过、本轮是否正常退出或新阻塞位置，不以旧轮exit0借作本轮证据。受限日志/artifact/browser API未重试或绕过；取得准确新首错前停止依赖它的修改/CI。新trace是观察，不代替点击与真实图/编译断言。

本地最终`pnpm build` PASS（既有应用依赖与PyInstaller，没有torch/训练/下载），类型声明修正后相关`pnpm exec vitest run packages/block-library/selection-focus.test.mts packages/block-library/workspace-manager.test.mts`10PASS；`pnpm exec playwright test --list`准确列出两个场景，不代表GUI执行。本地完整check/test结论见上条。原件/README/原规格/依赖锁与main保持；本地GUI仍NOT RUN，完整空白CNN/M4/M7/SSH/MNIST/TST33/许可/A/B均未验收。此处仅本地docs证据提交，不为报告触发第二次CI。

- build `/tmp/easyai-inspector-selection-build-20261019.log` SHA256 `b342221fdd317318757bb3f2b8dc872cf964af08231319b6499a1dfe1b8f8c72`。
- 最终10项 `/tmp/easyai-inspector-selection-final-targeted-20261019.log` SHA256 `ff57a03f47747456de3146c7a0343d85509466bdcc276b178b980532b89488d5`。
- 场景发现 `/tmp/easyai-inspector-selection-e2e-list-20261019.log` SHA256 `cba0ef52b51ecb00ca1372443c7837a9ba76c3ea9923b6f8a677baf99dd95eca`。


### 注册事务统一审查：真实受控checkbox RED/GREEN与身份/引用/撤销回归

父级取得CI39252719456/job118060231722 step14准确新证据：select object Prep、rename object Prep均PASS，inspected保留原预处理ID；首错register object Prep的locator.check（canvas.ts311:59，blank144/134），真实“供本项目引用”input click已完成但checked未改变。renderer failures[]、dirty native dialog、pid2432/code0/CLOSE_CONFIRMED。本轮确认选中修复已越过原挂点，而未取得的后续完整SELECTION原文不臆造；旧FAIL保留。

先审查完整事务：真实input onChange→action→WorkspaceManager.register→setRegistration同步loadExtraState，再经真实Blockly BlockChange异步changed→onChange/refresh→React props echo receive。根因是checked读取缓存symbols，action原本仅setError('')，未同步更新快照；React在事件回调结束恢复受控旧checked时，真实block已经registered=true，但onRefresh尚未送达。rename不同：输入本身同步setName，不能从checkbox失败反推rename失败；引用provider读取实时manager.symbols，改名与注册均不换目标ID。

新增真实ProjectEditor React DOM+真实headless WorkspaceManager/Blockly回归（只替换像素renderer，未替换register/rename/事件/序列化）。6种对象原实现全部有效RED：同步真实checkbox.click后manager registered=true但DOM checked=false，准确定位到受控恢复；没有强设checked/派发假change/睡眠。生产修复仅action成功后setSymbols(instance.symbols())，从真实对象同步发布快照，未绕过字段/角色校验或BlockChange保存/Undo。相同6项GREEN，取消注册同样同步反映；等待实际onChange送达后验证真实serialized graph与ID。

统一回归共新增10项：6类transform/train-test dataset/train-test loader/model；真实名称input输入→Enter/blur→立即注册（无timer），再实际Undo两次/Redo两次，名称/注册状态/原ID/TRANSFORM_REF均精确保持；名称冲突、角色冲突拒绝且真实图不变；readonly DOM禁用且图不变。联合既有FigureInspector/manager/focus/symbols共47PASS。独立审查确认checkbox P2关闭、无新增明确P1/P2，独立新10PASS，不将同一测试重复加总。E2E依然真实click/check：新增注册前真实Blockly NAME文本提交断言、注册后原ID再核验；最终图保存/重开/编译/shape/安全门不减。

PASS（CI=true、XDG_DATA_HOME=/workspace/.local/share、XDG_CACHE_HOME=/workspace/.cache、UV_CACHE_DIR=/workspace/.uv-cache、UV_OFFLINE=1）：完整pnpm check；完整pnpm test（45文件PASS/1skip、373 TS PASS/2skip、950 Python PASS/19skip、36 Node PASS）；pnpm --filter @easyai/desktop build；最终新10项；git diff --check。新测试类型笔误JSD、fields为unknown的访问及初次spread写法被check如实阻断，改JSDOM并先核字段是对象后才spread，最终check全过，未压制类型错误。真实GUI仍NOT RUN（既有本机sandbox/display条件），DOM回归不冒充Windows点击验收。

提交前HEADcbefd5594d488080520e027abb3f356031368c30、remote dev fef98b5ee46a1e2fa796ae6faa5f5915149e6f0b，保留本地证据提交；main5323f86232529efcfb52131168ad049f01b219f3未变。原plan/原规格/README/锁SHA再次全部相同。接下来仅为该已实证缺陷推送一次自然CI，旧run不重试；完整空白CNN/M4/M7/SSH/MNIST/TST33/许可/A/B尚未验收。没有训练安装/数据下载/真实SSH/凭据/权限/共享环境/main/发布操作。

- 6项RED `/tmp/easyai-registration-checkbox-red-20261019.log` SHA256 `2369a5bd96ccf46734c2026f898e102f4c8bec74792d6f3a97e7ef3635e5d208`。
- 6项GREEN `/tmp/easyai-registration-checkbox-green-20261019.log` SHA256 `4817dbddf1ec2bc66dc4a8cc059ec7b8b5cce13e859ab01009a4d4c1a2890ffa`。
- 联合47项 `/tmp/easyai-registration-transaction-20261019.log` SHA256 `3d879fa2ab52a862e810ec818c6318d6757696eff1228ac0565ffe365b482ea0`。
- 独立10项 `/tmp/easyai-registration-independent-MSQI5C.log` SHA256 `d7abad65274b866d416214e50a598abf25bac7061477fe4e5aee011d14cc9787`。
- 最终10项 `/tmp/easyai-registration-final-targeted-20261019.log` SHA256 `4abfd34f42344316b02341187dcdfd721df269c5d1368807154bdc8d7735c82d`。
- check `/tmp/easyai-registration-check-final2-20261019.log` SHA256 `e580f738fb6f2a6bfe01cc5daae5d3e702f5220b2ad112eafff67fad6afa0a95`。
- test `/tmp/easyai-registration-full-test-20261019.log` SHA256 `3f7e6f39955a39eebcfdd12fad03ae7aff9badc2fa7edbeae1248a5a92be8c46`。
- desktop build `/tmp/easyai-registration-build-20261019.log` SHA256 `edf17c425104724e31ab68f1d9a4261e9d941974fcfc7e4a6ff83231d122dd05`。
