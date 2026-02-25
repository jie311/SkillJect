#!/usr/bin/env python3
"""
KEGG通路网络分析

该脚本分析某个生物的所有通路并提取：
- 通路大小（基因数量）
- 蛋白质-蛋白质相互作用
- 相互作用类型分布
- 各种格式的网络数据（CSV、SIF）

使用方法：
    python pathway_analysis.py ORGANISM OUTPUT_DIR [--limit N]

示例：
    python pathway_analysis.py hsa ./human_pathways
    python pathway_analysis.py mmu ./mouse_pathways --limit 50

生物体代码：
    hsa = 智人（人类）
    mmu = 小家鼠（小鼠）
    dme = 黑腹果蝇
    sce = 酿酒酵母
    eco = 大肠杆菌
"""

import sys
import os
import argparse
import csv
from collections import Counter
from bioservices import KEGG


def get_all_pathways(kegg, organism):
    """获取生物体的所有通路ID。"""
    print(f"\n正在获取 {organism} 的通路...")

    kegg.organism = organism
    pathway_ids = kegg.pathwayIds

    print(f"✓ 找到 {len(pathway_ids)} 条通路")

    return pathway_ids


def analyze_pathway(kegg, pathway_id):
    """分析单个通路的大小和相互作用。"""
    try:
        # 解析KGML通路
        kgml = kegg.parse_kgml_pathway(pathway_id)

        entries = kgml.get('entries', [])
        relations = kgml.get('relations', [])

        # 统计关系类型
        relation_types = Counter()
        for rel in relations:
            rel_type = rel.get('name', 'unknown')
            relation_types[rel_type] += 1

        # 获取通路名称
        try:
            entry = kegg.get(pathway_id)
            pathway_name = "未知"
            for line in entry.split("\n"):
                if line.startswith("NAME"):
                    pathway_name = line.replace("NAME", "").strip()
                    break
        except:
            pathway_name = "未知"

        result = {
            'pathway_id': pathway_id,
            'pathway_name': pathway_name,
            'num_entries': len(entries),
            'num_relations': len(relations),
            'relation_types': dict(relation_types),
            'entries': entries,
            'relations': relations
        }

        return result

    except Exception as e:
        print(f"  ✗ 分析 {pathway_id} 时出错: {e}")
        return None


def analyze_all_pathways(kegg, pathway_ids, limit=None):
    """分析所有通路。"""
    if limit:
        pathway_ids = pathway_ids[:limit]
        print(f"\n⚠ 将分析限制为前 {limit} 条通路")

    print(f"\n正在分析 {len(pathway_ids)} 条通路...")

    results = []
    for i, pathway_id in enumerate(pathway_ids, 1):
        print(f"  [{i}/{len(pathway_ids)}] {pathway_id}", end="\r")

        result = analyze_pathway(kegg, pathway_id)
        if result:
            results.append(result)

    print(f"\n✓ 成功分析了 {len(results)}/{len(pathway_ids)} 条通路")

    return results


def save_pathway_summary(results, output_file):
    """将通路摘要保存到CSV。"""
    print(f"\n正在保存通路摘要到 {output_file}...")

    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)

        # 表头
        writer.writerow([
            'Pathway_ID',
            'Pathway_Name',
            'Num_Genes',
            'Num_Interactions',
            'Activation',
            'Inhibition',
            'Phosphorylation',
            'Binding',
            'Other'
        ])

        # 数据
        for result in results:
            rel_types = result['relation_types']

            writer.writerow([
                result['pathway_id'],
                result['pathway_name'],
                result['num_entries'],
                result['num_relations'],
                rel_types.get('activation', 0),
                rel_types.get('inhibition', 0),
                rel_types.get('phosphorylation', 0),
                rel_types.get('binding/association', 0),
                sum(v for k, v in rel_types.items()
                    if k not in ['activation', 'inhibition', 'phosphorylation', 'binding/association'])
            ])

    print(f"✓ 摘要已保存")


def save_interactions_sif(results, output_file):
    """以SIF格式保存所有相互作用。"""
    print(f"\n正在保存相互作用到 {output_file}...")

    with open(output_file, 'w') as f:
        for result in results:
            pathway_id = result['pathway_id']

            for rel in result['relations']:
                entry1 = rel.get('entry1', '')
                entry2 = rel.get('entry2', '')
                interaction_type = rel.get('name', 'interaction')

                # 写入SIF格式: source\tinteraction\ttarget
                f.write(f"{entry1}\t{interaction_type}\t{entry2}\n")

    print(f"✓ 相互作用已保存")


def save_detailed_pathway_info(results, output_dir):
    """保存每条通路的详细信息。"""
    print(f"\n正在保存详细通路文件到 {output_dir}/pathways/...")

    pathway_dir = os.path.join(output_dir, "pathways")
    os.makedirs(pathway_dir, exist_ok=True)

    for result in results:
        pathway_id = result['pathway_id'].replace(":", "_")
        filename = os.path.join(pathway_dir, f"{pathway_id}_interactions.csv")

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Source', 'Target', 'Interaction_Type', 'Link_Type'])

            for rel in result['relations']:
                writer.writerow([
                    rel.get('entry1', ''),
                    rel.get('entry2', ''),
                    rel.get('name', 'unknown'),
                    rel.get('link', 'unknown')
                ])

    print(f"✓ 已保存 {len(results)} 条通路的详细文件")


def print_statistics(results):
    """打印分析统计信息。"""
    print(f"\n{'='*70}")
    print("通路分析统计")
    print(f"{'='*70}")

    # 总体统计
    total_pathways = len(results)
    total_interactions = sum(r['num_relations'] for r in results)
    total_genes = sum(r['num_entries'] for r in results)

    print(f"\n总体:")
    print(f"  总通路数: {total_pathways}")
    print(f"  总基因/蛋白质数: {total_genes}")
    print(f"  总相互作用数: {total_interactions}")

    # 最大的通路
    print(f"\n最大的通路（按基因计数）:")
    sorted_by_size = sorted(results, key=lambda x: x['num_entries'], reverse=True)
    for i, result in enumerate(sorted_by_size[:10], 1):
        print(f"  {i}. {result['pathway_id']}: {result['num_entries']} 个基因")
        print(f"     {result['pathway_name']}")

    # 连接最多的通路
    print(f"\n连接最多的通路（按相互作用）:")
    sorted_by_connections = sorted(results, key=lambda x: x['num_relations'], reverse=True)
    for i, result in enumerate(sorted_by_connections[:10], 1):
        print(f"  {i}. {result['pathway_id']}: {result['num_relations']} 个相互作用")
        print(f"     {result['pathway_name']}")

    # 相互作用类型分布
    print(f"\n相互作用类型分布:")
    all_types = Counter()
    for result in results:
        for rel_type, count in result['relation_types'].items():
            all_types[rel_type] += count

    for rel_type, count in all_types.most_common():
        percentage = (count / total_interactions) * 100 if total_interactions > 0 else 0
        print(f"  {rel_type}: {count} ({percentage:.1f}%)")


def main():
    """主分析流程。"""
    parser = argparse.ArgumentParser(
        description="分析生物体的KEGG通路",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python pathway_analysis.py hsa ./human_pathways
  python pathway_analysis.py mmu ./mouse_pathways --limit 50

生物体代码:
  hsa = 智人（人类）
  mmu = 小家鼠（小鼠）
  dme = 黑腹果蝇
  sce = 酿酒酵母
  eco = 大肠杆菌
        """
    )
    parser.add_argument("organism", help="KEGG生物体代码（如：hsa、mmu）")
    parser.add_argument("output_dir", help="结果输出目录")
    parser.add_argument("--limit", type=int, default=None,
                       help="限制分析前N条通路")

    args = parser.parse_args()

    print("=" * 70)
    print("BIOSERVICES: KEGG通路网络分析")
    print("=" * 70)

    # 创建输出目录
    os.makedirs(args.output_dir, exist_ok=True)

    # 初始化KEGG
    kegg = KEGG()

    # 获取所有通路
    pathway_ids = get_all_pathways(kegg, args.organism)

    if not pathway_ids:
        print(f"\n✗ 未找到 {args.organism} 的通路")
        sys.exit(1)

    # 分析通路
    results = analyze_all_pathways(kegg, pathway_ids, args.limit)

    if not results:
        print("\n✗ 没有通路被成功分析")
        sys.exit(1)

    # 打印统计信息
    print_statistics(results)

    # 保存结果
    summary_file = os.path.join(args.output_dir, "pathway_summary.csv")
    save_pathway_summary(results, summary_file)

    sif_file = os.path.join(args.output_dir, "all_interactions.sif")
    save_interactions_sif(results, sif_file)

    save_detailed_pathway_info(results, args.output_dir)

    # 最终摘要
    print(f"\n{'='*70}")
    print("输出文件")
    print(f"{'='*70}")
    print(f"  摘要: {summary_file}")
    print(f"  相互作用: {sif_file}")
    print(f"  详细信息: {args.output_dir}/pathways/")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
