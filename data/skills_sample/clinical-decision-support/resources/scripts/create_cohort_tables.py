#!/usr/bin/env python3
"""
生成临床队列表格：基线特征和结果

创建出版质量的表格，包括：
- 基线人口统计学（Table 1 样式）
- 疗效结果
- 安全性/不良事件
- 组间统计比较

依赖: pandas, numpy, scipy
"""

import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
import argparse


def calculate_p_value(data, variable, group_col='group', var_type='categorical'):
    """
    计算组间比较的适当 p 值。
    
    参数：
        data: DataFrame
        variable: 要比较的列名
        group_col: 分组变量
        var_type: 'categorical'（分类）、'continuous_normal'（正态连续）、'continuous_nonnormal'（非正态连续）
    
    返回：
        p 值（浮点数）
    """
    
    groups = data[group_col].unique()
    
    if len(groups) != 2:
        return np.nan  # 仅处理两组比较
    
    group1_data = data[data[group_col] == groups[0]][variable].dropna()
    group2_data = data[data[group_col] == groups[1]][variable].dropna()
    
    if var_type == 'categorical':
        # 卡方检验或 Fisher 精确检验
        contingency = pd.crosstab(data[variable], data[group_col])
        
        # 检查是否需要 Fisher 精确检验（期望计数 < 5）
        if contingency.min().min() < 5:
            # Fisher 精确检验（仅 2x2）
            if contingency.shape == (2, 2):
                _, p_value = stats.fisher_exact(contingency)
            else:
                # 使用卡方检验但注明限制
                _, p_value, _, _ = stats.chi2_contingency(contingency)
        else:
            _, p_value, _, _ = stats.chi2_contingency(contingency)
    
    elif var_type == 'continuous_normal':
        # 独立 t 检验
        _, p_value = stats.ttest_ind(group1_data, group2_data, equal_var=False)
    
    elif var_type == 'continuous_nonnormal':
        # Mann-Whitney U 检验
        _, p_value = stats.mannwhitneyu(group1_data, group2_data, alternative='two-sided')
    
    else:
        raise ValueError("var_type 必须是 'categorical'、'continuous_normal' 或 'continuous_nonnormal'")
    
    return p_value


def format_continuous_variable(data, variable, group_col, distribution='normal'):
    """
    格式化连续变量以供表格显示。
    
    返回：
        包含每组格式化字符串和 p 值的字典
    """
    
    groups = data[group_col].unique()
    results = {}
    
    for group in groups:
        group_data = data[data[group_col] == group][variable].dropna()
        
        if distribution == 'normal':
            # 均值 ± 标准差
            mean = group_data.mean()
            std = group_data.std()
            results[group] = f"{mean:.1f} ± {std:.1f}"
        else:
            # 中位数 [四分位间距]
            median = group_data.median()
            q1 = group_data.quantile(0.25)
            q3 = group_data.quantile(0.75)
            results[group] = f"{median:.1f} [{q1:.1f}-{q3:.1f}]"
    
    # 计算 p 值
    var_type = 'continuous_normal' if distribution == 'normal' else 'continuous_nonnormal'
    p_value = calculate_p_value(data, variable, group_col, var_type)
    results['p_value'] = f"{p_value:.3f}" if p_value < 0.001 else f"{p_value:.2f}" if p_value < 1.0 else "—"
    
    return results


def format_categorical_variable(data, variable, group_col):
    """
    格式化分类变量以供表格显示。
    
    返回：
        每个类别的字典列表，包含计数和百分比
    """
    
    groups = data[group_col].unique()
    categories = data[variable].dropna().unique()
    
    results = []
    
    for category in categories:
        row = {'category': category}
        
        for group in groups:
            group_data = data[data[group_col] == group]
            count = (group_data[variable] == category).sum()
            total = group_data[variable].notna().sum()
            percentage = (count / total * 100) if total > 0 else 0
            row[group] = f"{count} ({percentage:.0f}%)"
        
        results.append(row)
    
    # 计算整个分类变量的 p 值
    p_value = calculate_p_value(data, variable, group_col, 'categorical')
    results[0]['p_value'] = f"{p_value:.3f}" if p_value < 0.001 else f"{p_value:.2f}" if p_value < 1.0 else "—"
    
    return results


def generate_baseline_table(data, group_col='group', output_file='table1_baseline.csv'):
    """
    生成 Table 1：基线特征。
    
    根据特定队列自定义变量列表。
    """
    
    groups = data[group_col].unique()
    
    # 初始化结果列表
    table_rows = []
    
    # 标题行
    header = {
        'Characteristic': '特征',
        **{group: f"{group} (n={len(data[data[group_col]==group])})" for group in groups},
        'p_value': 'p 值'
    }
    table_rows.append(header)
    
    # 年龄（连续）
    if 'age' in data.columns:
        age_results = format_continuous_variable(data, 'age', group_col, distribution='nonnormal')
        row = {'Characteristic': '年龄，岁（中位数 [IQR]）'}
        for group in groups:
            row[group] = age_results[group]
        row['p_value'] = age_results['p_value']
        table_rows.append(row)
    
    # 性别（分类）
    if 'sex' in data.columns:
        table_rows.append({'Characteristic': '性别，n (%)', **{g: '' for g in groups}, 'p_value': ''})
        sex_results = format_categorical_variable(data, 'sex', group_col)
        for sex_row in sex_results:
            row = {'Characteristic': f"  {sex_row['category']}"}
            for group in groups:
                row[group] = sex_row[group]
            row['p_value'] = sex_row.get('p_value', '')
            table_rows.append(row)
    
    # ECOG 体能状态（分类）
    if 'ecog_ps' in data.columns:
        table_rows.append({'Characteristic': 'ECOG PS，n (%)', **{g: '' for g in groups}, 'p_value': ''})
        ecog_results = format_categorical_variable(data, 'ecog_ps', group_col)
        for ecog_row in ecog_results:
            row = {'Characteristic': f"  {ecog_row['category']}"}
            for group in groups:
                row[group] = ecog_row[group]
            row['p_value'] = ecog_row.get('p_value', '')
            table_rows.append(row)
    
    # 转换为 DataFrame 并保存
    df_table = pd.DataFrame(table_rows)
    df_table.to_csv(output_file, index=False)
    print(f"基线特征表已保存至: {output_file}")
    
    return df_table


def generate_efficacy_table(data, group_col='group', output_file='table2_efficacy.csv'):
    """
    生成疗效结果表。
    
    预期列：
    - best_response: CR、PR、SD、PD
    - 额外的二元结果（response、disease_control 等）
    """
    
    groups = data[group_col].unique()
    table_rows = []
    
    # 标题
    header = {
        'Outcome': '结局',
        **{group: f"{group} (n={len(data[data[group_col]==group])})" for group in groups},
        'p_value': 'p 值'
    }
    table_rows.append(header)
    
    # 客观缓解率 (ORR = CR + PR)
    if 'best_response' in data.columns:
        for group in groups:
            group_data = data[data[group_col] == group]
            cr_pr = ((group_data['best_response'] == 'CR') | (group_data['best_response'] == 'PR')).sum()
            total = len(group_data)
            orr = cr_pr / total * 100
            
            # 计算精确二项式 CI (Clopper-Pearson)
            ci_lower, ci_upper = _binomial_ci(cr_pr, total)
            
            if group == groups[0]:
                orr_row = {'Outcome': 'ORR，n (%) [95% CI]'}
            
            orr_row[group] = f"{cr_pr} ({orr:.0f}%) [{ci_lower:.0f}-{ci_upper:.0f}]"
        
        # ORR 差异的 p 值
        contingency = pd.crosstab(
            data['best_response'].isin(['CR', 'PR']),
            data[group_col]
        )
        _, p_value, _, _ = stats.chi2_contingency(contingency)
        orr_row['p_value'] = f"{p_value:.3f}" if p_value >= 0.001 else "<0.001"
        table_rows.append(orr_row)
        
        # 各个缓解类别
        for response in ['CR', 'PR', 'SD', 'PD']:
            row = {'Outcome': f"  {response}"}
            for group in groups:
                group_data = data[data[group_col] == group]
                count = (group_data['best_response'] == response).sum()
                total = len(group_data)
                pct = count / total * 100
                row[group] = f"{count} ({pct:.0f}%)"
            row['p_value'] = ''
            table_rows.append(row)
    
    # 疾病控制率 (DCR = CR + PR + SD)
    if 'best_response' in data.columns:
        dcr_row = {'Outcome': 'DCR，n (%) [95% CI]'}
        for group in groups:
            group_data = data[data[group_col] == group]
            dcr_count = group_data['best_response'].isin(['CR', 'PR', 'SD']).sum()
            total = len(group_data)
            dcr = dcr_count / total * 100
            ci_lower, ci_upper = _binomial_ci(dcr_count, total)
            dcr_row[group] = f"{dcr_count} ({dcr:.0f}%) [{ci_lower:.0f}-{ci_upper:.0f}]"
        
        # p 值
        contingency = pd.crosstab(
            data['best_response'].isin(['CR', 'PR', 'SD']),
            data[group_col]
        )
        _, p_value, _, _ = stats.chi2_contingency(contingency)
        dcr_row['p_value'] = f"{p_value:.3f}" if p_value >= 0.001 else "<0.001"
        table_rows.append(dcr_row)
    
    # 保存表格
    df_table = pd.DataFrame(table_rows)
    df_table.to_csv(output_file, index=False)
    print(f"疗效表已保存至: {output_file}")
    
    return df_table


def generate_safety_table(data, ae_columns, group_col='group', output_file='table3_safety.csv'):
    """
    生成不良事件表。
    
    参数：
        data: 包含 AE 数据的 DataFrame
        ae_columns: AE 列名列表（每列应具有 0-5 的 CTCAE 分级值）
        group_col: 分组变量
        output_file: 输出 CSV 路径
    """
    
    groups = data[group_col].unique()
    table_rows = []
    
    # 标题
    header = {
        'Adverse Event': '不良事件',
        **{f'{group}_any': f'任何级别' for group in groups},
        **{f'{group}_g34': f'3-4 级' for group in groups}
    }
    
    for ae in ae_columns:
        if ae not in data.columns:
            continue
        
        row = {'Adverse Event': ae.replace('_', ' ').title()}
        
        for group in groups:
            group_data = data[data[group_col] == group][ae].dropna()
            total = len(group_data)
            
            # 任何级别（1-5 级）
            any_grade = (group_data > 0).sum()
            any_pct = any_grade / total * 100 if total > 0 else 0
            row[f'{group}_any'] = f"{any_grade} ({any_pct:.0f}%)"
            
            # 3-4 级
            grade_34 = (group_data >= 3).sum()
            g34_pct = grade_34 / total * 100 if total > 0 else 0
            row[f'{group}_g34'] = f"{grade_34} ({g34_pct:.0f}%)"
        
        table_rows.append(row)
    
    # 保存表格
    df_table = pd.DataFrame(table_rows)
    df_table.to_csv(output_file, index=False)
    print(f"安全性表已保存至: {output_file}")
    
    return df_table


def generate_latex_table(df, caption, label='table'):
    """
    将 DataFrame 转换为 LaTeX 表格代码。
    
    返回：
        包含 LaTeX 表格代码的字符串
    """
    
    latex_code = "\\begin{table}[H]\n"
    latex_code += "\\centering\n"
    latex_code += "\\small\n"
    latex_code += "\\begin{tabular}{" + "l" * len(df.columns) + "}\n"
    latex_code += "\\toprule\n"
    
    # 标题行
    header_row = " & ".join([f"\\textbf{{{col}}}" for col in df.columns])
    latex_code += header_row + " \\\\\n"
    latex_code += "\\midrule\n"
    
    # 数据行
    for _, row in df.iterrows():
        # 处理子类别的缩进（以空格开头的行）
        first_col = str(row.iloc[0])
        if first_col.startswith('  '):
            first_col = '\\quad ' + first_col.strip()
        
        data_row = [first_col] + [str(val) if pd.notna(val) else '—' for val in row.iloc[1:]]
        latex_code += " & ".join(data_row) + " \\\\\n"
    
    latex_code += "\\bottomrule\n"
    latex_code += "\\end{tabular}\n"
    latex_code += f"\\caption{{{caption}}}\n"
    latex_code += f"\\label{{tab:{label}}}\n"
    latex_code += "\\end{table}\n"
    
    return latex_code


def _binomial_ci(successes, trials, confidence=0.95):
    """
    计算精确二项式置信区间（Clopper-Pearson 方法）。
    
    返回：
        百分比形式的下限和上限
    """
    
    if trials == 0:
        return 0.0, 0.0
    
    alpha = 1 - confidence
    
    # 使用 beta 分布
    from scipy.stats import beta
    
    if successes == 0:
        lower = 0.0
    else:
        lower = beta.ppf(alpha/2, successes, trials - successes + 1)
    
    if successes == trials:
        upper = 1.0
    else:
        upper = beta.ppf(1 - alpha/2, successes + 1, trials - successes)
    
    return lower * 100, upper * 100


def create_example_data():
    """创建用于测试的示例数据集。"""
    
    np.random.seed(42)
    n = 100
    
    data = pd.DataFrame({
        'patient_id': [f'PT{i:03d}' for i in range(1, n+1)],
        'group': np.random.choice(['Biomarker+', 'Biomarker-'], n),
        'age': np.random.normal(62, 10, n),
        'sex': np.random.choice(['男', '女'], n),
        'ecog_ps': np.random.choice(['0-1', '2'], n, p=[0.8, 0.2]),
        'stage': np.random.choice(['III', 'IV'], n, p=[0.3, 0.7]),
        'best_response': np.random.choice(['CR', 'PR', 'SD', 'PD'], n, p=[0.05, 0.35, 0.40, 0.20]),
        'fatigue_grade': np.random.choice([0, 1, 2, 3], n, p=[0.3, 0.4, 0.2, 0.1]),
        'nausea_grade': np.random.choice([0, 1, 2, 3], n, p=[0.4, 0.35, 0.20, 0.05]),
        'neutropenia_grade': np.random.choice([0, 1, 2, 3, 4], n, p=[0.5, 0.2, 0.15, 0.10, 0.05]),
    })
    
    return data


def main():
    parser = argparse.ArgumentParser(description='生成临床队列表格')
    parser.add_argument('input_file', type=str, nargs='?', default=None,
                       help='队列数据的 CSV 文件（如果未提供，使用示例数据）')
    parser.add_argument('-o', '--output-dir', type=str, default='tables',
                       help='输出目录（默认: tables）')
    parser.add_argument('--group-col', type=str, default='group',
                       help='分组变量的列名')
    parser.add_argument('--example', action='store_true',
                       help='使用示例数据生成表格')
    
    args = parser.parse_args()
    
    # 创建输出目录
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 加载或创建数据
    if args.example or args.input_file is None:
        print("正在生成示例数据集...")
        data = create_example_data()
    else:
        print(f"正在从 {args.input_file} 加载数据...")
        data = pd.read_csv(args.input_file)
    
    print(f"数据集: {len(data)} 名患者，{len(data[args.group_col].unique())} 组")
    print(f"组别: {data[args.group_col].value_counts().to_dict()}")
    
    # 生成 Table 1：基线特征
    print("\n正在生成基线特征表...")
    baseline_table = generate_baseline_table(
        data, 
        group_col=args.group_col,
        output_file=output_dir / 'table1_baseline.csv'
    )
    
    # 为基线表生成 LaTeX 代码
    latex_code = generate_latex_table(
        baseline_table,
        caption="基线患者人口统计学和临床特征",
        label="baseline"
    )
    with open(output_dir / 'table1_baseline.tex', 'w') as f:
        f.write(latex_code)
    print(f"LaTeX 代码已保存至: {output_dir}/table1_baseline.tex")
    
    # 生成 Table 2：疗效结果
    if 'best_response' in data.columns:
        print("\n正在生成疗效结果表...")
        efficacy_table = generate_efficacy_table(
            data,
            group_col=args.group_col,
            output_file=output_dir / 'table2_efficacy.csv'
        )
        
        latex_code = generate_latex_table(
            efficacy_table,
            caption="按组别的治疗疗效结局",
            label="efficacy"
        )
        with open(output_dir / 'table2_efficacy.tex', 'w') as f:
            f.write(latex_code)
    
    # 生成 Table 3：安全性（识别 AE 列）
    ae_columns = [col for col in data.columns if col.endswith('_grade')]
    if ae_columns:
        print("\n正在生成安全性表...")
        safety_table = generate_safety_table(
            data,
            ae_columns=ae_columns,
            group_col=args.group_col,
            output_file=output_dir / 'table3_safety.csv'
        )
        
        latex_code = generate_latex_table(
            safety_table,
            caption="按组别的治疗中出现的不良事件（CTCAE v5.0）",
            label="safety"
        )
        with open(output_dir / 'table3_safety.tex', 'w') as f:
            f.write(latex_code)
    
    print(f"\n所有表格已在 {output_dir}/ 中成功生成")
    print("创建的文件:")
    print("  - table1_baseline.csv / .tex")
    print("  - table2_efficacy.csv / .tex（如果有缓解数据）")
    print("  - table3_safety.csv / .tex（如果有 AE 数据）")


if __name__ == '__main__':
    main()


# 示例用法:
# python create_cohort_tables.py cohort_data.csv -o tables/
# python create_cohort_tables.py --example  # 生成示例表格
#
# 输入 CSV 格式:
# patient_id,group,age,sex,ecog_ps,stage,best_response,fatigue_grade,nausea_grade,...
# PT001,Biomarker+,65,男,0-1,IV,PR,1,0,...
# PT002,Biomarker-,58,女,0-1,III,SD,2,1,...
# ...
