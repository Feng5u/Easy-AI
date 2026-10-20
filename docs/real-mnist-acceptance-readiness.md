# 真实 MNIST 小样本 CPU 验收：已授权，首次下载被代理拒绝


## 2026-10-20 新授权与实际结果

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
