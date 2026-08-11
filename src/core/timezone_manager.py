"""
Timezone Manager - Unified timezone conversion and trading hours validation.

Handles conversions between:
- IBKR Market Time (America/New_York - EST/EDT)
- UTC (internal storage standard)
- Local Time (Asia/Shanghai)

Automatically detects Daylight Saving Time (DST) transitions.
"""

from datetime import datetime, time, timedelta
from typing import Optional, Tuple
from zoneinfo import ZoneInfo
import pytz


class TimezoneManager:
    """
    Centralized timezone management for the trading system.

    Design principles:
    1. Store all timestamps in UTC internally
    2. Convert to appropriate timezone only at boundaries (display, API calls)
    3. Always use timezone-aware datetime objects
    """

    def __init__(
        self,
        market_timezone: str = "America/New_York",
        local_timezone: str = "Asia/Shanghai",
        regular_start: time = time(9, 30),
        regular_end: time = time(16, 0)
    ):
        """
        Initialize timezone manager.

        Args:
            market_timezone: Market timezone (default: America/New_York)
            local_timezone: Local timezone (default: Asia/Shanghai)
            regular_start: Regular trading session start time in market timezone
            regular_end: Regular trading session end time in market timezone
        """
        self.market_tz = pytz.timezone(market_timezone)
        self.local_tz = pytz.timezone(local_timezone)
        self.utc_tz = pytz.UTC

        self.regular_start = regular_start
        self.regular_end = regular_end

    def now_utc(self) -> datetime:
        """Get current time in UTC."""
        return datetime.now(self.utc_tz)

    def now_market(self) -> datetime:
        """Get current time in market timezone."""
        return self.now_utc().astimezone(self.market_tz)

    def now_local(self) -> datetime:
        """Get current time in local timezone."""
        return self.now_utc().astimezone(self.local_tz)

    def to_utc(self, dt: datetime, from_tz: Optional[str] = None) -> datetime:
        """
        Convert datetime to UTC.

        Args:
            dt: Input datetime (naive or aware)
            from_tz: Source timezone if dt is naive. If None, assumes UTC.

        Returns:
            Timezone-aware datetime in UTC
        """
        if dt.tzinfo is None:
            # Naive datetime
            if from_tz:
                source_tz = pytz.timezone(from_tz)
                dt = source_tz.localize(dt)
            else:
                dt = self.utc_tz.localize(dt)

        return dt.astimezone(self.utc_tz)

    def ibkr_to_utc(self, dt: datetime) -> datetime:
        """
        Convert IBKR market time to UTC.

        Args:
            dt: Datetime in market timezone (naive or aware)

        Returns:
            Timezone-aware datetime in UTC
        """
        if dt.tzinfo is None:
            dt = self.market_tz.localize(dt)
        return dt.astimezone(self.utc_tz)

    def utc_to_market(self, dt: datetime) -> datetime:
        """
        Convert UTC to market timezone.

        Args:
            dt: Datetime in UTC (naive or aware)

        Returns:
            Timezone-aware datetime in market timezone
        """
        if dt.tzinfo is None:
            dt = self.utc_tz.localize(dt)
        return dt.astimezone(self.market_tz)

    def utc_to_local(self, dt: datetime) -> datetime:
        """
        Convert UTC to local timezone.

        Args:
            dt: Datetime in UTC (naive or aware)

        Returns:
            Timezone-aware datetime in local timezone
        """
        if dt.tzinfo is None:
            dt = self.utc_tz.localize(dt)
        return dt.astimezone(self.local_tz)

    def local_to_utc(self, dt: datetime) -> datetime:
        """
        Convert local time to UTC.

        Args:
            dt: Datetime in local timezone (naive or aware)

        Returns:
            Timezone-aware datetime in UTC
        """
        if dt.tzinfo is None:
            dt = self.local_tz.localize(dt)
        return dt.astimezone(self.utc_tz)

    def market_to_utc(self, dt: datetime) -> datetime:
        """
        Convert market time to UTC.

        Args:
            dt: Datetime in market timezone (naive or aware)

        Returns:
            Timezone-aware datetime in UTC
        """
        return self.ibkr_to_utc(dt)

    def is_dst(self, dt: Optional[datetime] = None) -> bool:
        """
        Check if Daylight Saving Time is active in market timezone.

        Args:
            dt: Datetime to check (default: current time)

        Returns:
            True if DST is active (EDT), False if standard time (EST)
        """
        if dt is None:
            dt = self.now_market()
        elif dt.tzinfo is None:
            dt = self.market_tz.localize(dt)
        else:
            dt = dt.astimezone(self.market_tz)

        return bool(dt.dst())

    def get_utc_offset(self, dt: Optional[datetime] = None) -> int:
        """
        Get UTC offset in hours for market timezone.

        Args:
            dt: Datetime to check (default: current time)

        Returns:
            UTC offset in hours (e.g., -5 for EST, -4 for EDT)
        """
        if dt is None:
            dt = self.now_market()
        elif dt.tzinfo is None:
            dt = self.market_tz.localize(dt)
        else:
            dt = dt.astimezone(self.market_tz)

        offset_seconds = dt.utcoffset().total_seconds()
        return int(offset_seconds / 3600)

    def is_trading_time(
        self,
        dt: Optional[datetime] = None,
        session: str = "regular"
    ) -> bool:
        """
        Check if given time falls within trading hours.

        Args:
            dt: Datetime to check in UTC (default: current time)
            session: Trading session type ("regular", "pre", "after")

        Returns:
            True if within trading hours
        """
        if dt is None:
            dt = self.now_utc()

        market_time = self.utc_to_market(dt)
        current_time = market_time.time()

        if session == "regular":
            return self.regular_start <= current_time < self.regular_end
        elif session == "pre":
            return time(4, 0) <= current_time < self.regular_start
        elif session == "after":
            return self.regular_end <= current_time < time(20, 0)
        else:
            return False

    def next_market_open(self, dt: Optional[datetime] = None) -> datetime:
        """
        Get next market open time in UTC.

        Args:
            dt: Reference datetime in UTC (default: current time)

        Returns:
            Next market open datetime in UTC
        """
        if dt is None:
            dt = self.now_utc()

        market_time = self.utc_to_market(dt)

        # If before market open today, return today's open
        if market_time.time() < self.regular_start:
            next_open = market_time.replace(
                hour=self.regular_start.hour,
                minute=self.regular_start.minute,
                second=0,
                microsecond=0
            )
        else:
            # Otherwise return next day's open
            next_day = market_time + timedelta(days=1)
            next_open = next_day.replace(
                hour=self.regular_start.hour,
                minute=self.regular_start.minute,
                second=0,
                microsecond=0
            )

        return next_open.astimezone(self.utc_tz)

    def next_market_close(self, dt: Optional[datetime] = None) -> datetime:
        """
        Get next market close time in UTC.

        Args:
            dt: Reference datetime in UTC (default: current time)

        Returns:
            Next market close datetime in UTC
        """
        if dt is None:
            dt = self.now_utc()

        market_time = self.utc_to_market(dt)

        # If before market close today, return today's close
        if market_time.time() < self.regular_end:
            next_close = market_time.replace(
                hour=self.regular_end.hour,
                minute=self.regular_end.minute,
                second=0,
                microsecond=0
            )
        else:
            # Otherwise return next day's close
            next_day = market_time + timedelta(days=1)
            next_close = next_day.replace(
                hour=self.regular_end.hour,
                minute=self.regular_end.minute,
                second=0,
                microsecond=0
            )

        return next_close.astimezone(self.utc_tz)

    def get_trading_day_bounds(
        self,
        date: Optional[datetime] = None
    ) -> Tuple[datetime, datetime]:
        """
        Get start and end of trading day in UTC.

        Args:
            date: Reference date (default: current date)

        Returns:
            Tuple of (market_open_utc, market_close_utc)
        """
        if date is None:
            date = self.now_utc()

        market_time = self.utc_to_market(date)

        open_time = market_time.replace(
            hour=self.regular_start.hour,
            minute=self.regular_start.minute,
            second=0,
            microsecond=0
        )

        close_time = market_time.replace(
            hour=self.regular_end.hour,
            minute=self.regular_end.minute,
            second=0,
            microsecond=0
        )

        return (
            open_time.astimezone(self.utc_tz),
            close_time.astimezone(self.utc_tz)
        )

    def get_current_session(self, dt: Optional[datetime] = None) -> str:
        """
        Get current trading session.

        Args:
            dt: Datetime to check (default: current time)

        Returns:
            'pre_market' | 'regular' | 'after_hours' | 'closed'
        """
        if dt is None:
            dt = self.now_utc()

        market_time = self.utc_to_market(dt)
        current_time = market_time.time()

        # Pre-market: 04:00-09:30 ET
        if time(4, 0) <= current_time < time(9, 30):
            return 'pre_market'

        # Regular: 09:30-16:00 ET
        elif time(9, 30) <= current_time < time(16, 0):
            return 'regular'

        # After-hours: 16:00-20:00 ET
        elif time(16, 0) <= current_time < time(20, 0):
            return 'after_hours'

        # Closed: 20:00-04:00 ET (next day)
        else:
            return 'closed'

    def format_dual_timezone(self, dt: datetime) -> str:
        """
        Format datetime with both market and local time for logging.

        Args:
            dt: Datetime in any timezone

        Returns:
            Formatted string: "2026-08-08 09:30:00 ET / 21:30:00 CST"
        """
        market_time = self.utc_to_market(dt)
        local_time = self.utc_to_local(dt)

        tz_abbr = "EDT" if self.is_dst(market_time) else "EST"

        return (
            f"{market_time.strftime('%Y-%m-%d %H:%M:%S')} {tz_abbr} / "
            f"{local_time.strftime('%H:%M:%S')} CST"
        )
