"""
风控管理器

统一管理所有风控规则，提供订单检查、配置加载、统计等功能
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from risk.models import Order, RiskCheckResult, RiskRule, RiskStats
from risk.rules.order_rules import DailyTradesLimitRule, MaxOrderValueRule, TradingFrequencyRule
from risk.rules.position_rules import MaxSinglePositionRule, MaxTotalPositionRule, PositionConcentrationRule

logger = logging.getLogger(__name__)


class RiskManager:
    """
    风控管理器

    功能：
    - 管理所有风控规则
    - 执行订单检查
    - 加载和热更新配置
    - 统计风控信息
    """

    def __init__(self, config_path: str = "config/risk_config.yaml"):
        """
        初始化风控管理器

        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.rules: List[RiskRule] = []
        self.stats = RiskStats()

        # 特殊规则（需要记录状态）
        self.daily_trades_rule: Optional[DailyTradesLimitRule] = None
        self.frequency_rule: Optional[TradingFrequencyRule] = None

        # 加载配置并初始化规则
        self._load_config()
        self._init_rules()

        logger.info(f"RiskManager initialized with {len(self.rules)} rules")

    def check_order(self, order: Order, context: Dict[str, Any]) -> RiskCheckResult:
        """
        检查订单是否符合风控规则

        Args:
            order: 订单对象
            context: 上下文信息（portfolio, current_price等）

        Returns:
            风控检查结果
        """
        logger.debug(f"Checking order: {order}")

        # 遍历所有规则
        for rule in self.rules:
            if not rule.is_enabled():
                continue

            try:
                result = rule.check(order, context)

                # 记录规则统计
                rule.record_check(result)

                if not result.passed:
                    # 风控失败
                    self._record_rejection(order, result)
                    logger.warning(f"Order rejected by {rule.name}: {result.reason}")
                    return result

            except Exception as e:
                logger.error(f"Error checking rule {rule.name}: {e}", exc_info=True)
                # 严格模式下，规则异常视为失败
                if self.config.get("global", {}).get("strict_mode", False):
                    return RiskCheckResult(
                        passed=False, reason=f"Rule check error: {e}", rule_name=rule.name, severity="error"
                    )

        # 所有规则通过
        self._record_approval(order)

        # 记录交易（用于频率和次数统计）
        self._record_trade_for_rules(order)

        logger.debug(f"Order passed all risk checks: {order}")
        return RiskCheckResult(passed=True, rule_name="ALL")

    def _record_rejection(self, order: Order, result: RiskCheckResult):
        """
        记录拒绝

        Args:
            order: 订单
            result: 检查结果
        """
        self.stats.record_check(result)

        # 记录详细日志
        logger.warning(f"[RISK REJECT] {order} rejected by {result.rule_name}: {result.reason}")

        # 是否发送告警
        if self.config.get("global", {}).get("alert_on_rejection", True):
            if result.severity == "error":
                logger.error(f"[ALERT] Risk rejection: {result}")

    def _record_approval(self, order: Order):
        """
        记录通过

        Args:
            order: 订单
        """
        result = RiskCheckResult(passed=True, rule_name="ALL")
        self.stats.record_check(result)

        # 是否记录所有检查
        if self.config.get("global", {}).get("log_all_checks", False):
            logger.info(f"[RISK PASS] {order} passed all checks")

    def _record_trade_for_rules(self, order: Order):
        """
        记录交易到有状态的规则

        Args:
            order: 订单
        """
        # 记录到单日交易次数规则
        if self.daily_trades_rule:
            self.daily_trades_rule.record_trade(order)

        # 记录到频率检测规则
        if self.frequency_rule:
            self.frequency_rule.record_order(order)

    def _load_config(self):
        """加载配置文件"""
        try:
            config_file = Path(self.config_path)

            if not config_file.exists():
                logger.warning(f"Config file not found: {self.config_path}, using defaults")
                self.config = self._get_default_config()
                return

            with open(config_file, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)

            logger.info(f"Loaded risk config from {self.config_path}")

        except Exception as e:
            logger.error(f"Error loading config: {e}", exc_info=True)
            self.config = self._get_default_config()

    def _init_rules(self):
        """初始化风控规则"""
        self.rules.clear()

        # 持仓风控规则
        position_config = self.config.get("position", {})

        # 单只持仓上限
        if "max_single_position" in position_config:
            rule = MaxSinglePositionRule("max_single_position", position_config["max_single_position"])
            self.rules.append(rule)

        # 总持仓上限
        if "max_total_position" in position_config:
            rule = MaxTotalPositionRule("max_total_position", position_config["max_total_position"])
            self.rules.append(rule)

        # 持仓集中度
        if "position_concentration" in position_config:
            rule = PositionConcentrationRule("position_concentration", position_config["position_concentration"])
            self.rules.append(rule)

        # 订单风控规则
        order_config = self.config.get("order", {})

        # 订单金额上限
        if "max_order_value" in order_config:
            rule = MaxOrderValueRule("max_order_value", order_config["max_order_value"])
            self.rules.append(rule)

        # 单日交易次数
        if "daily_trades_limit" in order_config:
            rule = DailyTradesLimitRule("daily_trades_limit", order_config["daily_trades_limit"])
            self.rules.append(rule)
            self.daily_trades_rule = rule  # 保存引用

        # 交易频率
        if "trading_frequency" in order_config:
            rule = TradingFrequencyRule("trading_frequency", order_config["trading_frequency"])
            self.rules.append(rule)
            self.frequency_rule = rule  # 保存引用

        logger.info(f"Initialized {len(self.rules)} risk rules")

    def reload_config(self):
        """热更新配置"""
        logger.info("Reloading risk config...")

        # 保存有状态规则的数据
        daily_trades_data = None
        frequency_data = None

        if self.daily_trades_rule:
            daily_trades_data = {
                "daily_trades": self.daily_trades_rule.daily_trades.copy(),
                "symbol_daily_trades": {k: v.copy() for k, v in self.daily_trades_rule.symbol_daily_trades.items()},
            }

        if self.frequency_rule:
            frequency_data = self.frequency_rule.recent_orders.copy()

        # 重新加载配置和规则
        self._load_config()
        self._init_rules()

        # 恢复有状态规则的数据
        if daily_trades_data and self.daily_trades_rule:
            self.daily_trades_rule.daily_trades = daily_trades_data["daily_trades"]
            self.daily_trades_rule.symbol_daily_trades = daily_trades_data["symbol_daily_trades"]

        if frequency_data and self.frequency_rule:
            self.frequency_rule.recent_orders = frequency_data

        logger.info("Risk config reloaded successfully")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取风控统计信息

        Returns:
            统计信息字典
        """
        stats = {"summary": self.stats.get_summary(), "rules": [rule.get_stats() for rule in self.rules]}

        # 添加特殊规则的统计
        if self.daily_trades_rule:
            stats["daily_trades"] = self.daily_trades_rule.get_daily_stats()

        if self.frequency_rule:
            stats["frequency"] = self.frequency_rule.get_frequency_stats()

        return stats

    def reset_stats(self):
        """重置统计信息"""
        self.stats.reset()
        for rule in self.rules:
            rule.reset_stats()
        logger.info("Risk stats reset")

    def _get_default_config(self) -> Dict[str, Any]:
        """
        获取默认配置

        Returns:
            默认配置字典
        """
        return {
            "position": {
                "max_single_position": {"enabled": True, "max_quantity": 10000, "max_value": 100000},
                "max_total_position": {"enabled": True, "max_total_value": 500000},
                "position_concentration": {"enabled": True, "max_concentration": 0.3},
            },
            "order": {
                "max_order_value": {"enabled": True, "max_order_value": 50000},
                "daily_trades_limit": {"enabled": True, "max_daily_trades": 100, "max_symbol_daily_trades": 20},
                "trading_frequency": {
                    "enabled": True,
                    "time_window": 60,
                    "max_symbol_frequency": 5,
                    "max_total_frequency": 10,
                },
            },
            "global": {"strict_mode": False, "log_all_checks": False, "alert_on_rejection": True},
        }
