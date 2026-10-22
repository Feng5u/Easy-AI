/** Loaded only when a code view becomes visible. No CDN, blob bootstrap or remote worker. */
import EditorWorker from "monaco-editor/editor/editor.worker.js?worker";
import * as monaco from "monaco-editor/editor/editor.api.js";
import "monaco-editor/languages/definitions/python/register.js";
import "../node_modules/monaco-editor/esm/vs/base/browser/ui/codicons/codicon/codicon.css";

// The editor's WorkerManager owns these workers. Removing our final model calls
// _checkStopEmptyWorker and disposes its client; do not terminate another editor's worker.
(
  globalThis as typeof globalThis & { MonacoEnvironment: monaco.Environment }
).MonacoEnvironment = {
  getWorker: () => new EditorWorker({ name: "easyai-code-worker" }),
};
export { monaco };
