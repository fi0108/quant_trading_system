"""
SMA 双均线策略示例

使用 SMA 指标实现经典的双均线交易策略
"""

from common.logger import log
from strategy.qc_algorithm import QCAlgorithm
from strategy.resolution import Resolution


class SMAStrategy(QCAlgorithm):
    """
    SMA 双均线策略

    策略逻辑：
    1. 使用快线（10日）和慢线（20日）
    2. 金叉（快线上穿慢线）→ 买入
    3. 死叉（快线下穿慢线）→ 卖出
    """

    def Initialize(self):
        """策略初始化"""
        log.info("=" * 80)
        log.info("Initializing SMA Crossover Strategy")
        log.info("=" * 80)

        # 添加股票
        self.symbol = "AAPL"
        self.AddEquity(self.symbol, Resolution.Daily)

        # 创建指标
        self.sma_fast = self.SMA(self.symbol, 10, Resolution.Daily)
        self.sma_slow = self.SMA(self.symbol, 20, Resolution.Daily)

        # 记录上一次的快慢线关系
        self._last_cross_above = None

        log.info("Strategy initialized successfully")
        log.info("=" * 80)

    def OnData(self, data):
        """行情数据事件"""
        # 等待指标就绪
        if not self.sma_fast.IsReady or not self.sma_slow.IsReady:
            log.debug(
                f"Warming up: fast={self.sma_fast.Samples}/{self.sma_fast.Period}, slow={self.sma_slow.Samples}/{self.sma_slow.Period}"
            )
            return

        # 获取指标值
        fast_value = self.sma_fast.Current.Value
        slow_value = self.sma_slow.Current.Value

        # 判断当前关系
        current_cross_above = fast_value > slow_value

        # 检查交叉
        if self._last_cross_above is not None:
            # 金叉（快线上穿慢线）
            if current_cross_above and not self._last_cross_above:
                log.info(f"Golden Cross! SMA_fast={fast_value:.2f} > SMA_slow={slow_value:.2f}")
                self._on_golden_cross()

            # 死叉（快线下穿慢线）
            elif not current_cross_above and self._last_cross_above:
                log.info(f"Death Cross! SMA_fast={fast_value:.2f} < SMA_slow={slow_value:.2f}")
                self._on_death_cross()

        # 更新状态
        self._last_cross_above = current_cross_above

    def _on_golden_cross(self):
        """金叉信号处理"""
        holding = self.Portfolio[self.symbol]

        if not holding.Invested:
            # 买入
            log.info(f"BUY signal: Buying 100 shares of {self.symbol}")
            self.MarketOrder(self.symbol, 100)
        else:
            log.info("Already holding position, skip buy")

    def _on_death_cross(self):
        """死叉信号处理"""
        holding = self.Portfolio[self.symbol]

        if holding.Invested:
            # 卖出
            log.info(f"SELL signal: Liquidating {self.symbol}")
            self.Liquidate(self.symbol)
        else:
            log.info("No position to liquidate, skip sell")

    def OnOrderEvent(self, order_event):
        """订单事件"""
        log.info(
            f"Order {order_event.order_id}: {order_event.action} {order_event.filled_quantity} "
            f"{order_event.symbol} @ ${order_event.avg_fill_price:.2f} - Status: {order_event.status}"
        )
