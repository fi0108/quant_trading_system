"""
策略状态监控器

监控策略心跳、指标延迟、订单执行延迟
"""

import logging
import threading
import time
from typing import Any, Dict, List, Optional

from monitor.alert_manager import AlertManager

logger = logging.getLogger(__name__)


class StrategyMonitor:
    """
    策略状态监控器

    功能：
    - 心跳检测（60秒无数据告警）
    - 指标计算延迟监控
    - 订单执行延迟监控
    """

    def __init__(self, alert_manager: Optional[AlertManager] = None):
        """
        初始化策略监控器

        Args:
            alert_manager: 告警管理器实例
        """
        self.alert_manager = alert_manager

        # 心跳
        self.last_heartbeat = time.time()
        self.heartbeat_timeout = 60  # 60秒
        self.heartbeat_alerted = False

        # 指标延迟
        self.indicator_updates: Dict[str, float] = {}  # {indicator_name: timestamp}
        self.indicator_timeout = 120  # 2分钟

        # 订单延迟
        self.order_latencies: List[float] = []
        self.max_latency_samples = 100
        self.high_latency_threshold = 5.0  # 5秒

        # 监控状态
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None

    def update_heartbeat(self):
        """更新心跳（收到数据时调用）"""
        self.last_heartbeat = time.time()

        # 如果之前告警过，现在恢复了
        if self.heartbeat_alerted:
            if self.alert_manager:
                self.alert_manager.send_alert(
                    alert_type="strategy", severity="info", message="Strategy heartbeat recovered"
                )
            self.heartbeat_alerted = False
            logger.info("Strategy heartbeat recovered")

    def check_heartbeat(self) -> bool:
        """
        检查心跳超时

        Returns:
            True: 超时
            False: 正常
        """
        elapsed = time.time() - self.last_heartbeat

        if elapsed > self.heartbeat_timeout:
            if not self.heartbeat_alerted and self.alert_manager:
                self.alert_manager.send_alert(
                    alert_type="strategy",
                    severity="error",
                    message=f"Strategy heartbeat timeout: {elapsed:.0f}s",
                    context={"elapsed": elapsed, "timeout": self.heartbeat_timeout},
                )
                self.heartbeat_alerted = True

            return True

        return False

    def record_indicator_update(self, indicator_name: str):
        """
        记录指标更新

        Args:
            indicator_name: 指标名称
        """
        self.indicator_updates[indicator_name] = time.time()
        logger.debug(f"Indicator updated: {indicator_name}")

    def check_indicator_delays(self):
        """检查指标计算延迟"""
        now = time.time()

        for name, last_update in self.indicator_updates.items():
            delay = now - last_update

            if delay > self.indicator_timeout:
                if self.alert_manager:
                    self.alert_manager.send_alert(
                        alert_type="strategy",
                        severity="warning",
                        message=f"Indicator update timeout: {name} ({delay:.0f}s)",
                        context={"indicator": name, "delay": delay, "timeout": self.indicator_timeout},
                    )

    def record_order_latency(self, latency: float):
        """
        记录订单延迟

        Args:
            latency: 延迟时间（秒）
        """
        self.order_latencies.append(latency)

        # 限制样本数量
        if len(self.order_latencies) > self.max_latency_samples:
            self.order_latencies.pop(0)

        logger.debug(f"Order latency recorded: {latency:.3f}s")

        # 检查高延迟
        if latency > self.high_latency_threshold:
            if self.alert_manager:
                self.alert_manager.send_alert(
                    alert_type="strategy",
                    severity="warning",
                    message=f"High order latency: {latency:.2f}s",
                    context={"latency": latency, "threshold": self.high_latency_threshold},
                )

    def get_latency_stats(self) -> Dict[str, float]:
        """
        获取延迟统计

        Returns:
            统计信息字典
        """
        if not self.order_latencies:
            return {}

        sorted_latencies = sorted(self.order_latencies)

        return {
            "count": len(self.order_latencies),
            "min": min(self.order_latencies),
            "max": max(self.order_latencies),
            "avg": sum(self.order_latencies) / len(self.order_latencies),
            "p50": self._percentile(sorted_latencies, 0.50),
            "p95": self._percentile(sorted_latencies, 0.95),
            "p99": self._percentile(sorted_latencies, 0.99),
        }

    def _percentile(self, sorted_data: List[float], p: float) -> float:
        """
        计算百分位数

        Args:
            sorted_data: 已排序的数据
            p: 百分位（0-1）

        Returns:
            百分位值
        """
        if not sorted_data:
            return 0.0

        index = int(len(sorted_data) * p)
        return sorted_data[min(index, len(sorted_data) - 1)]

    def start_monitoring(self, check_interval: int = 30):
        """
        启动监控

        Args:
            check_interval: 检查间隔（秒）
        """
        if self.monitoring:
            logger.warning("StrategyMonitor is already running")
            return

        self.monitoring = True

        def monitor_loop():
            logger.info("StrategyMonitor loop started")

            while self.monitoring:
                try:
                    self.check_heartbeat()
                    self.check_indicator_delays()
                except Exception as e:
                    logger.error(f"Error in strategy monitor loop: {e}", exc_info=True)

                time.sleep(check_interval)

            logger.info("StrategyMonitor loop stopped")

        self.monitor_thread = threading.Thread(target=monitor_loop, name="StrategyMonitor", daemon=True)
        self.monitor_thread.start()
        logger.info(f"StrategyMonitor started, interval: {check_interval}s")

    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False

        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)

        logger.info("StrategyMonitor stopped")

    def get_status(self) -> Dict[str, Any]:
        """
        获取监控状态

        Returns:
            状态字典
        """
        now = time.time()
        heartbeat_elapsed = now - self.last_heartbeat

        return {
            "monitoring": self.monitoring,
            "heartbeat_elapsed": heartbeat_elapsed,
            "heartbeat_timeout": self.heartbeat_timeout,
            "heartbeat_ok": heartbeat_elapsed <= self.heartbeat_timeout,
            "indicators_count": len(self.indicator_updates),
            "order_latency_samples": len(self.order_latencies),
        }

    def reset_stats(self):
        """重置统计数据"""
        self.order_latencies.clear()
        logger.info("StrategyMonitor stats reset")
