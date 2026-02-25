#!/usr/bin/env python3
"""
化合物跨数据库搜索

该脚本按名称搜索化合物，并从多个数据库检索标识符：
- KEGG Compound
- ChEBI
- ChEMBL（通过UniChem）
- 基本化合物属性

使用方法：
    python compound_cross_reference.py COMPOUND_NAME [--output FILE]

示例：
    python compound_cross_reference.py Geldanamycin
    python compound_cross_reference.py "Adenosine triphosphate"
    python compound_cross_reference.py Aspirin --output aspirin_info.txt
"""

import sys
import argparse
from bioservices import KEGG, UniChem, ChEBI, ChEMBL


def search_kegg_compound(compound_name):
    """在KEGG中按名称搜索化合物。"""
    print(f"\n{'='*70}")
    print("步骤 1: KEGG化合物搜索")
    print(f"{'='*70}")

    k = KEGG()

    print(f"正在在KEGG中搜索: {compound_name}")

    try:
        results = k.find("compound", compound_name)

        if not results or not results.strip():
            print(f"✗ 在KEGG中未找到结果")
            return k, None

        # 解析结果
        lines = results.strip().split("\n")
        print(f"✓ 找到 {len(lines)} 个结果:\n")

        for i, line in enumerate(lines[:5], 1):
            parts = line.split("\t")
            kegg_id = parts[0]
            description = parts[1] if len(parts) > 1 else "无描述"
            print(f"  {i}. {kegg_id}: {description}")

        # 使用第一个结果
        first_result = lines[0].split("\t")
        kegg_id = first_result[0].replace("cpd:", "")

        print(f"\n使用: {kegg_id}")

        return k, kegg_id

    except Exception as e:
        print(f"✗ 错误: {e}")
        return k, None


def get_kegg_info(kegg, kegg_id):
    """检索详细的KEGG化合物信息。"""
    print(f"\n{'='*70}")
    print("步骤 2: KEGG化合物详细信息")
    print(f"{'='*70}")

    try:
        print(f"正在检索 {kegg_id} 的KEGG条目...")

        entry = kegg.get(f"cpd:{kegg_id}")

        if not entry:
            print("✗ 条目检索失败")
            return None

        # 解析条目
        compound_info = {
            'kegg_id': kegg_id,
            'name': None,
            'formula': None,
            'exact_mass': None,
            'mol_weight': None,
            'chebi_id': None,
            'pathways': []
        }

        current_section = None

        for line in entry.split("\n"):
            if line.startswith("NAME"):
                compound_info['name'] = line.replace("NAME", "").strip().rstrip(";")

            elif line.startswith("FORMULA"):
                compound_info['formula'] = line.replace("FORMULA", "").strip()

            elif line.startswith("EXACT_MASS"):
                compound_info['exact_mass'] = line.replace("EXACT_MASS", "").strip()

            elif line.startswith("MOL_WEIGHT"):
                compound_info['mol_weight'] = line.replace("MOL_WEIGHT", "").strip()

            elif "ChEBI:" in line:
                parts = line.split("ChEBI:")
                if len(parts) > 1:
                    compound_info['chebi_id'] = parts[1].strip().split()[0]

            elif line.startswith("PATHWAY"):
                current_section = "pathway"
                pathway = line.replace("PATHWAY", "").strip()
                if pathway:
                    compound_info['pathways'].append(pathway)

            elif current_section == "pathway" and line.startswith("            "):
                pathway = line.strip()
                if pathway:
                    compound_info['pathways'].append(pathway)

            elif line.startswith(" ") and not line.startswith("            "):
                current_section = None

        # 显示信息
        print(f"\n✓ KEGG化合物信息:")
        print(f"  ID: {compound_info['kegg_id']}")
        print(f"  名称: {compound_info['name']}")
        print(f"  分子式: {compound_info['formula']}")
        print(f"  精确质量: {compound_info['exact_mass']}")
        print(f"  分子量: {compound_info['mol_weight']}")

        if compound_info['chebi_id']:
            print(f"  ChEBI ID: {compound_info['chebi_id']}")

        if compound_info['pathways']:
            print(f"  通路: 找到 {len(compound_info['pathways'])} 条")

        return compound_info

    except Exception as e:
        print(f"✗ 错误: {e}")
        return None


def get_chembl_id(kegg_id):
    """通过UniChem将KEGG ID映射到ChEMBL。"""
    print(f"\n{'='*70}")
    print("步骤 3: ChEMBL映射（通过UniChem）")
    print(f"{'='*70}")

    try:
        u = UniChem()

        print(f"正在将 KEGG:{kegg_id} 映射到ChEMBL...")

        chembl_id = u.get_compound_id_from_kegg(kegg_id)

        if chembl_id:
            print(f"✓ ChEMBL ID: {chembl_id}")
            return chembl_id
        else:
            print("✗ 未找到ChEMBL映射")
            return None

    except Exception as e:
        print(f"✗ 错误: {e}")
        return None


def get_chebi_info(chebi_id):
    """检索ChEBI化合物信息。"""
    print(f"\n{'='*70}")
    print("步骤 4: ChEBI详细信息")
    print(f"{'='*70}")

    if not chebi_id:
        print("⊘ 没有可用的ChEBI ID")
        return None

    try:
        c = ChEBI()

        print(f"正在检索 {chebi_id} 的ChEBI条目...")

        # 确保格式正确
        if not chebi_id.startswith("CHEBI:"):
            chebi_id = f"CHEBI:{chebi_id}"

        entity = c.getCompleteEntity(chebi_id)

        if entity:
            print(f"\n✓ ChEBI信息:")
            print(f"  ID: {entity.chebiId}")
            print(f"  名称: {entity.chebiAsciiName}")

            if hasattr(entity, 'Formulae') and entity.Formulae:
                print(f"  分子式: {entity.Formulae}")

            if hasattr(entity, 'mass') and entity.mass:
                print(f"  质量: {entity.mass}")

            if hasattr(entity, 'charge') and entity.charge:
                print(f"  电荷: {entity.charge}")

            return {
                'chebi_id': entity.chebiId,
                'name': entity.chebiAsciiName,
                'formula': entity.Formulae if hasattr(entity, 'Formulae') else None,
                'mass': entity.mass if hasattr(entity, 'mass') else None
            }
        else:
            print("✗ ChEBI条目检索失败")
            return None

    except Exception as e:
        print(f"✗ 错误: {e}")
        return None


def get_chembl_info(chembl_id):
    """检索ChEMBL化合物信息。"""
    print(f"\n{'='*70}")
    print("步骤 5: ChEMBL详细信息")
    print(f"{'='*70}")

    if not chembl_id:
        print("⊘ 没有可用的ChEMBL ID")
        return None

    try:
        c = ChEMBL()

        print(f"正在检索 {chembl_id} 的ChEMBL条目...")

        compound = c.get_compound_by_chemblId(chembl_id)

        if compound:
            print(f"\n✓ ChEMBL信息:")
            print(f"  ID: {chembl_id}")

            if 'pref_name' in compound and compound['pref_name']:
                print(f"  首选名称: {compound['pref_name']}")

            if 'molecule_properties' in compound:
                props = compound['molecule_properties']

                if 'full_mwt' in props:
                    print(f"  分子量: {props['full_mwt']}")

                if 'alogp' in props:
                    print(f"  LogP: {props['alogp']}")

                if 'hba' in props:
                    print(f"  氢键受体: {props['hba']}")

                if 'hbd' in props:
                    print(f"  氢键供体: {props['hbd']}")

            if 'molecule_structures' in compound:
                structs = compound['molecule_structures']

                if 'canonical_smiles' in structs:
                    smiles = structs['canonical_smiles']
                    print(f"  SMILES: {smiles[:60]}{'...' if len(smiles) > 60 else ''}")

            return compound
        else:
            print("✗ ChEMBL条目检索失败")
            return None

    except Exception as e:
        print(f"✗ 错误: {e}")
        return None


def save_results(compound_name, kegg_info, chembl_id, output_file):
    """将结果保存到文件。"""
    print(f"\n{'='*70}")
    print(f"正在保存结果到 {output_file}")
    print(f"{'='*70}")

    with open(output_file, 'w') as f:
        f.write("=" * 70 + "\n")
        f.write(f"化合物交叉引用报告: {compound_name}\n")
        f.write("=" * 70 + "\n\n")

        # KEGG信息
        if kegg_info:
            f.write("KEGG化合物\n")
            f.write("-" * 70 + "\n")
            f.write(f"ID: {kegg_info['kegg_id']}\n")
            f.write(f"名称: {kegg_info['name']}\n")
            f.write(f"分子式: {kegg_info['formula']}\n")
            f.write(f"精确质量: {kegg_info['exact_mass']}\n")
            f.write(f"分子量: {kegg_info['mol_weight']}\n")
            f.write(f"通路: 找到 {len(kegg_info['pathways'])} 条\n")
            f.write("\n")

        # 数据库ID
        f.write("跨数据库标识符\n")
        f.write("-" * 70 + "\n")
        if kegg_info:
            f.write(f"KEGG: {kegg_info['kegg_id']}\n")
            if kegg_info['chebi_id']:
                f.write(f"ChEBI: {kegg_info['chebi_id']}\n")
        if chembl_id:
            f.write(f"ChEMBL: {chembl_id}\n")
        f.write("\n")

    print(f"✓ 结果已保存")


def main():
    """主流程。"""
    parser = argparse.ArgumentParser(
        description="在多个数据库中搜索化合物",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python compound_cross_reference.py Geldanamycin
  python compound_cross_reference.py "Adenosine triphosphate"
  python compound_cross_reference.py Aspirin --output aspirin_info.txt
        """
    )
    parser.add_argument("compound", help="要搜索的化合物名称")
    parser.add_argument("--output", default=None,
                       help="结果输出文件（可选）")

    args = parser.parse_args()

    print("=" * 70)
    print("BIOSERVICES: 化合物跨数据库搜索")
    print("=" * 70)

    # 步骤 1: 搜索KEGG
    kegg, kegg_id = search_kegg_compound(args.compound)
    if not kegg_id:
        print("\n✗ 未找到化合物。退出。")
        sys.exit(1)

    # 步骤 2: 获取KEGG详细信息
    kegg_info = get_kegg_info(kegg, kegg_id)

    # 步骤 3: 映射到ChEMBL
    chembl_id = get_chembl_id(kegg_id)

    # 步骤 4: 获取ChEBI详细信息
    chebi_info = None
    if kegg_info and kegg_info['chebi_id']:
        chebi_info = get_chebi_info(kegg_info['chebi_id'])

    # 步骤 5: 获取ChEMBL详细信息
    chembl_info = None
    if chembl_id:
        chembl_info = get_chembl_info(chembl_id)

    # 摘要
    print(f"\n{'='*70}")
    print("摘要")
    print(f"{'='*70}")
    print(f"  化合物: {args.compound}")
    if kegg_info:
        print(f"  KEGG ID: {kegg_info['kegg_id']}")
        if kegg_info['chebi_id']:
            print(f"  ChEBI ID: {kegg_info['chebi_id']}")
    if chembl_id:
        print(f"  ChEMBL ID: {chembl_id}")
    print(f"{'='*70}")

    # 如果需要则保存到文件
    if args.output:
        save_results(args.compound, kegg_info, chembl_id, args.output)


if __name__ == "__main__":
    main()
