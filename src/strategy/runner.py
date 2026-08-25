"""
策略运行器

用于启动和运行策略
"""

from typing import Type

from common.logger import log
from data.ibkr_client import IBKRClient
from strategy.qc_algorithm import QCAlgorithm
from trading.order.manager import OrderManager
from trading.position.manager import PositionManager


class StrategyRunner:
    """
    策略运行器

    负责：
    - 初始化依赖
    - 启动策略
    - 管理生命周期
    """

    def __init__(
        self,
        strategy_class: Type[QCAlgorithm],
        ibkr_client: IBKRClient,
        order_manager: OrderManager,
        position_manager: PositionManager,
    ):
        """
        初始化运行器

        Args:
            strategy_class: 策略类
            ibkr_client: IBKR 客户端
            order_manager: 订单管理器
            position_manager: 持仓管理器
        """
        self.strategy_class = strategy_class
        self.ibkr_client = ibkr_client
        self.order_manager = order_manager
        self.position_manager = position_manager

        self.strategy: Optional[QCAlgorithm] = None

    def start(self):
        """启动策略"""
        log.info("=" * 80)
        log.info(f"Starting strategy: {self.strategy_class.__name__}")
        log.info("=" * 80)

        # 创建策略实例
        self.strategy = self.strategy_class(
            ibkr_client=self.ibkr_client, order_manager=self.order_manager, position_manager=self.position_manager
        )

        # 运行初始化
        self.strategy._run_initialize()

        log.info("Strategy started successfully")
        log.info("=" * 80)

    def stop(self):
        """停止策略"""
        log.info(f"Stopping strategy: {self.strategy_class.__name__}")
        # TODO: 清理资源
        self.strategy = None

    def process_data(self, data):
        """
        处理行情数据

        Args:
            data: 行情数据
        """
        if self.strategy:
            self.strategy._process_data(data)
