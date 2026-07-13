# 系统架构设计

## 设计原则

1. **模块化**：每个服务独立，可单独升级、替换
2. **无状态**：服务不保存状态，方便水平扩展
3. **配置化**：通过环境变量配置，不修改代码
4. **预留扩展**：为工商内档等新功能预留接口

## 模块划分

```
legal-doc-generator/
├── docker/                 # 部署配置
│   ├── docker-compose.yml  # 服务编排
│   ├── Dockerfile.frontend # 前端镜像
│   ├── Dockerfile.backend  # 后端镜像
│   └── nginx/              # 网关配置
│
├── backend/                # 后端服务
│   ├── app/
│   │   ├── api/            # API路由
│   │   ├── services/
│   │   │   ├── qcc_extractor/      # 企查查提取器
│   │   │   ├── archives_extractor/ # 工商内档提取器（预留）
│   │   │   └── document_service/   # 文档生成服务
│   │   └── main.py
│   └── templates/word/     # Word模板目录
│
└── frontend/               # 前端服务
    └── my-app/
        └── app/
            └── components/
                ├── QCCExtractor.tsx      # 企查查提取组件
                ├── ArchivesExtractor.tsx # 内档提取（预留）
                └── DocumentGenerator.tsx # 文档生成组件
```

## 扩展指南

### 添加新的提取器（如工商内档）

**步骤1：创建提取器模块**
```
backend/app/services/
└── archives_extractor/
    ├── __init__.py
    ├── extractor.py       # 核心提取逻辑
    ├── parser.py          # 文件解析
    └── templates.py       # 输出模板
```

**步骤2：添加API路由**
```python
# backend/app/api/v1/archives.py
@router.post("/archives/extract")
async def extract_archives(file: UploadFile = File(...)):
    # 调用提取器
    result = await archives_extractor.extract(file)
    return result
```

**步骤3：前端添加组件**
```tsx
// frontend/my-app/app/components/ArchivesExtractor.tsx
export default function ArchivesExtractor() {
  // 复用QCCExtractor的UI结构
  // 修改API调用
}
```

**步骤4：升级部署**
```bash
./update.sh backend
```

### 添加新的文档类型

**步骤1：创建模板**
```
backend/templates/word/
├── 历史沿革模板.docx
├── 尽职调查报告模板.docx    # 新增
└── 法律意见书模板.docx      # 新增
```

**步骤2：添加生成逻辑**
```python
# backend/app/services/document_service.py
def generate_due_diligence_report(data: dict) -> str:
    # 使用尽职调查模板生成
    pass
```

**步骤3：前端添加选项**
```tsx
<select>
  <option>历史沿革</option>
  <option>尽职调查报告</option>  {/* 新增 */}
</select>
```

## 数据流

```
用户上传PDF
    ↓
Nginx (密码验证)
    ↓
Backend API
    ↓
Extractor (提取数据)
    ↓
Template Engine (渲染)
    ↓
Word Generator (生成文件)
    ↓
用户下载
```

## 部署架构

```
┌─────────────────────────────────────────┐
│              用户层                      │
│    微信 / 浏览器 / 手机 / 电脑            │
└──────────────┬──────────────────────────┘
               │
               ▼ HTTP
┌─────────────────────────────────────────┐
│            Nginx 网关                   │
│  - 密码保护 (Basic Auth)                │
│  - 静态资源缓存                          │
│  - 负载均衡（后续扩展）                   │
└──────────────┬──────────────────────────┘
               │
      ┌────────┴────────┐
      │                 │
      ▼                 ▼
┌──────────┐     ┌──────────┐
│ Frontend │     │ Backend  │
│ :3000    │     │ :8000    │
│ (Next.js)│     │ (FastAPI)│
└──────────┘     └────┬─────┘
                      │
           ┌──────────┼──────────┐
           │          │          │
           ▼          ▼          ▼
      ┌────────┐ ┌────────┐ ┌────────┐
      │QCC提取 │ │内档提取 │ │模板引擎 │
      │(已实现)│ │(预留)  │ │(已实现)│
      └────────┘ └────────┘ └────────┘
```

## 升级策略

### 热升级（零停机）

```bash
# 1. 构建新镜像
docker-compose build backend

# 2. 启动新容器
docker-compose up -d backend

# 3. 旧容器自动停止
```

### 蓝绿部署（高可用）

```bash
# 1. 启动绿色环境
docker-compose -f docker-compose.yml -f docker-compose.green.yml up -d

# 2. 切换Nginx到绿色环境
# 修改nginx配置

# 3. 停止蓝色环境
```

## 监控与健康检查

### 服务健康检查

```bash
# 检查所有服务
curl http://服务器IP/health

# 检查后端
curl http://服务器IP/api/health
```

### 日志收集

```bash
# 查看实时日志
docker-compose logs -f

# 导出日志到文件
docker-compose logs > /tmp/app.log 2>&1
```

## 安全考虑

1. **密码保护**：Nginx Basic Auth
2. **文件安全**：上传后立即处理，不持久存储
3. **网络安全**：只开放80/443端口
4. **容器隔离**：每个服务独立容器
5. **资源限制**：CPU和内存上限

## 成本优化建议

### 当前配置（月费用 ~105元）
- 服务器：2核4G 香港节点
- 支持：5-10人同时使用
- 存储：本地50GB SSD

### 升级路径

**阶段1：当前**
- 单机部署
- 本地存储
- 费用：105元/月

**阶段2：用户增多**
- 添加负载均衡
- 分离数据库（如需要用户系统）
- 费用：200元/月

**阶段3：企业级**
- Kubernetes集群
- 对象存储
- CDN加速
- 费用：500元+/月
