"""
监控模型定义

定义告警数据结构、处理器基类等
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """告警数据类"""

    alert_type: str  # 告警类型: system/strategy/risk/data
    severity: str  # 严重程度: info/warning/error/critical
    message: str  # 告警消息
    context: Dict[str, Any] = field(default_factory=dict)  # 上下文信息
    timestamp: float = 0.0  # 时间戳

    def get_fingerprint(self) -> str:
        """
        生成告警指纹（用于去重）

        Returns:
            告警指纹字符串
        """
        return f"{self.alert_type}:{self.message}"

    def __str__(self):
        return f"[{self.severity.upper()}] [{self.alert_type}] {self.message}"


@dataclass
class AlertRecord:
    """告警记录（用于去重）"""

    fingerprint: str  # 告警指纹
    first_seen: float  # 首次出现时间
    last_seen: float  # 最后出现时间
    count: int  # 出现次数
    alert: Alert  # 告警对象


class AlertHandler(ABC):
    """告警处理器抽象基类"""

    @abstractmethod
    def handle(self, alert: Alert, summary: Optional[str] = None):
        """
        处理告警

        Args:
            alert: 告警对象
            summary: 告警摘要（如去重信息）
        """
        pass


class LoggingAlertHandler(AlertHandler):
    """日志告警处理器"""

    def handle(self, alert: Alert, summary: Optional[str] = None):
        """写入日志"""
        suffix = f" {summary}" if summary else ""

        log_func = {
            "info": logger.info,
            "warning": logger.warning,
            "error": logger.error,
            "critical": logger.critical,
        }.get(alert.severity, logger.warning)

        log_func(f"[ALERT] [{alert.alert_type}] {alert.message}{suffix}")


class ConsoleAlertHandler(AlertHandler):
    """控制台告警处理器（仅严重告警）"""

    def handle(self, alert: Alert, summary: Optional[str] = None):
        """打印到控制台"""
        if alert.severity in ["error", "critical"]:
            suffix = f" {summary}" if summary else ""
            print(f"🚨 [ALERT] {alert.message}{suffix}")


class AlertStats:
    """告警统计信息"""

    def __init__(self):
        self.total_sent = 0
        self.total_deduplicated = 0
        self.by_type: Dict[str, int] = {}
        self.by_severity: Dict[str, int] = {}

    def record_sent(self, alert: Alert):
        """记录已发送告警"""
        self.total_sent += 1
        self.by_type[alert.alert_type] = self.by_type.get(alert.alert_type, 0) + 1
        self.by_severity[alert.severity] = self.by_severity.get(alert.severity, 0) + 1

    def record_deduplicated(self, alert: Alert):
        """记录已去重告警"""
        self.total_deduplicated += 1

    def get_summary(self) -> Dict[str, Any]:
        """获取统计摘要"""
        return {
            "total_sent": self.total_sent,
            "total_deduplicated": self.total_deduplicated,
            "by_type": self.by_type.copy(),
            "by_severity": self.by_severity.copy(),
        }

    def reset(self):
        """重置统计"""
        self.total_sent = 0
        self.total_deduplicated = 0
        self.by_type.clear()
        self.by_severity.clear()
