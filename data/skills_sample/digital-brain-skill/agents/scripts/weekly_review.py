#!/usr/bin/env python3
"""
周报生成器
将数字大脑中的数据编译成周报文档。
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

# 获取数字大脑根目录（agents/的父目录）
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
                # 跳过架构定义行
                if '_schema' not in data:
                    items.append(data)
            except json.JSONDecodeError:
                continue
    return items

def get_week_range():
    """获取当前周的开始和结束日期。"""
    today = datetime.now()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')

def analyze_content(week_start):
    """分析本周发布的内容。"""
    posts = load_jsonl(BRAIN_ROOT / 'content' / 'posts.jsonl')
    ideas = load_jsonl(BRAIN_ROOT / 'content' / 'ideas.jsonl')

    week_posts = [p for p in posts if p.get('published', '') >= week_start]
    new_ideas = [i for i in ideas if i.get('created', '') >= week_start]

    return {
        'posts_published': len(week_posts),
        'new_ideas': len(new_ideas),
        'posts': week_posts
    }

def analyze_network(week_start):
    """分析本周的网络活动。"""
    interactions = load_jsonl(BRAIN_ROOT / 'network' / 'interactions.jsonl')

    week_interactions = [i for i in interactions if i.get('date', '') >= week_start]

    return {
        'interactions': len(week_interactions),
        'details': week_interactions
    }

def analyze_metrics():
    """获取最新指标（如果可用）。"""
    metrics = load_jsonl(BRAIN_ROOT / 'operations' / 'metrics.jsonl')
    if metrics:
        return metrics[-1]  # 最新的
    return {}

def generate_review():
    """生成周报输出。"""
    week_start, week_end = get_week_range()

    content = analyze_content(week_start)
    network = analyze_network(week_start)
    metrics = analyze_metrics()

    review = f"""
# 周报: {week_start} 至 {week_end}
生成时间: {datetime.now().isoformat()}

## 摘要

### 内容
- 已发布帖子: {content['posts_published']}
- 新捕获创意: {content['new_ideas']}

### 人脉网络
- 已记录互动: {network['interactions']}

### 最新指标
"""

    if metrics:
        audience = metrics.get('audience', {})
        for key, value in audience.items():
            review += f"- {key}: {value}\n"
    else:
        review += "- 尚未记录指标\n"

    review += """
## 待办事项

1. [ ] 审查内容表现
2. [ ] 规划下周内容
3. [ ] 跟进待处理的介绍
4. [ ] 更新目标进度
5. [ ] 安排重要会议

## 备注

[在此添加您的反思]
"""

    return review

if __name__ == '__main__':
    print(generate_review())
