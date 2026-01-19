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
        """
        计算典型价格 (Typical Price)
        TP = (H + L + C) / 3

        Args:
            high: 最高价
            low: 最低价
            close: 收盘价

        Returns:
            典型价格
        """
        return (high + low + close) / 3.0

    @staticmethod
    def calculate_vwap(klines: List[List]) -> Optional[float]:
        """
        计算基于典型价格的VWAP
        VWAP = Σ(TP × Volume) / Σ(Volume)

        Args:
            klines: K线数据列表
                每条K线格式: [开盘时间, 开盘价, 最高价, 最低价, 收盘价, 成交量, ...]

        Returns:
            VWAP值
        """
        if not klines:
            return None

        total_tp_volume = 0.0
        total_volume = 0.0

        for kline in klines:
            try:
                # 解析K线数据
                # open_time = kline[0]
                open_price = float(kline[1])
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
                logger.warning(f"跳过无效K线数据: {e}")
                continue

        if total_volume == 0:
            return None

        vwap = total_tp_volume / total_volume
        return vwap

    @staticmethod
    def calculate_poc_for_period(klines: List[List]) -> Optional[float]:
        """
        计算指定周期的POC（等同于VWAP终点值）

        Args:
            klines: K线数据列表

        Returns:
            POC值
        """
        return POCCalculator.calculate_vwap(klines)

    @staticmethod
    def get_last_vwap_value(klines: List[List]) -> Optional[float]:
        """
        获取周期结束时的VWAP终点值
        这个值作为历史周期的POC

        Args:
            klines: K线数据列表

        Returns:
            VWAP终点值
        """
        return POCCalculator.calculate_vwap(klines)

    @staticmethod
    def calculate_all_pocs(
        current_month_klines: List[List],
        prev_month_klines: List[List],
        prev_prev_month_klines: List[List],
        current_quarter_klines: List[List],
        prev_quarter_klines: List[List],
        prev_prev_quarter_klines: List[List],
        global_klines: List[List]
    ) -> Dict[str, Optional[float]]:
        """
        计算所有POC关卡

        Args:
            current_month_klines: 当月K线
            prev_month_klines: 上月K线
            prev_prev_month_klines: 上上月K线
            current_quarter_klines: 当季K线
            prev_quarter_klines: 上季K线
            prev_prev_quarter_klines: 上上季K线
            global_klines: 全局K线（开盘至今）

        Returns:
            POC字典
        """
        # 计算全局POC（用于填充缺失值）
        global_poc = POCCalculator.calculate_vwap(global_klines)

        # 计算各周期POC
        pocs = {
            "mpoc": POCCalculator.calculate_vwap(current_month_klines),
            "pmpoc": POCCalculator.calculate_vwap(prev_month_klines),
            "ppmpoc": POCCalculator.calculate_vwap(prev_prev_month_klines),
            "qpoc": POCCalculator.calculate_vwap(current_quarter_klines),
            "pqpoc": POCCalculator.calculate_vwap(prev_quarter_klines),
            "ppqpoc": POCCalculator.calculate_vwap(prev_prev_quarter_klines),
            "global_poc": global_poc
        }

        # 用全局POC填充缺失值
        for key in ["mpoc", "pmpoc", "ppmpoc", "qpoc", "pqpoc", "ppqpoc"]:
            if pocs[key] is None:
                pocs[key] = global_poc
                logger.debug(f"{key} 缺失，使用全局POC填充: {global_poc}")

        return pocs

    @staticmethod
    def check_price_proximity(price: float, poc_value: float, threshold: float = 0.01) -> bool:
        """
        检查价格是否接近POC关卡

        Args:
            price: 当前价格
            poc_value: POC值
            threshold: 阈值百分比（默认1%）

        Returns:
            是否接近
        """
        if poc_value == 0:
            return False

        diff_percent = abs(price - poc_value) / poc_value
        return diff_percent <= threshold

    @staticmethod
    def check_crossover(prev_price: float, current_price: float, poc_value: float) -> bool:
        """
        检查是否发生向上穿透

        Args:
            prev_price: 上一次价格
            current_price: 当前价格
            poc_value: POC值

        Returns:
            是否发生向上穿透
        """
        # 之前在下方，现在在上方
        return prev_price < poc_value <= current_price

    @staticmethod
    def calculate_impact_level(poc_levels: POCLevels) -> Dict[str, any]:
        """
        计算冲击力等级

        Args:
            poc_levels: POC关卡数据

        Returns:
            冲击力等级信息
        """
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
