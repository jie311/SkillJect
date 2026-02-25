#!/usr/bin/env python3
"""
完整蛋白质分析流程

该脚本执行综合蛋白质分析流程：
1. UniProt搜索和标识符检索
2. FASTA序列检索
3. BLAST相似性搜索
4. KEGG通路发现
5. PSICQUIC相互作用映射
6. GO注释检索

使用方法：
    python protein_analysis_workflow.py PROTEIN_NAME EMAIL [--skip-blast]

示例：
    python protein_analysis_workflow.py ZAP70_HUMAN user@example.com
    python protein_analysis_workflow.py P43403 user@example.com --skip-blast

注意：BLAST搜索可能需要几分钟。使用 --skip-blast 跳过此步骤。
"""

import sys
import time
import argparse
from bioservices import UniProt, KEGG, NCBIblast, PSICQUIC, QuickGO


def search_protein(query):
    """搜索UniProt中的蛋白质并获取基本信息。"""
    print(f"\n{'='*70}")
    print("步骤 1: UniProt搜索")
    print(f"{'='*70}")

    u = UniProt(verbose=False)

    print(f"正在搜索: {query}")

    # 首先尝试直接检索（如果查询看起来像登录号）
    if len(query) == 6 and query[0] in "OPQ":
        try:
            entry = u.retrieve(query, frmt="tab")
            if entry:
                uniprot_id = query
                print(f"✓ 找到UniProt条目: {uniprot_id}")
                return u, uniprot_id
        except:
            pass

    # 否则进行搜索
    results = u.search(query, frmt="tab", columns="id,genes,organism,length,protein names", limit=5)

    if not results:
        print("✗ 未找到结果")
        return u, None

    lines = results.strip().split("\n")
    if len(lines) < 2:
        print("✗ 未找到条目")
        return u, None

    # 显示结果
    print(f"\n✓ 找到 {len(lines)-1} 个结果:")
    for i, line in enumerate(lines[1:], 1):
        fields = line.split("\t")
        print(f"  {i}. {fields[0]} - {fields[1]} ({fields[2]})")

    # 使用第一个结果
    first_entry = lines[1].split("\t")
    uniprot_id = first_entry[0]
    gene_names = first_entry[1] if len(first_entry) > 1 else "未知"
    organism = first_entry[2] if len(first_entry) > 2 else "未知"
    length = first_entry[3] if len(first_entry) > 3 else "未知"
    protein_name = first_entry[4] if len(first_entry) > 4 else "未知"

    print(f"\n使用第一个结果:")
    print(f"  UniProt ID: {uniprot_id}")
    print(f"  基因名称: {gene_names}")
    print(f"  生物体: {organism}")
    print(f"  长度: {length} 个氨基酸")
    print(f"  蛋白质: {protein_name}")

    return u, uniprot_id


def retrieve_sequence(uniprot, uniprot_id):
    """检索蛋白质的FASTA序列。"""
    print(f"\n{'='*70}")
    print("步骤 2: FASTA序列检索")
    print(f"{'='*70}")

    try:
        sequence = uniprot.retrieve(uniprot_id, frmt="fasta")

        if sequence:
            # 仅提取序列（移除头部）
            lines = sequence.strip().split("\n")
            header = lines[0]
            seq_only = "".join(lines[1:])

            print(f"✓ 已检索序列:")
            print(f"  头部: {header}")
            print(f"  长度: {len(seq_only)} 个残基")
            print(f"  前60个残基: {seq_only[:60]}...")

            return seq_only
        else:
            print("✗ 序列检索失败")
            return None

    except Exception as e:
        print(f"✗ 错误: {e}")
        return None


def run_blast(sequence, email, skip=False):
    """运行BLAST相似性搜索。"""
    print(f"\n{'='*70}")
    print("步骤 3: BLAST相似性搜索")
    print(f"{'='*70}")

    if skip:
        print("⊘ 已跳过（使用了--skip-blast标志）")
        return None

    if not email or "@" not in email:
        print("⊘ 已跳过（BLAST需要有效的电子邮件）")
        return None

    try:
        print(f"正在提交BLASTP任务...")
        print(f"  数据库: uniprotkb")
        print(f"  序列长度: {len(sequence)} 个氨基酸")

        s = NCBIblast(verbose=False)

        jobid = s.run(
            program="blastp",
            sequence=sequence,
            stype="protein",
            database="uniprotkb",
            email=email
        )

        print(f"✓ 任务已提交: {jobid}")
        print(f"  等待完成...")

        # 轮询完成状态
        max_wait = 300  # 5分钟
        start_time = time.time()

        while time.time() - start_time < max_wait:
            status = s.getStatus(jobid)
            elapsed = int(time.time() - start_time)
            print(f"  状态: {status} (已用时: {elapsed}秒)", end="\r")

            if status == "FINISHED":
                print(f"\n✓ BLAST在{elapsed}秒内完成")

                # 检索结果
                results = s.getResult(jobid, "out")

                # 解析并显示摘要
                lines = results.split("\n")
                print(f"\n  结果预览:")
                for line in lines[:20]:
                    if line.strip():
                        print(f"    {line}")

                return results

            elif status == "ERROR":
                print(f"\n✗ BLAST任务失败")
                return None

            time.sleep(5)

        print(f"\n✗ {max_wait}秒后超时")
        return None

    except Exception as e:
        print(f"✗ 错误: {e}")
        return None


def discover_pathways(uniprot, kegg, uniprot_id):
    """发现蛋白质的KEGG通路。"""
    print(f"\n{'='*70}")
    print("步骤 4: KEGG通路发现")
    print(f"{'='*70}")

    try:
        # 映射UniProt → KEGG
        print(f"正在将 {uniprot_id} 映射到KEGG...")
        kegg_mapping = uniprot.mapping(fr="UniProtKB_AC-ID", to="KEGG", query=uniprot_id)

        if not kegg_mapping or uniprot_id not in kegg_mapping:
            print("✗ 未找到KEGG映射")
            return []

        kegg_ids = kegg_mapping[uniprot_id]
        print(f"✓ KEGG ID: {kegg_ids}")

        # 获取第一个KEGG ID的通路
        kegg_id = kegg_ids[0]
        organism, gene_id = kegg_id.split(":")

        print(f"\n正在搜索 {kegg_id} 的通路...")
        pathways = kegg.get_pathway_by_gene(gene_id, organism)

        if not pathways:
            print("✗ 未找到通路")
            return []

        print(f"✓ 找到 {len(pathways)} 条通路:\n")

        # 获取通路名称
        pathway_info = []
        for pathway_id in pathways:
            try:
                entry = kegg.get(pathway_id)

                # 提取通路名称
                pathway_name = "未知"
                for line in entry.split("\n"):
                    if line.startswith("NAME"):
                        pathway_name = line.replace("NAME", "").strip()
                        break

                pathway_info.append((pathway_id, pathway_name))
                print(f"  • {pathway_id}: {pathway_name}")

            except Exception as e:
                print(f"  • {pathway_id}: [检索名称时出错]")

        return pathway_info

    except Exception as e:
        print(f"✗ 错误: {e}")
        return []


def find_interactions(protein_query):
    """通过PSICQUIC查找蛋白质-蛋白质相互作用。"""
    print(f"\n{'='*70}")
    print("步骤 5: 蛋白质-蛋白质相互作用")
    print(f"{'='*70}")

    try:
        p = PSICQUIC()

        # 尝试查询MINT数据库
        query = f"{protein_query} AND species:9606"
        print(f"正在查询MINT数据库...")
        print(f"  查询: {query}")

        results = p.query("mint", query)

        if not results:
            print("✗ 在MINT中未找到相互作用")
            return []

        # 解析PSI-MI TAB格式
        lines = results.strip().split("\n")
        print(f"✓ 找到 {len(lines)} 个相互作用:\n")

        # 显示前10个相互作用
        interactions = []
        for i, line in enumerate(lines[:10], 1):
            fields = line.split("\t")
            if len(fields) >= 12:
                protein_a = fields[4].split(":")[1] if ":" in fields[4] else fields[4]
                protein_b = fields[5].split(":")[1] if ":" in fields[5] else fields[5]
                interaction_type = fields[11]

                interactions.append((protein_a, protein_b, interaction_type))
                print(f"  {i}. {protein_a} ↔ {protein_b}")

        if len(lines) > 10:
            print(f"  ... 还有 {len(lines)-10} 个")

        return interactions

    except Exception as e:
        print(f"✗ 错误: {e}")
        return []


def get_go_annotations(uniprot_id):
    """检索GO注释。"""
    print(f"\n{'='*70}")
    print("步骤 6: 基因本体论注释")
    print(f"{'='*70}")

    try:
        g = QuickGO()

        print(f"正在检索 {uniprot_id} 的GO注释...")
        annotations = g.Annotation(protein=uniprot_id, format="tsv")

        if not annotations:
            print("✗ 未找到GO注释")
            return []

        lines = annotations.strip().split("\n")
        print(f"✓ 找到 {len(lines)-1} 个注释\n")

        # 按方面分组
        aspects = {"P": [], "F": [], "C": []}
        for line in lines[1:]:
            fields = line.split("\t")
            if len(fields) >= 9:
                go_id = fields[6]
                go_term = fields[7]
                go_aspect = fields[8]

                if go_aspect in aspects:
                    aspects[go_aspect].append((go_id, go_term))

        # 显示摘要
        print(f"  生物学过程 (P): {len(aspects['P'])} 个术语")
        for go_id, go_term in aspects['P'][:5]:
            print(f"    • {go_id}: {go_term}")
        if len(aspects['P']) > 5:
            print(f"    ... 还有 {len(aspects['P'])-5} 个")

        print(f"\n  分子功能 (F): {len(aspects['F'])} 个术语")
        for go_id, go_term in aspects['F'][:5]:
            print(f"    • {go_id}: {go_term}")
        if len(aspects['F']) > 5:
            print(f"    ... 还有 {len(aspects['F'])-5} 个")

        print(f"\n  细胞组分 (C): {len(aspects['C'])} 个术语")
        for go_id, go_term in aspects['C'][:5]:
            print(f"    • {go_id}: {go_term}")
        if len(aspects['C']) > 5:
            print(f"    ... 还有 {len(aspects['C'])-5} 个")

        return aspects

    except Exception as e:
        print(f"✗ 错误: {e}")
        return {}


def main():
    """主流程。"""
    parser = argparse.ArgumentParser(
        description="使用BioServices进行完整蛋白质分析流程",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python protein_analysis_workflow.py ZAP70_HUMAN user@example.com
  python protein_analysis_workflow.py P43403 user@example.com --skip-blast
        """
    )
    parser.add_argument("protein", help="蛋白质名称或UniProt ID")
    parser.add_argument("email", help="电子邮件地址（BLAST需要）")
    parser.add_argument("--skip-blast", action="store_true",
                       help="跳过BLAST搜索（更快）")

    args = parser.parse_args()

    print("=" * 70)
    print("BIOSERVICES: 完整蛋白质分析流程")
    print("=" * 70)

    # 步骤 1: 搜索蛋白质
    uniprot, uniprot_id = search_protein(args.protein)
    if not uniprot_id:
        print("\n✗ 未找到蛋白质。退出。")
        sys.exit(1)

    # 步骤 2: 检索序列
    sequence = retrieve_sequence(uniprot, uniprot_id)
    if not sequence:
        print("\n⚠ 警告: 无法检索序列")

    # 步骤 3: BLAST搜索
    if sequence:
        blast_results = run_blast(sequence, args.email, args.skip_blast)

    # 步骤 4: 通路发现
    kegg = KEGG()
    pathways = discover_pathways(uniprot, kegg, uniprot_id)

    # 步骤 5: 相互作用映射
    interactions = find_interactions(args.protein)

    # 步骤 6: GO注释
    go_terms = get_go_annotations(uniprot_id)

    # 摘要
    print(f"\n{'='*70}")
    print("流程摘要")
    print(f"{'='*70}")
    print(f"  蛋白质: {args.protein}")
    print(f"  UniProt ID: {uniprot_id}")
    print(f"  序列: {'✓' if sequence else '✗'}")
    print(f"  BLAST: {'✓' if not args.skip_blast and sequence else '⊘'}")
    print(f"  通路: 找到 {len(pathways)} 条")
    print(f"  相互作用: 找到 {len(interactions)} 个")
    print(f"  GO注释: 找到 {sum(len(v) for v in go_terms.values())} 个")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
