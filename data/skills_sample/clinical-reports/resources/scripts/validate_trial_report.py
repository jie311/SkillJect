#!/usr/bin/env python3
"""
根据 ICH-E3 结构验证临床试验报告。

检查临床研究报告 (CSR) 是否符合 ICH-E3。

用法：
    python validate_trial_report.py <csr_file.md>
"""

import argparse
import json
import re
from pathlib import Path


ICH_E3_SECTIONS = {
    "title_page": "标题页",
    "synopsis": "摘要 (2)",
    "toc": "目录 (3)",
    "abbreviations": "缩写列表 (4)",
    "ethics": "伦理 (第 2 节)",
    "investigators": "研究者和研究管理结构 (第 3 节)",
    "introduction": "引言 (第 4 节)",
    "objectives": "研究目标和计划 (第 5 节)",
    "study_patients": "研究患者 (第 6 节)",
    "efficacy": "疗效评价 (第 7 节)",
    "safety": "安全性评价 (第 8 节)",
    "discussion": "讨论和总体结论 (第 9 节)",
    "tables_figures": "表格、图形和图表 (第 10 节)",
    "references": "参考文献 (第 11 节)",
    "appendices": "附录 (第 12-14 节)",
}


def validate_ich_e3(filename: str) -> dict:
    """根据 ICH-E3 验证 CSR 结构。"""
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    results = {}
    for section_id, section_name in ICH_E3_SECTIONS.items():
        # 节标题的简单模式匹配
        pattern = rf"(?i)##?\s*{re.escape(section_name.split('(')[0].strip())}"
        found = bool(re.search(pattern, content))
        results[section_id] = {"name": section_name, "found": found}
    
    compliance_rate = sum(1 for r in results.values() if r["found"]) / len(results) * 100
    
    return {
        "filename": filename,
        "compliance_rate": round(compliance_rate, 1),
        "sections": results,
        "status": "PASS" if compliance_rate >= 90 else "NEEDS_REVISION"
    }


def main():
    """主入口点。"""
    parser = argparse.ArgumentParser(description="根据 ICH-E3 验证 CSR")
    parser.add_argument("input_file", help="CSR 文件路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    
    args = parser.parse_args()
    
    try:
        report = validate_ich_e3(args.input_file)
        
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"\nICH-E3 合规性: {report['compliance_rate']}%")
            print(f"状态: {report['status']}\n")
            print("章节检查清单:")
            for section, details in report["sections"].items():
                symbol = "✓" if details["found"] else "✗"
                print(f"{symbol} {details['name']}")
        
        return 0 if report["status"] == "PASS" else 1
        
    except Exception as e:
        print(f"错误: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
