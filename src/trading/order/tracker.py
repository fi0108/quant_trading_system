"""
订单状态跟踪器

监听 IBKR 订单状态变化，自动更新数据库和通知持仓管理器
"""

from datetime import datetime
from typing import Callable, List, Optional

from ib_insync import IB, Fill, Trade

from common.logger import log
from common.models import Order, OrderStatus
from data.storage.order_repository import OrderRepository


class OrderTracker:
    """订单状态跟踪器

    功能：
    - 监听 IBKR 订单状态事件
    - 自动更新数据库
    - 订单成交后触发回调（通知持仓管理器）
    """

    def __init__(self, ib: IB, order_repository: Optional[OrderRepository] = None):
        """
        初始化订单跟踪器

        Args:
            ib: IBKR 连接对象
            order_repository: 订单仓库（可选）
        """
        self.ib = ib
        self.repo = order_repository or OrderRepository()

        # 成交回调列表
        self._on_filled_callbacks: List[Callable[[Order], None]] = []

        # 订单缓存（order_id -> Order）
        self._orders = {}

    def start(self):
        """开始跟踪订单状态"""
        # 注册 IBKR 事件
        self.ib.orderStatusEvent += self._on_order_status
        self.ib.execDetailsEvent += self._on_execution

        log.info("OrderTracker started")

    def stop(self):
        """停止跟踪"""
        # 移除事件监听
        self.ib.orderStatusEvent -= self._on_order_status
        self.ib.execDetailsEvent -= self._on_execution

        log.info("OrderTracker stopped")

    def register_filled_callback(self, callback: Callable[[Order], None]):
        """
        注册订单成交回调

        Args:
            callback: 回调函数，参数为成交的订单
        """
        self._on_filled_callbacks.append(callback)

    def _on_order_status(self, trade: Trade):
        """
        订单状态变化事件

        Args:
            trade: IBKR Trade 对象
        """
        try:
            order_id = trade.order.orderId
            status_str = trade.orderStatus.status

            log.info(f"Order status changed: #{order_id} -> {status_str}")

            # 映射 IBKR 状态到本地状态
            status = self._map_status(status_str)

            if status is None:
                log.warning(f"Unknown order status: {status_str}")
                return

            # 更新订单对象
            order = self._get_or_create_order(trade)
            order.status = status
            order.filled_quantity = int(trade.orderStatus.filled)

            if trade.orderStatus.avgFillPrice > 0:
                order.avg_fill_price = trade.orderStatus.avgFillPrice

            # 如果已成交，记录成交时间
            if status == OrderStatus.FILLED:
                order.filled_at = datetime.now()

            # 保存到数据库
            self.repo.save(order)

            # 更新缓存
            self._orders[order_id] = order

            # 如果完全成交，触发回调
            if status == OrderStatus.FILLED:
                self._trigger_filled_callbacks(order)

        except Exception as e:
            log.error(f"Error handling order status: {e}", exc_info=True)

    def _on_execution(self, trade: Trade, fill: Fill):
        """
        订单成交事件

        Args:
            trade: IBKR Trade 对象
            fill: 成交详情
        """
        try:
            order_id = trade.order.orderId

            log.info(f"Order execution: #{order_id}, " f"filled {fill.execution.shares} @ {fill.execution.avgPrice}")

            # 更新订单
            order = self._get_or_create_order(trade)
            order.filled_quantity = int(trade.orderStatus.filled)
            order.avg_fill_price = fill.execution.avgPrice

            # 保存到数据库
            self.repo.save(order)

        except Exception as e:
            log.error(f"Error handling execution: {e}", exc_info=True)

    def _get_or_create_order(self, trade: Trade) -> Order:
        """
        获取或创建订单对象

        Args:
            trade: IBKR Trade 对象

        Returns:
            Order 对象
        """
        order_id = trade.order.orderId

        # 先从缓存查找
        if order_id in self._orders:
            return self._orders[order_id]

        # 从数据库查找
        order = self.repo.get_by_id(order_id)
        if order:
            self._orders[order_id] = order
            return order

        # 创建新订单
        order = Order(
            order_id=order_id,
            symbol=trade.contract.symbol,
            action=trade.order.action,
            quantity=int(trade.order.totalQuantity),
            order_type=trade.order.orderType,
            status=self._map_status(trade.orderStatus.status),
            limit_price=trade.order.lmtPrice if trade.order.lmtPrice else None,
            filled_quantity=int(trade.orderStatus.filled),
            avg_fill_price=trade.orderStatus.avgFillPrice if trade.orderStatus.avgFillPrice > 0 else None,
            created_at=datetime.now(),
        )

        self._orders[order_id] = order
        return order

    def _map_status(self, ibkr_status: str) -> Optional[OrderStatus]:
        """
        映射 IBKR 状态到本地状态

        Args:
            ibkr_status: IBKR 状态字符串

        Returns:
            本地 OrderStatus 枚举
        """
        mapping = {
            "Submitted": OrderStatus.SUBMITTED,
            "PreSubmitted": OrderStatus.SUBMITTED,
            "PendingSubmit": OrderStatus.SUBMITTED,
            "Filled": OrderStatus.FILLED,
            "Cancelled": OrderStatus.CANCELLED,
            "ApiCancelled": OrderStatus.CANCELLED,
            "Inactive": OrderStatus.REJECTED,
        }

        return mapping.get(ibkr_status)

    def _trigger_filled_callbacks(self, order: Order):
        """
        触发成交回调

        Args:
            order: 成交的订单
        """
        for callback in self._on_filled_callbacks:
            try:
                callback(order)
            except Exception as e:
                log.error(f"Error in filled callback: {e}", exc_info=True)

    def get_order(self, order_id: int) -> Optional[Order]:
        """
        获取订单

        Args:
            order_id: 订单ID

        Returns:
            订单对象，不存在则返回 None
        """
        # 先从缓存查找
        if order_id in self._orders:
            return self._orders[order_id]

        # 从数据库查找
        return self.repo.get_by_id(order_id)
