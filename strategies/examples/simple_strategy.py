"""
简单示例策略

演示如何使用 QCAlgorithm 基类
"""

from common.logger import log
from strategy.qc_algorithm import QCAlgorithm
from strategy.resolution import Resolution


class SimpleStrategy(QCAlgorithm):
    """
    简单买入持有策略

    逻辑：
    1. 启动时买入 100 股 AAPL
    2. 持有不卖
    """

    def Initialize(self):
        """策略初始化"""
        log.info("Initializing SimpleStrategy")

        # 添加股票
        self.AddEquity("AAPL", Resolution.Minute)

        # 标记是否已买入
        self.bought = False

    def OnData(self, data):
        """行情数据事件"""
        # 只在第一次数据到达时买入
        if not self.bought:
            holding = self.Portfolio["AAPL"]

            if not holding.Invested:
                log.info("Buying 100 shares of AAPL")
                self.MarketOrder("AAPL", 100)
                self.bought = True

    def OnOrderEvent(self, order_event):
        """订单事件"""
        log.info(f"Order event: {order_event.symbol} {order_event.status}")


class BuyAndSellStrategy(QCAlgorithm):
    """
    买入卖出示例策略

    逻辑：
    1. 第一次数据：买入 100 股
    2. 第二次数据：卖出 50 股
    3. 第三次数据：全部平仓
    """

    def Initialize(self):
        """策略初始化"""
        log.info("Initializing BuyAndSellStrategy")

        self.AddEquity("AAPL", Resolution.Minute)

        self.data_count = 0

    def OnData(self, data):
        """行情数据事件"""
        self.data_count += 1

        holding = self.Portfolio["AAPL"]

        if self.data_count == 1:
            # 第一次：买入 100 股
            log.info("Step 1: Buying 100 shares")
            self.MarketOrder("AAPL", 100)

        elif self.data_count == 2:
            # 第二次：卖出 50 股
            if holding.Invested and holding.Quantity >= 50:
                log.info("Step 2: Selling 50 shares")
                self.MarketOrder("AAPL", -50)

        elif self.data_count == 3:
            # 第三次：全部平仓
            if holding.Invested:
                log.info("Step 3: Liquidating all")
                self.Liquidate("AAPL")

    def OnOrderEvent(self, order_event):
        """订单事件"""
        log.info(
            f"Order {order_event.order_id}: "
            f"{order_event.action} {order_event.filled_quantity} "
            f"{order_event.symbol} @ ${order_event.avg_fill_price:.2f}"
        )
