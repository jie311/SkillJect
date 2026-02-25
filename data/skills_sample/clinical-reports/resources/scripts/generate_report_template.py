#!/usr/bin/env python3
"""
临床报告的交互式模板生成器。

帮助用户选择和生成适当的临床报告模板。

用法：
    python generate_report_template.py
    python generate_report_template.py --type case_report --output my_case_report.md
"""

import argparse
import shutil
from pathlib import Path


TEMPLATES = {
    "case_report": "case_report_template.md",
    "soap_note": "soap_note_template.md",
    "h_and_p": "history_physical_template.md",
    "discharge_summary": "discharge_summary_template.md",
    "consult_note": "consult_note_template.md",
    "radiology": "radiology_report_template.md",
    "pathology": "pathology_report_template.md",
    "lab": "lab_report_template.md",
    "sae": "clinical_trial_sae_template.md",
    "csr": "clinical_trial_csr_template.md",
}

DESCRIPTIONS = {
    "case_report": "临床病例报告（CARE 指南）",
    "soap_note": "SOAP 进程记录",
    "h_and_p": "病史和体格检查",
    "discharge_summary": "出院小结",
    "consult_note": "会诊记录",
    "radiology": "放射学/影像报告",
    "pathology": "外科病理报告",
    "lab": "实验室报告",
    "sae": "严重不良事件报告",
    "csr": "临床研究报告（ICH-E3）",
}


def get_template_dir() -> Path:
    """获取模板目录路径。"""
    script_dir = Path(__file__).parent
    template_dir = script_dir.parent / "assets"
    return template_dir


def list_templates():
    """列出可用模板。"""
    print("\n可用的临床报告模板:")
    print("=" * 60)
    for i, (key, desc) in enumerate(DESCRIPTIONS.items(), 1):
        print(f"{i:2}. {key:20} - {desc}")
    print("=" * 60)


def generate_template(template_type: str, output_file: str = None):
    """生成模板文件。"""
    if template_type not in TEMPLATES:
        raise ValueError(f"无效的模板类型: {template_type}")
    
    template_filename = TEMPLATES[template_type]
    template_path = get_template_dir() / template_filename
    
    if not template_path.exists():
        raise FileNotFoundError(f"模板未找到: {template_path}")
    
    if output_file is None:
        output_file = f"new_{template_filename}"
    
    shutil.copy(template_path, output_file)
    print(f"✓ 模板已创建: {output_file}")
    print(f"  类型: {DESCRIPTIONS[template_type]}")
    print(f"  源文件: {template_filename}")
    
    return output_file


def interactive_mode():
    """交互式模板选择。"""
    list_templates()
    print()
    
    while True:
        choice = input("选择模板编号（或 'q' 退出）: ").strip()
        
        if choice.lower() == 'q':
            print("再见！")
            return
        
        try:
            idx = int(choice) - 1
            template_types = list(TEMPLATES.keys())
            
            if 0 <= idx < len(template_types):
                template_type = template_types[idx]
                output_file = input(f"输出文件名（默认: new_{TEMPLATES[template_type]}）: ").strip()
                
                if not output_file:
                    output_file = None
                
                generate_template(template_type, output_file)
                
                another = input("\n生成另一个模板？: ").strip().lower()
                if another != 'y':
                    print("再见！")
                    return
                else:
                    print()
                    list_templates()
                    print()
            else:
                print("无效选择。请重试。")
        except (ValueError, IndexError):
            print("无效输入。请输入数字或 'q' 退出。")


def main():
    """主入口点。"""
    parser = argparse.ArgumentParser(
        description="生成临床报告模板"
    )
    parser.add_argument(
        "--type",
        choices=list(TEMPLATES.keys()),
        help="要生成的模板类型"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="输出文件名"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出可用模板"
    )
    
    args = parser.parse_args()
    
    try:
        if args.list:
            list_templates()
        elif args.type:
            generate_template(args.type, args.output)
        else:
            # 交互模式
            interactive_mode()
        
        return 0
        
    except Exception as e:
        print(f"错误: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
