"""订单管理模块

处理订单创建、提交和状态跟踪。
"""

from typing import Optional, Callable
from ib_insync import Stock, MarketOrder, Order as IBOrder
from common.logger import log
from common.models import Order, OrderStatus
from broker.ibkr_client import IBKRClient


class OrderManager:
    """订单管理器

    负责订单的创建、提交和状态跟踪。
    """

    def __init__(self, client: IBKRClient):
        """初始化订单管理器

        Args:
            client: IBKR客户端实例
        """
        self.client = client
        self.orders = {}  # order_id -> Order

    def create_market_order(
        self,
        symbol: str,
        quantity: int,
        action: str = "BUY"
    ) -> Optional[Order]:
        """创建市价单

        Args:
            symbol: 股票代码
            quantity: 数量
            action: 操作类型 "BUY" 或 "SELL"

        Returns:
            订单对象，失败返回None
        """
        if not self.client.is_connected():
            log.error("Cannot create order: IBKR not connected")
            return None

        try:
            # 创建合约
            contract = Stock(symbol, 'SMART', 'USD')

            # 创建市价单
            ib_order = MarketOrder(action, quantity)

            # 提交订单
            trade = self.client.ib.placeOrder(contract, ib_order)

            # 创建订单对象
            order = Order(
                order_id=trade.order.orderId,
                symbol=symbol,
                action=action,
                quantity=quantity,
                order_type="MARKET",
                status=OrderStatus.SUBMITTED
            )

            self.orders[order.order_id] = order

            log.info(f"Order created: {action} {quantity} {symbol}, ID: {order.order_id}")

            return order

        except Exception as e:
            log.error(f"Failed to create order: {e}")
            return None

    def get_order(self, order_id: int) -> Optional[Order]:
        """获取订单信息

        Args:
            order_id: 订单ID

        Returns:
            订单对象，不存在返回None
        """
        return self.orders.get(order_id)

    def get_all_orders(self):
        """获取所有订单"""
        return list(self.orders.values())
