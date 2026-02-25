#!/usr/bin/env python3
"""
批量标识符转换器

该脚本使用UniProt的映射服务在生物数据库之间转换多个标识符。
支持批量处理、自动分块和错误处理。

使用方法：
    python batch_id_converter.py INPUT_FILE --from DB1 --to DB2 [选项]

示例：
    python batch_id_converter.py uniprot_ids.txt --from UniProtKB_AC-ID --to KEGG
    python batch_id_converter.py gene_ids.txt --from GeneID --to UniProtKB --output mapping.csv
    python batch_id_converter.py ids.txt --from UniProtKB_AC-ID --to Ensembl --chunk-size 50

输入文件格式：
    每行一个标识符（纯文本）

常用数据库代码：
    UniProtKB_AC-ID  - UniProt登录号/ID
    KEGG             - KEGG基因ID
    GeneID           - NCBI Gene（Entrez）ID
    Ensembl          - Ensembl基因ID
    Ensembl_Protein  - Ensembl蛋白质ID
    RefSeq_Protein   - RefSeq蛋白质ID
    PDB              - 蛋白质数据库ID
    HGNC             - 人类基因符号
    GO               - 基因本体论ID
"""

import sys
import argparse
import csv
import time
from bioservices import UniProt


# 常用数据库代码映射
DATABASE_CODES = {
    'uniprot': 'UniProtKB_AC-ID',
    'uniprotkb': 'UniProtKB_AC-ID',
    'kegg': 'KEGG',
    'geneid': 'GeneID',
    'entrez': 'GeneID',
    'ensembl': 'Ensembl',
    'ensembl_protein': 'Ensembl_Protein',
    'ensembl_transcript': 'Ensembl_Transcript',
    'refseq': 'RefSeq_Protein',
    'refseq_protein': 'RefSeq_Protein',
    'pdb': 'PDB',
    'hgnc': 'HGNC',
    'mgi': 'MGI',
    'go': 'GO',
    'pfam': 'Pfam',
    'interpro': 'InterPro',
    'reactome': 'Reactome',
    'string': 'STRING',
    'biogrid': 'BioGRID'
}


def normalize_database_code(code):
    """将数据库代码规范化为官方格式。"""
    # 首先尝试精确匹配
    if code in DATABASE_CODES.values():
        return code

    # 尝试小写查找
    lowercase = code.lower()
    if lowercase in DATABASE_CODES:
        return DATABASE_CODES[lowercase]

    # 如果未找到则原样返回（可能仍然有效）
    return code


def read_ids_from_file(filename):
    """从文件中读取标识符（每行一个）。"""
    print(f"正在从 {filename} 读取标识符...")

    ids = []
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                ids.append(line)

    print(f"✓ 已读取 {len(ids)} 个标识符")

    return ids


def batch_convert(ids, from_db, to_db, chunk_size=100, delay=0.5):
    """使用自动分块和错误处理转换ID。"""
    print(f"\n正在转换 {len(ids)} 个ID:")
    print(f"  从: {from_db}")
    print(f"  到: {to_db}")
    print(f"  分块大小: {chunk_size}")
    print()

    u = UniProt(verbose=False)
    all_results = {}
    failed_ids = []

    total_chunks = (len(ids) + chunk_size - 1) // chunk_size

    for i in range(0, len(ids), chunk_size):
        chunk = ids[i:i+chunk_size]
        chunk_num = (i // chunk_size) + 1

        query = ",".join(chunk)

        try:
            print(f"  [{chunk_num}/{total_chunks}] 正在处理 {len(chunk)} 个ID...", end=" ")

            results = u.mapping(fr=from_db, to=to_db, query=query)

            if results:
                all_results.update(results)
                mapped_count = len([v for v in results.values() if v])
                print(f"✓ 已映射: {mapped_count}/{len(chunk)}")
            else:
                print(f"✗ 未返回映射")
                failed_ids.extend(chunk)

            # 速率限制
            if delay > 0 and i + chunk_size < len(ids):
                time.sleep(delay)

        except Exception as e:
            print(f"✗ 错误: {e}")

            # 尝试单独处理失败的分块中的ID
            print(f"    正在重试单个ID...")
            for single_id in chunk:
                try:
                    result = u.mapping(fr=from_db, to=to_db, query=single_id)
                    if result:
                        all_results.update(result)
                        print(f"      ✓ {single_id}")
                    else:
                        failed_ids.append(single_id)
                        print(f"      ✗ {single_id} - 无映射")
                except Exception as e2:
                    failed_ids.append(single_id)
                    print(f"      ✗ {single_id} - {e2}")

                time.sleep(0.2)

    # 将缺失的ID添加到结果中（标记为失败）
    for id_ in ids:
        if id_ not in all_results:
            all_results[id_] = None

    print(f"\n✓ 转换完成:")
    print(f"  总计: {len(ids)}")
    print(f"  已映射: {len([v for v in all_results.values() if v])}")
    print(f"  失败: {len(failed_ids)}")

    return all_results, failed_ids


def save_mapping_csv(mapping, output_file, from_db, to_db):
    """将映射结果保存到CSV。"""
    print(f"\n正在保存结果到 {output_file}...")

    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)

        # 表头
        writer.writerow(['Source_ID', 'Source_DB', 'Target_IDs', 'Target_DB', 'Mapping_Status'])

        # 数据
        for source_id, target_ids in sorted(mapping.items()):
            if target_ids:
                target_str = ";".join(target_ids)
                status = "成功"
            else:
                target_str = ""
                status = "失败"

            writer.writerow([source_id, from_db, target_str, to_db, status])

    print(f"✓ 结果已保存")


def save_failed_ids(failed_ids, output_file):
    """将失败的ID保存到文件。"""
    if not failed_ids:
        return

    print(f"\n正在保存失败的ID到 {output_file}...")

    with open(output_file, 'w') as f:
        for id_ in failed_ids:
            f.write(f"{id_}\n")

    print(f"✓ 已保存 {len(failed_ids)} 个失败的ID")


def print_mapping_summary(mapping, from_db, to_db):
    """打印映射结果摘要。"""
    print(f"\n{'='*70}")
    print("映射摘要")
    print(f"{'='*70}")

    total = len(mapping)
    mapped = len([v for v in mapping.values() if v])
    failed = total - mapped

    print(f"\n源数据库: {from_db}")
    print(f"目标数据库: {to_db}")
    print(f"\n总标识符数: {total}")
    print(f"成功映射: {mapped} ({mapped/total*100:.1f}%)")
    print(f"映射失败: {failed} ({failed/total*100:.1f}%)")

    # 显示一些示例
    if mapped > 0:
        print(f"\n示例映射（前5个）:")
        count = 0
        for source_id, target_ids in mapping.items():
            if target_ids:
                target_str = ", ".join(target_ids[:3])
                if len(target_ids) > 3:
                    target_str += f" ... 还有{len(target_ids)-3}个"
                print(f"  {source_id} → {target_str}")
                count += 1
                if count >= 5:
                    break

    # 显示多重映射统计
    multiple_mappings = [v for v in mapping.values() if v and len(v) > 1]
    if multiple_mappings:
        print(f"\n多重目标映射: {len(multiple_mappings)} 个ID")
        print(f"  （这些源ID映射到多个目标ID）")

    print(f"{'='*70}")


def list_common_databases():
    """打印常用数据库代码列表。"""
    print("\n常用数据库代码:")
    print("-" * 70)
    print(f"{'别名':<20} {'官方代码':<30}")
    print("-" * 70)

    for alias, code in sorted(DATABASE_CODES.items()):
        if alias != code.lower():
            print(f"{alias:<20} {code:<30}")

    print("-" * 70)
    print("\n注意：还支持许多其他数据库代码。")
    print("请参阅UniProt文档获取完整列表。")


def main():
    """主转换流程。"""
    parser = argparse.ArgumentParser(
        description="在数据库之间批量转换生物标识符",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python batch_id_converter.py uniprot_ids.txt --from UniProtKB_AC-ID --to KEGG
  python batch_id_converter.py ids.txt --from GeneID --to UniProtKB -o mapping.csv
  python batch_id_converter.py ids.txt --from uniprot --to ensembl --chunk-size 50

常用数据库代码:
  UniProtKB_AC-ID, KEGG, GeneID, Ensembl, Ensembl_Protein,
  RefSeq_Protein, PDB, HGNC, GO, Pfam, InterPro, Reactome

使用 --list-databases 查看所有支持的别名。
        """
    )
    parser.add_argument("input_file", help="包含ID的输入文件（每行一个）")
    parser.add_argument("--from", dest="from_db", required=True,
                       help="源数据库代码")
    parser.add_argument("--to", dest="to_db", required=True,
                       help="目标数据库代码")
    parser.add_argument("-o", "--output", default=None,
                       help="输出CSV文件（默认：mapping_results.csv）")
    parser.add_argument("--chunk-size", type=int, default=100,
                       help="每批ID数量（默认：100）")
    parser.add_argument("--delay", type=float, default=0.5,
                       help="批次间延迟（秒）（默认：0.5）")
    parser.add_argument("--save-failed", action="store_true",
                       help="将失败的ID保存到单独文件")
    parser.add_argument("--list-databases", action="store_true",
                       help="列出常用数据库代码并退出")

    args = parser.parse_args()

    # 列出数据库并退出
    if args.list_databases:
        list_common_databases()
        sys.exit(0)

    print("=" * 70)
    print("BIOSERVICES: 批量标识符转换器")
    print("=" * 70)

    # 规范化数据库代码
    from_db = normalize_database_code(args.from_db)
    to_db = normalize_database_code(args.to_db)

    if from_db != args.from_db:
        print(f"\n注意: 已将 '{args.from_db}' 规范化为 '{from_db}'")
    if to_db != args.to_db:
        print(f"注意: 已将 '{args.to_db}' 规范化为 '{to_db}'")

    # 读取输入ID
    try:
        ids = read_ids_from_file(args.input_file)
    except Exception as e:
        print(f"\n✗ 读取输入文件时出错: {e}")
        sys.exit(1)

    if not ids:
        print("\n✗ 输入文件中未找到ID")
        sys.exit(1)

    # 执行转换
    mapping, failed_ids = batch_convert(
        ids,
        from_db,
        to_db,
        chunk_size=args.chunk_size,
        delay=args.delay
    )

    # 打印摘要
    print_mapping_summary(mapping, from_db, to_db)

    # 保存结果
    output_file = args.output or "mapping_results.csv"
    save_mapping_csv(mapping, output_file, from_db, to_db)

    # 如果需要则保存失败的ID
    if args.save_failed and failed_ids:
        failed_file = output_file.replace(".csv", "_failed.txt")
        save_failed_ids(failed_ids, failed_file)

    print(f"\n✓ 完成!")


if __name__ == "__main__":
    main()
