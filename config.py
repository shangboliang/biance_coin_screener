"""
@author beck
Configuration file for Binance POC Monitor
"""
import os
from typing import Optional

class Config:
    """应用配置类"""

    # ==================== 币安API配置 ====================
    BINANCE_BASE_URL = "https://fapi.binance.com"
    BINANCE_TEST_URL = "https://demo-fapi.binance.com"

    # 代理配置
    USE_PROXY = True  # 设置为False则不使用代理，True则使用代理
    PROXY_HOST = "127.0.0.1"
    PROXY_PORT = 7897
    PROXY_URL = f"http://{PROXY_HOST}:{PROXY_PORT}"

    # API限制
    MAX_KLINES_LIMIT = 500  # 单次请求最大K线数
    REQUEST_WEIGHT_LIMIT = 2400  # 每分钟请求权重限制

    # K线间隔
    KLINE_INTERVAL_1D = "1d"  # 日线

    # ==================== 数据库配置 ====================
    DB_NAME = "poc_monitor.db"
    DB_PATH = os.path.join(os.path.dirname(__file__), DB_NAME)

    # ==================== Telegram配置 ====================
    TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: Optional[str] = os.getenv("TELEGRAM_CHAT_ID", "")

    # Telegram消息模板
    TELEGRAM_MESSAGE_TEMPLATE = """
🚀 POC突破提醒！

币种: {symbol}
当前价格: ${current_price:.6f}
突破关卡: {poc_level}
关卡价格: ${poc_price:.6f}
涨幅: {change_percent:.2f}%
时间: {timestamp}

{extra_info}
    """

    # ==================== POC计算配置 ====================
    # POC类型定义
    POC_TYPES = {
        'QPOC': 'Current Quarter Point of Control',
        'PQPOC': 'Previous Quarter Point of Control',
        'PPQPOC': 'Previous Previous Quarter POC',
        'MPOC': 'Current Month Point of Control',
        'PMPOC': 'Previous Month Point of Control',
        'PPMPOC': 'Previous Previous Month POC'
    }

    # 价格接近阈值（百分比）
    PRICE_PROXIMITY_THRESHOLD = 0.01  # 1%

    # ==================== 监控配置 ====================
    # 监控轮询间隔（秒）
    MONITOR_INTERVAL = 60  # 1分钟

    # 并发请求数（降低以避免触发速率限制）
    MAX_CONCURRENT_REQUESTS = 5  # 从50降低到5

    # 请求超时（秒）
    REQUEST_TIMEOUT = 30

    # 重试配置
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # 秒，增加延迟

    # 速率限制管理
    RATE_LIMIT_SAFETY_MARGIN = 0.8  # 使用80%的速率限制，留20%余量
    REQUEST_DELAY = 0.3  # 每个请求之间的延迟（秒）
    BATCH_SIZE = 50  # 每批处理的交易对数量
    BATCH_DELAY = 5.0  # 每批之间的延迟（秒）

    # ==================== Streamlit配置 ====================
    STREAMLIT_PAGE_TITLE = "币安POC监控工具"
    STREAMLIT_PAGE_ICON = "📊"
    STREAMLIT_LAYOUT = "wide"

    # 热图配色方案
    HEATMAP_COLORSCALE = "RdYlGn"

    # ==================== 冲击力等级配置 ====================
    IMPACT_LEVELS = {
        6: {"emoji": "🚀🚀🚀", "label": "超级冲击", "color": "#FF0000"},
        5: {"emoji": "🚀🚀", "label": "强力冲击", "color": "#FF4500"},
        4: {"emoji": "🚀", "label": "显著冲击", "color": "#FFA500"},
        3: {"emoji": "⚡", "label": "中等冲击", "color": "#FFD700"},
        2: {"emoji": "📈", "label": "轻度冲击", "color": "#90EE90"},
        1: {"emoji": "➡️", "label": "微弱冲击", "color": "#87CEEB"}
    }

    # ==================== 日志配置 ====================
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE = "poc_monitor.log"

    @classmethod
    def validate(cls) -> bool:
        """验证配置是否完整"""
        if not cls.TELEGRAM_BOT_TOKEN or not cls.TELEGRAM_CHAT_ID:
            print("⚠️ 警告: Telegram配置未设置，通知功能将不可用")
            print("请设置环境变量: TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID")
            return False
        return True

    @classmethod
    def get_proxy_config(cls) -> dict:
        """获取代理配置"""
        return {
            "http": cls.PROXY_URL,
            "https": cls.PROXY_URL
        }
