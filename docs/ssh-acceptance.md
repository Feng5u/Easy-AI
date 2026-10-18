# 显式 SSH 集成入口

`pnpm test:ssh` 是原计划 M5 阶段入口。当前实现及本地守门验证不等于真实 SSH 验收；至少一次明确授权的真实全链路成功才可记 M5 PASS。`test-frozen-ssh.mjs` 只验证冻结 HTTP 拒绝/协议，不能代替它。

本入口不安装应用/训练依赖、不创建凭据、不下载数据、不修改教师训练环境。仅支持已有 Linux 隔离账号、既有 Python/torch/torchvision/matplotlib 与本地已有 MNIST；应用 venv 不需要 torch。使用现有产品 LocalWorkspace、指纹确认/ConnectionManager、只读环境与Dataset probe、DataTransfers、编译器生成Bundle、owner start/resume/cancel、日志与产物缓存/RunViews，没有替代训练脚本或模拟曲线。连接管理器wait_idle只证明session/environment清理；新增RemoteRuns.wait_worker_exit另等同run旧owner线程，等待不stop/retire/unlock，不替代begin/core.attach的物理门复核。

退出状态：

| exit | 状态 | 含义 |
| --- | --- | --- |
| 0 | PASS | 仅真实执行模式全部断言及清理静止证据满足；当前未执行 |
| 1 | FAIL | 已进入执行或入口发生意外失败；可能有已登记远端owner，保留私有状态和runIds，不自动重复运行 |
| 2 | NOT RUN / NOT_CONFIGURED | 配置未提供或不存在，不创建工作区、不认证、不联网 |
| 3 | NOT RUN / NOT_AUTHORIZED 或 CREDENTIAL_INPUT_REQUIRED | 未选execute、窗口不合适或stdin凭据缺失，不当PASS |
| 4 | NOT RUN / PRECHECK_FAILED | 配置/参数/权限/平台/锁定开发环境不满足，不安装补救 |
| 5 | NOT RUN / READY_NOT_RUN | `--check` 的本地配置检查通过，但没有执行SSH；故意不是exit0 |

普通 `pnpm test:ssh` 无配置返回2；有配置但无 `--execute` 返回3。`--check` 仅检查配置、私有路径和窗口，不能证明目标存在、账号获准或环境可用。任何配置声明都不能替代实际授权。

配置由开发者在仓库外的私有绝对路径保存，当前只支持POSIX。文件必须属于当前用户、无group/other权限，读取同一个O_NOFOLLOW fd核权限/regular/大小/稳定身份；禁止中间symlink。`localRoot` 须是仓库外、尚不存在的新绝对路径，父目录属于当前用户且无group/other权限；保留该目录供事后核验，不自动递归删除。

配置结构如下（占位值不能用作授权或真实目标）：

```json
{
  "endpoint": {"host": "isolated.example.invalid", "port": 22},
  "username": "explicit-isolated-account",
  "fingerprint": "SHA256:<从可信独立渠道取得的43字符base64指纹>",
  "pythonPath": "/home/isolated/existing-env/bin/python",
  "dataRoot": "/home/isolated/existing-mnist",
  "runBase": "/home/isolated/.easyai/ssh-acceptance/<新的规范小写UUID>",
  "localRoot": "/absolute/private-parent/new-result-directory",
  "isolatedAccount": true,
  "authorizationReference": "非敏感的授权记录标识",
  "windowStart": "<含时区的ISO时间>",
  "windowEnd": "<含时区的ISO时间>",
  "operations": ["identity", "probe", "upload", "start", "logs", "disconnect", "resume", "cancel", "artifacts"],
  "maxSeconds": 180
}
```

窗口最多2小时，执行前剩余时间须覆盖maxSeconds（30–240秒）及30秒清理余量。隔离确认必须是布尔true，数字1不接受。runBase须有`.easyai/ssh-acceptance/<UUID>`后缀，与dataRoot互不包含；服务器端需要已有、安全的受保护父目录，未知目录/内容由产品门拒绝，不自动修复。窗口检查接入产品workspace身份验证回调，因此后台lease、上传、owner、artifact I/O边界也受限；SDK已阻塞的调用及远端已启动进程不承诺硬实时停止。窗口耗尽不再发新网络取消，保留owner和未知状态，需要原授权范围内人工后续处置。

先用 `EASYAI_SSH_TEST_CONFIG=/absolute/private-config.json pnpm test:ssh --check` 做本地检查（预期exit5），不要在公共仓库保存实际配置、数据路径、host或凭据。仅在得到真实测试授权后才用相同配置加 `--execute`。执行模式从stdin读一行、最多70000字节JSON凭据，只接受 `{"password":"..."}` 或 `{"privateKey":"...","passphrase":"..."}`；不要把内容放argv、配置、命令历史或公开日志，应由可信交互/secret注入渠道提供。无自动认证重试或凭据写盘；内存引用使用后丢弃，不承诺安全抹除不可变字符串。

执行顺序：可信pin匹配才允许确认/认证；通过产品显式上传一个自建小型协议文本（不是数据集），回读并只读inspect同slot；从实际Blockly fixture经Python编译生成quick模式1024/256上限、1epoch课程Bundle，数据探测使用download=False；启动同幂等key重放仍同runId，关闭连接后新认证，最多3秒等待同run旧worker实际退场后仅resume一次同owner；超时/owner替换/未知同步清理拒绝，不重start或再次认证；要求SUCCEEDED、产物全部核验、唯一runtime_started/process_exited及真实epoch事件，日志读至EOF、PNG内容长度/SHA256核验；再启动最多2epoch full模式同课程Bundle并对该owned run明确取消，要求CANCELLED执行证据及唯一process_exited。任何观察不到运行态、取消竞态输给自然完成、环境/数据不满足、同步错误或预算不足都FAIL，不伪造成功。

最后仅在窗口内按新私有ledger里的精确owned runId请求取消；不杀任意PID、不删除远端文件、不清理教师目录。取消请求本身不是静止证明，未知结果/清理不明为FAIL。私有`acceptance.json`只输出阶段、状态、run/slot UUID和计数；详细产品状态留在私有localRoot。再次执行必须提供新localRoot与新的明确授权，不能把FAIL当作安全重试依据。

当前最小缺失条件：隔离Linux主机及专用账号范围、可信渠道核验指纹、明确允许上述操作的起止窗口、已有训练Python和课程MNIST数据、受保护runBase父目录、可信stdin凭据注入渠道，以及可保留证据的私有本机新目录。当前没有这些授权目标，不连接、不训练；CIFAR裁决和旧226 PASS/1 FAIL UNKNOWN均保持。
