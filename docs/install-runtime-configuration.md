# 本机离线安装 runtime 合同

当前源码已接四项M6.3缺口；默认不执行。应用私有根内的`install-runtime.json`只有由可信操作者独立提供、来源完整且明确授权时才有执行能力，普通工程/Renderer/API不能提交这个配置或任意命令。**本轮没有创建实际配置、运行conda/pip、下载、安装或训练，真实兼容及tensor安装验收NOT RUN。** 受控测试中的inventory和conda文件占位明确不是有效安装包，不可用于实际能力配置。

支持合同固定为Linux x86_64、目标CPython3.11.17与现有CPU wheel lock，conda准确版本25.9.1。版本依据是精确官方tag：`main_create`对已有非环境目录经确认继续，对已有conda环境可能删除，因此adapter必须核本次claim与空prefix，拒绝已有/未知内容，无force/clone/删除回退。[main_create](https://raw.githubusercontent.com/conda/conda/25.9.1/conda/cli/main_create.py)

本地`@EXPLICIT`文件含file URI和SHA256，固定无位置包参数、no-default-packages；官方纯explicit分支绕过solver。[explicit解析](https://raw.githubusercontent.com/conda/conda/25.9.1/conda/misc.py)、[安装分支](https://raw.githubusercontent.com/conda/conda/25.9.1/conda/cli/install.py)。CLI参数说明页标题是25.9.1.dev4，只作参数参考，行为裁决取精确tag，不扩大支持范围。[create参数](https://docs.conda.io/projects/conda/en/25.9.x/commands/create.html)

配置模型`OfflineConfiguration`只接受以下字段（这里列结构，不提供虚构hash、来源、体积或可用配置）：

| 字段 | 核验 |
| --- | --- |
| schemaVersion / condaVersion | 1 / 精确25.9.1；其他版本拒绝 |
| launcher | 已获准base Python的绝对规范path、实际sha256和bytes；无默认launcher或PATH猜测 |
| moduleRoot / moduleTreeSha256 | 显式conda及其依赖模块目录，全树相对路径+实际文件SHA256的规范digest，最多10000项/1GiB；无symlink及不安全祖先；需要可信操作者确认来源，版本字符串不替代来源信任 |
| bootstrap | 完整已备本地conda档案清单，每项path/实际sha256/bytes；包含python-3.11.17和pip及完整依赖；只允许.conda/.tar.bz2；不解析网络包源、不猜缺失依赖 |
| wheelhouse | 已获准的本机目录，必须包含现有CPU sources清单全部精确filename/hash/bytes；未解析可选包仍block |
| diskBudgetBytes / seconds | 明确磁盘预算上限和每个受管进程1–3600秒预算；均进入runtime指纹/planHash，UI展示；不是总磁盘占用的虚构估计 |
| executionAuthorized / authorizationExpires | 默认false、严格布尔及有时区失效时间；表示此主机具体来源的独立授权，仍需本次计划确认。过期/来源漂移拒绝，不自动刷新授权 |

配置是当前用户私有regular文件，同O_NOFOLLOW fd核owner/mode/大小/稳定身份。launcher、模块、档案、wheel逐级核可信owner/无group-other写，继承已有受保护祖先及可信sticky临时根规则。文件身份、来源配置、实际hash和预算绑定runtimeFingerprint，再与基线/constraints绑定planHash；确认和内核lease后执行前重核。config缺失仍可离线规划/登记，但executionEnabled=false，没有worker或环境创建。配置损坏/来源不齐拒绝，不自动修复或下载。

bootstrap以已批准base Python的`-I -S -B`启动，禁site/.pth，显式添加完整hash核过的moduleRoot；准确conda版本及模块路径核验先于CLI。既有ManagedProcess增加可选环境白名单seam，默认训练行为保持；安装命令不继承CONDA/PIP/PYTHON/XDG/proxy/LD变量，使用独立HOME/tmp/cache、pkgs/envs路径与condarc，禁外部plugins、默认包、更新、notices及共享环境注册。`CONDARC`本身不能排除所有全局配置，因此固定wrapper限制Context的搜索路径，覆盖CLI再次初始化，其他版本不使用该补丁。[Context接口](https://raw.githubusercontent.com/conda/conda/25.9.1/conda/base/context.py)、[CLI重初始化](https://raw.githubusercontent.com/conda/conda/25.9.1/conda/cli/main.py)

只使用同一个ManagedInstallCommand/ManagedSupervisor进程owner；固定argv含offline/no-default-packages/copy/json/yes/prefix/file，不允许自由索引/命令。yes只用于本次已核空目录的创建确认，绝不授权接管已有conda环境。服务的claim/lease/inode guard紧贴exec和返回边界；conda退出0仅证明该受管命令退出，之后还要独立nonce/sys.prefix/Python版本及最终精确版本/import/实际CPU tensor复检才写ready。bootstrap、pip源和日志均保留，不自动删除失败/未知环境。

离线标志约束包管理器解析，不是OS网络隔离；已批准包与base解释器/标准库仍是信任边界，真实来源/许可/目标授权不可被hash或合成测试替代。磁盘检查有界扫描本次prefix与受管命令目录，不承诺硬实时quota；超预算/进程或SDK停止不明拒绝健康态并保留lease。

确认在同mutex内持久登记并注册唯一job worker，重放不spawn；后台只调原InstallService.execute。默认未配置分支仍AWAITING_EXECUTION。每job取消token也传给inspector；关闭先发全runtime取消并阻止新操作，等待预算包含mutex/规划及worker，锁外等静止；超时不关journal、不释放未知lease。重启只读恢复，不按PID或旧确认重跑。

baseline/bootstrap/final probe各有自己的owner收据；上一条bootstrap/pip退出不能证明下一条probe静止。异常后若reader/monitor/cancel线程或leader未确认退出，保留实际owner、lease与journal，拒绝同prefix新dispatch；其他prefix的取消token独立。执行前baseline先写WAL并持lease。未确认静止的规划probe也阻关闭；当前没有自动解除未知停止的入口。

UI按具体计划显示离线来源、bootstrap字节、未知实际解包占用、磁盘/时间预算和“确认执行”或“仅登记”。catalog能力不是全局授权，每份计划还受包锁、来源、基线、时效与明确确认约束。完整M6.3/B还需实际一次性owned目标上真实bootstrap/pip/复检验收；本轮没有该执行授权。
