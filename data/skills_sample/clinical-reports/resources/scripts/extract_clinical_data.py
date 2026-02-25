#!/usr/bin/env python3
"""
从报告中提取结构化临床数据。

用法：
    python extract_clinical_data.py <report_file>
"""

import argparse
import json
import re


def extract_vital_signs(content: str) -> dict:
    """提取生命体征。"""
    vitals = {}
    patterns = {
        "temperature": r"(?i)体温(?:度)?[:]\s*([\d.]+)\s*°?F",
        "bp": r"(?i)血压[:]\s*(\d+/\d+)",
        "hr": r"(?i)心率[:]\s*(\d+)",
        "rr": r"(?i)呼吸率[:]\s*(\d+)",
        "spo2": r"(?i)血氧饱和度[:]\s*([\d.]+)%",
    }
    
    for vital, pattern in patterns.items():
        match = re.search(pattern, content)
        if match:
            vitals[vital] = match.group(1)
    
    return vitals


def extract_demographics(content: str) -> dict:
    """提取患者人口统计学信息。"""
    demographics = {}
    patterns = {
        "age": r"(?i)(\d+)[\s-]岁[\s-]龄",
        "sex": r"(?i)(男|女|M|F)",
    }
    
    for demo, pattern in patterns.items():
        match = re.search(pattern, content)
        if match:
            demographics[demo] = match.group(1)
    
    return demographics


def extract_medications(content: str) -> list:
    """提取用药列表。"""
    meds = []
    # 常见药物格式的简单模式
    pattern = r"(?i)(\w+)\s+(\d+\s*mg)\s*(口服|静脉|皮下)\s*(每日|每日两次|每日三次|每日四次)"
    matches = re.findall(pattern, content)
    
    for match in matches:
        meds.append({
            "drug": match[0],
            "dose": match[1],
            "route": match[2],
            "frequency": match[3]
        })
    
    return meds


def main():
    """主入口点。"""
    parser = argparse.ArgumentParser(description="提取临床数据")
    parser.add_argument("input_file", help="临床报告路径")
    parser.add_argument("--output", "-o", help="输出 JSON 文件")
    
    args = parser.parse_args()
    
    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        extracted_data = {
            "demographics": extract_demographics(content),
            "vital_signs": extract_vital_signs(content),
            "medications": extract_medications(content),
        }
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(extracted_data, f, indent=2)
            print(f"✓ 数据已提取至: {args.output}")
        else:
            print(json.dumps(extracted_data, indent=2))
        
        return 0
        
    except Exception as e:
        print(f"错误: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
