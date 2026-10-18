import { useEffect, useRef, useState } from "react";
import type { ComponentProps } from "react";
import type { ConnectionProfile } from "../electron/bridge.js";
import { ConnectionPanel } from "./ConnectionPanel.js";

type Props = ComponentProps<typeof ConnectionPanel>;
export function ServerProfiles(props: Props) {
  const [profiles, setProfiles] = useState<ConnectionProfile[]>([]);
  const [selected, setSelected] = useState<ConnectionProfile | null>(null);
  const [editing, setEditing] = useState<ConnectionProfile | null>(null);
  const [alias, setAlias] = useState("");
  const [host, setHost] = useState("");
  const [port, setPort] = useState("22");
  const [username, setUsername] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const alive = useRef(false);
  useEffect(() => {
    alive.current = true;
    const current = ++generation.current;
    setBusy(true);
    void props.api
      .listProfiles()
      .then((items) => {
        if (alive.current && current === generation.current) setProfiles(items);
      })
      .catch(() => {
        if (alive.current && current === generation.current)
          setError("服务器概要列表读取失败；没有连接服务器。");
      })
      .finally(() => {
        if (alive.current && current === generation.current) setBusy(false);
      });
    return () => {
      alive.current = false;
      generation.current++;
    };
  }, [props.api, props.projectId]);
  function edit(profile: ConnectionProfile | null) {
    generation.current++;
    setSelected(null);
    setEditing(profile);
    setBusy(false);
    setError("");
    setAlias(profile?.alias ?? "");
    setHost(profile?.endpoint.host ?? "");
    setPort(String(profile?.endpoint.port ?? 22));
    setUsername(profile?.username ?? "");
  }
  async function save() {
    const current = ++generation.current;
    const input = { alias, endpoint: { host, port: Number(port) }, username };
    setBusy(true);
    setError("");
    try {
      const value = editing
        ? await props.api.updateProfile(editing.targetId, {
            ...input,
            expectedRevision: editing.revision,
          })
        : await props.api.createProfile(input);
      if (!alive.current || generation.current !== current) return;
      if (
        editing &&
        (value.targetId !== editing.targetId ||
          value.revision !== editing.revision + 1)
      )
        throw new Error("invalid profile");
      setProfiles((items) => [
        ...items.filter((item) => item.targetId !== value.targetId),
        value,
      ]);
      setEditing(value);
      setAlias(value.alias);
      setHost(value.endpoint.host);
      setPort(String(value.endpoint.port));
      setUsername(value.username);
    } catch {
      if (alive.current && generation.current === current)
        setError(
          "保存服务器概要失败。配置可能已过期，或目标仍被活动任务使用；输入已保留。请刷新列表后核对，不会自动重试。",
        );
    } finally {
      if (alive.current && generation.current === current) setBusy(false);
    }
  }
  async function reload() {
    const current = ++generation.current;
    setBusy(true);
    setSelected(null);
    setError("");
    try {
      const value = await props.api.listProfiles();
      if (alive.current && generation.current === current) setProfiles(value);
    } catch {
      if (alive.current && generation.current === current)
        setError("服务器概要列表读取失败。");
    } finally {
      if (alive.current && generation.current === current) setBusy(false);
    }
  }
  return (
    <section className="panel" aria-label="已保存服务器概要">
      <h2>服务器概要</h2>
      <p>
        只保存名称、服务器地址、端口和账号。选择概要仅填入配置；检查指纹、认证和运行都需要单独点击。密码、私钥和
        token 不会保存在概要中。
      </p>
      <ul>
        {profiles.map((profile) => (
          <li key={profile.targetId}>
            <span>
              {profile.alias} · {profile.username}@{profile.endpoint.host}:
              {profile.endpoint.port} · revision {profile.revision}
            </span>
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                generation.current++;
                setSelected(profile);
                setError("");
              }}
            >
              使用此服务器：{profile.alias}
            </button>
            <button type="button" disabled={busy} onClick={() => edit(profile)}>
              编辑概要：{profile.alias}
            </button>
          </li>
        ))}
      </ul>
      <div className="button-row">
        <button type="button" disabled={busy} onClick={() => edit(null)}>
          新建服务器概要
        </button>
        <button type="button" disabled={busy} onClick={() => void reload()}>
          刷新服务器列表
        </button>
      </div>
      {!selected && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          <label className="field">
            概要名称
            <input
              value={alias}
              maxLength={80}
              disabled={busy}
              onChange={(event) => setAlias(event.target.value)}
            />
          </label>
          <label className="field">
            服务器地址
            <input
              value={host}
              maxLength={253}
              autoComplete="off"
              spellCheck={false}
              disabled={busy}
              onChange={(event) => setHost(event.target.value)}
            />
          </label>
          <label className="field">
            服务器端口
            <input
              type="number"
              min={1}
              max={65535}
              value={port}
              disabled={busy}
              onChange={(event) => setPort(event.target.value)}
            />
          </label>
          <label className="field">
            服务器账号
            <input
              value={username}
              maxLength={128}
              autoComplete="off"
              disabled={busy}
              onChange={(event) => setUsername(event.target.value)}
            />
          </label>
          <button type="submit" disabled={busy || !alias || !host || !username}>
            {editing ? "保存概要修改" : "保存服务器概要"}
          </button>
          {editing && (
            <p>
              修改基于 revision {editing.revision}
              ；活动任务使用的目标身份不可修改。
            </p>
          )}
        </form>
      )}
      {busy && <p role="status">正在读取或保存概要；没有建立服务器连接。</p>}
      {error && <p role="alert">{error}</p>}
      {selected && (
        <ConnectionPanel
          {...props}
          key={`${props.projectId}:${selected.targetId}:${selected.revision}`}
          target={selected}
        />
      )}
      {!selected && (
        <button type="button" onClick={props.onClose}>
          关闭主机身份
        </button>
      )}
    </section>
  );
}
