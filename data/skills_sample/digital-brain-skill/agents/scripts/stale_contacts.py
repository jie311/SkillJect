#!/usr/bin/env python3
"""
过期联系人查找器
识别最近未联系过的联系人。
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

BRAIN_ROOT = Path(__file__).parent.parent.parent

# 每个圈子的阈值（天数）
THRESHOLDS = {
    'inner': 14,      # 2周
    'active': 30,     # 1个月
    'network': 60,    # 2个月
    'dormant': 180    # 6个月（用于潜在重新激活）
}

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

def days_since(date_str):
    """计算自某个日期以来的天数。"""
    if not date_str:
        return 999  # 如果没有日期则表示很久未联系
    try:
        date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return (datetime.now(date.tzinfo) - date).days
    except (ValueError, TypeError):
        return 999

def find_stale_contacts():
    """查找需要联系的联系人。"""
    contacts = load_jsonl(BRAIN_ROOT / 'network' / 'contacts.jsonl')

    stale = {
        'urgent': [],      # 严重逾期
        'due': [],         # 到期需要联系
        'coming_up': []    # 即将到期
    }

    for contact in contacts:
        circle = contact.get('circle', 'network')
        threshold = THRESHOLDS.get(circle, 60)
        days = days_since(contact.get('last_contact'))

        contact_info = {
            'name': contact.get('name', '未知'),
            'circle': circle,
            'days_since': days,
            'threshold': threshold,
            'handle': contact.get('handle', ''),
            'notes': contact.get('notes', '')[:100]
        }

        if days > threshold * 1.5:
            stale['urgent'].append(contact_info)
        elif days > threshold:
            stale['due'].append(contact_info)
        elif days > threshold * 0.75:
            stale['coming_up'].append(contact_info)

    return stale

def generate_report():
    """生成过期联系人报告。"""
    stale = find_stale_contacts()

    output = f"""
# 过期联系人报告
生成时间: {datetime.now().isoformat()}

## 紧急逾期 ({len(stale['urgent'])})
"""

    if stale['urgent']:
        for c in sorted(stale['urgent'], key=lambda x: -x['days_since']):
            output += f"- **{c['name']}** ({c['circle']}) - {c['days_since']} 天未联系\n"
            if c['handle']:
                output += f"  {c['handle']}\n"
    else:
        output += "无！您做得很好。\n"

    output += f"""
## 到期需要联系 ({len(stale['due'])})
"""

    if stale['due']:
        for c in sorted(stale['due'], key=lambda x: -x['days_since']):
            output += f"- {c['name']} ({c['circle']}) - {c['days_since']} 天\n"
    else:
        output += "目前没有到期的。\n"

    output += f"""
## 即将到期 ({len(stale['coming_up'])})
"""

    if stale['coming_up']:
        for c in sorted(stale['coming_up'], key=lambda x: -x['days_since']):
            output += f"- {c['name']} ({c['circle']}) - {c['days_since']} 天（阈值: {c['threshold']}）\n"
    else:
        output += "没有联系人即将达到阈值。\n"

    output += """
## 建议操作

1. 向紧急联系人发送"我想念您"的消息
2. 与到期的内圈联系人安排通话
3. 参与即将到期联系人的内容

## 阈值

- 内圈: 每2周
- 活跃: 每月
- 网络: 每2个月
- 休眠: 每季度检查以重新激活
"""

    return output

if __name__ == '__main__':
    print(generate_report())
