# 代理配置说明

## 独立代理配置

项目支持为币安API和Telegram分别配置代理，互不影响。

## 配置位置

在 `config.py` 文件中：

### 币安API代理
```python
# 币安API代理配置
BINANCE_USE_PROXY = True  # 启用/禁用代理
BINANCE_PROXY_HOST = "127.0.0.1"
BINANCE_PROXY_PORT = 7897
```

### Telegram代理
```python
# Telegram代理配置（独立于币安API代理）
TELEGRAM_USE_PROXY = True  # 启用/禁用代理
TELEGRAM_PROXY_HOST = "127.0.0.1"
TELEGRAM_PROXY_PORT = 7897
```

## 使用场景

### 场景1：国内用户，两者都需要代理
```python
BINANCE_USE_PROXY = True
TELEGRAM_USE_PROXY = True
```

### 场景2：国外用户，两者都不需要代理
```python
BINANCE_USE_PROXY = False
TELEGRAM_USE_PROXY = False
```

### 场景3：只有币安需要代理
```python
BINANCE_USE_PROXY = True
TELEGRAM_USE_PROXY = False
```

### 场景4：使用不同的代理服务器
```python
# 币安使用代理A
BINANCE_USE_PROXY = True
BINANCE_PROXY_HOST = "127.0.0.1"
BINANCE_PROXY_PORT = 7897

# Telegram使用代理B
TELEGRAM_USE_PROXY = True
TELEGRAM_PROXY_HOST = "127.0.0.1"
TELEGRAM_PROXY_PORT = 7898
```

## 测试配置

运行测试命令会分别显示两个代理的状态：

```bash
python main.py test
```

输出示例：
```
测试币安API连接...
币安API代理: 启用
✓ 币安API连接成功

测试Telegram连接...
Telegram代理: 启用
✓ Telegram连接测试成功
```

## 常见代理类型

- HTTP代理: `http://host:port`
- HTTPS代理: `https://host:port`
- Socks5代理: `socks5://host:port`

**注意**：当前版本支持HTTP/HTTPS代理。如需Socks5代理，需要额外配置。

## 故障排除

### 币安API连接失败
1. 检查 `BINANCE_USE_PROXY` 是否正确设置
2. 检查代理服务器是否正常运行
3. 尝试在浏览器中通过相同代理访问 https://fapi.binance.com

### Telegram发送失败
1. 检查 `TELEGRAM_USE_PROXY` 是否正确设置
2. 检查Bot Token和Chat ID是否正确
3. 尝试在浏览器中通过相同代理访问 https://api.telegram.org

### 代理服务器常见端口
- Clash: 7890
- V2Ray: 10808
- Shadowsocks: 1080
- HTTP代理: 8080, 3128
