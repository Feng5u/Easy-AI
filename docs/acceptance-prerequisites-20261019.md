# 剩余验收的独立最小条件（2026-10-19）

本次基线为本地 `e85e64dd88f2321363610fde06212ebe64b07023`、远端源码 `3c53280b16fc63f30567520951b3fe3055624863`。旧总览中的 Windows 无候选、存储门未开放等历史描述不代表当前状态；Windows 开发态和包内编辑/编译/保存重开已有真实 CI 证据，见 [3c53280 收据](candidate-windows-3c53280.md)。这些证据不能代替干净机或真实训练。

## TST32 的实际范围

原计划 §16.5 明定 React/Canvas/SVG 本地数值演示：固定 5×5 输入、可编辑 3×3 核、窗口位置、九项乘积、求和、输出网格即时联动。全 1 输入与核的每窗和 9 是明确的单元测试要求；不要求新增矩阵编辑功能、第四个工作区或 Python 算术运行器。现桌面固定输入 1–25，初始输出为 `63,72,81 / 108,117,126 / 153,162,171`。

新增真实 Electron 用例从离线教程入口验证上述九窗口、核编辑、输出格选窗、非法核值隐藏旧结果及修复/重置。用例无需打开工程、选择解释器/数据、编译或运行训练，不修改产品源码。不把 React/JSDOM 结果记作实际桌面结果；桌面状态以本轮自然 CI 收据为准。独立审查确认此范围与原计划一致。

## 可以分别推进的四项

| 项目 | 当前可用证据/依赖 | 最小缺失条件与下一步 |
| --- | --- | --- |
| 真实 MNIST | 独立 CPU 环境仍在；合成 IDX 真实参数更新/PNG/权重/事件已有回执 | 明确提供已准备的真实 MNIST 根目录、来源与使用范围，以及实际训练的 CPU/时间/轮次预算和新输出目录授权。保持 `download=False`。小样本和正式十轮效果验收分开，不用合成准确率替代。无需 SSH，也无需重装训练依赖。 |
| 真实 SSH | 产品协议与离线守门已有；[显式入口](ssh-acceptance.md)可做有界验收 | 隔离 Linux 主机/账号、独立可信渠道核验的指纹、已有兼容训练 Python/真实数据、受保护运行父目录、私密凭据注入渠道、明确操作范围/时间窗口和新私有本地证据目录。未给目标与授权，不拨号；不得把所有本地验收都等候 SSH。 |
| TST34 外部 Python Bundle | 桌面导出/完整性链已有；本地独立 CPU Python 和训练包元数据存在，辅助源码随 Bundle 提供，无需 Easy-AI Python 包 | 在应用外，以保存工程实际导出的完整 Bundle，选定该已有解释器、匹配的数据和新的独占输出目录，核配置/hash、真实退出、指标/PNG/权重。已有依赖足够独立推进合成 IDX 执行链，但本轮限定不训练，未运行；合成数据通过也不能称真实 MNIST 效果通过。原生导出 picker 和目标平台证据应单列。 |
| TST33 干净机器 | 已有 Windows 实际开发态/包内 GUI 证据，应用自带后端 | 需要明确 OS/架构的干净图形目标和普通测试账号，机器无开发 Node/Python/本地 torch，保留 Electron sandbox，能取得精确候选 ZIP/hash，并有私有可写项目目录及桌面交互/证据渠道。启动、编辑、保存子集可独立于 SSH 验证；完整 TST33 远端运行部分还需上一行 SSH 条件。开发工具齐全的 CI 机器不能冒充干净机。 |

## 本轮只读核实

命令（未 import 训练库、未训练/安装/联网/探测硬件）：

```sh
/workspace/easy-ai-training-cpu/.venv/bin/python -I -B -c 'import importlib.metadata as m,json,sys,pathlib; print(json.dumps({"python":sys.version.split()[0],"prefix":sys.prefix,"packages":{n:m.version(n) for n in ["torch","torchvision","matplotlib","numpy","pillow"]},"integration005":pathlib.Path("/workspace/easy-ai-training-cpu/integration-005/acceptance.json").is_file()},sort_keys=True))'
```

PASS：Python 3.11.17，torch 2.10.0+cpu、torchvision 0.25.0+cpu、Matplotlib 3.10.8、NumPy 2.4.2、Pillow 13.0.0；既有 integration-005 回执文件存在。元数据存在不等于本轮重新验证 ABI/训练执行；真实历史执行见 [M3 回执](m3-cpu-execution-evidence.md)。本轮没有提供真实 MNIST 数据根目录，不遍历或猜测用户数据。

这四项为分别待输入/授权的 NOT RUN，并非工具拒绝或执行结果不明。本云机既有无 DISPLAY 与 sandbox 条件不足仍阻止本机 GUI；没有重试被拒操作、修改权限或关闭 sandbox。完整 M4/M7、M5、TST33/34、许可/硬件和发布门 B 仍未整体验收。
