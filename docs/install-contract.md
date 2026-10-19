# M6.3 离线安装计划与生命周期合同

当前交付包括17包/4组目录、离线计划、明确确认、持久任务查询/取消、内部受管进程与复检适配器。**四项生产接线已有源码与受控验证，默认配置仍不授权执行。** LocalWorkspace注入ManagedInstallInspector；仅当前主机的可信离线来源配置完整、未过期且明确授权时，具体plan的executionEnabled才可能true，确认原子登记同job唯一worker并调用原execute。没有接收自由命令的HTTP execute路由。真实bootstrap/pip/安装与tensor纵向验收仍NOT RUN，不能宣称M6.3/B通过。

## 计划与确认

后端是唯一计划权威。桌面仅提交目录白名单中的 packageIds、固定 profile 和新环境名称或 owned UUID，不接收命令、索引 URL、任意 prefix 或远端目标。teacher-existing 始终只读；应用 Python 与训练 Python 分离。

新环境路径由服务在应用受控 training-environments 下分配 UUID，规划只观察路径缺失，不创建目录。当前 UI 仅提供这个入口。已有 owned 环境须在受控根下、没有末端符号链接、有精确所有权 marker，并经过可信 inspector；已接既有ManagedInstallInspector；仅受控owned目标可被只读复检，缺解释器/来源/健康证据继续拒绝。

内部 execute 现在可显式传入 bootstrap adapter，按原计划的新 UUID 创建流程运行；生产confirm已按具体plan能力调度唯一worker；默认能力禁用。OwnedCreation 在目标外建立独占 claim/内核锁，绑定UUID、jobId、planHash和应用根身份；锁后重核指纹/TTL、执行意图落盘后才独占mkdir受控空prefix。它不删除、覆盖、采用已有prefix或复用旧claim。每阶段核根/claim/prefix dev+ino，拒绝符号链接及目录替换。bootstrap必须接受已有空目录；当前只有可控标准库子进程/合成目录测试，现有精确25.9.1离线CondaBootstrap固定adapter，来源不齐/版本不符拒绝；本轮仅命令捕获与受控协议验证，没有创建实际Python环境。

bootstrap停止且nonce/sys.prefix/Python3.11检查通过，才写兼容的两字段owned marker；此前先在prefix内写origin并fsync目录。安装与最终完整复检通过后才写ready；require_ready同时核origin、claim、prefix身份、ready及持久SUCCEEDED/verified job。新job持久事件额外记录creationRequired，API DTO不变，读取兼容原无该内部字段的旧记录。claim缺失时有origin或同env新创建日志就保持INCOMPLETE，不能退回legacy接纳；缺失/冲突/取消/未知均保全目录和证据。失败的新环境不自动修复、清理或解除隔离，需要后续显式安全流程。

easyai-cpu 复用已有 Linux x86_64 / CPython 3.11 CPU 来源及 hash lock。单包请求也展示完整基础闭包，不隐瞒附带包。未锁定的可选包、平台不符或已有版本冲突产生明确 blocker，不猜版本、不自动升级。downloadBytes 是 wheel 下载元数据之和，installedBytes 是解包估计，均不是完整环境占用；未解析时为 null，不宣称零。

ML补充锁已覆盖scipy/pandas/scikit-learn及joblib/threadpoolctl；CV新增scikit-image及imageio/tifffile/lazy-loader，复用SciPy/core，按选择加入固定闭包，核心锁不变。DL补充14个固定依赖及fsspec[http]扩展，见[DL合同](install-dl-sources.md)。17卡中14卡有解析版本，其余3卡未支持。OpenCV只有候选证据，因目标系统动态库要求未核实，返回INSTALL_NATIVE_REQUIREMENTS_UNVERIFIED，不入锁、不换headless。新增wheel只有注册表下载体积，未下载测解包，ML/CV/DL/NLP计划installedBytes=null。见[ML合同](install-ml-sources.md)和[CV合同](install-cv-sources.md)。未选可选模块不进行实际import，基线版本inventory仍覆盖已知支持的distribution。

计划包含 baselineFingerprint、constraintsHash、planHash 和十分钟有效期。确认必须携带同一 planId/hash，confirmed 与 networkAcknowledged 必须是真正的布尔 true；整数 1 被拒绝。确认会重新核基线与来源 hash；重试同计划返回同一 job。固定错误码不回显用户路径、凭据或原始异常。

## 任务状态与所有权

默认未配置的生产路径只到 AWAITING_EXECUTION，明确 INSTALL_EXECUTION_NOT_ENABLED；取消后为 CANCELLED / INSTALL_CANCELLED_NO_EXECUTION，verified 仍为 false。具体可信配置及计划授权齐备时才调度唯一worker。会话最多64计划，持久目录最多64任务，当前没有自动清理历史或分页入口。任务状态复用 EventJournal 的单写入、fsync、序号及严格完整记录校验；执行意图先落盘再启动子进程。落盘失败关闭该服务的后续写入，不冒称执行成功。此处验证进程重启，不保证断电后的目录项持久性。

executor/inspector已有生产接线，内部受控替身仅用于合同测试。已有 owned 环境执行前先取得内核环境 lease、持久执行意图，再核 TTL、基线、来源及计划 hash；执行前基线probe也受同job lease/WAL覆盖。独立服务实例不能并发写同一环境。任务最多128条固定生命周期记录，受管命令另存有界原始日志。

内部状态依次为 INSTALLING、VERIFYING、SUCCEEDED，异常可为 FAILED；取消发出后为 CANCEL_REQUESTED，只有适配器证明已停止才可成为 CANCELLED。未知停止结果或执行异常保留环境 reservation 与内核 lease，不宣称已停止或可以再次安装。关闭会话发取消信号，不释放未证实停止的 lease。

重启后可从普通包管理面板有界发现任务并查看只读报告（见[历史合同](install-history.md)），但不重放安装、不按旧 PID 发信号：未执行确认作废，未确认结束的 INSTALLING/VERIFYING/CANCEL_REQUESTED 保守恢复为 CANCEL_REQUESTED/STOP_UNCONFIRMED 并隔离环境。取得环境内核锁后还会重新读其他任务的持久意图，防止早已打开的第二实例把“锁已释放”误当子进程停止。未知任务没有自动解除隔离入口；重连存活安装子进程、人工核实停止后的恢复/重建仍缺。历史列表区分本会话已登记worker、重启历史和外部实例记录；历史报告不接回执行控制。历史SUCCEEDED仅表示当时复检结果，新的安装计划仍须重新探测环境。

只有新的 nonce/prefix 匹配的可信复检、精确锁定版本、Python 3.11、torch/torchvision/matplotlib 导入和 tensor 检查都成功，内部合同才允许 verified=true。取消/失败不承诺回滚，保留 changesPossible/needsReprobe。

新增内部 ManagedInstallCommand 复用现有 ManagedSupervisor/ManagedProcess，而非第二套 Popen/进程管理器。POSIX独立进程组、取消升级、两管道排空、持久原始日志；每条stdout/stderr文件上限1MiB，超限继续排空。目标包原始输出重定向stderr，不能伪造stdout完成协议。已知非零退出判 FAILED，与未知停止区分。原训练进程默认日志行为不变，Windows安装进程入口仍拒绝。

OfflineWheelInstaller 实现固定目标 Python 的 isolated pip、require-hashes、only-binary、no-index、已提供本地wheelhouse和锁文件副本；无默认升级、自由命令/requirements URL或自动下载入口。authorized默认false；生产runtime仅在plan绑定的具体授权离线来源重核通过后构造该executor。owned marker核对后同一固定适配器可用于刚bootstrap的新目录。本轮只截获并编译该固定命令，不运行pip；来源hash也在复制lock前重核。ManagedInstallInspector 实现独立选中Python的精确metadata、实际核心imports和小CPU卷积报告；本轮仅在既有应用venv子进程做缺torch的负向只读探测。成功闭环测试仍是标准库子进程写合成inventory，再走合同复检，**不是实际训练环境安装/import成功或tensor效果证据**。

pip的isolated不等于禁用global/site配置，no-index也不移除配置追加的find-links。安装子进程在导入pip前清除所有继承PIP_*并设置PIP_CONFIG_FILE=os.devnull，禁用全部配置文件；不改宿主配置。现有base Python的pip26.2.1真实参数解析（未调用install.run）复现污染后target/远程候选链接，并验证修后只有固定本地find-links且无target/prefix。其他目标pip版本仍须兼容验证，测试机未提供pip时该可选兼容测试明确SKIP，不能算通过。依据：[pip配置文档](https://pip.pypa.io/en/stable/topics/configuration/#pip-config-file)。

## 尚缺与真实验证条件

四项代码接线、ML、scikit-image、Lightning及NLP四库固定可选闭包已实现；尚需确切可信conda/base模块及bootstrap来源配置、许可/目标/预算的真实执行授权，以及正向真实环境probe、其余3可选卡来源/系统要求核验、Main来源原生对话框真实验收（源码选择/预览/明确登记已有，见install-source-picker.md）、任务历史/保留策略、存活安装子进程重连和未知停止安全解除、远端真实目标验收以及实际owned环境纵向验收。实际安装器、probe及持久日志现在已有代码基础，但尚未完成真实依赖安装纵向验证。目录fsync仅用于本地origin先于owned marker的顺序，未据此签完整跨目录断电恢复保证。

真实执行前需明确一次性 owned 环境范围、包源和下载预算，展示具体计划后再获得执行授权；SDK/许可另核。不使用教师共享环境、不在应用 Python 安装 torch、不下载训练数据。当前合同/组件/Main/冻结 sidecar 测试均不执行这些动作。

生产接线审计与最小实施顺序见 [install-production-wiring.md](install-production-wiring.md)：审计基线的四项缺口已有本轮实现；配置格式及精确官方行为依据见install-runtime-configuration.md。默认授权门继续关闭，真实安装验收仍缺。

关闭先设置取消（包括planning inspector），总等待预算从mutex获取前开始；超时保留journal/lease，不将取消请求当静止证明。worker和pipe owner已确认退出且无未知lease后才关闭journal。plan在source散列返回后的最终保存边界再核close请求，迟到结果拒绝。

每次baseline/bootstrap/final probe持有独立receipt和本job取消token，保留其实际supervisor；静止须同时证明leader退出、reader/monitor/cancel线程结束及owner关闭。探测异常不能沿用上一条安装命令的静止结论；未知时保留lease、receipt和journal，不写ready。同prefix存在未确认静止的receipt时拒绝新probe，其他prefix独立；close显式取消所有receipt，单job取消不传播到其他job。规划/确认尚无job的未知probe也阻止关闭与同prefix重入；不自动退休或推断可安全重跑。


远端owned安装通过同一InstallService目标适配接入，计划仅接受已保存目标和当前认证会话引用。来源/根/预算来自私有operator策略，真实执行默认关闭；唯一writer/预留WAL/阶段intent/取消与未知隔离、只核验收口及固定实际复检接口见[远端合同](remote-install.md)。合成协议不是安装/ABI通过，未替代剩余3卡与真实课堂/SSH验收。

NLP 整批默认闭包裁决已接SentencePiece、spaCy、Transformers、Gensim的来源/预算/原安装器与选中import复检；NLTK候选安全阻断，HanLP三个依赖仅sdist而不支持。模型/语料API不提供，普通import零联网与ABI仍未验，详见[install-nlp-sources.md](install-nlp-sources.md)。14/17卡仅为元数据能力，非实际安装或B验收。
