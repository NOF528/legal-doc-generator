"use client";

import { useEffect, useRef, useState } from "react";
import { Plus, ArrowUp, X, FileText } from "lucide-react";

/* ============================================================
   共享上传卡片（历史沿革 / 知识产权 / 未来 SOP 模块共用）

   - 拖拽 + 点击选择 PDF
   - window 级 dragover/drop 阻止默认行为（防拖偏时浏览器直接打开 PDF）
   - 重复选择同一文件可再次触发 onChange
   ============================================================ */

interface UploadCardProps {
  file: File | null;
  loading: boolean;
  placeholder: string;
  onFileSelect: (f: File) => void;
  onFileRemove: () => void;
  onGenerate: () => void;
}

export default function UploadCard({
  file,
  loading,
  placeholder,
  onFileSelect,
  onFileRemove,
  onGenerate,
}: UploadCardProps) {
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  /* 拖到卡片外时阻止浏览器默认行为（否则浏览器会直接打开/下载 PDF，
     用户会误以为"上传没反应"） */
  useEffect(() => {
    const prevent = (e: DragEvent) => e.preventDefault();
    window.addEventListener("dragover", prevent);
    window.addEventListener("drop", prevent);
    return () => {
      window.removeEventListener("dragover", prevent);
      window.removeEventListener("drop", prevent);
    };
  }, []);

  return (
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
        const f = e.dataTransfer.files?.[0];
        if (f) onFileSelect(f);
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
                onFileRemove();
                // 清空 input 值，确保再次选择同一文件也能触发 onChange
                if (fileInputRef.current) fileInputRef.current.value = "";
              }}
              aria-label="移除文件"
            >
              <X size={14} strokeWidth={1.5} />
            </button>
          </span>
        ) : (
          <span className="kw-card-placeholder">{placeholder}</span>
        )}
      </div>
      <div className="kw-card-toolbar">
        <button className="kw-icon-btn" onClick={() => fileInputRef.current?.click()} aria-label="选择文件">
          <Plus size={20} strokeWidth={1.5} />
        </button>
        <button
          className={`kw-send-btn ${file && !loading ? "kw-active" : ""}`}
          onClick={onGenerate}
          disabled={!file || loading}
          aria-label="开始生成"
        >
          <ArrowUp size={18} strokeWidth={2} />
        </button>
      </div>
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,application/pdf"
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFileSelect(f);
          // 清空值，确保重复选择同一文件也能触发 onChange
          e.target.value = "";
        }}
      />
    </div>
  );
}
