"use client";

import { useState, useEffect } from "react";
import { API_BASE } from "../lib/api";

interface KnowledgeItem {
  id: string;
  title: string;
  content: string;
  category: string | null;
  tags: string[];
  created_at: string;
}

interface SOP {
  id: string;
  name: string;
  description: string | null;
  steps: string[];
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

export default function KnowledgeBase() {
  const [activeTab, setActiveTab] = useState<"items" | "sops">("items");
  const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([]);
  const [sops, setSops] = useState<SOP[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  
  // 表单状态
  const [showItemForm, setShowItemForm] = useState(false);
  const [showSOPForm, setShowSOPForm] = useState(false);
  const [itemForm, setItemForm] = useState({
    title: "",
    content: "",
    category: "",
    tags: "",
  });
  const [sopForm, setSopForm] = useState({
    name: "",
    description: "",
    document_type: "legal_opinion",
    steps: [""],
  });



  useEffect(() => {
    fetchKnowledgeItems();
    fetchSOPs();
  }, []);

  const fetchKnowledgeItems = async () => {
    try {
      const response = await fetch(`${API_BASE}/knowledge/items`);
      if (response.ok) {
        const data = await response.json();
        setKnowledgeItems(data);
      }
    } catch (error) {
      console.error("获取知识库失败:", error);
    }
  };

  const fetchSOPs = async () => {
    try {
      const response = await fetch(`${API_BASE}/knowledge/sops`);
      if (response.ok) {
        const data = await response.json();
        setSops(data);
      }
    } catch (error) {
      console.error("获取SOP失败:", error);
    }
  };

  const handleAddItem = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      const response = await fetch(`${API_BASE}/knowledge/items`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...itemForm,
          tags: itemForm.tags.split(",").map((t) => t.trim()).filter(Boolean),
        }),
      });

      if (response.ok) {
        setShowItemForm(false);
        setItemForm({ title: "", content: "", category: "", tags: "" });
        fetchKnowledgeItems();
      }
    } catch (error) {
      console.error("添加知识库条目失败:", error);
    }
  };

  const handleAddSOP = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      const response = await fetch(`${API_BASE}/knowledge/sops`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...sopForm,
          steps: sopForm.steps.filter(Boolean),
        }),
      });

      if (response.ok) {
        setShowSOPForm(false);
        setSopForm({ name: "", description: "", document_type: "legal_opinion", steps: [""] });
        fetchSOPs();
      }
    } catch (error) {
      console.error("添加SOP失败:", error);
    }
  };

  const handleDeleteItem = async (id: string) => {
    if (!confirm("确定删除这条知识库条目？")) return;
    
    try {
      await fetch(`${API_BASE}/knowledge/items/${id}`, { method: "DELETE" });
      fetchKnowledgeItems();
    } catch (error) {
      console.error("删除失败:", error);
    }
  };

  const handleDeleteSOP = async (id: string) => {
    if (!confirm("确定删除这个SOP？")) return;
    
    try {
      await fetch(`${API_BASE}/knowledge/sops/${id}`, { method: "DELETE" });
      fetchSOPs();
    } catch (error) {
      console.error("删除失败:", error);
    }
  };

  const addStep = () => {
    setSopForm({ ...sopForm, steps: [...sopForm.steps, ""] });
  };

  const removeStep = (index: number) => {
    setSopForm({
      ...sopForm,
      steps: sopForm.steps.filter((_, i) => i !== index),
    });
  };

  const updateStep = (index: number, value: string) => {
    const newSteps = [...sopForm.steps];
    newSteps[index] = value;
    setSopForm({ ...sopForm, steps: newSteps });
  };

  const filteredItems = knowledgeItems.filter(
    (item) =>
      item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.content.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getDocumentTypeLabel = (type: string) => {
    return documentTypes.find((t) => t.value === type)?.label || type;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="flex gap-4">
          <button
            onClick={() => setActiveTab("items")}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              activeTab === "items"
                ? "bg-blue-600 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            知识库条目
          </button>
          <button
            onClick={() => setActiveTab("sops")}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              activeTab === "sops"
                ? "bg-blue-600 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            SOP流程
          </button>
        </div>
        <button
          onClick={() =>
            activeTab === "items" ? setShowItemForm(true) : setShowSOPForm(true)
          }
          className="btn btn-primary flex items-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          添加{activeTab === "items" ? "条目" : "SOP"}
        </button>
      </div>

      {/* 搜索 */}
      <div className="relative">
        <input
          type="text"
          placeholder="搜索..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="input pl-10"
        />
        <svg
          className="absolute left-3 top-2.5 w-5 h-5 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
      </div>

      {/* 添加知识库条目表单 */}
      {showItemForm && (
        <div className="card">
          <h3 className="text-lg font-semibold mb-4">添加知识库条目</h3>
          <form onSubmit={handleAddItem} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                标题 *
              </label>
              <input
                type="text"
                required
                value={itemForm.title}
                onChange={(e) => setItemForm({ ...itemForm, title: e.target.value })}
                className="input"
                placeholder="例如：科创板上市法律意见书撰写要点"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  分类
                </label>
                <input
                  type="text"
                  value={itemForm.category}
                  onChange={(e) => setItemForm({ ...itemForm, category: e.target.value })}
                  className="input"
                  placeholder="例如：上市业务"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  标签（逗号分隔）
                </label>
                <input
                  type="text"
                  value={itemForm.tags}
                  onChange={(e) => setItemForm({ ...itemForm, tags: e.target.value })}
                  className="input"
                  placeholder="例如：科创板,法律意见书,IPO"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                内容 *
              </label>
              <textarea
                required
                value={itemForm.content}
                onChange={(e) => setItemForm({ ...itemForm, content: e.target.value })}
                className="input h-40 resize-none"
                placeholder="输入专业知识内容..."
              />
            </div>
            <div className="flex gap-3">
              <button type="submit" className="btn btn-primary">
                保存
              </button>
              <button
                type="button"
                onClick={() => setShowItemForm(false)}
                className="btn btn-secondary"
              >
                取消
              </button>
            </div>
          </form>
        </div>
      )}

      {/* 添加SOP表单 */}
      {showSOPForm && (
        <div className="card">
          <h3 className="text-lg font-semibold mb-4">添加SOP流程</h3>
          <form onSubmit={handleAddSOP} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  SOP名称 *
                </label>
                <input
                  type="text"
                  required
                  value={sopForm.name}
                  onChange={(e) => setSopForm({ ...sopForm, name: e.target.value })}
                  className="input"
                  placeholder="例如：法律意见书撰写流程"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  适用文档类型 *
                </label>
                <select
                  value={sopForm.document_type}
                  onChange={(e) => setSopForm({ ...sopForm, document_type: e.target.value })}
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
                value={sopForm.description}
                onChange={(e) => setSopForm({ ...sopForm, description: e.target.value })}
                className="input"
                placeholder="SOP的简要描述..."
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                流程步骤 *
              </label>
              <div className="space-y-2">
                {sopForm.steps.map((step, index) => (
                  <div key={index} className="flex gap-2">
                    <span className="flex-shrink-0 w-8 h-10 flex items-center justify-center text-gray-500 font-medium">
                      {index + 1}.
                    </span>
                    <input
                      type="text"
                      required
                      value={step}
                      onChange={(e) => updateStep(index, e.target.value)}
                      className="input flex-1"
                      placeholder={`步骤 ${index + 1}`}
                    />
                    {sopForm.steps.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeStep(index)}
                        className="text-red-600 hover:text-red-700 px-2"
                      >
                        删除
                      </button>
                    )}
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={addStep}
                className="mt-2 text-sm text-blue-600 hover:text-blue-700"
              >
                + 添加步骤
              </button>
            </div>
            <div className="flex gap-3">
              <button type="submit" className="btn btn-primary">
                保存
              </button>
              <button
                type="button"
                onClick={() => setShowSOPForm(false)}
                className="btn btn-secondary"
              >
                取消
              </button>
            </div>
          </form>
        </div>
      )}

      {/* 知识库条目列表 */}
      {activeTab === "items" && (
        <div className="grid grid-cols-1 gap-4">
          {filteredItems.map((item) => (
            <div key={item.id} className="card hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900">{item.title}</h3>
                  <div className="flex items-center gap-2 mt-2">
                    {item.category && (
                      <span className="badge badge-gray">{item.category}</span>
                    )}
                    {item.tags.map((tag, idx) => (
                      <span key={idx} className="badge badge-blue">
                        {tag}
                      </span>
                    ))}
                  </div>
                  <p className="mt-3 text-gray-600 text-sm line-clamp-3">{item.content}</p>
                </div>
                <button
                  onClick={() => handleDeleteItem(item.id)}
                  className="text-gray-400 hover:text-red-600 ml-4"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
          {filteredItems.length === 0 && (
            <div className="text-center py-12">
              <p className="text-gray-500">暂无知识库条目</p>
            </div>
          )}
        </div>
      )}

      {/* SOP列表 */}
      {activeTab === "sops" && (
        <div className="grid grid-cols-1 gap-4">
          {sops.map((sop) => (
            <div key={sop.id} className="card hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h3 className="text-lg font-semibold text-gray-900">{sop.name}</h3>
                    <span className="badge badge-green">
                      {getDocumentTypeLabel(sop.document_type)}
                    </span>
                  </div>
                  {sop.description && (
                    <p className="mt-2 text-gray-600 text-sm">{sop.description}</p>
                  )}
                  <div className="mt-4 space-y-2">
                    {sop.steps.map((step, idx) => (
                      <div key={idx} className="flex items-start gap-3">
                        <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-medium">
                          {idx + 1}
                        </span>
                        <span className="text-gray-700">{step}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <button
                  onClick={() => handleDeleteSOP(sop.id)}
                  className="text-gray-400 hover:text-red-600 ml-4"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
          {sops.length === 0 && (
            <div className="text-center py-12">
              <p className="text-gray-500">暂无SOP流程</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
