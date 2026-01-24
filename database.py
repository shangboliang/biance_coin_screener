"""
@author beck
SQLite Database Manager for POC Monitor
"""
import sqlite3
import logging
import os  # [新增] 用于创建目录
from typing import List, Dict, Optional, Any
from datetime import datetime
from contextlib import contextmanager
from config import Config

logger = logging.getLogger(__name__)


class DatabaseManager:
    """SQLite数据库管理器"""

    def __init__(self, db_path: str = Config.DB_PATH):
        """
        初始化数据库管理器

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path

        # [新增] 自动检测并创建数据库目录
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir)
                logger.info(f"已自动创建数据库目录: {db_dir}")
            except Exception as e:
                logger.error(f"创建数据库目录失败: {e}")

        self.init_database()

    @contextmanager
    def get_connection(self):
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 使结果可以按列名访问
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

            # 创建POC关卡表
            # [修改] 增加了 days_active 字段
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS poc_levels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    current_price REAL NOT NULL,
                    mpoc REAL,
                    pmpoc REAL,
                    ppmpoc REAL,
                    qpoc REAL,
                    pqpoc REAL,
                    ppqpoc REAL,
                    global_poc REAL,
                    days_active INTEGER DEFAULT 9999,
                    timestamp TEXT NOT NULL,
                    UNIQUE(symbol, timestamp)
                )
            """)

            # 创建突破事件表
            # [修改] 增加了 cross_type 字段
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

            # 创建价格历史表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)

            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_poc_levels_symbol
                ON poc_levels(symbol)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_poc_levels_timestamp
                ON poc_levels(timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_crossover_symbol
                ON crossover_events(symbol)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_crossover_timestamp
                ON crossover_events(timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_price_history_symbol
                ON price_history(symbol)
            """)

            conn.commit()
            logger.info("数据库初始化完成")

    def save_poc_levels(self, poc_data: Dict[str, Any]) -> bool:
        """
        保存POC关卡数据
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # [修改] 插入 days_active
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
                    poc_data.get("days_active", 9999), # [新增]
                    poc_data.get("timestamp", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
                ))
                return True
        except Exception as e:
            logger.error(f"保存POC数据失败: {e}")
            return False

    def save_crossover_event(self, event_data: Dict[str, Any]) -> bool:
        """
        保存突破事件
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # [修改] 插入 cross_type
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
                    event_data.get("cross_type", "UP"), # [新增]
                    event_data.get("timestamp", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
                    event_data.get("notified", 0)
                ))
                logger.info(f"保存突破事件: {event_data['symbol']} - {event_data['poc_type']}")
                return True
        except Exception as e:
            logger.error(f"保存突破事件失败: {e}")
            return False

    def save_price(self, symbol: str, price: float) -> bool:
        """保存价格历史"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO price_history (symbol, price, timestamp)
                    VALUES (?, ?, ?)
                """, (
                    symbol,
                    price,
                    datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                ))
                return True
        except Exception as e:
            logger.error(f"保存价格历史失败: {e}")
            return False

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """获取最新价格"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT price FROM price_history
                    WHERE symbol = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (symbol,))
                result = cursor.fetchone()
                return result["price"] if result else None
        except Exception as e:
            logger.error(f"获取最新价格失败: {e}")
            return None

    def get_latest_poc_levels(self, symbol: str) -> Optional[Dict]:
        """获取最新的POC关卡"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM poc_levels
                    WHERE symbol = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (symbol,))
                result = cursor.fetchone()
                return dict(result) if result else None
        except Exception as e:
            logger.error(f"获取POC关卡失败: {e}")
            return None

    def get_all_latest_poc_levels(self) -> List[Dict]:
        """获取所有交易对的最新POC关卡"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM poc_levels p1
                    WHERE timestamp = (
                        SELECT MAX(timestamp) FROM poc_levels p2
                        WHERE p1.symbol = p2.symbol
                    )
                    ORDER BY symbol
                """)
                results = cursor.fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"获取所有POC关卡失败: {e}")
            return []

    def get_crossover_events(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
        notified_only: bool = False
    ) -> List[Dict]:
        """获取突破事件"""
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

    def mark_event_as_notified(self, event_id: int) -> bool:
        """标记事件为已通知"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE crossover_events
                    SET notified = 1
                    WHERE id = ?
                """, (event_id,))
                return True
        except Exception as e:
            logger.error(f"标记事件失败: {e}")
            return False

    def query_by_condition(self, condition: str) -> List[Dict]:
        """根据条件查询POC数据"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = f"""
                    SELECT * FROM poc_levels p1
                    WHERE timestamp = (
                        SELECT MAX(timestamp) FROM poc_levels p2
                        WHERE p1.symbol = p2.symbol
                    )
                    AND ({condition})
                    ORDER BY symbol
                """
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

                # 总交易对数
                cursor.execute("SELECT COUNT(DISTINCT symbol) as count FROM poc_levels")
                stats["total_symbols"] = cursor.fetchone()["count"]

                # 总突破事件数
                cursor.execute("SELECT COUNT(*) as count FROM crossover_events")
                stats["total_events"] = cursor.fetchone()["count"]

                # 今日突破事件数
                cursor.execute("""
                    SELECT COUNT(*) as count FROM crossover_events
                    WHERE DATE(timestamp) = DATE('now')
                """)
                stats["today_events"] = cursor.fetchone()["count"]

                # 未通知事件数
                cursor.execute("""
                    SELECT COUNT(*) as count FROM crossover_events
                    WHERE notified = 0
                """)
                stats["unnotified_events"] = cursor.fetchone()["count"]

                return stats
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}

    def cleanup_old_data(self, days: int = 30):
        """清理旧数据"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # 清理旧的价格历史
                cursor.execute("""
                    DELETE FROM price_history
                    WHERE timestamp < datetime('now', '-' || ? || ' days')
                """, (days,))

                # [优化] 同时清理旧的POC数据
                cursor.execute("""
                    DELETE FROM poc_levels
                    WHERE timestamp < datetime('now', '-' || ? || ' days')
                """, (days,))

                deleted_count = cursor.rowcount
                logger.info(f"清理了 {deleted_count} 条旧记录")

        except Exception as e:
            logger.error(f"清理旧数据失败: {e}")