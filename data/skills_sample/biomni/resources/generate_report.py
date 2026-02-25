#!/usr/bin/env python3
"""
为biomni对话历史生成增强的PDF报告。

此脚本为biomni报告提供额外的自定义选项：
- 自定义样式和品牌
- 格式化的代码块
- 章节组织
- 元数据包含
- 导出格式选项（PDF、HTML、Markdown）

使用方法:
    python generate_report.py --input conversation.json --output report.pdf
    python generate_report.py --agent-object agent --output report.pdf --format html
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


def format_conversation_history(
    messages: List[Dict[str, Any]],
    include_metadata: bool = True,
    include_code: bool = True,
    include_timestamps: bool = False
) -> str:
    """
    将对话历史格式化为结构化markdown。

    参数:
        messages: 对话消息字典列表
        include_metadata: 包含元数据部分
        include_code: 包含代码块
        include_timestamps: 包含消息时间戳

    返回:
        格式化的markdown字符串
    """
    sections = []

    # 标题
    sections.append("# Biomni分析报告\n")

    # 元数据
    if include_metadata:
        sections.append("## 元数据\n")
        sections.append(f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        sections.append(f"- **交互次数**: {len(messages)}")
        sections.append("\n---\n")

    # 处理消息
    sections.append("## 分析\n")

    for i, msg in enumerate(messages, 1):
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')

        if role == 'user':
            sections.append(f"### 任务 {i // 2 + 1}\n")
            sections.append(f"**查询:**\n```\n{content}\n```\n")

        elif role == 'assistant':
            sections.append(f"**响应:**\n")

            # 检查内容是否包含代码
            if include_code and ('```' in content or 'import ' in content):
                # 尝试分离文本和代码
                parts = content.split('```')
                for j, part in enumerate(parts):
                    if j % 2 == 0:
                        # 文本内容
                        if part.strip():
                            sections.append(f"{part.strip()}\n")
                    else:
                        # 代码内容
                        # 检查是否指定了语言
                        lines = part.split('\n', 1)
                        if len(lines) > 1 and lines[0].strip() in ['python', 'r', 'bash', 'sql']:
                            lang = lines[0].strip()
                            code = lines[1]
                        else:
                            lang = 'python'  # 默认为python
                            code = part

                        sections.append(f"```{lang}\n{code}\n```\n")
            else:
                sections.append(f"{content}\n")

            sections.append("\n---\n")

    return '\n'.join(sections)


def markdown_to_html(markdown_content: str, title: str = "Biomni报告") -> str:
    """
    将markdown转换为带样式的HTML。

    参数:
        markdown_content: Markdown字符串
        title: HTML页面标题

    返回:
        HTML字符串
    """
    # 简单的markdown到HTML转换
    # 生产环境建议使用markdown或mistune等库

    html_template = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            border-bottom: 2px solid #95a5a6;
            padding-bottom: 5px;
        }}
        h3 {{
            color: #555;
        }}
        code {{
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
        }}
        pre {{
            background-color: #f8f8f8;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 15px;
            overflow-x: auto;
        }}
        pre code {{
            background-color: transparent;
            padding: 0;
        }}
        hr {{
            border: none;
            border-top: 1px solid #ddd;
            margin: 30px 0;
        }}
        .metadata {{
            background-color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .task {{
            background-color: #e8f4f8;
            padding: 10px;
            border-left: 4px solid #3498db;
            margin: 20px 0;
        }}
        .footer {{
            margin-top: 50px;
            text-align: center;
            color: #7f8c8d;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="content">
        {markdown_to_html_simple(markdown_content)}
    </div>
    <div class="footer">
        <p>由Biomni生成 | Stanford SNAP Lab</p>
        <p><a href="https://github.com/snap-stanford/biomni">github.com/snap-stanford/biomni</a></p>
    </div>
</body>
</html>
"""
    return html_template


def markdown_to_html_simple(md: str) -> str:
    """简单的markdown到HTML转换器（基本实现）。"""
    lines = md.split('\n')
    html_lines = []
    in_code_block = False
    in_list = False

    for line in lines:
        # 代码块
        if line.startswith('```'):
            if in_code_block:
                html_lines.append('</code></pre>')
                in_code_block = False
            else:
                lang = line[3:].strip()
                html_lines.append(f'<pre><code class="language-{lang}">')
                in_code_block = True
            continue

        if in_code_block:
            html_lines.append(line)
            continue

        # 标题
        if line.startswith('# '):
            html_lines.append(f'<h1>{line[2:]}</h1>')
        elif line.startswith('## '):
            html_lines.append(f'<h2>{line[3:]}</h2>')
        elif line.startswith('### '):
            html_lines.append(f'<h3>{line[4:]}</h3>')
        # 列表
        elif line.startswith('- '):
            if not in_list:
                html_lines.append('<ul>')
                in_list = True
            html_lines.append(f'<li>{line[2:]}</li>')
        else:
            if in_list:
                html_lines.append('</ul>')
                in_list = False

            # 水平线
            if line.strip() == '---':
                html_lines.append('<hr>')
            # 粗体
            elif '**' in line:
                line = line.replace('**', '<strong>', 1).replace('**', '</strong>', 1)
                html_lines.append(f'<p>{line}</p>')
            # 常规段落
            elif line.strip():
                html_lines.append(f'<p>{line}</p>')
            else:
                html_lines.append('<br>')

    if in_list:
        html_lines.append('</ul>')

    return '\n'.join(html_lines)


def generate_report(
    conversation_data: Dict[str, Any],
    output_path: Path,
    format: str = 'markdown',
    title: Optional[str] = None
):
    """
    从对话数据生成格式化报告。

    参数:
        conversation_data: 对话历史字典
        output_path: 输出文件路径
        format: 输出格式（'markdown'、'html'或'pdf'）
        title: 报告标题
    """
    messages = conversation_data.get('messages', [])

    if not title:
        title = f"Biomni分析 - {datetime.now().strftime('%Y-%m-%d')}"

    # 生成markdown
    markdown_content = format_conversation_history(messages)

    if format == 'markdown':
        output_path.write_text(markdown_content)
        print(f"✓ Markdown报告已保存到 {output_path}")

    elif format == 'html':
        html_content = markdown_to_html(markdown_content, title)
        output_path.write_text(html_content)
        print(f"✓ HTML报告已保存到 {output_path}")

    elif format == 'pdf':
        # 对于PDF生成，通常需要使用weasyprint或reportlab等库
        # 这是一个占位符实现
        print("PDF生成需要额外的依赖项（weasyprint或reportlab）")
        print("回退到HTML格式...")

        html_path = output_path.with_suffix('.html')
        html_content = markdown_to_html(markdown_content, title)
        html_path.write_text(html_content)

        print(f"✓ HTML报告已保存到 {html_path}")
        print("  要转换为PDF:")
        print(f"    1. 安装weasyprint: pip install weasyprint")
        print(f"    2. 运行: weasyprint {html_path} {output_path}")

    else:
        raise ValueError(f"不支持的格式: {format}")


def main():
    """CLI使用的主入口点。"""
    parser = argparse.ArgumentParser(
        description="从biomni对话历史生成增强报告"
    )

    parser.add_argument(
        '--input',
        type=Path,
        required=True,
        help='输入对话历史JSON文件'
    )

    parser.add_argument(
        '--output',
        type=Path,
        required=True,
        help='输出报告文件路径'
    )

    parser.add_argument(
        '--format',
        choices=['markdown', 'html', 'pdf'],
        default='markdown',
        help='输出格式（默认：markdown）'
    )

    parser.add_argument(
        '--title',
        type=str,
        help='报告标题（可选）'
    )

    args = parser.parse_args()

    # 加载对话数据
    try:
        with open(args.input, 'r') as f:
            conversation_data = json.load(f)
    except FileNotFoundError:
        print(f"❌ 未找到输入文件: {args.input}")
        return 1
    except json.JSONDecodeError:
        print(f"❌ 输入文件中的JSON无效: {args.input}")
        return 1

    # 生成报告
    try:
        generate_report(
            conversation_data,
            args.output,
            format=args.format,
            title=args.title
        )
        return 0
    except Exception as e:
        print(f"❌ 生成报告时出错: {e}")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
