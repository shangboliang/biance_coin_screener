# 币安API速率限制说明

## 问题原因

币安API有严格的速率限制：
- 每分钟最多2400的请求权重
- 超过限制会返回HTTP 429（速率限制）
- 持续违规会导致IP被封禁（HTTP 418），封禁时间2分钟-3天

## 已实施的优化

### 1. 降低并发数
```python
MAX_CONCURRENT_REQUESTS = 5  # 从50降低到5
```

### 2. 增加请求延迟
```python
REQUEST_DELAY = 0.3  # 每个请求间隔0.3秒
```

### 3. 分批处理
```python
BATCH_SIZE = 50  # 每批处理50个交易对
BATCH_DELAY = 5.0  # 批次间延迟5秒
```

### 4. 智能速率限制管理
- 实时监控权重使用情况
- 接近限制时自动等待
- 使用80%安全余量

### 5. 改进的重试机制
- 收到429错误时读取Retry-After头
- 指数退避策略
- 自动重置权重计数器

## 运行时间估算

对于541个交易对：
- 分为11批（每批50个）
- 每批大约需要30-60秒
- 批次间延迟5秒
- 总计约15-20分钟

## 如果仍然遇到速率限制

### 方案1：进一步降低并发数
在 `config.py` 中修改：
```python
MAX_CONCURRENT_REQUESTS = 3  # 降低到3
REQUEST_DELAY = 0.5  # 增加到0.5秒
```

### 方案2：减少批次大小
```python
BATCH_SIZE = 30  # 降低到30
BATCH_DELAY = 10.0  # 增加到10秒
```

### 方案3：只监控部分交易对
在运行时指定交易对列表：
```python
# 在main.py或monitor.py中
symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']  # 只监控这些
await monitor.calculate_all_pocs(symbols)
```

### 方案4：使用缓存策略
- 不需要每次都计算所有交易对
- 可以每天只更新一次POC数据
- 监控时只更新价格，不重新计算POC

## 如果IP已被封禁

1. **等待解封**
   - 首次封禁：2分钟
   - 重复违规：逐渐增加到3天

2. **检查日志**
   ```bash
   # 查看日志了解封禁时间
   cat poc_monitor.log | grep "418"
   ```

3. **更换IP（如果可能）**
   - 更换代理
   - 使用VPN
   - 使用不同的网络

## 推荐使用方式

### 首次运行（计算POC）
```bash
# 使用最保守的设置
python main.py calc
```
预计需要15-20分钟

### 日常监控
一旦POC数据计算完成，日常监控很快：
```bash
# 单次监控（只更新价格，不重新计算POC）
python main.py monitor
```
预计需要1-2分钟

### 持续监控
```bash
# 启动后台监控
python main.py loop
```
每分钟自动监控一次

## 最佳实践

1. **首次使用**：先运行 `python main.py calc` 计算所有POC
2. **每日更新**：每天运行一次calc更新POC数据
3. **实时监控**：使用 `python main.py loop` 持续监控
4. **Web界面**：使用 `python main.py web` 查看数据

## 进阶优化（未来版本）

1. 使用WebSocket获取实时价格（不占用REST API权重）
2. 实现本地缓存机制
3. 添加数据库查询优先级
4. 支持增量更新而非全量计算
