import { useState } from "react";
import { CONVOLUTION_INPUT, evaluateConvolution } from "./convolution.js";
const show = (value: number) => Number(value.toFixed(6)).toString();
export function ConvolutionLab() {
  const [weights, setWeights] = useState(() => Array<string>(9).fill("1"));
  const [position, setPosition] = useState(0);
  const row = Math.floor(position / 3),
    column = position % 3;
  const valid = weights.every(
    (value) =>
      value.trim() !== "" &&
      Number.isFinite(Number(value)) &&
      Math.abs(Number(value)) <= 10,
  );
  const kernel = [0, 1, 2].map((r) =>
    weights.slice(r * 3, r * 3 + 3).map(Number),
  );
  const result = valid
    ? evaluateConvolution(CONVOLUTION_INPUT, kernel, row, column)
    : null;
  return (
    <section className="convolution-lab" aria-label="本地数值卷积实验">
      <h3>5×5 输入与 3×3 核</h3>
      <p>
        stride=1 · padding=0 ·
        bias=0。此处只做本地算术，不训练、不改工程。显示值最多保留六位小数。
      </p>
      <table>
        <caption>固定输入，当前窗口已标记</caption>
        <tbody>
          {CONVOLUTION_INPUT.map((values, r) => (
            <tr key={r}>
              {values.map((value, c) => (
                <td
                  key={c}
                  className={
                    r >= row && r < row + 3 && c >= column && c < column + 3
                      ? "convolution-window"
                      : ""
                  }
                >
                  {value}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <fieldset>
        <legend>编辑卷积核（每项 −10 至 10）</legend>
        <div className="kernel-grid">
          {weights.map((value, index) => (
            <label key={index}>
              核第 {Math.floor(index / 3) + 1} 行第 {(index % 3) + 1} 列
              <input
                type="number"
                min={-10}
                max={10}
                step="any"
                value={value}
                onChange={(event) => {
                  const next = event.target.value;
                  setWeights((previous) =>
                    previous.map((item, at) => (at === index ? next : item)),
                  );
                }}
              />
            </label>
          ))}
        </div>
      </fieldset>
      {!valid && (
        <p role="alert">
          请为每一项输入 −10 至 10 的有限数值；无效时不显示旧计算结果。
        </p>
      )}
      <div className="button-row">
        <button
          type="button"
          disabled={position === 0}
          onClick={() => setPosition((previous) => previous - 1)}
        >
          上一个窗口
        </button>
        <button
          type="button"
          disabled={position === 8}
          onClick={() => setPosition((previous) => previous + 1)}
        >
          下一个窗口
        </button>
        <button
          type="button"
          onClick={() => {
            setWeights(Array<string>(9).fill("1"));
            setPosition(0);
          }}
        >
          重置卷积演示
        </button>
      </div>
      <p>
        窗口左上角：第 {row + 1} 行，第 {column + 1} 列
      </p>
      {result && (
        <>
          <h4>逐项乘积</h4>
          <ol aria-label="九项乘积">
            {result.terms.map((item, index) => (
              <li key={index}>
                {show(item.input)} × {show(item.weight)} = {show(item.product)}
              </li>
            ))}
          </ol>
          <output aria-live="polite">窗口求和：{show(result.sum)}</output>
          <table>
            <caption>3×3 输出（点击选择窗口）</caption>
            <tbody>
              {result.output.map((values, r) => (
                <tr key={r}>
                  {values.map((value, c) => (
                    <td key={c}>
                      <button
                        type="button"
                        aria-label={`输出第 ${r + 1} 行第 ${c + 1} 列`}
                        aria-pressed={row === r && column === c}
                        onClick={() => setPosition(r * 3 + c)}
                      >
                        {show(value)}
                      </button>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
