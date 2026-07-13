#!/bin/bash

# 法律文档生成器启动脚本

echo "================================"
echo "  法律文档生成器 - 启动服务"
echo "================================"

# 检查是否在正确的目录
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "错误：请在 legal-doc-generator 目录下运行此脚本"
    exit 1
fi

# 启动后端服务
echo ""
echo "[1/2] 启动后端服务..."
cd backend

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "警告：未找到 .env 文件，正在从模板创建..."
    cp .env.example .env
    echo "请编辑 backend/.env 文件，填入你的 OpenAI API Key"
fi

echo "后端服务将在 http://localhost:8000 启动"
echo "API 文档：http://localhost:8000/docs"

# 在新终端窗口启动后端（macOS）
if command -v osascript &> /dev/null; then
    osascript -e "tell application \"Terminal\" to do script \"cd $(pwd) && source venv/bin/activate && python run.py\""
else
    # Linux/其他系统：后台运行
    python run.py &
    echo "后端服务已在后台启动，PID: $!"
fi

cd ..

# 等待后端启动
sleep 3

# 启动前端服务
echo ""
echo "[2/2] 启动前端服务..."
cd frontend/my-app

# 检查 node_modules
if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install
fi

echo "前端服务将在 http://localhost:3000 启动"

# 在新终端窗口启动前端（macOS）
if command -v osascript &> /dev/null; then
    osascript -e "tell application \"Terminal\" to do script \"cd $(pwd) && npm run dev\""
else
    # Linux/其他系统：后台运行
    npm run dev &
    echo "前端服务已在后台启动，PID: $!"
fi

cd ../..

echo ""
echo "================================"
echo "  所有服务已启动！"
echo "================================"
echo ""
echo "  前端: http://localhost:3000"
echo "  后端: http://localhost:8000"
echo "  API文档: http://localhost:8000/docs"
echo ""
echo "  按 Ctrl+C 停止服务"
echo "================================"

# 保持脚本运行
wait
