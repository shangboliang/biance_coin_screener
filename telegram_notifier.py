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
        chat_id: Optional[str] = None
    ):
        """
        初始化Telegram通知器

        Args:
            bot_token: Telegram Bot Token
            chat_id: Telegram Chat ID
        """
        self.bot_token = bot_token or Config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or Config.TELEGRAM_CHAT_ID

        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram配置不完整，通知功能将不可用")
            self.enabled = False
        else:
            self.enabled = True
            logger.info("Telegram通知服务已启用")

        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        disable_notification: bool = False
    ) -> bool:
        """
        发送Telegram消息

        Args:
            text: 消息文本
            parse_mode: 解析模式（HTML/Markdown）
            disable_notification: 是否禁用通知声音

        Returns:
            是否发送成功
        """
        if not self.enabled:
            logger.warning("Telegram未启用，跳过发送消息")
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
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.info("✓ Telegram消息发送成功")
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
        发送POC穿透通知

        Args:
            event: 穿透事件数据

        Returns:
            是否发送成功
        """
        # 准备消息数据
        symbol = event["symbol"]
        current_price = event["price_after"]
        poc_level = event["poc_type"]
        poc_price = event["poc_value"]
        change_percent = event["change_percent"]
        timestamp = event["timestamp"]
        impact_emoji = event.get("impact_emoji", "🚀")

        # 额外信息
        extra_info = f"{impact_emoji} 冲击力等级: {event.get('impact_level', 1)}/6"

        # 构建消息
        message = f"""
{impact_emoji} <b>POC突破提醒！</b>

<b>币种:</b> {symbol}
<b>当前价格:</b> ${current_price:.6f}
<b>突破关卡:</b> {poc_level}
<b>关卡价格:</b> ${poc_price:.6f}
<b>涨幅:</b> {change_percent:+.2f}%
<b>时间:</b> {timestamp}

{extra_info}
        """.strip()

        return await self.send_message(message)

    async def send_daily_summary(self, stats: Dict) -> bool:
        """
        发送每日汇总

        Args:
            stats: 统计数据

        Returns:
            是否发送成功
        """
        message = f"""
📊 <b>每日POC监控汇总</b>

<b>监控交易对数:</b> {stats.get('total_symbols', 0)}
<b>今日穿透事件:</b> {stats.get('today_events', 0)}
<b>总穿透事件:</b> {stats.get('total_events', 0)}
<b>未处理事件:</b> {stats.get('unnotified_events', 0)}

生成时间: {stats.get('timestamp', 'N/A')}
        """.strip()

        return await self.send_message(message)

    async def send_hot_symbols(self, hot_symbols: list, top_n: int = 10) -> bool:
        """
        发送热门币种提醒

        Args:
            hot_symbols: 热门币种列表
            top_n: 显示数量

        Returns:
            是否发送成功
        """
        if not hot_symbols:
            return False

        message = f"🔥 <b>热门币种提醒 (最接近POC关卡)</b>\n\n"

        for i, symbol_data in enumerate(hot_symbols[:top_n], 1):
            impact_info = symbol_data.get("impact_level", {})
            emoji = impact_info.get("emoji", "➡️")

            message += f"{i}. <b>{symbol_data['symbol']}</b> {emoji}\n"
            message += f"   价格: ${symbol_data['current_price']:.6f}\n"
            message += f"   最近关卡: {symbol_data['nearest_poc']}\n"
            message += f"   距离: {symbol_data['distance_percent']:.2f}%\n\n"

        return await self.send_message(message)

    async def test_connection(self) -> bool:
        """
        测试Telegram连接

        Returns:
            是否连接成功
        """
        if not self.enabled:
            logger.error("Telegram未配置")
            return False

        test_message = "🤖 币安POC监控工具测试消息"
        result = await self.send_message(test_message)

        if result:
            logger.info("✓ Telegram连接测试成功")
        else:
            logger.error("✗ Telegram连接测试失败")

        return result

    def format_poc_info(self, poc_levels) -> str:
        """
        格式化POC信息为文本

        Args:
            poc_levels: POC关卡数据

        Returns:
            格式化的文本
        """
        text = f"<b>{poc_levels.symbol}</b>\n"
        text += f"当前价格: ${poc_levels.current_price:.6f}\n\n"

        text += "📊 <b>POC关卡:</b>\n"

        poc_data = [
            ("MPOC (当月)", poc_levels.mpoc),
            ("PMPOC (上月)", poc_levels.pmpoc),
            ("PPMPOC (上上月)", poc_levels.ppmpoc),
            ("QPOC (当季)", poc_levels.qpoc),
            ("PQPOC (上季)", poc_levels.pqpoc),
            ("PPQPOC (上上季)", poc_levels.ppqpoc),
        ]

        for label, value in poc_data:
            if value:
                # 判断价格是否突破
                if poc_levels.current_price > value:
                    status = "✅ 已突破"
                elif abs(poc_levels.current_price - value) / value < 0.01:
                    status = "⚠️ 接近"
                else:
                    status = "⬇️ 下方"

                text += f"  {label}: ${value:.6f} {status}\n"

        return text
