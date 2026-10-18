# M8.2 electron-builder 本地打包合同

精确开发依赖 electron-builder 26.15.3，来自 npm 正规注册表，完整 integrity/transitive graph 在 pnpm-lock.yaml。安装时使用 --ignore-scripts；不新增 lifecycle 白名单，不安装训练依赖。Node/Electron 等原直接版本保持；pnpm 自动解析的可选 peer 绑定变化保留于锁文件并定向复检。MIT 依赖声明不代表项目或所有捆绑资源已完成法律审查。

入口：先 `pnpm build`，再 `pnpm package:builder`。当前仅同主机 Linux x64；其他平台提前拒绝。真实调用 electron-builder API，显式 Linux dir 与 tar.gz，publish=never、publish配置null、不签名、不原生重建、不下载替代Electron。使用已安装、版本与ELF匹配的Electron目录；builder默认目标、自动发布和系统安装器不在本入口范围。

打包前复用原stagePortable的资源/架构/hash、显式应用/离线文档/教程/示例与notices allowlist。暂存位于独立dist/easyai-builder-<完整HEAD前12位>-<本次时间戳>-linux-x64/input；此处临时复制完整Electron以复用已验证的流程，增加磁盘占用，不改旧便携包或缓存。输出目录独占mkdir，已有或失败目录原样保留，不覆盖重跑。

builder将应用dist、dist-electron及最小package.json置于resources/app.asar；PyInstaller目录完整复制到resources/backend（包括_internal），供既有Main backendLocation使用，不放进ASAR；offline/notices独立resources目录，Electron许可证在产品根保留。无checkout node_modules/用户配置/运行数据/密钥进入app stage。应用依赖已由Vite打入dist，Main仅使用Electron/Node内置模块。

生成物在artifacts/linux-unpacked及easyai-0.0.0-linux-x64.tar.gz。builder-manifest.json绑定完整源码HEAD、builder/Electron版本及所有输出文件的相对路径/字节/hash/mode；它是完整性清单，不是签名或可信来源证明。`pnpm package:builder:verify <输出目录>` 检查实际完整清单、额外文件、ASAR入口及开发目录排除。构建完成额外对比ASAR关键入口和sidecar内置资源与当前输入；读取不发布、不运行窗口。临时stage和构建日志不属于分发归档。

`node scripts/test-frozen.mjs <artifacts/linux-unpacked/resources/backend>` 可从临时cwd验证实际包内sidecar的鉴权、资源、17卡离线计划、禁执行登记/取消、项目创建、黄金编译及EOF退出；不会启动训练、探测训练环境或连接SSH。不将直接启动sidecar当作真实Electron桌面验收。

所有本地包为unsigned-local，distributionReady=false、legalReviewComplete=false。原生Electron窗口沿用已知sandbox阻塞，不重试/绕过；无Node/开发Python的干净目标机、课堂编辑/已备训练环境连接和平台签名/系统兼容仍NOT RUN，不能宣称完整M8.2/B通过。正式Release/部署/上传/费用/许可接受或安全权限变化不由本入口授权。

官方依据：官网默认文档目前标注next v27，稳定入口为https://www.electron.build/v26/；配置概念参考https://www.electron.build/docs/contents/（files与extraResources），最终选项以本地26.15.3自带configuration.d.ts、PlatformSpecificBuildOptions.d.ts及build API为准。npm元数据确认26.15.3/Node>=14/MIT，未采用next选项。
