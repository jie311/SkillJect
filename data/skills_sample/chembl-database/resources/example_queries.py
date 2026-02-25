#!/usr/bin/env python3
"""
ChEMBL数据库查询示例

该脚本演示了使用chembl_webresource_client Python库
查询ChEMBL数据库的常见模式。

要求:
    pip install chembl_webresource_client
    pip install pandas（可选，用于数据处理）
"""

from chembl_webresource_client.new_client import new_client


def get_molecule_info(chembl_id):
    """
    通过ChEMBL ID检索分子的详细信息。

    参数:
        chembl_id: ChEMBL标识符（如'CHEMBL25'）

    返回:
        包含分子信息的字典
    """
    molecule = new_client.molecule
    return molecule.get(chembl_id)


def search_molecules_by_name(name_pattern):
    """
    按名称模式搜索分子。

    参数:
        name_pattern: 要搜索的名称或模式

    返回:
        匹配的分子列表
    """
    molecule = new_client.molecule
    results = molecule.filter(pref_name__icontains=name_pattern)
    return list(results)


def find_molecules_by_properties(max_mw=500, min_logp=None, max_logp=None):
    """
    根据物理化学性质查找分子。

    参数:
        max_mw: 最大分子量
        min_logp: 最小LogP值
        max_logp: 最大LogP值

    返回:
        匹配的分子列表
    """
    molecule = new_client.molecule

    filters = {
        'molecule_properties__mw_freebase__lte': max_mw
    }

    if min_logp is not None:
        filters['molecule_properties__alogp__gte'] = min_logp
    if max_logp is not None:
        filters['molecule_properties__alogp__lte'] = max_logp

    results = molecule.filter(**filters)
    return list(results)


def get_target_info(target_chembl_id):
    """
    检索生物靶点的信息。

    参数:
        target_chembl_id: ChEMBL靶点标识符（如'CHEMBL240'）

    返回:
        包含靶点信息的字典
    """
    target = new_client.target
    return target.get(target_chembl_id)


def search_targets_by_name(target_name):
    """
    按名称或关键词搜索靶点。

    参数:
        target_name: 靶点名称或关键词（如'kinase'、'EGFR'）

    返回:
        匹配的靶点列表
    """
    target = new_client.target
    results = target.filter(
        target_type='SINGLE PROTEIN',
        pref_name__icontains=target_name
    )
    return list(results)


def get_bioactivity_data(target_chembl_id, activity_type='IC50', max_value=100):
    """
    检索特定靶点的生物活性数据。

    参数:
        target_chembl_id: ChEMBL靶点标识符
        activity_type: 活性类型（IC50、Ki、EC50等）
        max_value: 最大活性值（nM）

    返回:
        活性记录列表
    """
    activity = new_client.activity
    results = activity.filter(
        target_chembl_id=target_chembl_id,
        standard_type=activity_type,
        standard_value__lte=max_value,
        standard_units='nM'
    )
    return list(results)


def find_similar_compounds(smiles, similarity_threshold=85):
    """
    查找与查询结构相似的化合物。

    参数:
        smiles: 查询分子的SMILES字符串
        similarity_threshold: 最小相似度百分比（0-100）

    返回:
        相似化合物列表
    """
    similarity = new_client.similarity
    results = similarity.filter(
        smiles=smiles,
        similarity=similarity_threshold
    )
    return list(results)


def substructure_search(smiles):
    """
    搜索包含特定子结构的化合物。

    参数:
        smiles: 子结构的SMILES字符串

    返回:
        包含该子结构的化合物列表
    """
    substructure = new_client.substructure
    results = substructure.filter(smiles=smiles)
    return list(results)


def get_drug_info(molecule_chembl_id):
    """
    检索药物信息，包括适应症和机制。

    参数:
        molecule_chembl_id: ChEMBL分子标识符

    返回:
        (药物信息、机制、适应症)元组
    """
    drug = new_client.drug
    mechanism = new_client.mechanism
    drug_indication = new_client.drug_indication

    try:
        drug_info = drug.get(molecule_chembl_id)
    except:
        drug_info = None

    mechanisms = list(mechanism.filter(molecule_chembl_id=molecule_chembl_id))
    indications = list(drug_indication.filter(molecule_chembl_id=molecule_chembl_id))

    return drug_info, mechanisms, indications


def find_kinase_inhibitors(max_ic50=100):
    """
    查找强效激酶抑制剂。

    参数:
        max_ic50: 最大IC50值（nM）

    返回:
        激酶抑制剂活性列表
    """
    target = new_client.target
    activity = new_client.activity

    # 查找激酶靶点
    kinase_targets = target.filter(
        target_type='SINGLE PROTEIN',
        pref_name__icontains='kinase'
    )

    # 获取靶点ID
    target_ids = [t['target_chembl_id'] for t in kinase_targets[:10]]  # 限制为前10个

    # 查找活性
    results = activity.filter(
        target_chembl_id__in=target_ids,
        standard_type='IC50',
        standard_value__lte=max_ic50,
        standard_units='nM'
    )

    return list(results)


def get_compound_bioactivities(molecule_chembl_id):
    """
    获取特定化合物的所有生物活性数据。

    参数:
        molecule_chembl_id: ChEMBL分子标识符

    返回:
        该化合物的所有活性记录列表
    """
    activity = new_client.activity
    results = activity.filter(
        molecule_chembl_id=molecule_chembl_id,
        pchembl_value__isnull=False
    )
    return list(results)


def export_to_dataframe(data):
    """
    将ChEMBL数据转换为pandas DataFrame（需要pandas）。

    参数:
        data: ChEMBL记录列表

    返回:
        pandas DataFrame
    """
    try:
        import pandas as pd
        return pd.DataFrame(data)
    except ImportError:
        print("未安装pandas。使用以下命令安装: pip install pandas")
        return None


# 使用示例
if __name__ == "__main__":
    print("ChEMBL数据库查询示例")
    print("=" * 50)

    # 示例 1: 获取阿司匹林的信息
    print("\n1. 正在获取阿司匹林（CHEMBL25）的信息...")
    aspirin = get_molecule_info('CHEMBL25')
    print(f"名称: {aspirin.get('pref_name')}")
    print(f"分子式: {aspirin.get('molecule_properties', {}).get('full_molformula')}")

    # 示例 2: 搜索EGFR抑制剂
    print("\n2. 正在搜索EGFR靶点...")
    egfr_targets = search_targets_by_name('EGFR')
    if egfr_targets:
        print(f"找到 {len(egfr_targets)} 个EGFR相关靶点")
        print(f"第一个靶点: {egfr_targets[0]['pref_name']}")

    # 示例 3: 查找靶点的强效化合物
    print("\n3. 正在查找EGFR（CHEMBL203）的强效化合物...")
    activities = get_bioactivity_data('CHEMBL203', 'IC50', max_value=10)
    print(f"找到 {len(activities)} 个IC50 <= 10 nM的化合物")

    print("\n" + "=" * 50)
    print("示例成功完成!")
