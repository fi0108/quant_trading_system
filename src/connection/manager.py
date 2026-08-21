"""
Connection Manager for IBKR Gateway.

Manages connection lifecycle:
- Establish connection to IB Gateway/TWS
- Maintain heartbeat (every 30 seconds)
- Handle disconnections and reconnections
- Monitor connection health
"""

import asyncio
from typing import Optional, Callable
from datetime import datetime, timedelta
from ib_insync import IB, util
import yaml

from state_machine import ConnectionState, ConnectionStateMachine
from reconnect import ReconnectStrategy


class ConnectionManager:
    """
    Manages IBKR Gateway connection.

    Features:
    - Automatic connection with timeout
    - Heartbeat monitoring (30s interval)
    - State machine for connection states
    - Automatic reconnection with exponential backoff
    - Gateway restart window handling
    """

    HEARTBEAT_INTERVAL = 30  # seconds
    DEFAULT_TIMEOUT = 15     # seconds

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4001,
        client_id: int = 1,
        timeout: int = DEFAULT_TIMEOUT,
        readonly: bool = False
    ):
        """
        Initialize connection manager.

        Args:
            host: IB Gateway host
            port: IB Gateway port (4001 for Gateway, 7497 for TWS)
            client_id: Client ID for connection
            timeout: Connection timeout in seconds
            readonly: If True, connect in read-only mode
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.timeout = timeout
        self.readonly = readonly

        # Connection objects
        self.ib = IB()
        self.state_machine = ConnectionStateMachine()
        self.reconnect_strategy = ReconnectStrategy()

        # Heartbeat tracking
        self._last_heartbeat: Optional[datetime] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._connection_task: Optional[asyncio.Task] = None

        # Callbacks
        self._on_connected_callbacks: list[Callable] = []
        self._on_disconnected_callbacks: list[Callable] = []
        self._on_error_callbacks: list[Callable] = []

        # Setup IB event handlers
        self._setup_event_handlers()

    @classmethod
    def from_config(cls, config_path: str = "config/ibkr.yaml"):
        """
        Create ConnectionManager from config file.

        Args:
            config_path: Path to YAML config file

        Returns:
            ConnectionManager instance
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        ibkr_config = config.get('ibkr', {})
        return cls(
            host=ibkr_config.get('host', '127.0.0.1'),
            port=ibkr_config.get('port', 4001),
            client_id=ibkr_config.get('client_id', 1),
            timeout=ibkr_config.get('timeout', cls.DEFAULT_TIMEOUT),
            readonly=ibkr_config.get('read_only', False)
        )

    def _setup_event_handlers(self):
        """Setup IB event handlers."""
        self.ib.connectedEvent += self._on_ib_connected
        self.ib.disconnectedEvent += self._on_ib_disconnected
        self.ib.errorEvent += self._on_ib_error

    def _on_ib_connected(self):
        """Handle IB connected event."""
        print(f"[{datetime.utcnow()}] Connected to IB Gateway at {self.host}:{self.port}")
        self.state_machine.on_connect()
        self.reconnect_strategy.record_success()
        self._last_heartbeat = datetime.utcnow()

        # Trigger callbacks
        for callback in self._on_connected_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"Error in connected callback: {e}")

    def _on_ib_disconnected(self):
        """Handle IB disconnected event."""
        print(f"[{datetime.utcnow()}] Disconnected from IB Gateway")

        if self.state_machine.is_connected():
            self.state_machine.on_disconnect()

        # Trigger callbacks
        for callback in self._on_disconnected_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"Error in disconnected callback: {e}")

    def _on_ib_error(self, reqId, errorCode, errorString, contract):
        """Handle IB error event."""
        # Filter out informational messages
        if errorCode in [2104, 2106, 2158]:  # Market data farm connection messages
            return

        print(f"[{datetime.utcnow()}] IB Error {errorCode}: {errorString}")

        # Trigger callbacks
        for callback in self._on_error_callbacks:
            try:
                callback(errorCode, errorString)
            except Exception as e:
                print(f"Error in error callback: {e}")

    async def connect(self) -> bool:
        """
        Establish connection to IB Gateway.

        Returns:
            True if connection successful

        Raises:
            TimeoutError: If connection times out
            ConnectionError: If connection fails
        """
        if self.is_connected():
            print("Already connected")
            return True

        self.state_machine.start_connect()

        try:
            await asyncio.wait_for(
                self.ib.connectAsync(
                    host=self.host,
                    port=self.port,
                    clientId=self.client_id,
                    readonly=self.readonly,
                    timeout=self.timeout
                ),
                timeout=self.timeout
            )

            # Wait for connection to be ready
            await asyncio.sleep(0.5)

            if self.ib.isConnected():
                self.state_machine.on_ready()
                self._start_heartbeat()
                return True
            else:
                self.state_machine.on_connect_failed()
                return False

        except asyncio.TimeoutError:
            print(f"Connection timeout after {self.timeout}s")
            self.state_machine.on_connect_failed()
            raise TimeoutError(f"Connection timeout to {self.host}:{self.port}")

        except Exception as e:
            print(f"Connection error: {e}")
            self.state_machine.on_connect_failed()
            raise ConnectionError(f"Failed to connect: {e}")

    async def disconnect(self):
        """Disconnect from IB Gateway."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

        if self.ib.isConnected():
            self.ib.disconnect()

        self.state_machine.reset()

    async def reconnect(self) -> bool:
        """
        Reconnect to IB Gateway with exponential backoff.

        Returns:
            True if reconnection successful
        """
        while self.reconnect_strategy.has_attempts_remaining:
            if not self.reconnect_strategy.should_retry_now():
                delay = self.reconnect_strategy.get_delay()
                print(f"Waiting {delay}s before reconnect attempt {self.reconnect_strategy.attempt_count + 1}")
                await asyncio.sleep(delay)

            self.reconnect_strategy.record_attempt()
            print(f"Reconnect attempt {self.reconnect_strategy.attempt_count}/{self.reconnect_strategy.max_retries}")

            try:
                success = await self.connect()
                if success:
                    print("Reconnection successful")
                    return True
            except Exception as e:
                print(f"Reconnect attempt failed: {e}")

        print(f"Reconnection failed after {self.reconnect_strategy.max_retries} attempts")
        return False

    def _start_heartbeat(self):
        """Start heartbeat monitoring task."""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self):
        """Heartbeat monitoring loop."""
        while self.is_connected():
            await asyncio.sleep(self.HEARTBEAT_INTERVAL)

            if self.ib.isConnected():
                self._last_heartbeat = datetime.utcnow()
                # Request account summary as heartbeat
                try:
                    await self.ib.reqAccountSummaryAsync()
                except Exception as e:
                    print(f"Heartbeat error: {e}")
            else:
                print("Heartbeat: Connection lost")
                break

    def is_connected(self) -> bool:
        """Check if connected."""
        return self.state_machine.is_connected() and self.ib.isConnected()

    def is_ready(self) -> bool:
        """Check if ready for trading."""
        return self.state_machine.is_ready() and self.ib.isConnected()

    def get_connection_duration(self) -> Optional[timedelta]:
        """
        Get connection duration.

        Returns:
            Timedelta since connection, or None if not connected
        """
        if not self.is_connected() or self._last_heartbeat is None:
            return None

        return datetime.utcnow() - self.state_machine.transition_time

    def get_last_heartbeat_age(self) -> Optional[timedelta]:
        """
        Get time since last heartbeat.

        Returns:
            Timedelta since last heartbeat, or None if never connected
        """
        if self._last_heartbeat is None:
            return None

        return datetime.utcnow() - self._last_heartbeat

    def register_connected_callback(self, callback: Callable):
        """Register callback for connection events."""
        self._on_connected_callbacks.append(callback)

    def register_disconnected_callback(self, callback: Callable):
        """Register callback for disconnection events."""
        self._on_disconnected_callbacks.append(callback)

    def register_error_callback(self, callback: Callable):
        """Register callback for error events."""
        self._on_error_callbacks.append(callback)

    def get_status(self) -> dict:
        """
        Get connection status.

        Returns:
            Dictionary with connection details
        """
        return {
            'state': self.state_machine.state.name,
            'is_connected': self.is_connected(),
            'is_ready': self.is_ready(),
            'host': self.host,
            'port': self.port,
            'client_id': self.client_id,
            'connection_duration': (
                self.get_connection_duration().total_seconds()
                if self.get_connection_duration()
                else None
            ),
            'last_heartbeat_age': (
                self.get_last_heartbeat_age().total_seconds()
                if self.get_last_heartbeat_age()
                else None
            ),
            'reconnect_attempts': self.reconnect_strategy.attempt_count,
            'reconnect_stats': self.reconnect_strategy.get_stats()
        }
