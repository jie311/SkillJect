#!/usr/bin/env python3
"""
api-test-automation - 生成器脚本
基于端点分析和规范为REST和GraphQL API生成综合测试套件。
生成时间: 2025-12-10 03:48:17
"""

import os
import json
import argparse
from pathlib import Path
from datetime import datetime

class Generator:
    def __init__(self, config: dict):
        self.config = config
        self.output_dir = Path(config.get('output', './output'))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_markdown(self, title: str, content: str) -> Path:
        """生成markdown文档。"""
        filename = f"{title.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        file_path = self.output_dir / filename

        md_content = f"""# {title}

由api-test-automation生成
日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 概述
{content}

## 配置
```json
{json.dumps(self.config, indent=2)}
```

## 类别
testing

## 插件
api-test-automation
"""

        file_path.write_text(md_content)
        return file_path

    def generate_json(self, data: dict) -> Path:
        """生成JSON输出。"""
        filename = f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_path = self.output_dir / filename

        output_data = {
            "generated_by": "api-test-automation",
            "timestamp": datetime.now().isoformat(),
            "category": "testing",
            "plugin": "api-test-automation",
            "data": data,
            "config": self.config
        }

        with open(file_path, 'w') as f:
            json.dump(output_data, f, indent=2)

        return file_path

    def generate_script(self, name: str, template: str) -> Path:
        """生成可执行脚本。"""
        filename = f"{name}.sh"
        file_path = self.output_dir / filename

        script_content = f"""#!/bin/bash
# 由api-test-automation生成
# 日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

set -e  # 出错时退出

echo "🚀 正在运行 {name}..."

# 模板内容
{template}

echo "✅ 成功完成"
"""

        file_path.write_text(script_content)
        file_path.chmod(0o755)  # 使其可执行
        return file_path

def main():
    parser = argparse.ArgumentParser(description="基于端点分析和规范为REST和GraphQL API生成综合测试套件。")
    parser.add_argument('--type', choices=['markdown', 'json', 'script'], default='markdown')
    parser.add_argument('--output', '-o', default='./output', help='输出目录')
    parser.add_argument('--config', '-c', help='配置文件')
    parser.add_argument('--title', default='api-test-automation 输出')
    parser.add_argument('--content', help='要包含的内容')

    args = parser.parse_args()

    config = {'output': args.output}
    if args.config and Path(args.config).exists():
        with open(args.config) as f:
            config.update(json.load(f))

    generator = Generator(config)

    print(f"🔧 正在生成 {args.type} 输出...")

    if args.type == 'markdown':
        output_file = generator.generate_markdown(
            args.title,
            args.content or "生成的内容"
        )
    elif args.type == 'json':
        output_file = generator.generate_json(
            {"title": args.title, "content": args.content}
        )
    else:  # script
        output_file = generator.generate_script(
            args.title.lower().replace(' ', '_'),
            args.content or "# 在此处添加你的脚本内容"
        )

    print(f"✅ 已生成: {output_file}")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
