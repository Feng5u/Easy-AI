# CIFAR10 本地预检：结构检查与未完成的安全构造边界

原计划 D10、§9.1、M6.1 要求三种官方 Dataset 适配器、CIFAR10 的 `[3,32,32]` 输入语义与 `download=False` 的真实构造探测。MNIST/FashionMNIST 原有本机 IDX 文件头/长度检查保持；本片不将它们或 CIFAR 的结构检查称为学习效果验收。

当前本机入口复用 Main 原生目录选择产生的 data selection ID，HTTP 不接收任意 data path。按已保存工程编译 IR 确定数据集名称；CIFAR10 的数据根目录应包含 `cifar-10-batches-py/`，其中固定五个 `data_batch_1..5`、一个 `test_batch` 与 `batches.meta`。只读检查目录、普通非链接文件、打开前后 fd 身份、重复 inode、粗大小和两字节 protocol-2 前缀。每批次只读两字节；不遍历样本、不扫描全数据哈希、不下载或解压，也不导入 torch/numpy/pickle。批次粗大小 30,720,000–40,000,000 字节、元数据 16–65,536 字节；它们只是提前拒绝明显错误，不证明批次内容、完整性、样本数量、shape、dtype 或 label 正确。

缺文件返回 `DATASET_MISSING_NO_DOWNLOAD`；不安全路径/别名返回 `DATA_PATH_FORBIDDEN`；粗格式不符返回 `DATASET_CIFAR10_FORMAT_INVALID`。全部初检符合仍返回 `DATASET_CIFAR10_SAFE_PROBE_REQUIRED`、`data.ok=false`，不能得到 `DATASET_READY`。本机 start 走同一门，拒绝发生在训练依赖探测、准备 Run 或启动训练前。数据检查 checkpoint 和启动解释器前重新核项目代次/revision；失效不启动旧选择的探测。UI明确显示“未反序列化 pickle，数据未就绪”。这不是完整 CIFAR10 适配器交付。

安全构造探测目前阻塞：冻结训练 profile 对应 torchvision 0.25.0 的官方 CIFAR10 构造器会先对全部 train/test 文件计算 MD5，再对批次和 metadata 执行 `pickle.load`。`download=False` 只禁止下载，不能阻止 pickle reducer 执行或全量哈希；见[固定版本官方源码](https://raw.githubusercontent.com/pytorch/vision/v0.25.0/torchvision/datasets/cifar.py)。本轮明确禁止执行不可信 pickle，计划 §9.1 又禁止预检扫描全数据哈希，因此不能直接调用构造器后宣称满足计划。未用自制另一数据格式、MD5 白名单或 pickle reducer 白名单替代官方构造验收。2026-10-18 19:18 UTC已向用户提出窄例外裁决，目前待答；保持SAFE_PROBE_REQUIRED，不重复请求、不执行官方构造、不另造解析路径绕过。答复前停止该项实现，其他证据保留。

同一风险也存在于原远端 `runtime/probe.py` 的 CIFAR 构造分支；本片在构造前返回固定 `unsafe_format_blocked`、`ok=false`，样本摘要为空，不能产生正向数据 binding。该错误同步进公开环境报告合同。MNIST/Fashion 的官方构造探测保持原行为。此处未执行真实远端 Python 或 SSH；已有生成 Bundle 的 `datasets.CIFAR10` 代码依然依赖调用方已有训练环境及数据安全条件，本片没有验收或许可其处理任意第三方 pickle，也没有将布局初检变成可移植训练授权。

合成稀疏文件故意包含恶意 reducer 字节，仅用于证明不执行反序列化、固定文件/划分缺失与边界拒绝、取消 checkpoint、HTTP selection、start 拒绝。它们不是 CIFAR10 数据或训练指标。编译契约检查来自已有真实 Blockly fixture 的参数修改：CIFAR10 双 split、Conv2d 三通道、Flatten/Linear 2048、`download=False`；原 MNIST `1568` 不能直接用于 CIFAR。计划只要求 train/test 角色、输入格式和类别数一致，未自行新增同名数据集限制。

真实 CIFAR/MNIST 训练、真实桌面目录选择、SSH、Windows、许可/数据来源、官方构造正向测试均 NOT RUN。旧 M8 便携目录不含本片代码，也未重打包或发布。
