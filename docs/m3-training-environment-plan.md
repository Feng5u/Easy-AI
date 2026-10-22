> 后续执行更新：用户已批准本计划的独立CPU范围（下载2GB、磁盘5GB、单次30分钟），已完成受限安装与合成IDX验证；以下保留批准前计划，实际命令/失败/资源/结果见[M3执行回执](m3-cpu-execution-evidence.md)。

# M3 CPU训练环境：待确认的独立安装计划

状态：**仅只读探测与计划，未安装、未创建训练环境、未运行训练。** M2父级审查仍在进行；本计划不是M2或A/B验收通过声明。不得自动执行以下命令，也不得加入应用`pnpm setup`。本文批准对象若获授权，是当前Linux x86_64执行器的独立CPU训练环境及合成IDX执行链，不包括数据下载、教师环境、GPU、SSH或真实MNIST效果验收。

## 已有环境探测

2026-10-18 UTC，使用各解释器的`-I -B -c`执行标准库`importlib.util.find_spec`与`importlib.metadata.version`；未导入torch/torchvision/Matplotlib，未运行其代码。检查结果：

| 解释器 | Python | torch | torchvision | matplotlib |
| --- | --- | --- | --- | --- |
| 应用`services/backend/.venv/bin/python` | 3.11.17 | 无 | 无 | 无 |
| 已有`/workspace/.python/cpython-3.11.17-linux-x86_64-gnu/bin/python3` | 3.11.17 | 无 | 无 | 无 |
| 默认`/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3` | 3.12.14 | 无 | 无 | 3.10.8（仅元数据） |
| 系统`/usr/bin/python3` | 3.13.5 | 无 | 无 | 3.10.1+dfsg1（仅元数据） |

在`/workspace`、`/opt`、`/usr/local`、`/usr/lib`进行了有界venv/包文件扫描，仅发现仓库应用venv。结论限于上述可见范围：没有发现可确认健康的torch/torchvision解释器；不能把“有Matplotlib元数据”当作健康训练环境，也不修改系统或宿主工具环境。

当前Debian13 x86_64；拟使用已有CPython3.11.17，不额外下载Python。拟新建`/workspace/easy-ai-training-cpu/.venv`，探测时该父目录不存在；如果执行时已存在，先停止核对，不允许覆盖或sync未知旧环境。

## 精确候选与官方来源

| 项目 | 候选精确版本 | 已核实依据 | 尚未核实 |
| --- | --- | --- | --- |
| Python | 3.11.17（复用已有解释器） | 已有解释器实际执行标准库探测 | 新训练环境尚未创建 |
| torch | 2.10.0+cpu | 官方CPU索引存在cp311 manylinux_2_28 x86_64 wheel | wheel未下载，二进制导入/运算未执行 |
| torchvision | 0.25.0+cpu | 官方CPU索引存在对应wheel；0.25.0包元数据要求torch==2.10.0 | CPU wheel实际依赖与算子导入待验证 |
| matplotlib | 3.10.8 | PyPI该版本元数据requires_python>=3.10 | 新环境Agg渲染待验证 |
| numpy | 2.4.2 | PyPI该版本元数据requires_python>=3.11 | 与CPU组合实际运行待验证 |

这是经过版本矩阵、Python约束与官方wheel存在性核对的候选组合，不是已完成运行兼容验收。[TorchVision官方版本矩阵](https://github.com/pytorch/vision#installation)列出torch2.10对应torchvision0.25、Python3.10–3.14；[torchvision0.25.0元数据](https://pypi.org/pypi/torchvision/0.25.0/json)、[Matplotlib3.10.8元数据](https://pypi.org/pypi/matplotlib/3.10.8/json)、[NumPy2.4.2元数据](https://pypi.org/pypi/numpy/2.4.2/json)支持上述约束。

已读取[官方torch CPU索引](https://download.pytorch.org/whl/cpu/torch/)和[官方torchvision CPU索引](https://download.pytorch.org/whl/cpu/torchvision/)。索引返回如下URL及SHA256；这些是**索引声明的hash**，尚未下载wheel作本地hash核验：

```text
torch @ https://download-r2.pytorch.org/whl/cpu/torch-2.10.0%2Bcpu-cp311-cp311-manylinux_2_28_x86_64.whl#sha256=b7cb1ec66cefb90fd7b676eac72cfda3b8d4e4d0cacd7a531963bc2e0a9710ab
torchvision @ https://download-r2.pytorch.org/whl/cpu/torchvision-0.25.0%2Bcpu-cp311-cp311-manylinux_2_28_x86_64.whl#sha256=aa016ab73e06a886f72edc8929ed2ed4c85aaaa6e10500ecdef921b03129b19e
matplotlib==3.10.8
numpy==2.4.2
```

URL直接取自成功读取的官方索引，不猜测或替换下载地址。另一次读取`https://pytorch.org/get-started/previous-versions/`被网络代理明确拒绝：`Tunnel connection failed: 403 Forbidden`；未重试、未绕过该拒绝。搜索连接器此前返回空内容`isError:true`，不将其算成成功证据。安装包本身的可下载性目前NOT VERIFIED；若批准后的访问也被拒绝，停止该动作并报告，不换镜像或扩大权限。

## 锁定与安装步骤（全部待用户确认，当前未执行）

1. 审批范围应明确为：只在`/workspace/easy-ai-training-cpu`新目录下载并安装上述CPU候选及其必要传递依赖；不改应用venv、锁文件、系统、教师共享解释器或学校服务器。使用已有Python3.11.17与uv0.12.23。CPU直连wheel固定，普通传递依赖只来自PyPI，禁用源码构建，不装CUDA、torchaudio、Jupyter或额外训练框架。
2. 将上面的四条候选写为新目录内的`requirements.in`，显式指定PyPI默认索引、已有解释器与Linux目标，解析成带全部传递依赖精确版本和hash的`requirements-linux-cpu.lock`。不以requirements.in冒充完整锁。目前**未解析完整依赖图、未生成完整锁**；Pillow等传递依赖由该步骤确定，不能现在虚构版本或空间。先审查锁：排除nvidia-*、triton/CUDA依赖、未知索引/来源、sdist和意外框架；出现任何一项即停止。
3. 复核空间预算与锁后，在新目录创建无system-site-packages的venv，以`--require-hashes --only-binary :all:`同步该锁。只要wheel hash不符、来源改变、空间不足或无兼容wheel，即停止，不降级为源码构建、去掉hash或改应用环境。
4. 将锁、下载来源/hash核验结果、实际版本、空间占用与测试结果作为后续验收材料；锁可纳入独立training profile，机器绝对路径、venv、缓存、数据与运行产物不得进入公开仓库。未来若加入显式`setup:training`，须单独说明安装范围，不接入普通setup。

下面仅是待批准后的命令草案，**没有执行**（先完成上述新目录与来源检查）：

```sh
uv --no-config pip compile /workspace/easy-ai-training-cpu/requirements.in \
  --python /workspace/.python/cpython-3.11.17-linux-x86_64-gnu/bin/python3 \
  --no-python-downloads --python-platform x86_64-manylinux_2_28 \
  --default-index https://pypi.org/simple --only-binary :all: --generate-hashes \
  --output-file /workspace/easy-ai-training-cpu/requirements-linux-cpu.lock
# 审查锁及空间；不允许继承非计划索引配置，需执行前核对uv相关索引环境变量。
uv --no-config venv --no-project --no-python-downloads \
  --python /workspace/.python/cpython-3.11.17-linux-x86_64-gnu/bin/python3 \
  /workspace/easy-ai-training-cpu/.venv
uv --no-config pip sync --no-python-downloads --require-hashes --only-binary :all: \
  --default-index https://pypi.org/simple \
  --python /workspace/easy-ai-training-cpu/.venv/bin/python \
  /workspace/easy-ai-training-cpu/requirements-linux-cpu.lock
```

空间：2026-10-18 08:58:31 UTC，`df -B1 --output=avail /workspace`为30,850,088,960 bytes。**所需wheel下载大小、传递依赖大小、缓存＋展开venv峰值、真实运行峰值内存/时间均未知**，没有执行下载、完整解析或训练来测量；当前可用空间不构成“足够”的保证。建议用户若同意，另给可接受的下载/磁盘上限；未指定前不能承诺空间或自动清理其他环境。实际安装前需通过锁与官方文件大小记录估算，并保留临时文件余量；预算不明确或不足时停止安装。

## 批准后的最小验证范围

先只读检查新环境依赖一致性与CPU版本，再导入torch、torchvision并执行小张量前向/反向、torchvision基础算子（发现二进制配对错误）、NumPy转换和Agg PNG渲染，记录实际结果。失败即停，不用模拟值掩盖。

随后以标准库在新建测试目录本地生成合法原始IDX：32张训练、16张测试、每张28×28 uint8，十分类标签，固定生成规则/seed；四个raw IDX文件合计37,728 bytes。数据图案是测试构造物，**不是下载、复制或声称MNIST数据**。放入torchvision MNIST在`download=False`下读取的`MNIST/raw`结构；数据根在项目/教师数据目录之外。所有输出另建新目录，测试中文/空格路径；不覆盖现有文件。

使用真实Blockly fixture编译的bundle（仅将epochs设为1、batch设为8）执行真实CPU训练，不替换模型、优化器、指标计算或图表。核对实际非空PNG、有限epochs.csv指标、state_dict、事件/退出码、代码/source-map/hash；记录“合成IDX执行链通过”，不能用准确率作为MNIST学习效果。此安装计划和合成数据运行仍不等于M0桌面或A/B门通过；M3正式推进须先处理M2待审项。

完全不下载MNIST/FashionMNIST/CIFAR10、不连接SSH、不检测学校硬件、不改变教师数据/环境。真实MNIST效果验收仍需用户提供已准备数据及另行运行范围。

## 可独立准备的标准库协议测试设计

此处仅设计，未新增M3实现：围绕已存在合同准备runId/快照hash/revision幂等与互斥；stdout/stderr并发大流量不死锁；普通日志与结构化事件分离、单写journal与单调seq；错误payload、非法/超限事件、重复终态；退出码与取消竞态；进程异常退出后重连/恢复；旧运行只用旧snapshot/source-map；输出路径逃逸与hash验证。可用标准库子进程发送固定协议消息验证I/O状态机；它们必须标注协议测试，不能冒充训练runner或真实训练指标。
