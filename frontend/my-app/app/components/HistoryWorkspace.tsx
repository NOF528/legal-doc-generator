"use client";

import { useRef, useState } from "react";
import {
  Plus,
  ArrowUp,
  Info,
  X,
  FileText,
  Lightbulb,
  ChevronUp,
  Mail,
  MessageCircle,
  List,
  Download,
  ClipboardList,
} from "lucide-react";

/* ============================================================
   常量
   ============================================================ */

const BRAND = "一只鱼律";
const PRODUCT = "历史沿革生成器";
const WECHAT = "一只鱼律";
const EMAIL = "northoceanfish01@gmail.com";

/* ============================================================
   类型
   ============================================================ */

interface Draft {
  date: string;
  sequence_title: string;
  draft_text: string;
  missing_fields: string[];
  warnings: string[];
}

interface HistoryResult {
  company_name: string;
  history_evolution: {
    drafts: Draft[];
    changes_count: number;
  };
  missing_fields: string[];
}

/* ============================================================
   工具：【**】占位高亮（灰底，不用彩色）
   ============================================================ */

function highlight(text: string) {
  const parts = text.split(/(【[^】]*】)/g);
  return parts.map((part, i) =>
    part.startsWith("【") ? <mark key={i}>{part}</mark> : part
  );
}

/** 把草稿文本渲染为段落 + 表格（识别 Markdown 表格行） */
function DraftBody({ text }: { text: string }) {
  const lines = text.split("\n");
  const blocks: React.ReactNode[] = [];
  let tableLines: string[] = [];

  const flushTable = (key: number) => {
    if (tableLines.length === 0) return;
    const rows = tableLines
      .map((l) =>
        l
          .split("|")
          .slice(1, -1)
          .map((c) => c.trim())
      )
      .filter((cells) => !cells.every((c) => /^[:\-]*$/.test(c)));
    if (rows.length > 0) {
      const [head, ...body] = rows;
      blocks.push(
        <table key={key} className="kw-event-table">
          <thead>
            <tr>
              {head.map((c, i) => (
                <th key={i}>{highlight(c)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {body.map((r, i) => (
              <tr key={i}>
                {r.map((c, j) => (
                  <td key={j}>{highlight(c)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      );
    }
    tableLines = [];
  };

  lines.forEach((line, idx) => {
    if (line.trim().startsWith("|")) {
      tableLines.push(line.trim());
      return;
    }
    flushTable(idx);
    if (line.trim()) {
      blocks.push(<p key={idx}>{highlight(line)}</p>);
    }
  });
  flushTable(lines.length);

  return <div className="kw-event-body">{blocks}</div>;
}

/** 二维码图片（真实公众号二维码） */
function QRImage() {
  return (
    <img
      src="/wechat-qr.jpg"
      alt="公众号二维码"
      width={200}
      height={200}
      style={{ display: "block", margin: "0 auto", borderRadius: "12px" }}
    />
  );
}

/* ============================================================
   主组件
   ============================================================ */

export default function HistoryWorkspace() {
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<HistoryResult | null>(null);
  const [showInfo, setShowInfo] = useState(true);
  const [showQR, setShowQR] = useState(false);
  const [showGuide, setShowGuide] = useState(false);
  const [toast, setToast] = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(""), 2000);
  };

  /* ---------- 文件选择 ---------- */

  const acceptFile = (f: File | undefined | null) => {
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      setError("请上传企查查 PDF 格式的企业信用报告");
      return;
    }
    setError("");
    setFile(f);
  };

  /* ---------- 生成 ---------- */

  const generate = async () => {
    if (!file || loading) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/v1/qcc/history-evolution", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data?.error?.message || data?.detail || "解析失败，请重试");
      }
      setResult(data);
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
    } catch (e) {
      setError(e instanceof Error ? e.message : "网络异常，请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  /* ---------- 下载 Word ---------- */

  const downloadDocx = async () => {
    if (!file || downloading) return;
    setDownloading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/v1/qcc/history-evolution/docx", { method: "POST", body: fd });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.error?.message || "导出失败，请重试");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${result?.company_name || "公司"}_历史沿革.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "导出失败，请重试");
    } finally {
      setDownloading(false);
    }
  };

  /* ---------- 邮箱 ---------- */

  const copyEmail = async () => {
    try {
      await navigator.clipboard.writeText(EMAIL);
      showToast("邮箱已复制，欢迎联系");
    } catch {
      window.location.href = `mailto:${EMAIL}`;
    }
  };

  /* ---------- 时间轴年份分组 ---------- */

  const yearOf = (date: string) => date.match(/(\d{4})年/)?.[1] || "";

  let lastYear = "";

  return (
    <div className="kw-page">
      {/* Toast */}
      {toast && <div className="kw-toast">{toast}</div>}

      <div className="kw-container">
        {/* 品牌区 */}
        <section className="kw-brand kw-fade-up">
          <h1 className="kw-brand-title">{PRODUCT}</h1>
          <p className="kw-brand-contact">
            公众号：{WECHAT} · {EMAIL}
          </p>
        </section>

        {/* 提示条 */}
        {showInfo && (
          <div className="kw-infobar kw-fade-up">
            <Info size={16} strokeWidth={1.5} />
            <span>仅收录股权转让、增资、减资三类变更，其余工商变更将自动过滤</span>
            <button className="kw-infobar-close" onClick={() => setShowInfo(false)} aria-label="关闭">
              <X size={14} strokeWidth={1.5} />
            </button>
          </div>
        )}

        {/* 主输入卡片 */}
        <div
          className={`kw-card kw-fade-up ${dragOver ? "kw-dragover" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            acceptFile(e.dataTransfer.files?.[0]);
          }}
        >
          <div className="kw-card-body" onClick={() => !file && fileInputRef.current?.click()}>
            {file ? (
              <span className="kw-file-chip">
                <FileText size={16} strokeWidth={1.5} />
                <span className="kw-file-chip-name">{file.name}</span>
                <button
                  className="kw-file-chip-remove"
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                    setResult(null);
                  }}
                  aria-label="移除文件"
                >
                  <X size={14} strokeWidth={1.5} />
                </button>
              </span>
            ) : (
              <span className="kw-card-placeholder">
                拖入企查查 PDF 报告，或点击 ＋ 选择文件，我来生成历史沿革…
              </span>
            )}
          </div>
          <div className="kw-card-toolbar">
            <button className="kw-icon-btn" onClick={() => fileInputRef.current?.click()} aria-label="选择文件">
              <Plus size={20} strokeWidth={1.5} />
            </button>
            <button
              className={`kw-send-btn ${file && !loading ? "kw-active" : ""}`}
              onClick={generate}
              disabled={!file || loading}
              aria-label="开始生成"
            >
              <ArrowUp size={18} strokeWidth={2} />
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            hidden
            onChange={(e) => acceptFile(e.target.files?.[0])}
          />
        </div>

        {/* 错误提示 */}
        {error && (
          <div className="kw-error kw-fade-up">
            <Info size={16} strokeWidth={1.5} />
            <span>{error}</span>
          </div>
        )}

        {/* 功能药丸：只保留两个，单独一行 */}
        <div className="kw-pills-row kw-fade-up">
          <span className="kw-pill">
            <Download size={14} strokeWidth={1.5} />
            导出 Word
          </span>
          <span className="kw-pill">
            <List size={14} strokeWidth={1.5} />
            时间轴视图
          </span>
        </div>

        {/* 联系药丸：另起一行，交错排列 */}
        <div className="kw-pills-contact-row kw-fade-up">
          <button className="kw-pill kw-pill-contact" onClick={() => setShowQR(true)}>
            <MessageCircle size={14} strokeWidth={1.5} />
            公众号：{WECHAT}
          </button>
          <button className="kw-pill kw-pill-contact" onClick={copyEmail}>
            <Mail size={14} strokeWidth={1.5} />
            邮箱联系
          </button>
        </div>

        {/* 骨架屏 */}
        {loading && (
          <div className="kw-result" ref={resultRef}>
            <div className="kw-skeleton" style={{ height: 36, width: "40%", marginBottom: 48 }} />
            {[0, 1, 2].map((i) => (
              <div key={i} className="kw-skeleton" style={{ height: 120, marginBottom: 32 }} />
            ))}
          </div>
        )}

        {/* 结果区 */}
        {result && !loading && (
          <section className="kw-result kw-fade-up" ref={resultRef}>
            <h2 className="kw-result-title">{result.company_name}</h2>
            <p className="kw-result-meta">
              共识别 {result.history_evolution.changes_count} 次股权类变更 · 以下内容由企查查报告生成，请核对后使用
            </p>

            <div className="kw-timeline">
              {result.history_evolution.drafts.map((draft, i) => {
                const year = yearOf(draft.date);
                const showYear = year !== lastYear;
                lastYear = year;
                return (
                  <div className="kw-event" key={i}>
                    <span className="kw-event-node" />
                    {showYear && <span className="kw-event-year">{year}</span>}
                    <h3 className="kw-event-title">{draft.sequence_title}</h3>
                    <DraftBody text={draft.draft_text} />
                  </div>
                );
              })}
            </div>

            {/* 待补充清单 */}
            {result.missing_fields?.length > 0 && (
              <div className="kw-missing">
                <p className="kw-missing-title">
                  <ClipboardList size={16} strokeWidth={1.5} />
                  {result.missing_fields.length} 项信息需要你手动补充
                </p>
                <ul className="kw-missing-list">
                  {result.missing_fields.map((m, i) => (
                    <li key={i}>{m}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* 下载 */}
            <div className="kw-actions">
              <button className="kw-download-btn" onClick={downloadDocx} disabled={downloading}>
                <Download size={16} strokeWidth={1.5} />
                {downloading ? "导出中…" : "下载 Word 文档"}
              </button>
            </div>

            <p className="kw-watermark">
              由 {BRAND} · {PRODUCT} 生成
            </p>
          </section>
        )}
      </div>

      {/* 底部探索条 + 页脚 */}
      <div className="kw-explore-wrap">
        <div className="kw-container">
          <button className="kw-explore" onClick={() => setShowGuide(true)}>
            <span>
              <Lightbulb size={16} strokeWidth={1.5} />
              探索灵感
            </span>
            <span>
              滑动探索 <ChevronUp size={14} strokeWidth={1.5} />
            </span>
          </button>
          <footer className="kw-footer">
            © 2026 {BRAND} · {PRODUCT}　|　
            <button onClick={() => setShowQR(true)}>公众号：{WECHAT}</button>
            　|　联系邮箱：<a href={`mailto:${EMAIL}`}>{EMAIL}</a>
          </footer>
        </div>
      </div>

      {/* 公众号二维码弹层 */}
      {showQR && (
        <div className="kw-modal-mask" onClick={() => setShowQR(false)}>
          <div className="kw-modal" onClick={(e) => e.stopPropagation()}>
            <p className="kw-modal-title">微信公众号：{WECHAT}</p>
            <QRImage />
            <p className="kw-modal-text">欢迎大佬关注，共同进步</p>
          </div>
        </div>
      )}

      {/* 使用说明弹层 */}
      {showGuide && (
        <div className="kw-modal-mask" onClick={() => setShowGuide(false)}>
          <div className="kw-modal" onClick={(e) => e.stopPropagation()}>
            <p className="kw-modal-title">如何使用</p>
            <ol>
              <li>在企查查下载目标公司的「企业信用报告」PDF。</li>
              <li>将 PDF 拖入上方输入框，点击发送按钮开始生成。</li>
              <li>系统只保留股权转让、增资、减资三类变更，其余自动过滤。</li>
              <li>下载 Word 后，按「待补充清单」完善【**】占位内容即可定稿。</li>
            </ol>
          </div>
        </div>
      )}
    </div>
  );
}
