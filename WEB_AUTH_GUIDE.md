# Web访问控制使用指南

## 概述

本项目的Streamlit Web界面已集成访问控制功能，保护您的监控数据不被未授权访问。

## 功能特性

- ✅ **密码认证**: 基于SHA256哈希的安全密码验证
- ✅ **会话管理**: 自动会话超时（默认1小时）
- ✅ **防暴力破解**: 记录登录失败次数并显示警告
- ✅ **时序攻击防护**: 使用恒定时间比较算法
- ✅ **开发模式**: 未设置密码时显示警告但允许访问
- ✅ **IP白名单**: 可选的IP地址限制（高级功能）

## 快速开始

### 1. 设置访问密码

#### Windows:
```bash
# 临时设置（当前会话有效）
set WEB_PASSWORD=your_secure_password

# 永久设置（系统环境变量）
setx WEB_PASSWORD "your_secure_password"
```

#### Linux/Mac:
```bash
# 临时设置
export WEB_PASSWORD=your_secure_password

# 永久设置（添加到 ~/.bashrc 或 ~/.zshrc）
echo 'export WEB_PASSWORD=your_secure_password' >> ~/.bashrc
source ~/.bashrc
```

#### 使用 .env 文件（推荐）:
```bash
# 1. 复制示例文件
copy .env.example .env  # Windows
# cp .env.example .env  # Linux/Mac

# 2. 编辑 .env 文件
WEB_PASSWORD=your_secure_password
WEB_SESSION_TIMEOUT=3600
```

### 2. 启动Web界面

```bash
# 激活虚拟环境
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 启动Streamlit
python main.py web
# 或直接运行
streamlit run streamlit_app.py
```

### 3. 访问Web界面

1. 浏览器打开 `http://localhost:8501`
2. 输入您设置的密码
3. 点击"登录"按钮

## 配置选项

### 环境变量说明

| 变量名 | 说明 | 默认值 | 示例 |
|--------|------|--------|------|
| `WEB_PASSWORD` | Web访问密码 | 无（开发模式） | `my_secure_pass123` |
| `WEB_SESSION_TIMEOUT` | 会话超时时间（秒） | 3600（1小时） | `7200`（2小时） |
| `IP_WHITELIST` | IP白名单（逗号分隔） | 无（不限制） | `192.168.1.1,10.0.0.1` |

### 在config.py中配置

```python
# config.py
class Config:
    # 是否启用访问控制
    ENABLE_WEB_AUTH = True  # 设为False可完全禁用认证

    # 会话超时（秒）
    WEB_SESSION_TIMEOUT = 3600  # 1小时
```

## 安全最佳实践

### 1. 密码强度建议

✅ **推荐的密码**:
- 至少12个字符
- 包含大小写字母、数字和特殊字符
- 示例: `P@ssw0rd!2024#POC`

❌ **避免使用**:
- 简单密码: `123456`, `password`
- 个人信息: 生日、姓名
- 常见词汇: `admin`, `test`

### 2. 生产环境部署

```bash
# 使用强密码
WEB_PASSWORD=$(openssl rand -base64 32)
echo "Generated password: $WEB_PASSWORD"

# 限制IP访问（仅允许内网）
IP_WHITELIST=192.168.1.0/24,10.0.0.0/8

# 缩短会话超时
WEB_SESSION_TIMEOUT=1800  # 30分钟
```

### 3. Docker部署配置

```yaml
# docker-compose.yml
version: '3.8'

services:
  poc-monitor-web:
    build: .
    ports:
      - "8501:8501"
    environment:
      - WEB_PASSWORD=${WEB_PASSWORD}
      - WEB_SESSION_TIMEOUT=3600
      - IP_WHITELIST=${IP_WHITELIST}
    secrets:
      - web_password

secrets:
  web_password:
    file: ./secrets/web_password.txt
```

### 4. Nginx反向代理（推荐）

```nginx
# /etc/nginx/sites-available/poc-monitor
server {
    listen 80;
    server_name poc-monitor.yourdomain.com;

    # 强制HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name poc-monitor.yourdomain.com;

    # SSL证书
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.key;

    # 安全头
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    # IP白名单（可选）
    allow 192.168.1.0/24;
    deny all;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## 使用场景

### 场景1: 本地开发（无密码）

```bash
# 不设置WEB_PASSWORD
streamlit run streamlit_app.py
```

系统会显示警告但允许访问，方便开发调试。

### 场景2: 团队内部使用

```bash
# 设置简单密码
export WEB_PASSWORD=team2024
streamlit run streamlit_app.py
```

### 场景3: 生产环境

```bash
# 强密码 + IP限制 + HTTPS
export WEB_PASSWORD=$(openssl rand -base64 32)
export IP_WHITELIST=192.168.1.0/24
export WEB_SESSION_TIMEOUT=1800

# 使用systemd服务
sudo systemctl start poc-monitor-web
```

## 故障排除

### 问题1: 忘记密码

**解决方案**:
```bash
# 重置密码
unset WEB_PASSWORD  # 临时移除
# 或
set WEB_PASSWORD=new_password  # 设置新密码

# 重启Streamlit
streamlit run streamlit_app.py
```

### 问题2: 会话频繁超时

**解决方案**:
```bash
# 延长会话时间
export WEB_SESSION_TIMEOUT=7200  # 2小时
```

### 问题3: IP白名单无法访问

**解决方案**:
```bash
# 检查当前IP
curl ifconfig.me

# 临时禁用IP限制
unset IP_WHITELIST

# 或添加当前IP到白名单
export IP_WHITELIST=your.current.ip.address
```

### 问题4: 多次登录失败

系统会记录失败次数并显示警告。如果超过5次失败：

1. 确认密码是否正确
2. 检查环境变量是否正确设置
3. 等待1小时后重试（计数器会重置）

## 高级功能

### 自定义认证逻辑

编辑 `auth.py` 文件可以实现更复杂的认证逻辑：

```python
# auth.py
class WebAuthenticator:
    def _verify_password(self, password: str) -> bool:
        # 添加自定义验证逻辑
        # 例如：LDAP认证、OAuth2等
        pass
```

### 集成第三方认证

可以集成以下认证方式：
- OAuth2 (Google, GitHub)
- LDAP/Active Directory
- JWT Token
- 双因素认证(2FA)

### 审计日志

在 `auth.py` 中添加日志记录：

```python
import logging

logger = logging.getLogger(__name__)

def _login(self, password: str) -> bool:
    if self._verify_password(password):
        logger.info(f"Login successful at {datetime.now()}")
        return True
    else:
        logger.warning(f"Login failed at {datetime.now()}")
        return False
```

## 安全检查清单

部署前请确认：

- [ ] 已设置强密码（至少12位）
- [ ] 密码未硬编码在代码中
- [ ] `.env` 文件已添加到 `.gitignore`
- [ ] 会话超时时间合理（建议≤1小时）
- [ ] 生产环境使用HTTPS
- [ ] 考虑启用IP白名单
- [ ] 定期更换密码
- [ ] 监控登录失败日志
- [ ] 备份环境变量配置

## 相关文档

- [部署指南](README.md)
- [代理配置](PROXY_GUIDE.md)
- [项目说明](CLAUDE.md)

## 技术支持

如有问题，请：
1. 查看日志文件 `poc_monitor.log`
2. 检查环境变量配置
3. 提交Issue到项目仓库

---

**作者**: @beck
**最后更新**: 2026-01-20
