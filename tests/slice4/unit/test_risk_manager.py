"""
风控管理器 - 单元测试
"""

import time
from datetime import datetime

import pytest

from risk.manager import RiskManager
from risk.models import Order, Position, RiskCheckResult
from risk.rules.order_rules import DailyTradesLimitRule, MaxOrderValueRule, TradingFrequencyRule
from risk.rules.position_rules import MaxSinglePositionRule, MaxTotalPositionRule, PositionConcentrationRule


class TestPositionRules:
    """持仓风控规则测试"""

    def test_single_position_quantity_limit(self):
        """测试1：单只持仓数量超限"""
        rule = MaxSinglePositionRule("test", {"enabled": True, "max_quantity": 1000, "max_value": 100000})

        order = Order(symbol="AAPL", action="BUY", quantity=500)
        context = {
            "portfolio": {"AAPL": Position(symbol="AAPL", quantity=600, average_price=150)},
            "current_price": {"AAPL": 150},
        }

        result = rule.check(order, context)

        assert not result.passed
        assert "limit exceeded" in result.reason.lower()
        assert result.context["new_position"] == 1100

    def test_single_position_value_limit(self):
        """测试2：单只持仓市值超限"""
        rule = MaxSinglePositionRule("test", {"enabled": True, "max_quantity": 10000, "max_value": 50000})

        order = Order(symbol="AAPL", action="BUY", quantity=200)
        context = {
            "portfolio": {"AAPL": Position(symbol="AAPL", quantity=200, average_price=150)},
            "current_price": {"AAPL": 150},
        }

        result = rule.check(order, context)

        assert not result.passed
        assert "value limit exceeded" in result.reason.lower()
        assert result.context["new_value"] == 60000

    def test_sell_order_bypass_position_rule(self):
        """测试3：卖出订单不受持仓限制"""
        rule = MaxSinglePositionRule("test", {"enabled": True, "max_quantity": 100, "max_value": 10000})

        order = Order(symbol="AAPL", action="SELL", quantity=500)
        context = {"portfolio": {}, "current_price": {"AAPL": 150}}

        result = rule.check(order, context)

        assert result.passed

    def test_total_position_limit(self):
        """测试4：总持仓超限"""
        rule = MaxTotalPositionRule("test", {"enabled": True, "max_total_value": 100000})

        order = Order(symbol="MSFT", action="BUY", quantity=100)
        context = {
            "portfolio": {
                "AAPL": Position(symbol="AAPL", quantity=500, average_price=150),
                "TSLA": Position(symbol="TSLA", quantity=100, average_price=200),
            },
            "current_price": {"AAPL": 150, "TSLA": 200, "MSFT": 300},
        }

        # 当前总市值: 500*150 + 100*200 = 95000
        # 新订单: 100*300 = 30000
        # 总计: 125000 > 100000

        result = rule.check(order, context)

        assert not result.passed
        assert "total position value limit exceeded" in result.reason.lower()
        assert result.context["new_total_value"] == 125000

    def test_position_concentration_limit(self):
        """测试5：持仓集中度超限"""
        rule = PositionConcentrationRule("test", {"enabled": True, "max_concentration": 0.3})  # 30%

        order = Order(symbol="AAPL", action="BUY", quantity=500)
        context = {
            "portfolio": {
                "AAPL": Position(symbol="AAPL", quantity=300, average_price=150),
                "TSLA": Position(symbol="TSLA", quantity=100, average_price=200),
            },
            "current_price": {"AAPL": 150, "TSLA": 200},
        }

        # 当前总市值: 300*150 + 100*200 = 65000
        # AAPL新市值: (300+500)*150 = 120000
        # 新总市值: 65000 + 500*150 = 140000
        # 集中度: 120000/140000 = 85.7% > 30%

        result = rule.check(order, context)

        assert not result.passed
        assert "concentration too high" in result.reason.lower()

    def test_position_within_limits(self):
        """测试6：持仓在限制范围内"""
        rule = MaxSinglePositionRule("test", {"enabled": True, "max_quantity": 1000, "max_value": 100000})

        order = Order(symbol="AAPL", action="BUY", quantity=100)
        context = {
            "portfolio": {"AAPL": Position(symbol="AAPL", quantity=200, average_price=150)},
            "current_price": {"AAPL": 150},
        }

        result = rule.check(order, context)

        assert result.passed


class TestOrderRules:
    """订单风控规则测试"""

    def test_order_value_limit(self):
        """测试1：订单金额超限"""
        rule = MaxOrderValueRule("test", {"enabled": True, "max_order_value": 10000})

        order = Order(symbol="AAPL", action="BUY", quantity=100)
        context = {"current_price": {"AAPL": 150}}

        # 订单金额: 100*150 = 15000 > 10000

        result = rule.check(order, context)

        assert not result.passed
        assert "order value exceeds limit" in result.reason.lower()
        assert result.context["order_value"] == 15000

    def test_daily_trades_limit(self):
        """测试2：单日交易次数超限"""
        rule = DailyTradesLimitRule("test", {"enabled": True, "max_daily_trades": 5, "max_symbol_daily_trades": 3})

        order = Order(symbol="AAPL", action="BUY", quantity=100)
        context = {}

        # 模拟5次交易
        for i in range(5):
            result = rule.check(order, context)
            if result.passed:
                rule.record_trade(order)

        # 第6次应该被拒绝（先触发单只股票限制）
        result = rule.check(order, context)

        assert not result.passed
        assert "limit" in result.reason.lower()  # 可能是总限制或单只限制

    def test_symbol_daily_limit(self):
        """测试3：单只股票日交易超限"""
        rule = DailyTradesLimitRule("test", {"enabled": True, "max_daily_trades": 100, "max_symbol_daily_trades": 3})

        order_aapl = Order(symbol="AAPL", action="BUY", quantity=100)
        order_tsla = Order(symbol="TSLA", action="BUY", quantity=100)
        context = {}

        # AAPL交易3次
        for i in range(3):
            result = rule.check(order_aapl, context)
            if result.passed:
                rule.record_trade(order_aapl)

        # TSLA可以交易
        result = rule.check(order_tsla, context)
        assert result.passed

        # AAPL第4次被拒绝
        result = rule.check(order_aapl, context)
        assert not result.passed
        assert "AAPL" in result.reason

    def test_trading_frequency(self):
        """测试4：频繁交易检测"""
        rule = TradingFrequencyRule(
            "test", {"enabled": True, "time_window": 60, "max_symbol_frequency": 3, "max_total_frequency": 10}
        )

        order = Order(symbol="AAPL", action="BUY", quantity=100)
        context = {}

        # 快速下3单
        for i in range(3):
            result = rule.check(order, context)
            if result.passed:
                rule.record_order(order)
            time.sleep(0.1)

        # 第4单应该被拒绝
        result = rule.check(order, context)

        assert not result.passed
        assert "frequency too high" in result.reason.lower()

    def test_frequency_time_window(self):
        """测试5：时间窗口过期清理"""
        rule = TradingFrequencyRule(
            "test", {"enabled": True, "time_window": 2, "max_symbol_frequency": 2, "max_total_frequency": 10}  # 2秒窗口
        )

        order = Order(symbol="AAPL", action="BUY", quantity=100)
        context = {}

        # 下2单
        for i in range(2):
            result = rule.check(order, context)
            if result.passed:
                rule.record_order(order)

        # 等待窗口过期
        time.sleep(2.5)

        # 现在应该可以再下单
        result = rule.check(order, context)
        assert result.passed

    def test_order_within_limits(self):
        """测试6：订单在限制范围内"""
        rule = MaxOrderValueRule("test", {"enabled": True, "max_order_value": 50000})

        order = Order(symbol="AAPL", action="BUY", quantity=100)
        context = {"current_price": {"AAPL": 150}}

        result = rule.check(order, context)

        assert result.passed


class TestRiskManager:
    """风控管理器测试"""

    def test_manager_initialization(self):
        """测试1：管理器初始化"""
        manager = RiskManager()

        assert len(manager.rules) > 0
        assert manager.stats is not None
        assert manager.config is not None

    def test_check_order_pass(self):
        """测试2：订单通过所有检查"""
        manager = RiskManager()

        order = Order(symbol="AAPL", action="BUY", quantity=10)
        context = {
            "portfolio": {
                "TSLA": Position(symbol="TSLA", quantity=100, average_price=200)
            },  # 已有其他持仓，避免集中度100%
            "current_price": {"AAPL": 150, "TSLA": 200},
        }

        result = manager.check_order(order, context)

        assert result.passed

    def test_check_order_fail(self):
        """测试3：订单被风控拒绝"""
        manager = RiskManager()

        # 创建超大订单
        order = Order(symbol="AAPL", action="BUY", quantity=10000)
        context = {"portfolio": {}, "current_price": {"AAPL": 150}}

        # 订单金额: 10000*150 = 1500000，远超限制

        result = manager.check_order(order, context)

        assert not result.passed

    def test_get_stats(self):
        """测试4：获取统计信息"""
        manager = RiskManager()

        order = Order(symbol="AAPL", action="BUY", quantity=10)
        context = {"portfolio": {}, "current_price": {"AAPL": 150}}

        # 执行几次检查
        for i in range(3):
            manager.check_order(order, context)

        stats = manager.get_stats()

        assert "summary" in stats
        assert "rules" in stats
        assert stats["summary"]["total_checks"] == 3

    def test_reset_stats(self):
        """测试5：重置统计"""
        manager = RiskManager()

        order = Order(symbol="AAPL", action="BUY", quantity=10)
        context = {"portfolio": {}, "current_price": {"AAPL": 150}}

        manager.check_order(order, context)

        manager.reset_stats()

        stats = manager.get_stats()
        assert stats["summary"]["total_checks"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
