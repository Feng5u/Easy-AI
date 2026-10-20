# M6.1/M6.3 官方来源复核（2026-10-20 05:59 UTC）

本次实际重新读取官方来源，并对一个精确 wheel 做静态检查。没有安装、import、执行 wheel 代码、源码构建、模型/语料/数据下载或系统库改动。后续用户转为演示质量优先，本复核保留为交接证据；三张卡和 CIFAR 执行门均不解禁。

## NLTK 与 HanLP

[NLTK 当前 PyPI JSON](https://pypi.org/pypi/nltk/json) 的最新版本仍是3.10.3；[固定版本](https://pypi.org/pypi/nltk/3.10.3/json)重新返回 GHSA-8mgp-746c-j5xp，fixed_in为空、withdrawn为空。[GitHub 当前官方公告](https://github.com/advisories/GHSA-8mgp-746c-j5xp)亦将受影响范围列为≤3.10.3、first_patched_version=null、withdrawn_at=null。没有找到满足当前安全门的更新候选，不自动降级以绕过漏洞。全量JSON SHA256 `bcb887db94e1c4fe5eb120e7125ac9da760b3c07f4d8c8065079373fec07db3c`；固定JSON `2b427a4d43422d771578c857339e036b5b5d0ba8efb1cdbc4443883c86ed860b`；公告API响应 `e975ae73d9e7d0b0035f7de27949f5085204eaf0048cecf6343d1ba7c0a52675`。这是本次来源事实，非重复引用旧快照，也不表示未来不会修复。

[HanLP 2.1.5](https://pypi.org/pypi/hanlp/2.1.5/json)的要求仍含hanlp-common≥0.0.23、hanlp-downloader、hanlp-trie≥0.0.4。分别读取三者当前完整 release 历史，按这些要求枚举所有非撤回稳定发行：没有任何匹配 wheel，不仅是最新版本无兼容Linux CPython3.11 wheel。

| 官方项目 | 当前版本/唯一当前文件 | 完整JSON SHA256 |
| --- | --- | --- |
| [hanlp-common](https://pypi.org/pypi/hanlp-common/json) | 0.0.23，sdist，28,930字节 | `5fe5a1a0a0bb2a192ec2bceb8a5758b58983f7c6e4bba439dd7384462c8ee557` |
| [hanlp-downloader](https://pypi.org/pypi/hanlp-downloader/json) | 0.0.25，sdist，13,873字节 | `65c166008b3ad1b290329b4895dc46db81efa5eb494df1e30e928f1e11fa1324` |
| [hanlp-trie](https://pypi.org/pypi/hanlp-trie/json) | 0.0.5，sdist，6,690字节 | `4bacd78b7f5f5a665b0241a4f915662ee79915b08c7e15bd3183414083d94a30` |

因此不能在既有 only-binary/安全门下开放 NLTK 或 HanLP。未下载sdist，不做本地打wheel或替换第三方来源。

## OpenCV 精确 wheel 静态结果

[官方 PyPI 5.0.0.93](https://pypi.org/pypi/opencv-python/5.0.0.93/json)的 `opencv_python-5.0.0.93-cp37-abi3-manylinux_2_28_x86_64.whl` 从其 files.pythonhosted.org URL 下载到本次独立临时目录；73,783,032字节，SHA256 `c8de2dec111122a02e8beb28e16c31904992dfd6186560b142a92c71403c1039`与原固定来源及当前官方JSON一致。下载耗时16.78秒，未超过100MB/5分钟限额；未安装/执行，不换headless。

读取 ZIP 目录及42个ELF的readelf动态段/版本需要表，所有成员展开总大小196,005,616字节。cv2.abi3.so 的 RPATH 为 `$ORIGIN/../opencv_python.libs`。按wheel内所有ELF直接DT_NEEDED扣除所带库，仍需目标系统提供以下16项（这是必要条件，不是完整dlopen/传递依赖或ABI证明）：

```text
ld-linux-x86-64.so.2 libGL.so.1 libICE.so.6 libSM.so.6
libX11.so.6 libXext.so.6 libc.so.6 libdl.so.2 libgcc_s.so.1
libglib-2.0.so.0 libgthread-2.0.so.0 libm.so.6 libpthread.so.0
libstdc++.so.6 libxcb.so.1 libz.so.1
```

静态版本需要上界分别为GLIBC_2.28、GLIBCXX_3.4.22、CXXABI_1.3.11。必要检查可以限定精确wheel hash/平台、解析这些SONAME及符号版本，缺项时给出拒绝原因；仅凭存在同名文件、manylinux标签或宿主ldconfig不能给未知目标正向兼容结论。Qt plugin/dlopen、系统库传递依赖、真实Python3.11/NumPy2.4.2 import、图形显示能力均未验。因此当前不将其加入可安装闭包或解除INSTALL_NATIVE_REQUIREMENTS_UNVERIFIED；不另造虚假的“兼容通过”路径。

所带METADATA SHA256 `20749df4e7500c53075dee344cd02f63d4df0dce93526e49e7e1c90fbc094e3e`，与原PEP658 hash一致；WHEEL `6a64b1cf98670e593de58d6559d5b0a34e778ebdfe2059140a09431aaa146b75`。wrapper许可证MIT，第三方说明涵盖OpenCV Apache2、FFmpeg LGPL2.1、Linux Qt5 LGPL3等；LICENSE.txt SHA256 `09d719058e782ac7bc71ba21c944e1136cde2bb957c0e888121f0218d6b5f02c`，LICENSE-3RD-PARTY.txt `2537f5653345db7231ff12f307bcfa4c89807d45ed1c4bb8ebfb6f26f61b160a`。所带SSL/crypto文件名标示1.1.1k，不能凭PyPI包级vulnerabilities为空推断全部native无漏洞，也不能只凭文件名断言实际补丁状态。分发许可/native安全审核尚未完成。

## CIFAR 最小裁决材料（未实现、未执行）

重新读取[固定 torchvision 0.25.0 官方构造源码](https://raw.githubusercontent.com/pytorch/vision/v0.25.0/torchvision/datasets/cifar.py)，源文件SHA256 `0a2d6786e8e9d1e9bc7db0664d0185bc14fb22c6733e8ee6dde750038b6ed835`。其固定官方校验值是MD5，不能称为抗恶意替换的认证hash：

| 官方文件 | 官方MD5 |
| --- | --- |
| cifar-10-python.tar.gz | `c58f30108f718f92721af3b95e74349a` |
| data_batch_1 | `c99cafc152244af753f735de768cd75f` |
| data_batch_2 | `d4bba439e000b95fd0a9bffe97cbabec` |
| data_batch_3 | `54ebc095f3ab1f0389bbae665268c751` |
| data_batch_4 | `634d18415352ddfa80567beed471001a` |
| data_batch_5 | `482c414d41f54cd18b22e5b47cb7c3cb` |
| test_batch | `40351d587109b95175f43aff81a1287e` |
| batches.meta | `5ff9c542aee3614f3951f8cda6e48888` |

未从所读[官方数据说明](https://www.cs.toronto.edu/~kriz/cifar.html)或该固定适配器取得这七个展开文件的官方SHA256；没有数据下载/扫描许可，不能补造精确SHA256。正向方案需要教师从可信准备过程提供七文件的精确大小/SHA256及可信来源记录，再绑定到一次私有不可变副本；MD5仍只是官方构造的完整性校验，不代替信任。

保留原官方适配器的最小候选范围：仅固定七文件、下载=False、无训练；允许一次准备复制及全量SHA256/官方构造MD5扫描的§9.1窄例外，并显式接受受信任pickle反序列化。使用隔离无凭据/无网络/只读数据的进程或一次性容器（不能把venv当安全沙箱），输出仅schema/shape/dtype/label范围/少量样本摘要，验证[3,32,32]与10类。建议每批≤40,000,000字节、metadata≤65,536字节，总输入≤240,065,536字节，私有磁盘≤1GiB、内存≤2GiB、CPU/墙钟≤120秒、网络/下载0；这是待批准的上限，未执行的性能承诺。两次train/test官方构造会重复扫描全部六批，输入复制/强hash/MD5/pickle总读取须另设保守≤2GiB预算并在实现时精确计数，超限拒绝且不重跑。

无pickle的二进制版本、受限解释器解析或转换为npz都改变当前官方 `torchvision.datasets.CIFAR10` Python格式构造路径；即使更安全，也不能直接声称满足原D10/§9.1官方适配器验收，需要用户明确改范围。pickletools静态扫指令不能证明pickle安全。当前SAFE_PROBE_REQUIRED保持。

## 其余验收的具体最小条件

- 正式十轮：一次新的明确执行范围，指定已准备MNIST根、独立CPython3.11.17/torch2.10.0+cpu/torchvision0.25.0+cpu/NumPy2.4.2/Matplotlib3.10.8路径、新run根、CPU选择；可提议完整60,000/10,000、10epoch、batch64、seed42、墙钟30分钟/私有输出≤2GiB、下载0、失败不自动重跑。若只有1024/256数据不能称完整正式验收。旧一次训练授权不可复用，旧实例路径不假设存在。
- SSH：单跳Linux x64隔离专用账号、host:port、可信渠道指纹、已有上述训练Python及MNIST、应用专有受保护run父目录、私密凭据输入。既有test:ssh入口范围是一次1024/256单轮成功任务及另一个最多2轮取消任务，maxSeconds30–240、窗口≤2小时，上传仅自建协议文本/编译Bundle，不下载数据；这是额外训练，必须单独计入新范围，不能复用十轮许可或声称只认证。正式十轮SSH若需要，应另外确定，不擅自扩展此入口。
- 干净Windows：Windows11 x64图形目标、明确操作人，无Node/开发Python；精确ZIP/SHA、新私有解压和项目目录，建议验收窗口30分钟、磁盘≥2GiB，不安装训练依赖/不自动取数据。应用包内Windows Server CI不代替该实机。受控本地自动建训练环境当前只实现Linux x64。
- 真实安装：新建应用owned Linux x64根、固定conda25.9.1启动器及Python3.11.17离线bootstrap，教师共享前缀只读。最小计划选torch/torchvision/numpy/matplotlib的既有核心21wheel（240,772,699字节），或单选sentencepiece在核心上加1,394,242字节；所有现有锁、来源SHA不变。提议包文件预置离线、执行下载0、私有容量≤2GiB、墙钟≤600秒，实际bootstrap大小由提供的来源清单算入预算，不能猜测总额。确认具体包ID/目标/路径/授权到期窗口后，才可用同一offline/no-index/only-binary/require-hashes安装与import/tensor复检；取消/故障的额外新环境次数另明确。不申请全局sudo、系统库安装、NLTK/HanLP/OpenCV例外或任何模型下载。
