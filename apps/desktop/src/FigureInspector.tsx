import { useEffect, useId, useState } from "react";
import { figureLayouts, figureSizes } from "./WorkspaceManager.js";
import type { FigureView } from "./WorkspaceManager.js";

const sizeLabels: Record<string, string> = {
  small: "小",
  medium: "中",
  large: "大",
};
const chartLabels: Record<string, string> = {
  line: "折线图",
  scatter: "散点图",
  image_grid: "图像网格",
};
export function FigureInspector({
  figure,
  selectedBlock,
  readOnly,
  onApply,
  onSelect,
}: {
  figure: FigureView;
  selectedBlock: string | null;
  readOnly: boolean;
  onApply(layout: string, size: string): void;
  onSelect(id: string): void;
}) {
  const heading = useId();
  const [layout, setLayout] = useState(figure.layout);
  const [size, setSize] = useState(figure.size);
  useEffect(() => {
    setLayout(figure.layout);
    setSize(figure.size);
  }, [figure.id, figure.layout, figure.size]);
  const compiledPanels = figure.disabled
    ? []
    : figure.panels.filter((panel) => !panel.disabled);
  const slots = Math.max(figure.rows * figure.columns, compiledPanels.length);
  return (
    <section aria-labelledby={heading}>
      <h3 id={heading}>画布布局与子图</h3>
      <p className="project-editor-note">
        网格按编译顺序排列启用子图；停用块不占运行格子。缩容仍保护全部已连接块。这里只配置布局，不显示训练结果。
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!readOnly) onApply(layout, size);
        }}
      >
        <label>
          画布布局
          <select
            value={layout}
            disabled={readOnly}
            onChange={(event) => setLayout(event.target.value)}
          >
            {figureLayouts.map((value) => (
              <option key={value} value={value}>
                {value.replace(",", " × ")}
              </option>
            ))}
          </select>
        </label>
        <label>
          画布尺寸
          <select
            value={size}
            disabled={readOnly}
            onChange={(event) => setSize(event.target.value)}
          >
            {figureSizes.map((value) => (
              <option key={value} value={value}>
                {sizeLabels[value] ?? value}
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          disabled={
            readOnly || (layout === figure.layout && size === figure.size)
          }
        >
          应用布局与尺寸
        </button>
      </form>
      <p>
        当前布局 {figure.rows} × {figure.columns}；已连接 {figure.panels.length}{" "}
        个子图，参与编译 {compiledPanels.length} 个。
      </p>
      {figure.disabled && (
        <p role="status">此画布或所属管线已停用，不会生成图像。</p>
      )}
      {figure.panels.length > figure.rows * figure.columns && (
        <p role="alert">
          配置链（含停用块）超过布局格子数；积木均已保留，调整布局时请选择足够容量。
        </p>
      )}
      <ol
        className="figure-grid"
        data-columns={figure.columns}
        aria-label="启用子图运行网格"
      >
        {Array.from({ length: slots }, (_, index) => {
          const panel = compiledPanels[index];
          const location = `第 ${Math.floor(index / figure.columns) + 1} 行，第 ${(index % figure.columns) + 1} 列`;
          return (
            <li key={panel?.id ?? `empty-${index}`}>
              {panel ? (
                <button
                  type="button"
                  aria-pressed={selectedBlock === panel.id}
                  aria-label={`${location}，子图 ${index + 1}，${chartLabels[panel.chartType] ?? panel.chartType}${panel.disabled ? "，停用" : ""}`}
                  onClick={() => onSelect(panel.id)}
                >
                  子图 {index + 1} ·{" "}
                  {chartLabels[panel.chartType] ?? panel.chartType}
                  {panel.disabled && "（停用）"}
                  <small>{panel.id}</small>
                </button>
              ) : (
                <span aria-label={`${location}，空格子`}>空格子</span>
              )}
            </li>
          );
        })}
      </ol>
      <details>
        <summary>完整配置链（含停用块）</summary>
        <ol aria-label="全部已连接子图">
          {figure.panels.map((panel, index) => (
            <li key={panel.id}>
              <button type="button" onClick={() => onSelect(panel.id)}>
                配置链第 {index + 1} 项 ·{" "}
                {chartLabels[panel.chartType] ?? panel.chartType}
                {panel.disabled ? "（停用）" : ""}
                <small>{panel.id}</small>
              </button>
            </li>
          ))}
        </ol>
      </details>
      {readOnly && (
        <p className="project-editor-note">
          只读快照：可以定位子图，不能修改布局或尺寸。
        </p>
      )}
    </section>
  );
}
