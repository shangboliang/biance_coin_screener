"""
@author beck
POC (Point of Control) Calculator based on VWAP
"""
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class POCLevels:
    """POC关卡数据类"""
    symbol: str
    current_price: float

    # 月度POC
    mpoc: Optional[float] = None  # 当月POC
    pmpoc: Optional[float] = None  # 上月POC
    ppmpoc: Optional[float] = None  # 上上月POC

    # 季度POC
    qpoc: Optional[float] = None  # 当季POC
    pqpoc: Optional[float] = None  # 上季POC
    ppqpoc: Optional[float] = None  # 上上季POC

    # 全局POC（用于填充缺失数据）
    global_poc: Optional[float] = None

    # [关键] 默认值设为 9999 (代表老币)，防止误报
    days_active: int = 9999

    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "symbol": self.symbol,
            "current_price": self.current_price,
            "mpoc": self.mpoc,
            "pmpoc": self.pmpoc,
            "ppmpoc": self.ppmpoc,
            "qpoc": self.qpoc,
            "pqpoc": self.pqpoc,
            "ppqpoc": self.ppqpoc,
            "global_poc": self.global_poc,
            "days_active": self.days_active, # [关键] 确保写入字典
            "timestamp": self.timestamp
        }

    def get_poc_value(self, poc_type: str) -> Optional[float]:
        """获取指定类型的POC值"""
        poc_map = {
            "MPOC": self.mpoc,
            "PMPOC": self.pmpoc,
            "PPMPOC": self.ppmpoc,
            "QPOC": self.qpoc,
            "PQPOC": self.pqpoc,
            "PPQPOC": self.ppqpoc,
            "GLOBAL_POC": self.global_poc
        }
        return poc_map.get(poc_type.upper())

    def count_breakthroughs(self) -> int:
        """计算当前价格突破了多少个POC关卡"""
        count = 0
        poc_values = [
            self.mpoc, self.pmpoc, self.ppmpoc,
            self.qpoc, self.pqpoc, self.ppqpoc
        ]
        for poc_value in poc_values:
            if poc_value and self.current_price > poc_value:
                count += 1
        return count

    def get_nearest_poc(self) -> Tuple[str, Optional[float]]:
        """获取最接近当前价格的POC关卡"""
        poc_dict = {
            "MPOC": self.mpoc,
            "PMPOC": self.pmpoc,
            "PPMPOC": self.ppmpoc,
            "QPOC": self.qpoc,
            "PQPOC": self.pqpoc,
            "PPQPOC": self.ppqpoc
        }

        min_distance = float('inf')
        nearest_name = ""
        nearest_value = None

        for name, value in poc_dict.items():
            if value:
                distance = abs(self.current_price - value)
                if distance < min_distance:
                    min_distance = distance
                    nearest_name = name
                    nearest_value = value

        return nearest_name, nearest_value


class POCCalculator:
    """POC计算器"""

    @staticmethod
    def calculate_tp(high: float, low: float, close: float) -> float:
        """计算典型价格 (Typical Price)"""
        return (high + low + close) / 3.0

    @staticmethod
    def calculate_vwap(klines: List[List]) -> Optional[float]:
        """计算基于典型价格的VWAP"""
        if not klines:
            return None

        total_tp_volume = 0.0
        total_volume = 0.0

        for kline in klines:
            try:
                # open_time = kline[0]
                # open_price = float(kline[1])
                high = float(kline[2])
                low = float(kline[3])
                close = float(kline[4])
                volume = float(kline[5])

                # 跳过无效数据
                if volume == 0:
                    continue

                # 计算典型价格
                tp = POCCalculator.calculate_tp(high, low, close)

                # 累加
                total_tp_volume += tp * volume
                total_volume += volume

            except (IndexError, ValueError, TypeError) as e:
                # logger.warning(f"跳过无效K线数据: {e}")
                continue

        if total_volume == 0:
            return None

        return total_tp_volume / total_volume

    @staticmethod
    def calculate_all_pocs(
        current_month_klines: List[List],
        prev_month_klines: List[List],
        prev_prev_month_klines: List[List],
        current_quarter_klines: List[List],
        prev_quarter_klines: List[List],
        prev_prev_quarter_klines: List[List],
        global_klines: List[List]
    ) -> Dict[str, any]:
        """
        计算所有POC关卡 (包含上市天数)
        """
        # ==================== 1. 计算上市天数 ====================
        days_active = 9999
        if global_klines and len(global_klines) > 0:
            try:
                # global_klines[0][0] 是第一根K线的开盘时间戳 (毫秒)
                listing_timestamp = global_klines[0][0]
                current_timestamp = datetime.utcnow().timestamp() * 1000

                # 毫秒 -> 天
                days_diff = (current_timestamp - listing_timestamp) / (1000 * 60 * 60 * 24)
                days_active = int(days_diff)
            except Exception as e:
                logger.error(f"计算上市天数失败: {e}")
                days_active = 9999

        # ==================== 2. 计算POC ====================
        global_poc = POCCalculator.calculate_vwap(global_klines)

        pocs = {
            "mpoc": POCCalculator.calculate_vwap(current_month_klines),
            "pmpoc": POCCalculator.calculate_vwap(prev_month_klines),
            "ppmpoc": POCCalculator.calculate_vwap(prev_prev_month_klines),
            "qpoc": POCCalculator.calculate_vwap(current_quarter_klines),
            "pqpoc": POCCalculator.calculate_vwap(prev_quarter_klines),
            "ppqpoc": POCCalculator.calculate_vwap(prev_prev_quarter_klines),
            "global_poc": global_poc,
            "days_active": days_active  # [关键] 必须要把算出来的天数放进去！
        }

        # 注意：这里已经删除了 "如果为None则填充global_poc" 的逻辑
        # 保持 None 状态，以便前端识别新币没有历史数据

        return pocs

    @staticmethod
    def calculate_impact_level(poc_levels: POCLevels) -> Dict[str, any]:
        """计算冲击力等级"""
        from config import Config

        breakthrough_count = poc_levels.count_breakthroughs()

        if breakthrough_count in Config.IMPACT_LEVELS:
            level_info = Config.IMPACT_LEVELS[breakthrough_count]
        else:
            level_info = Config.IMPACT_LEVELS.get(1, {"emoji": "➡️", "label": "微弱冲击", "color": "#87CEEB"})

        return {
            "count": breakthrough_count,
            "emoji": level_info["emoji"],
            "label": level_info["label"],
            "color": level_info["color"]
        }

    # 兼容性方法 (保留)
    @staticmethod
    def check_crossover_type(prev_price: float, current_price: float, poc_value: float) -> Optional[str]:
        if prev_price < poc_value <= current_price:
            return "UP"
        if prev_price > poc_value >= current_price:
            return "DOWN"
        return None