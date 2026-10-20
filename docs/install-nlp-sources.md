# NLP 默认闭包与整批裁决

本轮一次裁决剩余 spaCy、Transformers、Gensim、HanLP，沿用已核 SentencePiece 与 NLTK 决定。只读官方 PyPI JSON、Simple JSON 与 PEP 658 元数据；不下载 wheel/sdist、模型或语料，不安装、不执行 NLP import。目标固定 Linux x86_64 / CPython 3.11.17，核心 NumPy 2.4.2、torch 2.10.0+cpu 和全部既有 core/ML/CV/DL pins 不改。元数据闭包与计划能力不是实际 ABI/安装通过。

| 卡片及固定候选 | 默认闭包裁决 | 相对核心21的计划 |
| --- | --- | --- |
| sentencepiece 0.2.2 | 默认依赖为空；不启用 numpy/protobuf/test extras | 22文件；新增1394242字节 |
| spacy 3.8.16 | 43个可达节点（止于既有固定闭包锚点）；thinc/blis等新依赖完整核约束，复用DL的tqdm/idna | 60文件；新增59656447字节 |
| transformers 5.20.1 | 27个可达节点；hub/tokenizers/safetensors/hf-xet等默认闭包完整，复用原pyyaml/tqdm/idna，不选其他extras | 43文件；新增25866254字节 |
| gensim 4.4.0 | 5节点：本包、NumPy、既有SciPy、smart-open8.0.4、wrapt2.5.1 | 25文件；新增63473279字节（包含未在核心中的SciPy） |
| hanlp 2.1.5 | unsupported：直接依赖hanlp-common0.0.23、hanlp-downloader0.0.25、hanlp-trie0.0.5只有sdist，无目标wheel | 无完整可安装闭包；总体下载/解包体积未知 |
| nltk 3.10.3 | unsupported：官方固定JSON列有未撤回GHSA-8mgp-746c-j5xp，fixed_in为空；不降级绕过 | 不进入安装来源 |

三包联合计划为72个去重文件、注册表下载量387209225字节；加SentencePiece为73文件、388603467字节。这里是wheel下载估计，不含bootstrap/完整环境占用；所有解包量仍未知、installedBytes=null。表中可达节点止于此前已核的固定锚点，不冒充重新读取CPU torch wheel元数据。原ML SciPy为新增计划来源之一，不因已存在可选锁就隐瞒其下载预算。

`easyai-nlp-sources.json` 有48个可执行元数据记录（原SentencePiece加47个新wheel）、默认依赖边、四项批次裁决与两项拒绝记录；HanLP缺失wheel的JSON hash和sdist清单保留在blockedDependencies。来源文件97184字节，仍在原100000字节限制内。记录各精确URL/SHA256/注册表字节、Requires-Python/Requires-Dist、PEP658/pinnedJSON hash、yanked/漏洞与许可声明；不是持续安全保证或许可批准，legalReviewComplete/distributionReady未改。

三个HanLP依赖的源码包仅记元数据，未下载、构建或换用其他版本。没有把这一二进制来源限制冒称CPU/NumPy冲突。NLTK保留候选3.10.3安全阻断，不声称逐版本复现。开发审计曾在smart-open旧发行的非法Requires-Python `>=3.5.*` 字段停止单根候选选择；最终从已核联合图提取精确8.0.4完整Gensim闭包并逐边校验，不把审计工具错误冒称包不兼容。

## 原链与真实执行门

四个可解析NLP根均走同一NLP_ROOTS→wheels→lock_bytes→constraintsHash/planHash→来源选择/预算→原OfflineWheelInstaller/远端适配→版本、选中imports、原CPU tensor复检。没有新的运行时网络resolver或安装器。Gensim按需要加载既有ML provider；spaCy/Transformers加载DL provider重用固定依赖。只有选中Lightning才激活fsspec[http]，Transformer的普通fsspec依赖不引入aiohttp。

来源预览核精确hash/字节、缺失文件及选择预算；明确登记仍强制executionAuthorized=false。默认执行关闭。安装仍固定--no-index/--only-binary=:all:/--require-hashes、本地来源并清PIP配置，不执行源码构建。计划来源/锁变化使已确认计划过期。全NLP组选含NLTK/HanLP即blocked，无法可靠汇总体积时仍null。

## 模型、离线行为与能力限制

| 包 | 官方发行元数据能证明的行为 | 本应用能力边界 |
| --- | --- | --- |
| spaCy | 描述独立模型download命令/模型包安装，随后spacy.load加载模型 | 不调用download/load，不提供模型选择、下载或预训练pipeline入口 |
| Transformers | quickstart明确在实例化指定模型pipeline时下载并缓存 | 不调用pipeline/from_pretrained，不启用模型、服务、vision/audio等extras |
| Gensim | 元数据描述语料/API，默认含smart-open；未保证plain import零联网 | 不调用downloader或远端语料API，不因HTTP依赖存在就声称import会下载 |
| HanLP | 示例把import与hanlp.load(pretrained)分开，且默认含downloader组件 | 包本身blocked；不调用加载器、不获取预训练模型 |

probe源码仅对选中闭包作普通import与版本/tensor检查，不调用上述模型API。**这不是网络隔离。** pip离线参数只约束pip，私有HOME/超时/取消不证明第三方import零联网；不通过环境变量或未执行测试宣称封网。普通import是否有隐式副作用、实际native ABI与无下载行为仍NOT RUN，未来真实执行须在已明确来源/目标/许可/预算/窗口内另验，不能把元数据能力签成零egress或课堂模型功能。模型/语料功能保持不支持，没有新增条款接受或系统权限。

当前14/17卡具备元数据闭包；OpenCV native、NLTK安全候选与HanLP二进制来源仍unsupported。真实M6.3/B、正式训练/桌面/目标机/SSH门未验。

依据：[spaCy固定JSON](https://pypi.org/pypi/spacy/3.8.16/json)、[Transformers固定JSON](https://pypi.org/pypi/transformers/5.20.1/json)、[Gensim固定JSON](https://pypi.org/pypi/gensim/4.4.0/json)、[HanLP固定JSON](https://pypi.org/pypi/hanlp/2.1.5/json)、[SentencePiece固定JSON](https://pypi.org/pypi/sentencepiece/0.2.2/json)、[NLTK固定JSON](https://pypi.org/pypi/nltk/3.10.3/json)。各PEP658 URL/hash见来源文件；本批214次JSON/metadata读取及原始响应清单见进度证据，无wheel/sdist下载。
