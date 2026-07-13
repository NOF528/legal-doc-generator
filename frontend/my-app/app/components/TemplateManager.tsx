"use client";

import { useState, useEffect } from "react";
import { API_BASE } from "../lib/api";

interface Template {
  id: string;
  name: string;
  description: string | null;
  document_type: string;
  created_at: string;
}

const documentTypes = [
  { value: "legal_opinion", label: "法律意见书" },
  { value: "board_rules", label: "三会制度" },
  { value: "work_report", label: "律师工作报告" },
  { value: "contract", label: "合同" },
  { value: "custom", label: "自定义" },
];

export default function TemplateManager() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    document_type: "legal_opinion",
  });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);



  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    try {
      const response = await fetch(`${API_BASE}/templates`);
      if (response.ok) {
        const data = await response.json();
        setTemplates(data);
      }
    } catch (error) {
      console.error("获取模板失败:", error);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    setIsUploading(true);
    const form = new FormData();
    form.append("name", formData.name);
    form.append("description", formData.description);
    form.append("document_type", formData.document_type);
    form.append("file", selectedFile);

    try {
      const response = await fetch(`${API_BASE}/templates`, {
        method: "POST",
        body: form,
      });

      if (response.ok) {
        setShowUploadForm(false);
        setFormData({ name: "", description: "", document_type: "legal_opinion" });
        setSelectedFile(null);
        fetchTemplates();
      } else {
        alert("上传失败");
      }
    } catch (error) {
      console.error("上传错误:", error);
      alert("上传出错");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("确定要删除这个模板吗？")) return;

    try {
      const response = await fetch(`${API_BASE}/templates/${id}`, {
        method: "DELETE",
      });

      if (response.ok) {
        fetchTemplates();
      }
    } catch (error) {
      console.error("删除失败:", error);
    }
  };

  const getDocumentTypeLabel = (type: string) => {
    return documentTypes.find((t) => t.value === type)?.label || type;
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">模板管理</h2>
        <button
          onClick={() => setShowUploadForm(!showUploadForm)}
          className="btn btn-primary flex items-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          上传模板
        </button>
      </div>

      {showUploadForm && (
        <div className="card">
          <h3 className="text-lg font-semibold mb-4">上传新模板</h3>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  模板名称 *
                </label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="input"
                  placeholder="例如：科创板上市法律意见书模板"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  文档类型 *
                </label>
                <select
                  value={formData.document_type}
                  onChange={(e) => setFormData({ ...formData, document_type: e.target.value })}
                  className="input"
                >
                  {documentTypes.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                描述
              </label>
              <input
                type="text"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="input"
                placeholder="模板描述..."
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                模板文件 (.docx) *
              </label>
              <input
                type="file"
                accept=".docx"
                required
                onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
              />
            </div>
            <div className="flex gap-3 pt-2">
              <button
                type="submit"
                disabled={isUploading}
                className="btn btn-primary disabled:opacity-50"
              >
                {isUploading ? "上传中..." : "上传"}
              </button>
              <button
                type="button"
                onClick={() => setShowUploadForm(false)}
                className="btn btn-secondary"
              >
                取消
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {templates.map((template) => (
          <div key={template.id} className="card hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <h3 className="text-lg font-semibold text-gray-900 truncate">
                  {template.name}
                </h3>
                <span className="badge badge-blue mt-2">
                  {getDocumentTypeLabel(template.document_type)}
                </span>
              </div>
              <button
                onClick={() => handleDelete(template.id)}
                className="text-gray-400 hover:text-red-600 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
            {template.description && (
              <p className="mt-2 text-sm text-gray-600 line-clamp-2">
                {template.description}
              </p>
            )}
            <p className="mt-3 text-xs text-gray-400">
              创建于: {new Date(template.created_at).toLocaleDateString()}
            </p>
          </div>
        ))}
      </div>

      {templates.length === 0 && (
        <div className="text-center py-12">
          <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-gray-900">暂无模板</h3>
          <p className="mt-1 text-gray-500">上传一个Word模板开始生成文档</p>
        </div>
      )}
    </div>
  );
}
