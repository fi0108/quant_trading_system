"""
风控模型定义

定义风控检查结果、规则基类等核心数据结构
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class RiskCheckResult:
    """风控检查结果"""

    passed: bool  # 是否通过
    reason: str = ""  # 失败原因
    rule_name: str = ""  # 触发的规则名称
    severity: str = "warning"  # 严重程度: info/warning/error
    context: Dict[str, Any] = field(default_factory=dict)  # 上下文信息

    def __str__(self):
        if self.passed:
            return f"[PASS] {self.rule_name}"
        else:
            return f"[FAIL] {self.rule_name}: {self.reason} (severity: {self.severity})"


class RiskRule(ABC):
    """风控规则抽象基类"""

    def __init__(self, name: str, config: Dict[str, Any]):
        """
        初始化风控规则

        Args:
            name: 规则名称
            config: 规则配置
        """
        self.name = name
        self.config = config
        self.enabled = config.get("enabled", True)
        self.check_count = 0
        self.pass_count = 0
        self.fail_count = 0

    @abstractmethod
    def check(self, order: Any, context: Dict[str, Any]) -> RiskCheckResult:
        """
        检查订单是否符合风控规则

        Args:
            order: 订单对象
            context: 上下文信息（持仓、价格等）

        Returns:
            风控检查结果
        """
        pass

    def is_enabled(self) -> bool:
        """规则是否启用"""
        return self.enabled

    def record_check(self, result: RiskCheckResult):
        """记录检查结果"""
        self.check_count += 1
        if result.passed:
            self.pass_count += 1
        else:
            self.fail_count += 1

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "name": self.name,
            "enabled": self.enabled,
            "check_count": self.check_count,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "pass_rate": self.pass_count / self.check_count if self.check_count > 0 else 0,
        }

    def reset_stats(self):
        """重置统计"""
        self.check_count = 0
        self.pass_count = 0
        self.fail_count = 0


class RiskStats:
    """风控统计信息"""

    def __init__(self):
        self.total_checks = 0
        self.total_passed = 0
        self.total_failed = 0
        self.rejection_by_rule: Dict[str, int] = {}

    def record_check(self, result: RiskCheckResult):
        """记录检查结果"""
        self.total_checks += 1

        if result.passed:
            self.total_passed += 1
        else:
            self.total_failed += 1
            rule_name = result.rule_name
            self.rejection_by_rule[rule_name] = self.rejection_by_rule.get(rule_name, 0) + 1

    def get_summary(self) -> Dict[str, Any]:
        """获取统计摘要"""
        return {
            "total_checks": self.total_checks,
            "total_passed": self.total_passed,
            "total_failed": self.total_failed,
            "pass_rate": self.total_passed / self.total_checks if self.total_checks > 0 else 0,
            "rejection_by_rule": self.rejection_by_rule.copy(),
        }

    def reset(self):
        """重置统计"""
        self.total_checks = 0
        self.total_passed = 0
        self.total_failed = 0
        self.rejection_by_rule.clear()


@dataclass
class Order:
    """订单数据类（简化版）"""

    symbol: str  # 标的符号
    action: str  # 动作: BUY/SELL
    quantity: int  # 数量
    order_type: str = "MKT"  # 订单类型: MKT/LMT
    price: float = 0.0  # 限价单价格
    order_id: Optional[int] = None  # 订单ID

    def __str__(self):
        return f"{self.action} {self.symbol} x {self.quantity}"


@dataclass
class Position:
    """持仓数据类（简化版）"""

    symbol: str  # 标的符号
    quantity: int  # 持仓数量
    average_price: float  # 平均成本
    unrealized_pnl: float = 0.0  # 未实现盈亏

    def get_market_value(self, current_price: float) -> float:
        """计算市值"""
        return self.quantity * current_price
