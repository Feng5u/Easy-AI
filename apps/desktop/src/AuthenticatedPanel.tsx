import { useEffect, useRef, useState } from "react";
import type {
  AuthenticatedConnection,
  DesktopAPI,
  EnvironmentCatalog,
  EnvironmentProbeResult,
  EnvironmentRequest,
} from "../electron/bridge.js";

interface Pending {
  requestId: string;
  timer?: ReturnType<typeof setTimeout>;
}
export function AuthenticatedPanel({
  api,
  environments,
  projectId,
  identityRequestId,
  onInvalidated,
}: {
  api: DesktopAPI["connections"];
  environments: DesktopAPI["environments"];
  projectId: string;
  identityRequestId: string;
  onInvalidated(): void;
}) {
  const passwordInput = useRef<HTMLInputElement>(null);
  const [username, setUsername] = useState("");
  const [session, setSession] = useState<AuthenticatedConnection | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const auth = useRef<Pending | null>(null);
  const lease = useRef<AuthenticatedConnection | null>(null);
  function invalidate() {
    const previous = auth.current;
    auth.current = null;
    if (previous) {
      clearTimeout(previous.timer);
      void api.cancelAuth(projectId, previous.requestId).catch(() => undefined);
    }
    const owned = lease.current;
    lease.current = null;
    if (owned)
      void api
        .close(projectId, owned.scope.connectionId)
        .catch(() => undefined);
    if (passwordInput.current) passwordInput.current.value = "";
  }
  useEffect(() => () => invalidate(), [api, projectId, identityRequestId]);
  function expire() {
    invalidate();
    setSession(null);
    setUsername("");
    setBusy(false);
    onInvalidated();
  }
  useEffect(() => {
    if (!session) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    let watchdog: ReturnType<typeof setTimeout>;
    const poll = async () => {
      watchdog = setTimeout(() => {
        if (active && lease.current === session) expire();
      }, 10000);
      try {
        const value = await api.current(projectId, session.scope.connectionId);
        if (!active || lease.current !== session) return;
        if (!value) {
          expire();
          return;
        }
        timer = setTimeout(() => void poll(), 5000);
      } catch {
        if (active && lease.current === session) expire();
      } finally {
        clearTimeout(watchdog);
      }
    };
    timer = setTimeout(() => void poll(), 5000);
    return () => {
      active = false;
      clearTimeout(timer);
      clearTimeout(watchdog);
    };
  }, [api, projectId, session]);
  async function authenticate() {
    let password = passwordInput.current?.value ?? "";
    if (passwordInput.current) passwordInput.current.value = "";
    if (!username || !password || auth.current) {
      password = "";
      return;
    }
    const operation: Pending = { requestId: globalThis.crypto.randomUUID() };
    auth.current = operation;
    setBusy(true);
    setMessage("");
    operation.timer = setTimeout(() => {
      if (auth.current === operation) expire();
    }, 25000);
    try {
      const value = await api.authenticate(
        projectId,
        operation.requestId,
        identityRequestId,
        username,
        password,
      );
      if (auth.current !== operation) return;
      clearTimeout(operation.timer);
      lease.current = value;
      setSession(value);
    } catch {
      if (auth.current === operation) {
        invalidate();
        setBusy(false);
        setMessage("认证未完成，请重新检查主机身份后再输入密码。");
      }
    } finally {
      password = "";
      if (auth.current === operation) {
        clearTimeout(operation.timer);
        setBusy(false);
      }
    }
  }
  return (
    <section aria-label="SSH 用户认证">
      {!session ? (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void authenticate();
          }}
        >
          <p>
            已核对主机指纹。用户认证成功后才能检查环境。密码仅用于本次短时会话。
          </p>
          <label className="field">
            SSH 用户名
            <input
              value={username}
              autoComplete="off"
              maxLength={128}
              disabled={busy || !!auth.current}
              onChange={(event) => setUsername(event.target.value)}
            />
          </label>
          <label className="field">
            SSH 密码
            <input
              ref={passwordInput}
              type="password"
              autoComplete="off"
              maxLength={1024}
              disabled={busy || !!auth.current}
            />
          </label>
          <button type="submit" disabled={busy || !!auth.current || !username}>
            认证并建立短时会话
          </button>
          {busy && <p role="status">正在认证…</p>}
        </form>
      ) : (
        <>
          <p role="status">已认证，固定会话最长 5 分钟。环境需单独检查。</p>
          <EnvironmentPanel
            api={environments}
            session={session}
            onInvalidated={expire}
          />
        </>
      )}
      <button type="button" onClick={expire}>
        关闭认证会话
      </button>
      {message && <p role="alert">{message}</p>}
    </section>
  );
}
export function EnvironmentPanel({
  api,
  session,
  onInvalidated,
}: {
  api: DesktopAPI["environments"];
  session: AuthenticatedConnection;
  onInvalidated(): void;
}) {
  const [mode, setMode] = useState("auto");
  const [path, setPath] = useState("");
  const [catalog, setCatalog] = useState<EnvironmentCatalog | null>(null);
  const [selected, setSelected] = useState("");
  const [device, setDevice] = useState<"cpu" | "cuda" | "mps">("cpu");
  const [dataset, setDataset] = useState<
    "" | "MNIST" | "FashionMNIST" | "CIFAR10"
  >("");
  const [dataRoot, setDataRoot] = useState("");
  const [report, setReport] = useState<EnvironmentProbeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const pending = useRef<(Pending & EnvironmentRequest) | null>(null);
  function cancel() {
    const operation = pending.current;
    pending.current = null;
    if (operation) {
      clearTimeout(operation.timer);
      void api
        .cancel({
          projectId: operation.projectId,
          connectionId: operation.connectionId,
          requestId: operation.requestId,
        })
        .catch(() => undefined);
    }
  }
  useEffect(() => () => cancel(), [api, session]);
  function change() {
    setCatalog(null);
    setSelected("");
    setReport(null);
    setMessage("");
  }
  async function run(discover: boolean) {
    if (pending.current) return;
    const operation = {
      projectId: session.projectId,
      connectionId: session.scope.connectionId,
      requestId: globalThis.crypto.randomUUID(),
      timer: undefined as ReturnType<typeof setTimeout> | undefined,
    };
    pending.current = operation;
    setBusy(true);
    setReport(null);
    setMessage("");
    if (discover) {
      setCatalog(null);
      setSelected("");
    }
    operation.timer = setTimeout(() => {
      if (pending.current === operation) {
        cancel();
        onInvalidated();
      }
    }, 25000);
    const request = {
      projectId: operation.projectId,
      connectionId: operation.connectionId,
      requestId: operation.requestId,
    };
    try {
      if (discover) {
        const value = await api.discover({
          ...request,
          ...(mode === "conda"
            ? { condaPath: path }
            : mode === "python"
              ? { pythonPath: path }
              : {}),
        });
        if (pending.current !== operation) return;
        setCatalog(value);
        setSelected(value.environments[0]?.environmentId ?? "");
      } else {
        const value = await api.probe({
          ...request,
          environmentId: selected,
          device,
          ...(dataset ? { dataset: { name: dataset, dataRoot } } : {}),
        });
        if (pending.current !== operation) return;
        setReport(value);
      }
    } catch {
      if (pending.current === operation) {
        setMessage("环境检查未完成，会话已失效；请重新检查身份并认证。");
        onInvalidated();
      }
    } finally {
      if (pending.current === operation) {
        clearTimeout(operation.timer);
        pending.current = null;
        setBusy(false);
      }
    }
  }
  return (
    <section aria-label="远端只读环境检查">
      <h3>远端环境</h3>
      <p>
        检查解释器、依赖与小张量；可选检查现有数据的一个样本（download=False）。不训练。
      </p>
      <fieldset disabled={busy}>
        <label className="field">
          发现方式
          <select
            value={mode}
            onChange={(e) => {
              change();
              setPath("");
              setMode(e.target.value);
            }}
          >
            <option value="auto">自动查找 Conda</option>
            <option value="conda">指定 Conda 绝对路径</option>
            <option value="python">指定 Python 绝对路径</option>
          </select>
        </label>
        {mode !== "auto" && (
          <label className="field">
            远端可执行文件绝对路径
            <input
              value={path}
              maxLength={1024}
              onChange={(e) => {
                change();
                setPath(e.target.value);
              }}
            />
          </label>
        )}
        <button
          type="button"
          disabled={mode !== "auto" && !path.startsWith("/")}
          onClick={() => void run(true)}
        >
          发现环境
        </button>
        {catalog && (
          <>
            <p>发现 {catalog.environments.length} 个环境，尚未探测。</p>
            <label className="field">
              选择环境
              <select
                value={selected}
                onChange={(e) => {
                  setSelected(e.target.value);
                  setReport(null);
                }}
              >
                {catalog.environments.map((e) => (
                  <option key={e.environmentId} value={e.environmentId}>
                    {e.kind}: {e.location}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              检查设备
              <select
                value={device}
                onChange={(e) => {
                  setDevice(e.target.value as typeof device);
                  setReport(null);
                }}
              >
                <option value="cpu">CPU</option>
                <option value="cuda">CUDA</option>
                <option value="mps">MPS</option>
              </select>
            </label>
            <label className="field">
              现有数据检查
              <select
                value={dataset}
                onChange={(e) => {
                  setDataset(e.target.value as typeof dataset);
                  setReport(null);
                }}
              >
                <option value="">暂不检查数据</option>
                {["MNIST", "FashionMNIST", "CIFAR10"].map((name) => (
                  <option key={name}>{name}</option>
                ))}
              </select>
            </label>
            {dataset && (
              <label className="field">
                远端数据根目录
                <input
                  value={dataRoot}
                  maxLength={1024}
                  onChange={(e) => {
                    setDataRoot(e.target.value);
                    setReport(null);
                  }}
                />
              </label>
            )}
            <button
              type="button"
              disabled={!selected || (!!dataset && !dataRoot.startsWith("/"))}
              onClick={() => void run(false)}
            >
              只读检查所选环境
            </button>
          </>
        )}
      </fieldset>
      {busy && (
        <>
          <p role="status">正在检查环境…</p>
          <button
            type="button"
            onClick={() => {
              cancel();
              onInvalidated();
            }}
          >
            取消环境检查并关闭会话
          </button>
        </>
      )}
      {message && <p role="alert">{message}</p>}
      {report && (
        <div aria-label="环境检查报告">
          <p>
            环境：{report.environmentReady ? "就绪" : "未就绪"}；数据：
            {report.dataReady === null
              ? "未检查"
              : report.dataReady
                ? "就绪"
                : "未就绪"}
          </p>
          <p>
            Python {report.report.python.version.join(".")} ·{" "}
            {report.report.python.executable}
          </p>
          <p>
            torch {report.report.imports.torch.version ?? "不可用"}；torchvision{" "}
            {report.report.imports.torchvision.version ?? "不可用"}；matplotlib{" "}
            {report.report.imports.matplotlib.version ?? "不可用"}
          </p>
          <p>小张量：{report.report.tensor.ok ? "通过" : "未通过"}</p>
          {report.issues.map((issue) => (
            <p key={issue.code}>
              {issue.code}：{issue.suggestion}
            </p>
          ))}
        </div>
      )}
    </section>
  );
}
