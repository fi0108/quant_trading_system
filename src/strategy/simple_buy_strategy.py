"""固定买入策略

Week 1 Hello World版本：每收到10次数据买入1股。
"""

from ..common.logger import log
from ..common.models import Bar
from ..broker.order_manager import OrderManager
from ..broker.risk_manager import RiskManager


class SimpleBuyStrategy:
    """固定买入策略

    每收到10次数据买入1股AAPL，不看价格、不看持仓。
    """

    def __init__(
        self,
        order_manager: OrderManager,
        risk_manager: RiskManager,
        symbol: str = "AAPL",
        buy_interval: int = 10
    ):
        """初始化策略

        Args:
            order_manager: 订单管理器
            risk_manager: 风控管理器
            symbol: 交易标的
            buy_interval: 每N次数据买入一次
        """
        self.order_manager = order_manager
        self.risk_manager = risk_manager
        self.symbol = symbol
        self.buy_interval = buy_interval

        self.bar_count = 0

    def on_bar(self, bar: Bar):
        """处理K线数据

        Args:
            bar: K线数据
        """
        self.bar_count += 1

        log.info(
            f"[Bar {self.bar_count}] {bar.symbol} | "
            f"Time: {bar.timestamp} | "
            f"Close: ${bar.close:.2f} | "
            f"Volume: {bar.volume}"
        )

        # 每10次数据买入1股
        if self.bar_count % self.buy_interval == 0:
            self._try_buy()

    def _try_buy(self):
        """尝试买入"""
        log.info(f"Attempting to buy 1 share of {self.symbol}...")

        # 风控检查
        if not self.risk_manager.can_place_order(self.symbol, 1, "BUY"):
            log.warning("Risk check failed, order rejected")
            return

        # 下单
        order = self.order_manager.create_market_order(
            symbol=self.symbol,
            quantity=1,
            action="BUY"
        )

        if order:
            log.info(f"Order placed successfully: ID={order.order_id}")
        else:
            log.error("Failed to place order")
