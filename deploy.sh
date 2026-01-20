#!/bin/bash
# 快速部署脚本 - 无需Nginx
# @author beck

set -e

echo "=========================================="
echo "  币安POC监控工具 - 快速部署脚本"
echo "=========================================="

# 检查Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker未安装，请先安装Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose未安装，请先安装"
    exit 1
fi

echo "✅ Docker环境检查通过"

# 创建必要目录
echo "📁 创建数据目录..."
mkdir -p data logs

# 配置环境变量
if [ ! -f .env ]; then
    echo "⚙️  配置环境变量..."
    read -p "请输入Telegram Bot Token (可选，直接回车跳过): " telegram_token
    read -p "请输入Telegram Chat ID (可选，直接回车跳过): " telegram_id
    read -p "请输入Web访问密码 (默认: beck): " web_password
    web_password=${web_password:-beck}

    cat > .env <<EOF
# Telegram配置（可选）
TELEGRAM_BOT_TOKEN=${telegram_token}
TELEGRAM_CHAT_ID=${telegram_id}

# Web访问控制
WEB_PASSWORD=${web_password}
WEB_SESSION_TIMEOUT=3600

# 代理配置（国内用户取消注释）
# BINANCE_PROXY_HOST=127.0.0.1
# BINANCE_PROXY_PORT=7897
# TELEGRAM_PROXY_HOST=127.0.0.1
# TELEGRAM_PROXY_PORT=7897
EOF

    chmod 600 .env
    echo "✅ 环境变量配置完成"
else
    echo "ℹ️  .env文件已存在，跳过配置"
fi

# 构建镜像
echo "🔨 构建Docker镜像..."
docker-compose build

# 启动服务
echo "🚀 启动服务..."
docker-compose up -d

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 5

# 检查服务状态
echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo ""
docker-compose ps
echo ""
echo "📊 Web界面访问地址:"
echo "   http://$(hostname -I | awk '{print $1}'):8501"
echo "   或 http://localhost:8501"
echo ""
echo "🔑 默认密码: ${web_password:-beck}"
echo ""
echo "📝 常用命令:"
echo "   查看日志: docker-compose logs -f"
echo "   停止服务: docker-compose stop"
echo "   重启服务: docker-compose restart"
echo "   进入容器: docker exec -it poc_monitor bash"
echo ""
echo "=========================================="
