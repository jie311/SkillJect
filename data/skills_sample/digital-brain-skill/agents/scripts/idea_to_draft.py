#!/usr/bin/env python3
"""
创意草稿扩展器
获取创意ID并创建具有相关上下文的草稿框架。
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

def find_idea(idea_id):
    """通过ID或部分匹配查找创意。"""
    ideas = load_jsonl(BRAIN_ROOT / 'content' / 'ideas.jsonl')

    for idea in ideas:
        if idea.get('id') == idea_id:
            return idea
        # 部分匹配
        if idea_id.lower() in idea.get('id', '').lower():
            return idea
        if idea_id.lower() in idea.get('idea', '').lower():
            return idea

    return None

def find_related_bookmarks(tags, pillar):
    """查找与创意相关的书签。"""
    bookmarks = load_jsonl(BRAIN_ROOT / 'knowledge' / 'bookmarks.jsonl')

    related = []
    for bm in bookmarks:
        bm_tags = set(bm.get('tags', []))
        bm_category = bm.get('category', '')

        if tags and bm_tags.intersection(set(tags)):
            related.append(bm)
        elif pillar and bm_category == pillar:
            related.append(bm)

    return related[:5]

def find_similar_posts(pillar):
    """查找同一支柱中的过往帖子以供参考。"""
    posts = load_jsonl(BRAIN_ROOT / 'content' / 'posts.jsonl')

    similar = [p for p in posts if p.get('pillar') == pillar]
    return similar[:3]

def generate_draft_scaffold(idea_id):
    """从创意生成草稿框架。"""

    idea = find_idea(idea_id)

    if not idea:
        return f"错误: 无法找到匹配 '{idea_id}' 的创意"

    pillar = idea.get('pillar', 'general')
    tags = idea.get('tags', [])

    related_bookmarks = find_related_bookmarks(tags, pillar)
    similar_posts = find_similar_posts(pillar)

    output = f"""
# 草稿: {idea.get('idea', '无标题')}

## 元数据
```yaml
source_idea: {idea.get('id', 'unknown')}
pillar: {pillar}
created: {datetime.now().isoformat()}
status: draft
tags: {tags}
```

## 原始创意
```
{idea.get('idea', '无内容')}
```

来源: {idea.get('source', '未知')}
备注: {idea.get('notes', '无')}

---

## 引人入胜的开头选项
<!-- 撰写2-3个引人入胜的开头选项 -->

1. [开头选项 1]
2. [开头选项 2]
3. [开头选项 3]

---

## 主要观点

### 观点 1
[在此展开]

### 观点 2
[在此展开]

### 观点 3
[在此展开]

---

## 支持性证据
"""

    if related_bookmarks:
        output += "\n### 来自您的研究\n"
        for bm in related_bookmarks:
            output += f"- [{bm.get('title', '无标题')}]({bm.get('url', '#')})\n"
            if bm.get('key_insights'):
                output += f"  洞见: {bm['key_insights'][0]}\n"
    else:
        output += "\n未找到相关书签。考虑研究此主题。\n"

    output += """
---

## 参考: 相似过往内容
"""

    if similar_posts:
        for post in similar_posts:
            output += f"- {post.get('type', 'post')}: {post.get('url', '无URL')}\n"
    else:
        output += "\n未找到相似的过往内容。\n"

    output += """
---

## 行动号召

[读者应该做什么？]

---

## 发布前检查清单

- [ ] 引人入胜的开头
- [ ] 主要观点清晰且有价值
- [ ] 语调符合品牌（检查 identity/voice.md）
- [ ] 行动号召清晰
- [ ] 已校对

---

*记住: 在最终确定之前检查 identity/voice.md！*
"""

    return output

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='将创意扩展为草稿')
    parser.add_argument('idea_id', help='要扩展的创意的ID或部分匹配')

    args = parser.parse_args()
    print(generate_draft_scaffold(args.idea_id))
