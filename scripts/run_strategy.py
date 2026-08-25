"""
策略运行器

用于启动和运行交易策略的命令行工具。

使用示例：
    python scripts/run_strategy.py --strategy sma_crossover_live --config config/strategy_config.yaml
    python scripts/run_strategy.py --strategy sma_crossover_live --symbol AAPL --fast 10 --slow 20
"""

import argparse
import signal
import sys
import time
from pathlib import Path
from typing import Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import yaml

from common.config import Config
from common.logger import Logger
from database.connection import create_tables, init_database
from strategies.sma_crossover_live import SMAStrategyLive
from trading.connection.manager import ConnectionManager


class StrategyRunner:
    """策略运行器"""

    def __init__(self):
        self.strategy: Optional[SMAStrategyLive] = None
        self.connection_manager: Optional[IBKRConnectionManager] = None
        self.running = True
        self.logger = None

    def load_config(self, config_path: str) -> dict:
        """加载配置文件"""
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config

    def setup_database(self):
        """初始化数据库连接"""
        print("Initializing database connection...")
        init_database()
        create_tables()
        print("✓ Database initialized")

    def setup_logger(self, log_config: dict):
        """设置日志"""
        self.logger = Logger.get_logger(
            name="StrategyRunner",
            log_file=log_config.get("file", "logs/strategy.log"),
            level=log_config.get("level", "INFO"),
        )
        print(f"✓ Logger initialized: {log_config.get('file')}")

    def setup_ibkr_connection(self, ibkr_config: dict):
        """建立IBKR连接"""
        print("Connecting to IBKR...")
        self.connection_manager = IBKRConnectionManager(
            host=ibkr_config.get("host", "127.0.0.1"),
            port=ibkr_config.get("port", 7497),
            client_id=ibkr_config.get("client_id", 1),
        )
        self.connection_manager.connect()
        time.sleep(2)  # 等待连接建立

        if self.connection_manager.is_connected():
            print("✓ Connected to IBKR")
        else:
            raise ConnectionError("Failed to connect to IBKR")

    def create_strategy(self, strategy_name: str, config: dict) -> SMAStrategyLive:
        """创建策略实例"""
        print(f"Creating strategy: {strategy_name}")

        if strategy_name != "sma_crossover_live":
            raise ValueError(f"Unknown strategy: {strategy_name}")

        # 创建策略实例
        strategy = SMAStrategyLive()

        # 设置参数
        strategy_config = config["strategy"]
        strategy.symbol = strategy_config["trading"]["symbol"]
        strategy.fast_period = strategy_config["sma"]["fast_period"]
        strategy.slow_period = strategy_config["sma"]["slow_period"]
        strategy.trade_quantity = strategy_config["trading"]["default_quantity"]
        strategy.max_order_value = strategy_config["risk"]["max_order_value"]

        # 设置连接管理器
        strategy.set_connection_manager(self.connection_manager)

        print("✓ Strategy created")
        return strategy

    def run_strategy(self, strategy: SMAStrategyLive):
        """运行策略"""
        print("=" * 60)
        print("Starting strategy execution...")
        print("=" * 60)

        # 初始化策略
        strategy.Initialize()

        # 订阅市场数据
        print(f"\nSubscribing to market data: {strategy.symbol}")
        strategy.subscribe_market_data(strategy.symbol)

        # 运行循环
        print("\n✓ Strategy is running. Press Ctrl+C to stop.\n")

        try:
            while self.running:
                # 处理数据（由连接管理器的回调触发）
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n\nReceived interrupt signal, stopping strategy...")
        finally:
            self.cleanup()

    def cleanup(self):
        """清理资源"""
        print("\nCleaning up...")

        if self.connection_manager and self.connection_manager.is_connected():
            self.connection_manager.disconnect()
            print("✓ Disconnected from IBKR")

        print("✓ Strategy stopped")

    def handle_signal(self, signum, frame):
        """处理系统信号"""
        print(f"\nReceived signal {signum}")
        self.running = False


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Run trading strategy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 使用配置文件运行
  python scripts/run_strategy.py --strategy sma_crossover_live --config config/strategy_config.yaml

  # 覆盖配置文件中的参数
  python scripts/run_strategy.py --strategy sma_crossover_live --config config/strategy_config.yaml --symbol TSLA

  # 使用命令行参数（不需要配置文件）
  python scripts/run_strategy.py --strategy sma_crossover_live --symbol AAPL --fast 10 --slow 20 --quantity 100
        """,
    )

    parser.add_argument("--strategy", type=str, required=True, choices=["sma_crossover_live"], help="Strategy name")

    parser.add_argument(
        "--config",
        type=str,
        default="config/strategy_config.yaml",
        help="Path to config file (default: config/strategy_config.yaml)",
    )

    # 可选的覆盖参数
    parser.add_argument("--symbol", type=str, help="Trading symbol (overrides config)")
    parser.add_argument("--fast", type=int, help="Fast SMA period (overrides config)")
    parser.add_argument("--slow", type=int, help="Slow SMA period (overrides config)")
    parser.add_argument("--quantity", type=int, help="Trade quantity (overrides config)")

    return parser.parse_args()


def main():
    """主函数"""
    # 解析参数
    args = parse_arguments()

    print("=" * 60)
    print("Strategy Runner")
    print("=" * 60)

    # 创建运行器
    runner = StrategyRunner()

    # 注册信号处理
    signal.signal(signal.SIGINT, runner.handle_signal)
    signal.signal(signal.SIGTERM, runner.handle_signal)

    try:
        # 1. 加载配置
        print(f"\nLoading config from: {args.config}")
        config = runner.load_config(args.config)

        # 命令行参数覆盖配置文件
        if args.symbol:
            config["strategy"]["trading"]["symbol"] = args.symbol
        if args.fast:
            config["strategy"]["sma"]["fast_period"] = args.fast
        if args.slow:
            config["strategy"]["sma"]["slow_period"] = args.slow
        if args.quantity:
            config["strategy"]["trading"]["default_quantity"] = args.quantity

        print("✓ Config loaded")

        # 2. 初始化数据库
        runner.setup_database()

        # 3. 设置日志
        runner.setup_logger(config.get("logging", {}))

        # 4. 连接IBKR
        runner.setup_ibkr_connection(config["ibkr"])

        # 5. 创建策略
        strategy = runner.create_strategy(args.strategy, config)

        # 6. 运行策略
        runner.run_strategy(strategy)

    except FileNotFoundError as e:
        print(f"\n✗ Error: Config file not found: {e}")
        sys.exit(1)
    except ConnectionError as e:
        print(f"\n✗ Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Make sure TWS or IB Gateway is running")
        print("  2. Check if the port is correct (7497 for paper, 7496 for live)")
        print("  3. Enable API connections in TWS/Gateway settings")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
