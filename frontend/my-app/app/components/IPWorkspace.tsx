"use client";

import { useRef, useState } from "react";
import {
  Info,
  X,
  Mail,
  MessageCircle,
  Download,
} from "lucide-react";
import UploadCard from "./UploadCard";

/* ============================================================
   常量
   ============================================================ */

const BRAND = "一只鱼律";
const PRODUCT = "知识产权生成器";
const WECHAT = "一只鱼律";
const EMAIL = "northoceanfish01@gmail.com";

/* ============================================================
   类型
   ============================================================ */

interface Trademark {
  seq: number;
  name: string;
  status: string;
  app_no: string;
  app_date: string;
  intl_class: string;
  has_image: boolean;
}

interface Patent {
  seq: number;
  name: string;
  patent_type: string;
  legal_status: string;
  app_no: string;
  app_date: string;
}

interface IPResult {
  company_name: string;
  trademarks: Trademark[];
  patents: Patent[];
  trademark_summary_text: string;
  patent_summary_text: string;
  warnings: string[];
}

/* ============================================================
   主组件
   ============================================================ */

export default function IPWorkspace() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<IPResult | null>(null);
  const [showInfo, setShowInfo] = useState(true);
  const [showQR, setShowQR] = useState(false);

  const resultRef = useRef<HTMLDivElement>(null);

  /* ---------- 文件选择 ---------- */

  const acceptFile = (f: File) => {
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
      const res = await fetch("/api/v1/qcc/ip-asset", { method: "POST", body: fd });
      // 先读文本再尝试解析 JSON：网关/代理可能返回 HTML 错误页
      const text = await res.text();
      let data: any = null;
      try {
        data = JSON.parse(text);
      } catch {
        throw new Error(res.ok ? "服务响应异常，请重试" : `服务错误（${res.status}），请稍后重试`);
      }
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
      const res = await fetch("/api/v1/qcc/ip-asset/docx", { method: "POST", body: fd });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.error?.message || "导出失败，请重试");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${result?.company_name || "公司"}_知识产权.docx`;
      // Firefox 要求 <a> 挂载在 DOM 中；延迟 revoke 防 Safari 取消下载
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "导出失败，请重试");
    } finally {
      setDownloading(false);
    }
  };

  /* ---------- 渲染 ---------- */

  return (
    <div className="kw-page">
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
            <span>仅抽取「已注册」商标和「授权」专利，其余自动过滤；商标图案请在 Word 中查看</span>
            <button className="kw-infobar-close" onClick={() => setShowInfo(false)} aria-label="关闭">
              <X size={14} strokeWidth={1.5} />
            </button>
          </div>
        )}

        {/* 主输入卡片 */}
        <UploadCard
          file={file}
          loading={loading}
          placeholder="拖入企查查 PDF 报告，或点击 ＋ 选择文件，我来抽取商标和专利…"
          onFileSelect={acceptFile}
          onFileRemove={() => {
            setFile(null);
            setResult(null);
          }}
          onGenerate={generate}
        />

        {/* 错误提示 */}
        {error && (
          <div className="kw-error kw-fade-up">
            <Info size={16} strokeWidth={1.5} />
            <span>{error}</span>
          </div>
        )}

        {/* 骨架屏 */}
        {loading && (
          <div className="kw-result" ref={resultRef}>
            <div className="kw-skeleton" style={{ height: 36, width: "40%", marginBottom: 48 }} />
            {[0, 1].map((i) => (
              <div key={i} className="kw-skeleton" style={{ height: 160, marginBottom: 32 }} />
            ))}
          </div>
        )}

        {/* 结果区 */}
        {result && !loading && (
          <section className="kw-result kw-fade-up" ref={resultRef}>
            <h2 className="kw-result-title">{result.company_name}</h2>
            <p className="kw-result-meta">
              商标 {result.trademarks.length} 件 · 专利 {result.patents.length} 件 · 以下内容由企查查报告生成，请核对后使用
            </p>

            {/* 警告（报告截断等） */}
            {result.warnings.length > 0 && (
              <div className="kw-error kw-fade-up" style={{ marginBottom: 24 }}>
                <Info size={16} strokeWidth={1.5} />
                <span>{result.warnings.join("；")}</span>
              </div>
            )}

            {/* 商标 */}
            <div className="kw-ip-section">
              <h3 className="kw-event-title">一、商标</h3>
              <p className="kw-ip-summary">{result.trademark_summary_text}</p>
              {result.trademarks.length > 0 && (
                <div className="kw-ip-table-wrap">
                  <table className="kw-ip-table">
                    <thead>
                      <tr>
                        <th>序号</th>
                        <th>商标名称</th>
                        <th>商标状态</th>
                        <th>申请/注册号</th>
                        <th>申请日期</th>
                        <th>国际分类</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.trademarks.map((t) => (
                        <tr key={t.seq}>
                          <td>{t.seq}</td>
                          <td>{t.name}</td>
                          <td>{t.status}</td>
                          <td>{t.app_no}</td>
                          <td>{t.app_date}</td>
                          <td>{t.intl_class}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* 专利 */}
            <div className="kw-ip-section">
              <h3 className="kw-event-title">二、专利</h3>
              <p className="kw-ip-summary">{result.patent_summary_text}</p>
              {result.patents.length > 0 && (
                <div className="kw-ip-table-wrap">
                  <table className="kw-ip-table">
                    <thead>
                      <tr>
                        <th>序号</th>
                        <th>名称</th>
                        <th>专利类型</th>
                        <th>法律状态</th>
                        <th>申请号</th>
                        <th>申请日期</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.patents.map((p) => (
                        <tr key={p.seq}>
                          <td>{p.seq}</td>
                          <td style={{ textAlign: "left" }}>{p.name}</td>
                          <td>{p.patent_type}</td>
                          <td>{p.legal_status}</td>
                          <td>{p.app_no}</td>
                          <td>{p.app_date}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

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

      {/* 页脚 */}
      <div className="kw-explore-wrap">
        <div className="kw-container">
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
            <img
              src="/wechat-qr.jpg"
              alt="公众号二维码"
              width={200}
              height={200}
              style={{ display: "block", margin: "0 auto", borderRadius: "12px" }}
            />
            <p className="kw-modal-text">欢迎大佬关注，共同进步</p>
          </div>
        </div>
      )}
    </div>
  );
}
