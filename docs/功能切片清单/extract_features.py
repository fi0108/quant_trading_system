#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 MVP 核心模块清单中提取功能点和风险点，写入 CSV 文件
"""

import csv

# 风险点数据
risk_data = [
    ["风险ID", "风险描述", "风险场景", "防护措施", "负责切片", "验证方法", "验证状态", "备注"],
    ["R1", "重复下单", "网络重试导致同一信号下单 2 次", "订单幂等性（唯一 ID + 60 秒内去重）", "切片3", "模拟网络抖动测试", "未验证", ""],
    ["R2", "状态不同步", "本地持仓与 IBKR 账户不一致", "持仓对账（每 5 分钟）+ 差异告警", "切片6", "手动修改 IBKR 持仓测试", "未验证", ""],
    ["R3", "风控失效", "风控检查被绕过或计算错误", "单元测试覆盖所有风控规则", "切片3", "构造超限场景测试", "未验证", ""],
    ["R4", "断线未恢复", "系统以为在运行但实际未连接", "心跳检测（每 30 秒）+ 连接状态监控", "切片7", "断开连接测试（1 分钟内告警）", "未验证", ""],
]

# 切片计划数据
slice_data = [
    ["切片编号", "切片名称", "预计开始", "预计完成", "实际完成", "业务价值", "依赖切片", "覆盖功能点", "状态", "备注"],
    ["切片1", "数据接入验证切片", "Week 1 Day 1", "Week 1 Day 5", "", "能稳定接收行情数据", "无", "F1.1, F1.2, F1.5, F1.6, F5.1, F5.2, NFR1.1, NFR2.1", "📅 Planned", ""],
    ["切片2", "简单策略回测切片", "Week 2 Day 1", "Week 2 Day 5", "", "能跑通简单策略回测", "切片1", "F2.1, F2.2, F2.3, F2.4, F3.1, F3.2, F3.4, F3.5, F3.7", "📅 Planned", ""],
    ["切片3", "风控规则实现切片", "Week 3 Day 1", "Week 3 Day 5", "", "风控能拦截不合规订单", "切片2", "F4.1, F4.2, F4.3, F4.4, F4.5, F4.6, F4.7, F4.8, F1.3, R1, R3", "📅 Planned", ""],
    ["切片4", "回测完善+可视化切片", "Week 3-4 Day 1", "Week 4 Day 5", "", "回测结果可视化", "切片2, 切片3", "F3.5, F3.6, F2.2, F2.3", "📅 Planned", ""],
    ["切片5", "模拟盘下单切片", "Week 4-5 Day 1", "Week 5 Day 5", "", "能在模拟盘下单并跟踪", "切片1, 切片2, 切片3", "F6.1, F6.2, F6.5, F7.1-F7.6, F3.3, NFR2.2", "📅 Planned", ""],
    ["切片6", "持仓管理+对账切片", "Week 5-6 Day 1", "Week 6 Day 5", "", "持仓计算准确，对账有效", "切片5", "F8.1-F8.6, F2.3, F2.5, F1.4, F6.3, F6.4, F6.6, R2", "📅 Planned", ""],
    ["切片7", "监控告警切片", "Week 6-7 Day 1", "Week 7 Day 5", "", "异常能及时发现和告警", "切片1-6", "F9.1-F9.8, F5.2, F5.4, F6.7, NFR1.3, R4", "📅 Planned", ""],
    ["切片8", "完善风控+止损止盈切片", "Week 7-8 Day 1", "Week 8 Day 5", "", "止损止盈自动触发", "切片6, 切片7", "F10.1-F10.6, NFR3.3, NFR4.2, NFR4.3", "📅 Planned", ""],
]

# 写入风险点追踪表
print("Writing risk tracking table...")
with open('风险点追踪表.csv', 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerows(risk_data)
print("Done: 风险点追踪表.csv")

# 写入切片计划表
print("Writing slice plan table...")
with open('切片计划表.csv', 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerows(slice_data)
print("Done: 切片计划表.csv")

print("\nAll files generated successfully!")
print("You can open these CSV files with Excel.")
