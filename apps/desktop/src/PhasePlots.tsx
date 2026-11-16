import { useEffect, useId, useState } from "react";
import {
  figureLayouts,
  figureSizes,
  type PhaseFigureView,
} from "./WorkspaceManager.js";

const labels = { before: "训练前", body: "每轮结束", after: "训练后" };
const sizes: Record<string, string> = {
  auto: "自动",
  small: "小",
  medium: "中",
  large: "大",
};
export function PhasePlots({
  view,
  readOnly,
  onApply,
  onSelect,
}: {
  view: PhaseFigureView;
  readOnly: boolean;
  onApply(layout: string, size: string): void;
  onSelect(id: string): void;
}) {
  const heading = useId();
  const [layout, setLayout] = useState(view.layout);
  const [size, setSize] = useState(view.size);
  useEffect(() => {
    setLayout(view.layout);
    setSize(view.size);
  }, [view.layout, view.size]);
  const panels = view.disabled
    ? []
    : view.panels.filter((panel) => !panel.disabled);
  return (
    <section aria-labelledby={heading}>
      <h3 id={heading}>{labels[view.phase]} · 图表布局</h3>
      <p className="project-editor-note">
        直接连接到此阶段的图表会组合成一张图片，自动保存在本次运行结果中；每轮图片分别保留。
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!readOnly) onApply(layout, size);
        }}
      >
        <label>
          排列方式
          <select
            value={layout}
            disabled={readOnly}
            onChange={(event) => setLayout(event.target.value)}
          >
            {["auto", ...figureLayouts].map((value) => (
              <option key={value} value={value}>
                {value === "auto" ? "自动排列" : value.replace(",", " × ")}
              </option>
            ))}
          </select>
        </label>
        <label>
          图片尺寸
          <select
            value={size}
            disabled={readOnly}
            onChange={(event) => setSize(event.target.value)}
          >
            {["auto", ...figureSizes].map((value) => (
              <option key={value} value={value}>
                {sizes[value]}
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          disabled={readOnly || (layout === view.layout && size === view.size)}
        >
          应用图表设置
        </button>
      </form>
      <p>
        {panels.length === 0
          ? "尚无启用图表，不生成新图片。"
          : `${panels.length} 个图表，排列为 ${view.rows} 行 ${view.columns} 列。`}
      </p>
      {panels.length > view.rows * view.columns && (
        <p role="alert">布局格子不足，请选择自动排列或更大的布局。</p>
      )}
      {panels.length > 10 && (
        <p role="alert">每个阶段最多放置 10 个直接图表。</p>
      )}
      {view.legacyCount > 0 && (
        <p className="project-editor-note">
          此阶段还有 {view.legacyCount}{" "}
          个旧工程画布，仍使用各自的布局和保存设置。
        </p>
      )}
      {panels.length > 0 && (
        <ol
          className="figure-grid"
          data-columns={view.columns}
          aria-label={`${labels[view.phase]}图表排列预览`}
        >
          {Array.from(
            { length: Math.max(view.rows * view.columns, panels.length) },
            (_, index) => {
              const panel = panels[index];
              return (
                <li key={panel?.id ?? index}>
                  {panel ? (
                    <button type="button" onClick={() => onSelect(panel.id)}>
                      图表 {index + 1} ·{" "}
                      {panel.chartType === "image_grid"
                        ? "图片"
                        : panel.chartType === "scatter"
                          ? "散点图"
                          : "折线图"}
                    </button>
                  ) : (
                    <span>空格子</span>
                  )}
                </li>
              );
            },
          )}
        </ol>
      )}
    </section>
  );
}
