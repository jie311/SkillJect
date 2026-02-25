#!/usr/bin/env python3
"""
使用E-utilities查询NCBI基因数据库

该脚本提供对ESearch、ESummary和EFetch函数的访问
用于搜索和检索基因信息。
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from typing import Optional, Dict, List, Any
from xml.etree import ElementTree as ET


BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
DB = "gene"


def esearch(query: str, retmax: int = 20, api_key: Optional[str] = None) -> List[str]:
    """
    搜索NCBI基因数据库并返回基因ID列表。

    参数:
        query: 搜索查询（如"BRCA1[gene] AND human[organism]"）
        retmax: 要返回的最大结果数
        api_key: 可选的NCBI API密钥，用于更高的速率限制

    返回:
        基因ID列表（字符串形式）
    """
    params = {
        'db': DB,
        'term': query,
        'retmax': retmax,
        'retmode': 'json'
    }

    if api_key:
        params['api_key'] = api_key

    url = f"{BASE_URL}esearch.fcgi?{urllib.parse.urlencode(params)}"

    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())

        if 'esearchresult' in data and 'idlist' in data['esearchresult']:
            return data['esearchresult']['idlist']
        else:
            print(f"错误: 意外的响应格式", file=sys.stderr)
            return []

    except urllib.error.HTTPError as e:
        print(f"HTTP错误 {e.code}: {e.reason}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return []


def esummary(gene_ids: List[str], api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    获取基因ID的文档摘要。

    参数:
        gene_ids: 基因ID列表
        api_key: 可选的NCBI API密钥

    返回:
        基因摘要字典
    """
    params = {
        'db': DB,
        'id': ','.join(gene_ids),
        'retmode': 'json'
    }

    if api_key:
        params['api_key'] = api_key

    url = f"{BASE_URL}esummary.fcgi?{urllib.parse.urlencode(params)}"

    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
        return data
    except urllib.error.HTTPError as e:
        print(f"HTTP错误 {e.code}: {e.reason}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return {}


def efetch(gene_ids: List[str], retmode: str = 'xml', api_key: Optional[str] = None) -> str:
    """
    获取完整基因记录。

    参数:
        gene_ids: 基因ID列表
        retmode: 返回格式（'xml'、'text'、'asn.1'）
        api_key: 可选的NCBI API密钥

    返回:
        请求格式的基因记录字符串
    """
    params = {
        'db': DB,
        'id': ','.join(gene_ids),
        'retmode': retmode
    }

    if api_key:
        params['api_key'] = api_key

    url = f"{BASE_URL}efetch.fcgi?{urllib.parse.urlencode(params)}"

    try:
        with urllib.request.urlopen(url) as response:
            return response.read().decode()
    except urllib.error.HTTPError as e:
        print(f"HTTP错误 {e.code}: {e.reason}", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return ""


def search_and_summarize(query: str, organism: Optional[str] = None,
                        max_results: int = 20, api_key: Optional[str] = None) -> None:
    """
    搜索基因并显示摘要。

    参数:
        query: 基因搜索查询
        organism: 可选的生物体筛选
        max_results: 最大结果数
        api_key: 可选的NCBI API密钥
    """
    # 如果提供了生物体则添加筛选
    if organism:
        if '[organism]' not in query.lower():
            query = f"{query} AND {organism}[organism]"

    print(f"正在搜索: {query}")
    print("-" * 80)

    # 搜索基因ID
    gene_ids = esearch(query, retmax=max_results, api_key=api_key)

    if not gene_ids:
        print("未找到结果。")
        return

    print(f"找到 {len(gene_ids)} 个基因")
    print()

    # 获取摘要
    summaries = esummary(gene_ids, api_key=api_key)

    if 'result' in summaries:
        for gene_id in gene_ids:
            if gene_id in summaries['result']:
                gene = summaries['result'][gene_id]
                print(f"基因ID: {gene_id}")
                print(f"  符号: {gene.get('name', 'N/A')}")
                print(f"  描述: {gene.get('description', 'N/A')}")
                print(f"  生物体: {gene.get('organism', {}).get('scientificname', 'N/A')}")
                print(f"  染色体: {gene.get('chromosome', 'N/A')}")
                print(f"  定位位置: {gene.get('maplocation', 'N/A')}")
                print(f"  类型: {gene.get('geneticsource', 'N/A')}")
                print()

    # 遵守速率限制
    time.sleep(0.34)  # 每秒约3个请求


def fetch_by_id(gene_ids: List[str], output_format: str = 'json',
                api_key: Optional[str] = None) -> None:
    """
    通过ID获取并显示基因信息。

    参数:
        gene_ids: 基因ID列表
        output_format: 输出格式（'json'、'xml'、'text'）
        api_key: 可选的NCBI API密钥
    """
    if output_format == 'json':
        # 以JSON格式获取摘要
        summaries = esummary(gene_ids, api_key=api_key)
        print(json.dumps(summaries, indent=2))
    else:
        # 获取完整记录
        data = efetch(gene_ids, retmode=output_format, api_key=api_key)
        print(data)

    # 遵守速率限制
    time.sleep(0.34)


def main():
    parser = argparse.ArgumentParser(
        description='使用E-utilities查询NCBI基因数据库',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 按符号搜索基因
  %(prog)s --search "BRCA1" --organism "human"

  # 通过ID获取基因
  %(prog)s --id 672 --format json

  # 复杂搜索查询
  %(prog)s --search "insulin[gene] AND diabetes[disease]"

  # 多个基因ID
  %(prog)s --id 672,7157,5594
        """
    )

    parser.add_argument('--search', '-s', help='搜索查询')
    parser.add_argument('--organism', '-o', help='生物体筛选')
    parser.add_argument('--id', '-i', help='基因ID，逗号分隔')
    parser.add_argument('--format', '-f', default='json',
                       choices=['json', 'xml', 'text'],
                       help='输出格式（默认：json）')
    parser.add_argument('--max-results', '-m', type=int, default=20,
                       help='最大搜索结果数（默认：20）')
    parser.add_argument('--api-key', '-k', help='用于更高速率限制的NCBI API密钥')

    args = parser.parse_args()

    if not args.search and not args.id:
        parser.error("必须提供--search或--id")

    if args.id:
        # 通过ID获取
        gene_ids = [id.strip() for id in args.id.split(',')]
        fetch_by_id(gene_ids, output_format=args.format, api_key=args.api_key)
    else:
        # 搜索并摘要
        search_and_summarize(args.search, organism=args.organism,
                           max_results=args.max_results, api_key=args.api_key)


if __name__ == '__main__':
    main()
