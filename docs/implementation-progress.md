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
