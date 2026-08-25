"""
历史数据查询器

从数据库查询历史数据
"""

from typing import List, Optional
from datetime import datetime
import pandas as pd

from common.logger import log
from data.storage.models import BarModel
from strategy.resolution import Resolution


class HistoricalDataProvider:
    """
    历史数据提供器

    功能：
    - 从数据库查询历史数据
    - 转换为 DataFrame
    - 数据缓存
    """

    def __init__(self):
        """初始化"""
        self._cache = {}

    def get_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        resolution: Resolution = Resolution.Daily
    ) -> pd.DataFrame:
        """
        获取历史数据

        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            resolution: 时间周期

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        log.info(f"Querying history: {symbol} {resolution} {start_date} to {end_date}")

        # 检查缓存
        cache_key = f"{symbol}_{resolution.value}_{start_date}_{end_date}"
        if cache_key in self._cache:
            log.debug(f"Cache hit: {cache_key}")
            return self._cache[cache_key]

        # 查询数据库
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        query = (
            BarModel
            .select()
            .where(
                (BarModel.symbol == symbol) &
                (BarModel.bar_size == resolution.bar_size) &  # 使用 bar_size
                (BarModel.timestamp >= start_dt) &
                (BarModel.timestamp <= end_dt)
            )
            .order_by(BarModel.timestamp)
        )

        # 转换为 DataFrame
        bars = list(query)

        if not bars:
            log.warning(f"No data found for {symbol} {resolution}")
            return pd.DataFrame()

        df = pd.DataFrame([
            {
                'timestamp': bar.timestamp,
                'open': float(bar.open),
                'high': float(bar.high),
                'low': float(bar.low),
                'close': float(bar.close),
                'volume': int(bar.volume)
            }
            for bar in bars
        ])

        # 设置索引
        df.set_index('timestamp', inplace=True)

        # 缓存
        self._cache[cache_key] = df

        log.info(f"Retrieved {len(df)} bars")

        return df

    def get_latest_bars(
        self,
        symbol: str,
        count: int,
        resolution: Resolution = Resolution.Daily
    ) -> pd.DataFrame:
        """
        获取最新的 N 根 bar

        Args:
            symbol: 股票代码
            count: 数量
            resolution: 时间周期

        Returns:
            DataFrame
        """
        query = (
            BarModel
            .select()
            .where(
                (BarModel.symbol == symbol) &
                (BarModel.bar_size == resolution.bar_size)  # 使用 bar_size
            )
            .order_by(BarModel.timestamp.desc())
            .limit(count)
        )

        bars = list(query)

        if not bars:
            return pd.DataFrame()

        # 反转顺序（从旧到新）
        bars.reverse()

        df = pd.DataFrame([
            {
                'timestamp': bar.timestamp,
                'open': float(bar.open),
                'high': float(bar.high),
                'low': float(bar.low),
                'close': float(bar.close),
                'volume': int(bar.volume)
            }
            for bar in bars
        ])

        df.set_index('timestamp', inplace=True)

        return df

    def get_bar_count(
        self,
        symbol: str,
        resolution: Resolution = Resolution.Daily
    ) -> int:
        """
        获取数据条数

        Args:
            symbol: 股票代码
            resolution: 时间周期

        Returns:
            Bar 数量
        """
        count = (
            BarModel
            .select()
            .where(
                (BarModel.symbol == symbol) &
                (BarModel.bar_size == resolution.bar_size)  # 使用 bar_size
            )
            .count()
        )

        return count

    def get_available_symbols(self, resolution: Resolution = Resolution.Daily) -> List[str]:
        """
        获取可用的股票列表

        Args:
            resolution: 时间周期

        Returns:
            股票代码列表
        """
        query = (
            BarModel
            .select(BarModel.symbol)
            .where(BarModel.bar_size == resolution.bar_size)  # 使用 bar_size
            .distinct()
        )

        symbols = [row.symbol for row in query]

        return symbols

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        log.info("Cache cleared")
