"""
告警去重器

避免短时间内重复发送相同告警
"""

import logging
import time
from typing import Dict, Optional, Tuple

from monitor.models import Alert, AlertRecord

logger = logging.getLogger(__name__)


class AlertDeduplicator:
    """
    告警去重器

    功能：
    - 时间窗口内相同告警去重
    - 频率限制
    - 告警摘要生成
    """

    def __init__(self, window: int = 300, max_count: int = 10):
        """
        初始化去重器

        Args:
            window: 时间窗口（秒），默认300秒（5分钟）
            max_count: 窗口内最大告警次数
        """
        self.window = window
        self.max_count = max_count
        self.cache: Dict[str, AlertRecord] = {}

    def should_send(self, alert: Alert) -> Tuple[bool, Optional[str]]:
        """
        判断是否应该发送告警

        Args:
            alert: 告警对象

        Returns:
            (should_send, summary)
            - should_send: 是否应该发送
            - summary: 告警摘要（如去重信息）
        """
        fingerprint = alert.get_fingerprint()
        now = time.time()

        if fingerprint in self.cache:
            record = self.cache[fingerprint]
            elapsed = now - record.first_seen

            # 在时间窗口内
            if elapsed < self.window:
                record.count += 1
                record.last_seen = now

                # 检查频率限制
                if record.count > self.max_count:
                    return False, f"Rate limit exceeded: {record.count} alerts in {elapsed:.0f}s"
                else:
                    return False, f"Deduplicated: {record.count} times in {elapsed:.0f}s"
            else:
                # 超过窗口，发送摘要
                summary = self._create_summary(record)
                self._reset_record(fingerprint, alert, now)
                return True, summary
        else:
            # 首次出现
            self._create_record(fingerprint, alert, now)
            return True, None

    def _create_summary(self, record: AlertRecord) -> str:
        """
        创建告警摘要

        Args:
            record: 告警记录

        Returns:
            摘要字符串
        """
        elapsed = record.last_seen - record.first_seen
        return f"(repeated {record.count} times in {elapsed:.0f}s)"

    def _create_record(self, fingerprint: str, alert: Alert, now: float):
        """
        创建新记录

        Args:
            fingerprint: 告警指纹
            alert: 告警对象
            now: 当前时间
        """
        self.cache[fingerprint] = AlertRecord(
            fingerprint=fingerprint, first_seen=now, last_seen=now, count=1, alert=alert
        )

    def _reset_record(self, fingerprint: str, alert: Alert, now: float):
        """
        重置记录

        Args:
            fingerprint: 告警指纹
            alert: 告警对象
            now: 当前时间
        """
        self.cache[fingerprint] = AlertRecord(
            fingerprint=fingerprint, first_seen=now, last_seen=now, count=1, alert=alert
        )

    def cleanup_expired(self):
        """清理过期记录"""
        now = time.time()
        expired = [fp for fp, record in self.cache.items() if now - record.last_seen > self.window * 2]

        for fp in expired:
            del self.cache[fp]

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired alert records")

    def get_stats(self) -> Dict[str, any]:
        """
        获取去重统计

        Returns:
            统计信息字典
        """
        now = time.time()
        active_count = sum(1 for record in self.cache.values() if now - record.last_seen < self.window)

        return {
            "total_cached": len(self.cache),
            "active_alerts": active_count,
            "window": self.window,
            "max_count": self.max_count,
        }

    def reset(self):
        """重置去重器"""
        self.cache.clear()
        logger.info("AlertDeduplicator reset")
