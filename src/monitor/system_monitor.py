"""
系统资源监控器

监控CPU、内存、磁盘等系统资源
"""

import logging
import threading
import time
from typing import Any, Dict, List, Optional

try:
    import psutil
except ImportError:
    psutil = None
    print("Warning: psutil not installed, system monitoring will be disabled")

from monitor.alert_manager import AlertManager

logger = logging.getLogger(__name__)


class SystemMonitor:
    """
    系统资源监控器

    功能：
    - 监控CPU、内存、磁盘使用率
    - 超过阈值时告警
    - 记录历史数据
    """

    def __init__(self, alert_manager: Optional[AlertManager] = None):
        """
        初始化系统监控器

        Args:
            alert_manager: 告警管理器实例
        """
        self.alert_manager = alert_manager
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None

        # 阈值配置
        self.thresholds = {"cpu_percent": 80, "memory_percent": 80, "disk_usage": 90}

        # 历史数据
        self.history: Dict[str, List[float]] = {"cpu_percent": [], "memory_percent": [], "disk_usage": []}
        self.history_max_size = 60  # 保留60个数据点

        # psutil可用性检查
        self.psutil_available = psutil is not None

    def get_cpu_metrics(self) -> Dict[str, float]:
        """
        获取CPU指标

        Returns:
            CPU指标字典
        """
        if not self.psutil_available:
            return {}

        try:
            return {"cpu_percent": psutil.cpu_percent(interval=1), "cpu_count": psutil.cpu_count()}
        except Exception as e:
            logger.error(f"Error getting CPU metrics: {e}")
            return {}

    def get_memory_metrics(self) -> Dict[str, float]:
        """
        获取内存指标

        Returns:
            内存指标字典
        """
        if not self.psutil_available:
            return {}

        try:
            mem = psutil.virtual_memory()
            return {
                "memory_percent": mem.percent,
                "memory_total": mem.total / (1024**3),  # GB
                "memory_available": mem.available / (1024**3),  # GB
                "memory_used": mem.used / (1024**3),  # GB
            }
        except Exception as e:
            logger.error(f"Error getting memory metrics: {e}")
            return {}

    def get_disk_metrics(self, path: str = ".") -> Dict[str, float]:
        """
        获取磁盘指标

        Args:
            path: 磁盘路径

        Returns:
            磁盘指标字典
        """
        if not self.psutil_available:
            return {}

        try:
            disk = psutil.disk_usage(path)
            return {
                "disk_usage": disk.percent,
                "disk_total": disk.total / (1024**3),  # GB
                "disk_used": disk.used / (1024**3),  # GB
                "disk_free": disk.free / (1024**3),  # GB
            }
        except Exception as e:
            logger.error(f"Error getting disk metrics: {e}")
            return {}

    def get_all_metrics(self) -> Dict[str, Any]:
        """
        获取所有系统指标

        Returns:
            所有指标字典
        """
        metrics = {}
        metrics.update(self.get_cpu_metrics())
        metrics.update(self.get_memory_metrics())
        metrics.update(self.get_disk_metrics())
        return metrics

    def check_thresholds(self, metrics: Dict[str, float]):
        """
        检查阈值并告警

        Args:
            metrics: 指标字典
        """
        if not self.alert_manager:
            return

        for key, value in metrics.items():
            threshold = self.thresholds.get(key)

            if threshold and value > threshold:
                self.alert_manager.send_alert(
                    alert_type="system",
                    severity="warning",
                    message=f"{key} exceeds threshold: {value:.1f}% > {threshold}%",
                    context={"metric": key, "value": value, "threshold": threshold},
                )

    def record_history(self, metrics: Dict[str, float]):
        """
        记录历史数据

        Args:
            metrics: 指标字典
        """
        for key in ["cpu_percent", "memory_percent", "disk_usage"]:
            if key in metrics:
                self.history[key].append(metrics[key])

                # 限制历史大小
                if len(self.history[key]) > self.history_max_size:
                    self.history[key].pop(0)

    def get_history_stats(self, key: str) -> Dict[str, float]:
        """
        获取历史统计

        Args:
            key: 指标名称

        Returns:
            统计信息字典
        """
        if key not in self.history or not self.history[key]:
            return {}

        data = self.history[key]
        return {"current": data[-1], "min": min(data), "max": max(data), "avg": sum(data) / len(data)}

    def start_monitoring(self, interval: int = 60):
        """
        启动监控（后台线程）

        Args:
            interval: 检查间隔（秒）
        """
        if not self.psutil_available:
            logger.warning("psutil not available, system monitoring disabled")
            return

        if self.monitoring:
            logger.warning("SystemMonitor is already running")
            return

        self.monitoring = True

        def monitor_loop():
            logger.info("SystemMonitor loop started")

            while self.monitoring:
                try:
                    metrics = self.get_all_metrics()
                    self.record_history(metrics)
                    self.check_thresholds(metrics)
                except Exception as e:
                    logger.error(f"Error in system monitor loop: {e}", exc_info=True)

                time.sleep(interval)

            logger.info("SystemMonitor loop stopped")

        self.monitor_thread = threading.Thread(target=monitor_loop, name="SystemMonitor", daemon=True)
        self.monitor_thread.start()
        logger.info(f"SystemMonitor started, interval: {interval}s")

    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False

        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)

        logger.info("SystemMonitor stopped")

    def set_threshold(self, key: str, value: float):
        """
        设置阈值

        Args:
            key: 指标名称
            value: 阈值
        """
        self.thresholds[key] = value
        logger.info(f"Set threshold: {key} = {value}")

    def get_status(self) -> Dict[str, Any]:
        """
        获取监控状态

        Returns:
            状态字典
        """
        return {
            "monitoring": self.monitoring,
            "psutil_available": self.psutil_available,
            "thresholds": self.thresholds.copy(),
            "history_size": {k: len(v) for k, v in self.history.items()},
        }
