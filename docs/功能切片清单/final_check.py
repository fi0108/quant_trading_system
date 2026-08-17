#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
步骤 5：最终检查 - 生成检查报告
"""

import csv
from datetime import datetime

print("="*60)
print("MVP 功能点追踪 - 最终检查报告")
print("="*60)
print(f"检查日期：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"检查人：系统自动检查")
print()

# ===== 1. 读取数据 =====
print("正在读取数据文件...")

# 读取功能点清单
features = []
with open('功能点清单.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    features = list(reader)

# 读取切片计划
slices = []
with open('切片计划表.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    slices = list(reader)

# 读取风险点
risks = []
with open('风险点追踪表.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    risks = list(reader)

# 读取覆盖矩阵
matrix = []
with open('功能覆盖矩阵.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    matrix = list(reader)

print("Done!\n")

# ===== 2. 统计数据 =====
print("="*60)
print("统计数据")
print("="*60)

total_features = len(features) - 1
functional_features = sum(1 for row in features[1:] if row[0].startswith('F'))
non_functional = sum(1 for row in features[1:] if row[0].startswith('NFR'))
total_slices = len(slices) - 1
total_risks = len(risks) - 1

print(f"功能点总数：{total_features} 个")
print(f"  - 功能性需求 (F)：{functional_features} 个")
print(f"  - 非功能性需求 (NFR)：{non_functional} 个")
print(f"切片数量：{total_slices} 个")
print(f"风险点数量：{total_risks} 个")
print()

# ===== 3. 完整性检查 =====
print("="*60)
print("完整性检查")
print("="*60)

issues = []

# 检查项 1：功能点是否都有负责切片
print("\n[检查 1] 功能点是否都有负责切片...")
features_without_slice = []
for row in features[1:]:
    feature_id = row[0]
    responsible_slice = row[4]  # 负责切片列
    if not responsible_slice or responsible_slice.strip() == "":
        features_without_slice.append(feature_id)

if features_without_slice:
    print(f"  FAIL: {len(features_without_slice)} 个功能点没有负责切片")
    for fid in features_without_slice:
        print(f"    - {fid}")
    issues.append(f"有 {len(features_without_slice)} 个功能点没有负责切片")
else:
    print("  PASS: 所有功能点都有负责切片")

# 检查项 2：功能点是否都有完成度目标
print("\n[检查 2] 功能点是否都有完成度目标...")
features_without_target = []
for row in features[1:]:
    feature_id = row[0]
    target = row[5]  # 完成度目标列
    if not target or target.strip() == "":
        features_without_target.append(feature_id)

if features_without_target:
    print(f"  FAIL: {len(features_without_target)} 个功能点没有完成度目标")
    issues.append(f"有 {len(features_without_target)} 个功能点没有完成度目标")
else:
    print("  PASS: 所有功能点都有完成度目标")

# 检查项 3：覆盖矩阵最终覆盖列是否都是 100%
print("\n[检查 3] 覆盖矩阵最终覆盖是否都达到 100%...")
not_fully_covered = []
for row in matrix[1:]:
    feature_id = row[0]
    final_coverage = row[-1]  # 最终覆盖列
    if "100%" not in final_coverage:
        not_fully_covered.append((feature_id, final_coverage))

if not_fully_covered:
    print(f"  WARNING: {len(not_fully_covered)} 个功能点未达到 100% 覆盖")
    for fid, coverage in not_fully_covered:
        print(f"    - {fid}: {coverage}")
    issues.append(f"有 {len(not_fully_covered)} 个功能点未达到 100% 覆盖")
else:
    print("  PASS: 所有功能点最终覆盖都达到 100%")

# 检查项 4：风险点是否都有负责切片
print("\n[检查 4] 风险点是否都有负责切片...")
risks_without_slice = []
for row in risks[1:]:
    risk_id = row[0]
    responsible_slice = row[4]  # 负责切片列
    if not responsible_slice or responsible_slice.strip() == "":
        risks_without_slice.append(risk_id)

if risks_without_slice:
    print(f"  FAIL: {len(risks_without_slice)} 个风险点没有负责切片")
    issues.append(f"有 {len(risks_without_slice)} 个风险点没有负责切片")
else:
    print("  PASS: 所有风险点都有负责切片")

# 检查项 5：切片依赖关系是否合理（无循环依赖）
print("\n[检查 5] 切片依赖关系检查...")
# 简单检查：后面的切片不应该依赖更后面的切片
dependency_issues = []
for i, row in enumerate(slices[1:], 1):
    slice_id = row[0]
    dependencies = row[6]  # 依赖切片列
    if dependencies and dependencies != "无":
        # 提取依赖的切片编号
        dep_numbers = [int(d.replace("切片", "").strip()) for d in dependencies.split(",") if "切片" in d]
        for dep_num in dep_numbers:
            if dep_num >= i:
                dependency_issues.append(f"{slice_id} 依赖 切片{dep_num}（循环或后向依赖）")

if dependency_issues:
    print(f"  WARNING: 发现 {len(dependency_issues)} 个依赖问题")
    for issue in dependency_issues:
        print(f"    - {issue}")
    issues.append(f"发现 {len(dependency_issues)} 个切片依赖问题")
else:
    print("  PASS: 切片依赖关系合理")

print()

# ===== 4. 合理性检查 =====
print("="*60)
print("合理性检查")
print("="*60)

# 检查项 6：切片工作量平衡
print("\n[检查 6] 切片工作量平衡检查...")
slice_workload = {}
for i in range(1, 9):
    slice_name = f"切片{i}"
    count = sum(1 for row in matrix[1:] if row[i] != "-")
    slice_workload[slice_name] = count
    status = "OK" if 3 <= count <= 15 else "WARNING"
    print(f"  {slice_name}: {count} 个功能点 [{status}]")

unbalanced = [s for s, c in slice_workload.items() if c < 3 or c > 15]
if unbalanced:
    print(f"\n  建议：{len(unbalanced)} 个切片工作量不平衡，考虑调整")
    issues.append(f"{len(unbalanced)} 个切片工作量不平衡")

# 检查项 7：依赖链长度
print("\n[检查 7] 依赖链长度检查...")
max_depth = 0
for row in slices[1:]:
    dependencies = row[6]
    if dependencies and dependencies != "无":
        depth = len([d for d in dependencies.split(",") if "切片" in d])
        max_depth = max(max_depth, depth)

print(f"  最长依赖链：{max_depth} 层")
if max_depth > 3:
    print(f"  WARNING: 依赖链较长，可能影响并行开发")
    issues.append(f"依赖链过长（{max_depth} 层）")
else:
    print(f"  OK: 依赖链长度合理")

print()

# ===== 5. 发现的问题汇总 =====
print("="*60)
print("发现的问题汇总")
print("="*60)

if issues:
    print(f"\n共发现 {len(issues)} 个问题：\n")
    for i, issue in enumerate(issues, 1):
        print(f"{i}. {issue}")
    print("\n建议：修复这些问题后再开始开发")
    conclusion = "WARNING: 需要调整"
else:
    print("\nPASS: 未发现问题")
    conclusion = "SUCCESS: 准备工作完成，可以开始开发"

print()

# ===== 6. 结论 =====
print("="*60)
print("结论")
print("="*60)
print(f"\n{conclusion}\n")

# 保存报告
print("="*60)
report_lines = [
    "# MVP 功能点追踪 - 最终检查报告\n",
    f"\n**检查日期**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    "\n**检查人**：系统自动检查\n",
    "\n## 统计数据\n",
    f"- 功能点总数：{total_features} 个",
    f"  - 功能性需求 (F)：{functional_features} 个",
    f"  - 非功能性需求 (NFR)：{non_functional} 个",
    f"- 切片数量：{total_slices} 个",
    f"- 风险点数量：{total_risks} 个\n",
    "\n## 完整性检查\n",
]

if features_without_slice:
    report_lines.append(f"\n### FAIL: 有 {len(features_without_slice)} 个功能点没有负责切片\n")
    for fid in features_without_slice:
        report_lines.append(f"- {fid}\n")
else:
    report_lines.append("\n### PASS: 所有功能点都有负责切片\n")

if not_fully_covered:
    report_lines.append(f"\n### WARNING: 有 {len(not_fully_covered)} 个功能点未达到 100% 覆盖\n")
    for fid, coverage in not_fully_covered:
        report_lines.append(f"- {fid}: {coverage}\n")
else:
    report_lines.append("\n### PASS: 所有功能点最终覆盖都达到 100%\n")

report_lines.append("\n## 切片工作量分布\n")
for slice_name, count in slice_workload.items():
    report_lines.append(f"- {slice_name}: {count} 个功能点\n")

report_lines.append(f"\n## 发现的问题\n")
if issues:
    for i, issue in enumerate(issues, 1):
        report_lines.append(f"{i}. {issue}\n")
else:
    report_lines.append("\n无问题发现\n")

report_lines.append(f"\n## 结论\n\n{conclusion}\n")

with open('最终检查报告.md', 'w', encoding='utf-8') as f:
    f.writelines(report_lines)

print("Done: 最终检查报告.md")
print("="*60)
