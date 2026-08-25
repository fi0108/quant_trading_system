"""
Connection Manager for IBKR Gateway with Auto-Reconnect.

Manages connection lifecycle:
- Establish connection to IB Gateway/TWS
- Maintain heartbeat monitoring
- Handle disconnections and automatic reconnections
- Monitor connection health
"""

import time
from datetime import datetime
from threading import Event, Thread
from typing import Callable, List, Optional

from ib_insync import IB

from common.config import config
from common.logger import log

from .reconnect import ReconnectStrategy


class ConnectionManager:
    """
    Manages IBKR Gateway connection with auto-reconnect.

    Features:
    - Automatic connection with timeout
    - Heartbeat monitoring (30s interval)
    - Automatic reconnection with exponential backoff
    - Connection state tracking
    - Event callbacks
    """

    HEARTBEAT_INTERVAL = 30  # seconds
    HEARTBEAT_TIMEOUT = 60  # seconds (2x interval)
    DEFAULT_TIMEOUT = 15  # seconds

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4001,
        client_id: int = 1,
        timeout: int = DEFAULT_TIMEOUT,
        readonly: bool = False,
        auto_reconnect: bool = True,
    ):
        """
        Initialize connection manager.

        Args:
            host: IB Gateway host
            port: IB Gateway port (4001 for Gateway, 7497 for TWS)
            client_id: Client ID for connection
            timeout: Connection timeout in seconds
            readonly: If True, connect in read-only mode
            auto_reconnect: Enable automatic reconnection
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self._initial_client_id = client_id  # 记住初始 client_id
        self._max_client_id = client_id + 9  # 允许切换到 client_id+9
        self.timeout = timeout
        self.readonly = readonly
        self.auto_reconnect = auto_reconnect

        # Connection objects
        self.ib = IB()
        self.reconnect_strategy = ReconnectStrategy()

        # State tracking
        self._is_connected = False
        self._is_connecting = False
        self._client_id_conflict = False  # 标记 client_id 冲突
        self._last_heartbeat: Optional[datetime] = None
        self._should_stop = Event()

        # Background threads
        self._heartbeat_thread: Optional[Thread] = None
        self._reconnect_thread: Optional[Thread] = None

        # Callbacks
        self._on_connected_callbacks: List[Callable] = []
        self._on_disconnected_callbacks: List[Callable] = []
        self._on_reconnecting_callbacks: List[Callable] = []

        # Setup IB event handlers
        self._setup_event_handlers()

    @classmethod
    def from_config(cls):
        """
        Create ConnectionManager from unified config.

        Returns:
            ConnectionManager instance
        """
        return cls(
            host=config.get("ibkr.host", "127.0.0.1"),
            port=config.get("ibkr.port", 4001),
            client_id=config.get("ibkr.client_id", 1),
            timeout=config.get("ibkr.timeout", cls.DEFAULT_TIMEOUT),
            readonly=config.get("ibkr.read_only", False),
            auto_reconnect=config.get("ibkr.auto_reconnect", True),
        )

    def _setup_event_handlers(self):
        """Setup IB event handlers."""
        self.ib.connectedEvent += self._on_ib_connected
        self.ib.disconnectedEvent += self._on_ib_disconnected
        self.ib.errorEvent += self._on_ib_error

    def _on_ib_connected(self):
        """Handle IB connected event."""
        self._is_connected = True
        self._is_connecting = False
        self._last_heartbeat = datetime.now()
        self.reconnect_strategy.record_success()

        log.info(f"Connected to IBKR Gateway at {self.host}:{self.port}")

        # Start heartbeat
        self._start_heartbeat_thread()

        # Trigger callbacks
        for callback in self._on_connected_callbacks:
            try:
                callback()
            except Exception as e:
                log.error(f"Error in connected callback: {e}")

    def _on_ib_disconnected(self):
        """Handle IB disconnected event."""
        was_connected = self._is_connected
        self._is_connected = False
        self._is_connecting = False

        log.warning(f"Disconnected from IBKR Gateway")

        # Stop heartbeat
        self._stop_heartbeat_thread()

        # Trigger callbacks
        for callback in self._on_disconnected_callbacks:
            try:
                callback()
            except Exception as e:
                log.error(f"Error in disconnected callback: {e}")

        # Start reconnection if enabled and was previously connected
        if self.auto_reconnect and was_connected and not self._should_stop.is_set():
            self._start_reconnect_thread()

    def _on_ib_error(self, reqId, errorCode, errorString, contract):
        """Handle IB error event."""
        # Filter out informational messages
        if errorCode in [2104, 2106, 2158]:  # Market data farm connection messages
            return

        log.warning(f"IBKR Error {errorCode}: {errorString}")

        # Client ID already in use
        if errorCode == 326:
            log.error(f"Client ID {self.client_id} already in use!")
            self._client_id_conflict = True
            # 断开当前尝试
            if self.ib.isConnected():
                try:
                    self.ib.disconnect()
                except:
                    pass

        # Connection lost errors
        if errorCode in [1100, 2110]:
            log.error("Connection lost detected")
            self._is_connected = False

    def connect(self, retry_on_conflict: bool = True) -> bool:
        """
        Establish connection to IB Gateway.

        Args:
            retry_on_conflict: 如果 client_id 冲突，自动尝试下一个

        Returns:
            True if connection successful
        """
        if self.is_connected():
            log.info("Already connected")
            return True

        self._is_connecting = True
        log.info(f"Connecting to {self.host}:{self.port} with client_id={self.client_id}...")

        try:
            self.ib.connect(
                host=self.host, port=self.port, clientId=self.client_id, readonly=self.readonly, timeout=self.timeout
            )

            # Wait a bit for connection to stabilize
            time.sleep(0.5)

            if self.ib.isConnected():
                self._is_connecting = False
                return True
            else:
                self._is_connecting = False
                log.error("Connection failed")
                return False

        except Exception as e:
            self._is_connecting = False

            # 方案：等待一小段时间，检查 error event 是否设置了冲突标记
            time.sleep(0.2)

            if self._client_id_conflict and retry_on_conflict:
                log.warning(f"Client ID {self.client_id} conflict confirmed, trying next ID...")
                return self._try_next_client_id()

            # 其他错误
            log.error(f"Connection error: {e}")
            return False

    def _try_next_client_id(self) -> bool:
        """
        尝试使用下一个 client_id 连接

        Returns:
            True if connection successful
        """
        # 切换到下一个 client_id
        original_id = self.client_id
        self.client_id += 1

        # 如果超过最大值，循环回初始值
        if self.client_id > self._max_client_id:
            self.client_id = self._initial_client_id

        # 避免无限循环
        if self.client_id == original_id:
            log.error("All client IDs exhausted, cannot connect")
            return False

        log.info(f"Switching from client_id {original_id} to {self.client_id}")

        # 重置冲突标记
        self._client_id_conflict = False

        # 用新 ID 重试
        return self.connect(retry_on_conflict=True)

    def disconnect(self):
        """Disconnect from IB Gateway."""
        self._should_stop.set()

        # Stop threads
        self._stop_heartbeat_thread()
        self._stop_reconnect_thread()

        # Disconnect and cleanup
        if self.ib.isConnected():
            try:
                # 主动断开，让 Gateway 释放 client_id
                self.ib.disconnect()
                log.info(f"Disconnected from IBKR Gateway (client_id={self.client_id})")

                # 等待 Gateway 清理连接
                time.sleep(1)
            except Exception as e:
                log.error(f"Error during disconnect: {e}")

        self._is_connected = False

    def _start_heartbeat_thread(self):
        """Start heartbeat monitoring thread."""
        if self._heartbeat_thread is None or not self._heartbeat_thread.is_alive():
            self._heartbeat_thread = Thread(target=self._heartbeat_loop, daemon=True)
            self._heartbeat_thread.start()
            log.debug("Heartbeat thread started")

    def _stop_heartbeat_thread(self):
        """Stop heartbeat monitoring thread."""
        # Thread will stop on next check
        pass

    def _heartbeat_loop(self):
        """Heartbeat monitoring loop."""
        while not self._should_stop.is_set() and self._is_connected:
            time.sleep(self.HEARTBEAT_INTERVAL)

            if not self._is_connected:
                break

            # Check if connection is still alive
            if self.ib.isConnected():
                self._last_heartbeat = datetime.now()
                log.debug("Heartbeat OK")
            else:
                log.warning("Heartbeat: Connection lost")
                self._is_connected = False
                # Will trigger reconnect via disconnected event
                break

            # Check for timeout
            if self._last_heartbeat:
                age = (datetime.now() - self._last_heartbeat).total_seconds()
                if age > self.HEARTBEAT_TIMEOUT:
                    log.error(f"Heartbeat timeout ({age:.0f}s)")
                    self._is_connected = False
                    self.ib.disconnect()
                    break

        log.debug("Heartbeat thread stopped")

    def _start_reconnect_thread(self):
        """Start reconnection thread."""
        if self._reconnect_thread is None or not self._reconnect_thread.is_alive():
            self._reconnect_thread = Thread(target=self._reconnect_loop, daemon=True)
            self._reconnect_thread.start()
            log.info("Reconnect thread started")

    def _stop_reconnect_thread(self):
        """Stop reconnection thread."""
        # Thread will stop on next check
        pass

    def _reconnect_loop(self):
        """Reconnection loop with exponential backoff."""
        log.info("Starting reconnection attempts...")

        # Trigger reconnecting callbacks
        for callback in self._on_reconnecting_callbacks:
            try:
                callback()
            except Exception as e:
                log.error(f"Error in reconnecting callback: {e}")

        while self.reconnect_strategy.has_attempts_remaining and not self._should_stop.is_set():
            # Wait for delay
            if not self.reconnect_strategy.should_retry_now():
                delay = self.reconnect_strategy.get_delay()
                log.info(f"Waiting {delay}s before reconnect attempt {self.reconnect_strategy.attempt_count + 1}")
                time.sleep(delay)

            if self._should_stop.is_set():
                break

            # Record attempt
            self.reconnect_strategy.record_attempt()
            attempt_num = self.reconnect_strategy.attempt_count
            max_attempts = self.reconnect_strategy.max_retries

            log.info(f"Reconnect attempt {attempt_num}/{max_attempts}")

            # Try to connect
            try:
                success = self.connect()
                if success:
                    log.info("Reconnection successful")
                    return
            except Exception as e:
                log.error(f"Reconnect attempt {attempt_num} failed: {e}")

        log.error(f"Reconnection failed after {self.reconnect_strategy.max_retries} attempts")

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._is_connected and self.ib.isConnected()

    def register_connected_callback(self, callback: Callable):
        """Register callback for connection events."""
        self._on_connected_callbacks.append(callback)

    def register_disconnected_callback(self, callback: Callable):
        """Register callback for disconnection events."""
        self._on_disconnected_callbacks.append(callback)

    def register_reconnecting_callback(self, callback: Callable):
        """Register callback for reconnection start events."""
        self._on_reconnecting_callbacks.append(callback)

    def get_status(self) -> dict:
        """
        Get connection status.

        Returns:
            Dictionary with connection details
        """
        return {
            "is_connected": self.is_connected(),
            "is_connecting": self._is_connecting,
            "host": self.host,
            "port": self.port,
            "client_id": self.client_id,
            "last_heartbeat": self._last_heartbeat,
            "reconnect_attempts": self.reconnect_strategy.attempt_count,
            "auto_reconnect": self.auto_reconnect,
            "reconnect_stats": self.reconnect_strategy.get_stats(),
        }
