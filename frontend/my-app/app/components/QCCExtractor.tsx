"use client";

import { useState, useEffect } from "react";

interface HistoryChange {
  date: string;
  category: string;
  project: string;
  transfer_from: string;
  transfer_to: string;
  transfer_ratio: string;
  capital_before: string;
  capital_after: string;
}

interface HistoryResult {
  text: string;
  markdown: string;
  changes_count: number;
  changes: HistoryChange[];
  category_stats: Record<string, number>;
}

interface QCCData {
  report_meta: {
    company_name: string;
    report_type: string;
    report_date: string;
    total_pages: number;
  };
  registration: Record<string, string>;
  shareholders: Array<{
    seq: string;
    name: string;
    ratio: string;
    amount: string;
  }>;
  key_persons: Array<{
    seq: string;
    name: string;
    position: string;
  }>;
  change_history_count: number;
}

export default function QCCExtractor() {
  const [file, setFile] = useState<File | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [activeTab, setActiveTab] = useState<"basic" | "history">("basic");
  
  // 基础数据
  const [basicResult, setBasicResult] = useState<QCCData | null>(null);
  
  // 历史沿革数据
  const [historyResult, setHistoryResult] = useState<HistoryResult | null>(null);
  const [showMarkdown, setShowMarkdown] = useState(false);
  const [isGeneratingWord, setIsGeneratingWord] = useState(false);
  
  // Word生成参数
  const [lawFirmName, setLawFirmName] = useState("");
  const [lawyerName, setLawyerName] = useState("");
  const [useTemplate, setUseTemplate] = useState(false);
  const [availableTemplates, setAvailableTemplates] = useState<string[]>([]);
  
  const [error, setError] = useState<string>("");

  const API_BASE = "/api/v1";

  const handleExtractBasic = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setIsExtracting(true);
    setError("");
    setActiveTab("basic");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${API_BASE}/qcc/extract-basic`, {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        setBasicResult(data.data);
      } else {
        const err = await response.json();
        setError(err.detail || "提取失败");
      }
    } catch (e) {
      setError("网络错误，请检查后端服务");
    } finally {
      setIsExtracting(false);
    }
  };

  const handleExtractHistory = async () => {
    if (!file) return;

    setIsExtracting(true);
    setError("");
    setActiveTab("history");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${API_BASE}/qcc/history-evolution`, {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        setHistoryResult(data.history_evolution);
        // 同时更新基础信息
        setBasicResult({
          report_meta: data.basic_info?.registration || {},
          registration: data.basic_info?.registration || {},
          shareholders: data.basic_info?.current_shareholders || [],
          key_persons: [],
          change_history_count: data.history_evolution?.changes_count || 0,
        });
      } else {
        const err = await response.json();
        setError(err.detail || "提取失败");
      }
    } catch (e) {
      setError("网络错误，请检查后端服务");
    } finally {
      setIsExtracting(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    alert("已复制到剪贴板");
  };

  const handleGenerateWord = async () => {
    if (!file) return;

    setIsGeneratingWord(true);
    setError("");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("law_firm_name", lawFirmName);
    formData.append("lawyer_name", lawyerName);
    formData.append("use_template", useTemplate ? "true" : "false");

    try {
      const response = await fetch(`${API_BASE}/qcc/history-evolution/docx`, {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        // 获取文件名
        const contentDisposition = response.headers.get("content-disposition");
        let filename = "历史沿革.docx";
        if (contentDisposition) {
          const match = contentDisposition.match(/filename="(.+)"/);
          if (match) {
            filename = match[1];
          }
        }

        // 下载文件
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        const err = await response.json();
        setError(err.detail || "生成Word文档失败");
      }
    } catch (e) {
      setError("网络错误，请检查后端服务");
    } finally {
      setIsGeneratingWord(false);
    }
  };

  // 加载可用模板列表
  const loadTemplates = async () => {
    try {
      const response = await fetch(`${API_BASE}/qcc/history-evolution/templates`);
      if (response.ok) {
        const data = await response.json();
        setAvailableTemplates(data.templates || []);
      }
    } catch (e) {
      console.error("加载模板列表失败", e);
    }
  };

  // 组件挂载时加载模板列表
  useEffect(() => {
    loadTemplates();
  }, []);

  return (
    <div className="space-y-6">
      <div className="card">
        <h2 className="text-xl font-bold text-gray-900 mb-4">
          企查查报告提取
        </h2>
        <p className="text-gray-600 mb-6">
          上传企查查企业信用报告 PDF，自动提取工商信息、生成历史沿革文本，
          用于法律意见书的历史沿革章节。
        </p>

        <form onSubmit={handleExtractBasic} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              选择 PDF 文件
            </label>
            <input
              type="file"
              accept=".pdf"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
            />
          </div>

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={isExtracting || !file}
              className="btn btn-secondary disabled:opacity-50"
            >
              {isExtracting && activeTab === "basic" ? "提取中..." : "提取基础信息"}
            </button>
            <button
              type="button"
              onClick={handleExtractHistory}
              disabled={isExtracting || !file}
              className="btn btn-primary disabled:opacity-50"
            >
              {isExtracting && activeTab === "history" ? "生成中..." : "生成历史沿革"}
            </button>
          </div>
        </form>

        {error && (
          <div className="mt-4 p-4 bg-red-50 text-red-700 rounded-lg">
            {error}
          </div>
        )}
      </div>

      {/* 历史沿革结果 */}
      {historyResult && (
        <div className="space-y-6">
          {/* 统计信息 */}
          <div className="card bg-blue-50">
            <h3 className="font-semibold text-lg mb-3">历史沿革统计</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center p-3 bg-white rounded-lg">
                <div className="text-2xl font-bold text-blue-600">
                  {historyResult.changes_count}
                </div>
                <div className="text-sm text-gray-500">相关变更</div>
              </div>
              {Object.entries(historyResult.category_stats).map(([cat, count]) => (
                <div key={cat} className="text-center p-3 bg-white rounded-lg">
                  <div className="text-xl font-bold text-gray-700">{count}</div>
                  <div className="text-sm text-gray-500">{cat}</div>
                </div>
              ))}
            </div>
          </div>

          {/* 历史沿革文本 */}
          <div className="card">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-semibold text-lg">历史沿革文本</h3>
              <div className="flex gap-2">
                <button
                  onClick={() => setShowMarkdown(!showMarkdown)}
                  className="text-sm text-blue-600 hover:text-blue-700"
                >
                  {showMarkdown ? "显示简洁版" : "显示详细版"}
                </button>
                <button
                  onClick={() => copyToClipboard(showMarkdown ? historyResult.markdown : historyResult.text)}
                  className="text-sm text-gray-600 hover:text-gray-700"
                >
                  复制文本
                </button>
              </div>
            </div>
            <div className="bg-gray-50 p-4 rounded-lg whitespace-pre-wrap text-sm leading-relaxed max-h-96 overflow-y-auto">
              {showMarkdown ? historyResult.markdown : historyResult.text}
            </div>
          </div>

          {/* 变更明细 */}
          <div className="card">
            <h3 className="font-semibold text-lg mb-4">
              历史沿革明细（{historyResult.changes.length}条）
            </h3>
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {historyResult.changes.map((change, idx) => (
                <div key={idx} className="border-l-4 border-blue-500 pl-4 py-2 bg-gray-50 rounded-r-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-gray-900">{change.date}</span>
                    <span className="badge badge-blue">{change.category}</span>
                  </div>
                  <p className="text-sm text-gray-600 mb-1">{change.project}</p>
                  {(change.transfer_from || change.transfer_to) && (
                    <p className="text-sm">
                      <span className="text-gray-500">股权转让：</span>
                      {change.transfer_from && <span>{change.transfer_from} → </span>}
                      {change.transfer_to}
                      {change.transfer_ratio && <span className="text-blue-600 ml-1">({change.transfer_ratio})</span>}
                    </p>
                  )}
                  {(change.capital_before || change.capital_after) && (
                    <p className="text-sm">
                      <span className="text-gray-500">注册资本：</span>
                      <span>{change.capital_before} → {change.capital_after}</span>
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* 使用数据按钮 */}
          <div className="card bg-green-50">
            <h3 className="font-semibold text-lg mb-3">使用此数据生成文档</h3>
            
            {/* 可选参数 */}
            <div className="space-y-3 mb-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm text-gray-600 mb-1">律所名称（可选）</label>
                  <input
                    type="text"
                    value={lawFirmName}
                    onChange={(e) => setLawFirmName(e.target.value)}
                    placeholder="如：北京市中伦律师事务所"
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">律师姓名（可选）</label>
                  <input
                    type="text"
                    value={lawyerName}
                    onChange={(e) => setLawyerName(e.target.value)}
                    placeholder="如：张律师"
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
              
              {/* 模板选项 */}
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="useTemplate"
                  checked={useTemplate}
                  onChange={(e) => setUseTemplate(e.target.checked)}
                  className="w-4 h-4 text-blue-600"
                />
                <label htmlFor="useTemplate" className="text-sm text-gray-700">
                  使用自定义模板（需先上传模板到服务器 templates/word/ 目录）
                </label>
              </div>
              
              {useTemplate && availableTemplates.length > 0 && (
                <div className="text-sm text-gray-600 bg-white p-2 rounded">
                  可用模板: {availableTemplates.join(', ')}
                </div>
              )}
            </div>
            
            <div className="flex gap-3">
              <button
                onClick={handleGenerateWord}
                disabled={isGeneratingWord}
                className="btn btn-primary disabled:opacity-50"
              >
                {isGeneratingWord ? "生成中..." : "下载历史沿革Word文档"}
              </button>
            </div>
            
            <p className="text-xs text-gray-500 mt-3">
              提示：模板中使用占位符如 {'{{company_name}}'}、{'{{history_content}}'}、{'{{law_firm_name}}'} 等
            </p>
          </div>
        </div>
      )}

      {/* 基础信息结果 */}
      {basicResult && !historyResult && (
        <div className="space-y-6">
          {/* 报告元信息 */}
          <div className="card bg-blue-50">
            <h3 className="font-semibold text-lg mb-3">报告信息</h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-500">企业名称：</span>
                <span className="font-medium">{basicResult.report_meta?.company_name}</span>
              </div>
              <div>
                <span className="text-gray-500">报告类型：</span>
                <span>{basicResult.report_meta?.report_type}</span>
              </div>
              <div>
                <span className="text-gray-500">生成时间：</span>
                <span>{basicResult.report_meta?.report_date}</span>
              </div>
              <div>
                <span className="text-gray-500">总页数：</span>
                <span>{basicResult.report_meta?.total_pages} 页</span>
              </div>
            </div>
          </div>

          {/* 工商信息 */}
          {basicResult.registration && Object.keys(basicResult.registration).length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-lg mb-3">工商登记信息</h3>
              <div className="grid grid-cols-2 gap-3 text-sm">
                {Object.entries(basicResult.registration).map(([key, value]) => (
                  <div key={key} className="border-b border-gray-100 pb-2">
                    <span className="text-gray-500">{key}：</span>
                    <span className="font-medium">{value as string}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 股东信息 */}
          {basicResult.shareholders && basicResult.shareholders.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-lg mb-3">
                股东信息（{basicResult.shareholders.length}位）
              </h3>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left">序号</th>
                      <th className="px-4 py-2 text-left">股东名称</th>
                      <th className="px-4 py-2 text-left">持股比例</th>
                      <th className="px-4 py-2 text-left">认缴出资额</th>
                    </tr>
                  </thead>
                  <tbody>
                    {basicResult.shareholders.map((s) => (
                      <tr key={s.seq} className="border-b border-gray-100">
                        <td className="px-4 py-2">{s.seq}</td>
                        <td className="px-4 py-2 font-medium">{s.name}</td>
                        <td className="px-4 py-2">{s.ratio}</td>
                        <td className="px-4 py-2">{s.amount}万元</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 主要人员 */}
          {basicResult.key_persons && basicResult.key_persons.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-lg mb-3">
                主要人员（{basicResult.key_persons.length}位）
              </h3>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left">序号</th>
                      <th className="px-4 py-2 text-left">姓名</th>
                      <th className="px-4 py-2 text-left">职务</th>
                    </tr>
                  </thead>
                  <tbody>
                    {basicResult.key_persons.map((p) => (
                      <tr key={p.seq} className="border-b border-gray-100">
                        <td className="px-4 py-2">{p.seq}</td>
                        <td className="px-4 py-2 font-medium">{p.name}</td>
                        <td className="px-4 py-2">{p.position}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 变更记录统计 */}
          <div className="card">
            <h3 className="font-semibold text-lg mb-3">变更记录</h3>
            <p className="text-gray-600">
              共有 <span className="font-semibold text-blue-600">{basicResult.change_history_count}</span> 条变更记录
            </p>
            <button
              onClick={handleExtractHistory}
              disabled={isExtracting}
              className="mt-4 btn btn-primary"
            >
              生成历史沿革
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
