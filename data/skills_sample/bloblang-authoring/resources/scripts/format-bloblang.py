#!/usr/bin/env python3
"""
将jsonschema输出的bloblang函数或方法元数据格式化为类别文件。
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List


def parse_args():
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="将bloblang元数据格式化为类别文件"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="写入类别文件的目录",
    )
    return parser.parse_args()


def get_category_names(category_type: str) -> tuple:
    """根据类别类型获取标签类型和文件前缀。

    返回:
        tuple: (tag_type, file_prefix)，其中tag_type是单数（function/method）
               file_prefix是复数（functions/methods）
    """
    if category_type == "bloblang-functions":
        return ("function", "functions")
    else:
        return ("method", "methods")


def group_by_category(
    items: List[Dict[str, Any]], category_type: str
) -> Dict[str, List[Dict]]:
    """按类别（函数）或标签（方法）分组项目。"""
    grouped = defaultdict(list)

    for item in items:
        if category_type == "bloblang-functions":
            category = item.get("category", "未分类")
        else:  # methods
            categories = item.get("categories", [])
            if categories:
                # 方法可以有多个类别 - 使用第一个
                category = categories[0].get("Category", "未分类")
            else:
                category = "未分类"

        grouped[category].append(item)

    return dict(grouped)


def format_item(item: Dict[str, Any], category_type: str) -> str:
    """将单个函数或方法格式化为带标签的部分（无类别字段）。"""
    name = item["name"]

    # 构建参数字符串
    params = item.get("params", {}).get("named", [])
    if params:
        param_strs = [f"{p['name']}:{p['type']}" for p in params]
        params_attr = ", ".join(param_strs)
    else:
        params_attr = ""

    # 确定标签类型（函数或方法）
    tag_type, _ = get_category_names(category_type)

    # 带名称和参数属性的开始标签
    lines = [f'<{tag_type} name="{name}" params="{params_attr}">']

    # 描述，描述可能在categories[0].Description而不是顶层
    desc = item.get("description", "")
    if not desc:
        categories = item.get("categories", [])
        if categories and isinstance(categories[0], dict):
            desc = categories[0].get("Description", "")

    if desc:
        # 将描述分成句子（每句话单独一行）
        # 在'. '上分割以保留句子边界
        sentences = desc.split(". ")
        for i, sentence in enumerate(sentences):
            if sentence:  # 跳过空字符串
                # 如果不是最后一句则加回句号
                if i < len(sentences) - 1 and not sentence.endswith("."):
                    lines.append(sentence + ".")
                else:
                    lines.append(sentence)
    else:
        print(f"错误 {name} 缺少描述", file=sys.stderr)

    # 示例（如果存在则全部打印）
    examples = item.get("examples", [])
    for idx, example in enumerate(examples):
        if isinstance(example, dict):
            summary = example.get("summary", "")
            mapping = example.get("mapping", "")
        else:
            summary = ""
            mapping = example

        if mapping:  # 仅在非空时添加
            # 始终使用代码块格式（mapping在新行）
            if summary:
                lines.append(f'<example summary="{summary}">')
            else:
                lines.append("<example>")
            lines.append(mapping)
            lines.append("</example>")

    # 结束标签
    lines.append(f"</{tag_type}>")
    return "\n".join(lines)


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)

    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)

    # 从标准输入读取JSON
    schema = json.load(sys.stdin)

    # 查找类别类型和项目
    category_type = None
    items = None
    for key in ["bloblang-functions", "bloblang-methods"]:
        if key in schema:
            category_type = key
            items = schema[key]
            break

    if not items:
        print("错误：在schema中未找到bloblang项目", file=sys.stderr)
        sys.exit(1)

    # 按类别分组
    grouped = group_by_category(items, category_type)

    # 根据类型确定文件前缀
    _, file_prefix = get_category_names(category_type)

    # 将每个类别写入单独的文件
    for category_name in sorted(grouped.keys()):
        # 跳过空和已弃用的类别
        if not category_name or category_name == "Deprecated":
            continue

        # 清理类别名称用于文件名（用下划线替换空格）
        safe_category = (
            category_name.replace(" ", "_").replace("/", "_").replace("&", "_")
        )
        filename = f"{file_prefix}-{safe_category}.xml"
        filepath = output_dir / filename

        with open(filepath, "w") as f:
            # 按名称对类别内的项目排序
            category_items = sorted(grouped[category_name], key=lambda x: x["name"])

            # 格式化每个项目（不需要类别字段）
            formatted_items = []
            for item in category_items:
                formatted_items.append(format_item(item, category_type))

            f.write(f"<{file_prefix}>\n")
            f.write("\n\n".join(formatted_items))
            f.write(f"\n</{file_prefix}>\n")


if __name__ == "__main__":
    main()
