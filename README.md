# 币安永续合约POC监控工具 🚀

> **@author beck**

一个强大的币安永续合约USDT交易对POC (Point of Control) 监控工具，基于VWAP计算六大关卡，实时检测价格穿透事件，并通过Telegram推送通知。

## ✨ 核心功能

- 📊 **POC计算**: 基于典型价格 `TP = (H+L+C)/3` 计算VWAP
- 🎯 **六大关卡**: 月度POC (MPOC, PMPOC, PPMPOC) 和季度POC (QPOC, PQPOC, PPQPOC)
- ⚡ **异步处理**: 高效处理200+交易对，使用aiohttp实现并发请求
- 💾 **数据存储**: SQLite数据库记录所有POC数据和穿透事件
- 📱 **实时通知**: Telegram机器人推送突破提醒
- 🎨 **Web界面**: Streamlit交互式仪表板，包含热图、数据查询等功能
- 🔥 **冲击力等级**: 智能评估突破强度（1-6级）

## 📋 POC指标说明

| 缩写 | 全称 | 含义 |
|------|------|------|
| **QPOC** | Current Quarter Point of Control | 本季度成交量最集中的价格（当前季度VWAP） |
| **PQPOC** | Previous Quarter Point of Control | 上一个季度的VWAP终点值 |
| **PPQPOC** | Previous Previous Quarter POC | 上上个季度的VWAP终点值 |
| **MPOC** | Current Month Point of Control | 本月成交量最集中的价格（当前月度VWAP） |
| **PMPOC** | Previous Month Point of Control | 上个月的VWAP终点值 |
| **PPMPOC** | Previous Previous Month POC | 上上个月的VWAP终点值 |

## 🚀 快速开始

### 1. 环境准备

```bash
# Python 3.9
# 激活虚拟环境
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Unix/Mac

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置

#### 代理设置（可选）

**币安API和Telegram使用独立的代理配置**

在 `config.py` 中配置：

```python
# 币安API代理
BINANCE_USE_PROXY = True  # 启用/禁用
BINANCE_PROXY_HOST = "127.0.0.1"
BINANCE_PROXY_PORT = 7897

# Telegram代理（独立配置）
TELEGRAM_USE_PROXY = True  # 启用/禁用
TELEGRAM_PROXY_HOST = "127.0.0.1"
TELEGRAM_PROXY_PORT = 7897
```

常见场景：
- **国内用户**：两者都设为 `True`
- **国外用户**：两者都设为 `False`
- **只需要访问币安**：只启用 `BINANCE_USE_PROXY`

详见 [PROXY_GUIDE.md](PROXY_GUIDE.md)

#### Telegram设置（可选）
设置环境变量以启用通知功能：
```bash
# Windows
set TELEGRAM_BOT_TOKEN=your_bot_token
set TELEGRAM_CHAT_ID=your_chat_id

# Unix/Mac
export TELEGRAM_BOT_TOKEN=your_bot_token
export TELEGRAM_CHAT_ID=your_chat_id
```

### 3. 运行

#### 测试连接
```bash
python main.py test
```

#### 计算POC
```bash
python main.py calc
```

#### 单次监控
```bash
python main.py monitor
```

#### 持续监控（推荐）
```bash
python main.py loop
```

#### 启动Web界面
```bash
python main.py web
```
或
```bash
streamlit run streamlit_app.py
```

访问: http://localhost:8501

## 📊 Web界面功能

### 1. 概览页面
- 实时统计信息
- 热门币种（最接近POC关卡）
- 最近穿透事件

### 2. POC热图 🗺️
- 可视化所有交易对的POC突破状态
- 绿色=已突破，黄色=接近，红色=下方
- 一眼识别密集冲击区域

### 3. POC数据表
- 完整的POC数据展示
- 冲击力等级筛选
- 交易对搜索
- CSV导出功能

### 4. 穿透事件历史
- 所有突破事件记录
- POC类型分布统计
- 冲击力等级分布

### 5. 热门币种
- 按接近度排序
- 显示最近POC和距离
- 突破数量统计

### 6. 自定义查询
- 灵活的SQL查询
- 预设常用查询
- 实时结果展示

**预设查询示例:**
- 突破所有季度POC: `current_price > qpoc AND current_price > pqpoc AND current_price > ppqpoc`
- 接近当季POC (1%): `ABS(current_price - qpoc) / qpoc < 0.01`

## 🎯 核心算法

### VWAP计算
```
典型价格 TP = (High + Low + Close) / 3
VWAP = Σ(TP × Volume) / Σ(Volume)
```

### 穿透检测
```
上一价格 < POC价格 ≤ 当前价格
```

### 冲击力等级
基于突破的POC关卡数量：
- 6级 🚀🚀🚀 : 超级冲击
- 5级 🚀🚀 : 强力冲击
- 4级 🚀 : 显著冲击
- 3级 ⚡ : 中等冲击
- 2级 📈 : 轻度冲击
- 1级 ➡️ : 微弱冲击

## 📁 项目结构

```
biance_coin_screener/
├── config.py              # 配置文件
├── binance_api.py         # 币安API客户端
├── poc_calculator.py      # POC计算逻辑
├── database.py            # 数据库管理
├── monitor.py             # 核心监控逻辑
├── telegram_notifier.py   # Telegram通知
├── streamlit_app.py       # Web界面
├── main.py                # 主程序入口
├── requirements.txt       # 依赖包
├── poc_monitor.db         # 数据库（自动生成）
└── poc_monitor.log        # 日志文件（自动生成）
```

## 🛠️ 技术栈

- **Python 3.9**: 主要编程语言
- **aiohttp**: 异步HTTP客户端
- **asyncio**: 异步编程框架
- **SQLite**: 轻量级数据库
- **Streamlit**: Web界面框架
- **Plotly**: 数据可视化
- **Pandas**: 数据处理

## 📝 使用示例

### 简单方式（推荐新手）

#### 1. 查看热门币种
在Web界面点击"热门币种"标签，自动显示最接近POC关卡的币种

#### 2. 筛选强势币种
在"POC数据表"标签中：
- 使用"最小冲击力等级"下拉菜单筛选
- 选择等级4以上查看强势突破币种
- 使用搜索框输入币种名称快速定位

#### 3. 查看突破事件
在"穿透事件"标签中：
- 自动显示所有历史突破事件
- 可按交易对筛选
- 包含统计图表

### 高级方式（自定义查询）

在"自定义查询"标签中，可以使用预设查询或编写SQL条件：

**预设查询（直接选择）：**
- 突破所有季度POC
- 突破所有月度POC
- 接近当季POC (1%)
- 接近当月POC (1%)
- 高于全局POC

**自定义SQL条件示例：**
```sql
-- 查找接近QPOC的币种（1%以内）
ABS(current_price - qpoc) / qpoc < 0.01

-- 查找突破所有POC的币种
current_price > mpoc AND current_price > pmpoc AND
current_price > ppmpoc AND current_price > qpoc AND
current_price > pqpoc AND current_price > ppqpoc

-- 查找高价币种（价格>100）
current_price > 100
```

## ⚠️ 速率限制说明

币安API有严格的速率限制（每分钟2400权重）。对于541个交易对：
- **首次计算POC**：需要15-20分钟
- **日常监控**：1-2分钟
- 已优化：并发数降低、分批处理、智能延迟

详见 [RATE_LIMIT_GUIDE.md](RATE_LIMIT_GUIDE.md)

## 🔧 常见问题

### Q: 无法连接币安API
**A:**
1. 如果在国内，检查代理是否正常运行（`127.0.0.1:7897`），确保 `USE_PROXY = True`
2. 如果在国外或可以直接访问，设置 `USE_PROXY = False`
3. 运行 `python main.py test` 测试连接

### Q: 收到HTTP 429（速率限制）或418（IP被封禁）
**A:**
1. 这是正常的保护机制，程序已经做了优化
2. 如果IP被封禁，等待2分钟-3天自动解封
3. 可以进一步降低并发数：修改 `config.py` 中的 `MAX_CONCURRENT_REQUESTS`
4. 详细说明参考 [RATE_LIMIT_GUIDE.md](RATE_LIMIT_GUIDE.md)

### Q: Telegram未收到通知
**A:**
1. 确认环境变量已设置
2. 运行 `python main.py test` 测试连接
3. 检查Bot Token和Chat ID是否正确

### Q: 如何调整监控间隔？
**A:** 修改 `config.py` 中的 `MONITOR_INTERVAL`（默认60秒）

### Q: 数据库在哪里？
**A:** `poc_monitor.db` 在项目根目录，可使用SQLite工具查看

## 🚀 扩展功能

### 计划中的功能
- [ ] WebSocket实时价格推送
- [ ] 更多技术指标集成
- [ ] 邮件通知支持
- [ ] 移动端应用
- [ ] 回测功能
- [ ] AI预测模型

### 自定义扩展
- 在 `poc_calculator.py` 中添加新的POC类型
- 在 `streamlit_app.py` 中添加新的可视化页面
- 在 `monitor.py` 中自定义监控逻辑

## 📄 许可证

本项目仅供学习和研究使用。

## 👨‍💻 作者

**beck**

如有问题或建议，欢迎提Issue！

---

**⚠️ 免责声明**: 本工具仅用于数据分析和学习，不构成任何投资建议。加密货币投资有风险，请谨慎决策。
