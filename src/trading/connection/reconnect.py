"""
Reconnection strategy with exponential backoff.

Implements retry logic with increasing delays:
- Attempt 1: 0 seconds (immediate)
- Attempt 2: 5 seconds
- Attempt 3: 15 seconds
- Attempt 4: 30 seconds
- Attempt 5+: 60 seconds

Maximum 10 retry attempts before giving up.
"""

from datetime import datetime, timedelta
from typing import Optional


class ReconnectStrategy:
    """
    Manages reconnection attempts with exponential backoff.

    Backoff schedule:
    - Attempt 0: 0s (immediate)
    - Attempt 1: 5s
    - Attempt 2: 15s
    - Attempt 3: 30s
    - Attempt 4+: 60s (max)
    """

    # Backoff delays in seconds
    BACKOFF_DELAYS = [0, 5, 15, 30, 60]
    MAX_RETRIES = 10

    def __init__(self, max_retries: int = MAX_RETRIES):
        """
        Initialize reconnection strategy.

        Args:
            max_retries: Maximum number of retry attempts
        """
        self.max_retries = max_retries
        self._attempt_count = 0
        self._last_attempt_time: Optional[datetime] = None
        self._first_failure_time: Optional[datetime] = None

    @property
    def attempt_count(self) -> int:
        """Get current attempt count."""
        return self._attempt_count

    @property
    def has_attempts_remaining(self) -> bool:
        """Check if retry attempts remain."""
        return self._attempt_count < self.max_retries

    @property
    def last_attempt_time(self) -> Optional[datetime]:
        """Get time of last attempt."""
        return self._last_attempt_time

    @property
    def first_failure_time(self) -> Optional[datetime]:
        """Get time of first failure."""
        return self._first_failure_time

    def get_delay(self) -> int:
        """
        Get delay in seconds before next retry.

        Returns:
            Delay in seconds based on attempt count
        """
        if self._attempt_count >= len(self.BACKOFF_DELAYS):
            return self.BACKOFF_DELAYS[-1]
        return self.BACKOFF_DELAYS[self._attempt_count]

    def get_next_attempt_time(self) -> Optional[datetime]:
        """
        Calculate next attempt time.

        Returns:
            Datetime of next attempt, or None if no attempts remain
        """
        if not self.has_attempts_remaining:
            return None

        if self._last_attempt_time is None:
            return datetime.utcnow()

        delay = self.get_delay()
        return self._last_attempt_time + timedelta(seconds=delay)

    def should_retry_now(self) -> bool:
        """
        Check if should retry now.

        Returns:
            True if enough time has passed for next attempt
        """
        if not self.has_attempts_remaining:
            return False

        next_time = self.get_next_attempt_time()
        if next_time is None:
            return False

        return datetime.utcnow() >= next_time

    def record_attempt(self):
        """Record a reconnection attempt."""
        now = datetime.utcnow()

        if self._first_failure_time is None:
            self._first_failure_time = now

        self._last_attempt_time = now
        self._attempt_count += 1

    def record_success(self):
        """Record successful reconnection and reset counters."""
        self.reset()

    def reset(self):
        """Reset reconnection state."""
        self._attempt_count = 0
        self._last_attempt_time = None
        self._first_failure_time = None

    def get_total_downtime(self) -> Optional[timedelta]:
        """
        Calculate total downtime since first failure.

        Returns:
            Timedelta of downtime, or None if no failures
        """
        if self._first_failure_time is None:
            return None

        return datetime.utcnow() - self._first_failure_time

    def get_stats(self) -> dict:
        """
        Get reconnection statistics.

        Returns:
            Dictionary with attempt count, downtime, and next retry time
        """
        return {
            "attempt_count": self._attempt_count,
            "max_retries": self.max_retries,
            "has_attempts_remaining": self.has_attempts_remaining,
            "last_attempt_time": self._last_attempt_time,
            "first_failure_time": self._first_failure_time,
            "total_downtime_seconds": (
                self.get_total_downtime().total_seconds() if self.get_total_downtime() else None
            ),
            "next_attempt_time": self.get_next_attempt_time(),
            "next_delay_seconds": self.get_delay() if self.has_attempts_remaining else None,
        }
