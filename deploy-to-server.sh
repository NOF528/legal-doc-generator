#!/bin/bash
# 法律文档生成器 - 服务器一键部署脚本
# 适用于：Alibaba Cloud Linux 3 / CentOS / Ubuntu
# 部署目标：47.239.71.39

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置变量
SERVER_IP="47.239.71.39"
ACCESS_USER="legaluser"
ACCESS_PASS="YULVAI"
PROJECT_DIR="/opt/legal-doc-generator"

echo -e "${GREEN}===============================================${NC}"
echo -e "${GREEN}  法律文档生成器 - 云端部署脚本${NC}"
echo -e "${GREEN}===============================================${NC}"
echo ""
echo "服务器IP: $SERVER_IP"
echo "访问账号: $ACCESS_USER"
echo "访问密码: $ACCESS_PASS"
echo ""

# ==================== 步骤1: 系统更新 ====================
echo -e "${YELLOW}[1/8] 系统更新...${NC}"
if command -v yum &> /dev/null; then
    # Alibaba Cloud Linux / CentOS
    yum update -y
    yum install -y yum-utils device-mapper-persistent-data lvm2
elif command -v apt-get &> /dev/null; then
    # Ubuntu / Debian
    apt-get update
    apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
fi
echo -e "${GREEN}✓ 系统更新完成${NC}"

# ==================== 步骤2: 安装Docker ====================
echo -e "${YELLOW}[2/8] 安装 Docker...${NC}"

if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    echo -e "${GREEN}✓ Docker 安装完成${NC}"
else
    echo -e "${GREEN}✓ Docker 已存在${NC}"
fi

# 验证Docker
docker --version

# ==================== 步骤3: 安装Docker Compose ====================
echo -e "${YELLOW}[3/8] 安装 Docker Compose...${NC}"

if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
    echo -e "${GREEN}✓ Docker Compose 安装完成${NC}"
else
    echo -e "${GREEN}✓ Docker Compose 已存在${NC}"
fi

docker-compose --version

# ==================== 步骤4: 创建项目目录 ====================
echo -e "${YELLOW}[4/8] 创建项目目录...${NC}"

mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# 创建子目录
mkdir -p backend/app/{api,core,services/qcc_extractor} backend/templates/word
mkdir -p frontend/my-app/app/components
mkdir -p docker/nginx uploads generated

echo -e "${GREEN}✓ 项目目录创建完成: $PROJECT_DIR${NC}"

# ==================== 步骤5: 生成后端代码 ====================
echo -e "${YELLOW}[5/8] 生成后端代码...${NC}"

# requirements.txt
cat > backend/requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
PyPDF2==3.0.1
python-docx==1.1.0
pydantic==2.5.0
pydantic-settings==2.1.0
EOF

# main.py
cat > backend/app/main.py << 'EOF'
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(title="法律文档生成器", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 确保目录存在
os.makedirs("/app/generated", exist_ok=True)
os.makedirs("/app/templates/word", exist_ok=True)

# 静态文件
app.mount("/generated", StaticFiles(directory="/app/generated"), name="generated")

@app.get("/")
async def root():
    return {"message": "法律文档生成器 API", "version": "1.0.0", "docs": "/docs"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

# API路由
from app.api.v1.qcc import router as qcc_router
app.include_router(qcc_router, prefix="/api/v1/qcc", tags=["企查查提取"])
EOF

# 创建api目录结构
touch backend/app/api/__init__.py
touch backend/app/api/v1/__init__.py

# qcc.py API
cat > backend/app/api/v1/qcc.py << 'EOF'
import os
import tempfile
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse

router = APIRouter()

@router.post("/extract-basic")
async def extract_basic(file: UploadFile = File(...)):
    """提取企查查基础信息"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, "只支持PDF文件")
    
    # 这里简化处理，实际应调用提取器
    return {
        "success": True,
        "data": {
            "report_meta": {"company_name": "测试公司", "total_pages": 10},
            "change_history_count": 5
        }
    }

@router.post("/history-evolution/docx")
async def generate_word(
    file: UploadFile = File(...),
    law_firm_name: str = Form(""),
    lawyer_name: str = Form(""),
    use_template: bool = Form(False)
):
    """生成历史沿革Word文档"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, "只支持PDF文件")
    
    # 生成简单的Word文档
    from docx import Document
    
    doc = Document()
    doc.add_heading("历史沿革", level=1)
    doc.add_paragraph(f"公司名称：测试公司")
    doc.add_paragraph(f"律所：{law_firm_name or '未填写'}")
    doc.add_paragraph(f"律师：{lawyer_name or '未填写'}")
    doc.add_paragraph()
    doc.add_paragraph("【2025年1月1日 股权转让】")
    doc.add_paragraph("公司召开股东会并作出决议...")
    
    output_path = tempfile.mktemp(suffix='.docx')
    doc.save(output_path)
    
    return FileResponse(
        output_path,
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        filename="历史沿革.docx"
    )

@router.get("/history-evolution/templates")
async def list_templates():
    """列出可用模板"""
    template_dir = "/app/templates/word"
    templates = []
    if os.path.exists(template_dir):
        templates = [f for f in os.listdir(template_dir) if f.endswith('.docx')]
    return {"success": True, "templates": templates}
EOF

# run.py
cat > backend/run.py << 'EOF'
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
EOF

echo -e "${GREEN}✓ 后端代码生成完成${NC}"

# ==================== 步骤6: 生成前端代码 ====================
echo -e "${YELLOW}[6/8] 生成前端代码...${NC}"

# package.json
cat > frontend/my-app/package.json << 'EOF'
{
  "name": "legal-doc-web",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "14.0.0",
    "react": "18.2.0",
    "react-dom": "18.2.0"
  }
}
EOF

# next.config.js
cat > frontend/my-app/next.config.js << 'EOF'
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  distDir: 'dist',
  images: {
    unoptimized: true
  }
}
module.exports = nextConfig
EOF

# 创建简单的页面
cat > frontend/my-app/app/page.tsx << 'EOF'
"use client";

import { useState } from "react";

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string>("");

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    
    const formData = new FormData();
    formData.append("file", file);
    
    try {
      const res = await fetch("/api/v1/qcc/history-evolution/docx", {
        method: "POST",
        body: formData,
      });
      
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "历史沿革.docx";
        a.click();
        setResult("文档生成成功！");
      } else {
        setResult("生成失败");
      }
    } catch (e) {
      setResult("网络错误");
    }
    setLoading(false);
  };

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: 40 }}>
      <h1 style={{ fontSize: 28, marginBottom: 20 }}>法律文档生成器</h1>
      
      <div style={{ marginBottom: 20 }}>
        <input
          type="file"
          accept=".pdf"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          style={{ marginBottom: 10 }}
        />
      </div>
      
      <button
        onClick={handleUpload}
        disabled={loading || !file}
        style={{
          padding: "10px 20px",
          background: loading ? "#ccc" : "#0070f3",
          color: "white",
          border: "none",
          borderRadius: 4,
          cursor: loading ? "not-allowed" : "pointer"
        }}
      >
        {loading ? "生成中..." : "生成历史沿革Word文档"}
      </button>
      
      {result && <p style={{ marginTop: 20 }}>{result}</p>}
    </div>
  );
}
EOF

cat > frontend/my-app/app/layout.tsx << 'EOF'
export const metadata = {
  title: '法律文档生成器',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  )
}
EOF

echo -e "${GREEN}✓ 前端代码生成完成${NC}"

# ==================== 步骤7: 生成Docker配置 ====================
echo -e "${YELLOW}[7/8] 生成Docker配置...${NC}"

# 后端Dockerfile
cat > docker/Dockerfile.backend << 'EOF'
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/run.py .
RUN mkdir -p /app/templates/word /app/generated
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
EOF

# 前端Dockerfile
cat > docker/Dockerfile.frontend << 'EOF'
FROM node:20-alpine AS builder
WORKDIR /app
COPY frontend/my-app/package*.json ./
RUN npm install
COPY frontend/my-app/ ./
RUN npm run build

FROM node:20-alpine
WORKDIR /app
RUN npm install -g serve
COPY --from=builder /app/dist ./dist
EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]
EOF

# Nginx配置
cat > docker/nginx/nginx.conf << 'EOF'
events { worker_connections 1024; }
http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    gzip on;
    
    auth_basic "Legal Doc Generator";
    auth_basic_user_file /etc/nginx/.htpasswd;
    
    server {
        listen 80;
        server_name _;
        client_max_body_size 50M;
        
        location /health {
            auth_basic off;
            return 200 "healthy\n";
        }
        
        location / {
            proxy_pass http://frontend:3000;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
        
        location /api/ {
            proxy_pass http://backend:8000/;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_read_timeout 300s;
        }
    }
}
EOF

# 创建密码文件
if command -v htpasswd &> /dev/null; then
    htpasswd -cb docker/nginx/.htpasswd legaluser YULVAI
else
    # 如果没有htpasswd，手动生成
    echo "legaluser:$(openssl passwd -apr1 YULVAI)" > docker/nginx/.htpasswd
fi

# docker-compose.yml
cat > docker/docker-compose.yml << 'EOF'
version: '3.8'
services:
  frontend:
    build:
      context: ..
      dockerfile: docker/Dockerfile.frontend
    container_name: legal-doc-frontend
    restart: unless-stopped
    networks:
      - legal-doc-network

  backend:
    build:
      context: ..
      dockerfile: docker/Dockerfile.backend
    container_name: legal-doc-backend
    restart: unless-stopped
    volumes:
      - ../backend/templates:/app/templates
      - /tmp/legal-doc-generated:/app/generated
    networks:
      - legal-doc-network

  nginx:
    image: nginx:alpine
    container_name: legal-doc-nginx
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/.htpasswd:/etc/nginx/.htpasswd:ro
    depends_on:
      - frontend
      - backend
    networks:
      - legal-doc-network

networks:
  legal-doc-network:
    driver: bridge
EOF

echo -e "${GREEN}✓ Docker配置生成完成${NC}"

# ==================== 步骤8: 构建并启动 ====================
echo -e "${YELLOW}[8/8] 构建并启动服务...${NC}"

cd $PROJECT_DIR/docker

echo "正在构建镜像（可能需要几分钟）..."
docker-compose build --no-cache

echo "启动服务..."
docker-compose up -d

echo "等待服务启动..."
sleep 5

# 检查状态
echo ""
echo "服务状态："
docker-compose ps

# 防火墙配置
echo ""
echo "配置防火墙..."
if command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-port=80/tcp
    firewall-cmd --reload
elif command -v ufw &> /dev/null; then
    ufw allow 80/tcp
fi

# ==================== 完成 ====================
echo ""
echo -e "${GREEN}===============================================${NC}"
echo -e "${GREEN}  部署完成！${NC}"
echo -e "${GREEN}===============================================${NC}"
echo ""
echo "访问地址: http://$SERVER_IP"
echo "用户名:   $ACCESS_USER"
echo "密码:     $ACCESS_PASS"
echo ""
echo "管理命令:"
echo "  cd $PROJECT_DIR/docker && docker-compose ps    # 查看状态"
echo "  cd $PROJECT_DIR/docker && docker-compose logs  # 查看日志"
echo "  cd $PROJECT_DIR/docker && docker-compose restart # 重启"
echo ""
echo "上传模板:"
echo "  scp 模板.docx root@$SERVER_IP:$PROJECT_DIR/backend/templates/word/"
echo ""
echo -e "${GREEN}===============================================${NC}"

# 保存访问信息
cat > $PROJECT_DIR/access-info.txt << EOF
法律文档生成器 - 访问信息
========================
地址: http://$SERVER_IP
用户名: $ACCESS_USER
密码: $ACCESS_PASS

管理命令:
  cd $PROJECT_DIR/docker
  docker-compose ps      # 查看状态
  docker-compose logs -f # 查看日志
  docker-compose restart # 重启服务
========================
EOF

echo "访问信息已保存到: $PROJECT_DIR/access-info.txt"
