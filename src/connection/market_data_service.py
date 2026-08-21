"""
Real-time Market Data Service

Continuously subscribes to IBKR real-time data and writes to Redis + PostgreSQL.

Features:
- Real-time bar subscription
- Automatic session detection (pre-market, regular, after-hours)
- Sleep during market closed hours
- Data validation and error handling
- Graceful shutdown

Usage:
    # Start service for single symbol
    python src/connection/market_data_service.py --symbols AAPL

    # Start service for multiple symbols
    python src/connection/market_data_service.py --symbols AAPL,TSLA,GOOGL

    # With custom granularity
    python src/connection/market_data_service.py --symbols AAPL --granularity 1min
"""

import sys
import argparse
import asyncio
import signal
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from connection.ibkr_client import IBKRClient
from connection.storage.data_store import DataStore
from connection.storage.postgres_writer import PostgresWriter
from connection.storage.redis_writer import RedisWriter
from connection.market_data.validator import DataValidator
from core.timezone_manager import TimezoneManager
from calendar.trading_calendar import TradingCalendar
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MarketDataService:
    """
    Real-time market data service.

    Continuously subscribes to IBKR data and writes to storage.
    """

    def __init__(
        self,
        symbols: list,
        granularity: str = '1min',
        ibkr_host: str = '127.0.0.1',
        ibkr_port: int = 7497,
        db_url: str = 'postgresql://postgres:postgres@localhost:5432/quant_trading',
        redis_url: str = 'redis://localhost:6379/0'
    ):
        """
        Initialize market data service.

        Args:
            symbols: List of symbols to subscribe
            granularity: Data granularity
            ibkr_host: IBKR host
            ibkr_port: IBKR port
            db_url: PostgreSQL URL
            redis_url: Redis URL
        """
        self.symbols = symbols
        self.granularity = granularity

        # Initialize components
        self.client = IBKRClient(host=ibkr_host, port=ibkr_port)
        self.validator = DataValidator(strict_mode=False)
        self.tz_manager = TimezoneManager()
        self.calendar = TradingCalendar()

        # Initialize storage
        self.pg_writer = PostgresWriter(db_url=db_url, batch_size=100, batch_interval=10)
        self.redis_writer = RedisWriter(redis_url=redis_url, max_bars=100)
        self.data_store = DataStore(self.pg_writer, self.redis_writer)

        self.is_running = False

    async def start(self):
        """Start the service."""
        logger.info("=" * 60)
        logger.info("Market Data Service Starting")
        logger.info("=" * 60)
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Granularity: {self.granularity}")
        logger.info("=" * 60)

        # Connect to storage
        logger.info("Connecting to storage...")
        await self.pg_writer.init_pool()
        await self.pg_writer.start()
        self.redis_writer.connect()

        # Connect to IBKR
        logger.info("Connecting to IBKR...")
        if not self.client.connect():
            logger.error("Failed to connect to IBKR")
            return

        # Subscribe to symbols
        logger.info("Subscribing to real-time data...")
        for symbol in self.symbols:
            # Note: IBKR reqRealTimeBars only supports 5-second bars
            # For minute bars, we would need to aggregate or use different approach
            self.client.subscribe_realtime_bars(
                symbol=symbol,
                bar_size='5 secs',
                callback=self._on_new_bar
            )

        logger.info("Service started successfully")
        self.is_running = True

        # Enter main loop
        await self._main_loop()

    def _on_new_bar(self, symbol: str, bar_data: dict):
        """
        Callback for new bar data.

        Args:
            symbol: Stock symbol
            bar_data: Bar data dictionary
        """
        try:
            # Add session information
            bar_data['session'] = self.tz_manager.get_current_session()

            # Convert timestamp to UTC
            if isinstance(bar_data['timestamp'], str):
                bar_data['timestamp'] = datetime.fromisoformat(bar_data['timestamp'])

            bar_data['timestamp'] = self.tz_manager.to_utc(bar_data['timestamp'], from_tz='America/New_York')

            # Add metadata
            bar_data['source'] = 'realtime'

            # Validate
            is_valid, error, fixed_bar = self.validator.validate(bar_data)

            if not is_valid and not fixed_bar:
                logger.warning(f"[{symbol}] Invalid bar: {error}")
                return

            # Use fixed bar if available
            if fixed_bar:
                bar_data = fixed_bar

            # Save to both Redis and PostgreSQL
            self.data_store.save_bar(
                symbol=symbol,
                bar=bar_data,
                granularity=self.granularity,
                to_redis=True,
                to_pg=True
            )

            logger.info(
                f"[{symbol}] Saved bar: {bar_data['timestamp'].isoformat()} "
                f"close={bar_data['close']:.2f} session={bar_data['session']}"
            )

        except Exception as e:
            logger.error(f"[{symbol}] Error processing bar: {e}", exc_info=True)

    async def _main_loop(self):
        """
        Main service loop.

        Handles trading hours and sleep during closed hours.
        """
        while self.is_running:
            try:
                current_session = self.tz_manager.get_current_session()

                if current_session == 'closed':
                    # Market closed, sleep
                    logger.info("Market closed, sleeping for 5 minutes...")
                    await asyncio.sleep(300)  # 5 minutes
                else:
                    # Market open, keep running
                    logger.debug(f"Market open: {current_session}")
                    await asyncio.sleep(10)  # Check every 10 seconds

            except asyncio.CancelledError:
                logger.info("Main loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(10)

    async def stop(self):
        """Stop the service."""
        logger.info("Stopping market data service...")
        self.is_running = False

        # Disconnect from IBKR
        self.client.disconnect()

        # Flush and close storage
        await self.pg_writer.flush()
        await self.pg_writer.stop()
        await self.pg_writer.close_pool()
        self.redis_writer.disconnect()

        logger.info("Service stopped")

    def get_stats(self) -> dict:
        """Get service statistics."""
        return {
            'symbols': self.symbols,
            'granularity': self.granularity,
            'is_running': self.is_running,
            'current_session': self.tz_manager.get_current_session(),
            'storage': self.data_store.get_stats(),
            'validator': self.validator.get_stats()
        }


async def main():
    parser = argparse.ArgumentParser(
        description='Real-time market data service',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--symbols',
        required=True,
        help='Comma-separated stock symbols (e.g., AAPL,TSLA,GOOGL)'
    )

    parser.add_argument(
        '--granularity',
        default='1min',
        help='Data granularity (default: 1min)'
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

    parser.add_argument(
        '--redis-url',
        default='redis://localhost:6379/0',
        help='Redis connection URL'
    )

    args = parser.parse_args()

    # Parse symbols
    symbols = [s.strip().upper() for s in args.symbols.split(',')]

    # Create service
    service = MarketDataService(
        symbols=symbols,
        granularity=args.granularity,
        ibkr_host=args.ibkr_host,
        ibkr_port=args.ibkr_port,
        db_url=args.db_url,
        redis_url=args.redis_url
    )

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()

    def signal_handler(sig):
        logger.info(f"Received signal {sig}, shutting down...")
        asyncio.create_task(service.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

    # Start service
    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await service.stop()


if __name__ == '__main__':
    # Windows doesn't support add_signal_handler, use simpler approach
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(main())
