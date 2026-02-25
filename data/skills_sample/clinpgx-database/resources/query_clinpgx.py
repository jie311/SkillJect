#!/usr/bin/env python3
"""
ClinPGx API查询助手脚本

提供用于查询ClinPGx数据库API的就绪可用函数。
包括速率限制、错误处理和缓存功能。

ClinPGx API: https://api.clinpgx.org/
速率限制: 每秒2个请求
许可证: 知识共享署名-相同方式共享 4.0 国际
"""

import requests
import time
import json
from pathlib import Path
from typing import Dict, List, Optional, Any

# API配置
BASE_URL = "https://api.clinpgx.org/v1/"
RATE_LIMIT_DELAY = 0.5  # 500毫秒延迟 = 2个请求/秒


def rate_limited_request(url: str, params: Optional[Dict] = None, delay: float = RATE_LIMIT_DELAY) -> requests.Response:
    """
    发送符合速率限制的API请求。

    参数:
        url: API端点URL
        params: 查询参数
        delay: 请求间延迟（秒）（默认0.5秒，即2个请求/秒）

    返回:
        响应对象
    """
    response = requests.get(url, params=params)
    time.sleep(delay)
    return response


def safe_api_call(url: str, params: Optional[Dict] = None, max_retries: int = 3) -> Optional[Dict]:
    """
    发送带有错误处理和指数退避重试的API调用。

    参数:
        url: API端点URL
        params: 查询参数
        max_retries: 最大重试次数

    返回:
        JSON响应数据，失败时返回None
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                time.sleep(RATE_LIMIT_DELAY)
                return response.json()
            elif response.status_code == 429:
                # 超过速率限制
                wait_time = 2 ** attempt  # 指数退避: 1秒、2秒、4秒
                print(f"超过速率限制。等待 {wait_time}秒 后重试...")
                time.sleep(wait_time)
            elif response.status_code == 404:
                print(f"未找到资源: {url}")
                return None
            else:
                response.raise_for_status()

        except requests.exceptions.RequestException as e:
            print(f"尝试 {attempt + 1}/{max_retries} 失败: {e}")
            if attempt == max_retries - 1:
                print(f"在 {max_retries} 次尝试后失败")
                return None
            time.sleep(1)

    return None


def cached_query(cache_file: str, query_func, *args, **kwargs) -> Any:
    """
    缓存API结果以避免重复查询。

    参数:
        cache_file: 缓存文件路径
        query_func: 缓存未命中时调用的函数
        *args, **kwargs: 传递给query_func的参数

    返回:
        缓存或新查询的数据
    """
    cache_path = Path(cache_file)

    if cache_path.exists():
        print(f"正在从缓存加载: {cache_file}")
        with open(cache_path) as f:
            return json.load(f)

    print(f"缓存未命中。正在查询API...")
    result = query_func(*args, **kwargs)

    if result is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"已缓存到: {cache_path}")

    return result


# 核心查询函数

def get_gene_info(gene_symbol: str) -> Optional[Dict]:
    """
    检索药物基因的详细信息。

    参数:
        gene_symbol: 基因符号（如"CYP2D6"、"TPMT"）

    返回:
        基因信息字典

    示例:
        >>> gene_data = get_gene_info("CYP2D6")
        >>> print(gene_data['symbol'], gene_data['name'])
    """
    url = f"{BASE_URL}gene/{gene_symbol}"
    return safe_api_call(url)


def get_drug_info(drug_name: str) -> Optional[List[Dict]]:
    """
    按名称搜索药物/化学物质信息。

    参数:
        drug_name: 药物名称（如"warfarin"、"codeine"）

    返回:
        匹配的药物列表

    示例:
        >>> drugs = get_drug_info("warfarin")
        >>> for drug in drugs:
        >>>     print(drug['name'], drug['id'])
    """
    url = f"{BASE_URL}chemical"
    params = {"name": drug_name}
    return safe_api_call(url, params)


def get_gene_drug_pairs(gene: Optional[str] = None, drug: Optional[str] = None) -> Optional[List[Dict]]:
    """
    查询基因-药物相互作用对。

    参数:
        gene: 基因符号（可选）
        drug: 药物名称（可选）

    返回:
        具有临床注释的基因-药物对列表

    示例:
        >>> # 获取CYP2D6的所有配对
        >>> pairs = get_gene_drug_pairs(gene="CYP2D6")
        >>>
        >>> # 获取特定基因-药物配对
        >>> pair = get_gene_drug_pairs(gene="CYP2D6", drug="codeine")
    """
    url = f"{BASE_URL}geneDrugPair"
    params = {}
    if gene:
        params["gene"] = gene
    if drug:
        params["drug"] = drug

    return safe_api_call(url, params)


def get_cpic_guidelines(gene: Optional[str] = None, drug: Optional[str] = None) -> Optional[List[Dict]]:
    """
    检索CPIC临床实践指南。

    参数:
        gene: 基因符号（可选）
        drug: 药物名称（可选）

    返回:
        CPIC指南列表

    示例:
        >>> # 获取所有CPIC指南
        >>> guidelines = get_cpic_guidelines()
        >>>
        >>> # 获取特定基因-药物的指南
        >>> guideline = get_cpic_guidelines(gene="CYP2C19", drug="clopidogrel")
    """
    url = f"{BASE_URL}guideline"
    params = {"source": "CPIC"}
    if gene:
        params["gene"] = gene
    if drug:
        params["drug"] = drug

    return safe_api_call(url, params)


def get_alleles(gene: str) -> Optional[List[Dict]]:
    """
    获取药物基因的所有等位基因，包括功能和频率信息。

    参数:
        gene: 基因符号（如"CYP2D6"）

    返回:
        具有功能注释和群体频率的等位基因列表

    示例:
        >>> alleles = get_alleles("CYP2D6")
        >>> for allele in alleles:
        >>>     print(f"{allele['name']}: {allele['function']}")
    """
    url = f"{BASE_URL}allele"
    params = {"gene": gene}
    return safe_api_call(url, params)


def get_allele_info(allele_name: str) -> Optional[Dict]:
    """
    获取特定等位基因的详细信息。

    参数:
        allele_name: 等位基因名称（如"CYP2D6*4"）

    返回:
        等位基因信息字典

    示例:
        >>> allele = get_allele_info("CYP2D6*4")
        >>> print(allele['function'], allele['frequencies'])
    """
    url = f"{BASE_URL}allele/{allele_name}"
    return safe_api_call(url)


def get_clinical_annotations(
    gene: Optional[str] = None,
    drug: Optional[str] = None,
    evidence_level: Optional[str] = None
) -> Optional[List[Dict]]:
    """
    检索基因-药物相互作用的精选文献注释。

    参数:
        gene: 基因符号（可选）
        drug: 药物名称（可选）
        evidence_level: 按证据级别筛选（1A、1B、2A、2B、3、4）

    返回:
        临床注释列表

    示例:
        >>> # 获取CYP2D6的所有注释
        >>> annotations = get_clinical_annotations(gene="CYP2D6")
        >>>
        >>> # 仅获取高质量证据
        >>> high_quality = get_clinical_annotations(evidence_level="1A")
    """
    url = f"{BASE_URL}clinicalAnnotation"
    params = {}
    if gene:
        params["gene"] = gene
    if drug:
        params["drug"] = drug
    if evidence_level:
        params["evidenceLevel"] = evidence_level

    return safe_api_call(url, params)


def get_drug_labels(drug: str, source: Optional[str] = None) -> Optional[List[Dict]]:
    """
    检索药物基因组学药物标签信息。

    参数:
        drug: 药物名称
        source: 监管来源（如"FDA"、"EMA"）

    返回:
        具有PGx信息的药物标签列表

    示例:
        >>> # 获取华法林的所有标签
        >>> labels = get_drug_labels("warfarin")
        >>>
        >>> # 仅获取FDA标签
        >>> fda_labels = get_drug_labels("warfarin", source="FDA")
    """
    url = f"{BASE_URL}drugLabel"
    params = {"drug": drug}
    if source:
        params["source"] = source

    return safe_api_call(url, params)


def search_variants(rsid: Optional[str] = None, chromosome: Optional[str] = None,
                   position: Optional[str] = None) -> Optional[List[Dict]]:
    """
    通过rsID或基因组位置搜索遗传变异。

    参数:
        rsid: dbSNP rsID（如"rs4244285"）
        chromosome: 染色体编号
        position: 基因组位置

    返回:
        匹配的变异列表

    示例:
        >>> # 通过rsID搜索
        >>> variant = search_variants(rsid="rs4244285")
        >>>
        >>> # 通过位置搜索
        >>> variants = search_variants(chromosome="10", position="94781859")
    """
    url = f"{BASE_URL}variant"

    if rsid:
        url = f"{BASE_URL}variant/{rsid}"
        return safe_api_call(url)

    params = {}
    if chromosome:
        params["chromosome"] = chromosome
    if position:
        params["position"] = position

    return safe_api_call(url, params)


def get_pathway_info(pathway_id: Optional[str] = None, drug: Optional[str] = None) -> Optional[Any]:
    """
    检索药代动力学/药效学通路信息。

    参数:
        pathway_id: ClinPGx通路ID（可选）
        drug: 药物名称（可选）

    返回:
        通路信息或通路列表

    示例:
        >>> # 获取特定通路
        >>> pathway = get_pathway_info(pathway_id="PA146123006")
        >>>
        >>> # 获取药物的所有通路
        >>> pathways = get_pathway_info(drug="warfarin")
    """
    if pathway_id:
        url = f"{BASE_URL}pathway/{pathway_id}"
        return safe_api_call(url)

    url = f"{BASE_URL}pathway"
    params = {}
    if drug:
        params["drug"] = drug

    return safe_api_call(url, params)


# 实用工具函数

def export_to_dataframe(data: List[Dict], output_file: Optional[str] = None):
    """
    将API结果转换为pandas DataFrame进行分析。

    参数:
        data: 来自API的字典列表
        output_file: 可选的CSV输出文件路径

    返回:
        pandas DataFrame

    示例:
        >>> pairs = get_gene_drug_pairs(gene="CYP2D6")
        >>> df = export_to_dataframe(pairs, "cyp2d6_pairs.csv")
        >>> print(df.head())
    """
    try:
        import pandas as pd
    except ImportError:
        print("未安装pandas。使用以下命令安装: pip install pandas")
        return None

    df = pd.DataFrame(data)

    if output_file:
        df.to_csv(output_file, index=False)
        print(f"数据已导出到: {output_file}")

    return df


def batch_gene_query(gene_list: List[str], delay: float = 0.5) -> Dict[str, Dict]:
    """
    使用速率限制批量查询多个基因。

    参数:
        gene_list: 基因符号列表
        delay: 请求间延迟（默认0.5秒）

    返回:
        将基因符号映射到基因数据的字典

    示例:
        >>> genes = ["CYP2D6", "CYP2C19", "CYP2C9", "TPMT"]
        >>> results = batch_gene_query(genes)
        >>> for gene, data in results.items():
        >>>     print(f"{gene}: {data['name']}")
    """
    results = {}

    print(f"正在查询 {len(gene_list)} 个基因，请求间延迟 {delay} 秒...")

    for gene in gene_list:
        print(f"正在获取: {gene}")
        data = get_gene_info(gene)
        if data:
            results[gene] = data
        time.sleep(delay)

    print(f"完成: {len(results)}/{len(gene_list)} 成功")
    return results


def find_actionable_gene_drug_pairs(cpic_level: str = "A") -> Optional[List[Dict]]:
    """
    查找所有具有CPIC指南的临床可操作基因-药物对。

    参数:
        cpic_level: CPIC推荐级别（A、B、C、D）

    返回:
        可操作基因-药物对列表

    示例:
        >>> # 获取所有A级推荐
        >>> actionable = find_actionable_gene_drug_pairs(cpic_level="A")
        >>> for pair in actionable:
        >>>     print(f"{pair['gene']} - {pair['drug']}")
    """
    url = f"{BASE_URL}geneDrugPair"
    params = {"cpicLevel": cpic_level}
    return safe_api_call(url, params)


# 使用示例
if __name__ == "__main__":
    print("ClinPGx API查询示例\n")

    # 示例 1: 获取基因信息
    print("=" * 60)
    print("示例 1: 获取CYP2D6基因信息")
    print("=" * 60)
    cyp2d6 = get_gene_info("CYP2D6")
    if cyp2d6:
        print(f"基因: {cyp2d6.get('symbol')}")
        print(f"名称: {cyp2d6.get('name')}")
        print()

    # 示例 2: 搜索药物
    print("=" * 60)
    print("示例 2: 搜索华法林")
    print("=" * 60)
    warfarin = get_drug_info("warfarin")
    if warfarin:
        for drug in warfarin[:1]:  # 显示第一个结果
            print(f"药物: {drug.get('name')}")
            print(f"ID: {drug.get('id')}")
        print()

    # 示例 3: 获取基因-药物对
    print("=" * 60)
    print("示例 3: 获取CYP2C19-氯吡格雷对")
    print("=" * 60)
    pair = get_gene_drug_pairs(gene="CYP2C19", drug="clopidogrel")
    if pair:
        print(f"找到 {len(pair)} 个基因-药物对")
        if len(pair) > 0:
            print(f"注释: {pair[0].get('sources', [])}")
        print()

    # 示例 4: 获取CPIC指南
    print("=" * 60)
    print("示例 4: 获取CYP2C19的CPIC指南")
    print("=" * 60)
    guidelines = get_cpic_guidelines(gene="CYP2C19")
    if guidelines:
        print(f"找到 {len(guidelines)} 个指南")
        for g in guidelines[:2]:  # 显示前2个
            print(f"  - {g.get('name')}")
        print()

    # 示例 5: 获取基因的等位基因
    print("=" * 60)
    print("示例 5: 获取CYP2D6等位基因")
    print("=" * 60)
    alleles = get_alleles("CYP2D6")
    if alleles:
        print(f"找到 {len(alleles)} 个等位基因")
        for allele in alleles[:3]:  # 显示前3个
            print(f"  - {allele.get('name')}: {allele.get('function')}")
        print()

    print("=" * 60)
    print("示例完成!")
    print("=" * 60)
