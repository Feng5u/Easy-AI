# 发布前代码安全与演示修复（2026-10-20）

按用户“先一等、再检查几轮、检查代码漏洞”的最新要求，main合并与Release继续HOLD。以下是具体修复及其边界，不是“无漏洞”保证。所有新增验证仅使用内存ASGI、纯编译/计划、应用专有合成文件和构造替身；未执行torch.load、真实Dataset构造、训练、SSH、安装或数据下载。

## 鉴权先于请求体

固定FastAPI0.128.0在routing.py先await request.body/JSON，再solve_dependencies；原全局Depends不能阻止未持令牌的同机进程提交大/慢body占资源。该问题涉及服务可用性，不是持久数据读取或令牌绕过。依据[固定官方源码](https://github.com/fastapi/fastapi/blob/0.128.0/fastapi/routing.py#L268-L329)，本实例已核锁定安装源码的实际调用顺序。

新增纯ASGI SessionRequestBoundary，任何HTTP receive前只接受恰一份原始Authorization字节并恒时比较完整Bearer值；401固定内容、关闭连接、不读body。已认证请求先完整预读、累计实际chunk，硬限32MiB、总预读10秒，长度重复/非法/TE+CL拒绝，谎报短长度不能突破真实累计上限。32MiB是传输预算，保留原5MiB工程上限及最坏六倍JSON转义和请求外壳，并不放大领域/文件限制。

bytearray避免无限多小块对象；超限/超时在下游响应开始前单次413/408，响应发送不置于预读超时区，不继续drain。部分body断线不交下游；完整body回放一次，此后透传真实disconnect，空GET/SSE不会因永远回放空消息而忙循环。既有SSE纯ASGI夹具原receive永远等待，补上真实协议的首个空http.request后，项目切换终止剩余批次的原断言保留并通过。

内存回归覆盖未授权receive零调用、错误/重复令牌、分块/假长度/头部超额、慢体期限、断线、单一响应、空GET回放、实际5MiB合法工程compile请求及31MiB左右转义JSON。没有向真实服务发DoS；ASGI门不承诺阻止TCP慢头、任意并发或已持令牌调用方的一切资源滥用。

## MNIST/FashionMNIST 来源一致

[固定torchvision0.25.0官方源码](https://github.com/pytorch/vision/blob/v0.25.0/torchvision/datasets/mnist.py#L88-L111)会在raw读取前优先处理legacy processed缓存；download=False不禁用该分支。weights_only=True不等于已验raw来源，也不能据此称任意pickle RCE。

共享stdlib dataset_inputs拒绝processed目录符号链接/非目录、任一training.pt/test.pt（含悬挂链接），只查元数据，不读/删缓存。LocalWorkspace预检与RunService正式start都检查；实际生成构造改用继承官方MNIST/FashionMNIST的raw-only类型，固定原raw/processed目录名，_check_legacy_exist重核后恒False，_load_legacy_data恒拒绝。因此检查后新增缓存也不能切换到legacy；用父构造开始时插入无害缓存的stub证明拒绝，未调用真实torchvision。

类型为模块级惰性重建，普通应用/preflight导入不触发torch；测试核固定名称/模块查找与spawn可重建路径，没有反序列化。共享source随Bundle、冻结资源、Windows LF与远端固定probe前缀一起绑定；远端合成probe也拒绝缓存。正式start、Bundle导出及远端freeze拒绝旧编译器直接datasets.MNIST/FashionMNIST调用，保留旧快照/hash可查看，不静默重写。当前项目重新编译导出获得新helper；已经在外部磁盘导出的旧Bundle不能被本应用追溯修补，须停止用旧导出并重新导出。

此门消除了legacy选择竞态，不等于对同UID恶意进程任意替换raw内容/父路径提供完整隔离；既有raw文件安全与教师准备可信数据前提保留。CIFAR官方pickle/fullMD5门不变。

父级在55d6797独审发现确定P2回归：新增公开helper导入名construct_dataset不在保留词中，合法同名模型class会覆盖它；纯编译/AST检查仍通过，构造数据集才TypeError。改为生成代码内部别名_easyai_construct_dataset，沿用既有用户名称必须以英文字母开头的规则，保留原合法模型名；不扩大前后端保留词。两种数据集的因果stub回归先真实TypeError、修复后通过，只执行实际生成import/class定义/两条构造语句，没有main/model实例/torch/数据内容读取。既有绑定覆盖测试补查所有import/as绑定；其余新增helper均在独立sidecar/helper模块，无用户模型共享绑定。旧Bundle拒绝回归保持有效。

## 产物计划与安装来源预算

原300epoch/每轮一图的工程可编译，而远端第257条artifact及64KiB receipt/cache index会拒绝，可能留下未封存/未知状态。新增纯预算检查按before + epochs×body + after +最终model计数（quick按1轮），同时保守计算owner UTF8 receipt与本地ASCII cache index（含optional null规范化）的较大字节数，保留256条/64KiB现有门；identity/UID/sourceSeq预留16KiB。实际figure物理路径、producer和contributors进入预算；不只按记录数或ASCII估算。编译、导出、本地正式start、远端freeze共同检查，无法完成的计划不启动。纯测试覆盖300轮、低count但receipt超额、Unicode配置、quick与正式10轮示例；不训练或远端连线。

实际PNG/权重大小仍由运行时每件/总量和完整性门检查，静态数量/登记预算不能保证任意内容体积；发生未知封存结果仍诚实显示未知，不移除完整性门或伪造sealed FAILED。

安装来源先验证所有声明路径/regular文件/精确size，再汇总bootstrap+wheels磁盘预算；模块树完整元数据计数/大小inventory也先于任何内容hash。diskBudgetBytes既有owned环境语义保留，源扫描独立受diskBudgetBytes+launcher/module各1GiB的派生上限约束，不虚构安装后体积。archive按声明size限读，tree按采样size限读并前后重核dev/inode/size/mtime/ctime；并发增长不能把每件读取量扩大为1GiB。来源hash、许可/授权、offline/only-binary、teacher只读门均未放宽。预算超额零archive/tree扫描、模块总量超额零文件hash及元数据后增长的合成回归通过，未安装任何候选包。

## 演示与证据状态

6052609的Linux完整CI成功，Windows开发E2E新增重开检查3PASS/1FAIL，未进入打包。唯一失败是约187KiB日志需六次32KiB/秒分页，而重开断言仍用默认5秒；已与read_log的真实EOF/done逻辑核对，改为与首次读取相同的15秒有界等待，不改采集预算或伪造尾部。失败正文保留SHA256 `db469ac7d911177949b39bf8cdccd7f78595ad08b09d2eb403a2be16edaa8cf0`。

独审另核实同一来源再次点击只重定位Blockly，不会使用户滚离的Monaco回到对应代码。已将显式导航版本贯通SnapshotCode→CodeView惰性初始化/effect→controller；新版本才重复reveal，同版本/普通轮询不重滚。controller因果回归先FAIL（预期2次、实际1次），再通过；真实WindowsE2E新增手动滚离→同来源→高亮回视口。原summary折叠重开修复保留，未扩大UI范围。

本轮独立只读代码复审最终ACK，不能代替运行结果。最后完整check/test、实际build与后续Windows开发态/包内E2E收据见implementation-progress末节。正式十轮、真实SSH、干净Windows11、真实安装与完整A/B仍NOT RUN；合并与Release继续等待用户。

55d6797 / CI39381413118随后为LinuxSUCCESS、Windows开发E2E2PASS/2FAIL，后续打包/包内测试/候选上传均SKIPPED，不作为可交付通过。第一处新增测试把Monaco原生DOM scrollTop=0当作虚拟滚动顶部，实际高亮仍在视口；改用真实textbox聚焦和ControlOrMeta+Home，并核顶部代码可见、高亮离开，才检查同来源重新定位。第二处原startup点击长声明整行左上角时被html/scroll-decoration阻拦；改为先显示Monaco，再对精确Dataset声明中完整可见的非空文本token正常点击，原DataLoader→Dataset反向定位断言不变。没有force、dispatchEvent、内部editor测试API或sandbox修改；新的真实Windows结果仍须绑定新SHA。

最终0e1e1b29eb356aa217a0ae133327d4e33509dd25 / [CI39383662136](https://github.com/T1doo/Easy-AI/actions/runs/39383662136)全SUCCESS，完整Linux检查/测试/构建与Windows开发态、归档审计、包内同四E2E均通过。中间e656的Linux合成握手5秒FAIL没有略过：合法串行3+3秒受控复现后只改测试整体握手同步、提前退出诊断与精确自有child清理；生产每次5秒/整体20秒门和单次启动/旧worker/授权拒绝断言不变，单stage6秒反例仍明确FAIL。该修正不声称还原原CI的精确慢阶段。原日志、全部新收据及未验边界见implementation-progress末节；没有以代码独审ACK替代实跑，也没有执行新的训练/数据/真实SSH或安装。main/Release继续HOLD。
