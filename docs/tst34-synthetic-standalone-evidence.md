# TST34 合成 IDX 独立 Bundle 执行回执

2026-10-19，运行源码 `f487b6531f9e492fba3820d8408f3f372227cec9`；起始本地文档 HEAD `4b89ecb59052fea53ac5d734bc957909fa9968bf`。本轮产品、测试、依赖锁均未修改，没有为文档再触发 CI。结论仅为 **TST34 合成 IDX 独立执行切片 PASS**，不是正式 MNIST 效果、原生 picker、干净机器 TST33、完整 A/B 或发布验收。

## 授权与资源

复用原批准的独立 CPU 环境及 32/16 合成 IDX、1 epoch、batch 8 范围，见 [原 CPU 回执](m3-cpu-execution-evidence.md)。父级明确允许本轮 TST34 有界复用，不扩大到下载、安装、共享环境、GPU 或 SSH。解释器 Python 3.11.17，torch 2.10.0+cpu、torchvision 0.25.0+cpu、Matplotlib 3.10.8、NumPy 2.4.2、Pillow 13.0.0，与既有回执一致。私有训练根归当前用户、mode700；本次独占新建 `tst34-standalone-001`，保留所有失败和产物，不覆盖旧测试。

原总训练根磁盘上限 5,000,000,000 字节、单次 1,800 秒仍适用。执行前逻辑字节 1,988,484,456；训练采样峰值 1,989,866,859，后验证时 1,989,867,669。实际训练进程约 9.36 秒，另设 180 秒本次上限。没有安装或下载；4 个新合成 raw IDX 文件共 37,728 字节，明确不是 MNIST 原数据。

## 真实保存工程导出链

私有脚本 `export.mjs` 直接使用当前构建的生产 MainWorkflow/startBackend，没有替换 backend.request、编译器或导出器：选定本次新工程目录→创建工程→加载实际 Blockly mnist-figures fixture，只将 EPOCHS=1、两个 BATCH_SIZE=8，工程名称标明合成用途→真实 save 得 revision2→compile→exportBundle。仅目录选择回调指定测试目录，没有 Electron GUI/原生 picker 声明。

输出是专用 `standalone-export/easyai-code-80e7a26d-7ed4-4587-8d47-d8827407a4fc`，不是 RunService 暂存目录。包含 11 个清单文件及 bundle.json。原 Main 调用返回与 program/code/bundle hash 比较、逐文件 hash 检查均完成；随后私有 JS 检查器错误使用 localeCompare 计算聚合 hash，**整个 export.mjs 命令 exit1/FAIL**。原日志保留。finally 中自有 sidecar PID327012 正常 exit0/signal null；没有重导出或重启 sidecar。

使用标准库按 Python `sort_keys=True` 重新核验同一已导出目录，聚合 hash 及全部文件 PASS。后生成的 export-receipt.json 是此次恢复核验回执，不冒充原 HTTP 回执对象的原样录制。独立审查另核 canonical IR programHash、五个 helper 与当前源码逐字一致、保存工程与导出快照字节一致。执行结束后再次核全部文件/hash 不变，导出代码未修补或添依赖。

| 内容 | SHA256 |
| --- | --- |
| programHash | `4a367d3633473260a10a6657d4f63cc752ab900e9d988b47878f12bb905c5772` |
| codeHash / code/train.py | `de8d1fd0ef2ff3436f2f06308c9c28463f8a30b22a5534b7ee10e879f4f4e343` |
| bundleHash | `2b2cc10a7108e93bac7d2eecb1e64cd75c023a0f79555fa7a81959dffa4a0774` |
| bundle.json 文件 | `a1a504b2b3120b2e5a1a2f7e72c189c947c964e77d5fd0c05dfc66bb1d47702f` |
| 保存及导出 project.easyai.json | `c1d55fe822da2ab91ae3b77c55dcb0911753c89764332821b49729db3822747b` |
| code/source-map.json | `3e700e144995967feb9adbb9b7b28abc3eb2540a474843c9118ab75dc37fc10a` |

## 脱离应用执行

训练前核 sidecar 已退出且该旧 PID 不存在。本次未启动 Electron GUI；导出 Node 进程已结束。训练命令严格采用导出 README 的 standalone 参数，不用 --config 或 RunService。实际 cwd 为上述导出目录，argv：

```sh
/workspace/easy-ai-training-cpu/.venv/bin/python code/train.py \
  --data-root "/workspace/easy-ai-training-cpu/tst34-standalone-001/SYNTHETIC IDX ONLY" \
  --output-dir "/workspace/easy-ai-training-cpu/tst34-standalone-001/external-output" \
  --seed 42
```

本次私有 `standalone.py` 构造最小子进程环境，清除 PYTHONPATH/PYTHONHOME，不继承仓库路径或凭据；禁用写 pyc，Matplotlib/torch 缓存均在本次私有目录。已有独立 Python 的 `-I` 检查确认找不到 easyai 包。实际 generated train.py 只使用随 Bundle 提供的 easyai_runtime helper及已有第三方库，不导入 Easy-AI。保留 README Linux 默认 numWorkers=2，未改代码或用配置降 worker。

| 验证 | 实际结果 |
| --- | --- |
| 直接训练进程 | PID327173，exit0，约9.36秒，stderr为空 |
| 配置一致 | 保存 revision2、full、seed42、SGD lr0.01、1epoch、两个loader batch8；事件与IR/快照匹配 |
| 实际样本及 epoch | 32训练 / 16测试，唯一epoch1，CSV与事件一致 |
| 指标 | 有限 train_loss=2.3290645480155945，test_accuracy=0.125；仅合成执行值，无MNIST效果含义 |
| 事件 | 8条seq连续，runtime_started/device_selected/4个artifact_created/epoch_completed/pipeline_completed，无runtime_error；不是应用supervisor的13事件流 |
| 参数 | 独立训练Python以非main方式读取原样生成模块，不再训练；按seed42重建初始模型，8/8张量实际变化，已保存张量全部有限，weights_only加载成功 |
| PNG | 3张实际Pillow解码成功；独立标准库另核CRC/解压及1000×600尺寸 |
| 产物 | 4项大小/hash与artifact事件清单一致；全部导出文件和保存快照未变 |

`observedChildren=[]` 仅表示0.5秒轮询未采到短命 worker PID，不是“没有 worker”或逐 worker 停止证明。没有把本轮作为进程树取消/异常清理验收；本次直接训练进程的 exit0 与 sidecar 先行退出分别有记录。

| 产物 | SHA256 |
| --- | --- |
| before PNG | `a0362278f130df5f5ab8b153507e59836a5772ebafb684bd965c583d34067a8b` |
| epoch PNG | `33fd323dc00471e83c04ab3589032369598fdd76428511eeabc8b657d22e5f49` |
| after PNG | `c5535e6ffad702a58d81e5a0b2ecdf170ea5c66b1d15867c00c603052527ff1d` |
| model.pth | `ee42cc870d1125af4dfb630f6c5bb4e5168b6e94ec3acfbebb7b9a2821952845` |
| epochs.csv | `d9dea8cf3d959c935e994ff1e543ef66d928152e634a05b27f2240f714066be3` |
| events.jsonl | `1070f73143031c0d04b45310217b79c936b5043ed134cfabb6e53f6b4eed2c94` |

## 私有证据与复核

全部脚本、日志、数据、Bundle、权重及机器路径回执保留在本执行器私有 `tst34-standalone-001`，不提交运行目录。执行命令另包括 `node .../export.mjs`（FAIL如上）、`python .../verify-export.py`（同目录恢复核验PASS）、`python .../standalone.py`（实际训练及验证PASS）；后两者没有重导出或重新训练。关键证据 hash：

| 文件 | SHA256 |
| --- | --- |
| export.mjs | `9fafd4bcafaa8de800a771dabea9ba2859434fdfc86baea5dc95adb1056d6a7a` |
| export.log（原FAIL） | `df70717c37139bfbce53abacb04a4b7db1c893b21a108204457ac1c28d6581a8` |
| export-receipt.json（恢复核验） | `4048569a3c7a72b939d0cbfb9921567fc26fa08a5c648aa7a496e0bdcc336e08` |
| sidecar-stop.json | `05274867abcf4ee253b174aeec4724dc1766bb5f594fac2a185a50efb0e807a7` |
| standalone.py | `ccdacd2ec7c36851b93af7cbf6a810b629f70650298395034dd8a2633ad8ee56` |
| execution.json | `9d19b01cbc7437fa26b350a297f3aa9ef69be86212453629d02e9271788bc4e3` |
| acceptance.json | `79de024fd1f7fa81a0b980e31e8c32e1559b58fba6a83c06c42c3ebbaa694a56` |

独立审查仅读源码/私有回执并用标准库重算文件/IR/产物，未重复训练或导入 torch。8/8更新及Pillow解码来自主执行已结束的真实独立训练Python verifier，独审未冒称独立重跑。无明确P1/P2，未发现需要修生产导出链的缺陷。真实MNIST/SSH、Windows外部训练/原生picker、TST33、硬件/许可和完整A/B仍未完成。
