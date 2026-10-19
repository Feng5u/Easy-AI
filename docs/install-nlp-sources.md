# NLP 固定来源与有限能力

本片只读取官方 PyPI 固定发行 JSON、Simple JSON 索引及 PEP 658 wheel 元数据，不下载 wheel、模型、语料，不安装或执行 NLP/训练 import。固定目标为 Linux x86_64 / CPython 3.11.17，沿用 NumPy 2.4.2、torch 2.10.0+cpu 与原 core/ML/CV/DL 锁；元数据相容不等于真实 ABI 验收。

| 目录卡 | 本次候选 | 裁决 |
| --- | --- | --- |
| sentencepiece | 0.2.2 | 固定 Linux cp311 wheel；默认 Requires-Dist 闭包为空，不启用 numpy/protobuf/test extras；接入原安装链 |
| nltk | 3.10.3 | 官方 JSON 有未撤回 GHSA-8mgp-746c-j5xp，fixed_in 为空，暂不提供来源；不未经裁决回退旧版 |
| spacy | 3.8.16 | 顶层 NumPy 约束接受既有 pin；thinc 等完整依赖闭包尚未核完，unsupported |
| transformers | 5.20.1 | 顶层未发现核心 pin 冲突；hub/tokenizers/safetensors 等闭包尚未核完，unsupported |
| gensim | 4.4.0 | 顶层 NumPy/SciPy 约束接受既有 pin；smart-open 等完整闭包及原生 ABI 未验，unsupported |
| hanlp | 2.1.5 | 顶层 torch 约束接受既有 CPU pin；downloader/transformers 等闭包与离线模型行为未核，unsupported |

没有把后四项“尚未完成核验”冒称为已证实版本冲突。NLTK 的拒绝依据是本次候选的已知漏洞响应，不宣称所有历史版本已逐一审查，也不自行豁免风险或选择旧 pin。其余候选仅用于保留准确裁决，未进入可执行 wheels。

`easyai-nlp-sources.json` 保存六候选的精确 wheel 文件名/URL/SHA256/注册表字节、Requires-Python/Requires-Dist、固定 JSON 与 PEP658 URL/hash、许可声明、当次 yanked/漏洞投影。`packages` 仅含 sentencepiece，`rejectedCandidates` 不作为安装来源。漏洞/许可响应不是持续保证或许可批准，legalReviewComplete/distributionReady 未改变。

SentencePiece 固定文件为 `sentencepiece-0.2.2-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl`，注册表 **1394242 字节**，SHA256 `1416b92f2f010333786fe6306ed2631121d5ea492219b0841e967b6765e64107`。只记录元数据，解包占用未知；installedBytes=null。单选该卡需要核心21加该包，共22个去重文件，下载预算取实际注册表字节之和；混选 ML/CV/DL 复用同一闭包去重。

新增来源与 hash lock 均进入 constraintsHash，因此影响 planHash，源/锁改变会使已确认计划失效。来源选择只核选中闭包、精确 hash/字节、缺失文件和预算；明确登记仍强制 executionAuthorized=false。全 NLP 组选中未支持卡时保留 blocked/未知总体体积，不把 SentencePiece 子集当六卡完成。

固定离线命令继续由原 OfflineWheelInstaller/远端目标适配使用同一 lock_bytes 生成器提供，保持 --no-index/--require-hashes，无新解析器/安装器。最终版本清单、选中 sentencepiece import 和原 CPU tensor 门缺一不可，失败不得 verified；未选择时不增加 sentencepiece import。未引入任何模型/语料下载入口。

当前17卡中11卡具备元数据闭包，6卡仍 unsupported（OpenCV native 与 NLP 五卡）。默认执行门关闭，真实安装、ABI、正式训练、原生来源对话框及真实 SSH 验收仍 NOT RUN，不能签 M6.3/B。

依据：[SentencePiece 固定 JSON](https://pypi.org/pypi/sentencepiece/0.2.2/json)、[NLTK 固定 JSON](https://pypi.org/pypi/nltk/3.10.3/json)、[spaCy 固定 JSON](https://pypi.org/pypi/spacy/3.8.16/json)、[Transformers 固定 JSON](https://pypi.org/pypi/transformers/5.20.1/json)、[Gensim 固定 JSON](https://pypi.org/pypi/gensim/4.4.0/json)、[HanLP 固定 JSON](https://pypi.org/pypi/hanlp/2.1.5/json)。各 wheel 的 PEP658 URL/hash 见来源文件；原始响应与24请求审计位于本轮进度记录所列本地证据目录。
