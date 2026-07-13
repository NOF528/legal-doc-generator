"use client";

import { useState } from "react";
import TemplateManager from "./components/TemplateManager";
import DocumentGenerator from "./components/DocumentGenerator";
import KnowledgeBase from "./components/KnowledgeBase";
import QCCExtractor from "./components/QCCExtractor";

type Tab = "templates" | "generate" | "knowledge" | "qcc";

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>("generate");

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h1 className="text-xl font-bold text-gray-900">法律文档生成器</h1>
            </div>
            <div className="text-sm text-gray-500">
              专业法律文书智能生成
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8">
            <button
              onClick={() => setActiveTab("generate")}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === "generate"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              生成文档
            </button>
            <button
              onClick={() => setActiveTab("templates")}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === "templates"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              模板管理
            </button>
            <button
              onClick={() => setActiveTab("knowledge")}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === "knowledge"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              知识库
            </button>
            <button
              onClick={() => setActiveTab("qcc")}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === "qcc"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              企查查提取
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === "templates" && <TemplateManager />}
        {activeTab === "generate" && <DocumentGenerator />}
        {activeTab === "knowledge" && <KnowledgeBase />}
        {activeTab === "qcc" && <QCCExtractor />}
      </main>
    </div>
  );
}
