"""风控管理模块

实现基础风控检查。
"""

from common.logger import log
from data.ibkr_client import IBKRClient


class RiskManager:
    """风控管理器

    负责交易前的风控检查。
    """

    def __init__(self, client: IBKRClient, min_cash: float = 200.0):
        """初始化风控管理器

        Args:
            client: IBKR客户端实例
            min_cash: 最小现金余额要求
        """
        self.client = client
        self.min_cash = min_cash

    def check_cash(self) -> bool:
        """检查现金余额

        Returns:
            True表示通过，False表示不通过
        """
        if not self.client.is_connected():
            log.error("Cannot check cash: IBKR not connected")
            return False

        try:
            # 获取账户信息
            account_values = self.client.ib.accountValues()

            # 查找可用现金
            cash = 0.0
            for item in account_values:
                if item.tag == "AvailableFunds":
                    cash = float(item.value)
                    break

            log.info(f"Available cash: ${cash:.2f}, Required: ${self.min_cash:.2f}")

            if cash < self.min_cash:
                log.warning(f"Insufficient cash: ${cash:.2f} < ${self.min_cash:.2f}")
                return False

            return True

        except Exception as e:
            log.error(f"Failed to check cash: {e}")
            return False

    def can_place_order(self, symbol: str, quantity: int, action: str) -> bool:
        """检查是否可以下单

        Args:
            symbol: 股票代码
            quantity: 数量
            action: 操作类型

        Returns:
            True表示可以下单，False表示不可以
        """
        # Week 1 只检查现金
        if action == "BUY":
            return self.check_cash()

        # SELL 暂时不检查持仓
        return True
