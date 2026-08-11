"""
Historical Data Sync Script

Syncs historical market data from IBKR to PostgreSQL for backtesting.

Usage:
    # Sync AAPL for last 6 months (default)
    python scripts/sync_historical_data.py --symbols AAPL

    # Sync specific date range
    python scripts/sync_historical_data.py --symbols AAPL --start-date 2026-01-01 --end-date 2026-06-30

    # Sync multiple symbols with minute granularity
    python scripts/sync_historical_data.py --symbols AAPL,TSLA,GOOGL --granularity minute

    # Sync with all granularities
    python scripts/sync_historical_data.py --symbols AAPL --granularity daily,hour,minute
"""

import sys
import os
import argparse
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.connection.ibkr_client import IBKRClient
from src.connection.market_data.validator import DataValidator
from src.connection.storage.postgres_writer import PostgresWriter
from src.core.timezone_manager import TimezoneManager
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Granularity mapping
GRANULARITY_MAP = {
    'minute': '1 min',
    'hour': '1 hour',
    'daily': '1 day',
    'week': '1 week',
    'month': '1 month'
}

# Granularity to table mapping
TABLE_MAP = {
    'minute': 'market_data_1min',
    'hour': 'market_data_1hour',
    'daily': 'market_data_daily',
    'week': 'market_data_weekly',
    'month': 'market_data_monthly'
}


async def sync_historical_data(
    symbols: list,
    start_date: datetime,
    end_date: datetime,
    granularity: str,
    ibkr_host: str,
    ibkr_port: int,
    db_url: str
):
    """
    Sync historical data from IBKR to PostgreSQL.

    Args:
        symbols: List of stock symbols
        start_date: Start date
        end_date: End date
        granularity: Data granularity
        ibkr_host: IBKR host
        ibkr_port: IBKR port
        db_url: PostgreSQL connection URL
    """
    # Initialize components
    client = IBKRClient(host=ibkr_host, port=ibkr_port)

    # Set appropriate validation based on granularity
    if granularity == 'minute':
        max_gap_minutes = 5
    elif granularity == 'hour':
        max_gap_minutes = 120  # 2 hours
    elif granularity == 'daily':
        max_gap_minutes = 1440 * 5  # 5 days (allowing weekends)
    elif granularity == 'week':
        max_gap_minutes = 1440 * 14  # 2 weeks
    elif granularity == 'month':
        max_gap_minutes = 1440 * 62  # 2 months
    else:
        max_gap_minutes = 1440 * 5

    validator = DataValidator(strict_mode=False, max_bar_gap_minutes=max_gap_minutes)
    tz_manager = TimezoneManager()

    # Initialize PostgreSQL writer with table based on granularity
    table_name = TABLE_MAP.get(granularity, 'market_data_1min')
    pg_writer = PostgresWriter(db_url=db_url, batch_size=100, batch_interval=10, table_name=table_name)
    await pg_writer.init_pool()
    await pg_writer.start()

    # Connect to IBKR
    logger.info(f"Connecting to IBKR at {ibkr_host}:{ibkr_port}...")
    if not await client.connect_async():
        logger.error("Failed to connect to IBKR")
        return

    try:
        bar_size = GRANULARITY_MAP.get(granularity, '1 day')

        for symbol in symbols:
            logger.info(f"Syncing {symbol} ({granularity}) from {start_date.date()} to {end_date.date()}...")

            # Get historical bars
            bars = await client.get_historical_bars(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                bar_size=bar_size
            )

            if not bars:
                logger.warning(f"[{symbol}] No data received")
                continue

            # Validate and save bars
            valid_bars = []
            import pytz
            eastern = pytz.timezone('America/New_York')

            for bar in bars:
                # Process timestamp - store as Eastern Time (naive datetime)
                if isinstance(bar['timestamp'], str):
                    # Parse ISO format string
                    bar['timestamp'] = datetime.fromisoformat(bar['timestamp'])
                elif hasattr(bar['timestamp'], 'date') and not hasattr(bar['timestamp'], 'hour'):
                    # It's a date object, convert to datetime at market open (09:30 ET for intraday, 00:00 for daily)
                    if granularity == 'daily':
                        # For daily data, use midnight Eastern Time
                        bar['timestamp'] = datetime.combine(bar['timestamp'], datetime.min.time())
                    else:
                        # For intraday data, the timestamp from IBKR is already correct
                        bar['timestamp'] = datetime.combine(bar['timestamp'], datetime.min.time())

                # Remove timezone info - store as naive Eastern Time
                if hasattr(bar['timestamp'], 'tzinfo') and bar['timestamp'].tzinfo is not None:
                    # Convert to Eastern Time first, then remove timezone
                    bar['timestamp'] = bar['timestamp'].astimezone(eastern)
                    bar['timestamp'] = bar['timestamp'].replace(tzinfo=None)

                # Add metadata
                bar['source'] = 'historical'

                # Validate
                is_valid, error, fixed_bar = validator.validate(bar)

                if is_valid:
                    valid_bars.append(bar)
                elif fixed_bar:
                    # Non-strict mode returned fixed data
                    valid_bars.append(fixed_bar)
                else:
                    logger.warning(f"[{symbol}] Invalid bar: {error}")

            # Write to PostgreSQL
            if valid_bars:
                for bar in valid_bars:
                    pg_writer.add_bar(bar)

                logger.info(f"[{symbol}] Queued {len(valid_bars)}/{len(bars)} bars to database")
            else:
                logger.warning(f"[{symbol}] No valid bars to save")

        # Flush remaining data
        logger.info("Flushing remaining data to database...")
        await pg_writer.flush()

        # Show statistics
        stats = pg_writer.get_stats()
        logger.info(f"Sync complete: {stats['writes_success']} bars saved, {stats['writes_failed']} failed")

    finally:
        # Cleanup
        client.disconnect()
        await pg_writer.stop()
        await pg_writer.close_pool()


def main():
    parser = argparse.ArgumentParser(
        description='Sync historical market data from IBKR to PostgreSQL',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--symbols',
        required=True,
        help='Comma-separated stock symbols (e.g., AAPL,TSLA,GOOGL)'
    )

    parser.add_argument(
        '--start-date',
        help='Start date in YYYY-MM-DD format (default: 6 months ago)'
    )

    parser.add_argument(
        '--end-date',
        help='End date in YYYY-MM-DD format (default: today)'
    )

    parser.add_argument(
        '--granularity',
        default='daily',
        choices=['minute', 'hour', 'daily', 'week', 'month'],
        help='Data granularity (default: daily)'
    )

    parser.add_argument(
        '--ibkr-host',
        default='127.0.0.1',
        help='IBKR Gateway/TWS host (default: 127.0.0.1)'
    )

    parser.add_argument(
        '--ibkr-port',
        type=int,
        default=4002,
        help='IBKR Gateway/TWS port (default: 4002)'
    )

    parser.add_argument(
        '--db-url',
        default='postgresql://postgres:postgres@localhost:5432/quant_trading',
        help='PostgreSQL connection URL'
    )

    args = parser.parse_args()

    # Parse symbols
    symbols = [s.strip().upper() for s in args.symbols.split(',')]

    # Parse dates (interpret as US Eastern Time)
    import pytz
    eastern = pytz.timezone('America/New_York')

    if args.start_date:
        # Parse as naive datetime, then localize to Eastern Time
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        start_date = eastern.localize(start_date)
    else:
        # Default: 6 months ago in Eastern Time
        start_date = datetime.now(eastern) - timedelta(days=180)

    if args.end_date:
        # Parse as naive datetime, then localize to Eastern Time
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
        end_date = eastern.localize(end_date.replace(hour=23, minute=59, second=59))
    else:
        # Default: today in Eastern Time
        end_date = datetime.now(eastern)

    # Show summary
    logger.info("=" * 60)
    logger.info("Historical Data Sync")
    logger.info("=" * 60)
    logger.info(f"Symbols: {', '.join(symbols)}")
    logger.info(f"Date Range: {start_date.date()} to {end_date.date()}")
    logger.info(f"Granularity: {args.granularity}")
    logger.info(f"IBKR: {args.ibkr_host}:{args.ibkr_port}")
    logger.info(f"Database: {args.db_url.split('@')[-1]}")  # Hide password
    logger.info("=" * 60)

    # Run sync
    asyncio.run(sync_historical_data(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        granularity=args.granularity,
        ibkr_host=args.ibkr_host,
        ibkr_port=args.ibkr_port,
        db_url=args.db_url
    ))


if __name__ == '__main__':
    main()
