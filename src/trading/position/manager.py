"""持仓管理模块

管理和查询持仓信息
"""

from typing import List, Optional

from common.logger import log
from common.models import Order, Position
from data.ibkr_client import IBKRClient
from data.storage.position_repository import PositionRepository
from trading.position.tracker import PositionTracker


class PositionManager:
    """持仓管理器

    功能增强：
    - 集成 PositionTracker 自动跟踪持仓
    - 订单成交后自动更新持仓
    - 定期与 IBKR 同步对账
    - 持仓持久化到数据库
    """

    def __init__(
        self, client: IBKRClient, position_repository: Optional[PositionRepository] = None, enable_tracking: bool = True
    ):
        """初始化持仓管理器

        Args:
            client: IBKR客户端实例
            position_repository: 持仓仓库（可选）
            enable_tracking: 是否启用自动跟踪
        """
        self.client = client
        self.repo = position_repository or PositionRepository()

        # 持仓跟踪器
        self.tracker = None
        if enable_tracking:
            self.tracker = PositionTracker(client.ib, self.repo)
            log.info("Position tracking enabled")

    def on_order_filled(self, order: Order):
        """
        订单成交回调

        由 OrderManager 调用，自动更新持仓

        Args:
            order: 成交的订单
        """
        if self.tracker:
            self.tracker.on_order_filled(order)

    def sync_with_ibkr(self):
        """与 IBKR 同步持仓"""
        if self.tracker:
            self.tracker.sync_with_ibkr()
        else:
            log.warning("Position tracking not enabled")

    def get_positions(self) -> List[Position]:
        """获取所有持仓

        Returns:
            持仓列表
        """
        if self.tracker:
            return self.tracker.get_all_positions()
        else:
            return self.repo.get_all()

    def get_position(self, symbol: str) -> Optional[Position]:
        """获取指定标的的持仓

        Args:
            symbol: 股票代码

        Returns:
            持仓对象，不存在则返回 None
        """
        if self.tracker:
            return self.tracker.get_position(symbol)
        else:
            return self.repo.get_by_symbol(symbol)

    def get_total_market_value(self) -> float:
        """获取总市值"""
        if self.tracker:
            return self.tracker.get_total_market_value()
        else:
            positions = self.repo.get_all()
            return sum(pos.market_value for pos in positions)

    def get_total_unrealized_pnl(self) -> float:
        """获取总未实现盈亏"""
        if self.tracker:
            return self.tracker.get_total_unrealized_pnl()
        else:
            positions = self.repo.get_all()
            return sum(pos.unrealized_pnl for pos in positions)

    def get_total_realized_pnl(self) -> float:
        """获取总已实现盈亏"""
        if self.tracker:
            return self.tracker.get_total_realized_pnl()
        else:
            positions = self.repo.get_all()
            return sum(pos.realized_pnl for pos in positions)

    def print_positions(self):
        """打印持仓信息"""
        positions = self.get_positions()

        if not positions:
            log.info("No positions")
            return

        log.info("=" * 80)
        log.info("Current Positions")
        log.info("=" * 80)

        for pos in positions:
            log.info(
                f"{pos.symbol:6s} | "
                f"Qty: {pos.quantity:8.0f} | "
                f"Avg Cost: ${pos.avg_cost:8.2f} | "
                f"Market Value: ${pos.market_value:10.2f} | "
                f"P&L: ${pos.unrealized_pnl:8.2f}"
            )

        log.info("-" * 80)
        log.info(f"Total Market Value: ${self.get_total_market_value():.2f}")
        log.info(f"Total Unrealized P&L: ${self.get_total_unrealized_pnl():.2f}")
        log.info(f"Total Realized P&L: ${self.get_total_realized_pnl():.2f}")
        log.info("=" * 80)
