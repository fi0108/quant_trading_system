"""持仓管理模块

查询和管理持仓信息。
"""

from typing import List
from common.logger import log
from common.models import Position
from data.ibkr_client import IBKRClient


class PositionManager:
    """持仓管理器

    负责持仓查询和跟踪。
    """

    def __init__(self, client: IBKRClient):
        """初始化持仓管理器

        Args:
            client: IBKR客户端实例
        """
        self.client = client

    def get_positions(self) -> List[Position]:
        """获取当前持仓

        Returns:
            持仓列表
        """
        if not self.client.is_connected():
            log.error("Cannot get positions: IBKR not connected")
            return []

        try:
            positions = []

            # 从IBKR获取持仓
            ib_positions = self.client.ib.positions()

            for pos in ib_positions:
                position = Position(
                    symbol=pos.contract.symbol,
                    quantity=pos.position,
                    avg_cost=pos.avgCost,
                    market_value=pos.marketValue,
                    unrealized_pnl=pos.unrealizedPNL
                )
                positions.append(position)

            log.info(f"Retrieved {len(positions)} positions")

            return positions

        except Exception as e:
            log.error(f"Failed to get positions: {e}")
            return []

    def print_positions(self):
        """打印持仓信息"""
        positions = self.get_positions()

        if not positions:
            log.info("No positions")
            return

        log.info("=" * 60)
        log.info("Current Positions:")
        log.info("-" * 60)

        for pos in positions:
            log.info(
                f"{pos.symbol:8s} | "
                f"Qty: {pos.quantity:6.0f} | "
                f"Avg: ${pos.avg_cost:8.2f} | "
                f"Value: ${pos.market_value:10.2f} | "
                f"P&L: ${pos.unrealized_pnl:8.2f}"
            )

        log.info("=" * 60)
