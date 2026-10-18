import { defineConfig } from "vite";
import { styleNoncePlugin } from "../../scripts/style-nonce-adapter.mjs";
export default defineConfig({
  plugins: [styleNoncePlugin()],
  optimizeDeps: { exclude: ["blockly/core", "monaco-editor"] },
});
