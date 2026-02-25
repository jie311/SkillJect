#!/usr/bin/env python3
"""
Google 学术搜索工具
搜索 Google 学术并导出结果。

注意：此脚本需要 'scholarly' 库。
安装方式: pip install scholarly
"""

import sys
import argparse
import json
import time
import random
from typing import List, Dict, Optional

try:
    from scholarly import scholarly, ProxyGenerator
    SCHOLARLY_AVAILABLE = True
except ImportError:
    SCHOLARLY_AVAILABLE = False
    print('警告: 未安装 scholarly 库。安装方式: pip install scholarly', file=sys.stderr)

class GoogleScholarSearcher:
    """使用 scholarly 库搜索 Google 学术。"""
    
    def __init__(self, use_proxy: bool = False):
        """
        初始化搜索器。
        
        参数：
            use_proxy：使用免费代理（有助于避免速率限制）
        """
        if not SCHOLARLY_AVAILABLE:
            raise ImportError('需要 scholarly 库。安装方式: pip install scholarly')
        
        # 如果有请求，设置代理
        if use_proxy:
            try:
                pg = ProxyGenerator()
                pg.FreeProxies()
                scholarly.use_proxy(pg)
                print('正在使用免费代理', file=sys.stderr)
            except Exception as e:
                print(f'警告: 无法设置代理: {e}', file=sys.stderr)
    
    def search(self, query: str, max_results: int = 50,
               year_start: Optional[int] = None, year_end: Optional[int] = None,
               sort_by: str = 'relevance') -> List[Dict]:
        """
        搜索 Google 学术。
        
        参数：
            query：搜索查询
            max_results：最大结果数
            year_start：起始年份过滤器
            year_end：结束年份过滤器
            sort_by：排序顺序（'relevance' 或 'citations'）
            
        返回：
            结果字典列表
        """
        if not SCHOLARLY_AVAILABLE:
            print('错误: 未安装 scholarly 库', file=sys.stderr)
            return []
        
        print(f'正在搜索 Google 学术: {query}', file=sys.stderr)
        print(f'最大结果数: {max_results}', file=sys.stderr)
        
        results = []
        
        try:
            # 执行搜索
            search_query = scholarly.search_pubs(query)
            
            for i, result in enumerate(search_query):
                if i >= max_results:
                    break
                
                print(f'已检索 {i+1}/{max_results}', file=sys.stderr)
                
                # 提取元数据
                metadata = {
                    'title': result.get('bib', {}).get('title', ''),
                    'authors': ', '.join(result.get('bib', {}).get('author', [])),
                    'year': result.get('bib', {}).get('pub_year', ''),
                    'venue': result.get('bib', {}).get('venue', ''),
                    'abstract': result.get('bib', {}).get('abstract', ''),
                    'citations': result.get('num_citations', 0),
                    'url': result.get('pub_url', ''),
                    'eprint_url': result.get('eprint_url', ''),
                }
                
                # 按年份过滤
                if year_start or year_end:
                    try:
                        pub_year = int(metadata['year']) if metadata['year'] else 0
                        if year_start and pub_year < year_start:
                            continue
                        if year_end and pub_year > year_end:
                            continue
                    except ValueError:
                        pass
                
                results.append(metadata)
                
                # 速率限制以避免被封禁
                time.sleep(random.uniform(2, 5))
            
        except Exception as e:
            print(f'搜索过程中出错: {e}', file=sys.stderr)
        
        # 如果有请求则排序
        if sort_by == 'citations' and results:
            results.sort(key=lambda x: x.get('citations', 0), reverse=True)
        
        return results
    
    def metadata_to_bibtex(self, metadata: Dict) -> str:
        """将元数据转换为 BibTeX 格式。"""
        # 生成引用键
        if metadata.get('authors'):
            first_author = metadata['authors'].split(',')[0].strip()
            last_name = first_author.split()[-1] if first_author else 'Unknown'
        else:
            last_name = 'Unknown'
        
        year = metadata.get('year', 'XXXX')
        
        # 从标题获取关键词
        import re
        title = metadata.get('title', '')
        words = re.findall(r'\b[a-zA-Z]{4,}\b', title)
        keyword = words[0].lower() if words else 'paper'
        
        citation_key = f'{last_name}{year}{keyword}'
        
        # 确定条目类型（根据期刊猜测）
        venue = metadata.get('venue', '').lower()
        if 'proceedings' in venue or 'conference' in venue:
            entry_type = 'inproceedings'
            venue_field = 'booktitle'
        else:
            entry_type = 'article'
            venue_field = 'journal'
        
        # 构建 BibTeX
        lines = [f'@{entry_type}{{{citation_key},']
        
        # 转换作者格式
        if metadata.get('authors'):
            authors = metadata['authors'].replace(',', ' and')
            lines.append(f'  author  = {{{authors}}},')
        
        if metadata.get('title'):
            lines.append(f'  title   = {{{metadata["title"]}}},')
        
        if metadata.get('venue'):
            lines.append(f'  {venue_field} = {{{metadata["venue"]}}},')
        
        if metadata.get('year'):
            lines.append(f'  year    = {{{metadata["year"]}}},')
        
        if metadata.get('url'):
            lines.append(f'  url     = {{{metadata["url"]}}},')
        
        if metadata.get('citations'):
            lines.append(f'  note    = {{引用次数: {metadata["citations"]}}},')
        
        # 删除尾随逗号
        if lines[-1].endswith(','):
            lines[-1] = lines[-1][:-1]
        
        lines.append('}')
        
        return '\n'.join(lines)


def main():
    """命令行界面。"""
    parser = argparse.ArgumentParser(
        description='搜索 Google 学术（需要 scholarly 库）',
        epilog='示例: python search_google_scholar.py "机器学习" --limit 50'
    )
    
    parser.add_argument(
        'query',
        help='搜索查询'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='最大结果数（默认: 50）'
    )
    
    parser.add_argument(
        '--year-start',
        type=int,
        help='起始年份过滤器'
    )
    
    parser.add_argument(
        '--year-end',
        type=int,
        help='结束年份过滤器'
    )
    
    parser.add_argument(
        '--sort-by',
        choices=['relevance', 'citations'],
        default='relevance',
        help='排序顺序（默认: relevance）'
    )
    
    parser.add_argument(
        '--use-proxy',
        action='store_true',
        help='使用免费代理避免速率限制'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='输出文件（默认: 标准输出）'
    )
    
    parser.add_argument(
        '--format',
        choices=['json', 'bibtex'],
        default='json',
        help='输出格式（默认: json）'
    )
    
    args = parser.parse_args()
    
    if not SCHOLARLY_AVAILABLE:
        print('\n错误: 未安装 scholarly 库', file=sys.stderr)
        print('安装方式: pip install scholarly', file=sys.stderr)
        print('\n或者，使用 PubMed 搜索生物医学文献:', file=sys.stderr)
        print('  python search_pubmed.py "您的查询"', file=sys.stderr)
        sys.exit(1)
    
    # 搜索
    searcher = GoogleScholarSearcher(use_proxy=args.use_proxy)
    results = searcher.search(
        args.query,
        max_results=args.limit,
        year_start=args.year_start,
        year_end=args.year_end,
        sort_by=args.sort_by
    )
    
    if not results:
        print('未找到结果', file=sys.stderr)
        sys.exit(1)
    
    # 格式化输出
    if args.format == 'json':
        output = json.dumps({
            'query': args.query,
            'count': len(results),
            'results': results
        }, indent=2)
    else:  # bibtex
        bibtex_entries = [searcher.metadata_to_bibtex(r) for r in results]
        output = '\n\n'.join(bibtex_entries) + '\n'
    
    # 写入输出
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f'已写入 {len(results)} 个结果至 {args.output}', file=sys.stderr)
    else:
        print(output)
    
    print(f'\n检索了 {len(results)} 个结果', file=sys.stderr)


if __name__ == '__main__':
    main()
