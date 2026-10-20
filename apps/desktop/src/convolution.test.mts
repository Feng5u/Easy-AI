import { expect, it } from "vitest";
import { CONVOLUTION_INPUT, evaluateConvolution } from "./convolution.js";
const ones = (size: number) =>
  Array.from({ length: size }, () => Array<number>(size).fill(1));
it("all nine legal windows of ones sum to nine; one kernel change gives the arithmetic delta", () => {
  const input = ones(5),
    kernel = ones(3),
    before = JSON.stringify(input);
  for (let row = 0; row < 3; row++)
    for (let column = 0; column < 3; column++) {
      const result = evaluateConvolution(input, kernel, row, column);
      expect(result.sum).toBe(9);
      expect(result.terms).toHaveLength(9);
      expect(result.output).toEqual(ones(3).map((row) => row.map(() => 9)));
    }
  kernel[0][0] = 2;
  expect(evaluateConvolution(input, kernel, 0, 0).sum).toBe(10);
  expect(JSON.stringify(input)).toBe(before);
});
it("uses cross-correlation without kernel flipping and recalculates each window", () => {
  const kernel = Array.from({ length: 3 }, () => [0, 0, 0]);
  kernel[0][0] = 1;
  expect(evaluateConvolution(CONVOLUTION_INPUT, kernel, 2, 2)).toMatchObject({
    sum: 13,
    output: [
      [1, 2, 3],
      [6, 7, 8],
      [11, 12, 13],
    ],
  });
  const full = evaluateConvolution(CONVOLUTION_INPUT, ones(3), 0, 0);
  expect(full.terms.map((item) => item.product)).toEqual([
    1, 2, 3, 6, 7, 8, 11, 12, 13,
  ]);
  expect(full.output).toEqual([
    [63, 72, 81],
    [108, 117, 126],
    [153, 162, 171],
  ]);
  const fractional = ones(3);
  fractional[0][0] = 0.5;
  expect(
    evaluateConvolution(CONVOLUTION_INPUT, fractional, 0, 0).sum,
  ).toBeCloseTo(62.5);
});
it.each([
  [-1, 0],
  [0, 3],
  [1.5, 0],
  [Infinity, 1],
  [NaN, 0],
])("rejects invalid window %j", (row, column) => {
  expect(() => evaluateConvolution(ones(5), ones(3), row, column)).toThrow(
    "窗口",
  );
});
it.each(["input-shape", "kernel-shape", "nan", "infinite", "range"])(
  "rejects malformed %s without stale values",
  (variant) => {
    const input = ones(5),
      kernel = ones(3);
    if (variant === "input-shape") input.pop();
    if (variant === "kernel-shape") kernel[1].pop();
    if (variant === "nan") kernel[0][0] = NaN;
    if (variant === "infinite") kernel[0][0] = Infinity;
    if (variant === "range") kernel[0][0] = 11;
    expect(() => evaluateConvolution(input, kernel, 0, 0)).toThrow("矩阵");
  },
);
