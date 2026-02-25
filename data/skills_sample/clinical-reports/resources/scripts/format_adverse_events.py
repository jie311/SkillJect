#!/usr/bin/env python3
"""
将不良事件数据格式化为临床试验报告的表格。

将 CSV 或结构化数据转换为格式化的 AE 摘要表。

用法：
    python format_adverse_events.py <ae_data.csv>
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def format_ae_summary_table(data: list) -> str:
    """生成 markdown 格式的 AE 摘要表。"""
    # 按治疗组分组
    arm_stats = defaultdict(lambda: {
        'total': 0,
        'any_ae': 0,
        'related_ae': 0,
        'sae': 0,
        'deaths': 0,
        'discontinuations': 0
    })
    
    for row in data:
        arm = row.get('treatment_arm', 'Unknown')
        arm_stats[arm]['total'] += 1
        
        if row.get('any_ae', '').lower() == 'yes':
            arm_stats[arm]['any_ae'] += 1
        if row.get('related', '').lower() == 'yes':
            arm_stats[arm]['related_ae'] += 1
        if row.get('serious', '').lower() == 'yes':
            arm_stats[arm]['sae'] += 1
        if row.get('fatal', '').lower() == 'yes':
            arm_stats[arm]['deaths'] += 1
        if row.get('discontinuation', '').lower() == 'yes':
            arm_stats[arm]['discontinuations'] += 1
    
    # 生成表格
    table = "| 类别 | " + " | ".join(arm_stats.keys()) + " |\n"
    table += "|----------|" + "|".join(["--------"] * len(arm_stats)) + "|\n"
    
    categories = [
        ('总计 N', 'total'),
        ('任何 AE', 'any_ae'),
        ('治疗相关 AE', 'related_ae'),
        ('严重 AE', 'sae'),
        ('死亡', 'deaths'),
        ('因 AE 停药', 'discontinuations')
    ]
    
    for cat_name, cat_key in categories:
        row_data = [cat_name]
        for arm_data in arm_stats.values():
            count = arm_data[cat_key]
            total = arm_data['total']
            pct = (count / total * 100) if total > 0 and cat_key != 'total' else 0
            value = f"{count}" if cat_key == 'total' else f"{count} ({pct:.1f}%)"
            row_data.append(value)
        table += "| " + " | ".join(row_data) + " |\n"
    
    return table


def main():
    """主入口点。"""
    parser = argparse.ArgumentParser(description="将 AE 数据格式化为表格")
    parser.add_argument("input_file", help="AE 数据 CSV 路径")
    parser.add_argument("--output", "-o", help="输出 markdown 文件")
    
    args = parser.parse_args()
    
    try:
        with open(args.input_file, 'r') as f:
            reader = csv.DictReader(f)
            data = list(reader)
        
        table = format_ae_summary_table(data)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(table)
            print(f"✓ 表格已保存至: {args.output}")
        else:
            print("\n不良事件摘要表:\n")
            print(table)
        
        return 0
        
    except Exception as e:
        print(f"错误: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
