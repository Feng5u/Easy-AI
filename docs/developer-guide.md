# 开发入口

使用Node24.19.0、pnpm11.25.0、uv0.12.23；uv使用Python3.11.17。仓库初始化后执行：

```sh
pnpm install --frozen-lockfile
pnpm setup
pnpm check
pnpm test
pnpm dev
pnpm build
```

setup仅建立应用后端环境并运行Electron官方安装器，不安装torch、不下载课程数据、不访问SSH。Electron下载需要合法网络访问；下载失败不改用未知镜像。受限云环境可把缓存目录定向到/workspace，不要修改HOME或关闭sandbox。Linux需要支持Chromium sandbox及可用桌面显示服务；本次云环境尚不能完成窗口验收。

`pnpm fixtures`由真实Blockly重建fixtures；`pnpm contracts`由Pydantic生成schema和TS。check以只读比较模式检测漂移。生成文件不手改。`pnpm test:e2e`使用真实Electron且明确chromiumSandbox:true，不能为绿色测试关闭sandbox。

原始计划和原需求位于docs。当前只实现启动骨架与合同基础；无可运行训练入口。完整项目API/编译器/Runner、UI与SSH按M2以后实现。训练安装命令尚未开放，避免误装到应用环境。实际验证和限制见implementation-progress.md。

安全依据：[Electron官方安全指南](https://www.electronjs.org/docs/latest/tutorial/security)；序列化依据：[Blockly官方保存恢复说明](https://docs.blockly.com/guides/configure/serialization/)。
