# Windows 真实编辑与错误修复验收候选

- 源码：`6e2be20efa54eb0c8253dc3f13bb37a29592f6b1`；分支 `codex/demo-v0.0.0`。
- [CI39241524644](https://github.com/T1doo/Easy-AI/actions/runs/39241524644)：Windows job118023240831、Linux job118023241242 均完整 SUCCESS。
- ZIP：`easyai-0.0.0-win-x64.zip`，`435253885` 字节。
- SHA256：`69c358da9e0db34efd67893e926b78112de3910b2a1115a6596e75d45e113e00`。
- 下载：上述 run 的 Artifacts，`easyai-unsigned-win-x64-6e2be20efa54eb0c8253dc3f13bb37a29592f6b1`，上传 SUCCESS，保留一天。

Windows step14 `pnpm test:e2e` 开发态与step19设置 `EASYAI_E2E_PACKAGE` 后的同一场景都 PASS。后者明确断言 `app.isPackaged=true`、`app.asar` 身份、renderer无require、沙盒与原bridge清单；实际冻结后端执行工程保存和Python权威编译，不是浏览器假状态或预置编译结果。系统目录picker仅在测试Main中限定返回临时项目目录，其他IPC/存储/Blockly/Monaco不替换；数据、训练环境与凭据picker不允许调用。应用state通过实际 `app.getPath('userData')` 验证隔离，正常退出后才删除临时工程。

实际UI路径（两个模式各运行完整同一场景）：

1. “新建 MNIST 示例”在新目录创建并打开示例副本；“检查与编译”通过，打开“查看当前工程的只读生成代码”。
2. 实际Monaco textbox的只读派生ARIA、真实键盘插入及全选删除均验证代码不变；本页所有动态style带正确nonce且没有CSP/pageerror标志。
3. 对象列表选 `train_data`：实际编译映射的Dataset声明处于viewport，高亮有非零矩形/正确颜色并与该行Y对齐；先选loader，再点声明行可反向回Dataset ID。
4. “删除所选积木”→真实自动保存→“检查与编译”得到 `REF_NOT_FOUND / DATASET_REF`、说明与禁用运行；“源积木”定位实际DataLoader。
5. “撤销”恢复原Dataset ID，自动保存后重新编译通过；完整生成code与修改前全等。
6. 切“模型结构”保存并正常退出重启，三页块字段/连接/ID/坐标、activeTab、codeVisible与工程revision恢复；再编译code仍全等。只规范化根数组顺序，不忽略字段/坐标或引用。

修复的是产品SVG初始化缺少本地Blockly语言字典，以及固定Monaco HTML几何与严格CSP冲突；另修真实输入实现切换后不适用的私有textarea验收。现有受审Vite适配只命中固定hash的三个renderer sink，解析前移除style属性，用有限布局值CSSOM写回；CSP、nonce、IPC、sandbox均未放宽。旧三轮FAIL和源码排查/红绿/独审记录保存在implementation-progress.md，没有重跑旧失败workflow或掩盖失败。

本执行器仅读允许的run/jobs元数据和audit步骤实际字节/hash，未下载或独立重验ZIP、未取得artifact正文；以上执行证明来自真实CI各步骤SUCCESS。原项目/native cache/trust/冻结/开发与包内backend、打包保护/审计/上传全部保留并SUCCESS。Linux check/test/build完整SUCCESS，本地相关25PASS及独审5PASS不当作额外GUI证明或相加刷总数。

这是未签名短期候选，不是发布；`distributionReady=false`、`legalReviewComplete=false`。本次只验收指定M4/M7编辑与错误修复切片，不代表全M4/M7需求、完整Windows真实SSH、正式MNIST训练/硬件矩阵、干净机器TST33或许可完成；完整A/B未完成。没有训练、数据/模型下载、真实SSH、凭据配置、权限变化、Release/PR/部署或main写入。
