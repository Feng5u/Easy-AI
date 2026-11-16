# 用 EasyAI 从零搭建 MNIST CNN：积木操作教学

这次我们用积木搭一个识别手写数字的模型。给它一张图片，它要判断上面写的是 `0～9` 中的哪个数字。我们会从空白工程开始，一步步准备图片、搭建网络、训练模型，最后看看它认得怎么样。

完整示例是本目录的 [project.easyai.json](project.easyai.json)，也可以在软件里点击“新建 MNIST 示例”打开一份。我们要搭的模型叫 **`MnistCNN`**：它分两次提取图片特征，每次训练看 **128** 张图片，把训练集学习 **10 轮**。

图表可以直接放进“训练前”“每轮结束”“训练后”三个位置，EasyAI 会帮你排列并保存图片。

## 这份教程怎么用

按顺序跟着六个模块操作就可以。每一步都会告诉你点哪里、拖哪块积木、填什么，以及为什么这样做。搭完一个模块，再看看末尾的 Python，就能把积木和代码联系起来。

三个标签页各管一件事：数据页准备图片，模型页搭网络，训练页把两者用起来。后面的积木通过名字找到前面准备好的内容：

| 工作区标签 | 在这里搭什么                      | 给后面的模块提供什么                              |
| ---------- | --------------------------------- | ------------------------------------------------- |
| 数据处理   | 预处理流水线、Dataset、DataLoader | 训练批次 `train_batches`、测试批次 `test_batches` |
| 模型结构   | 模型类和按顺序连接的网络层        | 模型类 `MnistCNN`                                 |
| 训练管线   | 训练模型、三个阶段的图表          | 训练记录、图片、训练完成后的模型权重              |

图表的步骤比较多，所以单独放在模块五讲。操作时仍然留在“训练管线”标签页。

文中的 Python 来自这个示例生成的代码。为了好读，`preprocess`、`train_data`、`test_data`、`train_batches`、`test_batches` 这五个变量使用了与积木一致的简短名字；软件里生成的名字还可能带一段后缀。

代码按讲解内容分段展示，供你一边搭积木一边对照。完整运行代码可以在“代码对照”面板中查看。实际运行时，会先准备数据和模型，再展示样本、训练并画曲线，最后展示预测结果、保存模型。

## 模块一：准备工程，学会拖拽、填写与注册

### 1.1 准备好数据和训练环境

准备两样东西：老师提供的 MNIST 数据，以及能运行 PyTorch 的 Python 环境。这个环境需要装好 `torch`、`torchvision` 和 `matplotlib`。如果还没准备好，可以先搭积木，到模块六开始训练时再选择它们。

把 MNIST 数据解压后，文件夹里应当能找到下面四个文件：

```text
你选择的数据根目录/
└── MNIST/
    └── raw/
        ├── train-images-idx3-ubyte
        ├── train-labels-idx1-ubyte
        ├── t10k-images-idx3-ubyte
        └── t10k-labels-idx1-ubyte
```

例如，若文件位于 `D:\课程数据\MNIST\raw\train-images-idx3-ubyte`，稍后在软件中选择 **`D:\课程数据`** 就可以。EasyAI 会从里面找到 `MNIST/raw`。

“训练环境”就是实际执行计算的 Python 和它用到的工具包。课堂上直接使用老师准备的环境即可。

### 1.2 创建自己的空白练习工程

1. 打开 EasyAI，等待右上方出现“本地服务已就绪”。
2. 点击顶部“工程”。如果已有工程，先等待其显示“已保存”。
3. 在“新工程名称”中输入 `MNIST CNN 练习`。这是工程的显示名称，可以使用中文。
4. 点击“新建空白工程”。
5. 在目录选择窗口中，为这次练习建一个新文件夹，例如 `MNIST-CNN练习`，然后选中它。
6. 创建完成后，点击顶部“积木”，进入工作台。应看到“数据处理”“模型结构”“训练管线”三个标签。
7. 点击“数据处理”，确认中间画布为空。

工程就像这次实验的作业本，接下来搭好的积木会保存在里面。

想先看看最后会搭成什么样，可以在另一个文件夹里“新建 MNIST 示例”。看完后，回到自己的空白工程跟着做。

### 1.3 先认识四种操作

| 操作               | 具体做法                                                         | 怎么判断成功                         |
| ------------------ | ---------------------------------------------------------------- | ------------------------------------ |
| 放入一块积木       | 点击左侧分类，按住积木标题，拖到中间画布，松开鼠标               | 积木出现在画布中                     |
| 把积木放入容器     | 拖向大积木内部的凹槽，出现连接提示后再松手                       | 小积木嵌在大积木里面，不再孤立悬空   |
| 给已有积木接下一步 | 拖向上一块底部的连接口                                           | 两块上下咬合；位置相邻不等于已经连接 |
| 修改参数           | 点击白色或浅色参数框；数字和文字填完后按 Enter，下拉项则点击选择 | 参数框显示新值                       |

画布太大或太小时，先点击画布空白处，再用 `Ctrl + -`、`Ctrl + +` 调整积木大小，`Ctrl + 0` 恢复默认。光标正在数字或文字输入框内时，先退出输入状态。也可以使用画布上的 `+`、`−` 按钮。

### 1.4 起好名字，让后面的积木能找到它

例如，我们给训练数据集起名 `train_data`，再勾选“供本项目引用”，后面创建 DataLoader 时就能在下拉框里选到它。这个“让其他积木能选到”的操作，叫作**注册**。

后面提到“注册这块积木”时，就按下面的步骤做：

1. 点击该对象积木的标题或背景，选中它。
2. 如果右侧面板没有显示，点击画布上方“对象与参数”。
3. 找到“用于生成代码的名称”，填入教程指定的英文名字，按 Enter 或点击输入框外确认。也可以直接修改积木上的 `NAME`。
4. 把这块积木的其他选项填好。例如测试数据集要先选 `test`。
5. 在右侧勾选 **“供本项目引用”**。
6. 确认右侧“可引用对象”列表出现这个名字。

这些名字使用英文字母、数字和下划线，并以英文字母开头。照着教程填写大小写最方便。工程标题可以用中文，如“MNIST CNN 练习”；代码中使用的模型名字则是 `MnistCNN`。

本教程最后应注册六个对象：

| 对象名称        | 类型            | 用途                             |
| --------------- | --------------- | -------------------------------- |
| `preprocess`    | 预处理流水线    | 训练集和测试集共用的图片处理规则 |
| `train_data`    | 训练 Dataset    | 训练图片与正确标签               |
| `test_data`     | 测试 Dataset    | 用于评估的图片与正确标签         |
| `train_batches` | 训练 DataLoader | 按批提供训练数据                 |
| `test_batches`  | 测试 DataLoader | 按批提供测试数据                 |
| `MnistCNN`      | 模型类          | 要训练的神经网络结构             |

准备好空白工程后，就可以进入下一步了。表中的六项会在后面逐个搭出来。

### 1.5 对应 Python：运行时自动准备设备

开始训练时，EasyAI 会先选好用哪种设备计算，并设置随机种子。你可以先看代码里的 `device`：`cuda` 对应支持 CUDA 的显卡，`mps` 对应 Apple 的图形计算设备，`cpu` 对应处理器。软件会使用已选定的设备，或根据电脑情况自动选择。

`context` 帮我们管理这次运行的设置、记录和文件；这部分由 EasyAI 自动完成。

```python
import math
import platform
import random
import time
import torch
from torch import nn
from torchvision import datasets
from torchvision import transforms
import torchvision
from easyai_runtime import RunContext
from dataset_inputs import construct_dataset as _easyai_construct_dataset
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

context = RunContext.from_cli(default_seed=42, default_execution_mode="full")
started = time.monotonic()
random.seed(context.seed)
torch.manual_seed(context.seed)
if context.device != "auto":
    device = torch.device(context.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("Configured CUDA device is unavailable")
    if device.type == "mps" and not (
        hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    ):
        raise RuntimeError("Configured MPS device is unavailable")
    selection_reason = "Device fixed by the verified run configuration"
elif torch.cuda.is_available():
    torch.cuda.manual_seed_all(context.seed)
    device = torch.device("cuda")
    selection_reason = "CUDA is available in the selected training environment"
elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
    device = torch.device("mps")
    selection_reason = "CUDA unavailable; MPS is available"
else:
    device = torch.device("cpu")
    selection_reason = "CUDA and MPS unavailable; using CPU"
generator = torch.Generator().manual_seed(context.seed)
num_workers = context.num_workers
pin_memory = device.type == "cuda"
execution_mode = context.execution_mode
context.emit(
    "runtime_started",
    "training",
    {"executionMode": execution_mode, "seed": context.seed},
)
context.emit(
    "device_selected",
    "training",
    {
        "device": str(device),
        "selectionReason": selection_reason,
        "numWorkers": num_workers,
        "pinMemory": pin_memory,
        "python": platform.python_version(),
        "torch": torch.__version__,
        "torchvision": torchvision.__version__,
        "platform": platform.platform(),
    },
)
```

## 模块二：搭建数据处理——从图片到一批批训练数据

**操作位置：** 点击“数据处理”标签，再点击左侧“数据处理”分类。

这一页最后会有五块放在画布上的大积木：一条预处理流水线、两个 Dataset、两个 DataLoader。先搭好流水线，再让 Dataset 从下拉框中选它，最后让 DataLoader 选对应的 Dataset。

### 2.1 建立预处理流水线 `preprocess`

1. 从左侧拖出“预处理流水线”，放到画布上方。
2. 将 `NAME` 改为 `preprocess`。
3. 拖出“转为张量”，放进流水线内部的凹槽。
4. 拖出“归一化”，接在“转为张量”下方，仍然位于流水线内部。
5. 在“归一化”中，将 `MEAN` 填为 `0.1307`，`STD` 填为 `0.3081`。
6. 选中外层“预处理流水线”，在右侧勾选“供本项目引用”。

应当得到：

```text
预处理流水线 NAME=preprocess ✓供本项目引用
├── 第1步：转为张量
└── 第2步：归一化 MEAN=0.1307 STD=0.3081
```

两块都放在流水线的同一个凹槽里，上下接好，软件就会从上往下处理图片。

电脑看到的图片是一格格像素，每格的数值表示亮度。“转为张量”把这些数整理成模型能使用的形式，并把亮度从 `0～255` 缩放到 `0～1`。得到的形状是 `[1, 28, 28]`：`1` 表示一个灰度通道，后面的两个 `28` 是图片的高和宽。

“归一化”接着计算 `(像素值 - 0.1307) / 0.3081`，把数值调整到更适合学习的尺度。这两个数是本例采用的 MNIST 均值和标准差，直接照着填即可。处理后的数值可以是负数。

搭好后看一眼顺序：先“转为张量”，再“归一化”。`MEAN` 框中只填 `0.1307`，`STD` 框中只填 `0.3081`。

### 2.2 建立训练 Dataset：`train_data`

1. 再打开左侧“数据处理”分类。
2. 拖出“加载内置数据集”，放到流水线旁边的空白处，作为独立积木。
3. 按下表逐项填写。
4. 选中它，在右侧勾选“供本项目引用”。

| 字段            | 要填或选择的值            | 在做什么                         |
| --------------- | ------------------------- | -------------------------------- |
| `NAME`          | `train_data`              | 给训练数据集命名                 |
| `DATASET_NAME`  | `MNIST`                   | 选择手写数字数据集               |
| `SPLIT`         | `train`                   | 使用训练部分                     |
| `TRANSFORM_REF` | 从下拉框选择 `preprocess` | 每次取图片时应用刚刚定义的预处理 |

Dataset 负责按编号取出一张图片和它的正确答案。例如，取出一张写着“7”的图片时，也会一起得到标签 `7`。这里选好 `preprocess` 后，每次取图都会自动执行刚才的两步处理。

### 2.3 建立测试 Dataset：`test_data`

1. 再拖一块“加载内置数据集”，放到独立空白处。
2. 将 `NAME` 填为 `test_data`。
3. `DATASET_NAME` 仍选 `MNIST`。
4. **先把 `SPLIT` 改为 `test`**，再从 `TRANSFORM_REF` 选择 `preprocess`。
5. 最后勾选“供本项目引用”。

训练集供模型反复练习，测试集则用另一组图片看看它学得怎么样。两组图片都先经过 `preprocess`，这样送进模型的格式就一致了。

搭好后，右侧应该各有一份训练数据和测试数据。第二块先选 `test` 再注册，软件就知道它是用来测试的。

### 2.4 建立训练 DataLoader：`train_batches`

1. 从分类里拖出“创建 DataLoader”，放到画布空白处。
2. `NAME` 填为 `train_batches`。
3. 点击 `DATASET_REF` 的下拉箭头，选择 **`train_data`**。
4. 将 `BATCH_SIZE` 设为 `128`。
5. 保持 `SHUFFLE` 后的小方框为勾选状态。
6. 选中这块 DataLoader，在右侧勾选“供本项目引用”。

DataLoader 负责把图片分批送给模型。这里每次取 128 张，让模型一起计算；到最后，剩多少张就取多少张。勾选 `SHUFFLE` 会打乱取图顺序，让每轮学习时图片的排列有所变化。

### 2.5 建立测试 DataLoader：`test_batches`

1. 再拖出一块“创建 DataLoader”。
2. `NAME` 填为 `test_batches`。
3. `DATASET_REF` 选择 **`test_data`**。
4. `BATCH_SIZE` 仍为 `128`。
5. **取消勾选 `SHUFFLE`**。
6. 选中这块 DataLoader，勾选“供本项目引用”。

选中 `test_data` 后，这块 DataLoader 就属于测试这一边了。它会按固定顺序取出测试图片，方便我们逐轮比较结果。

测试时，模型只作答、统计正确率，参数保持原样；参数的学习和调整发生在训练那一边。

### 2.6 完成检查，以及下拉框为空时怎么办

现在右侧“可引用对象”应有五项：`preprocess`、`train_data`、`test_data`、`train_batches`、`test_batches`。本模块的完整关系是：

```text
preprocess：转为张量 → 归一化
    ↑ 被两个 Dataset 的 TRANSFORM_REF 选择
    ├── train_data（MNIST，train）← train_batches（128，SHUFFLE勾选）
    └── test_data （MNIST，test） ← test_batches （128，SHUFFLE不勾选）
```

图中的箭头表示“选用了谁”。在软件中，只要在相应下拉框里选好名字，就建立了这个关系。

如果 `DATASET_REF` 只有“请选择对象”：

1. 返回对应的“加载内置数据集”积木，确认它已经存在。
2. 确认 `NAME` 已设置，并勾选了右侧“供本项目引用”。
3. 确认积木没有被停用，且没有重名或同角色重复注册错误。
4. 再打开 DataLoader 的 `DATASET_REF` 下拉框选择它。

在 `DATASET_REF` 下拉框里选数据集，在 `SHUFFLE` 小方框里决定是否打乱顺序。

### 2.7 对应 Python：预处理、Dataset、DataLoader

读下面的代码时，沿着这条顺序看就可以：`preprocess` 定义处理方法，`train_data / test_data` 读取图片，`train_batches / test_batches` 把图片分批。

`_easyai_construct_dataset` 是 EasyAI 帮忙读取数据的函数；`download=False` 表示读取已经准备好的文件。`num_workers` 和 `pin_memory` 是读取速度方面的设置，软件会根据运行环境安排。

```python
preprocess = transforms.Compose(
    [
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.1307], std=[0.3081]),
    ]
)
train_data = _easyai_construct_dataset(
    datasets.MNIST,
    root=str(context.data_root),
    train=True,
    transform=preprocess,
    download=False,
)
test_data = _easyai_construct_dataset(
    datasets.MNIST,
    root=str(context.data_root),
    train=False,
    transform=preprocess,
    download=False,
)
train_batches = torch.utils.data.DataLoader(
    train_data,
    batch_size=128,
    shuffle=True,
    num_workers=num_workers,
    pin_memory=pin_memory,
    generator=generator,
)
test_batches = torch.utils.data.DataLoader(
    test_data,
    batch_size=128,
    shuffle=False,
    num_workers=num_workers,
    pin_memory=pin_memory,
    generator=generator,
)
train_loader = train_batches
test_loader = test_batches
if len(train_loader.dataset) == 0 or len(test_loader.dataset) == 0:
    raise ValueError("Training and test datasets must be nonempty")
```

## 模块三：搭建模型结构——两层卷积的 `MnistCNN`

**操作位置：** 点击“模型结构”标签，再点击左侧“模型结构”分类。

### 3.1 创建外层模型类

1. 拖出“定义模型类”，放到空白画布中。
2. 将 `NAME` 改成 `MnistCNN`，大小写保持一致。
3. 留意它内部的大凹槽：下面的十层网络全部放在这里。

把“定义模型类”看成整个网络的外壳。里面从上到下接了哪些层，一张图片就会按这个顺序经过它们。

### 3.2 放入第一组卷积、ReLU、池化

1. 拖出“卷积层”，放入“定义模型类”的内部凹槽，作为第一块。
2. 依次填写 `IN_CHANNELS=1`、`OUT_CHANNELS=16`、`KERNEL_SIZE=3`、`PADDING=1`。
3. 拖出 `ReLU`，接在这块卷积层下面。
4. 拖出“最大池化”，接在 ReLU 下面，设置 `KERNEL_SIZE=2`。

卷积层用小窗口扫过图片，学习笔画、边缘等局部特征，输出 16 张特征图。你可以把它们理解为从不同角度观察同一张数字图片。

ReLU 的规则很简单：负数变为 0，正数保留。例如 `[-2, 0, 3]` 经过它会变成 `[0, 0, 3]`。这样的非线性处理，让网络能学到更复杂的关系。

最大池化从每个 `2×2` 小区域中取最大值，把特征图缩小一半：`28×28` 变成 `14×14`，后面需要处理的数也就更少了。

`PADDING=1` 表示在四周补一圈边界。配合默认步长 1 和 `3×3` 卷积核，这一层卷积保持宽高不变。

### 3.3 放入第二组卷积、ReLU、池化

1. 再拖一块“卷积层”，接在刚才的最大池化下面。
2. 填写 `IN_CHANNELS=16`、`OUT_CHANNELS=32`、`KERNEL_SIZE=3`、`PADDING=1`。
3. 再接一块 `ReLU`。
4. 再接一块“最大池化”，仍设置 `KERNEL_SIZE=2`。

第二组接着处理第一组的结果，把 16 张特征图进一步整理成 32 张。再经过一次池化，每张特征图从 `14×14` 缩小到 `7×7`。

第二层的 `IN_CHANNELS` 填 `16`，正好接住上一组输出的 16 个通道。层与层之间就是这样衔接的：前面输出多少通道，后面就接收多少通道。

### 3.4 接上展平和分类部分

1. 拖出“展平”，接在第二个最大池化后面。
2. 拖出“全连接层”，接在“展平”下面。
3. 设置 `IN_FEATURES=1568`、`OUT_FEATURES=128`。
4. 再接一块 `ReLU`。
5. 再接一块“全连接层”，设置 `IN_FEATURES=128`、`OUT_FEATURES=10`。
6. 点击外层“定义模型类”，在右侧勾选“供本项目引用”。

现在每张图片已经变成 32 张 `7×7` 的特征图。“展平”把它们排成一列，一共有 `32×7×7=1568` 个数。这就是下一层 `IN_FEATURES` 填 `1568` 的原因。

全连接层综合这些特征，先得到 128 个数，再给数字 `0～9` 各打一个分。哪个数字的分数最高，就把它作为预测答案。

这十个分数在代码里叫作 `logits`。后面的交叉熵会直接使用它们，所以网络搭到 `128→10` 这一层就完成了。

### 3.5 按这张表逐层核对

表中 `N` 表示这一批有多少张图片，通常是 128。后面的数字描述每张图片经过这一层后的样子。

| 顺序 | 积木           | 参数                       | 输出形状          |
| ---- | -------------- | -------------------------- | ----------------- |
| 输入 | MNIST 图片批次 | 单通道，28×28              | `[N, 1, 28, 28]`  |
| 1    | 卷积层         | 输入1、输出16、核3、补边1  | `[N, 16, 28, 28]` |
| 2    | ReLU           | 无需填写                   | `[N, 16, 28, 28]` |
| 3    | 最大池化       | 核2                        | `[N, 16, 14, 14]` |
| 4    | 卷积层         | 输入16、输出32、核3、补边1 | `[N, 32, 14, 14]` |
| 5    | ReLU           | 无需填写                   | `[N, 32, 14, 14]` |
| 6    | 最大池化       | 核2                        | `[N, 32, 7, 7]`   |
| 7    | 展平           | 无需填写                   | `[N, 1568]`       |
| 8    | 全连接层       | 输入1568、输出128          | `[N, 128]`        |
| 9    | ReLU           | 无需填写                   | `[N, 128]`        |
| 10   | 全连接层       | 输入128、输出10            | `[N, 10]`         |

画布中的结构应是一条完整的链：

```text
定义模型类 NAME=MnistCNN ✓供本项目引用
└── 卷积层 1→16，核3，补边1
    ReLU
    最大池化 核2
    卷积层 16→32，核3，补边1
    ReLU
    最大池化 核2
    展平
    全连接层 1568→128
    ReLU
    全连接层 128→10
```

搭好后数一数：模型容器里一共十块——三个 ReLU、两个卷积、两个池化、两个全连接、一个展平。右侧“可引用对象”里也能看到 `MnistCNN`。

### 3.6 对应 Python：模型定义和前向计算

下面的代码分成两部分：`__init__` 把各层准备好，`forward` 让图片按顺序经过这些层。展平对应的是 `torch.flatten(x, 1)`，位于第二次池化和第一层全连接之间。

```python
class MnistCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer_0 = nn.Conv2d(1, 16, 3, padding=1)
        self.layer_1 = nn.ReLU()
        self.layer_2 = nn.MaxPool2d(2)
        self.layer_3 = nn.Conv2d(16, 32, 3, padding=1)
        self.layer_4 = nn.ReLU()
        self.layer_5 = nn.MaxPool2d(2)
        self.layer_7 = nn.Linear(1568, 128)
        self.layer_8 = nn.ReLU()
        self.layer_9 = nn.Linear(128, 10)

    def forward(self, x):
        x = self.layer_0(x)
        x = self.layer_1(x)
        x = self.layer_2(x)
        x = self.layer_3(x)
        x = self.layer_4(x)
        x = self.layer_5(x)
        x = torch.flatten(x, 1)
        x = self.layer_7(x)
        x = self.layer_8(x)
        x = self.layer_9(x)
        return x
```

## 模块四：搭建训练管线——把模型和数据连起来

**操作位置：** 点击“训练管线”标签，再点击左侧“训练管线”分类。

### 4.1 放入“训练模型”，选好模型和数据

1. 拖出“训练模型”，放到空白画布。
2. 点击 `MODEL_REF` 的下拉框，选择刚刚搭好的 `MnistCNN`。
3. 再从两个 Loader 下拉框里选择训练批次和测试批次，按下表填好剩余参数。

| 字段               | 选择或填写      | 含义                                 |
| ------------------ | --------------- | ------------------------------------ |
| `MODEL_REF`        | `MnistCNN`      | 使用刚搭好的 CNN                     |
| `TRAIN_LOADER_REF` | `train_batches` | 用这一路数据更新模型                 |
| `TEST_LOADER_REF`  | `test_batches`  | 用这一路数据评估模型                 |
| `CRITERION`        | `CrossEntropy`  | 用交叉熵衡量分类预测与正确答案的差距 |
| `OPTIMIZER`        | `SGD`           | 使用随机梯度下降更新参数             |
| `LEARNING_RATE`    | `0.01`          | 控制每次参数更新的步幅               |
| `EPOCHS`           | `10`            | 正式训练遍历训练集十轮               |

这块积木把前面的准备工作串了起来：用 `MnistCNN` 识别图片，用 `train_batches` 里的图片学习，再用 `test_batches` 看学习效果。

`CrossEntropy` 用来衡量模型的答案和正确答案差了多少；`SGD` 根据这个差距调整模型里的参数。学习率 `0.01` 决定每次调整的步子有多大。代码中的 `momentum=0.9` 是软件为 SGD 配好的动量，让更新时也参考前几步的方向。

### 4.2 理解 batch 与 epoch

- **一个 batch：** DataLoader 这次交给模型的一批图片，本例通常是 128 张。
- **一个 epoch：** 把训练集里的所有图片分批学习一遍。
- **十个 epoch：** 完整训练模式下，把训练集重复学习十轮；每轮之后使用测试集评估一次。

对每一批图片，“训练模型”都会完成：先预测答案，计算错得有多大，再找到参数该往哪个方向调整，最后更新参数。代码中把“找到调整方向”这一步叫作反向传播。

学完一轮后，模型会做一遍测试题。答对的张数除以测试图片总数，就是这一轮的测试准确率。做测试时模型参数保持原样。

### 4.3 认清训练积木中的三个位置

| 中文位置 | 什么时候执行                       | 下一模块放什么                   |
| -------- | ---------------------------------- | -------------------------------- |
| 训练前   | 第一轮参数更新之前，执行一次       | 5 张训练样本图片                 |
| 每轮结束 | 本轮训练和测试统计完成后，每轮一次 | 训练损失折线图、测试准确率折线图 |
| 训练后   | 所有轮次完成后，执行一次           | 10 张测试图片的预测结果          |

先让这三个位置空着，下一模块会把对应的图表放进去。

搭好后看一眼三个下拉框：它们应当依次显示 `MnistCNN`、`train_batches`、`test_batches`。如果某个名字找不到，回到对应积木，勾选“供本项目引用”后再来选择。

### 4.4 对应 Python：训练与测试循环

下面节选模型实例化和每轮训练/评估代码。图表代码在下一模块给出：训练前图片放在循环前，每轮曲线放在循环体末尾，预测图片放在循环后。

`train_loss` 是这一轮所有训练图片的平均损失。代码先累计每批的损失总量，再除以图片总数，这样最后一批即使不足 128 张，也能按实际张数计算。`test_accuracy` 是测试集上的正确比例，日志会把它显示成百分比。

```python
model = MnistCNN().to(device)
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.SGD(model.parameters(), lr=0.01, momentum=0.9)
epoch_history, train_loss_history, test_accuracy_history = [], [], []
last_progress = time.monotonic()

for epoch in range(1, 10 + 1):
    context.check_cancelled()
    model.train()
    total_loss, total_samples = 0.0, 0
    for x, y in train_loader:
        context.check_cancelled()
        x, y = x.to(device), y.to(device)
        logits = model(x)
        loss = criterion(logits, y)
        if not math.isfinite(float(loss.item())):
            raise ValueError("Non-finite training loss")
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        total_loss += float(loss.item()) * int(x.size(0))
        total_samples += int(x.size(0))
        if time.monotonic() - last_progress >= 1.0:
            context.emit(
                "progress",
                "training",
                {"epoch": epoch, "trainSamplesCompleted": total_samples},
            )
            last_progress = time.monotonic()
    if total_samples == 0:
        raise ValueError("Empty training loader")
    train_loss = total_loss / total_samples
    model.eval()
    correct, test_samples = 0, 0
    with torch.no_grad():
        for x, y in test_loader:
            context.check_cancelled()
            x, y = x.to(device), y.to(device)
            predicted = model(x).argmax(dim=1)
            correct += int((predicted == y).sum().item())
            test_samples += int(y.size(0))
    if test_samples == 0:
        raise ValueError("Empty test loader")
    test_accuracy = correct / test_samples
    epoch_history.append(epoch)
    train_loss_history.append(train_loss)
    test_accuracy_history.append(test_accuracy)
    metrics = {
        "epoch": epoch,
        "train_loss": train_loss,
        "test_accuracy": test_accuracy,
        "train_samples": total_samples,
        "test_samples": test_samples,
        "elapsed_seconds": time.monotonic() - started,
    }
    context.emit("epoch_completed", "training", metrics)
    print(
        f"Epoch {epoch}: loss={train_loss:.6f}, test accuracy={test_accuracy:.2%}",
        flush=True,
    )
```

## 模块五：搭建图表——看样本、看曲线、看预测

**操作位置：** 留在“训练管线”标签页，点击左侧“图表”分类。

### 5.1 先看看四种现成的图表

工具箱前面有四块已经选好数据的“绘制图表”。看里面的 `SOURCE`，就知道这块会画什么：

| 内部 `SOURCE`   | 用途               | 外层 `CHART_TYPE` |
| --------------- | ------------------ | ----------------- |
| `train_samples` | 看训练样本         | `image_grid`      |
| `train_loss`    | 看训练损失         | `line`            |
| `test_accuracy` | 看测试准确率       | `line`            |
| `predictions`   | 看测试样本预测结果 | `image_grid`      |

按住**外层“绘制图表”标题**拖动，就能把整张图表连同里面的数据来源一起带到画布上。

每块图表有两个凹槽：

- **数据：** 放“数据来源”，决定画什么。预设中已放好，可以直接核对字段。
- **样式（可选）：** 放“标题”“坐标轴”“图例”，让图更容易读懂。下面我们会给每张图加上这些说明。

### 5.2 训练前：显示 5 张训练图片

1. 找到内部 `SOURCE=train_samples` 的图片预设。
2. 按住外层标题，把整块拖进“训练模型”的 **“训练前”** 凹槽。
3. 核对外层字段：`CHART_TYPE=image_grid`、`COUNT=5`、`ROWS=1`、`COLS=5`。
4. 核对内部“数据来源”：`SOURCE=train_samples`、`X_SOURCE=none`。
5. 再打开“图表”分类，向下滚动，找到“标题”。将它拖到这张图表的 **“样式（可选）”** 凹槽。
6. 将标题的 `TEXT` 填为 `train_samples`，`COLOR` 选 `black`。
7. 拖出“坐标轴”，接在刚才“标题”的下面，仍在同一个样式凹槽内。
8. 保持 `SHOW_TICKS` 不勾选，隐藏图片周围的数字刻度。这张图的样式就配好了。

先看看模型将要学习的图片长什么样。每张图旁边会显示正确数字，也就是数据里的标签。显示图片时，软件会把前面归一化过的数值还原成适合观看的亮度。

`COUNT=5` 表示选 5 张样本，`ROWS=1`、`COLS=5` 把它们排成一行五张，最后一起保存在一张 PNG 图片里。

### 5.3 每轮结束：依次放损失和准确率两张图表

**先放训练损失：**

1. 拖出内部 `SOURCE=train_loss` 的折线图预设，放进 **“每轮结束”** 凹槽。
2. 核对 `CHART_TYPE=line`，内部 `SOURCE=train_loss`、`X_SOURCE=epoch`。
3. 在它的样式凹槽中放入“标题”，设置 `TEXT=train_loss`、`COLOR=black`。
4. 在标题下面接“坐标轴”，**勾选 `SHOW_TICKS`**。
5. 再在坐标轴下面接“图例”。

**再放测试准确率：**

6. 拖出内部 `SOURCE=test_accuracy` 的折线图预设。
7. 把它接在刚才**外层“绘制图表”的底部连接口**，让两张完整图表上下相接，一起放在“每轮结束”里面。
8. 核对 `CHART_TYPE=line`，内部 `SOURCE=test_accuracy`、`X_SOURCE=epoch`。
9. 在第二张图表的样式凹槽内依次连接：标题 → 坐标轴 → 图例。
10. 标题填写 `TEXT=test_accuracy`、`COLOR=black`，坐标轴的 `SHOW_TICKS` 勾选。

每学完一轮，我们就看一眼学习情况：左图画训练损失，右图画测试准确率。损失和准确率的含义、单位不同，分开画更容易看清各自的变化。

横轴的 `epoch` 就是轮次。第 1 轮只有一个点，第 2 轮就能把两个点连起来，之后曲线会越来越长。`COUNT`、`ROWS`、`COLS` 用于排列样本图片，在折线图上保持默认的 `10 / 2 / 5` 即可。

这里记住两个字段的分工就好：`SOURCE` 决定画什么数据，标题的 `TEXT` 决定图上写什么字。准确率图的 `SOURCE` 选 `test_accuracy`，标题也填 `test_accuracy`。

### 5.4 训练后：显示 10 张测试图片的预测

1. 拖出内部 `SOURCE=predictions` 的图片预设，放入 **“训练后”** 凹槽。
2. 核对 `CHART_TYPE=image_grid`、`COUNT=10`、`ROWS=2`、`COLS=5`。
3. 核对“数据来源”：`SOURCE=predictions`、`X_SOURCE=none`。
4. 在样式凹槽中依次放“标题”与“坐标轴”。
5. 标题设为 `TEXT=predictions`、`COLOR=black`；`SHOW_TICKS` 不勾选，让注意力集中在图片和答案上。

训练结束了，挑前 10 张测试图片看看模型的回答。`Pred` 是它预测的数字，`true` 是正确答案；`correct` 表示答对，`incorrect` 表示答错。

这张图适合观察“哪些数字认对了，哪些数字容易混淆”。要了解整体表现，再看前面的测试准确率，它统计了整个测试集。

### 5.5 布局怎样生效，图片怎样保存

EasyAI 会按图表数量自动排列。按前面的步骤搭好后，会得到：

| 阶段     | 连接的图表数 | 自动排列                        | 图片尺寸       | 保存时机                     |
| -------- | ------------ | ------------------------------- | -------------- | ---------------------------- |
| 训练前   | 1            | 1 行 1 列                       | 自动选中等尺寸 | 开始训练前保存一次           |
| 每轮结束 | 2            | 1 行 2 列，损失在左、准确率在右 | 自动选中等尺寸 | 每轮保存一张含两个图表的图片 |
| 训练后   | 1            | 1 行 1 列；内部样本是 2 行 5 列 | 自动选大尺寸   | 全部训练结束后保存一次       |

若要手动修改：

1. 点击某张“绘制图表”的标题。
2. 展开右侧“对象与参数”，找到相应阶段的“图表布局”。
3. “排列方式”默认是“自动排列”；“图片尺寸”默认是“自动”。
4. 例如，把“每轮结束”设为 `1 × 2`，再点击“应用图表设置”，就是一行两列。
5. 一张图表占一个格子。放了两张图表，就选择至少两个格子的排列，或直接使用“自动排列”。

可以把布局分成“外面”和“里面”来看：右侧“排列方式”安排几张图表；积木上的 `ROWS / COLS` 安排一张图表里的样本图片。比如预测结果只有一张图表，外面是 `1×1`，里面的十个数字排成 `2×5`。

图片会自动保存到这次运行的结果中，在“日志与结果”里就能看到。每一轮都有自己的一张曲线图，方便回头比较。

### 5.6 完成后应有的训练积木结构

```text
训练模型：MnistCNN / train_batches / test_batches / SGD / 0.01 / 10
├── 训练前
│   └── 绘制图表 image_grid，5张，1行5列
│       ├── 数据：train_samples，none
│       └── 样式：标题 train_samples → 坐标轴不显示刻度
├── 每轮结束
│   ├── 绘制图表 line
│   │   ├── 数据：train_loss，epoch
│   │   └── 样式：标题 train_loss → 坐标轴显示刻度 → 图例
│   └── 绘制图表 line
│       ├── 数据：test_accuracy，epoch
│       └── 样式：标题 test_accuracy → 坐标轴显示刻度 → 图例
└── 训练后
    └── 绘制图表 image_grid，10张，2行5列
        ├── 数据：predictions，none
        └── 样式：标题 predictions → 坐标轴不显示刻度
```

这里的两块 `line` 是连接在一起的同级图表，每张各有一个“数据”和一个“样式”凹槽。

### 5.7 对应 Python：三个时机的图表代码

读图表代码时，可以先认这几个名字：`fig` 是整张图片，`grid` 把图片分成几个格子，`ax` 负责在其中一格画图。`plot` 画曲线，`imshow` 显示数字图片，`savefig` 把图保存下来。其余 `context` 开头的语句帮助软件记录文件和对应积木。

**训练前，放在 epoch 循环开始之前：**

```python
context.check_cancelled()
fig = plt.figure(figsize=(10, 6), dpi=100)
try:
    grid = fig.add_gridspec(1, 1)
    ax = fig.add_subplot(grid[0])
    ax.set_title("train_samples", color="black")
    ax.set_axis_off()
    image_grid = grid[0].subgridspec(1, 5)
    sample_dataset = train_loader.dataset
    for sample_index in range(min(5, len(sample_dataset))):
        context.check_cancelled()
        image, label = sample_dataset[sample_index]
        display_image = image.detach().cpu().clone()
        display_image = display_image * torch.tensor([0.3081]).view(
            -1, 1, 1
        ) + torch.tensor([0.1307]).view(-1, 1, 1)
        display_image = display_image.clamp(0, 1)
        sample_ax = fig.add_subplot(image_grid[sample_index])
        if display_image.shape[0] == 1:
            sample_ax.imshow(
                display_image.squeeze(0).numpy(), cmap="gray", vmin=0, vmax=1
            )
        else:
            sample_ax.imshow(display_image.permute(1, 2, 0).numpy())
        sample_ax.set_title(f"True: {int(label)}")
        sample_ax.set_xticks([])
        sample_ax.set_yticks([])
    ax.set_xticks([])
    ax.set_yticks([])
    relative_path = context.figure_path("auto:training:before", "before", None, None)
    with context.atomic_target(relative_path) as figure_path:
        fig.savefig(figure_path, format="png", dpi=100)
    context.artifact(
        relative_path,
        "figure",
        "before-0-panel",
        ["before-0-panel", "before-0-title", "before-0-source", "before-0-axis"],
        "before",
        None,
    )
finally:
    plt.close(fig)
```

**每轮结束，放在 epoch 循环内部、统计完指标之后：**

```python
context.check_cancelled()
fig = plt.figure(figsize=(10, 6), dpi=100)
try:
    grid = fig.add_gridspec(1, 2)
    ax = fig.add_subplot(grid[0])
    ax.set_title("train_loss", color="black")
    ax.plot(epoch_history, train_loss_history, label="Training loss")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Cross entropy loss")
    ax.tick_params(
        axis="both",
        which="both",
        bottom=True,
        left=True,
        labelbottom=True,
        labelleft=True,
    )
    ax.legend()
    ax = fig.add_subplot(grid[1])
    ax.set_title("test_accuracy", color="black")
    ax.plot(epoch_history, test_accuracy_history, label="Test accuracy (fraction)")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Test accuracy (%)")
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))
    ax.tick_params(
        axis="both",
        which="both",
        bottom=True,
        left=True,
        labelbottom=True,
        labelleft=True,
    )
    ax.legend()
    relative_path = context.figure_path("auto:training:body", "epoch_end", epoch, None)
    with context.atomic_target(relative_path) as figure_path:
        fig.savefig(figure_path, format="png", dpi=100)
    context.artifact(
        relative_path,
        "figure",
        "body-0-panel",
        [
            "body-0-panel",
            "body-0-title",
            "body-0-source",
            "body-0-axis",
            "body-0-legend",
            "body-1-panel",
            "body-1-title",
            "body-1-source",
            "body-1-axis",
            "body-1-legend",
        ],
        "epoch_end",
        epoch,
    )
finally:
    plt.close(fig)
```

**训练后，放在整个 epoch 循环之后：**

```python
context.check_cancelled()
fig = plt.figure(figsize=(14, 8), dpi=100)
try:
    grid = fig.add_gridspec(1, 1)
    ax = fig.add_subplot(grid[0])
    ax.set_title("predictions", color="black")
    ax.set_axis_off()
    image_grid = grid[0].subgridspec(2, 5)
    sample_dataset = test_loader.dataset
    for sample_index in range(min(10, len(sample_dataset))):
        context.check_cancelled()
        image, label = sample_dataset[sample_index]
        display_image = image.detach().cpu().clone()
        display_image = display_image * torch.tensor([0.3081]).view(
            -1, 1, 1
        ) + torch.tensor([0.1307]).view(-1, 1, 1)
        display_image = display_image.clamp(0, 1)
        sample_ax = fig.add_subplot(image_grid[sample_index])
        if display_image.shape[0] == 1:
            sample_ax.imshow(
                display_image.squeeze(0).numpy(), cmap="gray", vmin=0, vmax=1
            )
        else:
            sample_ax.imshow(display_image.permute(1, 2, 0).numpy())
        model.eval()
        with torch.no_grad():
            prediction = int(model(image.unsqueeze(0).to(device)).argmax(dim=1).item())
        outcome = "correct" if prediction == int(label) else "incorrect"
        sample_ax.set_title(f"Pred: {prediction}, true: {int(label)} ({outcome})")
        sample_ax.set_xticks([])
        sample_ax.set_yticks([])
    ax.set_xticks([])
    ax.set_yticks([])
    relative_path = context.figure_path("auto:training:after", "after", None, None)
    with context.atomic_target(relative_path) as figure_path:
        fig.savefig(figure_path, format="png", dpi=100)
    context.artifact(
        relative_path,
        "figure",
        "after-0-panel",
        ["after-0-panel", "after-0-title", "after-0-source", "after-0-axis"],
        "after",
        None,
    )
finally:
    plt.close(fig)
```

## 模块六：运行起来，看看模型学得怎么样

### 6.1 先保存并检查积木

1. 等待顶部和底部保存状态变为“已保存”。普通积木编辑会自动保存；如果工程配置显示未保存，点击“保存工程配置”。
2. 点击顶部“检查与编译”，让软件把积木变成 Python，并找出引用或尺寸方面的问题。
3. 如果底部“检查与问题”出现错误，点击相应定位入口，返回积木修正。
4. 重新等待保存完成，再点“检查与编译”，直到看到“代码检查通过”。
5. 点击“代码对照”，查看完整生成代码。试着点击一块卷积或全连接积木，看看它对应哪几行。以后想调整网络，就修改积木，再看代码如何跟着变化。

### 6.2 选择本机训练环境和数据

1. 点击顶部“环境与数据”。
2. 将“运行位置”选择为“本机”。如果课堂使用服务器，按老师提供的连接方式选择“SSH 服务器”。
3. 点击“选择现有 Python”，找到老师准备的 Python；Windows 中通常选择对应环境文件夹里的 `python.exe`。
4. 点击“选择数据目录”，选择模块一所说明的、内部包含 `MNIST/raw` 的数据根目录。
5. 点击“检查本机环境与数据”。
6. 环境和数据两项都显示可用后，点击顶部“积木”返回，接下来就可以训练了。

如果出现“无法从已保存工程确定有效数据集”，回到模块二，看看两个 Dataset 的选项是否填好、工程是否已保存。

### 6.3 选择快速检查还是正式训练

第一次操作，可以先用少量图片跑一轮，看看整个流程是否顺畅：

1. 点击顶部“工程”。
2. 勾选“快速检查：1 epoch，最多 1024 个训练 / 256 个测试样本”。
3. 保存工程配置，再点“检查与编译”。如果界面提示重新检查环境和数据，按提示完成即可。
4. 点击“开始本次运行”，观察整个流程是否能完成。

跑通之后，再做完整的十轮训练：

5. 回到“工程”，**取消勾选快速检查**。
6. 确认“训练模型”里的 `EPOCHS` 是 `10`，保存并重新“检查与编译”。
7. 再点“开始本次运行”。

“快速检查”是一次小规模试跑：它只取少量图片、训练一轮。取消这个选项后，再按积木中填写的 10 轮进行完整训练。每次点击“开始本次运行”都会从头训练，并留下单独的记录。

### 6.4 按时间顺序观察这次运行

1. 点击底部“日志与结果”，这里会陆续显示图片和每轮的学习情况。
2. 先应出现“训练前”的样本图片，里面有 5 张手写数字及其标签。
3. 一轮训练和测试完成后，检查该轮日志中的 loss、test accuracy，以及指标表中的训练/测试样本数量。
4. 找到这一轮的曲线图片：包含损失和测试准确率两个图表。
5. 后续轮次会继续产生指标记录和新的曲线图片。
6. 全部轮次完成后，检查“训练后”预测图片，里面有 10 张测试样本及预测/真实标签。
7. 等图片和模型都保存好，运行状态会显示成功，这次实验就完成了。
8. 以后还可以在“运行记录”中找到这次实验，回看结果和当时使用的积木。

### 6.5 十轮训练结束后，看这些结果

用完整 MNIST 数据跑完十轮后，可以按下面这张表找到各项结果：

| 要检查的东西 | 应当看到什么                          | 如何理解                         |
| ------------ | ------------------------------------- | -------------------------------- |
| 运行状态     | 成功完成                              | 训练及后续保存均结束             |
| epoch 记录   | 10 条                                 | 每条对应一轮训练和测试           |
| 每轮样本数   | 训练 60000、测试 10000                | 用的是完整数据，不是快速检查子集 |
| 训练前图     | 1 张 PNG，内部有 5 个样本             | 核对输入图片                     |
| 每轮曲线图   | 10 张 PNG，每张包含两个图表           | 各轮独立保留，展示累积历史       |
| 训练后图     | 1 张 PNG，内部有 10 个预测样本        | 核对部分预测                     |
| 模型权重     | 本次运行目录下的 `outputs/model.pth`  | 最后一轮训练后模型的参数         |
| 逐轮指标     | 本次运行目录下的 `metrics/epochs.csv` | 便于再次核对和分析               |

因此完整十轮会生成 **12 张 PNG**；虽然积木中只放了四块“绘制图表”，其中两块每轮合画到同一张图片。

读曲线时，先看整体趋势：训练损失变小，通常说明模型的答案更接近训练标签；测试准确率变高，说明它在测试图片上答对得更多。中间有些起伏很常见，可以结合几轮的变化一起看。

CSV 中的 `test_accuracy` 用小数表示比例。例如，`0.973` 换成百分比就是 `97.30%`，也就是每 100 张测试图片中大约认对 97 张。

`model.pth` 保存了模型在最后一轮学到的参数，代码里叫 `state_dict`。以后把这些参数装回同样的 `MnistCNN` 网络，就能用训练好的模型继续识别图片。

### 6.6 卡住时，来这里找一找

| 现象                                    | 怎么处理                                                                   |
| --------------------------------------- | -------------------------------------------------------------------------- |
| 下拉框只有“请选择对象”                  | 选中想要使用的数据集或模型，填好名字，再勾选“供本项目引用”                 |
| 注册第二个 Dataset 时提示角色冲突       | 把第二个 Dataset 的 `SPLIT` 改成 `test`，再注册                            |
| 测试 Loader 下拉框找不到 `test_batches` | 回到 `test_batches`，让它选用 `test_data`，再勾选“供本项目引用”            |
| 第一层全连接提示尺寸不匹配              | 对照模块三的顺序表，补齐两次池化和展平，把第一层全连接的输入设为 `1568`    |
| 图表没有数据来源                        | 在图表的“数据”凹槽中放一块“数据来源”，选好 `SOURCE`                        |
| 两张曲线看起来相同                      | 把第二张图表的 `SOURCE` 改成 `test_accuracy`                               |
| 10 张图片显示不全或布局报错             | 将图片图表设为 `COUNT=10, ROWS=2, COLS=5`                                  |
| 两张图表放不进 `1×1` 布局               | 在右侧选择“自动排列”或 `1×2`                                               |
| 提示缺少 MNIST 文件                     | 按模块一的目录图找到四个解压后的文件，再选择包含 `MNIST/raw` 的根目录      |
| 提示存在旧 `processed` 缓存             | 请老师提供一份只有原始 `MNIST/raw` 数据的目录，再重新选择                  |
| “开始本次运行”按钮是灰色的              | 先保存并“检查与编译”，再到“环境与数据”完成检查；已有训练在进行时，等它结束 |
| 只运行了一轮                            | 到“工程”中取消勾选“快速检查”，保存后重新编译、运行                         |
| 想找到生成的图片                        | 打开底部“日志与结果”，按训练前、轮次和训练后查看                           |

想提前结束这次训练，点击停止，等状态变为“已停止”。已经生成的日志和图片仍然可以查看，方便了解模型跑到了哪一步。

### 6.7 对应 Python：正常完成后保存模型

训练结束后，`torch.save` 把学到的参数写进 `model.pth`。最后一条 `pipeline_completed` 消息告诉软件：这一套训练流程已经完成。下面的代码由 EasyAI 自动生成。

```python
context.check_cancelled()
with context.atomic_target("outputs/model.pth") as model_path:
    torch.save(model.state_dict(), model_path)
context.artifact("outputs/model.pth", "model", "training", [])
context.emit(
    "pipeline_completed",
    "training",
    {"epochs": len(epoch_history), "executionMode": execution_mode},
)
```
