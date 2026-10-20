# 演示检查与冻结边界（2026-10-20）

用户要求先等待、再检查演示，因此合并 main 与 Release 均暂停。基线产品为 `acdf3e6f74ac9835c0656060e7cf9f46f51b790b`，其 Linux/Windows [CI39376641569](https://github.com/T1doo/Easy-AI/actions/runs/39376641569) 成功；本次修复检查发现的来源面板折叠、重复定位和输入安全问题并补演示验收，不增加产品范围。最终候选 SHA、CI 和 artifact 另在进度记录冻结，不能把基线的绿灯转移给修复版本。

## 可实际演示的顺序

1. 完整解压精确 SHA 的未签名 Windows x64 候选，保留随包 notices，不从 ZIP 内直接运行。核候选 provenance、archive SHA 与当前检查收据；43474263 旧试用包不含 acdf3e6 的图像回放，不能混用。等待“本地服务已就绪”；页面不应露出 Node require，sandbox 必须保留。
2. 在新的可写项目目录新建 MNIST 示例，查看三类注册对象，执行“检查与编译”。这一步不读取真实数据、不启动训练。打开只读代码，点选积木检查源码高亮。
3. 改一个参数造成可解释的编译诊断，按定位修复；保存，正常退出并重开，核项目与生成代码。也可从空白项目用工具箱搭 CNN，核形状错误→修复→保存恢复；已有独立 E2E 覆盖此路径。
4. 若目标用户已经有自己保存的运行，再查看它的 stdout/stderr、暂停显示、从头分页、恢复实时；查看已登记 PNG 的最新/历史版本，点“来源”和“查看配置”进入该运行的只读快照，折叠后再次点击来源应重新展开。没有历史运行时跳过，不能制造训练指标或以测试夹具冒充教学结果。
5. 打开离线卷积教程，改变合法/非法核参数，核真实数值结果与纠错。未选好训练环境和数据时，开始按钮应保持不可用或给出具体预检原因；环境页三张不支持卡不能当成功安装示范。
6. 正常关闭并重开，确认工程保存、旧运行终态/日志/PNG仍可读取；关闭快照只退出只读查看，不改当前工程或冻结快照。真实训练/取消/SSH的演示需要另行明确范围，当前不执行。

## 不同目的的验证

- 源码/包：核原件 hash、分支/远端 SHA、candidate provenance，保留已验证43474263旧包与当前候选区别。Windows CI 对实际包执行 ASAR/冻结后端/鉴权/EOF/正常关闭检查。
- 编辑/恢复：既有 startup 与 blank-CNN E2E 执行真实 Blockly、Python 编译、Monaco、诊断修复、保存与重开，不替换 IPC 或后端。仅项目目录选择器由测试定向替代，原生 picker 的人工验收仍缺。
- 运行查看/导航：扩展原日志 E2E，经真实 LocalWorkspace 准备 CREATED 状态的测试专有运行，只有中性日志和两张1×1色块PNG；贡献者 ID 来自真实编译 FigureSpec，未启动任何训练/模型/数据读取。核独立日志游标、Unicode/EOF、横向条底部和≤24 DOM片段，PNG Canvas像素，producer及全部contributors映射，producer和一项配置的可见Blockly/Monaco，折叠重新定位，停止未启动运行，关闭重开恢复。前后项目和快照文件字节必须完全不变，事件禁止process_spawn/runtime_started/epoch_completed。
- 异步/错误：现有 React/模型测试覆盖运行切换后迟到source/image/events、图像失败/未就绪重试、无法确认停止不报成功、日志失败保持位置、双路独立与64书签/长行边界。本轮只跑与演示风险相关的组合；不将重复执行累计为更多验收。

## 发现与限制

后续独立安全检查发现并修复HTTP鉴权前body读取、MNIST legacy缓存、产物登记预算和安装来源预算顺序；同时补同来源Monaco重复定位。见[本次安全修复](security-review-20261020.md)。6052609 Windows新增重开日志断言曾FAIL，分页等待窗口已作有根据的修正；最终状态必须以新冻结提交CI为准，不能借基线绿灯放行。合并/Release仍暂停。

55d6797的Windows E2E另有两处真实失败：Monaco虚拟滚动被错误的DOM scrollTop前置判断掩盖、长Dataset行左上点击被编辑器视图层拦截；分别改为真实键盘回顶部并核实际代码、可见文本token正常点击。父级还发现合法construct_dataset模型名覆盖新增helper，已用不可被用户占用的内部别名修复，保留合法命名。上述失败均保留，新SHA的开发态和包内结果待实际CI，旧候选不能冒充已包含修复。

独审发现原生 details 的 summary 可把 DOM open 改成 false，而 React 保存的 open prop 仍为 true；再次来源请求只更新版本，不会重新打开。新增纯内存回归先真实 FAIL，再由导航 layout effect 对每次显式请求恢复 open；原生 Blockly 选择回声 `navigate=false` 不强制展开，待派发 toggle 不清除新请求。真实 Windows E2E 包含同一折叠/再点来源操作。

本实例已有 Chromium sandbox 宿主权限故障，不重试或加 no-sandbox。Windows 开发态与包内 E2E 由已有有界 CI 执行；CI VM 不代表 Windows 11 干净用户机。旧一次 MNIST 小样本授权已用完；无新训练、SSH、数据下载、用户设备操作、CIFAR门放宽。不能承诺完整B或所有实机演示无问题；剩余条件见 remaining-critical-path。

最终冻结为0e1e1b29eb356aa217a0ae133327d4e33509dd25 / [CI39383662136](https://github.com/T1doo/Easy-AI/actions/runs/39383662136)：Linux完整check/test/build及Windows开发态四场景、ZIP审计、包内相同四场景与正常退出均SUCCESS。新的[未签名候选](https://github.com/T1doo/Easy-AI/actions/runs/39383662136/artifacts/12245664573)保留至2026-10-21 15:05北京时间，未在本实例另行下载/重算；收据见implementation-progress末节。此前各次FAIL保留，整体失败的e656候选不充作全GREEN。当前绿色证明上述自动化演示路径，正式训练/SSH/干净Win11/原生picker人工验收及完整A/B仍未关闭；合并main与Release继续HOLD。
