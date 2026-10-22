# 可选 DL 固定来源与执行门

本片仅核对官方 PyPI 版本 JSON、PEP 691 索引及 PEP 658 wheel 元数据，未下载 wheel、未安装、未执行真实 import/ABI/tensor 或训练。目标固定为 Linux x86_64 / CPython 3.11 / easyai-cpu；其他平台仍返回 unsupported。元数据可满足约束不等于运行兼容性已验证。

`packages/training-profiles/easyai-dl-sources.json` 保留精确 wheel 文件名、URL、SHA256、注册表字节、Requires-Python/Requires-Dist、版本 JSON/元数据 URL 与 SHA、许可声明及该次 yanked/漏洞响应；不是持续安全或许可批准。`easyai-dl-linux-cp311.lock` 精确绑定这些候选文件，沿用现有离线 hash 安装器，无新安装器、不升级核心锁。

| 新增 distribution | 固定版本 |
| --- | --- |
| pytorch-lightning | 2.6.6 |
| torchmetrics | 1.9.0 |
| lightning-utilities | 0.15.3 |
| tqdm | 4.70.1 |
| pyyaml | 6.0.3 |
| aiohttp | 3.14.5 |
| aiohappyeyeballs | 2.7.1 |
| aiosignal | 1.4.0 |
| attrs | 26.1.0 |
| frozenlist | 1.8.0 |
| multidict | 7.1.0 |
| propcache | 0.5.4 |
| yarl | 1.25.1 |
| idna | 3.20 |

Lightning 要求的 `fsspec[http]` 复用核心 fsspec 2026.9.0 并扩展 HTTP 依赖；不是只登记 Lightning 顶层版本。其余复用 torch 2.10.0+cpu、numpy、packaging、typing-extensions 等核心版本。固定目标的完整 Requires-Dist/extra 图由合成测试逐边核对。14 个新增 wheel 的注册表下载体积合计 **5909314 字节**；解包体积未知，installedBytes=null。单选 Lightning 和完整 DL 组（torch、torchvision、Lightning）均为核心21加新增14，共35个去重文件；混合 ML/CV 继续去重。

来源预览/登记沿用现有本地私有清单、精确 hash/字节与按选择预算，登记不授予执行权。默认 executionEnabled=false；没有可信来源、许可/目标/预算授权不得下载或执行。最终复检要求精确版本、全部选中模块 import、`fsspec.implementations.http` 以及原 tensor 检查通过，失败不得 verified；未选 Lightning 时不增加这些导入。不启用其他 extras、模型或语料自动下载。

合成测试验证缺失来源、来源预算、固定锁漂移、核心覆盖拒绝、已有版本冲突、捕获离线命令和最终失败门；不冒充真实安装与 ABI 验收。本 DL 切片交付时为10/17卡；后续 NLP 有限能力与当前剩余项见[install-nlp-sources.md](install-nlp-sources.md)。远端现已有代码适配，真实安装仍未验。

上游依据：[PyPI Lightning 固定版本](https://pypi.org/project/pytorch-lightning/2.6.6/)、[官方 release](https://github.com/Lightning-AI/pytorch-lightning/releases/tag/2.6.6)。真实来源接入与许可接受另行授权，legalReviewComplete/distributionReady 未改变。
