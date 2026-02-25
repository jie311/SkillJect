#!/usr/bin/env python3
"""
BibTeX 格式化和清理工具
格式化、清理、排序和去重 BibTeX 文件。
"""

import sys
import re
import argparse
from typing import List, Dict, Tuple
from collections import OrderedDict

class BibTeXFormatter:
    """格式化和清理 BibTeX 条目。"""
    
    def __init__(self):
        # 标准字段顺序以提高可读性
        self.field_order = [
            'author', 'editor', 'title', 'booktitle', 'journal',
            'year', 'month', 'volume', 'number', 'pages',
            'publisher', 'address', 'edition', 'series',
            'school', 'institution', 'organization',
            'howpublished', 'doi', 'url', 'isbn', 'issn',
            'note', 'abstract', 'keywords'
        ]
    
    def parse_bibtex_file(self, filepath: str) -> List[Dict]:
        """
        解析 BibTeX 文件并提取条目。
        
        参数：
            filepath：BibTeX 文件路径
        
        返回：
            条目字典列表
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f'读取文件时出错: {e}', file=sys.stderr)
            return []
        
        entries = []
        
        # 匹配 BibTeX 条目
        pattern = r'@(\w+)\s*\{\s*([^,\s]+)\s*,(.*?)\n\}'
        matches = re.finditer(pattern, content, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            entry_type = match.group(1).lower()
            citation_key = match.group(2).strip()
            fields_text = match.group(3)
            
            # 解析字段
            fields = OrderedDict()
            field_pattern = r'(\w+)\s*=\s*\{([^}]*)\}|(\w+)\s*=\s*"([^"]*)"'
            field_matches = re.finditer(field_pattern, fields_text)
            
            for field_match in field_matches:
                if field_match.group(1):
                    field_name = field_match.group(1).lower()
                    field_value = field_match.group(2)
                else:
                    field_name = field_match.group(3).lower()
                    field_value = field_match.group(4)
                
                fields[field_name] = field_value.strip()
            
            entries.append({
                'type': entry_type,
                'key': citation_key,
                'fields': fields
            })
        
        return entries
    
    def format_entry(self, entry: Dict) -> str:
        """
        格式化单个 BibTeX 条目。
        
        参数：
            entry：条目字典
        
        返回：
            格式化的 BibTeX 字符串
        """
        lines = [f'@{entry["type"]}{{{entry["key"]},']
        
        # 按标准顺序排列字段
        ordered_fields = OrderedDict()
        
        # 按标准顺序添加字段
        for field_name in self.field_order:
            if field_name in entry['fields']:
                ordered_fields[field_name] = entry['fields'][field_name]
        
        # 添加任何剩余字段
        for field_name, field_value in entry['fields'].items():
            if field_name not in ordered_fields:
                ordered_fields[field_name] = field_value
        
        # 格式化每个字段
        max_field_len = max(len(f) for f in ordered_fields.keys()) if ordered_fields else 0
        
        for field_name, field_value in ordered_fields.items():
            # 填充字段名以对齐
            padded_field = field_name.ljust(max_field_len)
            lines.append(f'  {padded_field} = {{{field_value}}},')
        
        # 从最后一个字段删除尾随逗号
        if lines[-1].endswith(','):
            lines[-1] = lines[-1][:-1]
        
        lines.append('}')
        
        return '\n'.join(lines)
    
    def fix_common_issues(self, entry: Dict) -> Dict:
        """
        修复条目中的常见格式问题。
        
        参数：
            entry：条目字典
        
        返回：
            修复后的条目字典
        """
        fixed = entry.copy()
        fields = fixed['fields'].copy()
        
        # 修复页码范围（单个连字符改为双连字符）
        if 'pages' in fields:
            pages = fields['pages']
            # 如果是范围，将单个连字符替换为双连字符
            if re.search(r'\d-\d', pages) and '--' not in pages:
                pages = re.sub(r'(\d)-(\d)', r'\1--\2', pages)
                fields['pages'] = pages
        
        # 从页码中删除 "pp."
        if 'pages' in fields:
            pages = fields['pages']
            pages = re.sub(r'^pp\.\s*', '', pages, flags=re.IGNORECASE)
            fields['pages'] = pages
        
        # 修复 DOI（如果存在，删除 URL 前缀）
        if 'doi' in fields:
            doi = fields['doi']
            doi = doi.replace('https://doi.org/', '')
            doi = doi.replace('http://doi.org/', '')
            doi = doi.replace('doi:', '')
            fields['doi'] = doi
        
        # 修复作者分隔符（分号或 & 符号改为 'and'）
        if 'author' in fields:
            author = fields['author']
            author = author.replace(';', ' and')
            author = author.replace(' & ', ' and ')
            # 清理多个 'and'
            author = re.sub(r'\s+and\s+and\s+', ' and ', author)
            fields['author'] = author
        
        fixed['fields'] = fields
        return fixed
    
    def deduplicate_entries(self, entries: List[Dict]) -> List[Dict]:
        """
        基于 DOI 或引用键删除重复条目。
        
        参数：
            entries：条目字典列表
        
        返回：
            唯一条目列表
        """
        seen_dois = set()
        seen_keys = set()
        unique_entries = []
        
        for entry in entries:
            doi = entry['fields'].get('doi', '').strip()
            key = entry['key']
            
            # 首先检查 DOI（更可靠）
            if doi:
                if doi in seen_dois:
                    print(f'发现重复的 DOI: {doi} (跳过 {key})', file=sys.stderr)
                    continue
                seen_dois.add(doi)
            
            # 检查引用键
            if key in seen_keys:
                print(f'发现重复的引用键: {key} (跳过)', file=sys.stderr)
                continue
            seen_keys.add(key)
            
            unique_entries.append(entry)
        
        return unique_entries
    
    def sort_entries(self, entries: List[Dict], sort_by: str = 'key', descending: bool = False) -> List[Dict]:
        """
        按指定字段排序条目。
        
        参数：
            entries：条目字典列表
            sort_by：排序字段（'key'、'year'、'author'、'title'）
            descending：降序排序
        
        返回：
            排序后的条目列表
        """
        def get_sort_key(entry: Dict) -> str:
            if sort_by == 'key':
                return entry['key'].lower()
            elif sort_by == 'year':
                year = entry['fields'].get('year', '9999')
                return year
            elif sort_by == 'author':
                author = entry['fields'].get('author', 'ZZZ')
                # 获取第一作者的姓氏
                if ',' in author:
                    return author.split(',')[0].lower()
                else:
                    return author.split()[0].lower() if author else 'zzz'
            elif sort_by == 'title':
                return entry['fields'].get('title', '').lower()
            else:
                return entry['key'].lower()
        
        return sorted(entries, key=get_sort_key, reverse=descending)
    
    def format_file(self, filepath: str, output: str = None,
                   deduplicate: bool = False, sort_by: str = None,
                   descending: bool = False, fix_issues: bool = True) -> None:
        """
        格式化整个 BibTeX 文件。
        
        参数：
            filepath：输入 BibTeX 文件
            output：输出文件（None 表示原位）
            deduplicate：删除重复项
            sort_by：排序字段
            descending：降序排序
            fix_issues：修复常见格式问题
        """
        print(f'正在解析 {filepath}...', file=sys.stderr)
        entries = self.parse_bibtex_file(filepath)
        
        if not entries:
            print('未找到条目', file=sys.stderr)
            return
        
        print(f'找到 {len(entries)} 个条目', file=sys.stderr)
        
        # 修复常见问题
        if fix_issues:
            print('正在修复常见问题...', file=sys.stderr)
            entries = [self.fix_common_issues(e) for e in entries]
        
        # 去重
        if deduplicate:
            print('正在删除重复项...', file=sys.stderr)
            original_count = len(entries)
            entries = self.deduplicate_entries(entries)
            removed = original_count - len(entries)
            if removed > 0:
                print(f'删除了 {removed} 个重复项', file=sys.stderr)
        
        # 排序
        if sort_by:
            print(f'正在按 {sort_by} 排序...', file=sys.stderr)
            entries = self.sort_entries(entries, sort_by, descending)
        
        # 格式化条目
        print('正在格式化条目...', file=sys.stderr)
        formatted_entries = [self.format_entry(e) for e in entries]
        
        # 写入输出
        output_content = '\n\n'.join(formatted_entries) + '\n'
        
        output_file = output or filepath
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(output_content)
            print(f'成功写入 {len(entries)} 个条目至 {output_file}', file=sys.stderr)
        except Exception as e:
            print(f'写入文件时出错: {e}', file=sys.stderr)
            sys.exit(1)


def main():
    """命令行界面。"""
    parser = argparse.ArgumentParser(
        description='格式化、清理、排序和去重 BibTeX 文件',
        epilog='示例: python format_bibtex.py references.bib --deduplicate --sort year'
    )
    
    parser.add_argument(
        'file',
        help='要格式化的 BibTeX 文件'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='输出文件（默认: 覆盖输入文件）'
    )
    
    parser.add_argument(
        '--deduplicate',
        action='store_true',
        help='删除重复条目'
    )
    
    parser.add_argument(
        '--sort',
        choices=['key', 'year', 'author', 'title'],
        help='按字段排序'
    )
    
    parser.add_argument(
        '--descending',
        action='store_true',
        help='降序排序'
    )
    
    parser.add_argument(
        '--no-fix',
        action='store_true',
        help='不修复常见问题'
    )
    
    args = parser.parse_args()
    
    # 格式化文件
    formatter = BibTeXFormatter()
    formatter.format_file(
        args.file,
        output=args.output,
        deduplicate=args.deduplicate,
        sort_by=args.sort,
        descending=args.descending,
        fix_issues=not args.no_fix
    )


if __name__ == '__main__':
    main()
