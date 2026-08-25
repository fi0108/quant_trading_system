"""
测试时区转换和市场时间判断
"""

from datetime import datetime
from datetime import time as dt_time

import pytz


def check_market_time():
    """检查当前市场状态"""

    # 获取美东时区（自动处理夏令时/冬令时）
    eastern = pytz.timezone("US/Eastern")
    shanghai = pytz.timezone("Asia/Shanghai")

    # 获取当前时间
    local_now = datetime.now()
    utc_now = datetime.now(pytz.UTC)
    et_now = utc_now.astimezone(eastern)
    sh_now = utc_now.astimezone(shanghai)

    print("=" * 80)
    print("当前时间检查")
    print("=" * 80)
    print(f"本地时间:     {local_now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"UTC时间:      {utc_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"上海时间:     {sh_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"美东时间:     {et_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"星期:         {et_now.strftime('%A')} (美东)")
    print()

    # 判断是否是周末
    is_weekend = et_now.weekday() >= 5
    print(f"是否周末:     {'是' if is_weekend else '否'}")

    if is_weekend:
        print(f"结论:         周末无交易数据")
        return

    # 检查交易时段
    current_time = et_now.time()

    print()
    print("美股交易时段 (美东时间):")
    print("  盘前: 04:00-09:30")
    print("  盘中: 09:30-16:00")
    print("  盘后: 16:00-20:00")
    print("  休市: 20:00-04:00 (次日)")
    print()

    # 判断当前时段
    if dt_time(4, 0) <= current_time < dt_time(9, 30):
        status = "盘前交易 (Pre-market)"
        has_data = True
    elif dt_time(9, 30) <= current_time < dt_time(16, 0):
        status = "盘中交易 (Regular hours)"
        has_data = True
    elif dt_time(16, 0) <= current_time < dt_time(20, 0):
        status = "盘后交易 (After-hours)"
        has_data = True
    else:
        status = "休市 (Market closed)"
        has_data = False

    print(f"当前状态:     {status}")
    print(f"是否有数据:   {'是' if has_data else '否'}")

    # 时差说明
    print()
    print("=" * 80)
    print("时差说明:")
    print("=" * 80)

    # 检查是否夏令时
    is_dst = bool(et_now.dst())
    if is_dst:
        print("当前美国东部使用: EDT (Eastern Daylight Time, 夏令时)")
        print("上海时间 = 美东时间 + 12小时")
        print()
        print("示例:")
        print("  美东 09:30 (开盘) = 上海 21:30")
        print("  美东 16:00 (收盘) = 上海 04:00 (次日)")
    else:
        print("当前美国东部使用: EST (Eastern Standard Time, 标准时间)")
        print("上海时间 = 美东时间 + 13小时")
        print()
        print("示例:")
        print("  美东 09:30 (开盘) = 上海 22:30")
        print("  美东 16:00 (收盘) = 上海 05:00 (次日)")

    print()
    print("=" * 80)

    if has_data:
        print("✓ 当前可以运行集成测试（有市场数据）")
    else:
        print("✗ 当前不适合运行集成测试（无市场数据）")

    print("=" * 80)


if __name__ == "__main__":
    check_market_time()
