"use client";

import { useState, useEffect } from "react";
import { API_BASE } from "../lib/api";

interface Template {
  id: string;
  name: string;
  document_type: string;
  description: string | null;
}

interface Placeholder {
  name: string;
  label: string;
}

export default function DocumentGenerator() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>("");
  const [placeholders, setPlaceholders] = useState<string[]>([]);
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [useKnowledgeBase, setUseKnowledgeBase] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedDoc, setGeneratedDoc] = useState<string | null>(null);



  useEffect(() => {
    fetchTemplates();
  }, []);

  useEffect(() => {
    if (selectedTemplate) {
      fetchPlaceholders(selectedTemplate);
    }
  }, [selectedTemplate]);

  const fetchTemplates = async () => {
    try {
      const response = await fetch(`${API_BASE}/templates`);
      if (response.ok) {
        const data = await response.json();
        setTemplates(data);
        if (data.length > 0) {
          setSelectedTemplate(data[0].id);
        }
      }
    } catch (error) {
      console.error("获取模板失败:", error);
    }
  };

  const fetchPlaceholders = async (templateId: string) => {
    try {
      const response = await fetch(`${API_BASE}/templates/${templateId}/placeholders`);
      if (response.ok) {
        const data = await response.json();
        setPlaceholders(data.placeholders);
        // 初始化表单数据
        const initialData: Record<string, string> = {};
        data.placeholders.forEach((p: string) => {
          initialData[p] = "";
        });
        setFormData(initialData);
      }
    } catch (error) {
      console.error("获取占位符失败:", error);
      setPlaceholders([]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTemplate) {
      alert("请先选择一个模板");
      return;
    }

    setIsGenerating(true);
    setGeneratedDoc(null);

    try {
      const response = await fetch(`${API_BASE}/documents/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          template_id: selectedTemplate,
          form_data: formData,
          use_knowledge_base: useKnowledgeBase,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setGeneratedDoc(data.download_url);
      } else {
        const error = await response.json();
        alert(`生成失败: ${error.detail || "未知错误"}`);
      }
    } catch (error) {
      console.error("生成错误:", error);
      alert("生成出错，请检查后端服务是否运行");
    } finally {
      setIsGenerating(false);
    }
  };

  const getDocumentTypeLabel = (type: string) => {
    const types: Record<string, string> = {
      legal_opinion: "法律意见书",
      board_rules: "三会制度",
      work_report: "律师工作报告",
      contract: "合同",
      custom: "自定义",
    };
    return types[type] || type;
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      {/* 左侧：表单 */}
      <div className="lg:col-span-2 space-y-6">
        <div className="card">
          <h2 className="text-xl font-bold text-gray-900 mb-6">生成文档</h2>

          {templates.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-gray-500">暂无可用模板，请先上传模板</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* 模板选择 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  选择模板 *
                </label>
                <select
                  value={selectedTemplate}
                  onChange={(e) => setSelectedTemplate(e.target.value)}
                  className="input"
                >
                  {templates.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.name} ({getDocumentTypeLabel(template.document_type)})
                    </option>
                  ))}
                </select>
              </div>

              {/* 知识库选项 */}
              <div className="flex items-center gap-3 p-4 bg-blue-50 rounded-lg">
                <input
                  type="checkbox"
                  id="use_kb"
                  checked={useKnowledgeBase}
                  onChange={(e) => setUseKnowledgeBase(e.target.checked)}
                  className="w-4 h-4 text-blue-600 rounded"
                />
                <label htmlFor="use_kb" className="text-sm text-blue-900">
                  使用知识库增强生成效果
                </label>
              </div>

              {/* 动态表单字段 */}
              {placeholders.length > 0 && (
                <div className="border-t pt-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">
                    填写信息
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {placeholders.map((placeholder) => (
                      <div key={placeholder}>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          {placeholder}
                        </label>
                        <input
                          type="text"
                          value={formData[placeholder] || ""}
                          onChange={(e) =>
                            setFormData({ ...formData, [placeholder]: e.target.value })
                          }
                          className="input"
                          placeholder={`请输入${placeholder}`}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 如果没有占位符，显示提示 */}
              {placeholders.length === 0 && selectedTemplate && (
                <div className="border-t pt-6">
                  <p className="text-sm text-gray-500 mb-4">
                    该模板没有检测到占位符，AI将直接生成完整内容。
                  </p>
                </div>
              )}

              {/* 提交按钮 */}
              <div className="pt-4">
                <button
                  type="submit"
                  disabled={isGenerating}
                  className="btn btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  {isGenerating ? (
                    <>
                      <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                          fill="none"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        />
                      </svg>
                      生成中...
                    </>
                  ) : (
                    <>
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                      生成文档
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>

      {/* 右侧：结果 */}
      <div className="space-y-6">
        {generatedDoc && (
          <div className="card bg-green-50 border-green-200">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center">
                <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-green-900">生成成功！</h3>
                <p className="text-sm text-green-700">文档已准备好下载</p>
              </div>
            </div>
            <a
              href={`${generatedDoc}`}
              download
              className="btn btn-primary w-full text-center block"
            >
              下载文档
            </a>
          </div>
        )}

        <div className="card">
          <h3 className="font-semibold text-gray-900 mb-4">使用说明</h3>
          <ol className="space-y-3 text-sm text-gray-600 list-decimal list-inside">
            <li>选择或上传一个Word模板</li>
            <li>在模板中使用 {'{{'}占位符{'}}'} 格式标记需要填充的位置</li>
            <li>填写表单中的各项信息</li>
            <li>启用知识库可以获得更专业的内容</li>
            <li>点击生成按钮，AI将自动填充模板</li>
          </ol>
          
          <div className="mt-6 p-4 bg-gray-50 rounded-lg">
            <h4 className="font-medium text-gray-900 mb-2">模板示例</h4>
            <pre className="text-xs text-gray-600 overflow-x-auto">
{`关于{{company_name}}的
法律意见书

致：{{company_name}}

{{law_firm_name}}接受贵司委托...

{{ai_generated_content}}

特此致书！

{{law_firm_name}}
律师：{{lawyer_name}}
日期：{{date}}`}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
