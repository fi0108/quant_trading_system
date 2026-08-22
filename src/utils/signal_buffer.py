"""
Signal Buffer for Gateway restart window.

Buffers trading signals during Gateway restart and executes them after recovery.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum
import json


class SignalStatus(Enum):
    """Signal buffer status."""
    PENDING = "pending"
    EXECUTED = "executed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class BufferedSignal:
    """Represents a buffered trading signal."""

    def __init__(
        self,
        strategy_name: str,
        symbol: str,
        signal_type: str,
        signal_time: datetime,
        signal_data: Dict[str, Any],
        expiry_minutes: int = 10
    ):
        """
        Initialize buffered signal.

        Args:
            strategy_name: Name of strategy that generated signal
            symbol: Trading symbol
            signal_type: Type of signal (buy, sell, etc.)
            signal_time: Time signal was generated
            signal_data: Additional signal data
            expiry_minutes: Signal expiration time in minutes
        """
        self.strategy_name = strategy_name
        self.symbol = symbol
        self.signal_type = signal_type
        self.signal_time = signal_time
        self.signal_data = signal_data
        self.expiry_time = signal_time + timedelta(minutes=expiry_minutes)
        self.status = SignalStatus.PENDING
        self.executed_at: Optional[datetime] = None

    def is_expired(self, current_time: datetime) -> bool:
        """
        Check if signal has expired.

        Args:
            current_time: Current time

        Returns:
            True if signal is expired
        """
        return current_time >= self.expiry_time

    def is_valid(self, current_time: datetime) -> bool:
        """
        Check if signal is still valid for execution.

        Args:
            current_time: Current time

        Returns:
            True if signal can be executed
        """
        return (
            self.status == SignalStatus.PENDING and
            not self.is_expired(current_time)
        )

    def mark_executed(self, execution_time: datetime):
        """Mark signal as executed."""
        self.status = SignalStatus.EXECUTED
        self.executed_at = execution_time

    def mark_expired(self):
        """Mark signal as expired."""
        self.status = SignalStatus.EXPIRED

    def mark_cancelled(self):
        """Mark signal as cancelled."""
        self.status = SignalStatus.CANCELLED

    def get_age(self, current_time: datetime) -> timedelta:
        """
        Get signal age.

        Args:
            current_time: Current time

        Returns:
            Timedelta since signal generation
        """
        return current_time - self.signal_time

    def get_time_until_expiry(self, current_time: datetime) -> timedelta:
        """
        Get time until expiration.

        Args:
            current_time: Current time

        Returns:
            Timedelta until expiry
        """
        return self.expiry_time - current_time

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for persistence.

        Returns:
            Dictionary representation
        """
        return {
            'strategy_name': self.strategy_name,
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'signal_time': self.signal_time.isoformat(),
            'expiry_time': self.expiry_time.isoformat(),
            'signal_data': json.dumps(self.signal_data),
            'status': self.status.value,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BufferedSignal':
        """
        Create BufferedSignal from dictionary.

        Args:
            data: Dictionary data

        Returns:
            BufferedSignal instance
        """
        signal = cls(
            strategy_name=data['strategy_name'],
            symbol=data['symbol'],
            signal_type=data['signal_type'],
            signal_time=datetime.fromisoformat(data['signal_time']),
            signal_data=json.loads(data['signal_data'])
        )
        signal.expiry_time = datetime.fromisoformat(data['expiry_time'])
        signal.status = SignalStatus(data['status'])
        if data['executed_at']:
            signal.executed_at = datetime.fromisoformat(data['executed_at'])
        return signal


class SignalBuffer:
    """
    Manages signal buffering during Gateway restart.

    Features:
    - Buffer signals during restart window
    - Track signal expiration
    - Execute valid signals after recovery
    - Maintain signal history
    """

    def __init__(self, default_expiry_minutes: int = 10):
        """
        Initialize signal buffer.

        Args:
            default_expiry_minutes: Default signal expiration time
        """
        self.default_expiry_minutes = default_expiry_minutes
        self._signals: List[BufferedSignal] = []

    def add_signal(
        self,
        strategy_name: str,
        symbol: str,
        signal_type: str,
        signal_time: datetime,
        signal_data: Dict[str, Any],
        expiry_minutes: Optional[int] = None
    ) -> BufferedSignal:
        """
        Add signal to buffer.

        Args:
            strategy_name: Strategy name
            symbol: Trading symbol
            signal_type: Signal type
            signal_time: Signal generation time
            signal_data: Additional data
            expiry_minutes: Custom expiry time (uses default if None)

        Returns:
            Created BufferedSignal instance
        """
        if expiry_minutes is None:
            expiry_minutes = self.default_expiry_minutes

        signal = BufferedSignal(
            strategy_name=strategy_name,
            symbol=symbol,
            signal_type=signal_type,
            signal_time=signal_time,
            signal_data=signal_data,
            expiry_minutes=expiry_minutes
        )

        self._signals.append(signal)
        return signal

    def get_pending_signals(self, current_time: datetime) -> List[BufferedSignal]:
        """
        Get all pending (valid) signals.

        Args:
            current_time: Current time for expiry check

        Returns:
            List of valid pending signals
        """
        return [
            signal for signal in self._signals
            if signal.is_valid(current_time)
        ]

    def get_expired_signals(self, current_time: datetime) -> List[BufferedSignal]:
        """
        Get all expired signals.

        Args:
            current_time: Current time for expiry check

        Returns:
            List of expired signals
        """
        return [
            signal for signal in self._signals
            if signal.status == SignalStatus.PENDING and signal.is_expired(current_time)
        ]

    def mark_expired_signals(self, current_time: datetime) -> int:
        """
        Mark expired signals.

        Args:
            current_time: Current time for expiry check

        Returns:
            Number of signals marked as expired
        """
        count = 0
        for signal in self._signals:
            if signal.status == SignalStatus.PENDING and signal.is_expired(current_time):
                signal.mark_expired()
                count += 1
        return count

    def execute_signal(self, signal: BufferedSignal, execution_time: datetime):
        """
        Mark signal as executed.

        Args:
            signal: Signal to execute
            execution_time: Execution time
        """
        signal.mark_executed(execution_time)

    def cancel_signal(self, signal: BufferedSignal):
        """
        Cancel a buffered signal.

        Args:
            signal: Signal to cancel
        """
        signal.mark_cancelled()

    def clear_old_signals(self, keep_hours: int = 24, reference_time: Optional[datetime] = None) -> int:
        """
        Clear old signals from buffer.

        Args:
            keep_hours: Hours of history to keep
            reference_time: Reference time for comparison (default: now UTC)

        Returns:
            Number of signals removed
        """
        if reference_time is None:
            import pytz
            reference_time = pytz.UTC.localize(datetime.utcnow())

        cutoff_time = reference_time - timedelta(hours=keep_hours)
        before_count = len(self._signals)

        self._signals = [
            signal for signal in self._signals
            if signal.signal_time >= cutoff_time
        ]

        return before_count - len(self._signals)

    def get_all_signals(self) -> List[BufferedSignal]:
        """Get all signals in buffer."""
        return self._signals.copy()

    def count_by_status(self) -> Dict[SignalStatus, int]:
        """
        Count signals by status.

        Returns:
            Dictionary with counts per status
        """
        counts = {status: 0 for status in SignalStatus}
        for signal in self._signals:
            counts[signal.status] += 1
        return counts

    def get_statistics(self, current_time: datetime) -> Dict[str, Any]:
        """
        Get buffer statistics.

        Args:
            current_time: Current time

        Returns:
            Dictionary with statistics
        """
        pending = self.get_pending_signals(current_time)
        expired = self.get_expired_signals(current_time)

        return {
            'total_signals': len(self._signals),
            'pending_count': len(pending),
            'expired_count': len(expired),
            'status_counts': self.count_by_status(),
            'oldest_signal': (
                min(s.signal_time for s in self._signals)
                if self._signals else None
            ),
            'newest_signal': (
                max(s.signal_time for s in self._signals)
                if self._signals else None
            )
        }
