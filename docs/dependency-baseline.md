# 依赖基线

验证环境：Debian13 x64，Node24.19.0、pnpm11.25.0、uv0.12.23、CPython3.11.17。Python3.11是计划要求的首个基线，未以宿主3.12冒充。所有传递依赖完整列于pnpm-lock.yaml与services/backend/uv.lock。

| 依赖 | 精确版本 | 用途 |
| --- | --- | --- |
| typescript | 7.0.2 | strict类型检查 |
| vitest | 5.0.5 | TS测试 |
| @playwright/test | 1.64.1 | 真实桌面smoke |
| @types/node | 24.10.1 | Node类型 |
| blockly | 13.4.0 | 真实积木序列化与编辑 |
| json-schema-to-typescript | 16.0.0 | 从权威schema生成类型 |
| prettier | 3.9.10 | TS/JS格式检查 |
| react | 19.3.1 | 界面 |
| react-dom | 19.3.1 | React挂载 |
| electron | 44.9.0 | 安全桌面宿主 |
| vite | 8.3.4 | renderer构建 |
| @types/react | 19.2.14 | React类型 |
| @types/react-dom | 19.2.3 | DOM类型 |

Python应用：FastAPI0.128.0（API）、Uvicorn0.40.0（sidecar）、Pydantic2.12.5（权威合同）、Paramiko4.0.0（后续SSH）。开发：pytest9.0.2、httpx0.28.1、ruff0.14.13、mypy1.19.1、PyInstaller6.18.0、jsonschema4.26.0。完整传递版本在uv.lock；不同时维护requirements第二锁。

兼容证据：TS严格检查、真实headless Blockly save/load与Undo、Python3.11 sidecar子进程、Pydantic导出/TS生成同步、新目录冻结安装、Vite和PyInstaller构建通过。Electron模块与TypeScript需DOM lib声明；这是类型依赖，不是向Main暴露DOM执行能力。TS7构建明确rootDir，无skipLibCheck绕过。

未验证：云环境Electron窗口被OS sandbox前置条件阻断；Windows/macOS桌面和安装包不据此宣称支持。尚未选定torch/torchvision或训练profile锁；应用环境明确无torch。Monaco、electron-builder按M4/M8引入并锁定，当前不谎称它们已集成。
