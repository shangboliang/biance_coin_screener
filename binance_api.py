"""
@author beck
Binance Futures API Client with async support
"""
import asyncio
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import aiohttp
from config import Config

logger = logging.getLogger(__name__)


class BinanceAPIClient:
    """币安永续合约API客户端（异步）"""

    def __init__(self, use_proxy: bool = True):
        """
        初始化币安API客户端

        Args:
            use_proxy: 是否使用代理
        """
        self.base_url = Config.BINANCE_BASE_URL
        self.use_proxy = use_proxy
        self.proxy = Config.PROXY_URL if use_proxy else None
        self.session: Optional[aiohttp.ClientSession] = None
        self.current_weight = 0  # 当前使用的权重
        self.last_weight_reset = datetime.utcnow()  # 上次重置时间

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.create_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close_session()

    async def create_session(self):
        """创建aiohttp会话"""
        timeout = aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)
        connector = aiohttp.TCPConnector(limit=Config.MAX_CONCURRENT_REQUESTS)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector
        )
        logger.info("已创建aiohttp会话")

    async def close_session(self):
        """关闭aiohttp会话"""
        if self.session:
            await self.session.close()
            logger.info("已关闭aiohttp会话")

    async def check_rate_limit(self, estimated_weight: int = 1):
        """
        检查速率限制，如果接近限制则等待

        Args:
            estimated_weight: 预估的请求权重
        """
        # 检查是否需要重置权重计数器（每分钟重置）
        now = datetime.utcnow()
        time_diff = (now - self.last_weight_reset).total_seconds()
        if time_diff >= 60:
            self.current_weight = 0
            self.last_weight_reset = now
            logger.debug("权重计数器已重置")

        # 检查是否接近限制
        safe_limit = int(Config.REQUEST_WEIGHT_LIMIT * Config.RATE_LIMIT_SAFETY_MARGIN)
        if self.current_weight + estimated_weight > safe_limit:
            # 等待到下一分钟
            wait_time = 60 - time_diff
            if wait_time > 0:
                logger.warning(f"接近速率限制 ({self.current_weight}/{Config.REQUEST_WEIGHT_LIMIT})，等待 {wait_time:.1f} 秒...")
                await asyncio.sleep(wait_time)
                self.current_weight = 0
                self.last_weight_reset = datetime.utcnow()

        # 添加请求间延迟
        await asyncio.sleep(Config.REQUEST_DELAY)

    async def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> Optional[Dict]:
        """
        发送HTTP请求到币安API

        Args:
            endpoint: API端点
            params: 请求参数
            retry_count: 重试次数

        Returns:
            API响应数据
        """
        if not self.session:
            await self.create_session()

        # 检查速率限制
        await self.check_rate_limit()

        url = f"{self.base_url}{endpoint}"

        try:
            async with self.session.get(
                url,
                params=params,
                proxy=self.proxy
            ) as response:
                # 记录速率限制信息并更新权重计数器
                used_weight = response.headers.get('X-MBX-USED-WEIGHT-1M')
                if used_weight:
                    self.current_weight = int(used_weight)
                    logger.debug(f"API权重使用: {self.current_weight}/{Config.REQUEST_WEIGHT_LIMIT}")

                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    # 速率限制
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"触发速率限制 (429)，等待 {retry_after} 秒后重试...")
                    if retry_count < Config.MAX_RETRIES:
                        await asyncio.sleep(retry_after)
                        # 重置权重计数器
                        self.current_weight = 0
                        self.last_weight_reset = datetime.utcnow()
                        return await self._make_request(endpoint, params, retry_count + 1)
                    else:
                        logger.error("重试次数已达上限")
                        return None
                elif response.status == 418:
                    # IP被封禁
                    logger.error(f"IP已被封禁 (418)！请等待一段时间后再试。")
                    logger.error("建议: 1) 降低并发数  2) 增加请求间延迟  3) 等待IP解封（2分钟-3天不等）")
                    return None
                else:
                    error_text = await response.text()
                    logger.error(f"API请求失败: {response.status} - {error_text}")
                    return None

        except asyncio.TimeoutError:
            logger.error(f"请求超时: {url}")
            if retry_count < Config.MAX_RETRIES:
                await asyncio.sleep(Config.RETRY_DELAY)
                return await self._make_request(endpoint, params, retry_count + 1)
            return None
        except Exception as e:
            logger.error(f"请求异常: {e}")
            return None

    async def test_connectivity(self) -> bool:
        """
        测试API连接

        Returns:
            连接是否成功
        """
        try:
            result = await self._make_request("/fapi/v1/ping")
            if result is not None:
                logger.info("✓ API连接测试成功")
                return True
            else:
                logger.error("✗ API连接测试失败")
                return False
        except Exception as e:
            logger.error(f"✗ API连接测试异常: {e}")
            return False

    async def get_exchange_info(self) -> Optional[Dict]:
        """
        获取交易所信息

        Returns:
            交易所信息
        """
        return await self._make_request("/fapi/v1/exchangeInfo")

    async def get_all_usdt_perpetual_symbols(self) -> List[str]:
        """
        获取所有USDT永续合约交易对

        Returns:
            交易对列表
        """
        exchange_info = await self.get_exchange_info()
        if not exchange_info:
            logger.error("无法获取交易所信息")
            return []

        symbols = []
        for symbol_info in exchange_info.get("symbols", []):
            # 筛选USDT永续合约且状态为TRADING
            if (symbol_info.get("quoteAsset") == "USDT" and
                symbol_info.get("contractType") == "PERPETUAL" and
                symbol_info.get("status") == "TRADING"):
                symbols.append(symbol_info["symbol"])

        logger.info(f"找到 {len(symbols)} 个USDT永续合约交易对")
        return symbols

    async def get_klines(
        self,
        symbol: str,
        interval: str = Config.KLINE_INTERVAL_1D,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = Config.MAX_KLINES_LIMIT
    ) -> Optional[List[List]]:
        """
        获取K线数据

        Args:
            symbol: 交易对符号
            interval: K线间隔
            start_time: 开始时间戳（毫秒）
            end_time: 结束时间戳（毫秒）
            limit: 返回数量限制

        Returns:
            K线数据列表
        """
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, Config.MAX_KLINES_LIMIT)
        }

        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        klines = await self._make_request("/fapi/v1/klines", params)
        return klines

    async def get_klines_batch(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int
    ) -> List[List]:
        """
        批量获取K线数据（自动处理分页）

        Args:
            symbol: 交易对符号
            interval: K线间隔
            start_time: 开始时间戳（毫秒）
            end_time: 结束时间戳（毫秒）

        Returns:
            完整的K线数据列表
        """
        all_klines = []
        current_start = start_time

        while current_start < end_time:
            klines = await self.get_klines(
                symbol=symbol,
                interval=interval,
                start_time=current_start,
                end_time=end_time,
                limit=Config.MAX_KLINES_LIMIT
            )

            if not klines:
                break

            all_klines.extend(klines)

            # 更新起始时间为最后一条K线的时间 + 1ms
            if len(klines) == Config.MAX_KLINES_LIMIT:
                current_start = klines[-1][0] + 1
            else:
                break

            # 避免请求过快
            await asyncio.sleep(0.1)

        logger.debug(f"{symbol}: 获取到 {len(all_klines)} 条K线数据")
        return all_klines

    async def get_current_price(self, symbol: str) -> Optional[float]:
        """
        获取当前价格

        Args:
            symbol: 交易对符号

        Returns:
            当前价格
        """
        result = await self._make_request(
            "/fapi/v1/ticker/price",
            {"symbol": symbol}
        )
        if result:
            return float(result.get("price", 0))
        return None

    async def get_all_prices(self) -> Dict[str, float]:
        """
        获取所有交易对的当前价格

        Returns:
            交易对价格字典
        """
        result = await self._make_request("/fapi/v1/ticker/price")
        if result:
            return {
                item["symbol"]: float(item["price"])
                for item in result
                if item["symbol"].endswith("USDT")
            }
        return {}

    @staticmethod
    def calculate_time_range(days: int) -> tuple:
        """
        计算时间范围

        Args:
            days: 天数

        Returns:
            (start_time, end_time) 时间戳（毫秒）
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        return (
            int(start_time.timestamp() * 1000),
            int(end_time.timestamp() * 1000)
        )

    @staticmethod
    def get_month_range(months_ago: int = 0) -> tuple:
        """
        获取指定月份的时间范围

        Args:
            months_ago: 几个月前（0=当月, 1=上月, 2=上上月）

        Returns:
            (start_time, end_time) 时间戳（毫秒）
        """
        now = datetime.utcnow()
        year = now.year
        month = now.month

        # 计算目标月份
        target_month = month - months_ago
        target_year = year
        while target_month <= 0:
            target_month += 12
            target_year -= 1

        # 月初
        start_date = datetime(target_year, target_month, 1)

        # 月末
        if target_month == 12:
            end_date = datetime(target_year + 1, 1, 1)
        else:
            end_date = datetime(target_year, target_month + 1, 1)

        # 如果是当月，结束时间为现在
        if months_ago == 0:
            end_date = now

        return (
            int(start_date.timestamp() * 1000),
            int(end_date.timestamp() * 1000)
        )

    @staticmethod
    def get_quarter_range(quarters_ago: int = 0) -> tuple:
        """
        获取指定季度的时间范围

        Args:
            quarters_ago: 几个季度前（0=当季, 1=上季, 2=上上季）

        Returns:
            (start_time, end_time) 时间戳（毫秒）
        """
        now = datetime.utcnow()
        year = now.year
        month = now.month

        # 计算当前季度
        current_quarter = (month - 1) // 3

        # 计算目标季度
        target_quarter = current_quarter - quarters_ago
        target_year = year
        while target_quarter < 0:
            target_quarter += 4
            target_year -= 1

        # 季度开始月份
        start_month = target_quarter * 3 + 1
        start_date = datetime(target_year, start_month, 1)

        # 季度结束月份
        end_month = start_month + 3
        end_year = target_year
        if end_month > 12:
            end_month -= 12
            end_year += 1
        end_date = datetime(end_year, end_month, 1)

        # 如果是当季，结束时间为现在
        if quarters_ago == 0:
            end_date = now

        return (
            int(start_date.timestamp() * 1000),
            int(end_date.timestamp() * 1000)
        )
