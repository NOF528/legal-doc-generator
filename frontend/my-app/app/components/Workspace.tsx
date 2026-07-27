"use client";

import { useState } from "react";
import HistoryWorkspace from "./HistoryWorkspace";
import IPWorkspace from "./IPWorkspace";

/* ============================================================
   功能容器：Tab 切换各 SOP 模块
   未来新增模块只需在 FEATURES 数组加一项并注册组件
   ============================================================ */

const FEATURES = [
  { key: "history", label: "历史沿革" },
  { key: "ip", label: "知识产权" },
] as const;

type FeatureKey = (typeof FEATURES)[number]["key"];

export default function Workspace() {
  const [active, setActive] = useState<FeatureKey>("history");

  return (
    <>
      <nav className="kw-tabs">
        <div className="kw-tabs-inner">
          {FEATURES.map((f) => (
            <button
              key={f.key}
              className={`kw-tab ${active === f.key ? "kw-tab-active" : ""}`}
              onClick={() => setActive(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </nav>
      {/* 两个面板都保持挂载，切换 Tab 不丢失已上传的文件和结果 */}
      <div style={{ display: active === "history" ? "block" : "none" }}>
        <HistoryWorkspace />
      </div>
      <div style={{ display: active === "ip" ? "block" : "none" }}>
        <IPWorkspace />
      </div>
    </>
  );
}
