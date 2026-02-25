#!/usr/bin/env python3
"""
内容创意生成器
基于知识库和过往成功内容生成内容创意。
"""

import json
import argparse
from datetime import datetime
from pathlib import Path

BRAIN_ROOT = Path(__file__).parent.parent.parent

def load_jsonl(filepath):
    """加载JSONL文件，跳过架构行。"""
    items = []
    if not filepath.exists():
        return items
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if '_schema' not in data:
                    items.append(data)
            except json.JSONDecodeError:
                continue
    return items

def get_top_performing_content():
    """获取参与度最高的帖子。"""
    posts = load_jsonl(BRAIN_ROOT / 'content' / 'posts.jsonl')

    # 如果有参与度指标则按其排序
    def engagement_score(post):
        metrics = post.get('metrics', {})
        return (
            metrics.get('likes', 0) +
            metrics.get('comments', 0) * 2 +
            metrics.get('reposts', 0) * 3
        )

    sorted_posts = sorted(posts, key=engagement_score, reverse=True)
    return sorted_posts[:5]

def get_recent_bookmarks(category=None):
    """获取最近的书签，可选择按类别筛选。"""
    bookmarks = load_jsonl(BRAIN_ROOT / 'knowledge' / 'bookmarks.jsonl')

    if category:
        bookmarks = [b for b in bookmarks if b.get('category') == category]

    # 按日期排序，最近的在前
    bookmarks.sort(key=lambda x: x.get('saved_at', ''), reverse=True)
    return bookmarks[:10]

def get_undeveloped_ideas():
    """获取尚未开发的创意。"""
    ideas = load_jsonl(BRAIN_ROOT / 'content' / 'ideas.jsonl')

    raw_ideas = [i for i in ideas if i.get('status') == 'raw']
    return raw_ideas

def generate_suggestions(pillar=None, count=5):
    """生成内容建议。"""

    output = f"""
# 内容创意生成器
生成时间: {datetime.now().isoformat()}
筛选条件: {pillar or '所有支柱'}

## 基于表现最佳的内容
"""

    top_posts = get_top_performing_content()
    if top_posts:
        output += "\n您表现最佳的内容主题:\n"
        for post in top_posts[:3]:
            output += f"- {post.get('pillar', '未知')}: {post.get('type', 'post')}\n"
        output += "\n**建议**: 在这些高表现领域创建更多内容。\n"
    else:
        output += "\n尚无帖子历史。开始创作吧！\n"

    output += """
## 来自您的知识库
"""

    bookmarks = get_recent_bookmarks(pillar)
    if bookmarks:
        output += "\n您最近研究过的主题:\n"
        for bm in bookmarks[:5]:
            output += f"- {bm.get('title', '无标题')} ({bm.get('category', '未分类')})\n"
            if bm.get('key_insights'):
                output += f"  关键洞见: {bm['key_insights'][0]}\n"
        output += "\n**建议**: 将这些研究主题转化为教育性内容。\n"
    else:
        output += "\n还没有书签。保存有趣的内容以激发创意。\n"

    output += """
## 未开发的创意
"""

    ideas = get_undeveloped_ideas()
    if ideas:
        output += f"\n您有 {len(ideas)} 个未开发的创意:\n"
        for idea in ideas[:count]:
            output += f"- [{idea.get('priority', 'medium')}] {idea.get('idea', '无内容')}\n"
        output += "\n**建议**: 今天选择一个高优先级创意并开发它。\n"
    else:
        output += "\n队列中没有未开发的创意。\n"

    output += """
## 快速提示

1. "这周我学到了什么对他人有价值的东西？"
2. "我在行业中发现的一个常见错误是什么？"
3. "我被问到最多的问题是什么？"
4. "什么对我有效但违反直觉？"
5. "我希望我刚开始时知道什么？"
"""

    return output

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='生成内容创意')
    parser.add_argument('--pillar', '-p', help='按内容支柱筛选')
    parser.add_argument('--count', '-c', type=int, default=5, help='要显示的创意数量')

    args = parser.parse_args()
    print(generate_suggestions(args.pillar, args.count))
