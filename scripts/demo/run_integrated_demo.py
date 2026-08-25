"""
完整集成测试脚本 - 端到端验证整个交易系统

功能：
1. IBKR连接管理
2. 实时行情订阅
3. 技术指标计算（SMA）
4. 交易信号生成
5. 风控检查
6. 订单执行
7. 持仓追踪
8. 监控告警

运行：
    python scripts/demo/run_integrated_demo.py --symbol AAPL --duration 300
"""

import argparse
import logging
import time
from datetime import datetime
from typing import Any, Dict

from common.config import Config
from common.logger import setup_logger
from data.ibkr_client import IBKRClient
from monitor.alert_manager import AlertManager
from monitor.strategy_monitor import StrategyMonitor
from monitor.system_monitor import SystemMonitor
from risk.manager import RiskManager
from risk.models import Order as RiskOrder
from risk.models import Position as RiskPosition
from strategy.indicators.sma import SimpleMovingAverage

# 设置日志
setup_logger()
logger = logging.getLogger(__name__)


class IntegratedDemo:
    """集成测试Demo"""

    def __init__(self, symbol: str = "AAPL", duration: int = 300):
        """
        初始化

        Args:
            symbol: 交易标的
            duration: 运行时长（秒）
        """
        self.symbol = symbol
        self.duration = duration
        self.running = False

        # 加载配置
        self.config = Config()

        # 初始化各模块
        self.ibkr_client = None
        self.alert_manager = None
        self.risk_manager = None
        self.system_monitor = None
        self.strategy_monitor = None

        # 指标
        self.sma_fast = SimpleMovingAverage("SMA_FAST", period=10)
        self.sma_slow = SimpleMovingAverage("SMA_SLOW", period=20)

        # 数据缓存
        self.latest_price = 0
        self.bar_count = 0

        # 交易状态
        self.position = 0  # 当前持仓
        self.trades = []  # 交易记录

    def print_header(self):
        """打印标题"""
        print("\n" + "=" * 80)
        print("   🚀 量化交易系统 - 完整集成测试")
        print("=" * 80)
        print(f"📅 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 测试标的: {self.symbol}")
        print(f"⏱️  运行时长: {self.duration}秒")
        print(f"📍 交易环境: Paper Trading (纸质盘)")
        print("=" * 80 + "\n")

    def initialize_modules(self):
        """初始化所有模块"""
        print("📦 正在初始化模块...\n")

        # 1. 告警管理器
        print("  ✓ 初始化告警管理器...")
        self.alert_manager = AlertManager(dedup_window=300, max_count=10)

        # 2. 风控管理器
        print("  ✓ 初始化风控管理器...")
        self.risk_manager = RiskManager()

        # 3. 系统监控
        print("  ✓ 初始化系统监控...")
        self.system_monitor = SystemMonitor(alert_manager=self.alert_manager)

        # 4. 策略监控
        print("  ✓ 初始化策略监控...")
        self.strategy_monitor = StrategyMonitor(alert_manager=self.alert_manager)

        # 5. IBKR连接
        print("  ✓ 初始化IBKR连接...")
        self.ibkr_client = IBKRClient(
            host=self.config.get("ibkr.host", "127.0.0.1"),
            port=self.config.get("ibkr.port", 7497),
            client_id=self.config.get("ibkr.client_id", 1),
        )

        print("\n✅ 所有模块初始化完成\n")

    def connect_ibkr(self):
        """连接IBKR"""
        print("🔌 正在连接IBKR...\n")

        try:
            self.ibkr_client.connect()
            time.sleep(2)

            if self.ibkr_client.is_connected():
                print("✅ IBKR连接成功\n")
                return True
            else:
                print("❌ IBKR连接失败\n")
                return False
        except Exception as e:
            print(f"❌ 连接出错: {e}\n")
            logger.error(f"Connection error: {e}", exc_info=True)
            return False

    def subscribe_data(self):
        """订阅市场数据"""
        print(f"📡 订阅 {self.symbol} 实时行情...\n")

        try:
            # IBKRClient使用subscribe_realtime_bars方法
            def on_bar(bars, has_new_bar):
                if has_new_bar and len(bars) > 0:
                    bar = bars[-1]
                    self.on_market_data(bar)

            self.ibkr_client.subscribe_realtime_bars(symbol=self.symbol, callback=on_bar)
            print(f"✅ 已订阅 {self.symbol} 实时行情\n")
            return True
        except Exception as e:
            print(f"❌ 订阅失败: {e}\n")
            logger.error(f"Subscribe error: {e}", exc_info=True)
            return False

    def start_monitors(self):
        """启动监控"""
        print("📊 启动监控系统...\n")

        # 启动系统监控
        self.system_monitor.start_monitoring(interval=60)
        print("  ✓ 系统监控已启动")

        # 启动策略监控
        self.strategy_monitor.start_monitoring(check_interval=30)
        print("  ✓ 策略监控已启动\n")

    def process_bar(self, bar_data: Dict[str, Any]):
        """处理行情数据"""
        self.bar_count += 1

        # 更新策略心跳
        self.strategy_monitor.update_heartbeat()

        # 提取数据
        timestamp = bar_data.get("time", datetime.now())
        close_price = bar_data.get("close", 0)

        self.latest_price = close_price

        # 更新指标
        self.sma_fast.Update(timestamp, close_price)
        self.sma_slow.Update(timestamp, close_price)

        # 记录指标更新
        self.strategy_monitor.record_indicator_update("SMA_FAST")
        self.strategy_monitor.record_indicator_update("SMA_SLOW")

        # 显示行情
        print(f"📊 [{datetime.now().strftime('%H:%M:%S')}] " f"{self.symbol}: ${close_price:.2f}")

        # 检查指标是否就绪
        if self.sma_fast.IsReady and self.sma_slow.IsReady:
            sma_fast_value = self.sma_fast.Current.Value
            sma_slow_value = self.sma_slow.Current.Value

            print(f"   📈 SMA10={sma_fast_value:.2f}, SMA20={sma_slow_value:.2f}")

            # 生成交易信号
            self._check_trading_signal(sma_fast_value, sma_slow_value, close_price)
        else:
            print(f"   ⏳ 指标预热中... ({self.sma_fast._samples}/{self.sma_fast.period})")

        print()

    def _check_trading_signal(self, sma_fast: float, sma_slow: float, price: float):
        """检查交易信号"""
        # 简单的均线交叉策略
        if sma_fast > sma_slow and self.position == 0:
            # 买入信号
            print("   🔔 交易信号: BUY (快线上穿慢线)")
            self._execute_trade("BUY", 10, price)

        elif sma_fast < sma_slow and self.position > 0:
            # 卖出信号
            print("   🔔 交易信号: SELL (快线下穿慢线)")
            self._execute_trade("SELL", self.position, price)

    def _execute_trade(self, action: str, quantity: int, price: float):
        """执行交易"""
        # 创建风控订单
        order = RiskOrder(symbol=self.symbol, action=action, quantity=quantity)

        # 构建风控上下文
        context = {
            "portfolio": (
                {self.symbol: RiskPosition(symbol=self.symbol, quantity=self.position, average_price=price)}
                if self.position > 0
                else {}
            ),
            "current_price": {self.symbol: price},
        }

        # 风控检查
        print(f"   🛡️  风控检查...")
        result = self.risk_manager.check_order(order, context)

        if result.passed:
            print(f"   ✅ 风控通过")
            print(f"   📤 下单: {action} {self.symbol} {quantity}股 @ ${price:.2f}")

            # 更新持仓
            if action == "BUY":
                self.position += quantity
            else:
                self.position -= quantity

            # 记录交易
            trade = {
                "time": datetime.now(),
                "action": action,
                "symbol": self.symbol,
                "quantity": quantity,
                "price": price,
            }
            self.trades.append(trade)

            print(f"   💼 当前持仓: {self.position}股\n")
        else:
            print(f"   ❌ 风控拒绝: {result.reason}\n")

    def run(self):
        """运行Demo"""
        self.print_header()

        # 初始化
        self.initialize_modules()

        # 连接IBKR
        if not self.connect_ibkr():
            print("❌ 无法继续，请检查IBKR连接")
            return

        # 订阅数据
        if not self.subscribe_data():
            print("❌ 无法继续，请检查数据订阅")
            return

        # 启动监控
        self.start_monitors()

        # 主循环
        print("=" * 80)
        print("   🎬 开始实时交易测试")
        print("=" * 80 + "\n")

        self.running = True
        start_time = time.time()

        try:
            while self.running and (time.time() - start_time) < self.duration:
                # 模拟接收数据（实际应该从回调获取）
                # 这里每5秒生成一次模拟数据用于演示
                time.sleep(5)

                # 模拟行情数据
                bar_data = {
                    "time": datetime.now(),
                    "close": (
                        self.latest_price + (hash(time.time()) % 100 - 50) / 100 if self.latest_price > 0 else 180.0
                    ),
                }

                self.process_bar(bar_data)

        except KeyboardInterrupt:
            print("\n⚠️  用户中断\n")

        finally:
            self.stop()

    def stop(self):
        """停止并清理"""
        self.running = False

        print("=" * 80)
        print("   🏁 测试结束")
        print("=" * 80 + "\n")

        # 显示统计
        self._print_summary()

        # 停止监控
        if self.system_monitor:
            self.system_monitor.stop_monitoring()
        if self.strategy_monitor:
            self.strategy_monitor.stop_monitoring()

        # 断开连接
        if self.ibkr_client:
            try:
                self.ibkr_client.disconnect()
                print("✅ 已断开IBKR连接\n")
            except:
                pass

    def _print_summary(self):
        """打印摘要"""
        print("📊 运行摘要\n")
        print(f"  接收行情: {self.bar_count} 条")
        print(f"  交易次数: {len(self.trades)} 次")
        print(f"  最终持仓: {self.position} 股")

        if self.trades:
            print(f"\n  交易记录:")
            for trade in self.trades:
                print(
                    f"    {trade['time'].strftime('%H:%M:%S')} "
                    f"{trade['action']} {trade['quantity']}股 @ ${trade['price']:.2f}"
                )

        # 风控统计
        risk_stats = self.risk_manager.get_stats()
        print(f"\n  风控统计:")
        print(f"    总检查: {risk_stats['summary']['total_checks']}")
        print(f"    通过: {risk_stats['summary']['total_passed']}")
        print(f"    拒绝: {risk_stats['summary']['total_failed']}")

        # 告警统计
        alert_stats = self.alert_manager.get_stats()
        print(f"\n  告警统计:")
        print(f"    发送: {alert_stats['alert_stats']['total_sent']}")
        print(f"    去重: {alert_stats['alert_stats']['total_deduplicated']}")

        print()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="量化交易系统 - 完整集成测试")
    parser.add_argument("--symbol", default="AAPL", help="交易标的 (默认: AAPL)")
    parser.add_argument("--duration", type=int, default=300, help="运行时长(秒) (默认: 300)")

    args = parser.parse_args()

    # 创建并运行Demo
    demo = IntegratedDemo(symbol=args.symbol, duration=args.duration)
    demo.run()


if __name__ == "__main__":
    main()
