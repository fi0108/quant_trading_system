"""
Trading Calendar Manager - Manage trading days and market sessions.

Provides:
- Trading day identification (vs calendar days)
- Holiday detection
- Market hours validation
- Calendar data caching
"""

from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import pandas as pd
import pandas_market_calendars as mcal


class TradingCalendar:
    """
    Manages trading calendar for market operations.

    Uses pandas_market_calendars for accurate holiday and trading day data.
    Caches calendar data to minimize API calls.
    """

    def __init__(self, market: str = "NYSE", cache_days_ahead: int = 30, cache_days_back: int = 365):
        """
        Initialize trading calendar.

        Args:
            market: Market identifier (NYSE, NASDAQ, etc.)
            cache_days_ahead: Days to preload ahead
            cache_days_back: Days to preload back
        """
        self.market = market
        self.calendar = mcal.get_calendar(market)
        self.cache_days_ahead = cache_days_ahead
        self.cache_days_back = cache_days_back

        # Preload calendar data
        self._preload_calendar()

    def _preload_calendar(self):
        """Preload calendar data for faster lookups."""
        end_date = datetime.now() + timedelta(days=self.cache_days_ahead)
        start_date = datetime.now() - timedelta(days=self.cache_days_back)

        # Fetch valid trading days
        self._schedule = self.calendar.schedule(
            start_date=start_date.strftime("%Y-%m-%d"), end_date=end_date.strftime("%Y-%m-%d")
        )

    @lru_cache(maxsize=1024)
    def is_trading_day(self, date: date) -> bool:
        """
        Check if given date is a trading day.

        Args:
            date: Date to check

        Returns:
            True if trading day, False if weekend/holiday
        """
        date_str = date.strftime("%Y-%m-%d")
        return date_str in self._schedule.index.strftime("%Y-%m-%d")

    def get_trading_days(self, start_date: date, end_date: date) -> List[date]:
        """
        Get list of trading days in date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of trading days
        """
        if start_date > end_date:
            return []

        schedule = self.calendar.schedule(
            start_date=start_date.strftime("%Y-%m-%d"), end_date=end_date.strftime("%Y-%m-%d")
        )

        return [datetime.strptime(d, "%Y-%m-%d").date() for d in schedule.index.strftime("%Y-%m-%d")]

    def next_trading_day(self, date: Optional[date] = None) -> date:
        """
        Get next trading day after given date.

        Args:
            date: Reference date (default: today)

        Returns:
            Next trading day
        """
        if date is None:
            date = datetime.now().date()

        current = date + timedelta(days=1)

        # Search up to 10 days ahead (handles long weekends)
        for _ in range(10):
            if self.is_trading_day(current):
                return current
            current += timedelta(days=1)

        raise ValueError(f"No trading day found within 10 days of {date}")

    def previous_trading_day(self, date: Optional[date] = None) -> date:
        """
        Get previous trading day before given date.

        Args:
            date: Reference date (default: today)

        Returns:
            Previous trading day
        """
        if date is None:
            date = datetime.now().date()

        current = date - timedelta(days=1)

        # Search up to 10 days back
        for _ in range(10):
            if self.is_trading_day(current):
                return current
            current -= timedelta(days=1)

        raise ValueError(f"No trading day found within 10 days before {date}")

    def get_market_hours(self, date: date) -> Optional[Tuple[datetime, datetime]]:
        """
        Get market open and close times for a trading day.

        Args:
            date: Trading date

        Returns:
            Tuple of (market_open, market_close) in market timezone, or None if not a trading day
        """
        if not self.is_trading_day(date):
            return None

        date_str = date.strftime("%Y-%m-%d")
        row = self._schedule.loc[date_str]

        return (row["market_open"].to_pydatetime(), row["market_close"].to_pydatetime())

    def is_half_day(self, date: date) -> bool:
        """
        Check if given date is a half trading day (early close).

        Args:
            date: Date to check

        Returns:
            True if half day
        """
        hours = self.get_market_hours(date)
        if hours is None:
            return False

        open_time, close_time = hours
        trading_hours = (close_time - open_time).total_seconds() / 3600

        # Regular trading is 6.5 hours; half day is typically 3-4 hours
        return trading_hours < 5.0

    def count_trading_days(self, start_date: date, end_date: date) -> int:
        """
        Count number of trading days in range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            Count of trading days
        """
        return len(self.get_trading_days(start_date, end_date))

    def get_trading_day_offset(self, date: date, offset: int) -> date:
        """
        Get trading day N days before/after given date.

        Args:
            date: Reference date
            offset: Number of trading days (positive=future, negative=past)

        Returns:
            Target trading day
        """
        if offset == 0:
            return date if self.is_trading_day(date) else self.next_trading_day(date)

        current = date
        direction = 1 if offset > 0 else -1
        remaining = abs(offset)

        while remaining > 0:
            current += timedelta(days=direction)
            if self.is_trading_day(current):
                remaining -= 1

        return current

    def get_holidays(self, year: int) -> List[Tuple[date, str]]:
        """
        Get list of market holidays for given year.

        Args:
            year: Year to query

        Returns:
            List of (holiday_date, holiday_name) tuples
        """
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"

        holidays = self.calendar.holidays()

        # Get all trading days in the year
        all_days = pd.date_range(start=start_date, end=end_date, freq="D")
        trading_days = self.calendar.schedule(start_date=start_date, end_date=end_date).index

        # Holidays are days that are not trading days (excluding weekends)
        holiday_dates = []
        for day in all_days:
            # Skip weekends
            if day.weekday() >= 5:
                continue
            # Check if not a trading day
            if day not in trading_days:
                holiday_dates.append((day.date(), "Holiday"))

        return holiday_dates

    def refresh_cache(self):
        """Refresh calendar cache with latest data."""
        self._preload_calendar()
        # Clear LRU cache
        self.is_trading_day.cache_clear()
