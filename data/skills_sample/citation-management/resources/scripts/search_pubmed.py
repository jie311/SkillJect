#!/usr/bin/env python3
"""
PubMed 搜索工具
使用 E-utilities API 搜索 PubMed 并导出结果。
"""

import sys
import os
import requests
import argparse
import json
import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from datetime import datetime

class PubMedSearcher:
    """使用 NCBI E-utilities API 搜索 PubMed。"""
    
    def __init__(self, api_key: Optional[str] = None, email: Optional[str] = None):
        """
        初始化搜索器。
        
        参数：
            api_key：NCBI API 密钥（可选但建议）
            email：Entrez 的电子邮件（可选但建议）
        """
        self.api_key = api_key or os.getenv('NCBI_API_KEY', '')
        self.email = email or os.getenv('NCBI_EMAIL', '')
        self.base_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
        self.session = requests.Session()
        
        # 速率限制
        self.delay = 0.11 if self.api_key else 0.34  # 使用密钥 10 次/秒，无密钥 3 次/秒
    
    def search(self, query: str, max_results: int = 100,
               date_start: Optional[str] = None, date_end: Optional[str] = None,
               publication_types: Optional[List[str]] = None) -> List[str]:
        """
        搜索 PubMed 并返回 PMID。
        
        参数：
            query：搜索查询
            max_results：最大结果数
            date_start：起始日期（YYYY/MM/DD 或 YYYY）
            date_end：结束日期（YYYY/MM/DD 或 YYYY）
            publication_types：要过滤的发表类型列表
        
        返回：
            PMID 列表
        """
        # 使用过滤器构建查询
        full_query = query
        
        # 添加日期范围
        if date_start or date_end:
            start = date_start or '1900'
            end = date_end or datetime.now().strftime('%Y')
            full_query += f' AND {start}:{end}[Publication Date]'
        
        # 添加发表类型
        if publication_types:
            pub_type_query = ' OR '.join([f'"{pt}"[Publication Type]' for pt in publication_types])
            full_query += f' AND ({pub_type_query})'
        
        print(f'正在搜索 PubMed: {full_query}', file=sys.stderr)
        
        # ESearch 获取 PMID
        esearch_url = self.base_url + 'esearch.fcgi'
        params = {
            'db': 'pubmed',
            'term': full_query,
            'retmax': max_results,
            'retmode': 'json'
        }
        
        if self.email:
            params['email'] = self.email
        if self.api_key:
            params['api_key'] = self.api_key
        
        try:
            response = self.session.get(esearch_url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            pmids = data['esearchresult']['idlist']
            count = int(data['esearchresult']['count'])
            
            print(f'找到 {count} 个结果，正在检索 {len(pmids)} 个', file=sys.stderr)
            
            return pmids
            
        except Exception as e:
            print(f'搜索 PubMed 时出错: {e}', file=sys.stderr)
            return []
    
    def fetch_metadata(self, pmids: List[str]) -> List[Dict]:
        """
        获取 PMID 的元数据。
        
        参数：
            pmids：PubMed ID 列表
        
        返回：
            元数据字典列表
        """
        if not pmids:
            return []
        
        metadata_list = []
        
        # 分批获取（每批 200 个）
        batch_size = 200
        for i in range(0, len(pmids), batch_size):
            batch = pmids[i:i+batch_size]
            print(f'正在获取 PMID {i+1}-{min(i+batch_size, len(pmids))} 的元数据...', file=sys.stderr)
            
            efetch_url = self.base_url + 'efetch.fcgi'
            params = {
                'db': 'pubmed',
                'id': ','.join(batch),
                'retmode': 'xml',
                'rettype': 'abstract'
            }
            
            if self.email:
                params['email'] = self.email
            if self.api_key:
                params['api_key'] = self.api_key
            
            try:
                response = self.session.get(efetch_url, params=params, timeout=60)
                response.raise_for_status()
                
                # 解析 XML
                root = ET.fromstring(response.content)
                articles = root.findall('.//PubmedArticle')
                
                for article in articles:
                    metadata = self._extract_metadata_from_xml(article)
                    if metadata:
                        metadata_list.append(metadata)
                
                # 速率限制
                time.sleep(self.delay)
                
            except Exception as e:
                print(f'获取批次元数据时出错: {e}', file=sys.stderr)
                continue
        
        return metadata_list
    
    def _extract_metadata_from_xml(self, article: ET.Element) -> Optional[Dict]:
        """从 PubmedArticle XML 元素提取元数据。"""
        try:
            medline_citation = article.find('.//MedlineCitation')
            article_elem = medline_citation.find('.//Article')
            journal = article_elem.find('.//Journal')
            
            # 获取 PMID
            pmid = medline_citation.findtext('.//PMID', '')
            
            # 获取 DOI
            doi = None
            article_ids = article.findall('.//ArticleId')
            for article_id in article_ids:
                if article_id.get('IdType') == 'doi':
                    doi = article_id.text
                    break
            
            # 获取作者
            authors = []
            author_list = article_elem.find('.//AuthorList')
            if author_list is not None:
                for author in author_list.findall('.//Author'):
                    last_name = author.findtext('.//LastName', '')
                    fore_name = author.findtext('.//ForeName', '')
                    if last_name:
                        if fore_name:
                            authors.append(f'{last_name}, {fore_name}')
                        else:
                            authors.append(last_name)
            
            # 获取年份
            year = article_elem.findtext('.//Journal/JournalIssue/PubDate/Year', '')
            if not year:
                medline_date = article_elem.findtext('.//Journal/JournalIssue/PubDate/MedlineDate', '')
                if medline_date:
                    import re
                    year_match = re.search(r'\d{4}', medline_date)
                    if year_match:
                        year = year_match.group()
            
            metadata = {
                'pmid': pmid,
                'doi': doi,
                'title': article_elem.findtext('.//ArticleTitle', ''),
                'authors': ' and '.join(authors),
                'journal': journal.findtext('.//Title', ''),
                'year': year,
                'volume': journal.findtext('.//JournalIssue/Volume', ''),
                'issue': journal.findtext('.//JournalIssue/Issue', ''),
                'pages': article_elem.findtext('.//Pagination/MedlinePgn', ''),
                'abstract': article_elem.findtext('.//Abstract/AbstractText', '')
            }
            
            return metadata
            
        except Exception as e:
            print(f'提取元数据时出错: {e}', file=sys.stderr)
            return None
    
    def metadata_to_bibtex(self, metadata: Dict) -> str:
        """将元数据转换为 BibTeX 格式。"""
        # 生成引用键
        if metadata.get('authors'):
            first_author = metadata['authors'].split(' and ')[0]
            if ',' in first_author:
                last_name = first_author.split(',')[0].strip()
            else:
                last_name = first_author.split()[0]
        else:
            last_name = 'Unknown'
        
        year = metadata.get('year', 'XXXX')
        citation_key = f'{last_name}{year}pmid{metadata.get("pmid", "")}'
        
        # 构建 BibTeX 条目
        lines = [f'@article{{{citation_key},']
        
        if metadata.get('authors'):
            lines.append(f'  author  = {{{metadata["authors"]}}},')
        
        if metadata.get('title'):
            lines.append(f'  title   = {{{metadata["title"]}}},')
        
        if metadata.get('journal'):
            lines.append(f'  journal = {{{metadata["journal"]}}},')
        
        if metadata.get('year'):
            lines.append(f'  year    = {{{metadata["year"]}}},')
        
        if metadata.get('volume'):
            lines.append(f'  volume  = {{{metadata["volume"]}}},')
        
        if metadata.get('issue'):
            lines.append(f'  number  = {{{metadata["issue"]}}},')
        
        if metadata.get('pages'):
            pages = metadata['pages'].replace('-', '--')
            lines.append(f'  pages   = {{{pages}}},')
        
        if metadata.get('doi'):
            lines.append(f'  doi     = {{{metadata["doi"]}}},')
        
        if metadata.get('pmid'):
            lines.append(f'  note    = {{PMID: {metadata["pmid"]}}},')
        
        # 删除尾随逗号
        if lines[-1].endswith(','):
            lines[-1] = lines[-1][:-1]
        
        lines.append('}')
        
        return '\n'.join(lines)


def main():
    """命令行界面。"""
    parser = argparse.ArgumentParser(
        description='使用 E-utilities API 搜索 PubMed',
        epilog='示例: python search_pubmed.py "CRISPR 基因编辑" --limit 100'
    )
    
    parser.add_argument(
        'query',
        nargs='?',
        help='搜索查询（PubMed 语法）'
    )
    
    parser.add_argument(
        '--query',
        dest='query_arg',
        help='搜索查询（位置参数的替代）'
    )
    
    parser.add_argument(
        '--query-file',
        help='包含搜索查询的文件'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='最大结果数（默认: 100）'
    )
    
    parser.add_argument(
        '--date-start',
        help='起始日期（YYYY/MM/DD 或 YYYY）'
    )
    
    parser.add_argument(
        '--date-end',
        help='结束日期（YYYY/MM/DD 或 YYYY）'
    )
    
    parser.add_argument(
        '--publication-types',
        help='逗号分隔的发表类型（例如，"Review,Clinical Trial"）'
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
    
    parser.add_argument(
        '--api-key',
        help='NCBI API 密钥（或设置 NCBI_API_KEY 环境变量）'
    )
    
    parser.add_argument(
        '--email',
        help='Entrez 的电子邮件（或设置 NCBI_EMAIL 环境变量）'
    )
    
    args = parser.parse_args()
    
    # 获取查询
    query = args.query or args.query_arg
    
    if args.query_file:
        try:
            with open(args.query_file, 'r', encoding='utf-8') as f:
                query = f.read().strip()
        except Exception as e:
            print(f'读取查询文件时出错: {e}', file=sys.stderr)
            sys.exit(1)
    
    if not query:
        parser.print_help()
        sys.exit(1)
    
    # 解析发表类型
    pub_types = None
    if args.publication_types:
        pub_types = [pt.strip() for pt in args.publication_types.split(',')]
    
    # 搜索 PubMed
    searcher = PubMedSearcher(api_key=args.api_key, email=args.email)
    pmids = searcher.search(
        query,
        max_results=args.limit,
        date_start=args.date_start,
        date_end=args.date_end,
        publication_types=pub_types
    )
    
    if not pmids:
        print('未找到结果', file=sys.stderr)
        sys.exit(1)
    
    # 获取元数据
    metadata_list = searcher.fetch_metadata(pmids)
    
    # 格式化输出
    if args.format == 'json':
        output = json.dumps({
            'query': query,
            'count': len(metadata_list),
            'results': metadata_list
        }, indent=2)
    else:  # bibtex
        bibtex_entries = [searcher.metadata_to_bibtex(m) for m in metadata_list]
        output = '\n\n'.join(bibtex_entries) + '\n'
    
    # 写入输出
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f'已写入 {len(metadata_list)} 个结果至 {args.output}', file=sys.stderr)
    else:
        print(output)


if __name__ == '__main__':
    main()
