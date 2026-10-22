# Main 原生本地来源选择与登记

当前源码有普通入口：打开“受控包安装计划”→“选择本地离线来源”→Main原生文件对话框选择可信操作者准备的私有JSON清单→只读来源/预算预览→勾选明确确认→登记本机CPU来源→重新生成原安装计划。不是逐个选任意二进制后自动推断信任的向导；来源真实性、许可与实际执行授权仍由独立操作者负责。本轮未选择真实来源或打开真实Electron窗口。

基线9bb093d64bfcc0c6d71de2762d6c2f0ef570712a先核完整Main树：main.mts原有工程/数据/Python/私钥等showOpenDialog，workflow/preload/bridge及包管理只有catalog/plan/confirm/get/cancel，没有等效install-source入口或install-runtime.json配置选择。新增固定Main回调及两条IPC，复用原后端runtime manifest验证、InstallPlan及唯一worker，没有另建包解析器或安装器。

## 选择与预览

操作者清单沿用[原私有配置合同](install-runtime-configuration.md)：准确conda25.9.1，launcher实际path/SHA/bytes，moduleRoot完整tree hash，bootstrap档案、本地wheelhouse、预算、时限和带时区authorizationExpires。原件须当前用户拥有、私有regular文件、受保护祖先、无symlink；应用不会替用户chmod、补hash、信任URL、安装或下载缺失文件。普通入口选择清单，无需手动把它覆盖到应用配置路径。

Renderer只传白名单packageIds；路径只能来自Main固定JSON原生选择器，不接收renderer路径/命令/index/权限字段。既有IPC sender/frame校验、sandbox/contextIsolation等门不变。Main记录本次backend和previewId/hash，backend变化、dispose、新选择或取消后旧收据不能确认。原生取消不调用后端确认，不改变现配置。

后端沿用OfflineConfiguration与InstallRuntime.inspect_source，实际核launcher、完整模块、bootstrap与选中wheel闭包的hash/bytes/身份和磁盘预算，不加载或执行它们。未知/不支持包仍按原ML/CV规则拒绝。预览只给文件名/校验值、档案与wheel字节合计、解包占用未知、磁盘预算/命令时限、源授权原截止和预览截止，不把“哈希相符”等同“来源可信”。私有完整路径留在Main/后端，未返回renderer。

预览是本会话单收据，最多60秒且不跨原authorizationExpires，同时用monotonic deadline限时。绑定原清单真实SHA/身份、全部已验证源、目标原配置字节/身份、应用根身份、包选择与预算。取消/只预览不写install-runtime.json。原件/模块/档案/wheel/预算/源权限/原配置替换、过期或关闭请求变化，确认须重新核验并拒绝陈旧收据。

## 明确登记与独立授权

确认只接受本次previewId/hash和严格布尔confirmed=true，不接受任何替换路径或执行授权字段。服务锁、独占配置提交内核锁与来源/目标/根身份门下重核，私有临时文件fsync后原子发布配置并fsync目录；成功重放只返回同一结果，不再改文件。发布后结果不明时记录COMMIT_UNCONFIRMED，当前会话不自动重试或继续写来源；需先核现配置，不猜动作未发生。

**登记始终写executionAuthorized=false，即使所选清单声明true也不搬迁这个授权。** UI在确认前明确说明该行为。预算、命令时限与authorizationExpires原值原样保留其时间含义，不延长、不增加权限。登记只写固定应用配置路径，外部来源清单原件保持不变。后续只有操作者对本机已登记的具体来源独立授权，原InstallPlan执行门才可能启用；仍须重新预览和明确确认具体安装计划。此入口不是接受许可或授权真实安装的快捷方式。

配置文件真实身份也进入runtimeFingerprint；登记或外部替换配置使旧计划失效，不能沿用旧planHash。UI登记成功即清空旧计划/确认，刷新能力并由用户重新生成计划。默认缺配置和新登记都禁用执行，不创建环境、不调度安装worker。

## 活任务、关闭与跨实例

本实例有活任务、lease、probe或未知停止时拒绝换来源。对先前已打开的另一服务实例，还在提交锁下通过原EventJournal/read_install_job重读持久INSTALLING/VERIFYING/CANCEL_REQUESTED意图。安装execute写INSTALLING WAL短持同一提交锁，先发布持久意图后才释放；配置确认持锁检查意图再发布，消除“检查后才新增writer”的空隙。锁只覆盖交接，不把不同环境的整个安装串行化。

跨实例只读planning probe不是安装writer，也不被此配置锁视为静止证明；其原owner由各自服务保留。来源变更时已有配置指纹计划须重新核验；未知安装意图不能仅因内核锁已释放而解除。关闭在等待服务mutex前置请求标记，迟到预览或发布前已观测关闭须拒绝；已经明确确认并越过原子发布点的结果不能承诺撤销。Main对迟返确认再核epoch/backend/收据，过期会话不当作当前成功。

NOT RUN：真实来源配置/授权、真实原生对话框、launcher/conda/pip执行、下载/安装/训练/probe、SSH、凭据或新权限。合成测试只核固定IPC、只读hash/identity/预算、私有配置登记和原计划守门，不冒充真实来源信任或安装验收。完整M6.3/B仍未验。
