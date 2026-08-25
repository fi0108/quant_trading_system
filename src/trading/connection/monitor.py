"""
连接监控器

监控IBKR连接状态，支持自动重连和数据订阅恢复
"""

import logging
import threading
import time
from datetime import datetime
from typing import List, Optional

from common.exceptions import IBKRConnectionError
from common.retry import retry

logger = logging.getLogger(__name__)


class ConnectionMonitor:
    """
    连接状态监控器

    功能：
    - 定期检查连接状态
    - 检测到断线后自动重连
    - 重连后恢复数据订阅
    """

    def __init__(self, connection_manager, check_interval: int = 5):
        """
        初始化监控器

        Args:
            connection_manager: 连接管理器实例
            check_interval: 检查间隔（秒）
        """
        self.connection_manager = connection_manager
        self.check_interval = check_interval
        self.last_heartbeat = time.time()
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.subscribed_symbols: List[str] = []
        self.reconnect_count = 0

    def start(self):
        """启动监控"""
        if self.is_monitoring:
            logger.warning("Connection monitor is already running")
            return

        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, name="ConnectionMonitor", daemon=True)
        self.monitor_thread.start()
        logger.info("Connection monitor started")

    def stop(self):
        """停止监控"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
        logger.info("Connection monitor stopped")

    def update_heartbeat(self):
        """更新心跳时间（收到数据时调用）"""
        self.last_heartbeat = time.time()

    def register_subscription(self, symbol: str):
        """注册数据订阅（用于重连后恢复）"""
        if symbol not in self.subscribed_symbols:
            self.subscribed_symbols.append(symbol)
            logger.debug(f"Registered subscription: {symbol}")

    def unregister_subscription(self, symbol: str):
        """取消数据订阅"""
        if symbol in self.subscribed_symbols:
            self.subscribed_symbols.remove(symbol)
            logger.debug(f"Unregistered subscription: {symbol}")

    def _monitor_loop(self):
        """监控循环"""
        logger.info("Connection monitor loop started")

        while self.is_monitoring:
            try:
                # 检查连接状态
                if not self._check_connection():
                    logger.warning("Connection check failed, initiating reconnect...")
                    self._handle_disconnect()

                # 检查心跳超时（60秒无数据）
                self._check_heartbeat_timeout()

            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)

            time.sleep(self.check_interval)

        logger.info("Connection monitor loop stopped")

    def _check_connection(self) -> bool:
        """
        检查连接状态

        Returns:
            True: 连接正常
            False: 连接断开
        """
        try:
            return self.connection_manager.is_connected()
        except Exception as e:
            logger.error(f"Error checking connection: {e}")
            return False

    def _check_heartbeat_timeout(self):
        """检查心跳超时"""
        elapsed = time.time() - self.last_heartbeat

        # 60秒无数据认为心跳超时
        if elapsed > 60:
            logger.warning(f"Heartbeat timeout: no data received for {elapsed:.0f}s")
            # 可以选择触发告警或重连
            # 这里只记录日志，不主动重连（等待下次连接检查）

    @retry(max_attempts=3, backoff=2.0, exceptions=(IBKRConnectionError,))
    def _handle_disconnect(self):
        """
        处理断线

        尝试重连并恢复数据订阅
        """
        self.reconnect_count += 1
        logger.info(f"Handling disconnect (reconnect attempt #{self.reconnect_count})...")

        try:
            # 1. 断开旧连接
            self._cleanup_old_connection()

            # 2. 重新连接
            self._reconnect()

            # 3. 恢复数据订阅
            self._resubscribe_all()

            logger.info("Reconnection successful")

        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            raise IBKRConnectionError(f"Failed to reconnect: {e}")

    def _cleanup_old_connection(self):
        """清理旧连接"""
        try:
            if self.connection_manager.is_connected():
                self.connection_manager.disconnect()
                logger.debug("Old connection closed")
        except Exception as e:
            logger.warning(f"Error closing old connection: {e}")

    def _reconnect(self):
        """重新连接"""
        logger.info("Attempting to reconnect to IBKR...")

        # 使用新的client_id避免冲突
        original_client_id = self.connection_manager.client_id
        self.connection_manager.client_id = original_client_id + self.reconnect_count

        try:
            self.connection_manager.connect()
            time.sleep(2)  # 等待连接建立

            if not self.connection_manager.is_connected():
                raise IBKRConnectionError("Connection check failed after connect")

            logger.info(f"Reconnected successfully with client_id={self.connection_manager.client_id}")

        except Exception as e:
            logger.error(f"Reconnect failed: {e}")
            # 恢复原client_id
            self.connection_manager.client_id = original_client_id
            raise

    def _resubscribe_all(self):
        """重新订阅所有数据"""
        if not self.subscribed_symbols:
            logger.info("No subscriptions to restore")
            return

        logger.info(f"Restoring {len(self.subscribed_symbols)} subscriptions...")

        success_count = 0
        for symbol in self.subscribed_symbols:
            try:
                self.connection_manager.subscribe_market_data(symbol)
                success_count += 1
                logger.debug(f"Resubscribed: {symbol}")
                time.sleep(0.1)  # 避免过快订阅
            except Exception as e:
                logger.error(f"Failed to resubscribe {symbol}: {e}")

        logger.info(f"Subscription restoration complete: {success_count}/{len(self.subscribed_symbols)} successful")

    def get_status(self) -> dict:
        """
        获取监控状态

        Returns:
            状态字典
        """
        return {
            "is_monitoring": self.is_monitoring,
            "is_connected": self._check_connection(),
            "last_heartbeat": datetime.fromtimestamp(self.last_heartbeat).isoformat(),
            "seconds_since_heartbeat": time.time() - self.last_heartbeat,
            "reconnect_count": self.reconnect_count,
            "subscribed_symbols_count": len(self.subscribed_symbols),
            "subscribed_symbols": self.subscribed_symbols.copy(),
        }


class NetworkErrorHandler:
    """
    网络错误处理器

    处理各种网络相关异常
    """

    @staticmethod
    @retry(max_attempts=3, backoff=1.5, exceptions=(TimeoutError, ConnectionError))
    def request_with_retry(func, *args, **kwargs):
        """
        带重试的网络请求

        Args:
            func: 要执行的函数
            *args, **kwargs: 函数参数

        Returns:
            函数返回值
        """
        try:
            return func(*args, **kwargs)
        except TimeoutError as e:
            logger.warning(f"Request timeout: {e}")
            raise
        except ConnectionError as e:
            logger.warning(f"Connection error: {e}")
            raise

    @staticmethod
    def is_network_error(exception: Exception) -> bool:
        """
        判断是否为网络错误

        Args:
            exception: 异常对象

        Returns:
            True: 网络错误
            False: 其他错误
        """
        network_errors = (TimeoutError, ConnectionError, IBKRConnectionError, OSError)

        if isinstance(exception, network_errors):
            return True

        # 检查错误信息中的关键字
        error_msg = str(exception).lower()
        keywords = ["timeout", "connection", "network", "socket", "unreachable"]

        return any(keyword in error_msg for keyword in keywords)
