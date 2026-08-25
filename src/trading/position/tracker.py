"""
持仓跟踪器

根据订单成交自动更新持仓，并与 IBKR 定期同步
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from ib_insync import IB

from common.logger import log
from common.models import Order, Position
from data.storage.position_repository import PositionRepository


class PositionTracker:
    """持仓跟踪器

    功能：
    - 订单成交后自动更新持仓
    - 计算平均成本和盈亏
    - 与 IBKR 定期同步（对账）
    - 持仓持久化到数据库
    """

    def __init__(self, ib: IB, position_repository: Optional[PositionRepository] = None):
        """
        初始化持仓跟踪器

        Args:
            ib: IBKR 连接对象
            position_repository: 持仓仓库（可选）
        """
        self.ib = ib
        self.repo = position_repository or PositionRepository()

        # 持仓缓存（symbol -> Position）
        self._positions: Dict[str, Position] = {}

        # 加载已有持仓
        self._load_positions()

    def _load_positions(self):
        """从数据库加载持仓"""
        try:
            positions = self.repo.get_all()
            for pos in positions:
                self._positions[pos.symbol] = pos
            log.info(f"Loaded {len(positions)} positions from database")
        except Exception as e:
            log.error(f"Failed to load positions: {e}")

    def on_order_filled(self, order: Order):
        """
        订单成交回调

        根据成交订单更新持仓

        Args:
            order: 成交的订单
        """
        try:
            symbol = order.symbol
            quantity = order.filled_quantity
            price = order.avg_fill_price

            if price is None or price <= 0:
                log.warning(f"Invalid fill price for order {order.order_id}")
                return

            # 获取或创建持仓
            position = self._positions.get(symbol)

            if order.action == "BUY":
                position = self._handle_buy(symbol, quantity, price, position)
            elif order.action == "SELL":
                position = self._handle_sell(symbol, quantity, price, position)
            else:
                log.warning(f"Unknown order action: {order.action}")
                return

            # 更新缓存
            if position and position.quantity > 0:
                self._positions[symbol] = position
            elif symbol in self._positions:
                # 持仓清零，移除
                del self._positions[symbol]

            # 保存到数据库
            if position:
                self.repo.save_or_update(position)

            log.info(f"Position updated: {symbol}, qty={position.quantity if position else 0}")

        except Exception as e:
            log.error(f"Error updating position for order {order.order_id}: {e}", exc_info=True)

    def _handle_buy(self, symbol: str, quantity: int, price: float, existing_position: Optional[Position]) -> Position:
        """
        处理买入

        Args:
            symbol: 股票代码
            quantity: 买入数量
            price: 买入价格
            existing_position: 现有持仓（可选）

        Returns:
            更新后的持仓
        """
        if existing_position is None:
            # 新建持仓
            position = Position(
                symbol=symbol,
                quantity=float(quantity),
                avg_cost=price,
                market_value=quantity * price,
                unrealized_pnl=0.0,
                current_price=price,
                realized_pnl=0.0,
            )
            log.info(f"New position: {symbol}, qty={quantity}, cost={price:.2f}")
        else:
            # 增加持仓，重新计算平均成本
            old_qty = existing_position.quantity
            old_cost = existing_position.avg_cost
            new_qty = old_qty + quantity
            new_avg_cost = (old_qty * old_cost + quantity * price) / new_qty

            position = Position(
                symbol=symbol,
                quantity=new_qty,
                avg_cost=new_avg_cost,
                market_value=new_qty * price,
                unrealized_pnl=new_qty * (price - new_avg_cost),
                current_price=price,
                realized_pnl=existing_position.realized_pnl,
            )
            log.info(
                f"Increased position: {symbol}, "
                f"qty={old_qty:.0f}→{new_qty:.0f}, "
                f"avg_cost={old_cost:.2f}→{new_avg_cost:.2f}"
            )

        return position

    def _handle_sell(
        self, symbol: str, quantity: int, price: float, existing_position: Optional[Position]
    ) -> Optional[Position]:
        """
        处理卖出

        Args:
            symbol: 股票代码
            quantity: 卖出数量
            price: 卖出价格
            existing_position: 现有持仓

        Returns:
            更新后的持仓，如果持仓清零则返回 None
        """
        if existing_position is None:
            log.warning(f"Cannot sell {symbol}: no position")
            return None

        old_qty = existing_position.quantity
        if quantity > old_qty:
            log.warning(f"Sell quantity ({quantity}) exceeds position ({old_qty})")
            quantity = int(old_qty)

        # 计算已实现盈亏
        realized_pnl = quantity * (price - existing_position.avg_cost)
        new_qty = old_qty - quantity

        if new_qty <= 0:
            # 持仓清零
            log.info(f"Position closed: {symbol}, realized_pnl={realized_pnl:.2f}")
            # 删除持仓
            self.repo.delete(symbol)
            return None
        else:
            # 部分卖出
            position = Position(
                symbol=symbol,
                quantity=new_qty,
                avg_cost=existing_position.avg_cost,  # 平均成本不变
                market_value=new_qty * price,
                unrealized_pnl=new_qty * (price - existing_position.avg_cost),
                current_price=price,
                realized_pnl=existing_position.realized_pnl + realized_pnl,
            )
            log.info(
                f"Decreased position: {symbol}, "
                f"qty={old_qty:.0f}→{new_qty:.0f}, "
                f"realized_pnl={realized_pnl:.2f}"
            )
            return position

    def sync_with_ibkr(self):
        """
        与 IBKR 同步持仓（对账）

        定期调用，确保本地持仓与 IBKR 一致
        """
        try:
            # 获取 IBKR 持仓
            ib_positions = self.ib.positions()

            log.info(f"Syncing positions with IBKR: {len(ib_positions)} positions")

            # 对比并更新
            synced_symbols = set()

            for ib_pos in ib_positions:
                symbol = ib_pos.contract.symbol
                quantity = float(ib_pos.position)
                avg_cost = float(ib_pos.avgCost)

                # 获取当前市场价
                market_value = float(ib_pos.marketValue) if ib_pos.marketValue else quantity * avg_cost
                unrealized_pnl = float(ib_pos.unrealizedPNL) if ib_pos.unrealizedPNL else 0.0

                # 创建或更新持仓
                position = Position(
                    symbol=symbol,
                    quantity=quantity,
                    avg_cost=avg_cost,
                    market_value=market_value,
                    unrealized_pnl=unrealized_pnl,
                    current_price=market_value / quantity if quantity > 0 else avg_cost,
                    realized_pnl=0.0,  # IBKR 不提供已实现盈亏
                )

                # 更新缓存和数据库
                self._positions[symbol] = position
                self.repo.save_or_update(position)

                synced_symbols.add(symbol)

            # 删除不在 IBKR 的持仓
            local_symbols = set(self._positions.keys())
            removed_symbols = local_symbols - synced_symbols

            for symbol in removed_symbols:
                log.info(f"Removing position not in IBKR: {symbol}")
                del self._positions[symbol]
                self.repo.delete(symbol)

            log.info(f"Position sync completed: {len(self._positions)} positions")

        except Exception as e:
            log.error(f"Failed to sync positions: {e}", exc_info=True)

    def get_position(self, symbol: str) -> Optional[Position]:
        """
        获取持仓

        Args:
            symbol: 股票代码

        Returns:
            持仓对象，不存在则返回 None
        """
        # 先从缓存获取
        position = self._positions.get(symbol)
        if position:
            return position

        # 从数据库获取
        return self.repo.get_by_symbol(symbol)

    def get_all_positions(self) -> List[Position]:
        """获取所有持仓"""
        return list(self._positions.values())

    def get_total_market_value(self) -> float:
        """获取总市值"""
        return sum(pos.market_value for pos in self._positions.values())

    def get_total_unrealized_pnl(self) -> float:
        """获取总未实现盈亏"""
        return sum(pos.unrealized_pnl for pos in self._positions.values())

    def get_total_realized_pnl(self) -> float:
        """获取总已实现盈亏"""
        return sum(pos.realized_pnl for pos in self._positions.values())
