"""
Gateway Restart Handler.

Manages IB Gateway scheduled restart window:
- Detects scheduled restart window (03:00-03:30 ET)
- Distinguishes scheduled restart from unexpected disconnection
- Buffers signals during restart window
- Handles pre-restart preparation and post-restart recovery
"""

from datetime import datetime, time, timedelta
from typing import Optional, Callable
import pytz

from src.core.timezone_manager import TimezoneManager


class RestartWindow:
    """Represents a Gateway restart window configuration."""

    def __init__(
        self,
        scheduled_time: time = time(3, 0, 0),
        window_minutes: int = 30,
        prepare_minutes: int = 10,
        timezone: str = "America/New_York"
    ):
        """
        Initialize restart window.

        Args:
            scheduled_time: Scheduled restart time in market timezone
            window_minutes: Duration of restart window
            prepare_minutes: Pre-restart preparation time
            timezone: Market timezone
        """
        self.scheduled_time = scheduled_time
        self.window_minutes = window_minutes
        self.prepare_minutes = prepare_minutes
        self.timezone = pytz.timezone(timezone)

    def get_window_start(self, reference_date: datetime) -> datetime:
        """
        Get restart window start time for given date.

        Args:
            reference_date: Reference date (any timezone)

        Returns:
            Window start time in market timezone
        """
        market_date = reference_date.astimezone(self.timezone).date()
        window_start = datetime.combine(market_date, self.scheduled_time)
        return self.timezone.localize(window_start)

    def get_window_end(self, reference_date: datetime) -> datetime:
        """
        Get restart window end time for given date.

        Args:
            reference_date: Reference date (any timezone)

        Returns:
            Window end time in market timezone
        """
        window_start = self.get_window_start(reference_date)
        return window_start + timedelta(minutes=self.window_minutes)

    def get_prepare_time(self, reference_date: datetime) -> datetime:
        """
        Get pre-restart preparation time for given date.

        Args:
            reference_date: Reference date (any timezone)

        Returns:
            Preparation start time in market timezone
        """
        window_start = self.get_window_start(reference_date)
        return window_start - timedelta(minutes=self.prepare_minutes)

    def is_in_prepare_period(self, check_time: datetime) -> bool:
        """
        Check if time is in pre-restart preparation period.

        Args:
            check_time: Time to check (any timezone)

        Returns:
            True if in preparation period
        """
        market_time = check_time.astimezone(self.timezone)
        prepare_time = self.get_prepare_time(market_time)
        window_start = self.get_window_start(market_time)

        return prepare_time <= market_time < window_start

    def is_in_restart_window(self, check_time: datetime) -> bool:
        """
        Check if time is in restart window.

        Args:
            check_time: Time to check (any timezone)

        Returns:
            True if in restart window
        """
        market_time = check_time.astimezone(self.timezone)
        window_start = self.get_window_start(market_time)
        window_end = self.get_window_end(market_time)

        return window_start <= market_time < window_end

    def is_past_restart_window(self, check_time: datetime) -> bool:
        """
        Check if time is past restart window.

        Args:
            check_time: Time to check (any timezone)

        Returns:
            True if past restart window
        """
        market_time = check_time.astimezone(self.timezone)
        window_end = self.get_window_end(market_time)

        return market_time >= window_end

    def get_time_until_prepare(self, check_time: datetime) -> Optional[timedelta]:
        """
        Get time until preparation period starts.

        Args:
            check_time: Current time (any timezone)

        Returns:
            Timedelta until prepare time, or None if already in/past window
        """
        market_time = check_time.astimezone(self.timezone)
        prepare_time = self.get_prepare_time(market_time)

        if market_time >= prepare_time:
            # Already in or past prepare period
            return None

        return prepare_time - market_time

    def get_time_until_window_end(self, check_time: datetime) -> Optional[timedelta]:
        """
        Get time until restart window ends.

        Args:
            check_time: Current time (any timezone)

        Returns:
            Timedelta until window end, or None if past window
        """
        market_time = check_time.astimezone(self.timezone)
        window_end = self.get_window_end(market_time)

        if market_time >= window_end:
            return None

        return window_end - market_time


class GatewayRestartHandler:
    """
    Handles Gateway scheduled restart and recovery.

    Responsibilities:
    - Detect scheduled restart window
    - Manage pre-restart preparation
    - Buffer signals during restart
    - Handle post-restart recovery
    """

    def __init__(
        self,
        restart_window: RestartWindow,
        timezone_manager: TimezoneManager
    ):
        """
        Initialize restart handler.

        Args:
            restart_window: Restart window configuration
            timezone_manager: Timezone manager instance
        """
        self.restart_window = restart_window
        self.tz_manager = timezone_manager

        # State tracking
        self._in_prepare_mode = False
        self._in_restart_window = False
        self._last_check_time: Optional[datetime] = None
        self._restart_start_time: Optional[datetime] = None
        self._restart_end_time: Optional[datetime] = None

        # Callbacks
        self._on_prepare_callbacks: list[Callable] = []
        self._on_restart_start_callbacks: list[Callable] = []
        self._on_restart_end_callbacks: list[Callable] = []

    @property
    def is_preparing(self) -> bool:
        """Check if in preparation mode."""
        return self._in_prepare_mode

    @property
    def is_restarting(self) -> bool:
        """Check if in restart window."""
        return self._in_restart_window

    def check_restart_status(self, current_time: Optional[datetime] = None) -> str:
        """
        Check current restart window status.

        Args:
            current_time: Time to check (default: now in UTC)

        Returns:
            Status string: 'normal', 'prepare', 'restarting', 'past_window'
        """
        if current_time is None:
            current_time = self.tz_manager.now_utc()

        self._last_check_time = current_time

        if self.restart_window.is_in_restart_window(current_time):
            if not self._in_restart_window:
                self._enter_restart_window(current_time)
            return 'restarting'

        elif self.restart_window.is_in_prepare_period(current_time):
            if not self._in_prepare_mode:
                self._enter_prepare_mode(current_time)
            return 'prepare'

        else:
            # Normal operation or past window
            if self._in_prepare_mode or self._in_restart_window:
                if self.restart_window.is_past_restart_window(current_time):
                    if self._in_restart_window:
                        self._exit_restart_window(current_time)
                    return 'past_window'
                self._reset_state()

            return 'normal'

    def should_suppress_alert(self, disconnect_time: datetime) -> bool:
        """
        Check if disconnection alert should be suppressed.

        Args:
            disconnect_time: Time of disconnection

        Returns:
            True if disconnect occurred during restart window
        """
        return self.restart_window.is_in_restart_window(disconnect_time)

    def is_scheduled_restart(self, disconnect_time: datetime) -> bool:
        """
        Determine if disconnection is a scheduled restart.

        Args:
            disconnect_time: Time of disconnection

        Returns:
            True if disconnect occurred during restart window
        """
        return self.restart_window.is_in_restart_window(disconnect_time)

    def _enter_prepare_mode(self, enter_time: datetime):
        """Enter pre-restart preparation mode."""
        self._in_prepare_mode = True
        print(f"[{enter_time}] Entering restart preparation mode")

        # Trigger callbacks
        for callback in self._on_prepare_callbacks:
            try:
                callback(enter_time)
            except Exception as e:
                print(f"Error in prepare callback: {e}")

    def _enter_restart_window(self, enter_time: datetime):
        """Enter restart window."""
        self._in_restart_window = True
        self._restart_start_time = enter_time
        print(f"[{enter_time}] Entering Gateway restart window")

        # Trigger callbacks
        for callback in self._on_restart_start_callbacks:
            try:
                callback(enter_time)
            except Exception as e:
                print(f"Error in restart start callback: {e}")

    def _exit_restart_window(self, exit_time: datetime):
        """Exit restart window."""
        self._restart_end_time = exit_time

        downtime = None
        if self._restart_start_time:
            downtime = exit_time - self._restart_start_time

        print(f"[{exit_time}] Exiting Gateway restart window (downtime: {downtime})")

        # Trigger callbacks
        for callback in self._on_restart_end_callbacks:
            try:
                callback(exit_time, downtime)
            except Exception as e:
                print(f"Error in restart end callback: {e}")

        self._reset_state()

    def _reset_state(self):
        """Reset internal state."""
        self._in_prepare_mode = False
        self._in_restart_window = False

    def register_prepare_callback(self, callback: Callable):
        """Register callback for preparation period entry."""
        self._on_prepare_callbacks.append(callback)

    def register_restart_start_callback(self, callback: Callable):
        """Register callback for restart window entry."""
        self._on_restart_start_callbacks.append(callback)

    def register_restart_end_callback(self, callback: Callable):
        """Register callback for restart window exit."""
        self._on_restart_end_callbacks.append(callback)

    def get_status(self) -> dict:
        """
        Get restart handler status.

        Returns:
            Dictionary with status details
        """
        current_time = self.tz_manager.now_utc()

        return {
            'is_preparing': self.is_preparing,
            'is_restarting': self.is_restarting,
            'current_status': self.check_restart_status(current_time),
            'restart_window': {
                'scheduled_time': self.restart_window.scheduled_time.strftime('%H:%M:%S'),
                'window_minutes': self.restart_window.window_minutes,
                'prepare_minutes': self.restart_window.prepare_minutes
            },
            'time_until_prepare': (
                self.restart_window.get_time_until_prepare(current_time).total_seconds()
                if self.restart_window.get_time_until_prepare(current_time)
                else None
            ),
            'time_until_window_end': (
                self.restart_window.get_time_until_window_end(current_time).total_seconds()
                if self.restart_window.get_time_until_window_end(current_time)
                else None
            ),
            'last_restart_start': self._restart_start_time,
            'last_restart_end': self._restart_end_time
        }
