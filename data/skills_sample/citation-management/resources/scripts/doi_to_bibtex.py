#!/usr/bin/env python3
"""
DOI转BibTeX转换器
使用CrossRef API将DOI快速转换为BibTeX格式的实用工具。
"""

import sys
import requests
import argparse
import time
import json
from typing import Optional, List

class DOIConverter:
    """使用CrossRef API将DOI转换为BibTeX条目。"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'DOIConverter/1.0 (引文管理工具; mailto:support@example.com)'
        })
    
    def doi_to_bibtex(self, doi: str) -> Optional[str]:
        """
        将单个DOI转换为BibTeX格式。
        
        参数:
            doi: 数字对象标识符
            
        返回:
            BibTeX字符串，如果转换失败则返回None
        """
        # 清理DOI（如果存在URL前缀则移除）
        doi = doi.strip()
        if doi.startswith('https://doi.org/'):
            doi = doi.replace('https://doi.org/', '')
        elif doi.startswith('http://doi.org/'):
            doi = doi.replace('http://doi.org/', '')
        elif doi.startswith('doi:'):
            doi = doi.replace('doi:', '')
        
        # 从CrossRef内容协商请求BibTeX
        url = f'https://doi.org/{doi}'
        headers = {
            'Accept': 'application/x-bibtex',
            'User-Agent': 'DOIConverter/1.0 (引文管理工具)'
        }
        
        try:
            response = self.session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                bibtex = response.text.strip()
                # CrossRef有时返回@data类型的条目，转换为@misc
                if bibtex.startswith('@data{'):
                    bibtex = bibtex.replace('@data{', '@misc{', 1)
                return bibtex
            elif response.status_code == 404:
                print(f'错误: 未找到DOI: {doi}', file=sys.stderr)
                return None
            else:
                print(f'错误: 无法检索{doi}的BibTeX（状态 {response.status_code}）', file=sys.stderr)
                return None
                
        except requests.exceptions.Timeout:
            print(f'错误: DOI请求超时: {doi}', file=sys.stderr)
            return None
        except requests.exceptions.RequestException as e:
            print(f'错误: {doi}的请求失败: {e}', file=sys.stderr)
            return None
    
    def convert_multiple(self, dois: List[str], delay: float = 0.5) -> List[str]:
        """
        将多个DOI转换为BibTeX。
        
        参数:
            dois: DOI列表
            delay: 请求间延迟（秒），用于速率限制
            
        返回:
            BibTeX条目列表（不包括失败的转换）
        """
        bibtex_entries = []
        
        for i, doi in enumerate(dois):
            print(f'正在转换DOI {i+1}/{len(dois)}: {doi}', file=sys.stderr)
            bibtex = self.doi_to_bibtex(doi)
            
            if bibtex:
                bibtex_entries.append(bibtex)
            
            # 速率限制
            if i < len(dois) - 1:  # 最后一个请求后不延迟
                time.sleep(delay)
        
        return bibtex_entries


def main():
    """命令行接口。"""
    parser = argparse.ArgumentParser(
        description='使用CrossRef API将DOI转换为BibTeX格式',
        epilog='示例: python doi_to_bibtex.py 10.1038/s41586-021-03819-2'
    )
    
    parser.add_argument(
        'dois',
        nargs='*',
        help='要转换的DOI（可提供多个）'
    )
    
    parser.add_argument(
        '-i', '--input',
        help='包含DOI的输入文件（每行一个）'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='BibTeX输出文件（默认：stdout）'
    )
    
    parser.add_argument(
        '--delay',
        type=float,
        default=0.5,
        help='请求间延迟（秒）（默认：0.5）'
    )
    
    parser.add_argument(
        '--format',
        choices=['bibtex', 'json'],
        default='bibtex',
        help='输出格式（默认：bibtex）'
    )
    
    args = parser.parse_args()
    
    # 从命令行和/或文件收集DOI
    dois = []
    
    if args.dois:
        dois.extend(args.dois)
    
    if args.input:
        try:
            with open(args.input, 'r', encoding='utf-8') as f:
                file_dois = [line.strip() for line in f if line.strip()]
                dois.extend(file_dois)
        except FileNotFoundError:
            print(f'错误: 未找到输入文件: {args.input}', file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f'读取输入文件时出错: {e}', file=sys.stderr)
            sys.exit(1)
    
    if not dois:
        parser.print_help()
        sys.exit(1)
    
    # 转换DOI
    converter = DOIConverter()
    
    if len(dois) == 1:
        bibtex = converter.doi_to_bibtex(dois[0])
        if bibtex:
            bibtex_entries = [bibtex]
        else:
            sys.exit(1)
    else:
        bibtex_entries = converter.convert_multiple(dois, delay=args.delay)
    
    if not bibtex_entries:
        print('错误: 没有成功转换', file=sys.stderr)
        sys.exit(1)
    
    # 格式化输出
    if args.format == 'bibtex':
        output = '\n\n'.join(bibtex_entries) + '\n'
    else:  # json
        output = json.dumps({
            'count': len(bibtex_entries),
            'entries': bibtex_entries
        }, indent=2)
    
    # 写入输出
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
            print(f'成功将{len(bibtex_entries)}个条目写入 {args.output}', file=sys.stderr)
        except Exception as e:
            print(f'写入输出文件时出错: {e}', file=sys.stderr)
            sys.exit(1)
    else:
        print(output)
    
    # 摘要
    if len(dois) > 1:
        success_rate = len(bibtex_entries) / len(dois) * 100
        print(f'\n转换了 {len(bibtex_entries)}/{len(dois)} 个DOI ({success_rate:.1f}%)', file=sys.stderr)


if __name__ == '__main__':
    main()
