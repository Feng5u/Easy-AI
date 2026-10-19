# 启动 ready 与显式恢复的等待边界

本次输入为用户提供的错误正文，不是重新获取 Actions 日志。Windows 片段未附 run ID：Electron44.9.0 已启动 PID1940，Node inspector listening/connected/attached 后，startup.spec.ts 的 electron.launch 15000ms 超时，未执行 bridge 断言。另一个 Linux 附件明确失败于 consumed_start_lost_ack 的 fresh resume 返回422 REMOTE_RUN_BUSY，原结果1failed/923passed/8skipped/1warning、86.32s。不能据此把两个正文擅自归到同一运行。

允许的 jobs 元数据独立确认 run39198968754 的 check 在 pnpm test 失败，desktop 在 pnpm test:e2e 失败；这只能证明步骤结果，不补充正文归属。既有7→9项桥接断言修复保留，其执行位置在本次 Windows launch 失败之后。

## Electron44.9.0 / Playwright1.64.1 启动环

当前 Main 是 ESM，原来在入口顶层等待 app.whenReady。锁定 Playwright 的实际 loader 将该 Promise 的兑现延后到 __playwright_run；launch 先等待 Chromium CDP 再调用它。Electron44 的默认 app 又等待应用入口 import 完成。固定版本的原生启动源码补齐了另一端：appCodeLoaded 在入口 import 之后，JoinAppCode 阻止后续原生阶段，CDP handler 在更后面启动。因此延长 timeout 无法解除这条等待环。

证据来源均为固定官方代码或本机锁定包：

- [Electron44.9.0 browser init](https://raw.githubusercontent.com/electron/electron/v44.9.0/lib/browser/init.ts)：ESM入口完成后才通知 appCodeLoaded。
- [NodeBindings](https://raw.githubusercontent.com/electron/electron/v44.9.0/shell/common/node_bindings.cc)：JoinAppCode 等待加载信号。
- [BrowserMainParts](https://raw.githubusercontent.com/electron/electron/v44.9.0/shell/browser/electron_browser_main_parts.cc)：PostEarlyInitialization先JoinAppCode，PreMainMessageLoopRun再启动CDP。
- 本机 `playwright-core@1.64.1/lib/server/electron/loader.js` 和 `lib/coreBundle.js`，以及实际 Electron `default_app.asar/main.js`，已只读核验；未修改依赖或执行Electron。

修复仅让入口完成注册后返回：ready 前保留 scheme 和 single-instance 注册，其余原启动主体在异步 startDesktop 内依次等待 ready、创建安全窗口、启动 sidecar、加载视图。原IPC sender检查、sandbox/contextIsolation/webSecurity、无Node注入、token stdin、退出及清理门均不改。启动异常显示固定通用对话框并记录脱敏失败标志，不自动退出或跳过清理。新增固定 waiting-ready/ready/window-created/backend-ready/view-loaded 阶段日志不含路径、凭据或token；launch仍15000ms，不加sleep或兼容性开关。

`main-bootstrap.test.mts` 将真实Main临时编译，再以独立Node VM执行它和锁定的真实Playwright loader，nativeReady/backendReady均用显式Promise屏障。旧入口不能完成模块评价；修复后入口先完成，ready前无窗口或sidecar，之后安全窗口和sidecar均仅一次，最后加载受控视图。这是测试替身验证模块/等待顺序，不是Electron/Windows/CSP/正常退出实机验收；真实E2E全部原断言仍须通过。

## unknown/disconnected 与旧 worker 退出

异常路径可先公开 unknown/disconnected，再执行finally。该状态不承诺本地worker或传输已退出。原begin立即拒绝仍存活的owner是正确安全门；新认证也不等于旧线程静止。

显式API resume现调用已有wait_worker_exit，最多3秒，位于工作区/core/service锁外，不stop、不retire、不unlock。等待后重新核当前工程/run/runner/终态，再由原begin检查当前认证，并保留thread busy、core.attach物理静止/retiring/fresh-lease/identity fencing。恢复仍initial=False，只inspect，不重复start；超时仍BUSY。

原用例加入实际_publish后Event屏障，确定重现旧422；修复的4种调度严格覆盖202恢复、清理仍忙、工程切换、认证关闭。负例不允许inspect/start替换；正常分支start和fixture-starts均恰好一次，finally释放测试屏障。没有真实SSH或训练调用。

实际命令、所有FAIL/PASS、独立审查与日志hash见implementation-progress末节。Windows真实E2E仍待修复SHA的自然CI；不访问被拒日志接口、不重试浏览器拒绝、不更改CIFAR或真实环境授权。
