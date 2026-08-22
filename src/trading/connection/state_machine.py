"""
Connection State Machine for IBKR Gateway connection management.

States:
- DISCONNECTED: Initial state, no connection
- CONNECTING: Attempting to establish connection
- CONNECTED: TCP connection established, waiting for API ready
- READY: Fully connected and ready for trading
- CONNECTION_LOST: Connection dropped unexpectedly
- GATEWAY_RESTARTING: Gateway is in scheduled restart window
"""

from enum import Enum, auto
from typing import Optional, Callable
from datetime import datetime


class ConnectionState(Enum):
    """Connection states."""
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    READY = auto()
    CONNECTION_LOST = auto()
    GATEWAY_RESTARTING = auto()


class ConnectionStateMachine:
    """
    Manages connection state transitions.

    State transition rules:
    - DISCONNECTED → CONNECTING: start_connect()
    - CONNECTING → CONNECTED: on_connect()
    - CONNECTING → DISCONNECTED: on_connect_failed()
    - CONNECTED → READY: on_ready()
    - READY → CONNECTION_LOST: on_disconnect()
    - CONNECTION_LOST → CONNECTING: start_reconnect()
    - * → GATEWAY_RESTARTING: enter_restart_window()
    - GATEWAY_RESTARTING → CONNECTING: exit_restart_window()
    """

    def __init__(self):
        """Initialize state machine."""
        self._state = ConnectionState.DISCONNECTED
        self._previous_state: Optional[ConnectionState] = None
        self._transition_time = datetime.utcnow()
        self._callbacks: dict[ConnectionState, list[Callable]] = {}

    @property
    def state(self) -> ConnectionState:
        """Get current state."""
        return self._state

    @property
    def previous_state(self) -> Optional[ConnectionState]:
        """Get previous state."""
        return self._previous_state

    @property
    def transition_time(self) -> datetime:
        """Get last transition time."""
        return self._transition_time

    def is_connected(self) -> bool:
        """Check if in any connected state."""
        return self._state in [
            ConnectionState.CONNECTED,
            ConnectionState.READY
        ]

    def is_ready(self) -> bool:
        """Check if ready for trading."""
        return self._state == ConnectionState.READY

    def is_restarting(self) -> bool:
        """Check if in restart window."""
        return self._state == ConnectionState.GATEWAY_RESTARTING

    def can_transition_to(self, new_state: ConnectionState) -> bool:
        """
        Check if transition to new state is valid.

        Args:
            new_state: Target state

        Returns:
            True if transition is allowed
        """
        valid_transitions = {
            ConnectionState.DISCONNECTED: [
                ConnectionState.CONNECTING,
                ConnectionState.GATEWAY_RESTARTING
            ],
            ConnectionState.CONNECTING: [
                ConnectionState.CONNECTED,
                ConnectionState.DISCONNECTED,
                ConnectionState.GATEWAY_RESTARTING
            ],
            ConnectionState.CONNECTED: [
                ConnectionState.READY,
                ConnectionState.CONNECTION_LOST,
                ConnectionState.DISCONNECTED,
                ConnectionState.GATEWAY_RESTARTING
            ],
            ConnectionState.READY: [
                ConnectionState.CONNECTION_LOST,
                ConnectionState.DISCONNECTED,
                ConnectionState.GATEWAY_RESTARTING
            ],
            ConnectionState.CONNECTION_LOST: [
                ConnectionState.CONNECTING,
                ConnectionState.DISCONNECTED,
                ConnectionState.GATEWAY_RESTARTING
            ],
            ConnectionState.GATEWAY_RESTARTING: [
                ConnectionState.CONNECTING,
                ConnectionState.DISCONNECTED
            ]
        }

        return new_state in valid_transitions.get(self._state, [])

    def transition_to(self, new_state: ConnectionState) -> bool:
        """
        Transition to new state.

        Args:
            new_state: Target state

        Returns:
            True if transition succeeded

        Raises:
            ValueError: If transition is not allowed
        """
        if not self.can_transition_to(new_state):
            raise ValueError(
                f"Invalid transition from {self._state.name} to {new_state.name}"
            )

        self._previous_state = self._state
        self._state = new_state
        self._transition_time = datetime.utcnow()

        # Trigger callbacks
        self._trigger_callbacks(new_state)

        return True

    def register_callback(
        self,
        state: ConnectionState,
        callback: Callable
    ):
        """
        Register callback for state entry.

        Args:
            state: State to monitor
            callback: Function to call on state entry
        """
        if state not in self._callbacks:
            self._callbacks[state] = []
        self._callbacks[state].append(callback)

    def _trigger_callbacks(self, state: ConnectionState):
        """Trigger callbacks for state entry."""
        if state in self._callbacks:
            for callback in self._callbacks[state]:
                try:
                    callback(state)
                except Exception as e:
                    # Log but don't fail transition
                    print(f"Callback error for {state.name}: {e}")

    # Convenience transition methods

    def start_connect(self):
        """Start connection attempt."""
        self.transition_to(ConnectionState.CONNECTING)

    def on_connect(self):
        """Connection established."""
        self.transition_to(ConnectionState.CONNECTED)

    def on_ready(self):
        """System ready for trading."""
        self.transition_to(ConnectionState.READY)

    def on_disconnect(self):
        """Connection lost."""
        self.transition_to(ConnectionState.CONNECTION_LOST)

    def on_connect_failed(self):
        """Connection attempt failed."""
        self.transition_to(ConnectionState.DISCONNECTED)

    def enter_restart_window(self):
        """Enter Gateway restart window."""
        self.transition_to(ConnectionState.GATEWAY_RESTARTING)

    def exit_restart_window(self):
        """Exit Gateway restart window."""
        self.transition_to(ConnectionState.CONNECTING)

    def reset(self):
        """Reset to initial state."""
        self._previous_state = self._state
        self._state = ConnectionState.DISCONNECTED
        self._transition_time = datetime.utcnow()
