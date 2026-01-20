#!/bin/bash

# 遇到错误立即停止
set -e

echo "=== 1. 更新系统并安装基础工具 ==="
sudo apt update
# 增加安装 docker.io (Docker引擎)
sudo apt install -y git curl wget vim docker.io

echo "=== 2. 启动 Docker 服务 ==="
sudo systemctl start docker
sudo systemctl enable docker

# 将当前用户加入 docker 用户组（避免每次都输 sudo）
sudo usermod -aG docker $USER

echo "=== 3. 安装 Docker Compose ==="
# 下载 Docker Compose 二进制文件
sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

echo "=== 4. 准备项目代码 ==="
# 如果目录已存在，先删除以确保是新的
if [ -d "biance_coin_screener" ]; then
    echo "检测到旧项目目录，正在移除..."
    sudo rm -rf biance_coin_screener
fi

git clone https://github.com/shangboliang/biance_coin_screener.git
cd biance_coin_screener

echo "=== 5. 生成 .env 配置文件 ==="
cat > .env <<EOF
# Telegram配置
TELEGRAM_BOT_TOKEN=7104070263:AAEP30GEUanjPTT7YfiKhOUnv20sarlhwuI
TELEGRAM_CHAT_ID=5381545264

# Web访问密码
WEB_PASSWORD=beck
WEB_SESSION_TIMEOUT=3600

# 代理配置 (你在东京机房，通常不需要代理，设为 false)
BINANCE_USE_PROXY=false
BINANCE_PROXY_HOST=127.0.0.1
BINANCE_PROXY_PORT=7890
EOF

# 设置权限
chmod 600 .env

echo "=== 6. 创建目录结构 ==="
mkdir -p data logs nginx/ssl
# 确保当前用户对目录有读写权限
sudo chown -R $USER:$USER data logs nginx

echo "=== 7. 生成 Nginx 配置文件 ==="
cat > nginx/nginx.conf <<EOF
events {
    worker_connections 1024;
}

http {
    upstream poc_web {
        server poc-web:8501;
    }

    server {
        listen 80;
        server_name localhost;
        client_max_body_size 5m;

        location / {
            proxy_pass http://poc_web;
            proxy_http_version 1.1;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;

            # WebSocket 支持
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection "upgrade";
        }
    }
}
EOF

echo "=== 8. 构建并启动服务 ==="
# 注意：由于用户组权限可能还没生效，这里强制使用 sudo 和 docker-compose 连字符命令
sudo docker-compose --profile with-nginx pull
sudo docker-compose --profile with-nginx build
sudo docker-compose --profile with-nginx up -d

echo "-----------------------------------"
echo "✅ 部署成功！"
echo "请访问: http://$(curl -s ifconfig.me)"
echo "-----------------------------------"

#  # 进入项目目录
#  cd ~/biance_coin_screener
#
#  # 然后再执行命令
#  docker compose logs -f poc-monitor
#
#  或者你也可以直接用 docker logs（不需要在项目目录）：
#
#  # 直接查看容器日志（通过容器名）
#  docker logs -f poc_monitor
#
#  # 查看最近100行
#  docker logs --tail=100 poc_monitor
#
#  # 查看所有容器
#  docker ps
#
#  试试这个：
#
#  cd ~/biance_coin_screener && docker compose logs -f poc-monitor
#
#  或者更简单：
#
#  docker logs -f poc_monitor