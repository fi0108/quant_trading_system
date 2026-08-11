# 模块一：时区管理器和交易日历 - 快速验证脚本

"""
快速验证时区管理器和交易日历管理器功能
无需真实IBKR账号，纯本地测试
"""

import sys
import os
# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from datetime import datetime, date
from src.core.timezone_manager import TimezoneManager
from src.calendar.trading_calendar import TradingCalendar


def test_timezone_manager():
    """测试时区管理器"""
    print("=" * 60)
    print("测试时区管理器")
    print("=" * 60)

    tz = TimezoneManager()

    # 测试1：当前时间三时区显示
    print("\n1. 当前时间（三时区）:")
    now_utc = tz.now_utc()
    now_market = tz.now_market()
    now_local = tz.now_local()
    print(f"   UTC:    {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"   美东:   {now_market.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"   上海:   {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # 测试2：夏令时识别
    print("\n2. 夏令时状态:")
    is_dst = tz.is_dst()
    offset = tz.get_utc_offset()
    print(f"   当前是否夏令时: {is_dst} ({'EDT' if is_dst else 'EST'})")
    print(f"   UTC偏移: {offset}小时")

    # 测试3：交易时段判断
    print("\n3. 交易时段判断:")
    is_trading = tz.is_trading_time()
    print(f"   当前是否交易时段: {is_trading}")

    # 测试4：双时区日志格式
    print("\n4. 双时区日志格式:")
    log_format = tz.format_dual_timezone(now_utc)
    print(f"   {log_format}")

    # 测试5：时区转换验证（夏令时）
    print("\n5. 时区转换验证（夏令时期间）:")
    market_930 = datetime(2026, 6, 15, 9, 30, 0)  # 假设美东时间
    utc_time = tz.market_to_utc(tz.market_tz.localize(market_930))
    print(f"   美东 09:30 → UTC {utc_time.strftime('%H:%M')} (应为13:30)")

    # 测试6：时区转换验证（冬令时）
    print("\n6. 时区转换验证（冬令时期间）:")
    market_930_winter = datetime(2026, 12, 15, 9, 30, 0)
    utc_time_winter = tz.market_to_utc(tz.market_tz.localize(market_930_winter))
    print(f"   美东 09:30 → UTC {utc_time_winter.strftime('%H:%M')} (应为14:30)")

    print("\n✅ 时区管理器测试完成\n")


def test_trading_calendar():
    """测试交易日历管理器"""
    print("=" * 60)
    print("测试交易日历管理器")
    print("=" * 60)

    cal = TradingCalendar(market="NYSE")

    # 测试1：今天是否交易日
    print("\n1. 今天状态:")
    today = date.today()
    is_trading = cal.is_trading_day(today)
    print(f"   日期: {today}")
    print(f"   是否交易日: {is_trading}")
    print(f"   星期: {today.strftime('%A')}")

    # 测试2：感恩节识别（2026年）
    print("\n2. 节假日识别:")
    thanksgiving_2026 = date(2026, 11, 26)
    is_thanksgiving_trading = cal.is_trading_day(thanksgiving_2026)
    print(f"   2026-11-26 (感恩节): {is_thanksgiving_trading} (应为False)")

    # 测试3：周末识别
    print("\n3. 周末识别:")
    saturday = date(2026, 6, 13)  # 周六
    sunday = date(2026, 6, 14)    # 周日
    print(f"   2026-06-13 (周六): {cal.is_trading_day(saturday)} (应为False)")
    print(f"   2026-06-14 (周日): {cal.is_trading_day(sunday)} (应为False)")

    # 测试4：下一交易日（跨周末）
    print("\n4. 下一交易日（跨周末）:")
    friday = date(2026, 6, 12)
    next_day = cal.next_trading_day(friday)
    print(f"   2026-06-12 (周五) 的下一交易日: {next_day} (应为2026-06-15周一)")

    # 测试5：获取最近7个交易日
    print("\n5. 最近7个交易日:")
    end = date.today()
    start = end - __import__('datetime').timedelta(days=14)  # 往前推14天确保能找到7个交易日
    trading_days = cal.get_trading_days(start, end)
    print(f"   从 {start} 到 {end}:")
    print(f"   找到 {len(trading_days)} 个交易日")
    if len(trading_days) > 0:
        print(f"   最近3个: {trading_days[-3:]}")

    # 测试6：半日市检测（感恩节后）
    print("\n6. 半日市检测:")
    day_after_thanksgiving = date(2026, 11, 27)
    is_half = cal.is_half_day(day_after_thanksgiving)
    print(f"   2026-11-27 (感恩节后): 半日市={is_half}")

    # 测试7：2026年节假日列表
    print("\n7. 2026年市场节假日:")
    holidays = cal.get_holidays(2026)
    print(f"   共 {len(holidays)} 个节假日")
    if len(holidays) > 0:
        for h_date, h_name in holidays[:5]:
            print(f"   - {h_date}: {h_name}")
        if len(holidays) > 5:
            print(f"   ... 还有 {len(holidays)-5} 个")

    print("\n✅ 交易日历管理器测试完成\n")


def test_combined():
    """综合测试：时区+日历"""
    print("=" * 60)
    print("综合测试：交易时段判断（时区+日历）")
    print("=" * 60)

    tz = TimezoneManager()
    cal = TradingCalendar()

    now_utc = tz.now_utc()
    now_market = tz.now_market()
    today = now_market.date()

    print(f"\n当前时间: {tz.format_dual_timezone(now_utc)}")
    print(f"当前日期: {today} ({today.strftime('%A')})")

    # 综合判断
    is_trading_day = cal.is_trading_day(today)
    is_trading_time = tz.is_trading_time(now_utc)

    print(f"\n是否交易日: {is_trading_day}")
    print(f"是否交易时段: {is_trading_time}")

    should_connect = is_trading_day and is_trading_time
    print(f"\n💡 结论: {'应该连接IBKR实时订阅' if should_connect else '不应连接，使用离线回填'}")

    if not is_trading_day:
        next_trading = cal.next_trading_day(today)
        print(f"   下一交易日: {next_trading}")

    if is_trading_day and not is_trading_time:
        next_open = tz.next_market_open(now_utc)
        print(f"   下一开盘时间: {tz.format_dual_timezone(next_open)}")

    print("\n✅ 综合测试完成\n")


if __name__ == "__main__":
    print("\n")
    print("*" * 60)
    print("*" + " " * 58 + "*")
    print("*" + "  模块一功能验证 - 时区管理器 & 交易日历管理器  ".center(58) + "*")
    print("*" + " " * 58 + "*")
    print("*" * 60)
    print("\n")

    try:
        test_timezone_manager()
        test_trading_calendar()
        test_combined()

        print("=" * 60)
        print("🎉 所有测试完成！")
        print("=" * 60)
        print("\n建议：")
        print("1. 检查输出结果是否符合预期")
        print("2. 特别注意夏令时/冬令时的时间转换")
        print("3. 验证节假日识别是否准确")
        print("4. 确认交易时段判断逻辑正确")
        print("\n")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
