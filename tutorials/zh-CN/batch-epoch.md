# batch 与 epoch

batch 是一次交给模型的样本组；epoch 是遍历本次训练样本范围的一轮。最后一批可能少于 batch size。

## 观察参数

DataLoader 的 batch size 决定一批有多少样本，训练管线的 epochs 决定训练多少轮。减小批量常能减少内存需求，但不能保证准确率更高。

正式 MNIST 示例设为 10 epoch。快速检查只执行 1 epoch，并限制训练最多 1024、测试最多 256 个样本；它用于检查执行链，不能冒充正式效果验收。

固定 seed 有助于复现，但不同设备、平台或依赖仍可能产生差异。实际 workers 和 pin_memory 值记录在本次运行记录中：Linux 默认 workers=2，其他平台默认 0；仅 CUDA 启用 pin_memory。

## 动手

定位 DataLoader 或训练管线，比较批量大小与轮数的对应代码。教程不会修改参数或自动启动训练。
