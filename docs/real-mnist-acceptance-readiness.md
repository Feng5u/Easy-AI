# 真实 MNIST 小样本 CPU 验收：待明确授权

2026-10-20 仅只读核对授权/已有记录，没有搜索私人数据目录、读取真实 MNIST、下载、安装或训练。产品源码仍为已验收 `41b736b532e008634d01821b02a8d7b493351fcb`；该源码 CI39346965518 全 SUCCESS。本页不是实际验收 PASS。

## 当前缺失项

没有用户明确提供且允许本次使用的真实 MNIST 绝对根目录，也没有真实数据训练的样本/轮次/时间/新输出目录授权。已知 integration-005 与 tst34-standalone-001 的回执明确属于合成 IDX，不能重标为真实 MNIST；模板中的 data 路径也不构成数据来源或使用授权。原 CPU 合成范围及基础运算检查授权不自动扩为真实数据训练。

已有独立 Linux CPU Python 与 torch/torchvision/Matplotlib 可复用，不需要新增训练依赖。下一最小输入是：已准备数据根目录、来源/使用许可范围、明确同意一次 quick CPU 验收及预算、新私有输出目录。当前缺项为待用户提供，不是数据文件不存在的全盘搜索结论或新工具拒绝。

## 待确认的单次范围与命令

建议 quick 模式、seed42、batch64、最多1024训练/256测试样本、1epoch；总执行预算600秒，另留30秒取消/清理；新测试根最多256MiB，既有训练根总5GB门继续保留。全部是建议，尚未得到真实数据执行批准。保持 download=False，不复制/改写原始 IDX、不安装或修改共享环境。正式10轮另行确定范围。

仓库外已准备防误执行脚本 `/workspace/easy-ai-training-cpu/real-mnist-a-ready.py`，仅 ast.parse 和静态审查，**没有执行**。使用真实 LocalWorkspace 创建/保存 quick 工程→Python编译→选择已有CPU解释器/明确data根→预检→RunService→事件/CSV/图像/权重/源码映射及退出检查，不调用会生成合成数据的 pnpm test:integration。现有CPU-only版本必须匹配；缺授权引用/data根/新root/预算任一项即在导入应用或创建目录前拒绝。环境变量只是防误执行守门，不替代真实用户授权。

只有用户明确提供数据和批准上述范围后，才可填写并执行：

```sh
cd /workspace/Easy-AI
EASYAI_REAL_MNIST_AUTHORIZATION_REF='<明确用户批准的记录标识>' \
EASYAI_REAL_MNIST_DATA_ROOT='<用户明确提供并允许使用的真实数据根>' \
EASYAI_REAL_MNIST_NEW_ROOT='/workspace/easy-ai-training-cpu/real-mnist-a-001' \
EASYAI_REAL_MNIST_APPROVED_SECONDS=600 \
services/backend/.venv/bin/python -B \
  /workspace/easy-ai-training-cpu/real-mnist-a-ready.py
```

新根必须尚不存在；失败/取消保留原错和私有回执，不自动重跑，不按裸PID清理。PASS只在现有服务关闭确认后发布。它仅准备门槛A的真实小样本训练证据；可点击源积木映射仍需实际桌面操作证据，不能单靠后端脚本宣称完整A，更不是B。旧artifact限制保持，不下载/改留存；新候选435256032字节/hash `abee57c5f61db79b202f876ff97858a4f1007e51c39dcb2bead276da07b614ec` 不替代旧候选。

## 仅文档推送

9ce1cc613d1cfc06a06b7704d882b155b7dc8b75 已独审无敏感内容，保留原提交SHA。本页及进度记录的追加提交使用 `[skip ci]`，仅对这次纯文档 push 跳过不必要工作流，不改CI配置，不跳过产品41b736的检查。机制依据 [GitHub 官方说明](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs)。不把文档提交的跳过状态称为新的产品CI通过。
