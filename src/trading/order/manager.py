"""订单管理模块

处理订单创建、提交和状态跟踪。
"""

from typing import Callable, List, Optional

from ib_insync import LimitOrder, MarketOrder
from ib_insync import Order as IBOrder
from ib_insync import Stock

from common.logger import log
from common.models import Order, OrderStatus
from data.ibkr_client import IBKRClient
from data.storage.order_repository import OrderRepository
from trading.order.tracker import OrderTracker


class OrderManager:
    """订单管理器

    负责订单的创建、提交和状态跟踪。

    功能增强：
    - 集成 OrderTracker 自动跟踪订单状态
    - 订单持久化到数据库
    - 订单历史查询
    """

    def __init__(
        self, client: IBKRClient, order_repository: Optional[OrderRepository] = None, enable_tracking: bool = True
    ):
        """初始化订单管理器

        Args:
            client: IBKR客户端实例
            order_repository: 订单仓库（可选）
            enable_tracking: 是否启用自动跟踪
        """
        self.client = client
        self.repo = order_repository or OrderRepository()

        # 订单跟踪器
        self.tracker = None
        if enable_tracking:
            self.tracker = OrderTracker(client.ib, self.repo)
            self.tracker.start()
            log.info("Order tracking enabled")

    def register_filled_callback(self, callback: Callable[[Order], None]):
        """
        注册订单成交回调

        用于通知持仓管理器更新持仓

        Args:
            callback: 回调函数，参数为成交的订单
        """
        if self.tracker:
            self.tracker.register_filled_callback(callback)

    def create_market_order(self, symbol: str, quantity: int, action: str = "BUY") -> Optional[Order]:
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
            contract = Stock(symbol, "SMART", "USD")

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
                status=OrderStatus.SUBMITTED,
            )

            # 保存到数据库
            self.repo.save(order)

            log.info(f"Order created: {action} {quantity} {symbol}, ID: {order.order_id}")

            return order

        except Exception as e:
            log.error(f"Failed to create order: {e}")
            return None

    def create_limit_order(
        self, symbol: str, quantity: int, limit_price: float, action: str = "BUY"
    ) -> Optional[Order]:
        """创建限价单

        Args:
            symbol: 股票代码
            quantity: 数量
            limit_price: 限价
            action: 操作类型 "BUY" 或 "SELL"

        Returns:
            订单对象，失败返回None
        """
        if not self.client.is_connected():
            log.error("Cannot create order: IBKR not connected")
            return None

        try:
            # 创建合约
            contract = Stock(symbol, "SMART", "USD")

            # 创建限价单
            ib_order = LimitOrder(action, quantity, limit_price)

            # 提交订单
            trade = self.client.ib.placeOrder(contract, ib_order)

            # 创建订单对象
            order = Order(
                order_id=trade.order.orderId,
                symbol=symbol,
                action=action,
                quantity=quantity,
                order_type="LIMIT",
                limit_price=limit_price,
                status=OrderStatus.SUBMITTED,
            )

            # 保存到数据库
            self.repo.save(order)

            log.info(f"Limit order created: {action} {quantity} {symbol} @ {limit_price}, ID: {order.order_id}")

            return order

        except Exception as e:
            log.error(f"Failed to create limit order: {e}")
            return None

    def get_order(self, order_id: int) -> Optional[Order]:
        """获取订单信息

        Args:
            order_id: 订单ID

        Returns:
            订单对象，不存在返回None
        """
        # 优先从跟踪器获取（有最新状态）
        if self.tracker:
            order = self.tracker.get_order(order_id)
            if order:
                return order

        # 从数据库获取
        return self.repo.get_by_id(order_id)

    def get_all_orders(self) -> List[Order]:
        """获取所有订单"""
        return self.repo.get_all()

    def get_orders_by_symbol(self, symbol: str) -> List[Order]:
        """获取指定标的的所有订单

        Args:
            symbol: 股票代码

        Returns:
            订单列表
        """
        return self.repo.get_by_symbol(symbol)

    def get_orders_by_status(self, status: OrderStatus) -> List[Order]:
        """获取指定状态的订单

        Args:
            status: 订单状态

        Returns:
            订单列表
        """
        return self.repo.get_by_status(status)

    def cancel_order(self, order_id: int) -> bool:
        """取消订单

        Args:
            order_id: 订单ID

        Returns:
            是否成功
        """
        if not self.client.is_connected():
            log.error("Cannot cancel order: IBKR not connected")
            return False

        try:
            # 获取订单
            order = self.get_order(order_id)
            if not order:
                log.error(f"Order not found: {order_id}")
                return False

            # 查找对应的 IBKR Trade
            trades = [t for t in self.client.ib.trades() if t.order.orderId == order_id]
            if not trades:
                log.error(f"IBKR trade not found for order: {order_id}")
                return False

            # 取消订单
            self.client.ib.cancelOrder(trades[0].order)
            log.info(f"Order cancelled: {order_id}")
            return True

        except Exception as e:
            log.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def stop(self):
        """停止订单管理器"""
        if self.tracker:
            self.tracker.stop()
            log.info("Order tracking stopped")
