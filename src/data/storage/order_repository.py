"""
订单数据访问层

提供订单的增删改查操作
"""

from typing import List, Optional
from datetime import datetime

from data.storage.models import OrderModel, database
from common.logger import log
from common.models import Order, OrderStatus


class OrderRepository:
    """订单数据仓库"""

    @staticmethod
    def save(order: Order) -> bool:
        """
        保存订单到数据库

        Args:
            order: Order对象

        Returns:
            True表示保存成功
        """
        try:
            with database.atomic():
                OrderModel.create(
                    order_id=order.order_id,
                    symbol=order.symbol,
                    action=order.action,
                    order_type=order.order_type,
                    quantity=order.quantity,
                    limit_price=order.limit_price,
                    status=order.status.value,
                    filled_quantity=order.filled_quantity,
                    avg_fill_price=order.avg_fill_price,
                    created_at=order.created_at or datetime.now(),
                    filled_at=order.filled_at,
                    updated_at=datetime.now()
                )
            log.info(f"Order saved: {order.order_id}")
            return True

        except Exception as e:
            log.error(f"Failed to save order {order.order_id}: {e}")
            return False

    @staticmethod
    def update(order: Order) -> bool:
        """
        更新订单状态

        Args:
            order: Order对象

        Returns:
            True表示更新成功
        """
        try:
            query = OrderModel.update(
                status=order.status.value,
                filled_quantity=order.filled_quantity,
                avg_fill_price=order.avg_fill_price,
                filled_at=order.filled_at,
                updated_at=datetime.now()
            ).where(OrderModel.order_id == order.order_id)

            rows_updated = query.execute()

            if rows_updated > 0:
                log.info(f"Order updated: {order.order_id} -> {order.status.value}")
                return True
            else:
                log.warning(f"Order not found for update: {order.order_id}")
                return False

        except Exception as e:
            log.error(f"Failed to update order {order.order_id}: {e}")
            return False

    @staticmethod
    def get_by_id(order_id: int) -> Optional[Order]:
        """
        根据订单ID查询

        Args:
            order_id: 订单ID

        Returns:
            Order对象，不存在返回None
        """
        try:
            model = OrderModel.get(OrderModel.order_id == order_id)
            return OrderRepository._model_to_order(model)

        except OrderModel.DoesNotExist:
            return None

        except Exception as e:
            log.error(f"Failed to get order {order_id}: {e}")
            return None

    @staticmethod
    def get_all(limit: int = 100) -> List[Order]:
        """
        获取所有订单

        Args:
            limit: 返回数量限制

        Returns:
            Order对象列表
        """
        try:
            models = OrderModel.select().order_by(OrderModel.created_at.desc()).limit(limit)
            return [OrderRepository._model_to_order(m) for m in models]

        except Exception as e:
            log.error(f"Failed to get orders: {e}")
            return []

    @staticmethod
    def get_by_symbol(symbol: str, limit: int = 50) -> List[Order]:
        """
        按标的查询订单

        Args:
            symbol: 股票代码
            limit: 返回数量限制

        Returns:
            Order对象列表
        """
        try:
            models = (OrderModel
                      .select()
                      .where(OrderModel.symbol == symbol)
                      .order_by(OrderModel.created_at.desc())
                      .limit(limit))

            return [OrderRepository._model_to_order(m) for m in models]

        except Exception as e:
            log.error(f"Failed to get orders for {symbol}: {e}")
            return []

    @staticmethod
    def get_by_status(status: OrderStatus, limit: int = 50) -> List[Order]:
        """
        按状态查询订单

        Args:
            status: 订单状态
            limit: 返回数量限制

        Returns:
            Order对象列表
        """
        try:
            models = (OrderModel
                      .select()
                      .where(OrderModel.status == status.value)
                      .order_by(OrderModel.created_at.desc())
                      .limit(limit))

            return [OrderRepository._model_to_order(m) for m in models]

        except Exception as e:
            log.error(f"Failed to get orders by status {status}: {e}")
            return []

    @staticmethod
    def _model_to_order(model: OrderModel) -> Order:
        """
        将ORM模型转换为Order对象

        Args:
            model: OrderModel实例

        Returns:
            Order对象
        """
        return Order(
            order_id=model.order_id,
            symbol=model.symbol,
            action=model.action,
            order_type=model.order_type,
            quantity=model.quantity,
            limit_price=float(model.limit_price) if model.limit_price else None,
            status=OrderStatus(model.status),
            filled_quantity=model.filled_quantity,
            avg_fill_price=float(model.avg_fill_price) if model.avg_fill_price else None,
            created_at=model.created_at,
            filled_at=model.filled_at
        )
