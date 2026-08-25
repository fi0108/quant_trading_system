"""
告警管理器

统一管理所有告警，支持去重、多处理器
"""

import logging
import time
from typing import Any, Dict, List, Optional

from monitor.alert_deduplicator import AlertDeduplicator
from monitor.models import Alert, AlertHandler, AlertStats, ConsoleAlertHandler, LoggingAlertHandler

logger = logging.getLogger(__name__)


class AlertManager:
    """
    告警管理器

    功能：
    - 告警去重
    - 多处理器支持
    - 统计信息
    """

    def __init__(self, dedup_window: int = 300, max_count: int = 10):
        """
        初始化告警管理器

        Args:
            dedup_window: 去重时间窗口（秒）
            max_count: 窗口内最大告警次数
        """
        self.deduplicator = AlertDeduplicator(window=dedup_window, max_count=max_count)
        self.handlers: List[AlertHandler] = []
        self.stats = AlertStats()

        # 添加默认处理器
        self._add_default_handlers()

        logger.info("AlertManager initialized")

    def send_alert(self, alert_type: str, severity: str, message: str, context: Dict[str, Any] = None):
        """
        发送告警

        Args:
            alert_type: 告警类型（system/strategy/risk/data）
            severity: 严重程度（info/warning/error/critical）
            message: 告警消息
            context: 上下文信息
        """
        alert = Alert(
            alert_type=alert_type, severity=severity, message=message, context=context or {}, timestamp=time.time()
        )

        # 去重检查
        should_send, summary = self.deduplicator.should_send(alert)

        if should_send:
            # 发送到所有处理器
            for handler in self.handlers:
                try:
                    handler.handle(alert, summary)
                except Exception as e:
                    logger.error(f"Alert handler error: {e}", exc_info=True)

            self.stats.record_sent(alert)
        else:
            self.stats.record_deduplicated(alert)
            logger.debug(f"Alert deduplicated: {message} ({summary})")

    def add_handler(self, handler: AlertHandler):
        """
        添加告警处理器

        Args:
            handler: 告警处理器实例
        """
        self.handlers.append(handler)
        logger.info(f"Added alert handler: {handler.__class__.__name__}")

    def remove_handler(self, handler: AlertHandler):
        """
        移除告警处理器

        Args:
            handler: 告警处理器实例
        """
        if handler in self.handlers:
            self.handlers.remove(handler)
            logger.info(f"Removed alert handler: {handler.__class__.__name__}")

    def _add_default_handlers(self):
        """添加默认处理器"""
        self.handlers.append(LoggingAlertHandler())
        self.handlers.append(ConsoleAlertHandler())

    def cleanup_expired(self):
        """清理过期的去重记录"""
        self.deduplicator.cleanup_expired()

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        return {"alert_stats": self.stats.get_summary(), "dedup_stats": self.deduplicator.get_stats()}

    def reset_stats(self):
        """重置统计信息"""
        self.stats.reset()
        logger.info("AlertManager stats reset")


# 全局告警管理器实例
_global_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """
    获取全局告警管理器实例

    Returns:
        AlertManager实例
    """
    global _global_alert_manager

    if _global_alert_manager is None:
        _global_alert_manager = AlertManager()

    return _global_alert_manager


def send_alert(alert_type: str, severity: str, message: str, context: Dict[str, Any] = None):
    """
    发送告警的便捷函数

    Args:
        alert_type: 告警类型
        severity: 严重程度
        message: 告警消息
        context: 上下文信息
    """
    manager = get_alert_manager()
    manager.send_alert(alert_type, severity, message, context)
