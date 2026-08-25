"""
订单风控规则

包含订单金额上限、单日交易次数限制、频繁交易检测
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple

from risk.models import Order, RiskCheckResult, RiskRule

logger = logging.getLogger(__name__)


class MaxOrderValueRule(RiskRule):
    """单笔订单金额上限"""

    def check(self, order: Order, context: Dict[str, Any]) -> RiskCheckResult:
        """
        检查订单金额是否超限

        Args:
            order: 订单对象
            context: 上下文

        Returns:
            风控检查结果
        """
        current_prices = context.get("current_price", {})
        price = current_prices.get(order.symbol, 0)
        order_value = order.quantity * price

        max_value = self.config.get("max_order_value", 50000)

        if order_value > max_value:
            return RiskCheckResult(
                passed=False,
                reason=f"Order value exceeds limit: ${order_value:.0f} > ${max_value:.0f}",
                rule_name=self.name,
                severity="error",
                context={
                    "symbol": order.symbol,
                    "quantity": order.quantity,
                    "price": price,
                    "order_value": order_value,
                    "limit": max_value,
                },
            )

        return RiskCheckResult(passed=True, rule_name=self.name)


class DailyTradesLimitRule(RiskRule):
    """单日交易次数限制"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.daily_trades: Dict[str, int] = {}  # {date: count}
        self.symbol_daily_trades: Dict[str, Dict[str, int]] = {}  # {date: {symbol: count}}

    def check(self, order: Order, context: Dict[str, Any]) -> RiskCheckResult:
        """
        检查今日交易次数

        Args:
            order: 订单对象
            context: 上下文

        Returns:
            风控检查结果
        """
        today = datetime.now().date().isoformat()

        # 初始化今日计数
        if today not in self.daily_trades:
            self._reset_daily_counters(today)

        # 检查总交易次数
        max_daily_trades = self.config.get("max_daily_trades", 100)
        if self.daily_trades[today] >= max_daily_trades:
            return RiskCheckResult(
                passed=False,
                reason=f"Daily trades limit exceeded: {self.daily_trades[today]} >= {max_daily_trades}",
                rule_name=self.name,
                severity="warning",
                context={"daily_trades": self.daily_trades[today], "limit": max_daily_trades},
            )

        # 检查单只股票交易次数
        max_symbol_daily_trades = self.config.get("max_symbol_daily_trades", 20)
        symbol_count = self.symbol_daily_trades[today].get(order.symbol, 0)

        if symbol_count >= max_symbol_daily_trades:
            return RiskCheckResult(
                passed=False,
                reason=f"Daily trades limit for {order.symbol} exceeded: {symbol_count} >= {max_symbol_daily_trades}",
                rule_name=self.name,
                severity="warning",
                context={"symbol": order.symbol, "symbol_trades": symbol_count, "limit": max_symbol_daily_trades},
            )

        return RiskCheckResult(passed=True, rule_name=self.name)

    def record_trade(self, order: Order):
        """
        记录交易（风控通过后调用）

        Args:
            order: 订单对象
        """
        today = datetime.now().date().isoformat()

        # 初始化今日计数
        if today not in self.daily_trades:
            self._reset_daily_counters(today)

        self.daily_trades[today] += 1

        if order.symbol not in self.symbol_daily_trades[today]:
            self.symbol_daily_trades[today][order.symbol] = 0
        self.symbol_daily_trades[today][order.symbol] += 1

        logger.debug(
            f"Recorded trade: {order.symbol}, "
            f"daily total: {self.daily_trades[today]}, "
            f"symbol daily: {self.symbol_daily_trades[today][order.symbol]}"
        )

    def _reset_daily_counters(self, today: str):
        """
        重置每日计数器

        Args:
            today: 今天的日期（ISO格式）
        """
        # 清理旧日期
        old_dates = [d for d in self.daily_trades.keys() if d != today]
        for d in old_dates:
            del self.daily_trades[d]
            if d in self.symbol_daily_trades:
                del self.symbol_daily_trades[d]

        self.daily_trades[today] = 0
        self.symbol_daily_trades[today] = {}

        logger.debug(f"Reset daily counters for {today}")

    def get_daily_stats(self) -> Dict[str, Any]:
        """获取今日统计"""
        today = datetime.now().date().isoformat()
        return {
            "date": today,
            "total_trades": self.daily_trades.get(today, 0),
            "symbol_trades": self.symbol_daily_trades.get(today, {}).copy(),
        }


class TradingFrequencyRule(RiskRule):
    """频繁交易检测（防止短时间内大量下单）"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.recent_orders: List[Tuple[str, float]] = []  # [(symbol, timestamp)]

    def check(self, order: Order, context: Dict[str, Any]) -> RiskCheckResult:
        """
        检查交易频率

        Args:
            order: 订单对象
            context: 上下文

        Returns:
            风控检查结果
        """
        now = time.time()
        symbol = order.symbol

        # 清理过期记录
        time_window = self.config.get("time_window", 60)  # 默认60秒
        self.recent_orders = [(s, t) for s, t in self.recent_orders if now - t < time_window]

        # 统计时间窗口内的交易次数
        symbol_count = sum(1 for s, t in self.recent_orders if s == symbol)
        total_count = len(self.recent_orders)

        # 检查单只股票频率
        max_symbol_frequency = self.config.get("max_symbol_frequency", 5)
        if symbol_count >= max_symbol_frequency:
            return RiskCheckResult(
                passed=False,
                reason=f"Trading frequency too high for {symbol}: {symbol_count} orders in {time_window}s",
                rule_name=self.name,
                severity="warning",
                context={
                    "symbol": symbol,
                    "count": symbol_count,
                    "time_window": time_window,
                    "limit": max_symbol_frequency,
                },
            )

        # 检查总体频率
        max_total_frequency = self.config.get("max_total_frequency", 10)
        if total_count >= max_total_frequency:
            return RiskCheckResult(
                passed=False,
                reason=f"Trading frequency too high: {total_count} orders in {time_window}s",
                rule_name=self.name,
                severity="warning",
                context={"count": total_count, "time_window": time_window, "limit": max_total_frequency},
            )

        return RiskCheckResult(passed=True, rule_name=self.name)

    def record_order(self, order: Order):
        """
        记录订单（风控通过后调用）

        Args:
            order: 订单对象
        """
        self.recent_orders.append((order.symbol, time.time()))
        logger.debug(f"Recorded order for frequency check: {order.symbol}")

    def get_frequency_stats(self) -> Dict[str, Any]:
        """获取频率统计"""
        now = time.time()
        time_window = self.config.get("time_window", 60)

        # 清理过期记录
        self.recent_orders = [(s, t) for s, t in self.recent_orders if now - t < time_window]

        # 统计各标的
        symbol_counts: Dict[str, int] = {}
        for symbol, _ in self.recent_orders:
            symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1

        return {"time_window": time_window, "total_orders": len(self.recent_orders), "symbol_counts": symbol_counts}
