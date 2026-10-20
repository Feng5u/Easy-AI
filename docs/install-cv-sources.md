# M6.3 CV 可选来源与不支持边界

本片继续原14.3/14.5的CV目录，复用既有核心/ML来源、单一计划器、固定installer与probe owner。**scikit-image固定闭包可解析，opencv-python仍明确unsupported；CV全组未完成。** 当前17卡中9卡有可解析目标版本，另8卡未支持，其中OpenCV有专门native要求未确认的blocker。数量不等于实际安装或完整M6.3/B验收。

仅Linux x86_64 / CPython3.11.17 / 既有CPU核心，保留原NumPy2.4.2、Pillow13.0.0及ML的SciPy1.17.1；不换核心、不改老师环境。所有新增wheel解包占用未知，installedBytes=null。缺私有配置仍默认executionEnabled=false；本轮无真实安装/导入/训练。

## 只读核验来源

2026-10-18仅请求可信PyPI精确发行JSON与PEP658 `.metadata`，核发行文件URL/hash/字节、yanked/当次漏洞记录、实际METADATA SHA256、Name/Version/Requires-Python/Requires-Dist。捕获请求禁redirect、限定pypi.org/files.pythonhosted.org、15秒/2MiB；没有获取wheel/sdist、模型、数据或接受许可。证据在`easyai-cv-sources.json`，发行SHA是注册表声明值；未来本地文件仍由原archive实际核SHA/bytes/身份，不把METADATA hash当wheel内容hash。

| 固定发行 | 文件标签 | 声明下载字节 | 发行元数据 |
| --- | --- | ---: | --- |
| scikit-image 0.26.0 | cp311/cp311/manylinux_2_24或2_28/x86_64 | 13711217 | [PyPI](https://pypi.org/pypi/scikit-image/0.26.0/json) |
| imageio 2.38.1 | py3/none/any | 328389 | [PyPI](https://pypi.org/pypi/imageio/2.38.1/json) |
| tifffile 2025.10.16 | py3/none/any | 231162 | [PyPI](https://pypi.org/pypi/tifffile/2025.10.16/json) |
| lazy-loader 0.6 | py3/none/any | 8791 | [PyPI](https://pypi.org/pypi/lazy-loader/0.6/json) |

4份CV补充声明下载14279559字节；单选scikit-image还需原ML已审SciPy1.17.1的35349300字节，即比核心增加49628859字节。与ML合选时SciPy只出现一次，不重复计费/计预算。实际私有来源齐备时仍按既有合同downloadBytes=0，另核本地来源/磁盘预算；这不授权自动下载。

选择的tifffile版本允许Python3.11，没有为了使用最新版本升级目标Python。固定发行均非yanked、捕获时vulnerabilities为空；这不是持续安全或许可结论。metadata约束兼容不替代真实ABI/import验收。完整URL、filename、SHA、metadataSHA及捕获JSON SHA逐项保存在来源文件，不虚构解包估计。

## 运行闭包与markers

scikit-image要求NumPy>=1.24、SciPy>=1.11.4、NetworkX>=3、Pillow>=10.1、imageio>=2.33且!=2.35.0、tifffile>=2022.8.12、packaging>=21、lazy-loader>=0.4。复用核心NumPy2.4.2、NetworkX3.6.1、Pillow13.0.0、packaging26.3及ML的SciPy1.17.1。imageio运行依赖NumPy/Pillow>=8.3.2；tifffile仅NumPy；lazy-loader仅packaging。目标Python3.11的PEP508 markers和完整无extras闭包有离线合同核验。

不启用data/doc/test/build/optional、ffmpeg、pyav、imagecodecs、freeimage或codec插件extras；不下载示例图像或外部二进制插件。单选scikit-image不会附带pandas/scikit-learn/OpenCV。数据/codec相关功能不能因顶层包可安装就宣称齐备。显式distribution→import映射为scikit-image→skimage、lazy-loader→lazy_loader；最终仅导入本计划所需模块，未选CV不导入。原完整版本/import/CPU tensor门、owner/lease/WAL与未知probe保留合同不变。

## OpenCV：记录候选，拒绝安装

核验候选为[opencv-python 5.0.0.93](https://pypi.org/pypi/opencv-python/5.0.0.93/json)的`cp37-abi3-manylinux_2_28_x86_64`文件，声明73783032字节。其Python3.11生效要求为NumPy>=2，现有2.4.2在该Python元数据约束内；没有为了候选升级/降级NumPy。明确映射opencv-python→cv2。

但是Python发行元数据没有提供足以可靠确认具体目标机GUI/系统动态库准备情况的证据。官方[opencv-python README](https://github.com/opencv/opencv-python/blob/master/README.md)区分桌面包和不含GUI组件的headless包，并说明GUI依赖链；该说明不是具体目标库清单或主机已满足的证明。本轮不下载wheel查看ELF、不执行cv2或安装系统库，不能给出系统要求已通过的结论。

因此候选仅记录在`unsupportedPackages`，不进入CV lock、可执行闭包或下载预算；catalog targetVersion=null，计划保留`INSTALL_DEPENDENCIES_UNRESOLVED`并增加`INSTALL_NATIVE_REQUIREMENTS_UNVERIFIED`，确认失败，不spawn worker。CV全组选择也被阻挡。没有偷换opencv-python-headless/contrib、接管同名cv2或猜测缺库后安装。所列候选字节是审计记录，不作为可安装计划估计。

未来解除这个unsupported需要可靠的精确发行系统依赖清单和具体目标验证证据，再按原来源/许可/owned目标/预算/窗口取得独立执行授权；不能仅凭NumPy匹配、当前机器能找到某个库或一次通用开发许可启用。

## 原执行链与剩余门

constraintsHash绑定核心、ML、CV三对来源/锁；具体计划只合并实际闭包，同名依赖去重。补充锁与来源须一致。原runtime只为选中闭包核本地文件真实hash/字节、身份和预算，core/ML计划不要求CV wheel。固定no-index/require-hashes/only-binary命令和同一installer/probe复用，没有第二writer或网络解析器。

Main原生来源清单选择/来源预算预览/明确登记已接，登记不搬迁执行授权；真实对话框未验，见install-source-picker.md；未创建实际配置或打开默认执行门。真实scikit-image/ML安装、系统库验证、imports/ABI/tensor正向、下载/训练/SSH/新许可均NOT RUN。其余可选卡、OpenCV native证明、原生来源对话框真实验收及完整M6.3/B仍待完成。
