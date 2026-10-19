# Windows 应用 venv 的启动身份

输入源码：`fb7ddb632aab5635c02bc609b46d335af5f32f6a`。父侧提供的 [CI 39211585475](https://github.com/T1doo/Easy-AI/actions/runs/39211585475) 中，Windows 已完成 Electron launch/firstWindow，但 startup.spec.ts:12 期望“本地服务已就绪。”，实际为“本地服务启动协议不匹配。”，5000ms 内观察相同文本 13 次。Linux job SUCCESS。这说明失败推进到 sidecar ready；原错误没有记录 ready 内容或错误类别，不能把以下兼容性缺陷称为此次唯一实测根因。

## 固定版本的进程关系

[uv 0.12.23 的 Windows venv 实现](https://raw.githubusercontent.com/astral-sh/uv/0.12.23/crates/uv-virtualenv/src/virtualenv.rs) 优先复制 Python 的 venv 启动器。[CPython 3.11.14 的 launcher.c](https://raw.githubusercontent.com/python/cpython/v3.11.14/PC/launcher.c) 在 VENV_REDIRECT 路径读取 pyvenv.cfg 的 home，设置 __PYVENV_LAUNCHER__，创建实际解释器进程并继承标准流，随后等待该进程。Node 的 child.pid 因而可以是启动器 PID，而真实 easyai.main 发布的是解释器 PID。原严格相等检查正确拒绝这种启动形态。

[CPython 3.11.14 的 getpath.py](https://raw.githubusercontent.com/python/cpython/v3.11.14/Modules/getpath.py) 使用该启动器变量保留 venv executable/配置搜索路径，同时保留基础解释器位置。直接启动固定 home/python.exe 并仅对子进程设置该变量，可以保留应用 venv 身份并使 Node 持有实际服务进程。

## 当前改动和边界

Main 只对固定的应用 `.venv/Scripts/python.exe` 加 `-m easyai.main` 使用这一启动方式。配置有界读取；要求 CPython 3.11、绝对 home、禁用 system site packages，拒绝重复字段和递归启动器。基础 python.exe 必须存在。清除继承的 Python 路径/启动器覆盖后设置固定 venv 路径；不改全局环境、不搜索 PATH、不选择训练环境。此处信任已准备的应用 venv 配置，不是任意解释器安全验证器。冻结 --onedir 路线不变。

ready 仍必须是首行、精确三个字段、合法端口、版本 1、PID 严格等于实际 child.pid；BOM、调试前缀、额外字段及转发进程仍拒绝。CRLF 保持兼容。只输出固定 JSON/SCHEMA/PORT/VERSION/PID 类别，不记录原始 stdout、令牌或路径；Bearer health、stdin EOF 退出和安全窗口设置不变。

新增 Windows CI 非 GUI 检查实际解释器 PID、应用 sys.prefix、base_prefix 分离、easyai/fastapi import、启动器变量消费、health 和 EOF。真实转发子进程负例验证严格 PID 门没有放松；冻结 smoke 也补上精确字段、端口和 child.pid 检查。Linux 测试不证明 Windows 成功；当前修复仍须自然 CI 验证，完整 A/B 及真实课堂验收未通过。
