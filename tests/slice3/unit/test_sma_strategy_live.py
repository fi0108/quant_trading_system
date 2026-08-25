"""
SMA双均线策略 - 单元测试

测试策略的核心逻辑，不依赖外部系统（IBKR、数据库）
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from strategies.sma_crossover_live import SMAStrategyLive
from strategy.qc_algorithm import Resolution


class TestSMAStrategyLive:
    """SMA策略单元测试"""

    def setup_method(self):
        """每个测试前的设置"""
        self.strategy = SMAStrategyLive()
        self.strategy.symbol = "AAPL"
        self.strategy.fast_period = 3  # 使用小周期方便测试
        self.strategy.slow_period = 5

    def test_strategy_initialization(self):
        """测试1：策略初始化"""
        # 验证初始状态
        assert self.strategy.symbol == "AAPL"
        assert self.strategy.fast_period == 3
        assert self.strategy.slow_period == 5
        assert self.strategy.previous_signal == "none"
        assert self.strategy.sma_fast is None
        assert self.strategy.sma_slow is None

    def test_golden_cross_signal_detection(self):
        """测试2：金叉信号检测"""
        # 设置前一时刻的值：快线在慢线下方
        self.strategy.prev_fast = 100.0
        self.strategy.prev_slow = 102.0

        # 当前时刻：快线上穿慢线
        current_fast = 103.0
        current_slow = 102.5

        signal = self.strategy._detect_cross_signal(current_fast, current_slow)

        assert signal == "buy", "应该检测到金叉买入信号"

    def test_death_cross_signal_detection(self):
        """测试3：死叉信号检测"""
        # 设置前一时刻的值：快线在慢线上方
        self.strategy.prev_fast = 105.0
        self.strategy.prev_slow = 103.0

        # 当前时刻：快线下穿慢线
        current_fast = 102.0
        current_slow = 102.5

        signal = self.strategy._detect_cross_signal(current_fast, current_slow)

        assert signal == "sell", "应该检测到死叉卖出信号"

    def test_no_signal_when_no_cross(self):
        """测试4：无交叉时无信号"""
        # 快线持续在慢线上方
        self.strategy.prev_fast = 105.0
        self.strategy.prev_slow = 103.0

        current_fast = 106.0
        current_slow = 104.0

        signal = self.strategy._detect_cross_signal(current_fast, current_slow)

        assert signal == "none", "无交叉时不应该有信号"

    def test_no_signal_when_first_run(self):
        """测试5：首次运行时无信号"""
        # 没有历史值（prev_fast和prev_slow为0）
        current_fast = 105.0
        current_slow = 103.0

        signal = self.strategy._detect_cross_signal(current_fast, current_slow)

        assert signal == "none", "首次运行时不应该有信号"

    def test_no_duplicate_buy_signals(self):
        """测试6：避免重复买入信号"""
        # Mock Portfolio
        mock_portfolio = Mock()
        mock_holdings = Mock()
        mock_holdings.quantity = 0
        mock_portfolio.get_holdings.return_value = mock_holdings
        self.strategy.Portfolio = mock_portfolio

        # Mock MarketOrder
        self.strategy.MarketOrder = Mock()
        self.strategy.Log = Mock()

        # 设置更大的最大订单金额，避免风险控制阻止下单
        self.strategy.max_order_value = 50000

        # 第一次金叉，应该下单
        self.strategy._handle_signal("buy", 150.0, datetime.now())
        assert self.strategy.MarketOrder.call_count == 1
        assert self.strategy.previous_signal == "buy"

        # 第二次金叉，previous_signal已经是buy，不应该重复下单
        self.strategy.MarketOrder.reset_mock()
        self.strategy._handle_signal("buy", 151.0, datetime.now())
        assert self.strategy.MarketOrder.call_count == 0, "不应该重复下单"

    def test_handle_buy_signal_no_position(self):
        """测试7：处理买入信号（无持仓）"""
        # Mock Portfolio
        mock_portfolio = Mock()
        mock_portfolio.get_holdings.return_value = None  # 无持仓
        self.strategy.Portfolio = mock_portfolio

        # Mock MarketOrder
        self.strategy.MarketOrder = Mock()
        self.strategy.Log = Mock()

        # 设置交易数量和更大的最大订单金额
        self.strategy.trade_quantity = 100
        self.strategy.max_order_value = 50000

        # 处理买入信号
        self.strategy._handle_signal("buy", 150.0, datetime.now())

        # 验证下单
        self.strategy.MarketOrder.assert_called_once_with("AAPL", 100)
        assert self.strategy.previous_signal == "buy"

    def test_handle_sell_signal_with_position(self):
        """测试8：处理卖出信号（有持仓）"""
        # Mock Portfolio - 有100股多仓
        mock_portfolio = Mock()
        mock_holdings = Mock()
        mock_holdings.quantity = 100
        mock_portfolio.get_holdings.return_value = mock_holdings
        self.strategy.Portfolio = mock_portfolio

        # Mock MarketOrder
        self.strategy.MarketOrder = Mock()
        self.strategy.Log = Mock()

        # 处理卖出信号
        self.strategy._handle_signal("sell", 150.0, datetime.now())

        # 验证平仓
        self.strategy.MarketOrder.assert_called_once_with("AAPL", -100)
        assert self.strategy.previous_signal == "sell"

    def test_handle_sell_signal_no_position(self):
        """测试9：处理卖出信号（无持仓）"""
        # Mock Portfolio - 无持仓
        mock_portfolio = Mock()
        mock_portfolio.get_holdings.return_value = None
        self.strategy.Portfolio = mock_portfolio

        # Mock MarketOrder
        self.strategy.MarketOrder = Mock()
        self.strategy.Log = Mock()

        # 处理卖出信号
        self.strategy._handle_signal("sell", 150.0, datetime.now())

        # 验证不下单
        self.strategy.MarketOrder.assert_not_called()

    def test_risk_control_max_order_value(self):
        """测试10：风险控制 - 订单金额限制"""
        # Mock Portfolio
        mock_portfolio = Mock()
        mock_portfolio.get_holdings.return_value = None
        self.strategy.Portfolio = mock_portfolio

        # Mock MarketOrder
        self.strategy.MarketOrder = Mock()
        self.strategy.Log = Mock()

        # 设置参数
        self.strategy.trade_quantity = 100
        self.strategy.max_order_value = 10000  # 最大1万美元

        # 当前价格200，订单金额20000，超过限制
        self.strategy._handle_signal("buy", 200.0, datetime.now())

        # 验证不下单
        self.strategy.MarketOrder.assert_not_called()

    def test_order_event_filled(self):
        """测试11：订单成交事件处理"""
        # Mock Portfolio
        mock_portfolio = Mock()
        mock_holdings = Mock()
        mock_holdings.quantity = 100
        mock_holdings.average_price = 150.0
        mock_holdings.unrealized_pnl = 500.0
        mock_portfolio.get_holdings.return_value = mock_holdings
        self.strategy.Portfolio = mock_portfolio

        # Mock Log
        self.strategy.Log = Mock()

        # 创建订单成交事件
        order_event = Mock()
        order_event.order_id = 1
        order_event.status = "Filled"
        order_event.symbol = "AAPL"
        order_event.quantity = 100
        order_event.filled_quantity = 100
        order_event.average_fill_price = 150.0

        # 处理事件
        self.strategy.OnOrderEvent(order_event)

        # 验证日志记录
        assert self.strategy.Log.call_count >= 2  # 至少记录成交和持仓

    def test_order_event_rejected(self):
        """测试12：订单拒绝事件处理"""
        # Mock Log
        self.strategy.Log = Mock()

        # 创建订单拒绝事件
        order_event = Mock()
        order_event.order_id = 1
        order_event.status = "Rejected"
        order_event.message = "Insufficient margin"

        # 处理事件
        self.strategy.OnOrderEvent(order_event)

        # 验证记录了拒绝信息
        log_calls = [str(call) for call in self.strategy.Log.call_args_list]
        assert any("REJECT" in str(call) for call in log_calls)

    def test_on_data_indicators_not_ready(self):
        """测试13：OnData - 指标未就绪"""
        # Mock指标（未就绪）
        self.strategy.sma_fast = Mock()
        self.strategy.sma_fast.IsReady = False
        self.strategy.sma_fast._samples = 2

        self.strategy.sma_slow = Mock()
        self.strategy.sma_slow.IsReady = False
        self.strategy.sma_slow._samples = 3

        # Mock Log
        self.strategy.Log = Mock()

        # 创建数据
        data = {"AAPL": Mock(time=datetime.now(), close=150.0)}

        # 处理数据
        self.strategy.OnData(data)

        # 验证记录了预热信息
        log_calls = [str(call) for call in self.strategy.Log.call_args_list]
        assert any("WARMUP" in str(call) for call in log_calls)

    def test_on_data_with_golden_cross(self):
        """测试14：OnData - 完整金叉流程"""
        # Mock指标（已就绪）
        self.strategy.sma_fast = Mock()
        self.strategy.sma_fast.IsReady = True
        self.strategy.sma_fast._samples = 10
        self.strategy.sma_fast.Current.Value = 105.0

        self.strategy.sma_slow = Mock()
        self.strategy.sma_slow.IsReady = True
        self.strategy.sma_slow._samples = 10
        self.strategy.sma_slow.Current.Value = 103.0

        # 设置前值（快线在慢线下方）
        self.strategy.prev_fast = 102.0
        self.strategy.prev_slow = 103.0

        # Mock Portfolio
        mock_portfolio = Mock()
        mock_portfolio.get_holdings.return_value = None
        self.strategy.Portfolio = mock_portfolio

        # Mock MarketOrder
        self.strategy.MarketOrder = Mock()
        self.strategy.Log = Mock()
        self.strategy.trade_quantity = 100
        self.strategy.max_order_value = 50000

        # 创建数据
        data = {"AAPL": Mock(time=datetime.now(), close=150.0)}

        # 处理数据
        self.strategy.OnData(data)

        # 验证检测到金叉并下单
        self.strategy.MarketOrder.assert_called_once_with("AAPL", 100)

        # 验证记录了信号
        log_calls = [str(call) for call in self.strategy.Log.call_args_list]
        assert any("Golden Cross" in str(call) for call in log_calls)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
