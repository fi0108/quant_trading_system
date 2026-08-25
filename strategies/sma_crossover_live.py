"""
SMA双均线交叉策略 - 实盘版本

策略逻辑：
- 金叉（快线上穿慢线）：买入开仓
- 死叉（快线下穿慢线）：卖出平仓

风险控制：
- 限制单笔交易数量
- 避免重复信号
"""

from datetime import datetime
from typing import Optional

from strategy.indicators.sma import SimpleMovingAverage
from strategy.qc_algorithm import QCAlgorithm, Resolution


class SMAStrategyLive(QCAlgorithm):
    """SMA双均线交叉策略 - 实盘交易版本"""

    def __init__(self, ibkr_client=None, order_manager=None, position_manager=None):
        # 如果参数为None，延迟初始化（用于测试）
        if ibkr_client is not None and order_manager is not None and position_manager is not None:
            super().__init__(ibkr_client, order_manager, position_manager)
        else:
            # 测试模式：不调用父类初始化，手动设置必要属性
            self.Portfolio = None
            self._indicators = {}

        # 配置参数
        self.symbol: str = ""
        self.fast_period: int = 10
        self.slow_period: int = 20
        self.trade_quantity: int = 100
        self.max_order_value: float = 10000.0

        # 指标
        self.sma_fast: Optional[SimpleMovingAverage] = None
        self.sma_slow: Optional[SimpleMovingAverage] = None

        # 状态跟踪
        self.previous_signal: str = "none"  # "buy"/"sell"/"none"
        self.prev_fast: float = 0.0
        self.prev_slow: float = 0.0

    def Log(self, message: str):
        """日志方法（测试模式下可被mock）"""
        if hasattr(super(), "Log"):
            super().Log(message)
        else:
            # 测试模式：打印到stdout
            print(f"[LOG] {message}")

    def MarketOrder(self, symbol: str, quantity: int):
        """市价单方法（测试模式下可被mock）"""
        if hasattr(super(), "MarketOrder"):
            return super().MarketOrder(symbol, quantity)
        else:
            # 测试模式：什么都不做
            pass

    def SMA(self, symbol: str, period: int, resolution=None):
        """创建SMA指标（测试模式下可被mock）"""
        if hasattr(super(), "SMA"):
            return super().SMA(symbol, period, resolution or Resolution.Daily)
        else:
            # 测试模式：返回None
            return None

    def Initialize(self):
        """初始化策略"""
        self.Log("=" * 60)
        self.Log(f"Initializing SMA Crossover Strategy")
        self.Log(f"Symbol: {self.symbol}")
        self.Log(f"Fast SMA Period: {self.fast_period}")
        self.Log(f"Slow SMA Period: {self.slow_period}")
        self.Log(f"Trade Quantity: {self.trade_quantity}")
        self.Log(f"Max Order Value: ${self.max_order_value:.2f}")
        self.Log("=" * 60)

        # 创建SMA指标
        self.sma_fast = self.SMA(self.symbol, self.fast_period, Resolution.Daily)
        self.sma_slow = self.SMA(self.symbol, self.slow_period, Resolution.Daily)

        self.Log(f"[INDICATOR] Fast SMA created: period={self.fast_period}")
        self.Log(f"[INDICATOR] Slow SMA created: period={self.slow_period}")

        # 查询当前持仓
        if self.Portfolio:
            holdings = self.Portfolio.get_holdings(self.symbol)
            if holdings:
                self.Log(f"[POSITION] Current position: {holdings.quantity} shares")
            else:
                self.Log(f"[POSITION] No current position")

    def OnData(self, data):
        """处理实时数据"""
        try:
            # 检查数据是否包含当前标的
            if self.symbol not in data:
                return

            bar = data[self.symbol]

            # 检查指标是否就绪
            if not self.sma_fast.IsReady or not self.sma_slow.IsReady:
                self.Log(
                    f"[WARMUP] Indicators warming up... "
                    f"Fast: {self.sma_fast._samples}/{self.fast_period}, "
                    f"Slow: {self.sma_slow._samples}/{self.slow_period}"
                )
                return

            # 获取当前均线值
            current_fast = self.sma_fast.Current.Value
            current_slow = self.sma_slow.Current.Value

            # 记录均线值（每10次记录一次，避免日志过多）
            if self.sma_fast._samples % 10 == 0:
                self.Log(f"[INDICATOR] SMA_Fast={current_fast:.2f}, SMA_Slow={current_slow:.2f}")

            # 检测交叉信号
            signal = self._detect_cross_signal(current_fast, current_slow)

            if signal != "none":
                self._handle_signal(signal, bar.close, bar.time)

            # 保存当前值用于下次比较
            self.prev_fast = current_fast
            self.prev_slow = current_slow

        except Exception as e:
            self.Log(f"[ERROR] Exception in OnData: {e}")
            import traceback

            self.Log(traceback.format_exc())

    def _detect_cross_signal(self, current_fast: float, current_slow: float) -> str:
        """
        检测交叉信号

        Returns:
            "buy": 金叉（快线上穿慢线）
            "sell": 死叉（快线下穿慢线）
            "none": 无信号
        """
        # 第一次运行，没有历史值
        if self.prev_fast == 0.0 or self.prev_slow == 0.0:
            return "none"

        # 金叉：快线从下方穿过慢线
        if self.prev_fast <= self.prev_slow and current_fast > current_slow:
            self.Log(
                f"[SIGNAL] Golden Cross detected! "
                f"Fast: {self.prev_fast:.2f}→{current_fast:.2f}, "
                f"Slow: {self.prev_slow:.2f}→{current_slow:.2f}"
            )
            return "buy"

        # 死叉：快线从上方穿过慢线
        if self.prev_fast >= self.prev_slow and current_fast < current_slow:
            self.Log(
                f"[SIGNAL] Death Cross detected! "
                f"Fast: {self.prev_fast:.2f}→{current_fast:.2f}, "
                f"Slow: {self.prev_slow:.2f}→{current_slow:.2f}"
            )
            return "sell"

        return "none"

    def _handle_signal(self, signal: str, current_price: float, time: datetime):
        """
        处理交易信号

        Args:
            signal: "buy" 或 "sell"
            current_price: 当前价格
            time: 当前时间
        """
        # 避免重复信号
        if signal == self.previous_signal:
            self.Log(f"[SIGNAL] Duplicate {signal} signal ignored")
            return

        # 查询当前持仓
        if self.Portfolio:
            holdings = self.Portfolio.get_holdings(self.symbol)
            current_position = holdings.quantity if holdings else 0
        else:
            current_position = 0

        if signal == "buy":
            # 金叉买入
            if current_position >= 0:
                # 无持仓或多头持仓，买入
                order_value = current_price * self.trade_quantity

                # 风险控制：检查订单金额
                if order_value > self.max_order_value:
                    self.Log(f"[RISK] Order value ${order_value:.2f} exceeds max ${self.max_order_value:.2f}, skipping")
                    return

                self.Log(f"[ORDER] Placing BUY order: {self.symbol} x {self.trade_quantity} @ ${current_price:.2f}")
                self.MarketOrder(self.symbol, self.trade_quantity)
                self.previous_signal = "buy"
            else:
                # 有空仓，先平仓再开多
                self.Log(f"[ORDER] Closing SHORT position: {self.symbol} x {-current_position}")
                self.MarketOrder(self.symbol, -current_position)

                self.Log(f"[ORDER] Opening LONG position: {self.symbol} x {self.trade_quantity}")
                self.MarketOrder(self.symbol, self.trade_quantity)
                self.previous_signal = "buy"

        elif signal == "sell":
            # 死叉卖出
            if current_position > 0:
                # 有多仓，平仓
                self.Log(f"[ORDER] Closing LONG position: {self.symbol} x {current_position}")
                self.MarketOrder(self.symbol, -current_position)
                self.previous_signal = "sell"
            else:
                # 无持仓或已经空仓，不操作
                self.Log(f"[SIGNAL] No position to close, sell signal ignored")

    def OnOrderEvent(self, order_event):
        """处理订单事件"""
        try:
            order_id = order_event.order_id
            status = order_event.status
            symbol = order_event.symbol
            quantity = order_event.quantity
            filled_quantity = order_event.filled_quantity

            if status == "Filled":
                # 订单完全成交
                avg_price = order_event.average_fill_price
                self.Log(f"[FILL] Order {order_id} filled: {symbol} x {filled_quantity} @ ${avg_price:.2f}")

                # 查询更新后的持仓
                holdings = self.Portfolio.get_holdings(symbol)
                if holdings:
                    self.Log(
                        f"[POSITION] Current position: {holdings.quantity} shares, "
                        f"Avg cost: ${holdings.average_price:.2f}, "
                        f"P&L: ${holdings.unrealized_pnl:.2f}"
                    )
                else:
                    self.Log(f"[POSITION] Position closed")

            elif status == "PartiallyFilled":
                # 部分成交
                avg_price = order_event.average_fill_price
                self.Log(
                    f"[PARTIAL] Order {order_id} partially filled: " f"{filled_quantity}/{quantity} @ ${avg_price:.2f}"
                )

            elif status == "Cancelled":
                # 订单取消
                self.Log(f"[CANCEL] Order {order_id} cancelled")

            elif status == "Rejected":
                # 订单拒绝
                error_msg = getattr(order_event, "message", "Unknown error")
                self.Log(f"[REJECT] Order {order_id} rejected: {error_msg}")

            else:
                # 其他状态
                self.Log(f"[ORDER] Order {order_id} status: {status}")

        except Exception as e:
            self.Log(f"[ERROR] Exception in OnOrderEvent: {e}")
            import traceback

            self.Log(traceback.format_exc())
