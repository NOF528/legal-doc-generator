# 法律文档生成器

智能生成法律意见书、律师工作报告、三会制度等法律文书的专业工具。

## 功能特点

- **模板管理**：上传 Word 模板，自动识别占位符
- **智能生成**：AI 自动生成专业法律文书内容
- **知识库**：积累专业知识和 SOP 流程，提升生成质量
- **多类型支持**：法律意见书、三会制度、律师工作报告、合同等

## 技术栈

- **后端**：FastAPI + Python-docx + ChromaDB + LangChain + OpenAI
- **前端**：Next.js 16 + React 19 + TypeScript + Tailwind CSS

## 快速开始

### 1. 配置环境变量

后端配置（backend/.env）：
```bash
cd backend
cp .env.example .env
# 编辑 .env 文件，填入你的 OpenAI API Key
```

### 2. 启动后端服务

```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
python run.py
```

后端服务将在 http://localhost:8000 运行

### 3. 启动前端服务

```bash
cd frontend/my-app
npm run dev
```

前端服务将在 http://localhost:3000 运行

## 使用指南

### 1. 上传模板

1. 进入"模板管理"页面
2. 点击"上传模板"
3. 选择 Word 文件（.docx）
4. 填写模板名称和文档类型
5. 在模板中使用 `{{占位符}}` 格式标记需要填充的位置

### 2. 生成文档

1. 进入"生成文档"页面
2. 选择要使用的模板
3. 填写表单中的信息
4. 可选择启用知识库增强生成效果
5. 点击"生成文档"
6. 下载生成的 Word 文档

### 3. 管理知识库

1. 进入"知识库"页面
2. 添加专业知识条目（如：上市条件、法律条款等）
3. 添加 SOP 流程（标准化操作流程）
4. 生成文档时会自动匹配相关知识

## 模板示例

创建一个 Word 文档作为模板，使用 `{{占位符}}` 标记变量：

```
关于{{company_name}}的
法律意见书

致：{{company_name}}

{{law_firm_name}}接受贵司委托，就{{company_name}}申请在科创板上市事宜...

{{ai_generated_content}}

特此致书！

{{law_firm_name}}
律师：{{lawyer_name}}
日期：{{date}}
```

特殊占位符：
- `{{ai_generated_content}}` - AI 自动生成的核心内容

## 项目结构

```
legal-doc-generator/
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── api/v1/         # API 路由
│   │   ├── core/           # 配置文件
│   │   ├── models/         # 数据模型
│   │   ├── services/       # 业务逻辑
│   │   └── main.py         # 应用入口
│   ├── uploads/            # 上传文件存储
│   ├── venv/               # 虚拟环境
│   ├── requirements.txt    # 依赖
│   └── run.py              # 启动脚本
│
├── frontend/               # 前端应用
│   └── my-app/
│       ├── app/
│       │   ├── components/ # React 组件
│       │   ├── page.tsx    # 主页面
│       │   └── layout.tsx  # 布局
│       └── package.json
│
└── README.md
```

## API 文档

启动后端服务后，访问 http://localhost:8000/docs 查看 Swagger API 文档。

## 注意事项

1. 确保 OpenAI API Key 有效且余额充足
2. 模板文件必须是 .docx 格式
3. 占位符区分大小写，建议使用英文和下划线命名
4. 知识库内容越丰富，生成效果越好

## 后续优化方向

- [ ] 用户认证和权限管理
- [ ] 文档历史版本管理
- [ ] 在线预览和编辑
- [ ] 批量生成文档
- [ ] 微信小程序集成
- [ ] 协作分享功能
