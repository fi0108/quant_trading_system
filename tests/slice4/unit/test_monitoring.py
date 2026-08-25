"""
监控模块 - 单元测试
"""

import time
from unittest.mock import Mock, patch

import pytest

from monitor.alert_deduplicator import AlertDeduplicator
from monitor.alert_manager import AlertManager
from monitor.models import Alert, AlertRecord
from monitor.strategy_monitor import StrategyMonitor
from monitor.system_monitor import SystemMonitor


class TestAlertDeduplicator:
    """告警去重器测试"""

    def test_first_alert_should_send(self):
        """测试1：首次告警应该发送"""
        dedup = AlertDeduplicator(window=300, max_count=10)

        alert = Alert(alert_type="system", severity="warning", message="Test alert", timestamp=time.time())

        should_send, summary = dedup.should_send(alert)

        assert should_send is True
        assert summary is None

    def test_duplicate_alert_within_window(self):
        """测试2：时间窗口内重复告警去重"""
        dedup = AlertDeduplicator(window=300, max_count=10)

        alert = Alert(alert_type="system", severity="warning", message="Test alert", timestamp=time.time())

        # 第一次发送
        should_send1, _ = dedup.should_send(alert)
        assert should_send1 is True

        # 第二次去重
        should_send2, summary2 = dedup.should_send(alert)
        assert should_send2 is False
        assert "Deduplicated" in summary2

    def test_alert_after_window_expires(self):
        """测试3：时间窗口过期后重新发送"""
        dedup = AlertDeduplicator(window=2, max_count=10)  # 2秒窗口

        alert = Alert(alert_type="system", severity="warning", message="Test alert", timestamp=time.time())

        # 第一次发送
        should_send1, _ = dedup.should_send(alert)
        assert should_send1 is True

        # 第二次去重
        should_send2, _ = dedup.should_send(alert)
        assert should_send2 is False

        # 等待窗口过期
        time.sleep(2.5)

        # 第三次应该发送（带摘要）
        should_send3, summary3 = dedup.should_send(alert)
        assert should_send3 is True
        assert "repeated" in summary3

    def test_rate_limit_exceeded(self):
        """测试4：频率限制"""
        dedup = AlertDeduplicator(window=300, max_count=3)

        alert = Alert(alert_type="system", severity="warning", message="Test alert", timestamp=time.time())

        # 发送4次
        results = []
        for i in range(4):
            should_send, summary = dedup.should_send(alert)
            results.append((should_send, summary))

        # 第1次发送
        assert results[0][0] is True

        # 第2-3次去重但记录
        assert results[1][0] is False
        assert results[2][0] is False

        # 第4次超过频率限制
        assert results[3][0] is False
        assert "Rate limit exceeded" in results[3][1]

    def test_cleanup_expired(self):
        """测试5：清理过期记录"""
        dedup = AlertDeduplicator(window=1, max_count=10)  # 1秒窗口

        alert = Alert(alert_type="system", severity="warning", message="Test alert", timestamp=time.time())

        dedup.should_send(alert)
        assert len(dedup.cache) == 1

        # 等待过期
        time.sleep(2.5)

        dedup.cleanup_expired()
        assert len(dedup.cache) == 0


class TestAlertManager:
    """告警管理器测试"""

    def test_manager_initialization(self):
        """测试1：管理器初始化"""
        manager = AlertManager()

        assert manager.deduplicator is not None
        assert len(manager.handlers) >= 2  # 默认有日志和控制台处理器
        assert manager.stats is not None

    def test_send_alert(self):
        """测试2：发送告警"""
        manager = AlertManager()

        manager.send_alert(alert_type="system", severity="warning", message="Test alert")

        stats = manager.get_stats()
        assert stats["alert_stats"]["total_sent"] == 1

    def test_alert_deduplication(self):
        """测试3：告警去重"""
        manager = AlertManager(dedup_window=300, max_count=10)

        # 发送相同告警3次
        for i in range(3):
            manager.send_alert(alert_type="system", severity="warning", message="Same alert")

        stats = manager.get_stats()
        assert stats["alert_stats"]["total_sent"] == 1
        assert stats["alert_stats"]["total_deduplicated"] == 2

    def test_get_stats(self):
        """测试4：获取统计信息"""
        manager = AlertManager()

        manager.send_alert("system", "warning", "Alert 1")
        manager.send_alert("strategy", "error", "Alert 2")

        stats = manager.get_stats()

        assert "alert_stats" in stats
        assert "dedup_stats" in stats
        assert stats["alert_stats"]["total_sent"] == 2


class TestSystemMonitor:
    """系统资源监控器测试"""

    def test_get_cpu_metrics(self):
        """测试1：获取CPU指标"""
        monitor = SystemMonitor()

        if monitor.psutil_available:
            metrics = monitor.get_cpu_metrics()

            assert "cpu_percent" in metrics
            assert 0 <= metrics["cpu_percent"] <= 100

    def test_get_memory_metrics(self):
        """测试2：获取内存指标"""
        monitor = SystemMonitor()

        if monitor.psutil_available:
            metrics = monitor.get_memory_metrics()

            assert "memory_percent" in metrics
            assert 0 <= metrics["memory_percent"] <= 100

    def test_get_disk_metrics(self):
        """测试3：获取磁盘指标"""
        monitor = SystemMonitor()

        if monitor.psutil_available:
            metrics = monitor.get_disk_metrics()

            assert "disk_usage" in metrics
            assert 0 <= metrics["disk_usage"] <= 100

    def test_threshold_alert(self):
        """测试4：超过阈值告警"""
        alert_manager = AlertManager()
        monitor = SystemMonitor(alert_manager=alert_manager)

        # 模拟超过阈值的指标
        metrics = {"cpu_percent": 90, "memory_percent": 50}  # 超过80%阈值

        monitor.check_thresholds(metrics)

        stats = alert_manager.get_stats()
        assert stats["alert_stats"]["total_sent"] >= 1

    def test_history_recording(self):
        """测试5：历史数据记录"""
        monitor = SystemMonitor()

        # 记录几个数据点
        for i in range(5):
            metrics = {"cpu_percent": 50 + i, "memory_percent": 60 + i}
            monitor.record_history(metrics)

        assert len(monitor.history["cpu_percent"]) == 5
        assert len(monitor.history["memory_percent"]) == 5

        # 测试历史统计
        stats = monitor.get_history_stats("cpu_percent")
        assert "current" in stats
        assert "min" in stats
        assert "max" in stats
        assert "avg" in stats


class TestStrategyMonitor:
    """策略状态监控器测试"""

    def test_heartbeat_normal(self):
        """测试1：正常心跳"""
        monitor = StrategyMonitor()

        monitor.update_heartbeat()
        is_timeout = monitor.check_heartbeat()

        assert is_timeout is False

    def test_heartbeat_timeout(self):
        """测试2：心跳超时告警"""
        alert_manager = AlertManager()
        monitor = StrategyMonitor(alert_manager=alert_manager)

        # 设置较短的超时时间
        monitor.heartbeat_timeout = 1

        # 等待超时
        time.sleep(1.5)

        is_timeout = monitor.check_heartbeat()

        assert is_timeout is True
        assert monitor.heartbeat_alerted is True

    def test_heartbeat_recovery(self):
        """测试3：心跳恢复通知"""
        alert_manager = AlertManager()
        monitor = StrategyMonitor(alert_manager=alert_manager)

        monitor.heartbeat_timeout = 1
        time.sleep(1.5)

        # 触发超时告警
        monitor.check_heartbeat()
        assert monitor.heartbeat_alerted is True

        # 恢复心跳
        monitor.update_heartbeat()
        assert monitor.heartbeat_alerted is False

    def test_record_order_latency(self):
        """测试4：记录订单延迟"""
        monitor = StrategyMonitor()

        # 记录几个延迟
        latencies = [0.5, 1.0, 1.5, 2.0, 0.8]
        for latency in latencies:
            monitor.record_order_latency(latency)

        assert len(monitor.order_latencies) == 5

        # 获取统计
        stats = monitor.get_latency_stats()
        assert stats["count"] == 5
        assert stats["min"] == 0.5
        assert stats["max"] == 2.0
        assert "avg" in stats
        assert "p95" in stats

    def test_indicator_update(self):
        """测试5：指标更新记录"""
        monitor = StrategyMonitor()

        monitor.record_indicator_update("SMA_10")
        monitor.record_indicator_update("SMA_20")

        assert len(monitor.indicator_updates) == 2
        assert "SMA_10" in monitor.indicator_updates
        assert "SMA_20" in monitor.indicator_updates


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
