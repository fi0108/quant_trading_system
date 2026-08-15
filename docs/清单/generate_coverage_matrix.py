#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成功能覆盖矩阵 - 基于 MVP 开发准备工作流程
"""

import csv

# 读取已生成的功能点清单
features = []
with open('功能点清单.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    features = list(reader)

# 功能覆盖矩阵数据结构
# 格式：功能点ID, 切片1, 切片2, 切片3, 切片4, 切片5, 切片6, 切片7, 切片8, 最终覆盖
matrix_data = [
    ["功能点ID", "切片1", "切片2", "切片3", "切片4", "切片5", "切片6", "切片7", "切片8", "最终覆盖"]
]

# 定义每个切片覆盖的功能点
slice_coverage = {
    # 切片1：数据接入验证切片
    "切片1": {
        "F1.1": "✅ 100%",
        "F1.2": "⚠️ 60%",
        "F1.5": "✅ 100%",
        "F1.6": "⚠️ 80%",
        "F5.1": "⚠️ 60%",
        "F5.2": "⚠️ 60%",
        "NFR1.1": "✅ 100%",
        "NFR2.1": "✅ 100%",
        "NFR3.1": "✅ 100%",
    },

    # 切片2：简单策略回测切片
    "切片2": {
        "F2.1": "✅ 100%",
        "F2.2": "⚠️ 80%",
        "F2.3": "⚠️ 60%",
        "F2.4": "✅ 100%",
        "F3.1": "✅ 100%",
        "F3.2": "✅ 100%",
        "F3.4": "✅ 100%",
        "F3.5": "⚠️ 60%",
        "F3.7": "✅ 100%",
        "F5.3": "⚠️ 80%",
        "NFR3.2": "✅ 100%",
    },

    # 切片3：风控规则实现切片
    "切片3": {
        "F1.3": "✅ 100%",
        "F4.1": "✅ 100%",
        "F4.2": "✅ 100%",
        "F4.3": "✅ 100%",
        "F4.4": "✅ 100%",
        "F4.5": "⚠️ 80%",
        "F4.6": "✅ 100%",
        "F4.7": "✅ 100%",
        "F4.8": "✅ 100%",
        "NFR2.4": "✅ 100%",
        "NFR4.1": "✅ 100%",
        "NFR5.1": "✅ 100%",
    },

    # 切片4：回测完善+可视化切片
    "切片4": {
        "F2.2": "✅ 100%",
        "F2.3": "⚠️ 80%",
        "F3.5": "✅ 100%",
        "F3.6": "✅ 100%",
    },

    # 切片5：模拟盘下单切片
    "切片5": {
        "F3.3": "✅ 100%",
        "F4.5": "✅ 100%",
        "F6.1": "✅ 100%",
        "F6.2": "✅ 100%",
        "F6.5": "✅ 100%",
        "F7.1": "✅ 100%",
        "F7.2": "✅ 100%",
        "F7.3": "✅ 100%",
        "F7.4": "✅ 100%",
        "F7.5": "✅ 100%",
        "F7.6": "✅ 100%",
        "NFR1.2": "✅ 100%",
        "NFR2.2": "✅ 100%",
    },

    # 切片6：持仓管理+对账切片
    "切片6": {
        "F1.4": "✅ 100%",
        "F1.6": "✅ 100%",
        "F2.3": "✅ 100%",
        "F2.5": "✅ 100%",
        "F6.3": "✅ 100%",
        "F6.4": "✅ 100%",
        "F6.6": "✅ 100%",
        "F8.1": "✅ 100%",
        "F8.2": "✅ 100%",
        "F8.3": "✅ 100%",
        "F8.4": "✅ 100%",
        "F8.5": "✅ 100%",
        "F8.6": "✅ 100%",
        "NFR2.3": "✅ 100%",
    },

    # 切片7：监控告警切片
    "切片7": {
        "F5.2": "✅ 100%",
        "F5.4": "✅ 100%",
        "F6.7": "✅ 100%",
        "F9.1": "✅ 100%",
        "F9.2": "✅ 100%",
        "F9.3": "✅ 100%",
        "F9.4": "✅ 100%",
        "F9.5": "✅ 100%",
        "F9.6": "✅ 100%",
        "F9.7": "✅ 100%",
        "F9.8": "✅ 100%",
        "NFR1.3": "✅ 100%",
        "NFR5.2": "✅ 100%",
    },

    # 切片8：完善风控+止损止盈切片
    "切片8": {
        "F10.1": "✅ 100%",
        "F10.2": "✅ 100%",
        "F10.3": "✅ 100%",
        "F10.4": "✅ 100%",
        "F10.5": "✅ 100%",
        "F10.6": "✅ 100%",
        "NFR3.3": "✅ 100%",
        "NFR4.2": "✅ 100%",
        "NFR4.3": "✅ 100%",
    },
}

# 计算最终覆盖
def calculate_final_coverage(feature_id, slices_coverage):
    """计算功能点的最终覆盖情况"""
    max_coverage = 0
    has_coverage = False

    for slice_name in ["切片1", "切片2", "切片3", "切片4", "切片5", "切片6", "切片7", "切片8"]:
        if feature_id in slices_coverage.get(slice_name, {}):
            has_coverage = True
            coverage_str = slices_coverage[slice_name][feature_id]
            if "100%" in coverage_str:
                max_coverage = 100
            elif "80%" in coverage_str and max_coverage < 80:
                max_coverage = 80
            elif "60%" in coverage_str and max_coverage < 60:
                max_coverage = 60

    if not has_coverage:
        return "-"
    elif max_coverage == 100:
        return "✅ 100%"
    elif max_coverage >= 60:
        return f"⚠️ {max_coverage}%"
    else:
        return "-"

# 生成矩阵
for feature_row in features[1:]:  # 跳过表头
    feature_id = feature_row[0]

    row = [feature_id]

    # 遍历 8 个切片
    for slice_num in range(1, 9):
        slice_name = f"切片{slice_num}"
        coverage = slice_coverage.get(slice_name, {}).get(feature_id, "-")
        row.append(coverage)

    # 计算最终覆盖
    final_coverage = calculate_final_coverage(feature_id, slice_coverage)
    row.append(final_coverage)

    matrix_data.append(row)

# 写入功能覆盖矩阵
print("Writing feature coverage matrix...")
with open('功能覆盖矩阵.csv', 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerows(matrix_data)
print("Done: 功能覆盖矩阵.csv")

# 统计和检查
print("\n=== Coverage Statistics ===")
total_features = len(matrix_data) - 1
fully_covered = sum(1 for row in matrix_data[1:] if "✅ 100%" in row[-1])
partially_covered = sum(1 for row in matrix_data[1:] if "⚠️" in row[-1])
not_covered = sum(1 for row in matrix_data[1:] if row[-1] == "-")

print(f"Total features: {total_features}")
print(f"Fully covered (100%): {fully_covered}")
print(f"Partially covered (60-90%): {partially_covered}")
print(f"Not covered: {not_covered}")

if not_covered > 0:
    print("\nWARNING: Some features are not covered by any slice!")
    print("Not covered features:")
    for row in matrix_data[1:]:
        if row[-1] == "-":
            print(f"  - {row[0]}")
else:
    print("\nSUCCESS: All features are covered!")

# 按切片统计
print("\n=== Coverage by Slice ===")
for slice_num in range(1, 9):
    slice_name = f"切片{slice_num}"
    count = len(slice_coverage.get(slice_name, {}))
    print(f"{slice_name}: {count} features")
