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

原始计划和原需求位于docs。现已有Python权威编译器、真实Blockly序列化、项目持久化/本地训练进程与SSH基础、21类积木和离线教程；真实MNIST课堂链与完整B仍未验。训练环境与应用环境分离，生产安装源码已有受具体离线来源/时效授权约束的接线，默认仍禁用；没有执行真实安装验收，详见install-runtime-configuration.md。完整剩余代码与实测门见remaining-critical-path.md，不把局部测试当全阶段通过。

## 本地打包

先 `pnpm build`，再 `pnpm package`；它只用已安装Electron和PyInstaller onedir产物离线复制，当前实现同宿主Linux x64便携目录。输出 `dist/easyai-0.0.0-linux-x64` 必须不存在；失败半成品保留，不自动覆盖或删除。需要重做时由开发者自行保全/移走旧目录。`pnpm package:verify` 核资源manifest、完整文件集合、hash和可执行位。它不启动Electron、不修改sandbox、不下载工具/数据，也不生成或发布Release。

Main在打包模式只定位resources/backend的冻结可执行文件，无checkout/.venv/PATH回退；开发模式仍使用应用venv。便携根 `easyai` 是保留原sandbox的入口，不把它改名为electron：Electron44会按该默认文件名将app.isPackaged判为false，进而走开发路径。冻结sidecar及所有辅助资源在resources/backend，离线文档/教程在resources/offline，已有许可文本及不完整性说明在resources/notices，原Electron LICENSE和LICENSES.chromium.html留在根。manifest最后写入，缺失或校验失败的目录不能算完整包。

`pnpm test:package` 校验受控fixture的复制/冲突/资源漂移/篡改/链接拒绝；`node scripts/test-portable.mjs` 使用已生成便携目录的Main后端启动函数验证实际冻结HTTP/编译与EOF，不是Electron窗口或干净机器验收。

正式M8.2入口现为 `pnpm package:builder`，精确锁定electron-builder26.15.3，经原资源/许可清单门后实际生成同主机Linux x64 dir与tar.gz；`pnpm package:builder:verify <输出目录>`核完整性及ASAR入口。根electron-builder.json仅供包装入口绑定已核暂存路径，裸CLI默认app目录未准备。未签名、不发布；项目/native/system许可及原生窗口/干净目标机仍未验，distributionReady/legalReviewComplete=false。见[electron-builder合同](electron-builder.md)。旧 `pnpm package` 复制流程与旧portable保持独立。

安全依据：[Electron官方安全指南](https://www.electronjs.org/docs/latest/tutorial/security)；序列化依据：[Blockly官方保存恢复说明](https://docs.blockly.com/guides/configure/serialization/)。


## 完整代码导出

源码桌面入口现支持“导出已保存代码 Bundle”：先保存并检查编译，再由Main原生选择父目录，创建独占UUID子目录；全套辅助文件、可移植工程快照和hash清单一并导出。不会执行Python或读取数据。详见[code-bundle-export.md](code-bundle-export.md)。当前使用既有POSIX受控目录接口，Windows安全门未开放；真实独立训练运行、原生picker与旧便携包更新未验收。
