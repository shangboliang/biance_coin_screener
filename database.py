"""
@author beck
SQLite Database Manager for POC Monitor
Optimization: Snapshot Mode & WAL enabled
"""
import sqlite3
import logging
import os
from typing import List, Dict, Optional, Any
from datetime import datetime
from contextlib import contextmanager
from config import Config

logger = logging.getLogger(__name__)


class DatabaseManager:
    """SQLite数据库管理器 (高性能版)"""

    def __init__(self, db_path: str = Config.DB_PATH):
        self.db_path = db_path

        # 自动检测并创建数据库目录
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir)
            except Exception as e:
                logger.error(f"创建数据库目录失败: {e}")

        self.init_database()
        self.enable_wal_mode()  # [优化] 开启WAL模式

    def enable_wal_mode(self):
        """开启 Write-Ahead Logging 模式，提升并发读写性能"""
        try:
            with self.get_connection() as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
        except Exception as e:
            logger.error(f"开启WAL模式失败: {e}")

    @contextmanager
    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            conn.close()

    def init_database(self):
        """初始化数据库表结构"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # [优化] POC关卡表：将 symbol 设为 PRIMARY KEY
            # 这样同一个币种只会保留最后一条记录，不会无限膨胀
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS poc_levels (
                    symbol TEXT PRIMARY KEY,
                    current_price REAL NOT NULL,
                    mpoc REAL,
                    pmpoc REAL,
                    ppmpoc REAL,
                    qpoc REAL,
                    pqpoc REAL,
                    ppqpoc REAL,
                    global_poc REAL,
                    days_active INTEGER DEFAULT 9999,
                    timestamp TEXT NOT NULL
                )
            """)

            # [优化] 价格缓存表：同样只存最新价格，不存历史流水
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_cache (
                    symbol TEXT PRIMARY KEY,
                    price REAL NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)

            # 突破事件表 (这是唯一需要保留历史记录的表)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS crossover_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    poc_type TEXT NOT NULL,
                    poc_value REAL NOT NULL,
                    price_before REAL NOT NULL,
                    price_after REAL NOT NULL,
                    change_percent REAL NOT NULL,
                    impact_level INTEGER,
                    impact_emoji TEXT,
                    cross_type TEXT DEFAULT 'UP',
                    timestamp TEXT NOT NULL,
                    notified INTEGER DEFAULT 0
                )
            """)

            # 索引优化 (POC表不需要索引了，因为是主键查询)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_crossover_symbol
                ON crossover_events(symbol)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_crossover_timestamp
                ON crossover_events(timestamp)
            """)

            conn.commit()

    def save_poc_levels(self, poc_data: Dict[str, Any]) -> bool:
        """保存POC关卡数据 (覆盖更新)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # 使用 INSERT OR REPLACE，如果币种存在则直接覆盖
                cursor.execute("""
                    INSERT OR REPLACE INTO poc_levels
                    (symbol, current_price, mpoc, pmpoc, ppmpoc, qpoc, pqpoc, ppqpoc, global_poc, days_active, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    poc_data["symbol"],
                    poc_data["current_price"],
                    poc_data.get("mpoc"),
                    poc_data.get("pmpoc"),
                    poc_data.get("ppmpoc"),
                    poc_data.get("qpoc"),
                    poc_data.get("pqpoc"),
                    poc_data.get("ppqpoc"),
                    poc_data.get("global_poc"),
                    poc_data.get("days_active", 9999),
                    poc_data.get("timestamp", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
                ))
                return True
        except Exception as e:
            logger.error(f"保存POC数据失败: {e}")
            return False

    def save_price(self, symbol: str, price: float) -> bool:
        """保存最新价格 (覆盖更新)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # 不再无限追加，只更新最新价
                cursor.execute("""
                    INSERT OR REPLACE INTO price_cache (symbol, price, timestamp)
                    VALUES (?, ?, ?)
                """, (
                    symbol,
                    price,
                    datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                ))
                return True
        except Exception as e:
            logger.error(f"保存价格失败: {e}")
            return False

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """获取最新价格"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # 直接通过主键查询，速度极快
                cursor.execute("SELECT price FROM price_cache WHERE symbol = ?", (symbol,))
                result = cursor.fetchone()
                return result["price"] if result else None
        except Exception as e:
            logger.error(f"获取最新价格失败: {e}")
            return None

    def get_all_latest_poc_levels(self) -> List[Dict]:
        """
        获取所有交易对的最新POC关卡
        [极大优化] 不再需要复杂的子查询，直接全表扫描即可（因为表中只有最新数据）
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM poc_levels ORDER BY symbol")
                results = cursor.fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"获取所有POC关卡失败: {e}")
            return []

    def get_crossover_events(self, symbol: Optional[str] = None, limit: int = 100, notified_only: bool = False) -> List[Dict]:
        """获取突破事件历史"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM crossover_events WHERE 1=1"
                params = []

                if symbol:
                    query += " AND symbol = ?"
                    params.append(symbol)
                if notified_only:
                    query += " AND notified = 1"

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                results = cursor.fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"获取突破事件失败: {e}")
            return []

    def save_crossover_event(self, event_data: Dict[str, Any]) -> bool:
        """保存突破事件"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO crossover_events
                    (symbol, poc_type, poc_value, price_before, price_after,
                     change_percent, impact_level, impact_emoji, cross_type, timestamp, notified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_data["symbol"],
                    event_data["poc_type"],
                    event_data["poc_value"],
                    event_data["price_before"],
                    event_data["price_after"],
                    event_data["change_percent"],
                    event_data.get("impact_level", 1),
                    event_data.get("impact_emoji", "➡️"),
                    event_data.get("cross_type", "UP"),
                    event_data.get("timestamp", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
                    event_data.get("notified", 0)
                ))
                logger.info(f"保存突破事件: {event_data['symbol']} - {event_data['poc_type']}")
                return True
        except Exception as e:
            logger.error(f"保存突破事件失败: {e}")
            return False

    def query_by_condition(self, condition: str) -> List[Dict]:
        """根据条件查询POC数据 (优化版)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # 简化查询，直接查 poc_levels
                query = f"SELECT * FROM poc_levels WHERE {condition} ORDER BY symbol"
                cursor.execute(query)
                results = cursor.fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"条件查询失败: {e}")
            return []

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                stats = {}

                # 直接Count全表，速度极快
                cursor.execute("SELECT COUNT(*) as count FROM poc_levels")
                stats["total_symbols"] = cursor.fetchone()["count"]

                cursor.execute("SELECT COUNT(*) as count FROM crossover_events")
                stats["total_events"] = cursor.fetchone()["count"]

                cursor.execute("SELECT COUNT(*) as count FROM crossover_events WHERE DATE(timestamp) = DATE('now')")
                stats["today_events"] = cursor.fetchone()["count"]

                cursor.execute("SELECT COUNT(*) as count FROM crossover_events WHERE notified = 0")
                stats["unnotified_events"] = cursor.fetchone()["count"]

                return stats
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}

    def cleanup_old_data(self, days: int = 30):
        """清理旧数据并压缩数据库"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # 只需要清理事件表，POC表和Price表永远不会有旧数据（因为只存最新）
                cursor.execute("""
                    DELETE FROM crossover_events
                    WHERE timestamp < datetime('now', '-' || ? || ' days')
                """, (days,))

                deleted = cursor.rowcount

                # [新增] VACUUM 命令，释放磁盘空间
                if deleted > 0:
                    cursor.execute("VACUUM")
                    logger.info(f"清理了 {deleted} 条历史事件并压缩了数据库")

        except Exception as e:
            logger.error(f"清理旧数据失败: {e}")