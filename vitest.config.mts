import { defineConfig } from "vitest/config";
export default defineConfig({
  test: {
    include: ["apps/**/*.test.mts", "packages/**/*.test.mts"],
    exclude: ["**/node_modules/**", "**/dist*/**"],
  },
});
