#!/bin/bash
# 更新脚本 - 支持模块化升级
# 用法: ./update.sh [frontend|backend|all]

set -e

COMPONENT=${1:-all}
PROJECT_NAME="legal-doc-generator"
DOCKER_DIR="/opt/$PROJECT_NAME/docker"

echo "==================================="
echo "法律文档生成器 - 更新脚本"
echo "组件: $COMPONENT"
echo "==================================="

cd $DOCKER_DIR

# 备份当前运行状态
echo "[1/4] 备份当前状态..."
docker-compose ps > /tmp/docker-ps-backup.txt

# 拉取最新代码（假设使用git）
echo "[2/4] 拉取最新代码..."
cd /opt/$PROJECT_NAME
if [ -d ".git" ]; then
    git pull origin main 2>/dev/null || echo "未配置git或拉取失败，使用本地代码"
else
    echo "使用本地代码更新"
fi

# 根据组件进行更新
echo "[3/4] 构建新镜像..."
cd $DOCKER_DIR

case $COMPONENT in
    frontend)
        echo "仅更新前端..."
        docker-compose build --no-cache frontend
        docker-compose up -d frontend
        ;;
    backend)
        echo "仅更新后端..."
        docker-compose build --no-cache backend
        docker-compose up -d backend
        ;;
    all|*)
        echo "更新所有服务..."
        docker-compose pull 2>/dev/null || true
        docker-compose build --no-cache
        docker-compose up -d
        ;;
esac

# 清理旧镜像
echo "[4/4] 清理旧镜像..."
docker image prune -f

# 健康检查
echo ""
echo "健康检查..."
sleep 3

docker-compose ps

echo ""
echo "==================================="
echo "更新完成！"
echo "==================================="
echo ""
echo "查看日志: docker-compose logs -f"
