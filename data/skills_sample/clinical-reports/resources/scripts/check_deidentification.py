#!/usr/bin/env python3
"""
检查临床报告中需要移除的HIPAA标识符。

扫描文本中的18种HIPAA标识符并标记潜在的隐私违规。

使用方法:
    python check_deidentification.py <input_file>
    python check_deidentification.py <input_file> --output violations.json
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List


# 18种HIPAA标识符模式
HIPAA_IDENTIFIERS = {
    "1_names": {
        "description": "姓名（患者、家属、提供者）",
        "patterns": [
            r"\b(Dr\.|Mr\.|Mrs\.|Ms\.)\s+[A-Z][a-z]+",
            r"\b[A-Z][a-z]+,\s+[A-Z][a-z]+\b",  # 姓, 名
        ],
        "severity": "HIGH"
    },
    "2_geographic": {
        "description": "小于州的地理细分区域",
        "patterns": [
            r"\b\d+\s+[A-Z][a-z]+\s+(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b",
            r"\b[A-Z][a-z]+,\s+[A-Z]{2}\s+\d{5}\b",  # 市, 州 邮编
        ],
        "severity": "HIGH"
    },
    "3_dates": {
        "description": "日期（年份除外）",
        "patterns": [
            r"\b(0?[1-9]|1[0-2])/(0?[1-9]|[12][0-9]|3[01])/\d{4}\b",
            r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}\b",
            r"\b\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b",
        ],
        "severity": "HIGH"
    },
    "4_telephone": {
        "description": "电话号码",
        "patterns": [
            r"\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
            r"\b1-\d{3}-\d{3}-\d{4}\b",
        ],
        "severity": "HIGH"
    },
    "5_fax": {
        "description": "传真号码",
        "patterns": [
            r"(?i)传真[:]\s*\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
            r"(?i)fax[:]\s*\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
        ],
        "severity": "HIGH"
    },
    "6_email": {
        "description": "电子邮件地址",
        "patterns": [
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        ],
        "severity": "HIGH"
    },
    "7_ssn": {
        "description": "社会保障号",
        "patterns": [
            r"\b\d{3}-\d{2}-\d{4}\b",
            r"\b\d{9}\b",
        ],
        "severity": "CRITICAL"
    },
    "8_mrn": {
        "description": "病历号",
        "patterns": [
            r"(?i)(病历号|MRN|medical\s+record\s+(number|#))[:]\s*\d+",
            r"(?i)患者ID[:]\s*\d+",
        ],
        "severity": "HIGH"
    },
    "9_health_plan": {
        "description": "健康计划受益人号码",
        "patterns": [
            r"(?i)(保险|保单)\s+(号码|#|id)[:]\s*[A-Z0-9]+",
        ],
        "severity": "HIGH"
    },
    "10_account": {
        "description": "账号号码",
        "patterns": [
            r"(?i)账号\s+(号码|#)[:]\s*\d+",
        ],
        "severity": "MEDIUM"
    },
    "11_license": {
        "description": "证书/执照号码",
        "patterns": [
            r"(?i)(驾驶证|执照|license|DL)[:]\s*[A-Z0-9]+",
        ],
        "severity": "MEDIUM"
    },
    "12_vehicle": {
        "description": "车辆标识符",
        "patterns": [
            r"(?i)(车牌|VIN)[:]\s*[A-Z0-9]+",
        ],
        "severity": "MEDIUM"
    },
    "13_device": {
        "description": "设备标识符和序列号",
        "patterns": [
            r"(?i)(序列号|设备)\s+(号码|#)[:]\s*[A-Z0-9-]+",
        ],
        "severity": "MEDIUM"
    },
    "14_url": {
        "description": "网址URL",
        "patterns": [
            r"https?://[^\s]+",
            r"www\.[^\s]+",
        ],
        "severity": "MEDIUM"
    },
    "15_ip": {
        "description": "IP地址",
        "patterns": [
            r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
        ],
        "severity": "HIGH"
    },
    "16_biometric": {
        "description": "生物识别标识符",
        "patterns": [
            r"(?i)(指纹|声纹|视网膜扫描)",
        ],
        "severity": "CRITICAL"
    },
    "17_photos": {
        "description": "全脸照片",
        "patterns": [
            r"(?i)(照片|相片|图像).*面",
            r"\.(jpg|jpeg|png|gif)\b",
        ],
        "severity": "HIGH"
    },
    "18_unique": {
        "description": "任何其他唯一的识别特征",
        "patterns": [
            r"(?i)(纹身|胎记|疤痕).*独特",
        ],
        "severity": "MEDIUM"
    },
}


def check_identifiers(text: str) -> Dict:
    """检查文本中的HIPAA标识符。"""
    violations = {}
    total_issues = 0
    
    for identifier_id, config in HIPAA_IDENTIFIERS.items():
        matches = []
        for pattern in config["patterns"]:
            found = re.findall(pattern, text, re.IGNORECASE)
            matches.extend(found)
        
        if matches:
            # 移除重复项，限制为前5个示例
            unique_matches = list(set(matches))[:5]
            violations[identifier_id] = {
                "description": config["description"],
                "severity": config["severity"],
                "count": len(matches),
                "examples": unique_matches
            }
            total_issues += len(matches)
    
    return {
        "total_violations": len(violations),
        "total_instances": total_issues,
        "violations": violations
    }


def check_age_compliance(text: str) -> Dict:
    """检查大于89岁的年龄是否正确聚合。"""
    age_pattern = r"\b(\d{2,3})\s*(?:岁|year|yr)s?[\s-]?old\b"
    ages = [int(age) for age in re.findall(age_pattern, text, re.IGNORECASE)]
    
    violations = [age for age in ages if age > 89]
    
    return {
        "ages_over_89": len(violations),
        "examples": violations[:5] if violations else [],
        "compliant": len(violations) == 0
    }


def generate_report(filename: str) -> Dict:
    """生成去标识化合规报告。"""
    filepath = Path(filename)
    
    if not filepath.exists():
        raise FileNotFoundError(f"未找到文件: {filename}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    
    identifier_check = check_identifiers(text)
    age_check = check_age_compliance(text)
    
    # 确定整体合规性
    critical_violations = sum(
        1 for v in identifier_check["violations"].values()
        if v["severity"] == "CRITICAL"
    )
    high_violations = sum(
        1 for v in identifier_check["violations"].values()
        if v["severity"] == "HIGH"
    )
    
    if critical_violations > 0 or high_violations >= 3:
        status = "NON_COMPLIANT"
    elif high_violations > 0 or not age_check["compliant"]:
        status = "NEEDS_REVIEW"
    else:
        status = "COMPLIANT"
    
    report = {
        "filename": str(filename),
        "status": status,
        "identifier_violations": identifier_check,
        "age_compliance": age_check,
        "recommendation": get_recommendation(status, identifier_check, age_check)
    }
    
    return report


def get_recommendation(status: str, identifiers: Dict, ages: Dict) -> str:
    """根据发现生成建议。"""
    if status == "COMPLIANT":
        return "文档看起来合规。发布前进行最终人工审查。"
    
    recommendations = []
    
    if identifiers["total_violations"] > 0:
        recommendations.append(
            f"移除或编辑识别出的{identifiers['total_instances']}个HIPAA标识符。"
        )
    
    if not ages["compliant"]:
        recommendations.append(
            f"将{ages['ages_over_89']}个大于89岁的年龄聚合为'90岁或以上'或'>89岁'。"
        )
    
    return " ".join(recommendations)


def print_report(report: Dict):
    """打印人类可读报告。"""
    print("=" * 70)
    print("HIPAA去标识化检查")
    print(f"文件: {report['filename']}")
    print("=" * 70)
    print()
    
    print(f"整体状态: {report['status']}")
    print()
    
    if report["identifier_violations"]["total_violations"] == 0:
        print("✓ 未检测到HIPAA标识符")
    else:
        print(f"⚠  发现 {report['identifier_violations']['total_violations']} 类违规")
        print(f"   总实例数: {report['identifier_violations']['total_instances']}")
        print()
        
        print("按类型分类的违规:")
        print("-" * 70)
        
        for id_type, details in sorted(
            report["identifier_violations"]["violations"].items(),
            key=lambda x: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}[x[1]["severity"]]
        ):
            severity_symbol = "⚠⚠⚠" if details["severity"] == "CRITICAL" else "⚠⚠" if details["severity"] == "HIGH" else "⚠"
            print(f"{severity_symbol} [{details['severity']:8}] {details['description']}")
            print(f"   数量: {details['count']}")
            print(f"   示例:")
            for example in details["examples"]:
                print(f"     - {example}")
            print()
    
    age_check = report["age_compliance"]
    if age_check["compliant"]:
        print("✓ 年龄报告合规（没有大于89岁的年龄或正确聚合）")
    else:
        print(f"⚠  年龄合规问题: 检测到{age_check['ages_over_89']}个大于89岁的年龄")
        print(f"   年龄必须聚合为'90岁或以上'或'>89岁'")
        print(f"   发现的年龄: {age_check['examples']}")
    
    print()
    print("建议:")
    print(report["recommendation"])
    print("=" * 70)


def main():
    """主入口点。"""
    parser = argparse.ArgumentParser(
        description="检查临床报告中的HIPAA标识符"
    )
    parser.add_argument("input_file", help="临床报告文件路径")
    parser.add_argument("--output", "-o", help="输出JSON报告到文件")
    parser.add_argument("--json", action="store_true", help="输出JSON到stdout")
    
    args = parser.parse_args()
    
    try:
        report = generate_report(args.input_file)
        
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print_report(report)
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\nJSON报告已保存到: {args.output}")
        
        # 如果发现违规则返回非零退出代码
        exit_code = 0 if report["status"] == "COMPLIANT" else 1
        return exit_code
        
    except Exception as e:
        print(f"错误: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
