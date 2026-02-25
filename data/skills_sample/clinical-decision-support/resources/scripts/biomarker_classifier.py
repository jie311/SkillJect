#!/usr/bin/env python3
"""
基于生物标志物的患者分层和分类

基于生物标志物谱进行患者分层，包括：
- 二分类（生物标志物+/-）
- 多类别分子亚型
- 连续生物标志物评分
- 与临床结果的相关性

依赖项: pandas, numpy, scipy, scikit-learn（可选，用于聚类）
"""

import pandas as pd
import numpy as np
from scipy import stats
import argparse
from pathlib import Path


def classify_binary_biomarker(data, biomarker_col, threshold, 
                              above_label='生物标志物+', below_label='生物标志物-'):
    """
    基于生物标志物阈值进行二分类。
    
    参数:
        data: DataFrame
        biomarker_col: 生物标志物值的列名
        threshold: 临界点值
        above_label: 大于等于阈值的标签
        below_label: 小于阈值的标签
    
    返回:
        添加了'biomarker_class'列的DataFrame
    """
    
    data = data.copy()
    data['biomarker_class'] = data[biomarker_col].apply(
        lambda x: above_label if x >= threshold else below_label
    )
    
    return data


def classify_pd_l1_tps(data, pd_l1_col='pd_l1_tps'):
    """
    将PD-L1肿瘤比例评分分类为临床类别。
    
    类别:
    - 阴性: <1%
    - 低表达: 1-49%
    - 高表达: >=50%
    
    返回:
        包含'pd_l1_category'列的DataFrame
    """
    
    data = data.copy()
    
    def categorize(tps):
        if tps < 1:
            return 'PD-L1阴性（<1%）'
        elif tps < 50:
            return 'PD-L1低表达（1-49%）'
        else:
            return 'PD-L1高表达（≥50%）'
    
    data['pd_l1_category'] = data[pd_l1_col].apply(categorize)
    
    # 分布
    print("\nPD-L1 TPS分布:")
    print(data['pd_l1_category'].value_counts())
    
    return data


def classify_her2_status(data, ihc_col='her2_ihc', fish_col='her2_fish'):
    """
    根据IHC和FISH结果分类HER2状态（ASCO/CAP指南）。
    
    IHC评分: 0, 1+, 2+, 3+
    FISH: 阳性, 阴性（如果IHC 2+）
    
    分类:
    - HER2阳性: IHC 3+ 或 IHC 2+/FISH+
    - HER2阴性: IHC 0/1+ 或 IHC 2+/FISH-
    - HER2低表达: IHC 1+ 或 IHC 2+/FISH-（HER2阴性的子集）
    
    返回:
        包含'her2_status'和'her2_low'列的DataFrame
    """
    
    data = data.copy()
    
    def classify_her2(row):
        ihc = row[ihc_col]
        fish = row.get(fish_col, None)
        
        if ihc == '3+':
            status = 'HER2阳性'
            her2_low = False
        elif ihc == '2+':
            if fish == '阳性':
                status = 'HER2阳性'
                her2_low = False
            elif fish == '阴性':
                status = 'HER2阴性'
                her2_low = True  # HER2低表达
            else:
                status = 'HER2待定（需要FISH）'
                her2_low = False
        elif ihc == '1+':
            status = 'HER2阴性'
            her2_low = True  # HER2低表达
        else:  # IHC 0
            status = 'HER2阴性'
            her2_low = False
        
        return pd.Series({'her2_status': status, 'her2_low': her2_low})
    
    data[['her2_status', 'her2_low']] = data.apply(classify_her2, axis=1)
    
    print("\nHER2状态分布:")
    print(data['her2_status'].value_counts())
    print(f"\nHER2低表达（IHC 1+或2+/FISH-）: {data['her2_low'].sum()} 位患者")
    
    return data


def classify_breast_cancer_subtype(data, er_col='er_positive', pr_col='pr_positive', 
                                   her2_col='her2_positive'):
    """
    将乳腺癌分类为分子亚型。
    
    亚型:
    - HR+/HER2-: Luminal（ER+和/或PR+，HER2-）
    - HER2+: 任何HER2阳性（无论HR状态如何）
    - 三阴性: ER-、PR-、HER2-
    
    返回:
        包含'bc_subtype'列的DataFrame
    """
    
    data = data.copy()
    
    def get_subtype(row):
        er = row[er_col]
        pr = row[pr_col]
        her2 = row[her2_col]
        
        if her2:
            if er or pr:
                return 'HR+/HER2+（Luminal B HER2+）'
            else:
                return 'HR-/HER2+（HER2富集）'
        elif er or pr:
            return 'HR+/HER2-（Luminal）'
        else:
            return '三阴性'
    
    data['bc_subtype'] = data.apply(get_subtype, axis=1)
    
    print("\n乳腺癌亚型分布:")
    print(data['bc_subtype'].value_counts())
    
    return data


def correlate_biomarker_outcome(data, biomarker_col, outcome_col, biomarker_type='binary'):
    """
    评估生物标志物与临床结果的相关性。
    
    参数:
        biomarker_col: 生物标志物变量
        outcome_col: 结果变量  
        biomarker_type: 'binary'、'categorical'、'continuous'
    
    返回:
        统计检验结果
    """
    
    print(f"\n相关性分析: {biomarker_col} vs {outcome_col}")
    print("="*60)
    
    # 移除缺失数据
    analysis_data = data[[biomarker_col, outcome_col]].dropna()
    
    if biomarker_type == 'binary' or biomarker_type == 'categorical':
        # 交叉表
        contingency = pd.crosstab(analysis_data[biomarker_col], analysis_data[outcome_col])
        print("\n列联表:")
        print(contingency)
        
        # 卡方检验
        chi2, p_value, dof, expected = stats.chi2_contingency(contingency)
        
        print(f"\n卡方检验:")
        print(f"  χ² = {chi2:.2f}, df = {dof}, p = {p_value:.4f}")
        
        # 优势比（如果是2x2表）
        if contingency.shape == (2, 2):
            a, b = contingency.iloc[0, :]
            c, d = contingency.iloc[1, :]
            or_value = (a * d) / (b * c) if b * c > 0 else np.inf
            
            # 计算OR的置信区间（对数方法）
            log_or = np.log(or_value)
            se_log_or = np.sqrt(1/a + 1/b + 1/c + 1/d)
            ci_lower = np.exp(log_or - 1.96 * se_log_or)
            ci_upper = np.exp(log_or + 1.96 * se_log_or)
            
            print(f"\n优势比: {or_value:.2f}（95% CI {ci_lower:.2f}-{ci_upper:.2f}）")
    
    elif biomarker_type == 'continuous':
        # 相关系数
        r, p_value = stats.pearsonr(analysis_data[biomarker_col], analysis_data[outcome_col])
        
        print(f"\n皮尔逊相关:")
        print(f"  r = {r:.3f}, p = {p_value:.4f}")
        
        # 也报告Spearman以获得稳健性
        rho, p_spearman = stats.spearmanr(analysis_data[biomarker_col], analysis_data[outcome_col])
        print(f"Spearman相关:")
        print(f"  ρ = {rho:.3f}, p = {p_spearman:.4f}")
    
    return p_value


def stratify_cohort_report(data, stratification_var, output_dir='stratification_report'):
    """
    生成综合分层报告。
    
    参数:
        data: 包含患者数据的DataFrame
        stratification_var: 分层变量列名
        output_dir: 报告输出目录
    """
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n队列分层报告")
    print("="*60)
    print(f"分层变量: {stratification_var}")
    print(f"总患者数: {len(data)}")
    
    # 组分布
    distribution = data[stratification_var].value_counts()
    print(f"\n组分布:")
    for group, count in distribution.items():
        pct = count / len(data) * 100
        print(f"  {group}: {count} ({pct:.1f}%)")
    
    # 保存分布
    distribution.to_csv(output_dir / 'group_distribution.csv')
    
    # 比较各组的基线特征
    print(f"\n按{stratification_var}分层的基线特征:")
    
    results = []
    
    # 连续变量
    continuous_vars = data.select_dtypes(include=[np.number]).columns.tolist()
    continuous_vars = [v for v in continuous_vars if v != stratification_var]
    
    for var in continuous_vars[:5]:  # 演示限制为前5个
        print(f"\n{var}:")
        for group in distribution.index:
            group_data = data[data[stratification_var] == group][var].dropna()
            print(f"  {group}: 中位数 {group_data.median():.1f} [IQR {group_data.quantile(0.25):.1f}-{group_data.quantile(0.75):.1f}]")
        
        # 统计检验
        if len(distribution) == 2:
            groups_list = distribution.index.tolist()
            g1 = data[data[stratification_var] == groups_list[0]][var].dropna()
            g2 = data[data[stratification_var] == groups_list[1]][var].dropna()
            _, p_value = stats.mannwhitneyu(g1, g2, alternative='two-sided')
            print(f"  p值: {p_value:.4f}")
            
            results.append({
                'Variable': var,
                'Test': 'Mann-Whitney U',
                'p_value': p_value,
                'Significant': '是' if p_value < 0.05 else '否'
            })
    
    # 保存结果
    if results:
        df_results = pd.DataFrame(results)
        df_results.to_csv(output_dir / 'statistical_comparisons.csv', index=False)
        print(f"\n统计比较结果已保存到: {output_dir}/statistical_comparisons.csv")
    
    print(f"\n分层报告完成！文件保存到 {output_dir}/")


def main():
    parser = argparse.ArgumentParser(description='基于生物标志物的患者分类')
    parser.add_argument('input_file', type=str, nargs='?', default=None,
                       help='包含患者和生物标志物数据的CSV文件')
    parser.add_argument('-b', '--biomarker', type=str, default=None,
                       help='用于分层的生物标志物列名')
    parser.add_argument('-t', '--threshold', type=float, default=None,
                       help='二分类的阈值')
    parser.add_argument('-o', '--output-dir', type=str, default='stratification',
                       help='输出目录')
    parser.add_argument('--example', action='store_true',
                       help='使用示例数据运行')
    
    args = parser.parse_args()
    
    # 示例数据（如果请求）
    if args.example or args.input_file is None:
        print("正在生成示例数据集...")
        np.random.seed(42)
        n = 80
        
        data = pd.DataFrame({
            'patient_id': [f'PT{i:03d}' for i in range(1, n+1)],
            'age': np.random.normal(62, 10, n),
            'sex': np.random.choice(['男', '女'], n),
            'pd_l1_tps': np.random.exponential(20, n),  # PD-L1的指数分布
            'tmb': np.random.exponential(8, n),  # 每Mb突变数
            'her2_ihc': np.random.choice(['0', '1+', '2+', '3+'], n, p=[0.6, 0.2, 0.15, 0.05]),
            'response': np.random.choice(['是', '否'], n, p=[0.4, 0.6]),
        })
        
        # 模拟相关性：更高的PD-L1 -> 更好的响应
        data.loc[data['pd_l1_tps'] >= 50, 'response'] = np.random.choice(['是', '否'], 
                                                                         (data['pd_l1_tps'] >= 50).sum(),
                                                                         p=[0.65, 0.35])
    else:
        print(f"正在从 {args.input_file} 加载数据...")
        data = pd.read_csv(args.input_file)
    
    print(f"数据集: {len(data)} 位患者")
    print(f"列: {list(data.columns)}")
    
    # PD-L1分类示例
    if 'pd_l1_tps' in data.columns or args.biomarker == 'pd_l1_tps':
        data = classify_pd_l1_tps(data, 'pd_l1_tps')
        
        # 如果有可用则与响应相关
        if 'response' in data.columns:
            correlate_biomarker_outcome(data, 'pd_l1_category', 'response', biomarker_type='categorical')
    
    # 如果有HER2列则进行HER2分类
    if 'her2_ihc' in data.columns:
        if 'her2_fish' not in data.columns:
            # 为IHC 2+添加占位符FISH
            data['her2_fish'] = np.nan
        data = classify_her2_status(data, 'her2_ihc', 'her2_fish')
    
    # 如果提供了阈值则进行通用二分类
    if args.biomarker and args.threshold is not None:
        print(f"\n二分类: {args.biomarker}，阈值 {args.threshold}")
        data = classify_binary_biomarker(data, args.biomarker, args.threshold)
        print(data['biomarker_class'].value_counts())
    
    # 生成分层报告
    if args.biomarker:
        stratify_cohort_report(data, args.biomarker, output_dir=args.output_dir)
    elif 'pd_l1_category' in data.columns:
        stratify_cohort_report(data, 'pd_l1_category', output_dir=args.output_dir)
    
    # 保存分类数据
    output_path = Path(args.output_dir) / 'classified_data.csv'
    data.to_csv(output_path, index=False)
    print(f"\n分类数据已保存到: {output_path}")


if __name__ == '__main__':
    main()
