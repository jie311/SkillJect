#!/usr/bin/env python3
"""
引文验证工具
验证BibTeX文件的准确性、完整性和格式合规性。
"""

import sys
import re
import requests
import argparse
import json
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

class CitationValidator:
    """验证BibTeX条目的错误和不一致性。"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CitationValidator/1.0 (引文管理工具)'
        })
        
        # 按条目类型分类的必填字段
        self.required_fields = {
            'article': ['author', 'title', 'journal', 'year'],
            'book': ['title', 'publisher', 'year'],  # author 或 editor
            'inproceedings': ['author', 'title', 'booktitle', 'year'],
            'incollection': ['author', 'title', 'booktitle', 'publisher', 'year'],
            'phdthesis': ['author', 'title', 'school', 'year'],
            'mastersthesis': ['author', 'title', 'school', 'year'],
            'techreport': ['author', 'title', 'institution', 'year'],
            'misc': ['title', 'year']
        }
        
        # 推荐字段
        self.recommended_fields = {
            'article': ['volume', 'pages', 'doi'],
            'book': ['isbn'],
            'inproceedings': ['pages'],
        }
    
    def parse_bibtex_file(self, filepath: str) -> List[Dict]:
        """
        解析BibTeX文件并提取条目。
        
        参数:
            filepath: BibTeX文件路径
            
        返回:
            条目字典列表
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f'读取文件时出错: {e}', file=sys.stderr)
            return []
        
        entries = []
        
        # 匹配BibTeX条目
        pattern = r'@(\w+)\s*\{\s*([^,\s]+)\s*,(.*?)\n\}'
        matches = re.finditer(pattern, content, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            entry_type = match.group(1).lower()
            citation_key = match.group(2).strip()
            fields_text = match.group(3)
            
            # 解析字段
            fields = {}
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
                'fields': fields,
                'raw': match.group(0)
            })
        
        return entries
    
    def validate_entry(self, entry: Dict) -> Tuple[List[Dict], List[Dict]]:
        """
        验证单个BibTeX条目。
        
        参数:
            entry: 条目字典
            
        返回:
            (错误, 警告)元组
        """
        errors = []
        warnings = []
        
        entry_type = entry['type']
        key = entry['key']
        fields = entry['fields']
        
        # 检查必填字段
        if entry_type in self.required_fields:
            for req_field in self.required_fields[entry_type]:
                if req_field not in fields or not fields[req_field]:
                    # 特殊情况: book 可以有 author 或 editor
                    if entry_type == 'book' and req_field == 'author':
                        if 'editor' not in fields or not fields['editor']:
                            errors.append({
                                'type': 'missing_required_field',
                                'field': 'author or editor',
                                'severity': 'high',
                                'message': f'条目 {key}: 缺少必填字段"author"或"editor"'
                            })
                    else:
                        errors.append({
                            'type': 'missing_required_field',
                            'field': req_field,
                            'severity': 'high',
                            'message': f'条目 {key}: 缺少必填字段"{req_field}"'
                        })
        
        # 检查推荐字段
        if entry_type in self.recommended_fields:
            for rec_field in self.recommended_fields[entry_type]:
                if rec_field not in fields or not fields[rec_field]:
                    warnings.append({
                        'type': 'missing_recommended_field',
                        'field': rec_field,
                        'severity': 'medium',
                        'message': f'条目 {key}: 缺少推荐字段"{rec_field}"'
                    })
        
        # 验证年份
        if 'year' in fields:
            year = fields['year']
            if not re.match(r'^\d{4}$', year):
                errors.append({
                    'type': 'invalid_year',
                    'field': 'year',
                    'value': year,
                    'severity': 'high',
                    'message': f'条目 {key}: 无效的年份格式"{year}"（应为4位数字）'
                })
            elif int(year) < 1600 or int(year) > 2030:
                warnings.append({
                    'type': 'suspicious_year',
                    'field': 'year',
                    'value': year,
                    'severity': 'medium',
                    'message': f'条目 {key}: 可疑的年份"{year}"（超出合理范围）'
                })
        
        # 验证DOI格式
        if 'doi' in fields:
            doi = fields['doi']
            if not re.match(r'^10\.\d{4,}/[^\s]+$', doi):
                warnings.append({
                    'type': 'invalid_doi_format',
                    'field': 'doi',
                    'value': doi,
                    'severity': 'medium',
                    'message': f'条目 {key}: 无效的DOI格式"{doi}"'
                })
        
        # 检查页码中的单个连字符（应为 --）
        if 'pages' in fields:
            pages = fields['pages']
            if re.search(r'\d-\d', pages) and '--' not in pages:
                warnings.append({
                    'type': 'page_range_format',
                    'field': 'pages',
                    'value': pages,
                    'severity': 'low',
                    'message': f'条目 {key}: 页码范围使用单个连字符，应使用 --（en破折号）'
                })
        
        # 检查作者格式
        if 'author' in fields:
            author = fields['author']
            if ';' in author or '&' in author:
                errors.append({
                    'type': 'invalid_author_format',
                    'field': 'author',
                    'severity': 'high',
                    'message': f'条目 {key}: 作者应使用" and "分隔，而不是";"或"&"'
                })
        
        return errors, warnings
    
    def verify_doi(self, doi: str) -> Tuple[bool, Optional[Dict]]:
        """
        验证DOI是否正确解析并获取元数据。
        
        参数:
            doi: 数字对象标识符
            
        返回:
            (is_valid, metadata)元组
        """
        try:
            url = f'https://doi.org/{doi}'
            response = self.session.head(url, timeout=10, allow_redirects=True)
            
            if response.status_code < 400:
                # DOI解析，现在从CrossRef获取元数据
                crossref_url = f'https://api.crossref.org/works/{doi}'
                metadata_response = self.session.get(crossref_url, timeout=10)
                
                if metadata_response.status_code == 200:
                    data = metadata_response.json()
                    message = data.get('message', {})
                    
                    # 提取关键元数据
                    metadata = {
                        'title': message.get('title', [''])[0],
                        'year': self._extract_year_crossref(message),
                        'authors': self._format_authors_crossref(message.get('author', [])),
                    }
                    return True, metadata
                else:
                    return True, None  # DOI解析但没有CrossRef元数据
            else:
                return False, None
                
        except Exception:
            return False, None
    
    def detect_duplicates(self, entries: List[Dict]) -> List[Dict]:
        """
        检测重复条目。
        
        参数:
            entries: 条目字典列表
            
        返回:
            重复组列表
        """
        duplicates = []
        
        # 检查重复的DOI
        doi_map = defaultdict(list)
        for entry in entries:
            doi = entry['fields'].get('doi', '').strip()
            if doi:
                doi_map[doi].append(entry['key'])
        
        for doi, keys in doi_map.items():
            if len(keys) > 1:
                duplicates.append({
                    'type': 'duplicate_doi',
                    'doi': doi,
                    'entries': keys,
                    'severity': 'high',
                    'message': f'发现重复的DOI {doi}，位于条目: {", ".join(keys)}'
                })
        
        # 检查重复的引用键
        key_counts = defaultdict(int)
        for entry in entries:
            key_counts[entry['key']] += 1
        
        for key, count in key_counts.items():
            if count > 1:
                duplicates.append({
                    'type': 'duplicate_key',
                    'key': key,
                    'count': count,
                    'severity': 'high',
                    'message': f'引用键"{key}"出现{count}次'
                })
        
        # 检查相似的标题（可能的重复）
        titles = {}
        for entry in entries:
            title = entry['fields'].get('title', '').lower()
            title = re.sub(r'[^\w\s]', '', title)  # 移除标点符号
            title = ' '.join(title.split())  # 标准化空白字符
            
            if title:
                if title in titles:
                    duplicates.append({
                        'type': 'similar_title',
                        'entries': [titles[title], entry['key']],
                        'severity': 'medium',
                        'message': f'可能的重复: "{titles[title]}"和"{entry["key"]}"具有相同的标题'
                    })
                else:
                    titles[title] = entry['key']
        
        return duplicates
    
    def validate_file(self, filepath: str, check_dois: bool = False) -> Dict:
        """
        验证整个BibTeX文件。
        
        参数:
            filepath: BibTeX文件路径
            check_dois: 是否验证DOI（较慢）
            
        返回:
            验证报告字典
        """
        print(f'正在解析 {filepath}...', file=sys.stderr)
        entries = self.parse_bibtex_file(filepath)
        
        if not entries:
            return {
                'total_entries': 0,
                'errors': [],
                'warnings': [],
                'duplicates': []
            }
        
        print(f'找到 {len(entries)} 个条目', file=sys.stderr)
        
        all_errors = []
        all_warnings = []
        
        # 验证每个条目
        for i, entry in enumerate(entries):
            print(f'正在验证条目 {i+1}/{len(entries)}: {entry["key"]}', file=sys.stderr)
            errors, warnings = self.validate_entry(entry)
            
            for error in errors:
                error['entry'] = entry['key']
                all_errors.append(error)
            
            for warning in warnings:
                warning['entry'] = entry['key']
                all_warnings.append(warning)
        
        # 检查重复项
        print('正在检查重复项...', file=sys.stderr)
        duplicates = self.detect_duplicates(entries)
        
        # 如果需要则验证DOI
        doi_errors = []
        if check_dois:
            print('正在验证DOI...', file=sys.stderr)
            for i, entry in enumerate(entries):
                doi = entry['fields'].get('doi', '')
                if doi:
                    print(f'正在验证DOI {i+1}: {doi}', file=sys.stderr)
                    is_valid, metadata = self.verify_doi(doi)
                    
                    if not is_valid:
                        doi_errors.append({
                            'type': 'invalid_doi',
                            'entry': entry['key'],
                            'doi': doi,
                            'severity': 'high',
                            'message': f'条目 {entry["key"]}: DOI无法解析: {doi}'
                        })
        
        all_errors.extend(doi_errors)
        
        return {
            'filepath': filepath,
            'total_entries': len(entries),
            'valid_entries': len(entries) - len([e for e in all_errors if e['severity'] == 'high']),
            'errors': all_errors,
            'warnings': all_warnings,
            'duplicates': duplicates
        }
    
    def _extract_year_crossref(self, message: Dict) -> str:
        """从CrossRef消息中提取年份。"""
        date_parts = message.get('published-print', {}).get('date-parts', [[]])
        if not date_parts or not date_parts[0]:
            date_parts = message.get('published-online', {}).get('date-parts', [[]])
        
        if date_parts and date_parts[0]:
            return str(date_parts[0][0])
        return ''
    
    def _format_authors_crossref(self, authors: List[Dict]) -> str:
        """格式化来自CrossRef的作者列表。"""
        if not authors:
            return ''
        
        formatted = []
        for author in authors[:3]:  # 前3位作者
            given = author.get('given', '')
            family = author.get('family', '')
            if family:
                formatted.append(f'{family}, {given}' if given else family)
        
        if len(authors) > 3:
            formatted.append('et al.')
        
        return ', '.join(formatted)


def main():
    """命令行接口。"""
    parser = argparse.ArgumentParser(
        description='验证BibTeX文件的错误和不一致性',
        epilog='示例: python validate_citations.py references.bib'
    )
    
    parser.add_argument(
        'file',
        help='要验证的BibTeX文件'
    )
    
    parser.add_argument(
        '--check-dois',
        action='store_true',
        help='验证DOI是否正确解析（较慢）'
    )
    
    parser.add_argument(
        '--auto-fix',
        action='store_true',
        help='尝试自动修复常见问题（尚未实现）'
    )
    
    parser.add_argument(
        '--report',
        help='JSON验证报告的输出文件'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='显示详细输出'
    )
    
    args = parser.parse_args()
    
    # 验证文件
    validator = CitationValidator()
    report = validator.validate_file(args.file, check_dois=args.check_dois)
    
    # 打印摘要
    print('\n' + '='*60)
    print('引文验证报告')
    print('='*60)
    print(f'\n文件: {args.file}')
    print(f'总条目数: {report["total_entries"]}')
    print(f'有效条目数: {report["valid_entries"]}')
    print(f'错误: {len(report["errors"])}')
    print(f'警告: {len(report["warnings"])}')
    print(f'重复: {len(report["duplicates"])}')
    
    # 打印错误
    if report['errors']:
        print('\n' + '-'*60)
        print('错误（必须修复）:')
        print('-'*60)
        for error in report['errors']:
            print(f'\n{error["message"]}')
            if args.verbose:
                print(f'  类型: {error["type"]}')
                print(f'  严重程度: {error["severity"]}')
    
    # 打印警告
    if report['warnings'] and args.verbose:
        print('\n' + '-'*60)
        print('警告（应该修复）:')
        print('-'*60)
        for warning in report['warnings']:
            print(f'\n{warning["message"]}')
    
    # 打印重复项
    if report['duplicates']:
        print('\n' + '-'*60)
        print('重复项:')
        print('-'*60)
        for dup in report['duplicates']:
            print(f'\n{dup["message"]}')
    
    # 保存报告
    if args.report:
        with open(args.report, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        print(f'\n详细报告已保存到: {args.report}')
    
    # 如果有错误则返回错误代码
    if report['errors']:
        sys.exit(1)


if __name__ == '__main__':
    main()
