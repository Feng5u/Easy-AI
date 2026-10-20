# Dataset 与 DataLoader

Dataset 描述一条样本从哪里来、如何变换；DataLoader 将多条样本组成一批，交给训练或测试循环。

## 本版本怎样连接

预处理流水线供 Dataset 引用，Dataset 再供 DataLoader 引用。先为对象命名并勾选“供本项目引用”，训练管线选择的是稳定对象 ID。改显示名称不会把引用改成任意 Python 字符串。

训练和测试各有一个 Dataset 与 DataLoader。训练可以打乱样本；测试不打乱。取消注册或删除已引用对象后，先修复检查问题，不能直接启动。

数据由你或老师预先准备。MNIST、FashionMNIST、CIFAR10 的尺寸和通道不同，必须与模型、Normalize 参数匹配；应用默认不下载数据。本机 CIFAR10 的运行预检尚未闭合，不能据此教程当成已支持完整执行。

## 动手

选择关联积木，点击“定位关联积木”。保存并检查工程后，再点击“显示对应代码”，阅读 Dataset 和 DataLoader 的真实生成代码；代码只读。
