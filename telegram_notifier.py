"""
@author beck
Telegram Notification Service
"""
import aiohttp
import logging
from typing import Dict, Optional
from config import Config

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Telegram通知服务"""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        use_proxy: bool = None
    ):
        """
        初始化Telegram通知器
        """
        self.bot_token = bot_token or Config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or Config.TELEGRAM_CHAT_ID

        # 代理设置
        if use_proxy is None:
            self.use_proxy = Config.TELEGRAM_USE_PROXY
        else:
            self.use_proxy = use_proxy

        self.proxy = Config.TELEGRAM_PROXY_URL if self.use_proxy else None

        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram配置不完整，通知功能将不可用")
            self.enabled = False
        else:
            self.enabled = True
            proxy_status = f"(代理: {self.proxy})" if self.use_proxy else "(直连)"
            logger.info(f"Telegram通知服务已启用 {proxy_status}")

        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        disable_notification: bool = False
    ) -> bool:
        """
        发送Telegram消息
        """
        if not self.enabled:
            return False

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": disable_notification
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    proxy=self.proxy
                ) as response:
                    if response.status == 200:
                        logger.info(f"✓ Telegram消息发送成功: {text[:20]}...")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"✗ Telegram消息发送失败: {response.status} - {error_text}")
                        return False
        except Exception as e:
            logger.error(f"✗ Telegram消息发送异常: {e}")
            return False

    async def send_crossover_notification(self, event: Dict) -> bool:
        """
        发送POC穿透通知 (优化版：支持多方向 + 新币标记)
        """
        # POC类型中文说明
        poc_names = {
            "MPOC": "当月POC",
            "PMPOC": "上月POC",
            "PPMPOC": "上上月POC",
            "QPOC": "当季POC",
            "PQPOC": "上季POC",
            "PPQPOC": "上上季POC"
        }

        # 1. 基础数据提取
        symbol = event["symbol"]
        current_price = event["price_after"]
        poc_type = event["poc_type"]
        poc_name = poc_names.get(poc_type, poc_type)
        poc_price = event["poc_value"]
        change_percent = event["change_percent"]
        timestamp = event["timestamp"]

        # 2. 状态判断 (方向 & 新币)
        impact_level = event.get("impact_level", 1)
        cross_type = event.get("cross_type", "UP") # 默认为UP兼容旧数据

        # 判断方向文案
        if cross_type == "UP":
            title_emoji = "🚀"
            action_text = "突破压力位"
            color_emoji = "🟢" # 绿色圆圈
        else:
            title_emoji = "🔻"
            action_text = "跌破支撑位"
            color_emoji = "🔴" # 红色圆圈

        # 3. 构建消息
        # 标题行
        message = f"<b>{title_emoji} POC{action_text}提醒</b>\n\n"

        # 币种行 (带新币标记)
        # 这里虽然拿不到 days_active 具体数字(因为event里可能没传),
        # 但通常我们只关心价格行为，如果需要可以在 monitor.py 的 event 里加上 days_active
        message += f"<b>币种:</b> #{symbol}\n"

        # 核心价格行为
        message += f"<b>动作:</b> {color_emoji} {action_text} {poc_type} ({poc_name})\n"
        message += f"<b>价格:</b> ${current_price:.6f}\n"
        message += f"<b>POC价:</b> ${poc_price:.6f}\n"

        # 涨跌幅格式化
        change_str = f"+{change_percent:.2f}%" if change_percent > 0 else f"{change_percent:.2f}%"
        message += f"<b>波动:</b> {change_str}\n"

        # 冲击力说明
        impact_bar = "🔥" * impact_level + "▫️" * (6 - impact_level)
        message += f"<b>强度:</b> {impact_bar} ({impact_level}/6)\n"

        # 底部时间
        message += f"\n<b>{timestamp}</b> "

        return await self.send_message(message)

    async def send_daily_summary(self, stats: Dict) -> bool:
        """
        发送每日汇总
        """
        message = f"""
📊 <b>每日POC监控日报</b>

📅 日期: {stats.get('timestamp', 'N/A')}

<b>全市场扫描:</b> {stats.get('total_symbols', 0)} 个币种
<b>今日信号数:</b> {stats.get('today_events', 0)} 次
<b>累计捕获:</b> {stats.get('total_events', 0)} 次
<b>待处理:</b> {stats.get('unnotified_events', 0)} 条

💡 <i>请登录 Web 控制台查看详细热力图</i>
        """.strip()

        return await self.send_message(message)

    async def send_hot_symbols(self, hot_symbols: list, top_n: int = 10) -> bool:
        """
        发送热门币种提醒
        """
        if not hot_symbols:
            return False

        message = f"🔥 <b>POC 热门回踩榜 Top {top_n}</b>\n\n"

        for i, symbol_data in enumerate(hot_symbols[:top_n], 1):
            emoji = symbol_data.get("impact_level", {}).get("emoji", "➡️")
            dist = symbol_data['distance_percent']

            # 距离越近，图标越紧急
            dist_icon = "🎯" if dist < 1.0 else "📡"

            message += f"<b>{i}. {symbol_data['symbol']}</b> {emoji}\n"
            message += f"   {dist_icon} 距 {symbol_data['nearest_poc']}: {dist:.2f}%\n"
            message += f"   💰 ${symbol_data['current_price']:.4f}\n\n"

        message += "<i>*筛选逻辑: 当前价格距离POC关卡最近</i>"
        return await self.send_message(message)

    async def test_connection(self) -> bool:
        """测试Telegram连接"""
        if not self.enabled:
            logger.error("Telegram未配置")
            return False

        test_message = "🤖 <b>系统通知</b>\n\n币安POC监控工具连接测试成功！✅"
        result = await self.send_message(test_message)

        if result:
            logger.info("✓ Telegram连接测试成功")
        else:
            logger.error("✗ Telegram连接测试失败")

        return result