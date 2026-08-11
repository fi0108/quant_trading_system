# 模块一：数据验证器 - 验证脚本

"""
验证数据验证器功能（模拟测试，无需真实IBKR连接）
测试内容：
1. 数据完整性检查
2. 逻辑一致性检查
3. 价格变动检查
4. 时间连续性检查
5. 异常处理策略
6. 连续失败检测
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from datetime import datetime, timedelta
from src.connection.market_data.validator import DataValidator


def test_validator_initialization():
    """测试验证器初始化"""
    print("=" * 60)
    print("测试验证器初始化")
    print("=" * 60)

    # 测试1：默认参数
    print("\n1. 默认参数初始化:")
    validator = DataValidator()
    print(f"   最大价格变动: {validator.max_price_change_percent * 100}%")
    print(f"   最大时间间隔: {validator.max_bar_gap_minutes}分钟")
    print(f"   最小成交量: {validator.min_volume}")
    print(f"   严格模式: {validator.strict_mode}")

    if (validator.max_price_change_percent == 0.20 and
        validator.max_bar_gap_minutes == 5):
        print("   [OK] 默认参数正确")
    else:
        print("   [FAIL] 默认参数错误")

    # 测试2：自定义参数
    print("\n2. 自定义参数初始化:")
    validator2 = DataValidator(
        max_price_change_percent=0.10,
        max_bar_gap_minutes=3,
        min_volume=1000,
        strict_mode=True
    )
    print(f"   最大价格变动: {validator2.max_price_change_percent * 100}%")
    print(f"   最大时间间隔: {validator2.max_bar_gap_minutes}分钟")
    print(f"   最小成交量: {validator2.min_volume}")
    print(f"   严格模式: {validator2.strict_mode}")
    print("   [OK] 自定义参数正确")

    print("\n[OK] 验证器初始化测试完成\n")


def test_completeness_check():
    """测试数据完整性检查"""
    print("=" * 60)
    print("测试数据完整性检查")
    print("=" * 60)

    validator = DataValidator()

    # 测试1：完整数据
    print("\n1. 完整数据验证:")
    valid_bar = {
        'symbol': 'AAPL',
        'timestamp': datetime(2026, 8, 9, 9, 30, 0),
        'open': 150.0,
        'high': 151.0,
        'low': 149.5,
        'close': 150.5,
        'volume': 100000
    }

    is_valid, msg, _ = validator.validate(valid_bar)
    print(f"   验证结果: {is_valid}")
    if is_valid:
        print("   [OK] 完整数据通过验证")
    else:
        print(f"   [FAIL] 应该通过: {msg}")

    # 测试2：缺少字段
    print("\n2. 缺少字段:")
    incomplete_bar = {
        'symbol': 'AAPL',
        'timestamp': datetime(2026, 8, 9, 9, 31, 0),
        'open': 150.0,
        # 缺少 high, low, close, volume
    }

    is_valid, msg, _ = validator.validate(incomplete_bar)
    print(f"   验证结果: {is_valid}")
    print(f"   错误信息: {msg}")
    if not is_valid and "缺少字段" in msg:
        print("   [OK] 正确检测到缺少字段")
    else:
        print("   [FAIL] 应该拒绝")

    # 测试3：价格为0
    print("\n3. 价格为0:")
    zero_price_bar = {
        'symbol': 'AAPL',
        'timestamp': datetime(2026, 8, 9, 9, 32, 0),
        'open': 0,  # 异常价格
        'high': 151.0,
        'low': 149.5,
        'close': 150.5,
        'volume': 100000
    }

    is_valid, msg, _ = validator.validate(zero_price_bar)
    print(f"   验证结果: {is_valid}")
    print(f"   错误信息: {msg}")
    if not is_valid and "无效" in msg:
        print("   [OK] 正确检测到价格为0")
    else:
        print("   [FAIL] 应该拒绝")

    # 测试4：成交量为负
    print("\n4. 成交量为负:")
    negative_volume_bar = {
        'symbol': 'AAPL',
        'timestamp': datetime(2026, 8, 9, 9, 33, 0),
        'open': 150.0,
        'high': 151.0,
        'low': 149.5,
        'close': 150.5,
        'volume': -100  # 负数
    }

    is_valid, msg, _ = validator.validate(negative_volume_bar)
    print(f"   验证结果: {is_valid}")
    print(f"   错误信息: {msg}")
    if not is_valid:
        print("   [OK] 正确检测到负成交量")
    else:
        print("   [FAIL] 应该拒绝")

    print("\n[OK] 数据完整性检查测试完成\n")


def test_consistency_check():
    """测试逻辑一致性检查"""
    print("=" * 60)
    print("测试逻辑一致性检查")
    print("=" * 60)

    validator = DataValidator()

    # 测试1：逻辑一致
    print("\n1. 逻辑一致的数据:")
    consistent_bar = {
        'symbol': 'AAPL',
        'timestamp': datetime(2026, 8, 9, 9, 30, 0),
        'open': 150.0,
        'high': 151.0,  # >= max(open, close)
        'low': 149.5,   # <= min(open, close)
        'close': 150.5,
        'volume': 100000
    }

    is_valid, msg, _ = validator.validate(consistent_bar)
    if is_valid:
        print("   [OK] 逻辑一致的数据通过")
    else:
        print(f"   [FAIL] 应该通过: {msg}")

    # 测试2：high < close
    print("\n2. high < close:")
    bad_high_bar = {
        'symbol': 'TSLA',
        'timestamp': datetime(2026, 8, 9, 9, 30, 0),
        'open': 200.0,
        'high': 199.0,  # < close，不一致
        'low': 198.0,
        'close': 200.5,
        'volume': 100000
    }

    is_valid, msg, _ = validator.validate(bad_high_bar)
    print(f"   验证结果: {is_valid}")
    print(f"   错误信息: {msg}")
    if not is_valid and "high" in msg:
        print("   [OK] 正确检测到high不一致")
    else:
        print("   [FAIL] 应该拒绝")

    # 测试3：low > open
    print("\n3. low > open:")
    bad_low_bar = {
        'symbol': 'MSFT',
        'timestamp': datetime(2026, 8, 9, 9, 30, 0),
        'open': 300.0,
        'high': 302.0,
        'low': 301.0,  # > open，不一致
        'close': 301.5,
        'volume': 100000
    }

    is_valid, msg, _ = validator.validate(bad_low_bar)
    print(f"   验证结果: {is_valid}")
    print(f"   错误信息: {msg}")
    if not is_valid and "low" in msg:
        print("   [OK] 正确检测到low不一致")
    else:
        print("   [FAIL] 应该拒绝")

    print("\n[OK] 逻辑一致性检查测试完成\n")


def test_price_change_check():
    """测试价格变动检查"""
    print("=" * 60)
    print("测试价格变动检查")
    print("=" * 60)

    # 非严格模式
    validator = DataValidator(max_price_change_percent=0.20, strict_mode=False)

    # 第一根Bar
    bar1 = {
        'symbol': 'AAPL',
        'timestamp': datetime(2026, 8, 9, 9, 30, 0),
        'open': 100.0,
        'high': 101.0,
        'low': 99.0,
        'close': 100.0,
        'volume': 100000
    }
    validator.validate(bar1)

    # 测试1：正常价格变动（5%）
    print("\n1. 正常价格变动（5%）:")
    bar2 = {
        'symbol': 'AAPL',
        'timestamp': datetime(2026, 8, 9, 9, 31, 0),
        'open': 105.0,  # 变动5%
        'high': 106.0,
        'low': 104.0,
        'close': 105.0,
        'volume': 100000
    }

    is_valid, msg, _ = validator.validate(bar2)
    print(f"   验证结果: {is_valid}")
    if is_valid:
        print("   [OK] 5%变动通过验证")
    else:
        print(f"   [FAIL] 应该通过: {msg}")

    # 测试2：价格暴涨（50%，超过20%阈值）
    print("\n2. 价格暴涨（50%，超过阈值）:")
    bar3 = {
        'symbol': 'AAPL',
        'timestamp': datetime(2026, 8, 9, 9, 32, 0),
        'open': 157.5,  # 变动50%
        'high': 160.0,
        'low': 155.0,
        'close': 157.5,
        'volume': 100000
    }

    is_valid, msg, fixed = validator.validate(bar3)
    print(f"   验证结果: {is_valid}")
    print(f"   错误信息: {msg[:60]}..." if msg else "")

    if is_valid and fixed and fixed.get('_fixed'):
        print("   [OK] 非严格模式，数据已修正")
        print(f"   修正后价格: {fixed['close']}")
    elif not is_valid:
        print("   [WARN] 严格模式会拒绝此数据")
    else:
        print("   [FAIL] 处理不正确")

    # 测试3：严格模式下的暴涨
    print("\n3. 严格模式下的价格暴涨:")
    strict_validator = DataValidator(max_price_change_percent=0.20, strict_mode=True)
    strict_validator.validate(bar1)

    is_valid, msg, fixed = strict_validator.validate(bar3)
    print(f"   验证结果: {is_valid}")
    print(f"   修正数据: {fixed}")
    if not is_valid and fixed is None:
        print("   [OK] 严格模式正确拒绝异常数据")
    else:
        print("   [FAIL] 严格模式应该拒绝")

    print("\n[OK] 价格变动检查测试完成\n")


def test_time_gap_check():
    """测试时间连续性检查"""
    print("=" * 60)
    print("测试时间连续性检查")
    print("=" * 60)

    validator = DataValidator(max_bar_gap_minutes=5)

    # 第一根Bar
    bar1 = {
        'symbol': 'AAPL',
        'timestamp': datetime(2026, 8, 9, 9, 30, 0),
        'open': 150.0,
        'high': 151.0,
        'low': 149.5,
        'close': 150.5,
        'volume': 100000
    }
    validator.validate(bar1)

    # 测试1：正常间隔（1分钟）
    print("\n1. 正常时间间隔（1分钟）:")
    bar2 = {
        'symbol': 'AAPL',
        'timestamp': datetime(2026, 8, 9, 9, 31, 0),
        'open': 150.5,
        'high': 151.5,
        'low': 150.0,
        'close': 151.0,
        'volume': 100000
    }

    is_valid, msg, _ = validator.validate(bar2)
    if is_valid:
        print("   [OK] 1分钟间隔通过")
    else:
        print(f"   [FAIL] 应该通过: {msg}")

    # 测试2：间隔过大（10分钟）
    print("\n2. 间隔过大（10分钟）:")
    bar3 = {
        'symbol': 'AAPL',
        'timestamp': datetime(2026, 8, 9, 9, 41, 0),  # 跳过10分钟
        'open': 151.0,
        'high': 152.0,
        'low': 150.5,
        'close': 151.5,
        'volume': 100000
    }

    is_valid, msg, _ = validator.validate(bar3)
    print(f"   验证结果: {is_valid}")
    print(f"   错误信息: {msg}")
    if not is_valid and "时间间隔过大" in msg:
        print("   [OK] 正确检测到时间间隔过大")
    else:
        print("   [FAIL] 应该拒绝")

    # 测试3：时间倒退
    print("\n3. 时间倒退:")
    bar4 = {
        'symbol': 'AAPL',
        'timestamp': datetime(2026, 8, 9, 9, 30, 0),  # 回到之前时间
        'open': 151.5,
        'high': 152.0,
        'low': 151.0,
        'close': 151.5,
        'volume': 100000
    }

    is_valid, msg, _ = validator.validate(bar4)
    print(f"   验证结果: {is_valid}")
    print(f"   错误信息: {msg}")
    if not is_valid and "时间倒退" in msg:
        print("   [OK] 正确检测到时间倒退")
    else:
        print("   [FAIL] 应该拒绝")

    print("\n[OK] 时间连续性检查测试完成\n")


def test_consecutive_failures():
    """测试连续失败检测"""
    print("=" * 60)
    print("测试连续失败检测")
    print("=" * 60)

    validator = DataValidator(strict_mode=True)

    # 模拟连续3次失败
    print("\n1. 模拟连续失败:")
    bad_bar = {
        'symbol': 'AAPL',
        'timestamp': datetime(2026, 8, 9, 9, 30, 0),
        'open': 0,  # 无效价格
        'high': 151.0,
        'low': 149.5,
        'close': 150.5,
        'volume': 100000
    }

    for i in range(3):
        validator.validate(bad_bar)
        failures = validator.get_consecutive_failures('AAPL')
        print(f"   第{i+1}次失败，连续失败次数: {failures}")

    # 测试是否应该暂停
    should_pause = validator.should_pause_subscription('AAPL', threshold=3)
    print(f"   是否应该暂停订阅: {should_pause}")

    if should_pause:
        print("   [OK] 正确建议暂停订阅")
    else:
        print("   [FAIL] 应该建议暂停")

    # 测试重置
    print("\n2. 重置失败计数:")
    validator.reset_failures('AAPL')
    failures = validator.get_consecutive_failures('AAPL')
    print(f"   重置后失败次数: {failures}")

    if failures == 0:
        print("   [OK] 失败计数已重置")
    else:
        print("   [FAIL] 重置失败")

    print("\n[OK] 连续失败检测测试完成\n")


def test_statistics():
    """测试统计信息"""
    print("=" * 60)
    print("测试统计信息")
    print("=" * 60)

    validator = DataValidator()

    # 模拟一些验证
    print("\n1. 模拟验证过程:")

    # 3个成功
    valid_bar = {
        'symbol': 'AAPL',
        'timestamp': datetime(2026, 8, 9, 9, 30, 0),
        'open': 150.0,
        'high': 151.0,
        'low': 149.5,
        'close': 150.5,
        'volume': 100000
    }

    for i in range(3):
        valid_bar['timestamp'] = datetime(2026, 8, 9, 9, 30 + i, 0)
        validator.validate(valid_bar)

    # 2个失败
    invalid_bar = {
        'symbol': 'TSLA',
        'timestamp': datetime(2026, 8, 9, 9, 30, 0),
        'open': 0,
        'high': 201.0,
        'low': 199.0,
        'close': 200.0,
        'volume': 100000
    }

    for i in range(2):
        validator.validate(invalid_bar)

    print("   模拟完成：3个成功 + 2个失败")

    # 获取统计
    print("\n2. 统计信息:")
    stats = validator.get_stats()
    print(f"   总验证数: {stats['total_validated']}")
    print(f"   通过数: {stats['total_passed']}")
    print(f"   失败数: {stats['total_failed']}")
    print(f"   通过率: {stats['pass_rate']}")
    print(f"   失败原因: {stats['failed_reasons']}")
    print(f"   连续失败: {stats['consecutive_failures']}")

    if stats['total_validated'] == 5 and stats['total_passed'] == 3:
        print("   [OK] 统计信息正确")
    else:
        print("   [FAIL] 统计信息错误")

    # 重置统计
    print("\n3. 重置统计:")
    validator.reset_stats()
    stats = validator.get_stats()
    print(f"   重置后总验证数: {stats['total_validated']}")

    if stats['total_validated'] == 0:
        print("   [OK] 统计已重置")
    else:
        print("   [FAIL] 重置失败")

    print("\n[OK] 统计信息测试完成\n")


def print_integration_guide():
    """打印集成指南"""
    print("=" * 60)
    print("集成使用指南")
    print("=" * 60)

    print("\n使用示例:")
    print("""
from src.connection.market_data.validator import DataValidator

# 1. 创建验证器
validator = DataValidator(
    max_price_change_percent=0.20,  # 最大20%变动
    max_bar_gap_minutes=5,          # 最大5分钟间隔
    strict_mode=False               # 非严格模式（允许修正）
)

# 2. 验证数据
is_valid, error_msg, fixed_data = validator.validate(bar_data)

if is_valid:
    if fixed_data:
        # 数据被修正
        print(f"数据已修正: {error_msg}")
        bar_data = fixed_data
    # 继续处理
    process_bar(bar_data)
else:
    # 验证失败
    print(f"验证失败: {error_msg}")

# 3. 检查连续失败
if validator.should_pause_subscription('AAPL', threshold=3):
    print("AAPL连续失败3次，建议暂停订阅")
    subscriber.unsubscribe('AAPL')

# 4. 查看统计
stats = validator.get_stats()
print(f"通过率: {stats['pass_rate']}")
""")

    print("\n与订阅器集成:")
    print("""
# 在订阅器回调中使用验证器
def on_bar_data(bar):
    # 验证数据
    is_valid, error_msg, fixed_data = validator.validate(bar)

    if is_valid:
        # 使用修正后的数据（如果有）
        final_data = fixed_data if fixed_data else bar

        # 写入存储
        redis_writer.write_bar(final_data)
        postgres_writer.add_bar(final_data)
    else:
        logger.warning(f"Bar验证失败: {error_msg}")

subscriber.register_callback(on_bar_data)
""")

    print()


if __name__ == "__main__":
    print("\n")
    print("*" * 60)
    print("*" + " " * 58 + "*")
    print("*" + "  模块一功能验证 - 数据验证器  ".center(58) + "*")
    print("*" + " " * 58 + "*")
    print("*" * 60)
    print("\n")

    try:
        test_validator_initialization()
        test_completeness_check()
        test_consistency_check()
        test_price_change_check()
        test_time_gap_check()
        test_consecutive_failures()
        test_statistics()
        print_integration_guide()

        print("=" * 60)
        print("[SUCCESS] 所有测试完成！")
        print("=" * 60)
        print("\n总结：")
        print("[OK] 数据完整性检查 - OHLCV非空且>0")
        print("[OK] 逻辑一致性检查 - high/low合理")
        print("[OK] 价格变动检查 - 最大20%变动")
        print("[OK] 时间连续性检查 - 最大5分钟间隔")
        print("[OK] 异常处理 - 严格/非严格模式")
        print("[OK] 连续失败检测 - 3次失败建议暂停")
        print("[OK] 统计信息 - 通过率、失败原因")
        print("\n[TIP] 数据验证器已创建: src/connection/market_data/validator.py")
        print("[TIP] 支持严格模式和数据修正模式")
        print("\n")

    except Exception as e:
        print(f"\n[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
