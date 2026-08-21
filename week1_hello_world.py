"""Week 1 Hello World 主程序

实现验收标准：
1. 连接IBKR
2. 订阅AAPL 5秒Bar
3. 每10次数据买入1股
4. 检查现金余额
5. 打印持仓和订单
"""

import signal
import sys
from src.broker.ibkr_client import IBKRClient
from src.broker.order_manager import OrderManager
from src.broker.risk_manager import RiskManager
from src.broker.position_manager import PositionManager
from src.data.realtime_feed import RealtimeDataFeed
from src.strategy.simple_buy_strategy import SimpleBuyStrategy
from src.common.logger import log


class TradingSystem:
    """Week 1 交易系统"""

    def __init__(self):
        self.client = None
        self.feed = None
        self.running = False

    def setup(self):
        """初始化系统组件"""
        log.info("Initializing trading system...")

        # 初始化客户端
        self.client = IBKRClient()

        # 初始化管理器
        self.order_manager = OrderManager(self.client)
        self.risk_manager = RiskManager(self.client, min_cash=200.0)
        self.position_manager = PositionManager(self.client)

        # 初始化策略
        self.strategy = SimpleBuyStrategy(
            order_manager=self.order_manager,
            risk_manager=self.risk_manager,
            symbol="AAPL",
            buy_interval=10
        )

        # 初始化数据订阅
        self.feed = RealtimeDataFeed(self.client)

        log.info("System initialized")

    def start(self):
        """启动系统"""
        log.info("=" * 80)
        log.info("Week 1 Hello World - Trading System Starting")
        log.info("=" * 80)

        # 连接IBKR
        log.info("Connecting to IBKR...")
        if not self.client.connect():
            log.error("Failed to connect to IBKR")
            return False

        log.info("Connected to IBKR successfully")

        # 查询初始持仓
        log.info("\nInitial positions:")
        self.position_manager.print_positions()

        # 订阅实时数据
        log.info("\nSubscribing to AAPL 5-second bars...")
        self.feed.subscribe_bars(
            symbol="AAPL",
            bar_size="5 secs",
            callback=self.strategy.on_bar
        )

        log.info("System is running. Press Ctrl+C to stop.")
        log.info("-" * 80)

        self.running = True
        return True

    def stop(self):
        """停止系统"""
        if not self.running:
            return

        log.info("\n" + "=" * 80)
        log.info("Stopping trading system...")
        log.info("=" * 80)

        # 显示最终状态
        log.info("\nFinal orders:")
        orders = self.order_manager.get_all_orders()
        log.info(f"Total orders: {len(orders)}")
        for order in orders:
            log.info(
                f"  #{order.order_id}: {order.action} {order.quantity} "
                f"{order.symbol} @ {order.order_type} - {order.status.value}"
            )

        log.info("\nFinal positions:")
        self.position_manager.print_positions()

        # 清理资源
        if self.feed:
            self.feed.unsubscribe_all()

        if self.client:
            self.client.disconnect()

        self.running = False
        log.info("System stopped")


def main():
    """主函数"""
    system = TradingSystem()

    # 注册信号处理
    def signal_handler(sig, frame):
        log.info("\nReceived stop signal")
        system.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # 初始化
        system.setup()

        # 启动
        if system.start():
            # 保持运行
            signal.pause()

    except Exception as e:
        log.error(f"System error: {e}")
        system.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
