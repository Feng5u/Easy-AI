# pnpm 11.25.0 构建脚本策略修复

2026-10-19 后续CI证据：父侧通过允许的run/jobs元数据确认 [run39195428530](https://github.com/T1doo/Easy-AI/actions/runs/39195428530) 的Linux/Windows安装门均PASS，原安装阻塞解除。Linux setup/check PASS、pnpm test FAIL（失败正文仍缺）；Windows persistence/实验NTFS/freeze/frozenHTTP资源门均PASS，随后desktop build FAIL、e2e skipped。精确源码a62b48ac04e9c9fd434f9217d78679ebe1a2fa7a本地Linux完整test与desktop build均PASS，不能覆盖云CI FAIL或证明Windows通过。未读被拒接口，本轮无确定修复、不推送触发新CI。最小所需错误段见implementation-progress末节。

起始 HEAD `66c4570ccec7590bfa9621eb0ff33d6a8ea87bd2`，单一写入者、工作区clean，远端开发分支相同；main仍`5323f86232529efcfb52131168ad049f01b219f3`。本修复只处理用户提供的Windows CI run39181255841正文：锁文件校验/下载完成后，`ERR_PNPM_IGNORED_BUILDS: electron-winstaller@5.4.0`。没有重新读取Actions日志或重跑旧SHA；Linux job原失败正文未提供，根因仍UNKNOWN。

## 精确原因与决定

锁中 `electron-builder@26.15.3` → `app-builder-lib@26.15.3` 的 `electron-builder-squirrel-windows@26.15.3` peer → `electron-winstaller@5.4.0`。它是Squirrel功能相关的传递依赖，不是Electron运行时；锁中winstaller本身并非optionalDependency，不能简单声称pnpm会省掉。其自身optionalDependency是`@electron/windows-sign`。

已只读核验本机锁定包的package.json和`script/select-7z-arch.js`：唯一安装hook为`node ./script/select-7z-arch.js`，读取os.arch（代码原样为属性），在包内把`vendor/7z-<arch>.exe/.dll`复制为`vendor/7z.exe/.dll`；没有运行此脚本。并非下载脚本，拒绝也不是判定此包恶意。

Windows CI当前执行后端冻结、desktop build及E2E，没有Squirrel安装器目标。`electron-builder.json`仅声明Linux dir/tar.gz，`scripts/package-builder.mjs`限定linux/x64并明确Platform.LINUX，未提供Windows打包能力。因此当前不需要准备Squirrel的7-Zip，后续若新增该目标必须重新审查，不借此宣称Windows安装器支持。

原配置为`onlyBuiltDependencies: [electron]`。已核pnpm11.25.0本机源码：该旧字段仅在兼容已知字段表中，实际`createAllowBuildFunction`读取`allowBuilds`；不是运行approve-builds。现使用当前[官方构建设置](https://pnpm.io/settings/build#allowbuilds)：

```yaml
strictDepBuilds: true
allowBuilds:
  electron@44.9.0: true
  electron-winstaller@5.4.0: false
```

Electron沿用既有明确安装许可并收窄版本；winstaller明确禁止，非忽略所有未知脚本。未关闭strict、未设ignoreScripts、未全局授权、未改lock/版本/CI目标。将来其它版本winstaller或任何未裁决脚本仍须失败，不自动继承此拒绝规则。

## 有界验证及限制

- PASS：pnpm config读取精确true/false和strict=true。
- FAIL（工具缓存选择，非修复失败）：隔离git archive +新配置，首次`CI=true XDG_CACHE_HOME=/workspace/.cache pnpm install --offline --frozen-lockfile --store-dir /workspace/Easy-AI/.pnpm-store`在空缓存缺@playwright/test tarball；未下载。改用原node_modules/.modules.yaml记录的真实store后执行同命令（store `/workspace/.local/share/pnpm/store`），PASS，354复用、0下载、锁/供应链校验通过。隔离位置`/workspace/easyai-pnpm-policy-7onsg4ra`，不覆盖主工作区依赖。该Linux缓存证据不能替代Windows clean runner。
- PASS：隔离实际包vendor中`7z.exe/.dll`均不存在，证明未准备被禁hook输出；安装状态精确记录上述allowBuilds。
- PASS：独立临时file依赖负例的无害install写marker脚本，在同strict/allowBuilds下真实pnpm install --offline返回ERR_PNPM_IGNORED_BUILDS，marker未出现。只验证未知脚本仍失败，不冒充winstaller/Windows功能测试；fixture不入仓库。
- FAIL（本机pnpm自动依赖核验）：主工作区`pnpm --filter @easyai/desktop check`未进入TS，尝试默认`/home/agent/.local/share/pnpm`失败ENOENT。未提权/重试该目标；使用已完成离线安装的隔离目录直接运行原两条tsc命令，PASS。
- PASS：`node --test scripts/package-builder.test.mjs`，5项；没有生成新包。`git diff --check` PASS。
- NOT RUN：Windows运行/新CI结果、Electron GUI、Squirrel构建、安装脚本执行、真实SSH/训练/受控安装。普通开发分支正常push触发既有两job一次工作流；不额外workflow_dispatch/重跑/读被拒接口，结果需父侧合法渠道确认。

CIFAR待答和真实环境/SSH/安装权限均未改变，原A/B仍未通过。下一项只核本修复SHA的Windows安装门与后续实际结果；Linux另核，不凭历史步骤名同因推断。
