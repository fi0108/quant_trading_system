"""
历史数据下载脚本

用法：
    python scripts/download_history.py AAPL 2020-01-01 2024-12-31 --resolution daily
"""

import argparse
import sys
from pathlib import Path

from common.logger import log
from data.historical.downloader import HistoricalDataDownloader
from data.ibkr_client import IBKRClient
from strategy.resolution import Resolution


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Download historical data from IBKR")
    parser.add_argument("symbol", help="Stock symbol (e.g., AAPL)")
    parser.add_argument("start_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("end_date", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--resolution", choices=["daily", "minute", "hour"], default="daily", help="Data resolution (default: daily)"
    )
    parser.add_argument(
        "--what-to-show",
        choices=["TRADES", "MIDPOINT", "BID", "ASK"],
        default="TRADES",
        help="What data to show (default: TRADES)",
    )

    args = parser.parse_args()

    # 解析 resolution
    resolution_map = {"daily": Resolution.Daily, "minute": Resolution.Minute, "hour": Resolution.Hour}
    resolution = resolution_map[args.resolution]

    log.info("=" * 80)
    log.info("Historical Data Download")
    log.info("=" * 80)
    log.info(f"Symbol: {args.symbol}")
    log.info(f"Period: {args.start_date} to {args.end_date}")
    log.info(f"Resolution: {args.resolution}")
    log.info("=" * 80)

    # 初始化数据库（使用 Slice 1 的功能）
    log.info("Initializing database...")
    from data.storage.models import create_tables, init_database

    # 直接调用 init_database，它会从配置读取参数
    init_database()
    create_tables()

    # 连接 IBKR
    log.info("Connecting to IBKR...")
    client = IBKRClient()
    if not client.connect():
        log.error("Failed to connect to IBKR")
        return 1

    try:
        # 创建下载器
        downloader = HistoricalDataDownloader(client)

        # 下载数据
        total_bars = downloader.download(
            symbol=args.symbol,
            start_date=args.start_date,
            end_date=args.end_date,
            resolution=resolution,
            what_to_show=args.what_to_show,
        )

        log.info("=" * 80)
        log.info(f"Download completed: {total_bars} bars saved")
        log.info("=" * 80)

        return 0

    except KeyboardInterrupt:
        log.warning("Download interrupted by user")
        return 1

    except Exception as e:
        log.error(f"Download failed: {e}", exc_info=True)
        return 1

    finally:
        client.disconnect()


if __name__ == "__main__":
    sys.exit(main())
