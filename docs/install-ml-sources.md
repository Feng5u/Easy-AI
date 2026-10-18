# M6.3 ML 可选依赖来源合同

本片为原计划14.3/14.5的ML白名单组补固定发行元数据、闭包和受控执行接线。17张卡中现在8张有可解析的目标版本：原5核心加scipy/pandas/scikit-learn；其余9张仍unresolved，不能凭展示卡片宣称支持。完整ML组为numpy、scipy、pandas、matplotlib、scikit-learn。

仅支持既有Linux x86_64 / CPython3.11.17 CPU核心。核心文件及版本不变；新增锁是可选补充，不把ML加进MNIST最小安装。元数据约束兼容不等于实际ABI/import/tensor兼容验收。默认executionEnabled仍false，教师环境仍只读，应用sidecar不安装或导入这些训练依赖。

## 可信发行记录与准确体积

2026-10-18仅只读请求PyPI精确发行JSON和选定wheel的PEP658独立`.metadata`，未下载wheel/sdist/模型/数据、安装包或接受许可。JSON只用于选择文件、发行hash/字节/yanked/已知漏洞记录；Requires-Python/Requires-Dist取独立METADATA，并与索引发布的metadata SHA256逐字节核对。依据[PyPI JSON API](https://docs.pypi.org/api/json/)和[Simple Repository API](https://packaging.python.org/en/latest/specifications/simple-repository-api/)。项目级requires_dist不代替wheel元数据。

| 发行 | 选定文件标签 | 下载字节 | 来源 |
| --- | --- | ---: | --- |
| scipy 1.17.1 | cp311/cp311/manylinux_2_27或2_28/x86_64 | 35349300 | [PyPI发行JSON](https://pypi.org/pypi/scipy/1.17.1/json) |
| pandas 3.0.1 | cp311/cp311/manylinux_2_24或2_28/x86_64 | 11255234 | [PyPI发行JSON](https://pypi.org/pypi/pandas/3.0.1/json) |
| scikit-learn 1.8.0 | cp311/cp311/manylinux_2_27或2_28/x86_64 | 9103788 | [PyPI发行JSON](https://pypi.org/pypi/scikit-learn/1.8.0/json) |
| joblib 1.5.3 | py3/none/any | 309071 | [PyPI发行JSON](https://pypi.org/pypi/joblib/1.5.3/json) |
| threadpoolctl 3.6.0 | py3/none/any | 18638 | [PyPI发行JSON](https://pypi.org/pypi/threadpoolctl/3.6.0/json) |

完整新增闭包共56036031下载字节，加上既有核心闭包；单选按其实际闭包计。真实URL/filename、发行SHA256/字节、METADATA URL/SHA256、Requires-Python/Requires-Dist及此次JSON SHA256保存在`packages/training-profiles/easyai-ml-sources.json`，与补充hash lock共同绑定constraintsHash。这里的wheel SHA是注册表声明值，没有声称本轮核验了wheel内容；未来operator本地来源仍须由既有archive读取真实字节/hash/身份后才能启用。没有为未下载的wheel虚构解包大小，新增项unpackedBytes=null，ML计划installedBytes=null；downloadBytes与解包占用不混同。

所选文件当次均非yanked，发行JSON的vulnerabilities为空；这只是捕获时注册表结果，不替代持续安全/许可审查。版本为固定兼容候选，没有声称最新。所有版本均允许Python3.11；继承核心manylinux2.28运行要求，不扩大其他平台支持。

## 选择、闭包与核心约束

- scipy要求`numpy>=1.26.4,<2.7`，复用核心2.4.2。
- pandas在Python3.11要求`numpy>=1.26.0`及`python-dateutil>=2.8.2`，复用核心2.4.2和2.9.0.post0；dateutil/six已有核心闭包。tzdata只对win32/emscripten的marker生效，此Linux合同不选。无pandas extras。
- scikit-learn要求`numpy>=1.24.1`、`scipy>=1.10.0`、`joblib>=1.3.0`、`threadpoolctl>=3.2.0`；选上述准确版本。joblib/threadpoolctl没有运行Requires-Dist。test/doc/build/benchmark等extras不选，不包含模型或数据。

生产不是通用联网解析器。只消费审过的白名单根与固定依赖图；单选scipy只附带scipy，单选pandas只附带pandas（均另含原核心），单选scikit-learn附带scipy/joblib/threadpoolctl，不顺带选pandas。组全选走同一生成器。测试用PEP508 marker和版本约束核整个补充图与核心版本，发行锁与manifest不一致即拒绝。未锁可选项、平台不符、现有版本冲突保持明确blocker，不自动改torch或升级共享环境。

## 原执行门和复检

constraintsHash绑定核心与ML两对来源/锁文件，planHash还绑定具体闭包、字节、基线、runtimeFingerprint、bootstrap和磁盘/时间预算。既有核心计划只验证核心本地wheel；具体ML计划额外验证其选择闭包的operator wheelhouse文件，实际SHA/字节进入runtimeFingerprint及预算。可选文件缺失/变更或预算不够拒绝，不把core capability当ML来源授权。计划仍需本次明确确认。

同一OfflineWheelInstaller只把本次精确闭包的补充pin加到核心锁副本；固定no-index/require-hashes/only-binary命令、私有配置禁用和原owner/lease/WAL/取消/未知停止合同保持。没有第二套writer或自由命令入口。Main原生来源picker仍未实现，目前只有operator私有manifest；本片没有创建实际配置或启用本机安装。

固定inspector对已知distribution读取metadata版本（不因此导入模块）；基线/规划只导入原核心3模块。最终receipt指定本计划所需模块，用显式distribution→import映射，scikit-learn→sklearn；未选的ML模块不导入。最终须完整版本闭包、选中模块真实import及原CPU tensor检查全部通过，才可verified/ready。未知probe仍保留owner/lease/journal，同prefix阻重入；单job取消保持隔离。

NOT RUN：实际ML wheel获取、环境创建/安装、ML实际import/ABI与tensor正向验收、训练、SSH、新许可接受。仍需真实来源/许可与一次性owned目标/预算/窗口的独立授权。其余9卡、原生source picker、远端安装和完整M6.3/B均未完成；本片不把元数据可解析当真实安装完成。
