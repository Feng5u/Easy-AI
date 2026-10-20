export const CONVOLUTION_INPUT: readonly (readonly number[])[] = Object.freeze(
  Array.from({ length: 5 }, (_, row) =>
    Object.freeze(
      Array.from({ length: 5 }, (_, column) => row * 5 + column + 1),
    ),
  ),
);
function matrix(
  value: readonly (readonly number[])[],
  size: number,
  bound: number,
): void {
  if (
    value.length !== size ||
    value.some(
      (row) =>
        row.length !== size ||
        row.some(
          (item) =>
            typeof item !== "number" ||
            !Number.isFinite(item) ||
            Math.abs(item) > bound,
        ),
    )
  )
    throw new Error("数值矩阵形状或范围无效。");
}
export function evaluateConvolution(
  input: readonly (readonly number[])[],
  kernel: readonly (readonly number[])[],
  row: number,
  column: number,
) {
  matrix(input, 5, 100);
  matrix(kernel, 3, 10);
  if (
    !Number.isInteger(row) ||
    !Number.isInteger(column) ||
    row < 0 ||
    row > 2 ||
    column < 0 ||
    column > 2
  )
    throw new Error("窗口必须位于合法的3×3输出网格。");
  const termsAt = (r: number, c: number) =>
    kernel.flatMap((values, kr) =>
      values.map((weight, kc) => ({
        input: input[r + kr][c + kc],
        weight,
        product: input[r + kr][c + kc] * weight,
      })),
    );
  const sum = (terms: ReturnType<typeof termsAt>) =>
    terms.reduce((total, item) => total + item.product, 0);
  const terms = termsAt(row, column);
  return {
    terms,
    sum: sum(terms),
    output: Array.from({ length: 3 }, (_, r) =>
      Array.from({ length: 3 }, (_, c) => sum(termsAt(r, c))),
    ),
  };
}
