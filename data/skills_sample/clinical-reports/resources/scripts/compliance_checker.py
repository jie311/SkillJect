#!/usr/bin/env python3
"""
检查临床报告的法规合规性（HIPAA、GCP、FDA）。

用法：
    python compliance_checker.py <report_file>
"""

import argparse
import json
import re


COMPLIANCE_CHECKS = {
    "hipaa": {
        "consent_statement": r"(?i)(知情\s+同意|书面\s+同意).*已获得",
        "deidentification": r"(?i)(去标识|匿名)",
    },
    "gcp": {
        "irb_approval": r"(?i)(IRB|IEC|伦理\s+委员会).*批准",
        "protocol_compliance": r"(?i)方案",
        "informed_consent": r"(?i)知情\s+同意",
    },
    "fda": {
        "study_id": r"(?i)(IND|IDE|方案)\s+(编号|#)[:]\s*\S+",
        "safety_reporting": r"(?i)(不良\s+事件|SAE)",
    }
}


def check_compliance(filename: str) -> dict:
    """检查法规合规性。"""
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    results = {}
    for regulation, checks in COMPLIANCE_CHECKS.items():
        reg_results = {}
        for check_name, pattern in checks.items():
            reg_results[check_name] = bool(re.search(pattern, content))
        results[regulation] = reg_results
    
    return {"filename": filename, "compliance": results}


def main():
    """主入口点。"""
    parser = argparse.ArgumentParser(description="检查法规合规性")
    parser.add_argument("input_file", help="临床报告路径")
    parser.add_argument("--json", action="store_true")
    
    args = parser.parse_args()
    
    try:
        report = check_compliance(args.input_file)
        
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print("\n法规合规性检查:\n")
            for reg, checks in report["compliance"].items():
                print(f"{reg.upper()}:")
                for check, passed in checks.items():
                    symbol = "✓" if passed else "✗"
                    print(f"  {symbol} {check}")
                print()
        
        return 0
        
    except Exception as e:
        print(f"错误: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
