#!/bin/bash
# 法律文档生成器 - 一键部署脚本
# 适用于：香港/海外云服务器（2核4G）

set -e  # 遇到错误立即退出

echo "==================================="
echo "法律文档生成器 - 云端部署脚本"
echo "==================================="

# 配置变量
PROJECT_NAME="legal-doc-generator"
DEFAULT_PASSWORD="legal2024"  # 默认密码，建议修改

# 检查是否以root运行
if [ "$EUID" -ne 0 ]; then 
    echo "请使用 sudo 运行此脚本"
    exit 1
fi

# ==================== 步骤1: 安装Docker ====================
echo ""
echo "[1/6] 安装 Docker 和 Docker Compose..."

if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    echo "✓ Docker 安装完成"
else
    echo "✓ Docker 已存在"
fi

if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo "✓ Docker Compose 安装完成"
else
    echo "✓ Docker Compose 已存在"
fi

# ==================== 步骤2: 设置密码 ====================
echo ""
echo "[2/6] 设置访问密码..."

read -p "请输入访问密码（直接回车使用默认: $DEFAULT_PASSWORD）: " USER_PASSWORD
PASSWORD=${USER_PASSWORD:-$DEFAULT_PASSWORD}

# 生成htpasswd文件
apt-get update && apt-get install -y apache2-utils
htpasswd -cb nginx/.htpasswd legaluser "$PASSWORD"
echo "✓ 密码设置完成: legaluser / $PASSWORD"

# ==================== 步骤3: 准备目录 ====================
echo ""
echo "[3/6] 准备项目目录..."

mkdir -p /opt/$PROJECT_NAME
cp -r ../* /opt/$PROJECT_NAME/ 2>/dev/null || true
cd /opt/$PROJECT_NAME/docker
mkdir -p nginx/ssl

# 创建环境变量文件
cat > .env << EOF
# 生产环境配置
ENV=production
DEBUG=false
ACCESS_PASSWORD=$PASSWORD
EOF

echo "✓ 目录准备完成: /opt/$PROJECT_NAME"

# ==================== 步骤4: 构建和启动 ====================
echo ""
echo "[4/6] 构建并启动服务..."

docker-compose down 2>/dev/null || true
docker-compose build --no-cache
docker-compose up -d

echo "✓ 服务启动完成"

# ==================== 步骤5: 健康检查 ====================
echo ""
echo "[5/6] 健康检查..."

sleep 5

# 检查各服务状态
services=("frontend" "backend" "nginx")
for service in "${services[@]}"; do
    if docker-compose ps | grep -q "$service.*Up"; then
        echo "✓ $service 运行正常"
    else
        echo "✗ $service 启动失败，请检查日志: docker-compose logs $service"
    fi
done

# ==================== 步骤6: 输出信息 ====================
echo ""
echo "==================================="
echo "部署完成！"
echo "==================================="
echo ""
echo "访问地址:"
echo "  - HTTP:  http://$(curl -s ifconfig.me || echo '你的服务器IP')"
echo ""
echo "登录信息:"
echo "  - 用户名: legaluser"
echo "  - 密码:   $PASSWORD"
echo ""
echo "管理命令:"
echo "  - 查看状态:  cd /opt/$PROJECT_NAME/docker && docker-compose ps"
echo "  - 查看日志:  cd /opt/$PROJECT_NAME/docker && docker-compose logs -f"
echo "  - 重启服务:  cd /opt/$PROJECT_NAME/docker && docker-compose restart"
echo "  - 停止服务:  cd /opt/$PROJECT_NAME/docker && docker-compose down"
echo "  - 更新代码:  cd /opt/$PROJECT_NAME/docker && ./update.sh"
echo ""
echo "模板上传:"
echo "  - 将Word模板上传到: /opt/$PROJECT_NAME/backend/templates/word/"
echo ""
echo "==================================="

# 保存访问信息
cat > /root/access-info.txt << EOF
法律文档生成器 - 访问信息
========================
地址: http://$(curl -s ifconfig.me || echo '你的服务器IP')
用户名: legaluser
密码: $PASSWORD
========================
EOF

echo "访问信息已保存到: /root/access-info.txt"
