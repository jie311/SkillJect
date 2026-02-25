#!/usr/bin/env python3
"""
使用NCBI数据集API获取基因数据

该脚本提供对NCBI数据集API的访问，用于检索
包括元数据和序列的综合基因信息。
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from typing import Optional, Dict, Any, List


DATASETS_API_BASE = "https://api.ncbi.nlm.nih.gov/datasets/v2alpha/gene"


def get_taxon_id(taxon_name: str) -> Optional[str]:
    """
    将分类名称转换为NCBI分类ID。

    参数:
        taxon_name: 通用名或学名（如"human"、"Homo sapiens"）

    返回:
        分类ID字符串，如果未找到则返回None
    """
    # 常用映射
    common_taxa = {
        'human': '9606',
        'homo sapiens': '9606',
        'mouse': '10090',
        'mus musculus': '10090',
        'rat': '10116',
        'rattus norvegicus': '10116',
        'zebrafish': '7955',
        'danio rerio': '7955',
        'fruit fly': '7227',
        'drosophila melanogaster': '7227',
        'c. elegans': '6239',
        'caenorhabditis elegans': '6239',
        'yeast': '4932',
        'saccharomyces cerevisiae': '4932',
        'arabidopsis': '3702',
        'arabidopsis thaliana': '3702',
        'e. coli': '562',
        'escherichia coli': '562',
    }

    taxon_lower = taxon_name.lower().strip()
    return common_taxa.get(taxon_lower)


def fetch_gene_by_id(gene_id: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    通过基因ID获取基因数据。

    参数:
        gene_id: NCBI基因ID
        api_key: 可选的NCBI API密钥

    返回:
        基因数据字典
    """
    url = f"{DATASETS_API_BASE}/id/{gene_id}"

    headers = {}
    if api_key:
        headers['api-key'] = api_key

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP错误 {e.code}: {e.reason}", file=sys.stderr)
        if e.code == 404:
            print(f"未找到基因ID {gene_id}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return {}


def fetch_gene_by_symbol(symbol: str, taxon: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    通过基因符号和分类获取基因数据。

    参数:
        symbol: 基因符号（如"BRCA1"）
        taxon: 生物体名称或分类ID
        api_key: 可选的NCBI API密钥

    返回:
        基因数据字典
    """
    # 如果需要，将分类名称转换为ID
    taxon_id = get_taxon_id(taxon)
    if not taxon_id:
        # 尝试原样使用（可能已经是分类ID）
        taxon_id = taxon

    url = f"{DATASETS_API_BASE}/symbol/{symbol}/taxon/{taxon_id}"

    headers = {}
    if api_key:
        headers['api-key'] = api_key

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP错误 {e.code}: {e.reason}", file=sys.stderr)
        if e.code == 404:
            print(f"未找到分类 {taxon} 的基因符号 '{symbol}'", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return {}


def fetch_multiple_genes(gene_ids: List[str], api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    通过ID获取多个基因的数据。

    参数:
        gene_ids: 基因ID列表
        api_key: 可选的NCBI API密钥

    返回:
        组合基因数据字典
    """
    # 对于多个基因，使用POST请求
    url = f"{DATASETS_API_BASE}/id"

    data = json.dumps({"gene_ids": gene_ids}).encode('utf-8')
    headers = {'Content-Type': 'application/json'}

    if api_key:
        headers['api-key'] = api_key

    try:
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP错误 {e.code}: {e.reason}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return {}


def display_gene_info(data: Dict[str, Any], verbose: bool = False) -> None:
    """
    以人类可读的格式显示基因信息。

    参数:
        data: 来自API的基因数据字典
        verbose: 显示详细信息
    """
    if 'genes' not in data:
        print("响应中未找到基因数据")
        return

    for gene in data['genes']:
        gene_info = gene.get('gene', {})

        print(f"基因ID: {gene_info.get('gene_id', 'N/A')}")
        print(f"符号: {gene_info.get('symbol', 'N/A')}")
        print(f"描述: {gene_info.get('description', 'N/A')}")

        if 'tax_name' in gene_info:
            print(f"生物体: {gene_info['tax_name']}")

        if 'chromosomes' in gene_info:
            chromosomes = ', '.join(gene_info['chromosomes'])
            print(f"染色体: {chromosomes}")

        # 命名法
        if 'nomenclature_authority' in gene_info:
            auth = gene_info['nomenclature_authority']
            print(f"命名法: {auth.get('authority', 'N/A')}")

        # 同义词
        if 'synonyms' in gene_info and gene_info['synonyms']:
            print(f"同义词: {', '.join(gene_info['synonyms'])}")

        if verbose:
            # 基因类型
            if 'type' in gene_info:
                print(f"类型: {gene_info['type']}")

            # 基因组位置
            if 'genomic_ranges' in gene_info:
                print("\n基因组位置:")
                for range_info in gene_info['genomic_ranges']:
                    accession = range_info.get('accession_version', 'N/A')
                    start = range_info.get('range', [{}])[0].get('begin', 'N/A')
                    end = range_info.get('range', [{}])[0].get('end', 'N/A')
                    strand = range_info.get('orientation', 'N/A')
                    print(f"  {accession}: {start}-{end} ({strand})")

            # 转录本
            if 'transcripts' in gene_info:
                print(f"\n转录本: {len(gene_info['transcripts'])}")
                for transcript in gene_info['transcripts'][:5]:  # 显示前5个
                    print(f"  {transcript.get('accession_version', 'N/A')}")

        print()


def main():
    parser = argparse.ArgumentParser(
        description='从NCBI数据集API获取基因数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 通过基因ID获取
  %(prog)s --gene-id 672

  # 通过基因符号和生物体获取
  %(prog)s --symbol BRCA1 --taxon human

  # 获取多个基因
  %(prog)s --gene-id 672,7157,5594

  # 获取JSON输出
  %(prog)s --symbol TP53 --taxon "Homo sapiens" --output json

  # 带详细信息的详细输出
  %(prog)s --gene-id 672 --verbose
        """
    )

    parser.add_argument('--gene-id', '-g', help='基因ID，逗号分隔')
    parser.add_argument('--symbol', '-s', help='基因符号')
    parser.add_argument('--taxon', '-t', help='生物体名称或分类ID（使用--symbol时需要）')
    parser.add_argument('--output', '-o', choices=['pretty', 'json'], default='pretty',
                       help='输出格式（默认：pretty）')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='显示详细信息')
    parser.add_argument('--api-key', '-k', help='NCBI API密钥')

    args = parser.parse_args()

    if not args.gene_id and not args.symbol:
        parser.error("必须提供--gene-id或--symbol")

    if args.symbol and not args.taxon:
        parser.error("使用--symbol时需要--taxon")

    # 获取数据
    if args.gene_id:
        gene_ids = [id.strip() for id in args.gene_id.split(',')]
        if len(gene_ids) == 1:
            data = fetch_gene_by_id(gene_ids[0], api_key=args.api_key)
        else:
            data = fetch_multiple_genes(gene_ids, api_key=args.api_key)
    else:
        data = fetch_gene_by_symbol(args.symbol, args.taxon, api_key=args.api_key)

    if not data:
        sys.exit(1)

    # 输出
    if args.output == 'json':
        print(json.dumps(data, indent=2))
    else:
        display_gene_info(data, verbose=args.verbose)


if __name__ == '__main__':
    main()
