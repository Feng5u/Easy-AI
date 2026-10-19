# a4de782 本地未签名候选

这是真实构建的 Linux x64 验证候选，未发布，完整 A/B 未通过。候选源码为 `a4de782a5efa717868d7180eee18d60e71dfb16a`，Git tree 为 `bf301d98fc4e85ee3f0def4eadd337de80c009d3`。本记录在构建后追加，其证据提交不是候选源码。原最新完整候选来自 `5b3df8d565f75a1f5cdeaf4e2f9300ce04bee17f`，旧产物保留。[CI 39213624352](https://github.com/T1doo/Easy-AI/actions/runs/39213624352) 的 Linux/Windows 均 SUCCESS，但工作流没有候选打包或产物上传步骤；Windows开发启动E2E不等于本Linux包的GUI验收。

## 实际产物与来源

输出根：`dist/easyai-builder-a4de782a5efa-1792393988003-linux-x64`。目录包：`artifacts/linux-unpacked`；仅此目录及同级 tar.gz 为应用候选，input、源快照和构建 venv 不交给应用用户。所有下列收据均已真实落盘，未放进或修改封存的应用归档。

| 文件 | 字节 / SHA256 |
| --- | --- |
| `artifacts/easyai-0.0.0-linux-x64.tar.gz` | 152781550 / `4733c8bd71f1b32836069fa0670843c0db8b98411200feb5ce42f2306b3ee0b9` |
| `builder-manifest.json` | `a04d9c7da1145952cf5540d5fada1c86d8c4d5571675b9eecd8a467ce32a775b` |
| `candidate-audit.json` | `2e4bea775c013b02ed72aecf7fffb055816a1a325fb793783eaf61f534dd6c6d` |
| `candidate-provenance.json` | `080906845b656f30906f7fad89ad8b67ce9caec73f93952f3ee47f7c918f51c7` |
| `artifacts/linux-unpacked/resources/notices/inventory.json` | `e9e536f1ef44649f4be2868b76b08a5f4b9dae5429998677ef474c4350c13a54` |

固定Git快照根为 `dist/builder-inputs-a4de782a5efa-35658474-3034-4b32-aa3d-c5520e80dafe`，其中 `source.tar` SHA256 为 `62aa67af33c07273888fa5fd6f4d2b8189d8b9fd6a38c89c65a48b6c8a3c8c34`，`approved-inputs.json` 为 `eeed98b293e957214762b40fafab529678cbb41e12e0f16261276e72568fb03d`。清单绑定 app35/backend142/offline20/notices58/vendor72 五组；输出296记录，归档内294普通文件。64个实际 easyai Python源文件均来自该快照，7个namespace占位符不当成文件，未发现回退原工作区源码。

## 依赖与许可边界

Node24.19.0、pnpm11.25.0、uv0.12.23、CPython3.11.17、PyInstaller6.18.0、electron-builder26.15.3。Electron44.9.0取自既有官方校验缓存，新解压后使用；archive SHA256 `ecced7ecb55697f92ca870939c5988557faa8acd8c222c232cae5913d318c8b9`，与旧候选同一vendor来源。354个Node包复用store、下载0；原应用uv锁在新快照venv离线准备43包，没有torch/torchvision等训练环境安装。未改原应用venv或教师共享环境。

来源完整性：`pnpm-lock.yaml` SHA256 `886aa7c3d4943909de165f313ac3eaae1260e0b4cd2849995cd960ddc40e046c`；`services/backend/uv.lock` SHA256 `7a04b74c033975f0bdea0c4cc7f828d15edd36efc4abaa2d83fcf10a9f9bf77c`。其他配置/声明的逐文件字节和hash见 candidate-provenance.json。

随包保留Electron/Chromium许可、第三方NOTICE与50项inventory：7项前端依赖和43项已安装应用Python发行包（包括开发/构建依赖，非精确冻结依赖集合）。没有新增许可接受、费用或凭据；项目许可证尚未声明，精确native/系统库义务和最终支持矩阵仍未审核。`legalReviewComplete=false`、`distributionReady=false`，不授权分发或正式发布。构建宿主glibc2.41，不据此宣称较旧Linux兼容；干净目标机还需核显示服务、系统库和sandbox条件。

## 实际验证与未验范围

PASS：原有Git tracked普通文件快照、clean/HEAD门、逐文件批准闭集、ASAR精确内容/metadata、冻结resourcePairs和vendor变换校验；没有放宽任何门或使用旧dist拼包。tar只读逐项核bytes/mode/hash/集合，通过，无链接、特殊文件、重复或越界。原隐私路径过滤仍在；额外对294个unpacked文件（含ASAR原始字节）扫描完整私钥块、GitHub token、AWS access ID、OpenAI token特征，零命中。该有限扫描不检查任意秘密，也不解析PYZ/native嵌入内容，不是零秘密证明。

PASS：包内真实冻结sidecar在临时cwd完成精确ready三字段/端口/child PID、Bearer鉴权、资源/native选择API、项目创建、黄金编译、离线安装计划及显式登记/取消（执行仍禁用）、stdin EOF正常退出。身份/停止/受控安装门保留；没有实际SSH或安装。构建保留原有大chunk、缺description/author等警告，没有为了消除警告扩展元数据或权限。

NOT RUN：本包Electron GUI/原生picker/Blockly课堂流、干净目标机TST33、Windows/macOS候选包、GPU/MPS矩阵、真实MNIST正式10轮、真实SSH、训练环境安装、数据/模型下载、签名、发布、部署。既有Electron sandbox拒绝没有重试或绕过。CIFAR安全构造、Windows生产storage门和受控安装默认禁执行边界均未改变。下一项是对明确目标和窗口获得授权后验证该精确归档的干净机/课堂路径；目前不能称完整demo。

独立只读审查PASS：独立verifier296记录、tar294文件逐项核验、Git archive的558个tracked文件与固定提交逐字一致；本范围无明确P1/P2。未重建、联网或执行GUI/SSH/训练。
