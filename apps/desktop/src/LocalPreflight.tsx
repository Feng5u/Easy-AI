import { useEffect, useRef, useState } from "react";
import type {
  DesktopAPI,
  LocalPreflightRequest,
  LocalPreflightResult,
} from "../electron/bridge.js";

const messages: Record<string, string> = {
  ENVIRONMENT_READY: "依赖导入通过。",
  ENVIRONMENT_PYTHON_UNAVAILABLE:
    "所选 Python 无法启动，请重新选择已有解释器。",
  ENVIRONMENT_IMPORT_FAILED:
    "所选 Python 无法导入 torch、torchvision 或 Matplotlib。请检查该环境；此操作不会安装包。",
  ENVIRONMENT_PROBE_TIMEOUT: "环境检查超时。",
  ENVIRONMENT_PROBE_INVALID: "解释器未返回有效检查报告。",
  ENVIRONMENT_PROBE_CLEANUP_PENDING: "环境检查尚未确认清理，请稍后重试。",
  LOCAL_STORAGE_FORBIDDEN: "本机检查缓存路径不可安全使用。",
  DATASET_READY: "数据文件头与长度检查通过；未验证数据来源或学习效果。",
  DATASET_MISSING_NO_DOWNLOAD:
    "所选目录缺少预期的数据文件。请准备数据或重新选择目录；未下载数据。",
  DATASET_IDX_INVALID: "数据文件格式或长度不符合要求。",
  DATASET_CIFAR10_FORMAT_INVALID:
    "CIFAR10 需要完整的 cifar-10-batches-py Python 格式目录，含五个训练批次、测试批次及元数据；当前文件结构不符合要求。",
  DATASET_CIFAR10_SAFE_PROBE_REQUIRED:
    "CIFAR10 文件布局初检完成，但安全的官方适配器构造探测尚未完成；未反序列化 pickle，数据未就绪，不能开始本机训练。",
  DATA_PATH_FORBIDDEN: "数据路径未通过安全检查。",
  DATASET_UNREADABLE: "数据文件不可读，请检查目录与读取权限。",
  DATASET_PREFLIGHT_NOT_SUPPORTED: "此数据集尚不支持本机预检。",
  DATASET_PROJECT_NOT_RUNNABLE:
    "无法从已保存工程确定有效数据集，请先处理编译问题。",
};
export function LocalPreflight({
  api,
  request,
  pythonLabel,
  dataLabel,
  disabled,
}: {
  api: DesktopAPI["local"];
  request: LocalPreflightRequest;
  pythonLabel: string;
  dataLabel: string;
  disabled: boolean;
}) {
  const [result, setResult] = useState<LocalPreflightResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);
  useEffect(
    () => () => {
      generation.current += 1;
    },
    [],
  );
  async function check() {
    const current = ++generation.current;
    setBusy(true);
    setResult(null);
    setError("");
    try {
      const value = await api.preflight(request);
      if (generation.current !== current) return;
      if (
        value.projectId !== request.projectId ||
        value.expectedRevision !== request.expectedRevision ||
        value.pythonSelectionId !== request.pythonSelectionId ||
        value.dataSelectionId !== request.dataSelectionId
      )
        throw new Error("检查报告与当前选择不一致，请重新检查。");
      setResult(value);
    } catch (reason) {
      if (generation.current === current)
        setError(`本机预检未完成：${String(reason)}`);
    } finally {
      if (generation.current === current) setBusy(false);
    }
  }
  return (
    <section aria-label="本机环境与数据预检">
      <p>
        检查已选择的 Python
        依赖与已保存工程需要的数据。仅执行固定导入探测、读取数据文件头和长度；不训练、不安装、不下载。
      </p>
      <p>
        Python：{pythonLabel}；数据：{dataLabel}
      </p>
      <button
        type="button"
        disabled={disabled || busy}
        onClick={() => void check()}
      >
        检查本机环境与数据
      </button>
      {disabled && <p>请先保存工程；运行期间暂停预检。</p>}
      {busy && <p role="status">正在检查本机环境与数据…</p>}
      {error && <p role="alert">{error}</p>}
      {result && (
        <div role="status">
          <p>
            环境：{result.environment.ok ? "可用" : "未通过"} ·{" "}
            {messages[result.environment.code] ??
              "检查未通过，请查看技术代码。"}{" "}
            <code>{result.environment.code}</code>
          </p>
          {result.versions && (
            <p>
              解释器：{result.versions.python}；torch {result.versions.torch}
              ；torchvision {result.versions.torchvision}；Matplotlib{" "}
              {result.versions.matplotlib}
            </p>
          )}
          <p>
            数据（{result.datasetNames.join("、") || "未确定"}）：
            {result.data.ok ? "可用" : "未通过"} ·{" "}
            {messages[result.data.code] ?? "检查未通过，请查看技术代码。"}{" "}
            <code>{result.data.code}</code>
          </p>
          <p>这是本次选择的检查结果；开始训练时仍会重新检查。</p>
        </div>
      )}
    </section>
  );
}
