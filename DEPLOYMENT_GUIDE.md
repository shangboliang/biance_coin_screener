# 服务器部署完整指南

> **@author beck**
>
> 本指南提供多种部署方案，推荐使用Docker方式部署

---

## 📋 目录

1. [部署前准备](#部署前准备)
2. [方案一：Docker部署（推荐）](#方案一docker部署推荐)
3. [方案二：Systemd服务部署](#方案二systemd服务部署)
4. [方案三：直接运行](#方案三直接运行)
5. [生产环境配置](#生产环境配置)
6. [监控和维护](#监控和维护)
7. [故障排除](#故障排除)

---

## 部署前准备

### 1. 服务器要求

**最低配置：**
- CPU: 1核
- 内存: 512MB
- 磁盘: 5GB
- 系统: Ubuntu 20.04+ / CentOS 7+ / Debian 10+

**推荐配置：**
- CPU: 2核
- 内存: 1GB
- 磁盘: 10GB

### 2. 安装必要软件

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装基础工具
sudo apt install -y git curl wget vim

# 安装Docker（方案一）
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 安装Python（方案二/三）
sudo apt install -y python3.9 python3.9-venv python3-pip
```

### 3. 克隆项目

```bash
# 创建项目目录
cd /opt
sudo git clone <your-repo-url> poc-monitor
sudo chown -R $USER:$USER poc-monitor
cd poc-monitor
```

---

## 方案一：Docker部署（推荐）⭐

### 优点
- ✅ 环境隔离，不污染系统
- ✅ 易于迁移和备份
- ✅ 自动重启和健康检查
- ✅ 资源限制和日志管理
- ✅ 一键部署和更新

### 步骤

#### 1. 配置环境变量

```bash
# 创建.env文件
cat > .env <<EOF
# Telegram配置
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Web访问密码
WEB_PASSWORD=your_secure_password

# 会话超时（秒）
WEB_SESSION_TIMEOUT=3600

# 如果在国内需要代理，取消注释并配置
# BINANCE_PROXY_HOST=127.0.0.1
# BINANCE_PROXY_PORT=7897
# TELEGRAM_PROXY_HOST=127.0.0.1
# TELEGRAM_PROXY_PORT=7897
EOF

# 设置权限
chmod 600 .env
```

#### 2. 创建数据目录

```bash
mkdir -p data logs
```

#### 3. 构建并启动服务

```bash
# 构建镜像
docker-compose build

# 启动服务（后台运行）
docker-compose up -d

# 查看日志
docker-compose logs -f

# 查看服务状态
docker-compose ps
```

#### 4. 访问Web界面

浏览器打开: `http://your-server-ip:8501`

默认密码: `beck` （建议在.env中修改）

#### 5. 管理命令

```bash
# 停止服务
docker-compose stop

# 重启服务
docker-compose restart

# 完全删除（数据会保留在data目录）
docker-compose down

# 更新代码并重启
git pull
docker-compose build
docker-compose up -d

# 查看监控服务日志
docker-compose logs -f poc-monitor

# 查看Web服务日志
docker-compose logs -f poc-web

# 进入容器
docker exec -it poc_monitor bash
```

#### 6. 高级配置

**启用Nginx反向代理（HTTPS）：**

```bash
# 创建Nginx配置
mkdir -p nginx

cat > nginx/nginx.conf <<'EOF'
events {
    worker_connections 1024;
}

http {
    upstream streamlit {
        server poc-web:8501;
    }

    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;

        location / {
            proxy_pass http://streamlit;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
EOF

# 放置SSL证书到 nginx/ssl/ 目录

# 启动Nginx
docker-compose --profile with-nginx up -d
```

---

## 方案二：Systemd服务部署

### 优点
- ✅ 系统原生，资源占用小
- ✅ 开机自启动
- ✅ 日志集成到journald

### 缺点
- ❌ 依赖系统环境
- ❌ 难以迁移

### 步骤

#### 1. 安装依赖

```bash
cd /opt/poc-monitor
python3.9 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 2. 配置环境变量

```bash
# 创建环境变量文件
sudo mkdir -p /etc/poc-monitor
sudo cat > /etc/poc-monitor/env <<EOF
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
WEB_PASSWORD=your_password
EOF

sudo chmod 600 /etc/poc-monitor/env
```

#### 3. 创建监控服务

```bash
sudo cat > /etc/systemd/system/poc-monitor.service <<EOF
[Unit]
Description=Binance POC Monitor Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/poc-monitor
EnvironmentFile=/etc/poc-monitor/env
ExecStart=/opt/poc-monitor/.venv/bin/python main.py loop
Restart=always
RestartSec=10

# 安全加固
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/poc-monitor

[Install]
WantedBy=multi-user.target
EOF
```

#### 4. 创建Web服务

```bash
sudo cat > /etc/systemd/system/poc-web.service <<EOF
[Unit]
Description=POC Monitor Web Interface
After=network.target poc-monitor.service

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/poc-monitor
EnvironmentFile=/etc/poc-monitor/env
ExecStart=/opt/poc-monitor/.venv/bin/streamlit run streamlit_app.py --server.port=8501 --server.address=0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

#### 5. 启动服务

```bash
# 重载systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start poc-monitor
sudo systemctl start poc-web

# 开机自启
sudo systemctl enable poc-monitor
sudo systemctl enable poc-web

# 查看状态
sudo systemctl status poc-monitor
sudo systemctl status poc-web

# 查看日志
sudo journalctl -u poc-monitor -f
sudo journalctl -u poc-web -f
```

#### 6. 管理命令

```bash
# 重启服务
sudo systemctl restart poc-monitor
sudo systemctl restart poc-web

# 停止服务
sudo systemctl stop poc-monitor
sudo systemctl stop poc-web

# 查看日志（最近100行）
sudo journalctl -u poc-monitor -n 100

# 清理日志
sudo journalctl --vacuum-time=7d
```

---

## 方案三：直接运行

### 适用场景
- ✅ 临时测试
- ✅ 开发环境

### 步骤

```bash
# 安装依赖
cd /opt/poc-monitor
python3.9 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 配置环境变量
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_CHAT_ID=your_id
export WEB_PASSWORD=your_password

# 使用screen后台运行
screen -S poc-monitor
python main.py loop
# 按Ctrl+A+D分离会话

# 启动Web界面
screen -S poc-web
streamlit run streamlit_app.py
# 按Ctrl+A+D分离会话

# 重新连接
screen -r poc-monitor
screen -r poc-web
```

---

## 生产环境配置

### 1. 安全加固

#### 防火墙配置

```bash
# 启用UFW防火墙
sudo apt install ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing

# 允许SSH
sudo ufw allow 22/tcp

# 允许Web访问（根据需要）
sudo ufw allow 8501/tcp  # Streamlit
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS

# 启用防火墙
sudo ufw enable
```

#### 仅允许特定IP访问

```bash
# 只允许特定IP访问Web界面
sudo ufw delete allow 8501/tcp
sudo ufw allow from 192.168.1.0/24 to any port 8501
```

### 2. 配置HTTPS（使用Let's Encrypt）

```bash
# 安装Certbot
sudo apt install certbot

# 获取证书（需要域名）
sudo certbot certonly --standalone -d your-domain.com

# 证书路径
# /etc/letsencrypt/live/your-domain.com/fullchain.pem
# /etc/letsencrypt/live/your-domain.com/privkey.pem

# 配置Nginx（参考方案一）
```

### 3. 数据备份

```bash
# 创建备份脚本
cat > /opt/poc-monitor/backup.sh <<'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/poc-monitor"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# 备份数据库
cp /opt/poc-monitor/data/poc_monitor.db $BACKUP_DIR/poc_monitor_$DATE.db

# 备份配置
cp /opt/poc-monitor/.env $BACKUP_DIR/env_$DATE

# 删除7天前的备份
find $BACKUP_DIR -name "*.db" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/poc_monitor_$DATE.db"
EOF

chmod +x /opt/poc-monitor/backup.sh

# 添加到crontab（每天凌晨2点备份）
crontab -e
# 添加这行：
0 2 * * * /opt/poc-monitor/backup.sh >> /var/log/poc-backup.log 2>&1
```

### 4. 日志轮转

```bash
# Docker方式已自动配置

# Systemd方式配置logrotate
sudo cat > /etc/logrotate.d/poc-monitor <<EOF
/opt/poc-monitor/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    missingok
    copytruncate
}
EOF
```

---

## 监控和维护

### 1. 健康检查脚本

```bash
cat > /opt/poc-monitor/healthcheck.sh <<'EOF'
#!/bin/bash

# 检查Docker服务
if ! docker ps | grep -q poc_monitor; then
    echo "❌ POC Monitor container is not running"
    docker-compose restart poc-monitor
fi

if ! docker ps | grep -q poc_web; then
    echo "❌ POC Web container is not running"
    docker-compose restart poc-web
fi

# 检查数据库
if [ ! -f /opt/poc-monitor/data/poc_monitor.db ]; then
    echo "❌ Database file missing"
    exit 1
fi

# 检查Web访问
if ! curl -s -o /dev/null -w "%{http_code}" http://localhost:8501 | grep -q 200; then
    echo "⚠️  Web interface not responding"
fi

echo "✅ All checks passed"
EOF

chmod +x /opt/poc-monitor/healthcheck.sh

# 添加到crontab（每5分钟检查）
*/5 * * * * /opt/poc-monitor/healthcheck.sh >> /var/log/poc-health.log 2>&1
```

### 2. 性能监控

```bash
# 查看Docker资源占用
docker stats poc_monitor poc_web

# 查看数据库大小
du -h data/poc_monitor.db

# 查看日志大小
du -h logs/
```

### 3. 更新流程

```bash
# Docker方式
cd /opt/poc-monitor
git pull
docker-compose build
docker-compose up -d

# Systemd方式
cd /opt/poc-monitor
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart poc-monitor
sudo systemctl restart poc-web
```

---

## 故障排除

### 问题1: 容器无法启动

```bash
# 查看详细日志
docker-compose logs poc-monitor

# 检查配置
docker-compose config

# 重新构建
docker-compose build --no-cache
docker-compose up -d
```

### 问题2: 无法访问Web界面

```bash
# 检查端口占用
sudo netstat -tulpn | grep 8501

# 检查防火墙
sudo ufw status

# 检查容器网络
docker network inspect poc_network
```

### 问题3: 数据库锁定

```bash
# 停止所有服务
docker-compose stop

# 检查数据库完整性
sqlite3 data/poc_monitor.db "PRAGMA integrity_check;"

# 重启服务
docker-compose start
```

### 问题4: 内存不足

```bash
# 查看资源使用
docker stats

# 调整内存限制（编辑docker-compose.yml）
deploy:
  resources:
    limits:
      memory: 1G

# 重启服务
docker-compose up -d
```

### 问题5: 代理问题

```bash
# 测试代理
curl -x http://127.0.0.1:7897 https://fapi.binance.com/fapi/v1/ping

# 如果在国外，禁用代理
# 编辑config.py，设置：
BINANCE_USE_PROXY = False
TELEGRAM_USE_PROXY = False
```

---

## 性能优化

### 1. 数据库优化

```bash
# 定期清理旧数据
sqlite3 data/poc_monitor.db <<EOF
DELETE FROM crossover_events WHERE timestamp < datetime('now', '-30 days');
VACUUM;
EOF
```

### 2. 日志清理

```bash
# 清理旧日志
find logs/ -name "*.log" -mtime +7 -delete
```

### 3. 资源限制

在 `docker-compose.yml` 中调整：

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'      # 增加CPU限制
      memory: 1G       # 增加内存限制
```

---

## 安全检查清单

部署后请确认：

- [ ] 已修改默认密码
- [ ] 防火墙已配置
- [ ] HTTPS已启用（生产环境）
- [ ] 定期备份已配置
- [ ] 日志轮转已配置
- [ ] 健康检查已配置
- [ ] 监控告警已配置
- [ ] 环境变量文件权限正确（600）
- [ ] 非root用户运行
- [ ] 数据目录权限正确

---

## 推荐的生产环境架构

```
Internet
    ↓
Nginx (HTTPS, 443)
    ↓
Streamlit Web (8501)
    ↓
POC Monitor Service
    ↓
SQLite Database
```

---

## 相关文档

- [项目说明](CLAUDE.md)
- [代理配置](PROXY_GUIDE.md)
- [访问控制](WEB_AUTH_GUIDE.md)
- [API限流](RATE_LIMIT_GUIDE.md)

---

**作者**: @beck
**最后更新**: 2026-01-20
**版本**: 1.0
