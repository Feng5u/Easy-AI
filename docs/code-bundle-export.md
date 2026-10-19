# 从桌面导出完整代码 Bundle

2026-10-19 增量：源码 `f487b6531f9e492fba3820d8408f3f372227cec9` 已完成真实保存工程导出→结束自有 sidecar→已有独立 CPU Python 按 README 原样执行的 **TST34 合成 IDX 独立切片 PASS**。11文件/hash、32/16样本、1epoch、3PNG解码、8/8参数更新及4产物通过，见[准确回执与原检查器FAIL](tst34-synthetic-standalone-evidence.md)。不是正式MNIST/原生picker/Windows外部训练/TST33/完整A或B；以下“没有运行”描述为历史阶段，不覆盖此新增证据。

保存当前工程，完成“检查与编译”，再点击“导出已保存代码 Bundle”。未保存草稿、只读工程或未通过编译时该入口不可用；工程 JSON 的“导出当前工程”入口仍单独保留。只导出这次已保存 revision 的代码，不拿历史运行快照或屏幕上的旧代码替代。

Main 原生选择器要求选择已有父目录；Renderer 只能发送 projectId、revision、programHash，不能发送路径。后端核当前工程、保存版本与实际 Python 编译 hash，在父目录下独占创建 `easyai-code-<UUID>` 新子目录。已存在目录不能合并或覆盖；原工程文件不修改；不会主动搜集数据、私钥、凭据、运行和父目录其他文件。保存快照原样保留用户字段，不是脱敏器，字段中的敏感内容仍可能被导出。picker 取消不写输出，选择期间工程/版本/后端变化会拒绝；开始写文件后没有强制取消功能。返回前再次核身份，服务中断或身份变化可能使回执未确认，即使目录已经存在；UI明确提示保留检查，重试新建另一目录。

Bundle 包含 `code/train.py`、`easyai_runtime.py`、`entry.py`、`supervisor.py`、`portable_journal.py`、`managed.py`、source-map、`program.ir.json`、可移植 `project.easyai.json` 保存快照、README 与 ENVIRONMENT 环境说明。`bundle.json`记录文件内容 SHA256、programHash/codeHash/bundleHash；在受控目录内所有内容写入、同步后才排他发布，返回不含本机绝对路径。清单是完整性记录，不是签名或来源认证。

当前桌面写入复用既有持有目录身份、无链接路径、排他新建和同步接口，生产能力门仅在已支持的 POSIX 文件系统开放；不新增 Windows 路径回退、不放开其既有安全 gate。导出父目录必须通过该接口的所有权和权限检查，不能借此写不安全共享目录。磁盘错误/目录变化/同步失败不报告成功，可能保留部分输出；不会自动递归删除目录。失败目录没有可靠完成回执；不能仅看目录存在即认为成功，需核 manifest 与实际文件。

在用户/教师已准备的独立训练 Python 环境中，按 Bundle README 使用：

```sh
python code/train.py --data-root "/absolute/path/to/data" --output-dir "/absolute/path/to/new-output" --seed 0
```

data-root 的 Dataset 布局及模型参数必须匹配保存工程；新输出目录不能覆盖已有运行。导出本身不会选择或启动解释器、导入训练库、读取数据、安装依赖、联网、启动 SSH 或生成训练指标。辅助文件随包提供，不依赖 Easy-AI Python 包。正式参数与快速小样本模式仍由该保存工程决定。

本轮验证实际 Main→鉴权 sidecar→Python 编译→新目录导出链、全部文件 hash、保存快照、原文件保全、失效/取消/冲突/写入失败；没有运行导出代码。原计划 TST34 在已有第三方库的训练环境脱离应用运行、真实 native picker、Windows/干净机及课堂验收仍 NOT RUN。CIFAR 安全构造门保持关闭，不能凭源码可以导出宣称其数据可运行；不得用 Bundle 绕过未解决的不可信 pickle 边界。旧 M8 便携产物不含本轮功能，未重新打包或发布。
