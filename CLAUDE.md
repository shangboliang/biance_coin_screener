# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**币安永续合约POC监控工具 (Binance Futures POC Monitor)**

一个用于监控币安永续合约USDT交易对的POC (Point of Control) 突破事件的工具。基于VWAP计算六大关卡（月度和季度POC），实时检测价格穿透，并通过Telegram发送通知。

作者: @beck

## Core Features

1. **POC计算**: 基于典型价格 TP=(H+L+C)/3 计算VWAP
2. **六大关卡**: MPOC, PMPOC, PPMPOC (月度) 和 QPOC, PQPOC, PPQPOC (季度)
3. **实时监控**: 异步处理200+交易对，检测价格穿透事件
4. **数据存储**: SQLite数据库记录POC数据和穿透事件
5. **Telegram通知**: 实时推送突破提醒到指定频道
6. **Web界面**: Streamlit交互式仪表板，包含热图和数据查询

## POC指标说明

| 缩写 | 全称 | 含义 |
|------|------|------|
| QPOC | Current Quarter Point of Control | 本季度VWAP |
| PQPOC | Previous Quarter Point of Control | 上季度VWAP终点值 |
| PPQPOC | Previous Previous Quarter POC | 上上季度VWAP终点值 |
| MPOC | Current Month Point of Control | 本月VWAP |
| PMPOC | Previous Month Point of Control | 上月VWAP终点值 |
| PPMPOC | Previous Previous Month POC | 上上月VWAP终点值 |

## Environment Setup

- **Python Version**: 3.9
- **Virtual Environment**: `.venv`
- **Activate venv**:
  - Windows: `.venv\Scripts\activate`
  - Unix/Mac: `source .venv/bin/activate`
- **Install dependencies**: `pip install -r requirements.txt`

## Configuration

### 代理设置

**币安API和Telegram使用独立的代理配置**

在 `config.py` 中配置:

```python
# 币安API代理
BINANCE_USE_PROXY = True  # 启用/禁用
BINANCE_PROXY_HOST = "127.0.0.1"
BINANCE_PROXY_PORT = 7897

# Telegram代理（独立配置，避免混淆）
TELEGRAM_USE_PROXY = True  # 启用/禁用
TELEGRAM_PROXY_HOST = "127.0.0.1"
TELEGRAM_PROXY_PORT = 7897
```

常见场景：
- 国内用户：两者都设为 `True`
- 国外用户：两者都设为 `False`
- 只需要币安API：只启用 `BINANCE_USE_PROXY`
- 使用不同代理：设置不同的端口号

详见 [PROXY_GUIDE.md](PROXY_GUIDE.md)

### Telegram设置
需要设置环境变量:
```bash
set TELEGRAM_BOT_TOKEN=your_bot_token
set TELEGRAM_CHAT_ID=your_chat_id
```

或在配置文件中直接修改

## Project Structure

```
biance_coin_screener/
├── config.py              # 配置文件（API、代理、Telegram等）
├── binance_api.py         # 币安API异步客户端
├── poc_calculator.py      # POC计算逻辑（VWAP）
├── database.py            # SQLite数据库管理
├── monitor.py             # 核心监控逻辑
├── telegram_notifier.py   # Telegram通知服务
├── streamlit_app.py       # Streamlit Web界面
├── main.py                # 主程序入口
├── requirements.txt       # 依赖包列表
├── poc_monitor.db         # SQLite数据库（自动生成）
└── poc_monitor.log        # 日志文件（自动生成）
```

## Running the Application

### 测试连接
```bash
python main.py test
```
测试币安API和Telegram连接

### 计算POC
```bash
python main.py calc
```
计算所有交易对的POC并保存到数据库

### 单次监控
```bash
python main.py monitor
```
执行一次完整的监控周期

### 持续监控
```bash
python main.py loop
```
启动持续监控模式（默认60秒轮询）

### 查看统计
```bash
python main.py stats
```
显示数据库统计信息

### 启动Web界面
```bash
python main.py web
```
或直接运行:
```bash
streamlit run streamlit_app.py
```

## Architecture

### 数据流
1. **BinanceAPIClient**: 异步获取K线数据，支持批量和并发
2. **POCCalculator**: 计算各周期VWAP作为POC关卡
3. **POCMonitor**: 核心监控器，检测价格穿透事件
4. **DatabaseManager**: 存储POC数据和穿透事件
5. **TelegramNotifier**: 发送实时通知

### 关键算法
- **典型价格**: `TP = (H + L + C) / 3`
- **VWAP**: `VWAP = Σ(TP × Volume) / Σ(Volume)`
- **穿透检测**: 上一价格 < POC ≤ 当前价格
- **冲击力等级**: 基于突破的POC关卡数量（1-6级）

### 数据库设计
- **poc_levels**: POC关卡数据
- **crossover_events**: 穿透事件记录
- **price_history**: 价格历史（用于穿透检测）

## Development Notes

- 项目使用异步编程（asyncio + aiohttp）处理200+交易对
- 代理支持可选：通过 `Config.USE_PROXY` 控制（国内建议启用，国外可禁用）
- 使用信号量控制并发数，避免触发API限流
- POC计算基于日线数据（1d interval）
- 如果币种历史不足，使用全局VWAP填充缺失关卡
- Streamlit界面包含热图、数据表、事件历史、自定义查询等功能

## API Usage

项目直接使用币安原生REST API，不依赖ccxt库:
- Exchange Info: `/fapi/v1/exchangeInfo`
- Kline Data: `/fapi/v1/klines`
- Ticker Price: `/fapi/v1/ticker/price`

API文档: https://binance-docs.github.io/apidocs/futures/en/

## Troubleshooting

### 代理问题
如果API连接失败，检查:
1. 如果在国内需要代理：
   - 确认代理是否正常运行（127.0.0.1:7897）
   - config.py中设置 `USE_PROXY = True`
2. 如果在国外或可以直接访问：
   - config.py中设置 `USE_PROXY = False`
3. 运行 `python main.py test` 测试连接

### Telegram未收到通知
1. 检查环境变量是否设置
2. 运行 `python main.py test` 测试连接
3. 确认Bot Token和Chat ID正确

### 数据库问题
- 数据库文件: `poc_monitor.db`
- 如需重置: 删除数据库文件后重新运行

## Extending Functionality

### 添加新的POC类型
在 `poc_calculator.py` 中扩展 `POCLevels` 类

### 自定义监控间隔
修改 `config.py` 中的 `MONITOR_INTERVAL`

### 升级为WebSocket
当前使用REST API，可在 `binance_api.py` 中添加WebSocket支持实现实时价格推送
