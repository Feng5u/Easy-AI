# Windows 空白画布构建 CNN 验收候选

- 源码：`4d60b86986e79d46690fd1a5d63d6e5fdb590195`；开发分支 `codex/demo-v0.0.0`。
- [CI39257059104](https://github.com/T1doo/Easy-AI/actions/runs/39257059104)：Windows job118074889967、Linux job118074890058 全部 SUCCESS。
- ZIP：`easyai-0.0.0-win-x64.zip`，`435254893` 字节。
- SHA256：`a6d3b407d6046f2c877c1b7624fbc22d07afbaddd270952e322d19afece77ace`。
- 获取：上述运行的 Artifacts，`easyai-unsigned-win-x64-4d60b86986e79d46690fd1a5d63d6e5fdb590195`；上传 SUCCESS，按工作流保留一天。

Windows step14开发态与step19实际打包应用均执行同一组两个真实E2E场景，全部PASS。原示例删除Dataset→权威编译报错→源积木定位→Undo→重新编译→Monaco只读/双向映射→保存重启的场景保持；新增场景从空白工程实际操作工具箱构建CNN。不是只加载预制最终图，也没有生产mock runner或伪造编译结果。

新增场景在两个模式中各完整执行：

1. 在临时目录创建空白工程，先读真实保存文件确认三个工作区均为空。
2. 实际拖入并连接预处理流水线和ToTensor，注册Prep；创建训练/测试Dataset及DataLoader，实际选择原ID引用，注册TrainData/TestData/TrainBatches/TestBatches，并实际切换测试loader SHUFFLE为false。
3. 实际拖入定义类与Conv→ReLU→Pool→Flatten→Linear六个模型块，注册ToolboxCNN；参数对应Conv2d(1,16,3,padding=1)、Pool2、Linear(3136,10)。训练块通过实际菜单选择模型、训练及测试loader的固定ID。
4. Python权威编译通过；真实生成代码包含ToolboxCNN、Conv2d和Linear声明。整个工程共13个实际积木。
5. 切回Linear，第二次真实编辑IN_FEATURES为3135；编译得到唯一SHAPE_MISMATCH，精确说明上一层输出[3136]与输入参数不匹配，定位原Linear ID并禁止运行。再实际编辑为3136，重新编译通过，完整代码与最初全等。
6. 核真实保存的预处理连接、Dataset/Loader引用、SHUFFLE、CNN层序和训练引用ID；正常退出后使用同一隔离state重启。模型页恢复，重新编译代码全等，整个workspaces（含字段、连接、ID、坐标）与重启前严格全等，未绑定训练环境时运行仍禁用。

原生目录picker仅在测试Main中返回该测试临时工程目录；其余生产Blockly/React/存储/编译/IPC路径保留。E2E没有调用setFieldValue、程序选中/注册/连接、加载最终图或替换编译响应。真实鼠标、输入、菜单、checkbox、命中/可达性、稳定身份、语义诊断和正常退出门均保留。sandbox=true、contextIsolation=true、nodeIntegration=false、webSecurity及严格CSP/nonce不变。

本阶段实际修复包括Inspector逻辑对象与HTML焦点分离、从真实manager同步发布注册状态，以及原生选择回写不再重复居中关闭活动编辑器；测试helper统一核锁定Blockly真实静态label/紧邻editable/header结构。每轮真实失败、准确首错、定向RED/GREEN和独立审查均保存在implementation-progress.md，没有盲重跑旧CI、放宽断言或重试受限接口。本地最后check、397 TS/950 Python/36 Node回归、桌面build全部PASS；本地SVG/React受控布局回归不冒充GUI证据，GUI证明来自本轮实际Windows步骤SUCCESS。

Windows native缓存/主机信任安全合同、冻结backend、HTTP/资源、应用环境隔离、打包保护、实际build、ZIP审计、包内PID/鉴权/资源/EOF和上传均SUCCESS。本执行器仅读取允许的run/jobs元数据及审计步骤字节/hash，未下载或本机独立重算ZIP，未读取artifact正文。获取候选请使用上述Actions页面，留存期限以工作流为准。

这是未签名、短期验证候选；`distributionReady=false`、`legalReviewComplete=false`。这里只验收空白CNN真实编辑/编译/错误修复/保存重开切片，不代表全M4/M7、真实SSH、正式MNIST训练/效果、硬件矩阵、干净机器TST33或许可验收完成，完整A/B仍未完成。本场景没有启动训练、下载数据/模型、安装训练依赖、连接真实SSH或配置凭据，没有main写入、PR、Release、部署或权限变化。
