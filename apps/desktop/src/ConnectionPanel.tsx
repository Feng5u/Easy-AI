import { AuthenticatedPanel } from "./AuthenticatedPanel.js";
import { useEffect, useRef, useState } from "react";
import type {
  DesktopAPI,
  IdentityResult,
  RemoteRunControls,
} from "../electron/bridge.js";

const messages: Record<string, string> = {
  SSH_HOST_KEY_CHANGED: "主机密钥已变化，已拒绝信任。请联系管理员核对。",
  SSH_IDENTITY_BUSY: "上一项检查仍在退出，请稍后重新检查。",
  SSH_IDENTITY_PROJECT_CHANGED: "工程已切换，请重新检查当前目标。",
  SSH_IDENTITY_REQUEST_RETIRED: "本次检查已失效，请重新检查。",
  SSH_IDENTITY_CONFIRMATION_STALE: "确认已失效，请重新检查目标和指纹。",
  SSH_CONFIRMATION_EXPIRED: "指纹确认已过期，请重新检查。",
  SSH_TRUST_PERMISSIONS_UNSAFE:
    "主机信任存储权限不安全，已拒绝操作；请由管理员检查。",
  SSH_TRUST_PLATFORM_UNVERIFIED: "当前平台的安全信任存储尚未完成验证。",
  SSH_TIMEOUT: "主机检查超时，请核对目标后手动重试。",
  SSH_IDENTITY_REQUEST_LIMIT: "短时间内检查过多，请稍后重试。",
};
interface Pending {
  id: string;
  timer?: ReturnType<typeof setTimeout>;
}
export function ConnectionPanel({
  api,
  environments,
  projectId,
  onClose,
  remote,
}: {
  api: DesktopAPI["connections"];
  environments?: DesktopAPI["environments"];
  projectId: string;
  onClose(): void;
  remote?: RemoteRunControls;
}) {
  const [host, setHost] = useState("");
  const [port, setPort] = useState("22");
  const [result, setResult] = useState<IdentityResult | null>(null);
  const [verified, setVerified] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const pending = useRef<Pending | null>(null);
  function invalidate() {
    const previous = pending.current;
    pending.current = null;
    if (previous) {
      clearTimeout(previous.timer);
      void api.cancel(projectId, previous.id).catch(() => undefined);
    }
  }
  useEffect(() => () => invalidate(), [api, projectId]);
  function reset() {
    remote?.onBinding(null);
    remote?.onSession(null);
    invalidate();
    setBusy(false);
    setResult(null);
    setVerified(false);
    setMessage("");
  }
  function deadline(operation: Pending) {
    clearTimeout(operation.timer);
    operation.timer = setTimeout(() => {
      if (pending.current !== operation) return;
      invalidate();
      setBusy(false);
      setResult(null);
      setVerified(false);
      setMessage("等待已超时；旧响应已失效，请稍后重新检查。");
    }, 25000);
  }
  async function probe() {
    reset();
    const targetPort = Number(port);
    if (
      !host ||
      host.length > 253 ||
      !Number.isSafeInteger(targetPort) ||
      targetPort < 1 ||
      targetPort > 65535
    ) {
      setMessage("请输入主机名或 IP，以及 1–65535 的端口。");
      return;
    }
    const operation: Pending = { id: globalThis.crypto.randomUUID() };
    pending.current = operation;
    setBusy(true);
    deadline(operation);
    try {
      const value = await api.probe(projectId, operation.id, {
        host,
        port: targetPort,
      });
      if (pending.current !== operation) return;
      clearTimeout(operation.timer);
      setResult(value);
    } catch (error) {
      if (pending.current === operation) {
        invalidate();
        setBusy(false);
        setMessage(describe(error));
      }
    } finally {
      if (pending.current === operation) {
        clearTimeout(operation.timer);
        setBusy(false);
      }
    }
  }
  async function confirm() {
    const operation = pending.current;
    if (!operation || !verified || result?.observation.trustState !== "unknown")
      return;
    setBusy(true);
    setMessage("");
    deadline(operation);
    try {
      const value = await api.confirm(
        projectId,
        operation.id,
        result.observation.fingerprint,
      );
      if (pending.current !== operation) return;
      setResult(value);
      setVerified(false);
    } catch (error) {
      if (pending.current === operation) {
        invalidate();
        setBusy(false);
        setResult(null);
        setVerified(false);
        setMessage(describe(error));
      }
    } finally {
      if (pending.current === operation) {
        clearTimeout(operation.timer);
        setBusy(false);
      }
    }
  }
  const observed = result?.observation;
  return (
    <section className="panel" aria-labelledby="ssh-identity-heading">
      <h2 id="ssh-identity-heading">SSH 主机身份</h2>
      <p>
        目标仅保存在当前工程会话。此步骤只检查服务器身份，不登录、不上传或运行任务。
      </p>
      <label className="field">
        主机名或 IP
        <input
          value={host}
          maxLength={253}
          autoComplete="off"
          spellCheck={false}
          onChange={(event) => {
            reset();
            setHost(event.target.value);
          }}
        />
      </label>
      <label className="field">
        SSH 端口
        <input
          type="number"
          min={1}
          max={65535}
          value={port}
          onChange={(event) => {
            reset();
            setPort(event.target.value);
          }}
        />
      </label>
      <div className="button-row">
        <button
          type="button"
          disabled={busy || !host}
          onClick={() => void probe()}
        >
          {observed ? "重新检查主机指纹" : "检查主机指纹"}
        </button>
        <button
          type="button"
          disabled={!pending.current}
          onClick={() => {
            reset();
            setMessage(
              "已关闭本次检查，旧响应已失效。已完成的信任记录会保留。",
            );
          }}
        >
          取消检查
        </button>
        <button type="button" onClick={onClose}>
          关闭主机身份
        </button>
      </div>
      {busy && <p role="status">正在检查，请稍候…</p>}
      {message && <p role="alert">{message}</p>}
      {observed && (
        <div aria-label="主机指纹结果">
          <dl>
            <dt>实际目标</dt>
            <dd>
              {observed.endpoint.host}:{observed.endpoint.port}
            </dd>
            <dt>算法</dt>
            <dd>{observed.algorithm}</dd>
            <dt>SHA256 指纹</dt>
            <dd>
              <code>{observed.fingerprint}</code>
            </dd>
          </dl>
          {observed.trustState === "unknown" && (
            <>
              <p>
                首次遇到此主机。请通过管理员或其他独立渠道核对上面的目标、算法和指纹。
              </p>
              <label>
                <input
                  type="checkbox"
                  checked={verified}
                  disabled={busy}
                  onChange={(event) => setVerified(event.target.checked)}
                />
                已通过独立渠道核对目标和指纹
              </label>
              <button
                type="button"
                disabled={!verified || busy}
                onClick={() => void confirm()}
              >
                确认信任此指纹
              </button>
            </>
          )}
          {observed.trustState === "changed" && (
            <p role="alert">
              主机密钥已变化，已拒绝信任。原指纹：
              <code>{observed.previousFingerprint}</code>。请联系管理员核对。
            </p>
          )}
          {observed.trustState === "trusted" && environments && result && (
            <AuthenticatedPanel
              key={result.requestId}
              api={api}
              environments={environments}
              projectId={projectId}
              identityRequestId={result.requestId}
              onInvalidated={reset}
              remote={remote}
            />
          )}
          {observed.trustState === "trusted" && (
            <p role="status">
              主机指纹与信任记录一致。信任指纹本身不代表用户认证或环境就绪。
            </p>
          )}
        </div>
      )}
    </section>
  );
}
function describe(error: unknown): string {
  const text = error instanceof Error ? error.message : "";
  const code = text.match(/\bSSH_[A-Z_]{1,80}\b/)?.[0];
  return code && messages[code]
    ? messages[code]
    : "无法完成主机身份检查。请核对目标后重新检查。";
}
