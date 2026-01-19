"""
@author beck
Binance POC Monitor - Main Entry Point
币安永续合约POC监控工具
"""
import asyncio
import logging
import argparse
import sys
from datetime import datetime

from config import Config
from monitor import POCMonitor
from binance_api import BinanceAPIClient
from telegram_notifier import TelegramNotifier
from database import DatabaseManager

# 配置日志
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format=Config.LOG_FORMAT,
    handlers=[
        logging.FileHandler(Config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def print_banner():
    """打印启动横幅"""
    banner = """
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║        币安永续合约 POC 监控工具                          ║
    ║        Binance Futures POC Monitor                        ║
    ║                                                           ║
    ║        @author beck                                       ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)


async def test_api_connection():
    """测试API连接"""
    print("\n" + "="*60)
    print("测试币安API连接...")
    print(f"币安API代理: {'启用' if Config.BINANCE_USE_PROXY else '禁用'}")
    print("="*60)

    async with BinanceAPIClient(use_proxy=Config.BINANCE_USE_PROXY) as client:
        # 测试连接
        if await client.test_connectivity():
            logger.info("✓ 币安API连接成功")

            # 获取交易所信息
            exchange_info = await client.get_exchange_info()
            if exchange_info:
                server_time = datetime.fromtimestamp(
                    exchange_info.get("serverTime", 0) / 1000
                )
                logger.info(f"✓ 服务器时间: {server_time}")

            # 获取USDT永续合约数量
            symbols = await client.get_all_usdt_perpetual_symbols()
            logger.info(f"✓ 找到 {len(symbols)} 个USDT永续合约")

            return True
        else:
            logger.error("✗ 币安API连接失败")
            return False


async def test_telegram():
    """测试Telegram连接"""
    print("\n" + "="*60)
    print("测试Telegram连接...")
    print(f"Telegram代理: {'启用' if Config.TELEGRAM_USE_PROXY else '禁用'}")
    print("="*60)

    if not Config.TELEGRAM_BOT_TOKEN or not Config.TELEGRAM_CHAT_ID:
        logger.warning("⚠️ Telegram未配置，跳过测试")
        return False

    telegram = TelegramNotifier()
    result = await telegram.test_connection()

    return result


async def run_monitor_once():
    """运行一次监控"""
    print("\n" + "="*60)
    print("运行POC监控（单次）...")
    print(f"币安API代理: {'启用' if Config.BINANCE_USE_PROXY else '禁用'}")
    print("="*60)

    monitor = POCMonitor(use_proxy=Config.BINANCE_USE_PROXY)
    await monitor.initialize()

    try:
        stats = await monitor.monitor_once()

        print("\n监控完成!")
        print(f"  - 监控交易对: {stats['total_symbols']}")
        print(f"  - 穿透事件: {stats['total_events']}")
        print(f"  - 时间: {stats['timestamp']}")

        if stats['total_events'] > 0:
            print("\n穿透事件详情:")
            for event in stats['crossover_events']:
                print(f"  {event['impact_emoji']} {event['symbol']} - "
                      f"{event['poc_type']} @ ${event['poc_value']:.6f} "
                      f"({event['change_percent']:+.2f}%)")

    finally:
        await monitor.cleanup()


async def run_monitor_loop():
    """运行持续监控"""
    print("\n" + "="*60)
    print("启动持续监控模式...")
    print(f"币安API代理: {'启用' if Config.BINANCE_USE_PROXY else '禁用'}")
    print(f"轮询间隔: {Config.MONITOR_INTERVAL}秒")
    print("按 Ctrl+C 停止")
    print("="*60)

    monitor = POCMonitor(use_proxy=Config.BINANCE_USE_PROXY)
    await monitor.initialize()

    try:
        await monitor.monitor_loop()
    except KeyboardInterrupt:
        print("\n\n收到停止信号...")
    finally:
        await monitor.cleanup()


async def calculate_all_pocs():
    """计算所有交易对的POC"""
    print("\n" + "="*60)
    print("计算所有交易对的POC...")
    print(f"币安API代理: {'启用' if Config.BINANCE_USE_PROXY else '禁用'}")
    print("="*60)

    monitor = POCMonitor(use_proxy=Config.BINANCE_USE_PROXY)
    await monitor.initialize()

    try:
        poc_levels_list = await monitor.calculate_all_pocs()

        # 保存到数据库
        db = DatabaseManager()
        for poc_levels in poc_levels_list:
            db.save_poc_levels(poc_levels.to_dict())

        print(f"\n✓ 成功计算并保存 {len(poc_levels_list)} 个交易对的POC数据")

    finally:
        await monitor.cleanup()


def show_database_stats():
    """显示数据库统计"""
    print("\n" + "="*60)
    print("数据库统计信息")
    print("="*60)

    db = DatabaseManager()
    stats = db.get_statistics()

    print(f"\n监控交易对数: {stats.get('total_symbols', 0)}")
    print(f"总穿透事件数: {stats.get('total_events', 0)}")
    print(f"今日事件数: {stats.get('today_events', 0)}")
    print(f"未通知事件数: {stats.get('unnotified_events', 0)}")

    # 显示最近的穿透事件
    print("\n最近10个穿透事件:")
    events = db.get_crossover_events(limit=10)
    if events:
        for i, event in enumerate(events, 1):
            print(f"{i}. {event['impact_emoji']} {event['symbol']} - "
                  f"{event['poc_type']} @ ${event['poc_value']:.6f} "
                  f"({event['change_percent']:+.2f}%) - {event['timestamp']}")
    else:
        print("  暂无事件")


def main():
    """主函数"""
    print_banner()

    parser = argparse.ArgumentParser(description="币安POC监控工具")
    parser.add_argument(
        "command",
        choices=["test", "calc", "monitor", "loop", "stats", "web"],
        help="命令: test=测试连接, calc=计算POC, monitor=单次监控, loop=持续监控, stats=查看统计, web=启动Web界面"
    )

    args = parser.parse_args()

    try:
        if args.command == "test":
            # 测试连接
            asyncio.run(test_api_connection())
            asyncio.run(test_telegram())

        elif args.command == "calc":
            # 计算POC
            asyncio.run(calculate_all_pocs())

        elif args.command == "monitor":
            # 单次监控
            asyncio.run(run_monitor_once())

        elif args.command == "loop":
            # 持续监控
            asyncio.run(run_monitor_loop())

        elif args.command == "stats":
            # 显示统计
            show_database_stats()

        elif args.command == "web":
            # 启动Streamlit
            import os
            os.system("streamlit run streamlit_app.py")

    except KeyboardInterrupt:
        print("\n\n程序已停止")
    except Exception as e:
        logger.error(f"程序异常: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
