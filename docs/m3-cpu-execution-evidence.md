# M3 合成IDX真实CPU执行回执

范围仅为生成Bundle的真实执行链，**不是MNIST学习效果验收，不是M0桌面或A/B全门通过**。用户于2026-10-18 09:02:11 UTC批准父级明确提出的独立CPU环境安装和32/16合成IDX验证，限下载2GB、磁盘5GB、单次测试30分钟；父级随后有限关闭504cedf两项M2 P2，允许依赖/算子探测通过后执行。

环境：已有CPython3.11.17，新建独立`/workspace/easy-ai-training-cpu/.venv`；torch2.10.0+cpu、torchvision0.25.0+cpu、Matplotlib3.10.8、NumPy2.4.2。21项传递依赖经官方来源/CPU wheel SHA256、离线uv完整解析和`uv pip check`核验。应用venv、系统/教师环境未安装训练包；没有CUDA、MNIST下载、SSH或付费资源。

可复核锁为[Linux CPython3.11 CPU锁](../packages/training-profiles/easyai-cpu-linux-cp311.lock)，SHA256 `f30a1d2eb86b13a7ae8a708e3356fade92e8dd942f746616a66376f281d8641b`；每个wheel的官方URL、SHA256、压缩/展开字节记录在[来源清单](../packages/training-profiles/easyai-cpu-sources.json)。这不是Windows/macOS通用锁，不支持绕过hash或缺wheel时源码构建。

资源：wheel实体总下载240,772,699 bytes；包括中断解析流量的保守计费上界508,745,232 bytes（其中为无法逐次精确还原的首次JSON解析流量保守预扣250MB，不能称为精确网线流量）；安装前按wheelhouse＋三份展开量＋128MB余量估计峰值2,982,200,172 bytes。离线安装阶段观察峰值1,905,627,560 bytes；实际测试后整个独立目录逻辑字节1,986,724,165，均低于授权上限。安装和训练没有后续网络下载。没有为释放空间删除其他目录。

健康检查：依赖一致性、真实张量前向/反向、torchvision NMS、Tensor→NumPy、CPU-only确认和Agg PNG实际解码全部PASS；健康测试约0.071秒（不含Python导入启动）。初次健康脚本有Fontconfig缓存不可写提示，PNG仍真实成功；生成运行随后将Matplotlib/XDG缓存置于所属运行目录，未改HOME或系统缓存权限。

最终正式命令：

```sh
EASYAI_TRAINING_PYTHON=/workspace/easy-ai-training-cpu/.venv/bin/python \
EASYAI_TRAINING_TEST_ROOT=/workspace/easy-ai-training-cpu/integration-005 \
UV_CACHE_DIR=/workspace/.uv-cache UV_PYTHON_INSTALL_DIR=/workspace/.python \
pnpm test:integration
```

结果 **1 PASS**，约15.55秒，未超过30分钟。该命令不安装依赖；必须显式传入已批准解释器与新的测试目录。常规`pnpm test`会明确SKIP该用例，不假称常规CI已经运行训练。

测试在中文/空格路径内以标准库生成4个raw IDX文件，32训练/16测试、28×28 uint8、固定图案与十类标签，共37,728 bytes；torchvision以`download=False`读取。原真实Blockly示例仅将epoch设1、batch设8，再由Python编译器生成Bundle；模型、梯度、优化器、损失、图表、权重没有替换为测试runner或假指标。

| 项目 | 实际结果 |
| --- | --- |
| runId | `7b584e0b-e0ba-4a0e-9f23-f282cefd0e61` |
| ProgramHash | `4a367d3633473260a10a6657d4f63cc752ab900e9d988b47878f12bb905c5772` |
| CodeHash | `67564b0f6308014453f4d7684f0b77688b665ae6c96c39b332bb7cbe1cce8543` |
| BundleHash | `d420de2ffb814663375001fe3317a48c4fdde7481623422839b4a18df3d57ca3` |
| 训练样本/测试样本 | 32 / 16 |
| 样本加权train_loss | 2.3290645480155945 |
| 合成数据test_accuracy | 0.125（仅执行链结果，无MNIST学习含义） |
| 实际参数更新 | 8/8张量与相同seed初始权重不同 |
| PNG | 三阶段共3张，真实Pillow解码成功 |
| state_dict | 831,555 bytes，`torch.load(weights_only=True)`实际加载成功 |
| 退出/状态 | 实际exit0、pipeline_completed、产物hash校验后SUCCEEDED |
| 关闭重开 | 13条连续规范事件、4项产物恢复；无重复事件、无重新执行 |

产物在本执行器私有独立目录内保留，不把数据、权重、运行目录或机器配置提交Git：`/workspace/easy-ai-training-cpu/integration-005/runs/7b584e0b-e0ba-4a0e-9f23-f282cefd0e61/`。精确hash如下：

| 产物 | SHA256 |
| --- | --- |
| before PNG | `a0362278f130df5f5ab8b153507e59836a5772ebafb684bd965c583d34067a8b` |
| epoch1 PNG | `33fd323dc00471e83c04ab3589032369598fdd76428511eeabc8b657d22e5f49` |
| after PNG | `c5535e6ffad702a58d81e5a0b2ecdf170ea5c66b1d15867c00c603052527ff1d` |
| model.pth | `e238aaceb1a5a14420248abc51b5c02330d3d648c804a9897fdde69602398450` |

保留失败过程：integration-001误将venv Python resolve为裸解释器，缺torch后exit1；修为保留已选择的绝对venv入口，并以真实标准库venv回归。integration-002实际完成epoch与PNG但PyTorch拒绝以dot开头的临时权重名，状态FAILED；第一次修正误落同名JSON临时函数，unit回归拦住，integration-003仍真实失败；随后撤回无关修改、精确修复atomic_target临时名为非dot且保留suffix，原子不覆盖门不变，12项helper测试GREEN，integration-004与最终005真实通过。每次均使用新目录，不覆盖原失败记录。真实保存错误的train.py第217行通过该次冻结source-map准确定位到训练根`training`；不拿当前项目行号解释旧运行。

M3当前是后端协议/运行小切片：具备saved snapshot、revision/hash、幂等/互斥、双管道supervisor、单写journal、取消、重放和可配置服务的认证SSE。Main路径选择绑定、正式运行创建HTTP/IPC入口、renderer调试流程、应用退出对话/异常崩溃身份恢复尚未接齐；因此M3整体不勾选，M0桌面仍FAIL，A/B仍未达到。Windows训练和清理、真实MNIST/SSH均NOT RUN。
