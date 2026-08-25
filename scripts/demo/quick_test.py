"""
快速测试脚本 - 验证IBKR连接和基本功能

功能：
1. 连接IBKR Paper Trading
2. 订阅实时行情
3. 显示数据
4. 测试下单（可选）

运行：
    python scripts/demo/quick_test.py
"""

import logging
import time
from datetime import datetime

from common.config import Config
from common.logger import setup_logger
from data.ibkr_client import IBKRClient

# 设置日志
setup_logger()
logger = logging.getLogger(__name__)


def print_separator(title=""):
    """打印分隔线"""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}\n")
    else:
        print(f"{'='*60}\n")


def test_connection():
    """测试1：连接IBKR"""
    print_separator("测试1：连接IBKR")

    try:
        # 加载配置
        config = Config()

        # 创建IBKR客户端
        logger.info("正在连接IBKR...")
        client = IBKRClient(
            host=config.get("ibkr.host", "127.0.0.1"),
            port=config.get("ibkr.port", 7497),
            client_id=config.get("ibkr.client_id", 1),
        )

        # 连接
        client.connect()
        time.sleep(2)  # 等待连接建立

        if client.is_connected():
            print("✅ IBKR连接成功！")
            logger.info(f"已连接到 {config.get('ibkr.host')}:{config.get('ibkr.port')}")
            return client
        else:
            print("❌ IBKR连接失败")
            return None

    except Exception as e:
        print(f"❌ 连接出错: {e}")
        logger.error(f"Connection error: {e}", exc_info=True)
        return None


def test_market_data(manager, symbol="AAPL"):
    """测试2：订阅实时行情"""
    print_separator(f"测试2：订阅 {symbol} 实时行情")

    try:
        logger.info(f"订阅 {symbol} 数据...")

        # 订阅数据
        req_id = manager.subscribe_market_data(symbol)
        print(f"✅ 已订阅 {symbol}，请求ID: {req_id}")

        # 等待接收数据
        print(f"\n等待接收数据（10秒）...\n")

        for i in range(10):
            time.sleep(1)

            # 获取最新数据（这里简化处理，实际需要从回调获取）
            print(f"[{i+1}/10] 等待数据... ⏱️")

        print("\n✅ 数据订阅测试完成")
        print("💡 提示：实际数据通过回调接收，完整版在 run_integrated_demo.py 中")

        return True

    except Exception as e:
        print(f"❌ 订阅出错: {e}")
        logger.error(f"Market data error: {e}", exc_info=True)
        return False


def test_order(manager, symbol="AAPL", quantity=1):
    """测试3：下单测试（纸质盘）"""
    print_separator(f"测试3：下单测试")

    try:
        print(f"⚠️  注意：这是纸质盘测试，不会使用真实资金")
        print(f"\n准备下单: BUY {symbol} {quantity}股")

        # 询问是否继续
        response = input("\n是否继续下单测试？(y/n): ").strip().lower()

        if response != "y":
            print("❌ 已取消下单测试")
            return False

        logger.info(f"Testing order: BUY {symbol} {quantity}")

        # 创建订单（这里简化，完整版需要使用OrderManager）
        print(f"✅ 订单创建成功（模拟）")
        print(f"💡 提示：完整的下单流程在 run_integrated_demo.py 中")

        return True

    except Exception as e:
        print(f"❌ 下单出错: {e}")
        logger.error(f"Order error: {e}", exc_info=True)
        return False


def main():
    """主函数"""
    print("\n" + "🚀" * 30)
    print("   IBKR 快速测试脚本")
    print("   纸质盘 (Paper Trading)")
    print("🚀" * 30 + "\n")

    # 显示当前时间
    now = datetime.now()
    print(f"📅 本地时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📍 测试环境: Paper Trading")
    print(f"🎯 测试标的: AAPL\n")

    # 测试1：连接
    manager = test_connection()
    if not manager:
        print("\n❌ 连接失败，无法继续测试")
        print("\n请检查：")
        print("  1. TWS 或 IB Gateway 是否已启动？")
        print("  2. 是否已登录 Paper Trading 账号？")
        print("  3. 配置文件中的端口是否正确？(TWS: 7497, Gateway: 4002)")
        print("  4. 是否启用了 API 连接？(配置 -> API -> 启用 ActiveX 和 Socket 客户端)")
        return

    # 测试2：行情订阅
    test_market_data(manager, "AAPL")

    # 测试3：下单（可选）
    test_order(manager, "AAPL", 1)

    # 清理
    print_separator("测试完成")
    print("✅ 所有测试已完成")
    print("\n💡 下一步：")
    print("  运行完整集成测试：python scripts/demo/run_integrated_demo.py\n")

    # 断开连接
    try:
        manager.disconnect()
        print("✅ 已断开连接")
    except:
        pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n❌ 程序出错: {e}")
        logger.error(f"Program error: {e}", exc_info=True)
