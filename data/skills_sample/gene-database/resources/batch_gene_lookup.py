#!/usr/bin/env python3
"""
使用NCBI API进行批量基因查询

该脚本使用适当的速率限制和错误处理
高效地处理多个基因查询。
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from typing import Optional, List, Dict, Any


def read_gene_list(filepath: str) -> List[str]:
    """
    从文件中读取基因标识符（每行一个）。

    参数:
        filepath: 包含基因符号或ID的文件路径

    返回:
        基因标识符列表
    """
    try:
        with open(filepath, 'r') as f:
            genes = [line.strip() for line in f if line.strip()]
        return genes
    except FileNotFoundError:
        print(f"错误: 未找到文件 '{filepath}'", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"读取文件时出错: {e}", file=sys.stderr)
        sys.exit(1)


def batch_esearch(queries: List[str], organism: Optional[str] = None,
                  api_key: Optional[str] = None) -> Dict[str, str]:
    """
    搜索多个基因符号并返回其ID。

    参数:
        queries: 基因符号列表
        organism: 可选的生物体筛选
        api_key: 可选的NCBI API密钥

    返回:
        将基因符号映射到基因ID的字典（或'NOT_FOUND'）
    """
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    results = {}

    # 速率限制
    delay = 0.1 if api_key else 0.34  # 有密钥10个请求/秒，无密钥3个请求/秒

    for query in queries:
        # 构建搜索词
        search_term = f"{query}[gene]"
        if organism:
            search_term += f" AND {organism}[organism]"

        params = {
            'db': 'gene',
            'term': search_term,
            'retmax': 1,
            'retmode': 'json'
        }

        if api_key:
            params['api_key'] = api_key

        url = f"{base_url}esearch.fcgi?{urllib.parse.urlencode(params)}"

        try:
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())

            if 'esearchresult' in data and 'idlist' in data['esearchresult']:
                id_list = data['esearchresult']['idlist']
                results[query] = id_list[0] if id_list else 'NOT_FOUND'
            else:
                results[query] = 'ERROR'

        except Exception as e:
            print(f"搜索 {query} 时出错: {e}", file=sys.stderr)
            results[query] = 'ERROR'

        time.sleep(delay)

    return results


def batch_esummary(gene_ids: List[str], api_key: Optional[str] = None,
                   chunk_size: int = 200) -> Dict[str, Dict[str, Any]]:
    """
    批量获取多个基因的摘要。

    参数:
        gene_ids: 基因ID列表
        api_key: 可选的NCBI API密钥
        chunk_size: 每个请求的ID数量（最多500）

    返回:
        将基因ID映射到摘要数据的字典
    """
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    all_results = {}

    # 速率限制
    delay = 0.1 if api_key else 0.34

    # 分批处理
    for i in range(0, len(gene_ids), chunk_size):
        chunk = gene_ids[i:i + chunk_size]

        params = {
            'db': 'gene',
            'id': ','.join(chunk),
            'retmode': 'json'
        }

        if api_key:
            params['api_key'] = api_key

        url = f"{base_url}esummary.fcgi?{urllib.parse.urlencode(params)}"

        try:
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())

            if 'result' in data:
                for gene_id in chunk:
                    if gene_id in data['result']:
                        all_results[gene_id] = data['result'][gene_id]

        except Exception as e:
            print(f"获取分块摘要时出错: {e}", file=sys.stderr)

        time.sleep(delay)

    return all_results


def batch_lookup_by_ids(gene_ids: List[str], api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    通过ID查找基因并返回结构化数据。

    参数:
        gene_ids: 基因ID列表
        api_key: 可选的NCBI API密钥

    返回:
        基因信息字典列表
    """
    summaries = batch_esummary(gene_ids, api_key=api_key)

    results = []
    for gene_id in gene_ids:
        if gene_id in summaries:
            gene = summaries[gene_id]
            results.append({
                'gene_id': gene_id,
                'symbol': gene.get('name', 'N/A'),
                'description': gene.get('description', 'N/A'),
                'organism': gene.get('organism', {}).get('scientificname', 'N/A'),
                'chromosome': gene.get('chromosome', 'N/A'),
                'map_location': gene.get('maplocation', 'N/A'),
                'type': gene.get('geneticsource', 'N/A')
            })
        else:
            results.append({
                'gene_id': gene_id,
                'error': '未找到或获取时出错'
            })

    return results


def batch_lookup_by_symbols(gene_symbols: List[str], organism: str,
                            api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    通过符号查找基因并返回结构化数据。

    参数:
        gene_symbols: 基因符号列表
        organism: 生物体名称
        api_key: 可选的NCBI API密钥

    返回:
        基因信息字典列表
    """
    # 首先搜索ID
    print(f"正在搜索 {len(gene_symbols)} 个基因符号...", file=sys.stderr)
    symbol_to_id = batch_esearch(gene_symbols, organism=organism, api_key=api_key)

    # 筛选到有效ID
    valid_ids = [id for id in symbol_to_id.values() if id not in ['NOT_FOUND', 'ERROR']]

    if not valid_ids:
        print("未找到基因", file=sys.stderr)
        return []

    print(f"找到 {len(valid_ids)} 个基因，正在获取详细信息...", file=sys.stderr)

    # 获取摘要
    summaries = batch_esummary(valid_ids, api_key=api_key)

    # 构建结果
    results = []
    for symbol, gene_id in symbol_to_id.items():
        if gene_id == 'NOT_FOUND':
            results.append({
                'query_symbol': symbol,
                'status': 'not_found'
            })
        elif gene_id == 'ERROR':
            results.append({
                'query_symbol': symbol,
                'status': 'error'
            })
        elif gene_id in summaries:
            gene = summaries[gene_id]
            results.append({
                'query_symbol': symbol,
                'gene_id': gene_id,
                'symbol': gene.get('name', 'N/A'),
                'description': gene.get('description', 'N/A'),
                'organism': gene.get('organism', {}).get('scientificname', 'N/A'),
                'chromosome': gene.get('chromosome', 'N/A'),
                'map_location': gene.get('maplocation', 'N/A'),
                'type': gene.get('geneticsource', 'N/A')
            })

    return results


def main():
    parser = argparse.ArgumentParser(
        description='使用NCBI API进行批量基因查询',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 通过基因ID查询
  %(prog)s --ids 672,7157,5594

  # 通过文件中的符号查询
  %(prog)s --file genes.txt --organism human

  # 使用API密钥查询并保存到文件
  %(prog)s --ids 672,7157,5594 --api-key YOUR_KEY --output results.json
        """
    )

    parser.add_argument('--ids', '-i', help='逗号分隔的基因ID')
    parser.add_argument('--file', '-f', help='包含基因符号的文件（每行一个）')
    parser.add_argument('--organism', '-o', help='生物体名称（使用--file时需要）')
    parser.add_argument('--output', '-O', help='输出文件路径（JSON格式）')
    parser.add_argument('--api-key', '-k', help='NCBI API密钥')
    parser.add_argument('--pretty', '-p', action='store_true',
                       help='美化打印JSON输出')

    args = parser.parse_args()

    if not args.ids and not args.file:
        parser.error("必须提供--ids或--file")

    if args.file and not args.organism:
        parser.error("使用--file时需要--organism")

    # 处理基因
    if args.ids:
        gene_ids = [id.strip() for id in args.ids.split(',')]
        results = batch_lookup_by_ids(gene_ids, api_key=args.api_key)
    else:
        gene_symbols = read_gene_list(args.file)
        results = batch_lookup_by_symbols(gene_symbols, args.organism, api_key=args.api_key)

    # 输出结果
    indent = 2 if args.pretty else None
    json_output = json.dumps(results, indent=indent)

    if args.output:
        try:
            with open(args.output, 'w') as f:
                f.write(json_output)
            print(f"结果已写入 {args.output}", file=sys.stderr)
        except Exception as e:
            print(f"写入输出文件时出错: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(json_output)


if __name__ == '__main__':
    main()
