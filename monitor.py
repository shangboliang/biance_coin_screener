"""
@author beck
POC Monitor - Core monitoring logic
"""
import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime

from binance_api import BinanceAPIClient
from poc_calculator import POCCalculator, POCLevels
from database import DatabaseManager
from config import Config

logger = logging.getLogger(__name__)


class POCMonitor:
    """POC监控器"""

    def __init__(self, use_proxy: bool = True):
        """
        初始化POC监控器

        Args:
            use_proxy: 是否使用代理
        """
        self.use_proxy = use_proxy
        self.db = DatabaseManager()
        self.api_client: Optional[BinanceAPIClient] = None

    async def initialize(self):
        """初始化API客户端"""
        self.api_client = BinanceAPIClient(use_proxy=self.use_proxy)
        await self.api_client.create_session()
        logger.info("POC监控器初始化完成")

    async def cleanup(self):
        """清理资源"""
        if self.api_client:
            await self.api_client.close_session()
        logger.info("POC监控器资源已清理")

    async def calculate_symbol_poc(self, symbol: str) -> Optional[POCLevels]:
        """
        计算单个交易对的所有POC关卡 (优化版：减少API请求次数)

        优化逻辑：
        不再分别请求7个时间段的K线（原逻辑8次请求），
        改为只请求1次全量（365天）K线，然后在内存中进行切片分类。
        总请求数降为：1次价格 + 1次K线 = 2次。

        Args:
            symbol: 交易对符号

        Returns:
            POC关卡数据
        """
        try:
            # 1. 获取当前价格 (请求 #1)
            current_price = await self.api_client.get_current_price(symbol)
            if not current_price:
                logger.warning(f"{symbol}: 无法获取当前价格")
                return None

            # 2. 获取各周期的时间戳范围 (本地计算，不消耗API)
            # 格式: (start_timestamp, end_timestamp)
            time_ranges = {
                "mpoc": self.api_client.get_month_range(0),  # 当月
                "pmpoc": self.api_client.get_month_range(1),  # 上月
                "ppmpoc": self.api_client.get_month_range(2),  # 前月
                "qpoc": self.api_client.get_quarter_range(0),  # 当季
                "pqpoc": self.api_client.get_quarter_range(1),  # 上季
                "ppqpoc": self.api_client.get_quarter_range(2),  # 前季
            }

            # 3. 获取全局K线数据 (请求 #2，一次拉取365天)
            global_start, global_end = self.api_client.calculate_time_range(365)
            global_klines = await self.api_client.get_klines_batch(symbol, "1d", global_start, global_end)

            if not global_klines:
                # 如果完全没K线数据，说明可能是刚上架几秒钟或API错误
                return None

            # 4. 内存切片：根据时间戳将 global_klines 分配到各个周期
            # Binance K线格式: [open_time, open, high, low, close, volume, ...]
            # k[0] 是开盘时间戳

            sliced_data = {}
            for key, (start_ts, end_ts) in time_ranges.items():
                # 列表推导式筛选，速度极快
                sliced_data[key] = [
                    k for k in global_klines
                    if start_ts <= k[0] <= end_ts
                ]

            # 5. 计算所有POC
            # 注意参数顺序：当月, 上月, 前月, 当季, 上季, 前季, 全局
            pocs = POCCalculator.calculate_all_pocs(
                sliced_data["mpoc"],
                sliced_data["pmpoc"],
                sliced_data["ppmpoc"],
                sliced_data["qpoc"],
                sliced_data["pqpoc"],
                sliced_data["ppqpoc"],
                global_klines
            )

            # 6. 创建POC关卡对象
            poc_levels = POCLevels(
                symbol=symbol,
                current_price=current_price,
                mpoc=pocs.get("mpoc"),
                pmpoc=pocs.get("pmpoc"),
                ppmpoc=pocs.get("ppmpoc"),
                qpoc=pocs.get("qpoc"),
                pqpoc=pocs.get("pqpoc"),
                ppqpoc=pocs.get("ppqpoc"),
                global_poc=pocs.get("global_poc"),
                days_active=pocs.get("days_active", 9999)  # 传递新币天数
            )

            logger.debug(f"{symbol}: POC计算完成 (优化模式)")
            return poc_levels

        except Exception as e:
            logger.error(f"{symbol}: POC计算失败 - {e}")
            return None

    async def calculate_all_pocs(self, symbols: Optional[List[str]] = None) -> List[POCLevels]:
        """
        计算所有交易对的POC（分批处理）

        Args:
            symbols: 交易对列表（可选，默认获取所有USDT永续合约）

        Returns:
            POC关卡列表
        """
        if not symbols:
            logger.info("正在获取所有USDT永续合约交易对...")
            symbols = await self.api_client.get_all_usdt_perpetual_symbols()

        total_symbols = len(symbols)
        batch_size = Config.BATCH_SIZE
        logger.info(f"开始计算 {total_symbols} 个交易对的POC（分 {(total_symbols + batch_size - 1) // batch_size} 批处理）...")

        all_poc_levels = []

        # 分批处理
        for batch_num, i in enumerate(range(0, total_symbols, batch_size), 1):
            batch_symbols = symbols[i:i + batch_size]
            logger.info(f"处理第 {batch_num} 批: {len(batch_symbols)} 个交易对...")

            # 使用信号量限制并发数
            semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT_REQUESTS)

            async def calculate_with_semaphore(symbol):
                async with semaphore:
                    return await self.calculate_symbol_poc(symbol)

            # 并发计算当前批次的POC
            tasks = [calculate_with_semaphore(symbol) for symbol in batch_symbols]
            results = await asyncio.gather(*tasks)

            # 过滤掉失败的结果
            batch_poc_levels = [r for r in results if r is not None]
            all_poc_levels.extend(batch_poc_levels)

            logger.info(f"第 {batch_num} 批完成: {len(batch_poc_levels)}/{len(batch_symbols)} 个成功")

            # 批次间延迟（除了最后一批）
            if i + batch_size < total_symbols:
                logger.info(f"等待 {Config.BATCH_DELAY} 秒后处理下一批...")
                await asyncio.sleep(Config.BATCH_DELAY)

        logger.info(f"全部完成: 成功计算 {len(all_poc_levels)}/{total_symbols} 个交易对的POC")
        return all_poc_levels

    def check_crossovers(self, symbol: str, current_poc_levels: POCLevels) -> List[Dict]:
        events = []
        prev_price = self.db.get_latest_price(symbol)

        if prev_price is None:
            self.db.save_price(symbol, current_poc_levels.current_price)
            return events

        current_price = current_poc_levels.current_price
        poc_types = ["MPOC", "PMPOC", "PPMPOC", "QPOC", "PQPOC", "PPQPOC"]

        for poc_type in poc_types:
            poc_value = current_poc_levels.get_poc_value(poc_type)

            # 使用新的 check_crossover_type 方法
            if poc_value:
                # 注意：这里调用的是修改后的方法名
                cross_type = POCCalculator.check_crossover_type(prev_price, current_price, poc_value)

                if cross_type:
                    change_percent = ((current_price - prev_price) / prev_price) * 100
                    impact_info = POCCalculator.calculate_impact_level(current_poc_levels)

                    # 根据方向定义 Emoji 和 描述
                    if cross_type == "UP":
                        direction_emoji = "🚀"  # 火箭
                        action_label = "向上突破"
                    else:
                        direction_emoji = "🔻"  # 向下红色倒三角
                        action_label = "向下跌破"

                    event = {
                        "symbol": symbol,
                        "poc_type": poc_type,
                        "poc_value": poc_value,
                        "price_before": prev_price,
                        "price_after": current_price,
                        "change_percent": change_percent,
                        "impact_level": impact_info["count"],
                        # 组合 Emoji: 方向 + 冲击力
                        "impact_emoji": f"{direction_emoji} {impact_info['emoji']}",
                        "cross_type": cross_type,  # 新增字段记录方向
                        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    }

                    events.append(event)
                    logger.info(f"{direction_emoji} 检测到{action_label}: {symbol} - {poc_type} @ ${poc_value:.6f}")

        self.db.save_price(symbol, current_price)
        return events

    async def monitor_once(self, symbols: Optional[List[str]] = None) -> Dict[str, any]:
        """
        执行一次完整的监控

        Args:
            symbols: 交易对列表（可选）

        Returns:
            监控结果统计
        """
        logger.info("=" * 60)
        logger.info("开始新一轮监控...")

        # 计算所有POC
        poc_levels_list = await self.calculate_all_pocs(symbols)

        # 保存POC数据
        for poc_levels in poc_levels_list:
            self.db.save_poc_levels(poc_levels.to_dict())

        # 检查穿透事件
        total_events = 0
        crossover_events = []

        for poc_levels in poc_levels_list:
            events = self.check_crossovers(poc_levels.symbol, poc_levels)
            if events:
                for event in events:
                    self.db.save_crossover_event(event)
                    crossover_events.append(event)
                    total_events += 1

        # 统计结果
        stats = {
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "total_symbols": len(poc_levels_list),
            "total_events": total_events,
            "crossover_events": crossover_events
        }

        logger.info(f"监控完成: {stats['total_symbols']} 个交易对, {stats['total_events']} 个穿透事件")
        logger.info("=" * 60)

        return stats

    async def monitor_loop(self, symbols: Optional[List[str]] = None):
        """
        持续监控循环

        Args:
            symbols: 交易对列表（可选）
        """
        logger.info(f"启动持续监控模式，轮询间隔: {Config.MONITOR_INTERVAL}秒")

        # 导入telegram_notifier（避免循环导入）
        try:
            from telegram_notifier import TelegramNotifier
            telegram = TelegramNotifier()
            use_telegram = True
        except Exception as e:
            logger.warning(f"Telegram通知不可用: {e}")
            use_telegram = False

        while True:
            try:
                # 执行一次监控
                stats = await self.monitor_once(symbols)

                # 发送Telegram通知
                if use_telegram and stats["total_events"] > 0:
                    for event in stats["crossover_events"]:
                        await telegram.send_crossover_notification(event)

                # 等待下一次轮询
                await asyncio.sleep(Config.MONITOR_INTERVAL)

            except KeyboardInterrupt:
                logger.info("收到停止信号，退出监控...")
                break
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                await asyncio.sleep(Config.MONITOR_INTERVAL)

    async def get_hot_symbols(self, top_n: int = 20) -> List[Dict]:
        """
        获取热门币种（最接近POC关卡的币种）

        Args:
            top_n: 返回数量

        Returns:
            热门币种列表
        """
        all_poc_levels = self.db.get_all_latest_poc_levels()

        hot_symbols = []
        for poc_data in all_poc_levels:
            # 移除数据库的id字段
            poc_dict = {k: v for k, v in poc_data.items() if k != 'id'}
            poc_levels = POCLevels(**poc_dict)

            # 计算到最近POC的距离
            nearest_poc_name, nearest_poc_value = poc_levels.get_nearest_poc()

            if nearest_poc_value:
                distance_percent = abs(
                    poc_levels.current_price - nearest_poc_value
                ) / nearest_poc_value * 100

                hot_symbols.append({
                    "symbol": poc_levels.symbol,
                    "current_price": poc_levels.current_price,
                    "nearest_poc": nearest_poc_name,
                    "nearest_poc_value": nearest_poc_value,
                    "distance_percent": distance_percent,
                    "impact_level": POCCalculator.calculate_impact_level(poc_levels)
                })

        # 按距离排序
        hot_symbols.sort(key=lambda x: x["distance_percent"])

        return hot_symbols[:top_n]
