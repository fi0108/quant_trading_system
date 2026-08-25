"""
持仓和账户封装

提供 QuantConnect 风格的持仓和账户 API
"""

from typing import Dict, Optional

from common.models import Position
from trading.position.manager import PositionManager


class SecurityHolding:
    """
    单个证券的持仓信息

    封装 Position 对象，提供 QC 风格的 API
    """

    def __init__(self, position: Optional[Position] = None):
        """
        初始化持仓

        Args:
            position: 持仓对象（可选）
        """
        self._position = position

    @property
    def Symbol(self) -> str:
        """股票代码"""
        return self._position.symbol if self._position else ""

    @property
    def Quantity(self) -> float:
        """持仓数量"""
        return self._position.quantity if self._position else 0.0

    @property
    def AveragePrice(self) -> float:
        """平均成本"""
        return self._position.avg_cost if self._position else 0.0

    @property
    def Price(self) -> float:
        """当前价格"""
        return self._position.current_price if self._position else 0.0

    @property
    def MarketValue(self) -> float:
        """市值"""
        return self._position.market_value if self._position else 0.0

    @property
    def UnrealizedProfit(self) -> float:
        """未实现盈亏"""
        return self._position.unrealized_pnl if self._position else 0.0

    @property
    def Invested(self) -> bool:
        """是否持有仓位"""
        return self.Quantity != 0

    def __repr__(self):
        return f"SecurityHolding({self.Symbol}, Qty={self.Quantity:.0f}, Price=${self.Price:.2f})"


class SecurityPortfolioManager:
    """
    投资组合管理器

    封装 PositionManager，提供 QC 风格的 API
    """

    def __init__(self, position_manager: PositionManager):
        """
        初始化投资组合

        Args:
            position_manager: 持仓管理器
        """
        self._position_manager = position_manager
        self._holdings_cache: Dict[str, SecurityHolding] = {}

    def __getitem__(self, symbol: str) -> SecurityHolding:
        """
        获取指定股票的持仓

        Args:
            symbol: 股票代码

        Returns:
            持仓对象
        """
        # 从缓存获取
        if symbol in self._holdings_cache:
            # 更新持仓数据
            position = self._position_manager.get_position(symbol)
            self._holdings_cache[symbol] = SecurityHolding(position)
        else:
            # 首次获取
            position = self._position_manager.get_position(symbol)
            self._holdings_cache[symbol] = SecurityHolding(position)

        return self._holdings_cache[symbol]

    @property
    def Cash(self) -> float:
        """
        账户现金

        TODO: 从账户管理器获取
        目前返回固定值
        """
        return 100000.0

    @property
    def TotalPortfolioValue(self) -> float:
        """
        总资产（现金 + 持仓市值）
        """
        market_value = self._position_manager.get_total_market_value()
        return self.Cash + market_value

    @property
    def TotalUnrealizedProfit(self) -> float:
        """总未实现盈亏"""
        return self._position_manager.get_total_unrealized_pnl()

    @property
    def TotalRealizedProfit(self) -> float:
        """总已实现盈亏"""
        return self._position_manager.get_total_realized_pnl()

    def get_all_holdings(self) -> Dict[str, SecurityHolding]:
        """
        获取所有持仓

        Returns:
            持仓字典 {symbol: SecurityHolding}
        """
        positions = self._position_manager.get_positions()
        holdings = {}

        for position in positions:
            holdings[position.symbol] = SecurityHolding(position)

        return holdings
