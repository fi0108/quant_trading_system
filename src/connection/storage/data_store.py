"""
DataStore - Unified interface for PostgreSQL and Redis storage.

Provides simplified interface for:
- Batch saving bars to PostgreSQL
- Single bar saving to Redis cache
- Automatic granularity-based table routing
"""

from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class DataStore:
    """
    Unified data storage interface.

    Routes data to appropriate storage:
    - PostgreSQL: all data, persistent
    - Redis: latest 100 bars, fast access
    """

    # Granularity to table name mapping
    TABLE_MAP = {
        '1min': 'market_data_1min',
        'minute': 'market_data_1min',
        '1hour': 'market_data_1hour',
        'hour': 'market_data_1hour',
        'daily': 'market_data_daily',
        'day': 'market_data_daily',
        'weekly': 'market_data_weekly',
        'week': 'market_data_weekly',
        'monthly': 'market_data_monthly',
        'month': 'market_data_monthly'
    }

    def __init__(self, postgres_writer, redis_writer):
        """
        Initialize DataStore.

        Args:
            postgres_writer: PostgresWriter instance
            redis_writer: RedisWriter instance
        """
        self.pg = postgres_writer
        self.redis = redis_writer

    def save_bars_to_pg(
        self,
        symbol: str,
        bars: List[Dict],
        granularity: str = '1min'
    ) -> bool:
        """
        Save bars to PostgreSQL.

        Args:
            symbol: Stock symbol
            bars: List of bar dictionaries
            granularity: Data granularity ('1min', '1hour', 'daily', 'weekly', 'monthly')

        Returns:
            True if save successful
        """
        if not bars:
            logger.warning(f"[{symbol}] No bars to save")
            return True

        # Add symbol to each bar if not present
        for bar in bars:
            if 'symbol' not in bar:
                bar['symbol'] = symbol

        # Route to PostgreSQL writer
        for bar in bars:
            self.pg.add_bar(bar)

        logger.info(f"[{symbol}] Queued {len(bars)} bars to PostgreSQL ({granularity})")
        return True

    def save_bar_to_redis(
        self,
        symbol: str,
        bar: Dict,
        granularity: str = '1min',
        max_size: int = 100
    ) -> bool:
        """
        Save bar to Redis (latest N bars).

        Args:
            symbol: Stock symbol
            bar: Bar dictionary
            granularity: Data granularity
            max_size: Maximum bars to keep in Redis

        Returns:
            True if save successful
        """
        if 'symbol' not in bar:
            bar['symbol'] = symbol

        success = self.redis.write_bar(symbol, bar)

        if success:
            logger.debug(f"[{symbol}] Saved bar to Redis ({granularity})")
        else:
            logger.warning(f"[{symbol}] Failed to save bar to Redis")

        return success

    def save_bar(
        self,
        symbol: str,
        bar: Dict,
        granularity: str = '1min',
        to_redis: bool = True,
        to_pg: bool = True
    ) -> bool:
        """
        Save bar to both PostgreSQL and Redis.

        Args:
            symbol: Stock symbol
            bar: Bar dictionary
            granularity: Data granularity
            to_redis: Save to Redis
            to_pg: Save to PostgreSQL

        Returns:
            True if at least one save successful
        """
        redis_success = True
        pg_success = True

        if to_redis:
            redis_success = self.save_bar_to_redis(symbol, bar, granularity)

        if to_pg:
            pg_success = self.save_bars_to_pg(symbol, [bar], granularity)

        return redis_success or pg_success

    def get_table_name(self, granularity: str) -> str:
        """
        Get table name for granularity.

        Args:
            granularity: Data granularity

        Returns:
            Table name
        """
        return self.TABLE_MAP.get(granularity, 'market_data_1min')

    def is_connected(self) -> Dict[str, bool]:
        """
        Check connection status.

        Returns:
            Dictionary with connection status for each store
        """
        return {
            'postgresql': self.pg.is_connected(),
            'redis': self.redis.is_connected()
        }

    def get_stats(self) -> Dict:
        """
        Get statistics from both stores.

        Returns:
            Combined statistics
        """
        return {
            'postgresql': self.pg.get_stats(),
            'redis': self.redis.get_stats()
        }
