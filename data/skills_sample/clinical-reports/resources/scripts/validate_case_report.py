#!/usr/bin/env python3
"""
根据 CARE（CAse REport）指南验证临床病例报告。

此脚本检查临床病例报告是否符合 CARE 指南
并提供所需要素的检查清单。

用法：
    python validate_case_report.py <input_file.md|.txt>
    python validate_case_report.py <input_file> --output report.json
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple


class CareValidator:
    """CARE 指南合规性验证器。"""
    
    # 带有正则表达式模式的 CARE 检查清单项目
    CARE_REQUIREMENTS = {
        "title": {
            "name": "标题包含 'case report'",
            "pattern": r"(?i)(case\s+report|case\s+study)",
            "section": "Title",
            "required": True
        },
        "keywords": {
            "name": "提供关键词（2-5 个）",
            "pattern": r"(?i)keywords?[:]\s*(.+)",
            "section": "Keywords",
            "required": True
        },
        "abstract": {
            "name": "摘要存在",
            "pattern": r"(?i)##?\s*abstract",
            "section": "Abstract",
            "required": True
        },
        "introduction": {
            "name": "介绍解释新颖性",
            "pattern": r"(?i)##?\s*introduction",
            "section": "Introduction",
            "required": True
        },
        "patient_info": {
            "name": "患者人口统计学信息存在",
            "pattern": r"(?i)(patient\s+information|demographics?)",
            "section": "Patient Information",
            "required": True
        },
        "clinical_findings": {
            "name": "临床发现已记录",
            "pattern": r"(?i)(clinical\s+findings?|physical\s+exam)",
            "section": "Clinical Findings",
            "required": True
        },
        "timeline": {
            "name": "事件时间线",
            "pattern": r"(?i)(timeline|chronology)",
            "section": "Timeline",
            "required": True
        },
        "diagnostic": {
            "name": "诊断评估",
            "pattern": r"(?i)diagnostic\s+(assessment|evaluation|workup)",
            "section": "Diagnostic Assessment",
            "required": True
        },
        "therapeutic": {
            "name": "治疗干预",
            "pattern": r"(?i)(therapeutic\s+intervention|treatment)",
            "section": "Therapeutic Interventions",
            "required": True
        },
        "followup": {
            "name": "随访和结局",
            "pattern": r"(?i)(follow[\-\s]?up|outcomes?)",
            "section": "Follow-up and Outcomes",
            "required": True
        },
        "discussion": {
            "name": "讨论和文献综述",
            "pattern": r"(?i)##?\s*discussion",
            "section": "Discussion",
            "required": True
        },
        "consent": {
            "name": "知情同意声明",
            "pattern": r"(?i)(informed\s+consent|written\s+consent|consent.*obtained)",
            "section": "Informed Consent",
            "required": True
        },
    }
    
    # 要检查的 HIPAA 标识符
    HIPAA_PATTERNS = {
        "dates": r"\b(0?[1-9]|1[0-2])/(0?[1-9]|[12][0-9]|3[01])/\d{4}\b",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "mrn": r"(?i)(mrn|medical\s+record)[:]\s*\d+",
        "zip_full": r"\b\d{5}-\d{4}\b",
    }
    
    def __init__(self, filename: str):
        """使用输入文件初始化验证器。"""
        self.filename = Path(filename)
        self.content = self._read_file()
        self.results = {}
        
    def _read_file(self) -> str:
        """读取输入文件内容。"""
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"文件未找到: {self.filename}")
        except Exception as e:
            raise Exception(f"读取文件时出错: {e}")
    
    def validate_care_compliance(self) -> Dict[str, Dict]:
        """验证 CARE 指南合规性。"""
        results = {}
        
        for key, item in self.CARE_REQUIREMENTS.items():
            pattern = item["pattern"]
            found = bool(re.search(pattern, self.content))
            
            results[key] = {
                "name": item["name"],
                "section": item["section"],
                "required": item["required"],
                "found": found,
                "status": "PASS" if found else "FAIL" if item["required"] else "WARNING"
            }
        
        self.results["care_compliance"] = results
        return results
    
    def check_deidentification(self) -> Dict[str, List[str]]:
        """检查潜在的 HIPAA 标识符违规。"""
        violations = {}
        
        for identifier, pattern in self.HIPAA_PATTERNS.items():
            matches = re.findall(pattern, self.content)
            if matches:
                violations[identifier] = matches[:5]  # 限制为前 5 个示例
        
        self.results["hipaa_violations"] = violations
        return violations
    
    def check_word_count(self) -> Dict[str, int]:
        """检查字数并提供范围指导。"""
        words = len(re.findall(r'\b\w+\b', self.content))
        
        word_count = {
            "total_words": words,
            "typical_min": 1500,
            "typical_max": 3000,
            "status": "ACCEPTABLE" if 1500 <= words <= 3500 else "CHECK"
        }
        
        self.results["word_count"] = word_count
        return word_count
    
    def check_references(self) -> Dict[str, any]:
        """检查引用是否存在。"""
        ref_patterns = [
            r"##?\s*references",
            r"\[\d+\]",
            r"\d+\.\s+[A-Z][a-z]+.*\d{4}",  # 编号引用
        ]
        
        has_refs = any(re.search(p, self.content, re.IGNORECASE) for p in ref_patterns)
        ref_count = len(re.findall(r"\[\d+\]", self.content))
        
        references = {
            "has_references": has_refs,
            "estimated_count": ref_count,
            "recommended_min": 10,
            "status": "ACCEPTABLE" if ref_count >= 10 else "LOW"
        }
        
        self.results["references"] = references
        return references
    
    def generate_report(self) -> Dict:
        """生成综合验证报告。"""
        if not self.results:
            self.validate_care_compliance()
            self.check_deidentification()
            self.check_word_count()
            self.check_references()
        
        # 计算总体合规性
        care = self.results["care_compliance"]
        total_required = sum(1 for v in care.values() if v["required"])
        passed = sum(1 for v in care.values() if v["required"] and v["found"])
        compliance_rate = (passed / total_required * 100) if total_required > 0 else 0
        
        report = {
            "filename": str(self.filename),
            "compliance_rate": round(compliance_rate, 1),
            "care_compliance": care,
            "hipaa_violations": self.results["hipaa_violations"],
            "word_count": self.results["word_count"],
            "references": self.results["references"],
            "overall_status": "PASS" if compliance_rate >= 90 and not self.results["hipaa_violations"] else "NEEDS_REVISION"
        }
        
        return report
    
    def print_report(self):
        """打印人类可读的验证报告。"""
        report = self.generate_report()
        
        print("=" * 70)
        print(f"CARE 指南验证报告")
        print(f"文件: {report['filename']}")
        print("=" * 70)
        print()
        
        print(f"总体合规性: {report['compliance_rate']}%")
        print(f"状态: {report['overall_status']}")
        print()
        
        print("CARE 检查清单:")
        print("-" * 70)
        for key, item in report["care_compliance"].items():
            status_symbol = "✓" if item["found"] else "✗"
            print(f"{status_symbol} [{item['status']:8}] {item['name']}")
        print()
        
        if report["hipaa_violations"]:
            print("HIPAA 去标识警告:")
            print("-" * 70)
            for identifier, examples in report["hipaa_violations"].items():
                print(f"⚠  {identifier.upper()}: 发现 {len(examples)} 个实例")
                for ex in examples[:3]:
                    print(f"   示例: {ex}")
            print()
        else:
            print("✓ 未检测到明显的 HIPAA 标识符")
            print()
        
        wc = report["word_count"]
        print(f"字数: {wc['total_words']} 字")
        print(f"  典型范围: {wc['typical_min']}-{wc['typical_max']} 字")
        print(f"  状态: {wc['status']}")
        print()
        
        refs = report["references"]
        print(f"引用: 检测到 {refs['estimated_count']} 个引用")
        print(f"  推荐最小值: {refs['recommended_min']}")
        print(f"  状态: {refs['status']}")
        print()
        
        print("=" * 70)
        
        # 建议
        issues = []
        if report['compliance_rate'] < 100:
            missing = [v["name"] for v in report["care_compliance"].values() if v["required"] and not v["found"]]
            issues.append(f"缺少必需部分: {', '.join(missing)}")
        
        if report["hipaa_violations"]:
            issues.append("检测到 HIPAA 标识符 - 审查去标识化")
        
        if refs["status"] == "LOW":
            issues.append("引用数量低 - 考虑添加更多引用")
        
        if issues:
            print("建议:")
            for i, issue in enumerate(issues, 1):
                print(f"{i}. {issue}")
        else:
            print("✓ 病例报告符合 CARE 指南！")
        
        print("=" * 70)


def main():
    """主入口点。"""
    parser = argparse.ArgumentParser(
        description="根据 CARE 指南验证临床病例报告"
    )
    parser.add_argument(
        "input_file",
        help="病例报告文件路径（Markdown 或文本）"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="输出 JSON 报告至文件"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON 至标准输出而不是人类可读报告"
    )
    
    args = parser.parse_args()
    
    try:
        validator = CareValidator(args.input_file)
        report = validator.generate_report()
        
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            validator.print_report()
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\nJSON 报告已保存至: {args.output}")
        
        # 如果验证失败则返回非零退出码
        exit_code = 0 if report["overall_status"] == "PASS" else 1
        return exit_code
        
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
