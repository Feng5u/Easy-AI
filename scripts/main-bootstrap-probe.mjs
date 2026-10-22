// Node-only module lifecycle regression. Never launch Electron or a browser.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join, extname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import vm from "node:vm";
import { setImmediate } from "node:timers/promises";

const entry = process.argv[2];
assert(entry, "compiled Main path required");
const require = createRequire(import.meta.url);
const loader = join(
  dirname(require.resolve("playwright-core/package.json")),
  "lib/server/electron/loader.js",
);
const nativeReady = Promise.withResolvers();
const backendReady = Promise.withResolvers();
const loaded = Promise.withResolvers();
const windows = [];
let backendStarts = 0;
const errors = [];
const app = {
  whenReady: () => nativeReady.promise,
  emit: () => false,
  listenerCount: () => 0,
  commandLine: { appendSwitch() {} },
  requestSingleInstanceLock: () => true,
  on() {},
  getPath: () => "/test-owned/state",
  isPackaged: false,
};
class BrowserWindow {
  constructor(options) {
    this.options = options;
    this.webContents = {
      setWindowOpenHandler() {},
      on() {},
    };
    windows.push(this);
  }
  on() {}
  async loadURL(url) {
    assert.equal(url, "easyai://app/index.html");
    loaded.resolve();
  }
}
const electron = {
  app,
  BrowserWindow,
  ipcMain: { handle() {} },
  protocol: { registerSchemesAsPrivileged() {}, handle() {} },
  session: {
    defaultSession: {
      setPermissionRequestHandler() {},
      setPermissionCheckHandler() {},
    },
  },
  dialog: { showErrorBox: (...args) => errors.push(args) },
};
const context = vm.createContext({
  console,
  process: { argv: ["electron", "--remote-debugging-port=0", "app"], env: {} },
  require: (name) => {
    assert.equal(name, "electron");
    return electron;
  },
});
// Execute the pinned real Playwright ready gate, not a reimplementation of it.
vm.runInContext(await readFile(loader, "utf8"), context);
const replacements = {
  electron,
  "node:timers/promises": { setTimeout() {} },
  "node:url": { fileURLToPath },
  "node:path": { dirname, join, extname },
  "node:fs/promises": { readFile },
  "./app-assets.mjs": { renderAppHtml: (text) => text },
  "./workflow.mjs": { MainWorkflow: class {}, WORKFLOW_CHANNELS: [] },
  "./backend.mjs": {
    startBackend: () => {
      backendStarts++;
      return backendReady.promise;
    },
  },
  "./backend-location.mjs": {
    backendLocation: () => ({ executable: "unused", cwd: "unused", args: [] }),
  },
  "./security.mjs": {
    trustedSender: () => false,
    SECURE_PREFERENCES: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
    },
  },
};
const main = new vm.SourceTextModule(await readFile(entry, "utf8"), {
  context,
  initializeImportMeta: (meta) => (meta.url = pathToFileURL(entry).href),
});
await main.link((specifier) => {
  const value = replacements[specifier];
  assert(value, `unexpected Main import: ${specifier}`);
  return new vm.SyntheticModule(
    Object.keys(value),
    function () {
      for (const [key, item] of Object.entries(value))
        this.setExport(key, item);
    },
    { context },
  );
});
let evaluated = false;
const evaluation = main.evaluate().then(() => (evaluated = true));
await setImmediate(); // Drain evaluation jobs; ready remains behind explicit barriers.
assert.equal(
  evaluated,
  true,
  "Main evaluation must finish before native/PW ready",
);
await evaluation;
assert.equal(windows.length, 0);
assert.equal(backendStarts, 0);
app.emit("ready");
nativeReady.resolve();
await context.__playwright_run();
await setImmediate();
assert.equal(windows.length, 1);
assert.equal(backendStarts, 1);
assert.deepEqual(
  { ...windows[0].options.webPreferences },
  {
    preload: join(dirname(entry), "preload.cjs"),
    nodeIntegration: false,
    contextIsolation: true,
    sandbox: true,
    webSecurity: true,
  },
);
backendReady.resolve({ process: { once() {} } });
await loaded.promise;
assert.equal(errors.length, 0);
assert.equal(backendStarts, 1);
console.log(
  "PASS Main evaluation -> native/PW ready -> secure window -> sidecar -> view",
);
