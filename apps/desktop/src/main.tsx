import { createRoot } from "react-dom/client";
import { useEffect, useState } from "react";
import "./style.css";

declare global {
  interface Window {
    easyai: { status: { get(): Promise<{ ready: boolean; message: string }> } };
  }
}
function App() {
  const [status, setStatus] = useState("正在连接本地服务…");
  useEffect(() => {
    let active = true;
    void window.easyai.status
      .get()
      .then((s) => {
        if (active) setStatus(s.message);
      })
      .catch(() => {
        if (active)
          setStatus("本地服务无法连接。请关闭后重新启动，或查看开发日志。");
      });
    return () => {
      active = false;
    };
  }, []);
  return (
    <main>
      <p className="eyebrow">EASY-AI · v0.0.0 开发版</p>
      <h1>从积木出发，理解 AI。</h1>
      <p role="status">{status}</p>
      <nav aria-label="工作区">
        <button disabled>数据处理</button>
        <button disabled>模型</button>
        <button disabled>训练管线</button>
      </nav>
      <p>正在构建项目与编译合同；训练功能尚未开放。</p>
    </main>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
