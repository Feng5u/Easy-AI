# 真实 MNIST 小样本 CPU 验收：单次后端切片 PASS

## 2026-10-20 03:55 UTC：新实例真实执行结果

父级转达用户03:44明确批准在独立目录重建原锁定训练环境，并接续唯一一次真实MNIST quick。本次实际产品源码为 `352c91014f5e4c517b8339b15adbcbad19c955db`，对应[CI39357036818](https://github.com/T1doo/Easy-AI/actions/runs/39357036818) Linux/Windows全部SUCCESS；未退回旧实现、修改产品代码或借文档提交触发重复CI。原计划、规格、README和两锁保持。

已安装：独立CPython3.11.17及原CPU锁21包，torch2.10.0+cpu、torchvision0.25.0+cpu、NumPy2.4.2、Matplotlib3.10.8。Python归档来自固定uv0.12.23的[官方元数据](https://raw.githubusercontent.com/astral-sh/uv/0.12.23/crates/uv-python/download-metadata.json)，20261003 Linux x86_64 install-only归档30,785,899字节，本地SHA256 `aadcba18994cb8f9ee752aceb31d61e04f75b5d900d76fb575c6fbfabadec434`匹配；安全路径/链接检查后解包，许可说明保留。全部21个wheel来自原来源清单，240,772,699字节，逐项SHA256、精确大小、包名/版本与展开大小通过后，uv以offline/no-index/only-binary/require-hashes同步原锁；无新增候选包或交互接受条款。依赖一致性、CPU卷积、CPU NMS、NumPy转换和Agg PNG解码PASS，无健康检查训练。系统/宿主/共享环境未安装训练包，宿主Torch spec仍None。

原先四文件已在新配置下下载成功，此轮没有重下MNIST。训练前后均核四项压缩MD5，后验还将gzip重新流式解压的SHA256与原raw逐字节摘要对照，通过；私有MNIST/raw结构只建立原raw的硬链接，不改数据内容。原训练/测试来源分别为60,000/10,000条，本次分别只用前1024/256条，未将训练集冒充测试集，不做数据/图像/权重公开再分发或猜测许可证身份。

真实链：LocalWorkspace创建示例工程→设置quick/seed42/两个loader的batch64/1epoch→保存revision2→真实Python编译器→所选独立Python及数据预检→RunService.prepare不可变快照/Bundle→RunService.start一次→真实entry/runtime协议。编排使用本实例已有Python3.12.14/Pydantic2.13.4；实际训练子进程使用锁定Python3.11.17，不把宿主当作冻结应用环境验收。执行命令经脱敏记为 `python3 -I -B <private-root>/run-real-mnist.py`；实际完整argv、脚本、日志和运行目录均保留在私有证据内。独占attempt标记在唯一start前落盘，无第二次训练或追加评估循环。

实际启动03:54:40 UTC，runId `be6f1659-082a-4fd9-96bf-04a16e919b24`，状态SUCCEEDED、exit0；含解释器启动和图表的受管墙钟10.123248秒，指标自身elapsed_seconds=0.842151752。实际device=cpu、workers0、pinMemory=false；配置设备策略auto在该CPU-only环境中实际选CPU，未使用GPU。唯一epoch的真实 `train_loss=2.2593740820884705`、`test_accuracy=0.390625`（39.0625%）、train_samples1024/test_samples256，与CSV及事件一致；这是小样本一轮结果，不作为正式十轮学习效果。

13条应用事件、9条执行事件连续且同runId，唯一epoch/completion、process_exited0、无runtime_error；普通stderr为空。最终state_dict831,555字节，SHA256 `c1cb78af5eab974e9756555c9c5b857b807bfe5f23a5939e89d1aa5a822625b2`；自身权重用weights_only加载，8/8张量有限且变化。初始基线在start前从同一生成类/seed初始化，后验重建哈希相同；没有将重建初始参数冒称另一次训练。三张1000×600 PNG实际Pillow解码通过；四产物hash/大小/producer及contributors、代码/Bundle/旧快照source-map均核验通过。

programHash `111c12137238e2a48262e95ab1d4eae8c362b4cb1d410d343a35521965fe8b75`；codeHash `8d2d72cca7de25d2d2f26a7184506ac86e8bac5e5ea9111cfdf02e2497b55d8b`；bundleHash `d5b91ba9c564ce69a2302a80f636fcfeb0572d57d6486e841f4adba091f5f53a`。私有receipt SHA256 `94f4354414eaf5beb2cdfe3cd30778842d13742030b1095038c164f9856be062`，后验核查 `9ec4e724b78b3bb5ebe4e0e8a8f2ff469e10480ad325cd752817f4c60223bf89`，实际命令全日志 `4d78162076b7e865eb22df0debe65720786642b192ea62f419e46d5c24cb3629`。

工作区已close，监督线程quiescent、持有child已退出、无本次训练/参数检查进程；清理0.002514秒，无超时或取消。新输出在receipt时1,327,569字节，后验保守总占用2,219,333,988字节（包括Python、wheelhouse、缓存、环境、临时文件、数据硬链接重复计量及原数据），分别低于256MiB和5GB。此结果仅关闭真实小样本后端执行切片，不代表实际GUI点击映射、干净机、真实SSH、正式10轮或完整A/B通过；不造百分比或将旧合成数据结果改名。

## 历史：首次授权与代理失败

以下旧章节保留准备时的历史状态；当前缺项已从“授权/来源”变为“允许取得数据的路径”。父线程01a14dbf-e27d-721e-888a-587c8c296022转达用户允许寻找公开真实数据，随后明确批准一次CPU quick：最多1024训练/256测试、1epoch、batch64、seed42、600秒加30秒清理、新输出256MiB、既有训练根总5,000,000,000字节；不新增依赖、不用GPU、不改共享环境。训练/测试集分离，不重复合成TST34，也不作为正式10轮/完整A或B验收。

父线程核对 [torchvision官方MNIST源码](https://docs.pytorch.org/vision/stable/_modules/torchvision/datasets/mnist.html) 与 [CVDF托管说明](https://github.com/cvdfoundation/mnist)，批准固定HTTPS源 `https://ossci-datasets.s3.amazonaws.com/mnist/` 四文件。父线程提供的压缩完整性MD5如下（不是数字签名；本机尚未取得文件，未完成校验）：

| 文件 | 官方压缩MD5 |
| --- | --- |
| train-images-idx3-ubyte.gz | f68b3c2dcbeaaa9fbdd348bbdeb94873 |
| train-labels-idx1-ubyte.gz | d53e105ee54ea40749a09fcbcd1e9432 |
| t10k-images-idx3-ubyte.gz | 9fb629c4189551a2d022fa330f9573f3 |
| t10k-labels-idx1-ubyte.gz | ec29112dd5afa0611ce80d1b7f02629c |

来源页面无登录或单独接受条款步骤，CVDF说明获Yann LeCun许可托管。原作者站点父线程未成功读取，未确认具体数据许可身份，不能称CC0/GPL等已核；只在隔离私有目录验收，不再分发数据/权重/样本进公开仓库。

本轮真实命令：`python -B /workspace/easy-ai-training-cpu/download-real-mnist-001.py`，**FAIL，exit1**。目标仅第一个文件 `https://ossci-datasets.s3.amazonaws.com/mnist/train-images-idx3-ubyte.gz`。`urllib.request` 经当前配置代理建立隧道即返回 `OSError: Tunnel connection failed: 403 Forbidden`，外层 `urllib.error.URLError`；不是文件HTTP正文校验失败或训练失败，也不是自动审批审核拒绝。没有调用提权、镜像、替代下载工具、跳转或重试。

已创建独占私有 `real-mnist-data-001/MNIST/raw`，其中数据文件0个，仅根下 `failure.json` 与 `blocked-receipt.json`；原FAIL回执保留，completedFiles=[]。新输出 `real-mnist-a-001` 未创建，准备训练脚本未执行，真实训练 **NOT RUN**。下载脚本预设先MD5、再有界解压并核IDX magic/维度/数量/长度/标签范围，随后原样落raw文件；这些步骤均未到达，不能记PASS。下载脚本SHA256 `f5d17bdcf777b62303b287859762a2fb380b7783e57a4cf6976dbb96c3b3956f`，原准备脚本SHA256 `1e8561427d70f2e1c2c9787b5bab4808445f6cf05a5ddea53b18e519d042d5cd`。脚本、失败回执均仓库外保留。

本地只读PASS：branch/remote HEAD均 `985f99bcc5b54f9bfd177770da73575d9a006707`，main仍 `5323f86232529efcfb52131168ad049f01b219f3`；开始工作区干净，无其他真实训练/sidecar/git写进程；既有CPU metadata torch2.10.0+cpu/torchvision0.25.0+cpu/Matplotlib3.10.8，未导入torch或安装依赖。原训练根逻辑1,989,886,593字节，磁盘余量18,851,844,096字节（下载前检查），未扩大原预算。原计划116185字节/SHA256 dade1fcaadac319e130de415b48154601254dcae9b148a2d42475fb82205fa43及规格/README/两锁不变。

下一项：父线程处理明确目标的代理拒绝，或提供经批准且能在本执行器取得、可按上述校验值验证的四文件交接。一般“继续推进”不解除拒绝；本次不自动重试或将合成数据代替真实验收。授权已具备，无需再次索要相同训练授权。实际来源映射GUI点击、参数变化、PNG解码、产物manifest及真实指标均仍NOT RUN，不能借先前合成证据回填。

## 历史准备记录（新授权前）

2026-10-20 仅只读核对授权/已有记录，没有搜索私人数据目录、读取真实 MNIST、下载、安装或训练。产品源码仍为已验收 `41b736b532e008634d01821b02a8d7b493351fcb`；该源码 CI39346965518 全 SUCCESS。本页不是实际验收 PASS。

## 当前缺失项

没有用户明确提供且允许本次使用的真实 MNIST 绝对根目录，也没有真实数据训练的样本/轮次/时间/新输出目录授权。已知 integration-005 与 tst34-standalone-001 的回执明确属于合成 IDX，不能重标为真实 MNIST；模板中的 data 路径也不构成数据来源或使用授权。原 CPU 合成范围及基础运算检查授权不自动扩为真实数据训练。

已有独立 Linux CPU Python 与 torch/torchvision/Matplotlib 可复用，不需要新增训练依赖。下一最小输入是：已准备数据根目录、来源/使用许可范围、明确同意一次 quick CPU 验收及预算、新私有输出目录。当前缺项为待用户提供，不是数据文件不存在的全盘搜索结论或新工具拒绝。

## 待确认的单次范围与命令

建议 quick 模式、seed42、batch64、最多1024训练/256测试样本、1epoch；总执行预算600秒，另留30秒取消/清理；新测试根最多256MiB，既有训练根总5GB门继续保留。全部是建议，尚未得到真实数据执行批准。保持 download=False，不复制/改写原始 IDX、不安装或修改共享环境。正式10轮另行确定范围。

仓库外已准备防误执行脚本 `/workspace/easy-ai-training-cpu/real-mnist-a-ready.py`，仅 ast.parse 和静态审查，**没有执行**。使用真实 LocalWorkspace 创建/保存 quick 工程→Python编译→选择已有CPU解释器/明确data根→预检→RunService→事件/CSV/图像/权重/源码映射及退出检查，不调用会生成合成数据的 pnpm test:integration。现有CPU-only版本必须匹配；缺授权引用/data根/新root/预算任一项即在导入应用或创建目录前拒绝。环境变量只是防误执行守门，不替代真实用户授权。

只有用户明确提供数据和批准上述范围后，才可填写并执行：

```sh
cd /workspace/Easy-AI
EASYAI_REAL_MNIST_AUTHORIZATION_REF='<明确用户批准的记录标识>' \
EASYAI_REAL_MNIST_DATA_ROOT='<用户明确提供并允许使用的真实数据根>' \
EASYAI_REAL_MNIST_NEW_ROOT='/workspace/easy-ai-training-cpu/real-mnist-a-001' \
EASYAI_REAL_MNIST_APPROVED_SECONDS=600 \
services/backend/.venv/bin/python -B \
  /workspace/easy-ai-training-cpu/real-mnist-a-ready.py
```

新根必须尚不存在；失败/取消保留原错和私有回执，不自动重跑，不按裸PID清理。PASS只在现有服务关闭确认后发布。它仅准备门槛A的真实小样本训练证据；可点击源积木映射仍需实际桌面操作证据，不能单靠后端脚本宣称完整A，更不是B。旧artifact限制保持，不下载/改留存；新候选435256032字节/hash `abee57c5f61db79b202f876ff97858a4f1007e51c39dcb2bead276da07b614ec` 不替代旧候选。

## 仅文档推送

9ce1cc613d1cfc06a06b7704d882b155b7dc8b75 已独审无敏感内容，保留原提交SHA。本页及进度记录的追加提交使用 `[skip ci]`，仅对这次纯文档 push 跳过不必要工作流，不改CI配置，不跳过产品41b736的检查。机制依据 [GitHub 官方说明](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs)。不把文档提交的跳过状态称为新的产品CI通过。
