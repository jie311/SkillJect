#!/usr/bin/env python3
"""
元数据提取工具
使用各种 API 从 DOI、PMID、arXiv ID 或 URL 提取引用元数据。
"""

import sys
import os
import requests
import argparse
import time
import re
import json
import xml.etree.ElementTree as ET
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse

class MetadataExtractor:
    """从各种来源提取元数据并生成 BibTeX。"""
    
    def __init__(self, email: Optional[str] = None):
        """
        初始化提取器。
        
        参数：
            email：Entrez API 的电子邮件（建议用于 PubMed）
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MetadataExtractor/1.0 (引用管理工具)'
        })
        self.email = email or os.getenv('NCBI_EMAIL', '')
    
    def identify_type(self, identifier: str) -> Tuple[str, str]:
        """
        识别标识符的类型。
        
        参数：
            identifier：DOI、PMID、arXiv ID 或 URL
            
        返回：
            (类型, 清理后的标识符) 元组
        """
        identifier = identifier.strip()
        
        # 检查是否为 URL
        if identifier.startswith('http://') or identifier.startswith('https://'):
            return self._parse_url(identifier)
        
        # 检查 DOI
        if identifier.startswith('10.'):
            return ('doi', identifier)
        
        # 检查 arXiv ID
        if re.match(r'^\d{4}\.\d{4,5}(v\d+)?$', identifier):
            return ('arxiv', identifier)
        if identifier.startswith('arXiv:'):
            return ('arxiv', identifier.replace('arXiv:', ''))
        
        # 检查 PMID（通常为 8 位数字）
        if identifier.isdigit() and len(identifier) >= 7:
            return ('pmid', identifier)
        
        # 检查 PMCID
        if identifier.upper().startswith('PMC') and identifier[3:].isdigit():
            return ('pmcid', identifier.upper())
        
        return ('unknown', identifier)
    
    def _parse_url(self, url: str) -> Tuple[str, str]:
        """解析 URL 以提取标识符类型和值。"""
        parsed = urlparse(url)
        
        # DOI URL
        if 'doi.org' in parsed.netloc:
            doi = parsed.path.lstrip('/')
            return ('doi', doi)
        
        # PubMed URL
        if 'pubmed.ncbi.nlm.nih.gov' in parsed.netloc or 'ncbi.nlm.nih.gov/pubmed' in url:
            pmid = re.search(r'/(\d+)', parsed.path)
            if pmid:
                return ('pmid', pmid.group(1))
        
        # arXiv URL
        if 'arxiv.org' in parsed.netloc:
            arxiv_id = re.search(r'/abs/(\d{4}\.\d{4,5})', parsed.path)
            if arxiv_id:
                return ('arxiv', arxiv_id.group(1))
        
        # Nature、Science、Cell 等 - 尝试从 URL 中提取 DOI
        doi_match = re.search(r'10\.\d{4,}/[^\s/]+', url)
        if doi_match:
            return ('doi', doi_match.group())
        
        return ('url', url)
    
    def extract_from_doi(self, doi: str) -> Optional[Dict]:
        """
        使用 CrossRef API 从 DOI 提取元数据。
        
        参数：
            doi：数字对象标识符
            
        返回：
            元数据字典或 None
        """
        url = f'https://api.crossref.org/works/{doi}'
        
        try:
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                message = data.get('message', {})
                
                metadata = {
                    'type': 'doi',
                    'entry_type': self._crossref_type_to_bibtex(message.get('type')),
                    'doi': doi,
                    'title': message.get('title', [''])[0],
                    'authors': self._format_authors_crossref(message.get('author', [])),
                    'year': self._extract_year_crossref(message),
                    'journal': message.get('container-title', [''])[0] if message.get('container-title') else '',
                    'volume': str(message.get('volume', '')) if message.get('volume') else '',
                    'issue': str(message.get('issue', '')) if message.get('issue') else '',
                    'pages': message.get('page', ''),
                    'publisher': message.get('publisher', ''),
                    'url': f'https://doi.org/{doi}'
                }
                
                return metadata
            else:
                print(f'错误: CrossRef API 返回状态 {response.status_code}，DOI: {doi}', file=sys.stderr)
                return None
                
        except Exception as e:
            print(f'从 DOI {doi} 提取元数据时出错: {e}', file=sys.stderr)
            return None
    
    def extract_from_pmid(self, pmid: str) -> Optional[Dict]:
        """
        使用 PubMed E-utilities 从 PMID 提取元数据。
        
        参数：
            pmid：PubMed ID
            
        返回：
            元数据字典或 None
        """
        url = f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
        params = {
            'db': 'pubmed',
            'id': pmid,
            'retmode': 'xml',
            'rettype': 'abstract'
        }
        
        if self.email:
            params['email'] = self.email
        
        api_key = os.getenv('NCBI_API_KEY')
        if api_key:
            params['api_key'] = api_key
        
        try:
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                article = root.find('.//PubmedArticle')
                
                if article is None:
                    print(f'错误: 未找到 PMID 的文章: {pmid}', file=sys.stderr)
                    return None
                
                # 从 XML 提取元数据
                medline_citation = article.find('.//MedlineCitation')
                article_elem = medline_citation.find('.//Article')
                journal = article_elem.find('.//Journal')
                
                # 获取 DOI（如果可用）
                doi = None
                article_ids = article.findall('.//ArticleId')
                for article_id in article_ids:
                    if article_id.get('IdType') == 'doi':
                        doi = article_id.text
                        break
                
                metadata = {
                    'type': 'pmid',
                    'entry_type': 'article',
                    'pmid': pmid,
                    'title': article_elem.findtext('.//ArticleTitle', ''),
                    'authors': self._format_authors_pubmed(article_elem.findall('.//Author')),
                    'year': self._extract_year_pubmed(article_elem),
                    'journal': journal.findtext('.//Title', ''),
                    'volume': journal.findtext('.//JournalIssue/Volume', ''),
                    'issue': journal.findtext('.//JournalIssue/Issue', ''),
                    'pages': article_elem.findtext('.//Pagination/MedlinePgn', ''),
                    'doi': doi
                }
                
                return metadata
            else:
                print(f'错误: PubMed API 返回状态 {response.status_code}，PMID: {pmid}', file=sys.stderr)
                return None
                
        except Exception as e:
            print(f'从 PMID {pmid} 提取元数据时出错: {e}', file=sys.stderr)
            return None
    
    def extract_from_arxiv(self, arxiv_id: str) -> Optional[Dict]:
        """
        使用 arXiv API 从 arXiv ID 提取元数据。
        
        参数：
            arxiv_id：arXiv 标识符
            
        返回：
            元数据字典或 None
        """
        url = 'http://export.arxiv.org/api/query'
        params = {
            'id_list': arxiv_id,
            'max_results': 1
        }
        
        try:
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                # 解析 Atom XML
                root = ET.fromstring(response.content)
                ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}
                
                entry = root.find('atom:entry', ns)
                if entry is None:
                    print(f'错误: 未找到 arXiv ID 的条目: {arxiv_id}', file=sys.stderr)
                    return None
                
                # 提取 DOI（如果已发表）
                doi_elem = entry.find('arxiv:doi', ns)
                doi = doi_elem.text if doi_elem is not None else None
                
                # 提取期刊引用（如果已发表）
                journal_ref_elem = entry.find('arxiv:journal_ref', ns)
                journal_ref = journal_ref_elem.text if journal_ref_elem is not None else None
                
                # 获取发表日期
                published = entry.findtext('atom:published', '', ns)
                year = published[:4] if published else ''
                
                # 获取作者
                authors = []
                for author in entry.findall('atom:author', ns):
                    name = author.findtext('atom:name', '', ns)
                    if name:
                        authors.append(name)
                
                metadata = {
                    'type': 'arxiv',
                    'entry_type': 'misc' if not doi else 'article',
                    'arxiv_id': arxiv_id,
                    'title': entry.findtext('atom:title', '', ns).strip().replace('\n', ' '),
                    'authors': ' and '.join(authors),
                    'year': year,
                    'doi': doi,
                    'journal_ref': journal_ref,
                    'abstract': entry.findtext('atom:summary', '', ns).strip().replace('\n', ' '),
                    'url': f'https://arxiv.org/abs/{arxiv_id}'
                }
                
                return metadata
            else:
                print(f'错误: arXiv API 返回状态 {response.status_code}，ID: {arxiv_id}', file=sys.stderr)
                return None
                
        except Exception as e:
            print(f'从 arXiv {arxiv_id} 提取元数据时出错: {e}', file=sys.stderr)
            return None
    
    def metadata_to_bibtex(self, metadata: Dict, citation_key: Optional[str] = None) -> str:
        """
        将元数据字典转换为 BibTeX 格式。
        
        参数：
            metadata：元数据字典
            citation_key：可选的自定义引用键
        
        返回：
            BibTeX 字符串
        """
        if not citation_key:
            citation_key = self._generate_citation_key(metadata)
        
        entry_type = metadata.get('entry_type', 'misc')
        
        # 构建 BibTeX 条目
        lines = [f'@{entry_type}{{{citation_key},']
        
        # 添加字段
        if metadata.get('authors'):
            lines.append(f'  author  = {{{metadata["authors"]}}},')
        
        if metadata.get('title'):
            # 保护大小写
            title = self._protect_title(metadata['title'])
            lines.append(f'  title   = {{{title}}},')
        
        if entry_type == 'article' and metadata.get('journal'):
            lines.append(f'  journal = {{{metadata["journal"]}}},')
        elif entry_type == 'misc' and metadata.get('type') == 'arxiv':
            lines.append(f'  howpublished = {{arXiv}},')
        
        if metadata.get('year'):
            lines.append(f'  year    = {{{metadata["year"]}}},')
        
        if metadata.get('volume'):
            lines.append(f'  volume  = {{{metadata["volume"]}}},')
        
        if metadata.get('issue'):
            lines.append(f'  number  = {{{metadata["issue"]}}},')
        
        if metadata.get('pages'):
            pages = metadata['pages'].replace('-', '--')  # 短划线
            lines.append(f'  pages   = {{{pages}}},')
        
        if metadata.get('doi'):
            lines.append(f'  doi     = {{{metadata["doi"]}}},')
        elif metadata.get('url'):
            lines.append(f'  url     = {{{metadata["url"]}}},')
        
        if metadata.get('pmid'):
            lines.append(f'  note    = {{PMID: {metadata["pmid"]}}},')
        
        if metadata.get('type') == 'arxiv' and not metadata.get('doi'):
            lines.append(f'  note    = {{预印本}},')
        
        # 从最后一个字段删除尾随逗号
        if lines[-1].endswith(','):
            lines[-1] = lines[-1][:-1]
        
        lines.append('}')
        
        return '\n'.join(lines)
    
    def _crossref_type_to_bibtex(self, crossref_type: str) -> str:
        """将 CrossRef 类型映射到 BibTeX 条目类型。"""
        type_map = {
            'journal-article': 'article',
            'book': 'book',
            'book-chapter': 'incollection',
            'proceedings-article': 'inproceedings',
            'posted-content': 'misc',
            'dataset': 'misc',
            'report': 'techreport'
        }
        return type_map.get(crossref_type, 'misc')
    
    def _format_authors_crossref(self, authors: List[Dict]) -> str:
        """格式化 CrossRef 数据的作者列表。"""
        if not authors:
            return ''
        
        formatted = []
        for author in authors:
            given = author.get('given', '')
            family = author.get('family', '')
            if family:
                if given:
                    formatted.append(f'{family}, {given}')
                else:
                    formatted.append(family)
        
        return ' and '.join(formatted)
    
    def _format_authors_pubmed(self, authors: List) -> str:
        """格式化 PubMed XML 的作者列表。"""
        formatted = []
        for author in authors:
            last_name = author.findtext('.//LastName', '')
            fore_name = author.findtext('.//ForeName', '')
            if last_name:
                if fore_name:
                    formatted.append(f'{last_name}, {fore_name}')
                else:
                    formatted.append(last_name)
        
        return ' and '.join(formatted)
    
    def _extract_year_crossref(self, message: Dict) -> str:
        """从 CrossRef 消息提取年份。"""
        # 先尝试 published-print，然后是 published-online
        date_parts = message.get('published-print', {}).get('date-parts', [[]])
        if not date_parts or not date_parts[0]:
            date_parts = message.get('published-online', {}).get('date-parts', [[]])
        
        if date_parts and date_parts[0]:
            return str(date_parts[0][0])
        return ''
    
    def _extract_year_pubmed(self, article: ET.Element) -> str:
        """从 PubMed XML 提取年份。"""
        year = article.findtext('.//Journal/JournalIssue/PubDate/Year', '')
        if not year:
            medline_date = article.findtext('.//Journal/JournalIssue/PubDate/MedlineDate', '')
            if medline_date:
                year_match = re.search(r'\d{4}', medline_date)
                if year_match:
                    year = year_match.group()
        return year
    
    def _generate_citation_key(self, metadata: Dict) -> str:
        """从元数据生成引用键。"""
        # 获取第一作者的姓氏
        authors = metadata.get('authors', '')
        if authors:
            first_author = authors.split(' and ')[0]
            if ',' in first_author:
                last_name = first_author.split(',')[0].strip()
            else:
                last_name = first_author.split()[-1] if first_author else 'Unknown'
        else:
            last_name = 'Unknown'
        
        # 获取年份
        year = metadata.get('year', '').strip()
        if not year:
            year = 'XXXX'
        
        # 清理姓氏（删除特殊字符）
        last_name = re.sub(r'[^a-zA-Z]', '', last_name)
        
        # 从标题获取关键词
        title = metadata.get('title', '')
        words = re.findall(r'\b[a-zA-Z]{4,}\b', title)
        keyword = words[0].lower() if words else 'paper'
        
        return f'{last_name}{year}{keyword}'
    
    def _protect_title(self, title: str) -> str:
        """保护 BibTeX 标题中的大小写。"""
        # 保护常见缩略词和专有名词
        protected_words = [
            'DNA', 'RNA', 'CRISPR', 'COVID', 'HIV', 'AIDS', 'AlphaFold',
            'Python', 'AI', 'ML', 'GPU', 'CPU', 'USA', 'UK', 'EU'
        ]
        
        for word in protected_words:
            title = re.sub(rf'\b{word}\b', f'{{{word}}}', title, flags=re.IGNORECASE)
        
        return title
    
    def extract(self, identifier: str) -> Optional[str]:
        """
        提取元数据并返回 BibTeX。
        
        参数：
            identifier：DOI、PMID、arXiv ID 或 URL
        
        返回：
            BibTeX 字符串或 None
        """
        id_type, clean_id = self.identify_type(identifier)
        
        print(f'识别为 {id_type}: {clean_id}', file=sys.stderr)
        
        metadata = None
        
        if id_type == 'doi':
            metadata = self.extract_from_doi(clean_id)
        elif id_type == 'pmid':
            metadata = self.extract_from_pmid(clean_id)
        elif id_type == 'arxiv':
            metadata = self.extract_from_arxiv(clean_id)
        else:
            print(f'错误: 未知的标识符类型: {identifier}', file=sys.stderr)
            return None
        
        if metadata:
            return self.metadata_to_bibtex(metadata)
        else:
            return None


def main():
    """命令行界面。"""
    parser = argparse.ArgumentParser(
        description='从 DOI、PMID、arXiv ID 或 URL 提取引用元数据',
        epilog='示例: python extract_metadata.py --doi 10.1038/s41586-021-03819-2'
    )
    
    parser.add_argument('--doi', help='数字对象标识符')
    parser.add_argument('--pmid', help='PubMed ID')
    parser.add_argument('--arxiv', help='arXiv ID')
    parser.add_argument('--url', help='文章的 URL')
    parser.add_argument('-i', '--input', help='标识符输入文件（每行一个）')
    parser.add_argument('-o', '--output', help='BibTeX 输出文件（默认: 标准输出）')
    parser.add_argument('--format', choices=['bibtex', 'json'], default='bibtex', help='输出格式')
    parser.add_argument('--email', help='NCBI E-utilities 的电子邮件（建议）')
    
    args = parser.parse_args()
    
    # 收集标识符
    identifiers = []
    if args.doi:
        identifiers.append(args.doi)
    if args.pmid:
        identifiers.append(args.pmid)
    if args.arxiv:
        identifiers.append(args.arxiv)
    if args.url:
        identifiers.append(args.url)
    
    if args.input:
        try:
            with open(args.input, 'r', encoding='utf-8') as f:
                file_ids = [line.strip() for line in f if line.strip()]
                identifiers.extend(file_ids)
        except Exception as e:
            print(f'读取输入文件时出错: {e}', file=sys.stderr)
            sys.exit(1)
    
    if not identifiers:
        parser.print_help()
        sys.exit(1)
    
    # 提取元数据
    extractor = MetadataExtractor(email=args.email)
    bibtex_entries = []
    
    for i, identifier in enumerate(identifiers):
        print(f'\n正在处理 {i+1}/{len(identifiers)}...', file=sys.stderr)
        bibtex = extractor.extract(identifier)
        if bibtex:
            bibtex_entries.append(bibtex)
        
        # 速率限制
        if i < len(identifiers) - 1:
            time.sleep(0.5)
    
    if not bibtex_entries:
        print('错误: 没有成功的提取', file=sys.stderr)
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
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f'\n成功写入 {len(bibtex_entries)} 个条目至 {args.output}', file=sys.stderr)
    else:
        print(output)
    
    print(f'\n提取了 {len(bibtex_entries)}/{len(identifiers)} 个条目', file=sys.stderr)


if __name__ == '__main__':
    main()
