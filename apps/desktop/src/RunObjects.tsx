import type { RunSource } from "../electron/bridge.js";
import { captureRunSnapshot, locateRunBlock } from "./runSnapshot.js";
import { useMemo } from "react";
const labels = {
  transform: "变换",
  dataset: "数据集",
  dataloader: "加载器",
  model_class: "模型类",
};
export function RunObjects({
  source,
  onLocate,
}: {
  source: RunSource;
  onLocate(id: string): void;
}) {
  const view = useMemo(() => captureRunSnapshot(source), [source]);
  const objects = (Array.isArray(source.objects) ? source.objects : []).filter(
    (item) => {
      if (!item || typeof item !== "object") return false;
      const location = locateRunBlock(view, item.blockId);
      return (
        Object.hasOwn(labels, item.kind) &&
        typeof item.registered === "boolean" &&
        (item.role === null || item.role === "train" || item.role === "test") &&
        location.blockId &&
        location.workspace === item.workspace
      );
    },
  );
  return (
    <section className="panel" aria-label="旧运行对象与注册状态">
      <h3 id="run-objects-heading" tabIndex={-1}>
        旧运行对象与注册状态
      </h3>
      <p>
        仅核对此运行保存快照，不读取当前编辑工程；对象名称不在此摘要中显示。
      </p>
      <p>
        旧快照引用检查：
        {source.referenceCheck === "passed"
          ? "通过；运行时异常仍可能来自生成器或依赖。"
          : source.referenceCheck === "failed"
            ? "存在问题，请核对旧对象。"
            : "未核实。"}
      </p>
      {objects.length ? (
        <ul>
          {objects.map((item, index) => (
            <li key={item.blockId}>
              {labels[item.kind]} #{index + 1} ·{" "}
              {item.role === "train"
                ? "训练角色"
                : item.role === "test"
                  ? "测试角色"
                  : "无数据角色"}{" "}
              · {item.registered ? "已注册" : "未注册"}
              <button type="button" onClick={() => onLocate(item.blockId)}>
                定位旧对象 #{index + 1}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p>没有可核对的对象记录。</p>
      )}
    </section>
  );
}
