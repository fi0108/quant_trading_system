"""
持仓风控规则

包含单只持仓上限、总持仓上限、持仓集中度检查
"""

import logging
from typing import Any, Dict

from risk.models import Order, Position, RiskCheckResult, RiskRule

logger = logging.getLogger(__name__)


class MaxSinglePositionRule(RiskRule):
    """单只股票持仓上限"""

    def check(self, order: Order, context: Dict[str, Any]) -> RiskCheckResult:
        """
        检查单只持仓是否超限

        Args:
            order: 订单对象
            context: 上下文（包含portfolio和current_price）

        Returns:
            风控检查结果
        """
        # 只检查买入订单
        if order.action != "BUY":
            return RiskCheckResult(passed=True, rule_name=self.name)

        symbol = order.symbol
        quantity = order.quantity

        # 获取当前持仓
        portfolio = context.get("portfolio", {})
        current_position = portfolio.get(symbol)
        current_qty = current_position.quantity if current_position else 0

        # 计算下单后持仓
        new_position = current_qty + quantity

        # 检查数量上限
        max_quantity = self.config.get("max_quantity", 10000)
        if new_position > max_quantity:
            return RiskCheckResult(
                passed=False,
                reason=f"Single position limit exceeded: {new_position} > {max_quantity}",
                rule_name=self.name,
                severity="error",
                context={
                    "symbol": symbol,
                    "current_position": current_qty,
                    "new_position": new_position,
                    "limit": max_quantity,
                },
            )

        # 检查市值上限
        current_prices = context.get("current_price", {})
        current_price = current_prices.get(symbol, 0)

        if current_price > 0:
            new_value = new_position * current_price
            max_value = self.config.get("max_value", 100000)

            if new_value > max_value:
                return RiskCheckResult(
                    passed=False,
                    reason=f"Single position value limit exceeded: ${new_value:.0f} > ${max_value:.0f}",
                    rule_name=self.name,
                    severity="error",
                    context={
                        "symbol": symbol,
                        "new_position": new_position,
                        "price": current_price,
                        "new_value": new_value,
                        "limit": max_value,
                    },
                )

        return RiskCheckResult(passed=True, rule_name=self.name)


class MaxTotalPositionRule(RiskRule):
    """总持仓上限"""

    def check(self, order: Order, context: Dict[str, Any]) -> RiskCheckResult:
        """
        检查总持仓是否超限

        Args:
            order: 订单对象
            context: 上下文

        Returns:
            风控检查结果
        """
        # 只检查买入订单
        if order.action != "BUY":
            return RiskCheckResult(passed=True, rule_name=self.name)

        portfolio = context.get("portfolio", {})
        current_prices = context.get("current_price", {})

        # 计算当前总市值
        total_value = 0
        for symbol, position in portfolio.items():
            if isinstance(position, Position):
                price = current_prices.get(symbol, 0)
                total_value += position.quantity * price

        # 计算订单市值
        order_price = current_prices.get(order.symbol, 0)
        order_value = order.quantity * order_price

        new_total_value = total_value + order_value

        # 检查总市值上限
        max_total_value = self.config.get("max_total_value", 500000)

        if new_total_value > max_total_value:
            return RiskCheckResult(
                passed=False,
                reason=f"Total position value limit exceeded: ${new_total_value:.0f} > ${max_total_value:.0f}",
                rule_name=self.name,
                severity="error",
                context={
                    "current_total_value": total_value,
                    "order_value": order_value,
                    "new_total_value": new_total_value,
                    "limit": max_total_value,
                },
            )

        return RiskCheckResult(passed=True, rule_name=self.name)


class PositionConcentrationRule(RiskRule):
    """持仓集中度检查"""

    def check(self, order: Order, context: Dict[str, Any]) -> RiskCheckResult:
        """
        检查单只股票占总持仓的比例

        Args:
            order: 订单对象
            context: 上下文

        Returns:
            风控检查结果
        """
        # 只检查买入订单
        if order.action != "BUY":
            return RiskCheckResult(passed=True, rule_name=self.name)

        portfolio = context.get("portfolio", {})
        current_prices = context.get("current_price", {})
        symbol = order.symbol

        # 计算当前总市值
        total_value = 0
        for sym, position in portfolio.items():
            if isinstance(position, Position):
                price = current_prices.get(sym, 0)
                total_value += position.quantity * price

        # 计算订单后该股票的市值
        current_position = portfolio.get(symbol)
        current_qty = current_position.quantity if current_position else 0
        new_qty = current_qty + order.quantity
        price = current_prices.get(symbol, 0)
        symbol_value = new_qty * price

        # 加上订单后的总市值
        new_total_value = total_value + (order.quantity * price)

        # 计算集中度
        if new_total_value > 0:
            concentration = symbol_value / new_total_value
        else:
            concentration = 0

        max_concentration = self.config.get("max_concentration", 0.3)  # 默认30%

        if concentration > max_concentration:
            return RiskCheckResult(
                passed=False,
                reason=f"Position concentration too high: {concentration*100:.1f}% > {max_concentration*100:.1f}%",
                rule_name=self.name,
                severity="warning",
                context={
                    "symbol": symbol,
                    "symbol_value": symbol_value,
                    "total_value": new_total_value,
                    "concentration": concentration,
                    "limit": max_concentration,
                },
            )

        return RiskCheckResult(passed=True, rule_name=self.name)
