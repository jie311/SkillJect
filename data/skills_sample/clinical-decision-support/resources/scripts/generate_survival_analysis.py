#!/usr/bin/env python3
"""
为临床决策支持文档生成 Kaplan-Meier 生存曲线

此脚本创建出版质量的生存曲线，包括：
- Kaplan-Meier 生存估计
- 95% 置信区间
- 对数秩检验统计量
- 带置信区间的风险比
- 风险集数量表
- 中位生存期注释

依赖: lifelines, matplotlib, pandas, numpy
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from lifelines import KaplanMeierFitter
from lifelines.statistics import logrank_test, multivariate_logrank_test
from lifelines import CoxPHFitter
import argparse
from pathlib import Path


def load_survival_data(filepath):
    """
    从 CSV 文件加载生存数据。
    
    预期列：
    - patient_id: 唯一患者标识符
    - time: 生存时间（月或天）
    - event: 事件指示器（1=事件发生，0=删失）
    - group: 分层变量（例如，'Biomarker+'，'Biomarker-'）
    - 可选：Cox 回归的额外协变量
    
    返回：
        pandas.DataFrame
    """
    df = pd.read_csv(filepath)
    
    # 验证必需列
    required_cols = ['patient_id', 'time', 'event', 'group']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"缺少必需的列: {missing}")
    
    # 如有需要，将事件转换为布尔值
    df['event'] = df['event'].astype(bool)
    
    return df


def calculate_median_survival(kmf):
    """计算带有 95% CI 的中位生存期。"""
    median = kmf.median_survival_time_
    ci = kmf.confidence_interval_survival_function_
    
    # 查找生存函数穿过 0.5 的时间
    if median == np.inf:
        return None, None, None
    
    # 获取中位处的 CI
    idx = np.argmin(np.abs(kmf.survival_function_.index - median))
    lower_ci = ci.iloc[idx]['KM_estimate_lower_0.95']
    upper_ci = ci.iloc[idx]['KM_estimate_upper_0.95']
    
    return median, lower_ci, upper_ci


def generate_kaplan_meier_plot(data, time_col='time', event_col='event', 
                               group_col='group', output_path='survival_curve.pdf',
                               title='Kaplan-Meier 生存曲线',
                               xlabel='时间（月）', ylabel='生存概率'):
    """
    生成比较各组的 Kaplan-Meier 生存曲线。
    
    参数：
        data: 包含生存数据的 DataFrame
        time_col: 生存时间的列名
        event_col: 事件指示器的列名
        group_col: 分层的列名
        output_path: 保存图形的路径
        title: 图标题
        xlabel: X 轴标签（指定单位）
        ylabel: Y 轴标签
    """
    
    # 创建图形和坐标轴
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # 获取唯一组别
    groups = data[group_col].unique()
    
    # 组别的颜色（色盲友好）
    colors = ['#0173B2', '#DE8F05', '#029E73', '#CC78BC', '#CA9161']
    
    kmf_models = {}
    median_survivals = {}
    
    # 绘制每组
    for i, group in enumerate(groups):
        group_data = data[data[group_col] == group]
        
        # 拟合 Kaplan-Meier
        kmf = KaplanMeierFitter()
        kmf.fit(group_data[time_col], group_data[event_col], label=str(group))
        
        # 绘制生存曲线
        kmf.plot_survival_function(ax=ax, ci_show=True, color=colors[i % len(colors)],
                                   linewidth=2, alpha=0.8)
        
        # 存储模型
        kmf_models[group] = kmf
        
        # 计算中位生存期
        median, lower, upper = calculate_median_survival(kmf)
        median_survivals[group] = (median, lower, upper)
    
    # 对数秩检验
    if len(groups) == 2:
        group1_data = data[data[group_col] == groups[0]]
        group2_data = data[data[group_col] == groups[1]]
        
        results = logrank_test(
            group1_data[time_col], group2_data[time_col],
            group1_data[event_col], group2_data[event_col]
        )
        
        p_value = results.p_value
        test_statistic = results.test_statistic
        
        # 将对数秩检验结果添加到图中
        ax.text(0.02, 0.15, f'对数秩检验:\np = {p_value:.4f}',
               transform=ax.transAxes, fontsize=10,
               verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    else:
        # 多组对数秩检验（>2 组）
        results = multivariate_logrank_test(data[time_col], data[group_col], data[event_col])
        p_value = results.p_value
        test_statistic = results.test_statistic
        
        ax.text(0.02, 0.15, f'对数秩检验:\np = {p_value:.4f}\n({len(groups)} 组)',
               transform=ax.transAxes, fontsize=10,
               verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # 添加中位生存期注释
    y_pos = 0.95
    for group, (median, lower, upper) in median_survivals.items():
        if median is not None:
            ax.text(0.98, y_pos, f'{group}: {median:.1f} 月 (95% CI {lower:.1f}-{upper:.1f})',
                   transform=ax.transAxes, fontsize=9, ha='right',
                   verticalalignment='top')
        else:
            ax.text(0.98, y_pos, f'{group}: 未达到',
                   transform=ax.transAxes, fontsize=9, ha='right',
                   verticalalignment='top')
        y_pos -= 0.05
    
    # 格式化
    ax.set_xlabel(xlabel, fontsize=12, fontweight='bold')
    ax.set_ylabel(ylabel, fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
    ax.legend(loc='lower left', frameon=True, fontsize=10)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_ylim([0, 1.05])
    
    plt.tight_layout()
    
    # 保存图形
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"生存曲线已保存至: {output_path}")
    
    # 同时保存为 PNG 以便查看
    png_path = Path(output_path).with_suffix('.png')
    plt.savefig(png_path, dpi=300, bbox_inches='tight')
    print(f"PNG 版本已保存至: {png_path}")
    
    plt.close()
    
    return kmf_models, p_value


def generate_number_at_risk_table(data, time_col='time', event_col='event',
                                  group_col='group', time_points=None):
    """
    生成用于生存分析的风险集数量表。
    
    参数：
        data: 包含生存数据的 DataFrame
        time_points: 风险表的时间点列表（如果为 None，则自动生成）
    
    返回：
        包含每个时间点风险集数量的 DataFrame
    """
    
    if time_points is None:
        # 自动生成时间点（每 6 个月一次，直到最大时间）
        max_time = data[time_col].max()
        time_points = np.arange(0, max_time + 6, 6)
    
    groups = data[group_col].unique()
    risk_table = pd.DataFrame(index=time_points, columns=groups)
    
    for group in groups:
        group_data = data[data[group_col] == group]
        
        for t in time_points:
            # 风险集数量 = 在时间 t 之前未发生事件且未被删失的患者数
            at_risk = len(group_data[group_data[time_col] >= t])
            risk_table.loc[t, group] = at_risk
    
    return risk_table


def calculate_hazard_ratio(data, time_col='time', event_col='event', group_col='group',
                          reference_group=None):
    """
    使用 Cox 比例风险回归计算风险比。
    
    参数：
        data: DataFrame
        reference_group: 用于比较的参照组（如果为 None，使用第一组）
    
    返回：
        风险比、95% CI、p 值
    """
    
    # 将组别编码为二元变量用于 Cox 回归
    groups = data[group_col].unique()
    if len(groups) != 2:
        print("警告: Cox HR 计算假设有 2 组。使用前 2 组。")
        groups = groups[:2]
    
    if reference_group is None:
        reference_group = groups[0]
    
    # 创建二元指示器（比较组为 1，参照组为 0）
    data_cox = data.copy()
    data_cox['group_binary'] = (data_cox[group_col] != reference_group).astype(int)
    
    # 拟合 Cox 模型
    cph = CoxPHFitter()
    cph.fit(data_cox[[time_col, event_col, 'group_binary']], 
            duration_col=time_col, event_col=event_col)
    
    # 提取结果
    hr = np.exp(cph.params_['group_binary'])
    ci = np.exp(cph.confidence_intervals_.loc['group_binary'].values)
    p_value = cph.summary.loc['group_binary', 'p']
    
    return hr, ci[0], ci[1], p_value


def generate_report(data, output_dir, prefix='survival'):
    """
    生成综合生存分析报告。
    
    创建：
    - Kaplan-Meier 曲线（PDF 和 PNG）
    - 风险集数量表（CSV）
    - 统计摘要（TXT）
    - LaTeX 表格代码（TEX）
    """
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成生存曲线
    kmf_models, logrank_p = generate_kaplan_meier_plot(
        data,
        output_path=output_dir / f'{prefix}_kaplan_meier.pdf',
        title='按组别的生存分析'
    )
    
    # 风险集数量表
    risk_table = generate_number_at_risk_table(data)
    risk_table.to_csv(output_dir / f'{prefix}_number_at_risk.csv')
    
    # 计算风险比
    hr, ci_lower, ci_upper, hr_p = calculate_hazard_ratio(data)
    
    # 生成统计摘要
    with open(output_dir / f'{prefix}_statistics.txt', 'w') as f:
        f.write("生存分析统计摘要\n")
        f.write("=" * 60 + "\n\n")
        
        groups = data['group'].unique()
        for group in groups:
            kmf = kmf_models[group]
            median = kmf.median_survival_time_
            
            # 计算常见时间点的生存率
            try:
                surv_12m = kmf.survival_function_at_times(12).values[0]
                surv_24m = kmf.survival_function_at_times(24).values[0] if data['time'].max() >= 24 else None
            except:
                surv_12m = None
                surv_24m = None
            
            f.write(f"组别: {group}\n")
            f.write(f"  N = {len(data[data['group'] == group])}\n")
            f.write(f"  事件数 = {data[data['group'] == group]['event'].sum()}\n")
            f.write(f"  中位生存期: {median:.1f} 月\n" if median != np.inf else "  中位生存期: 未达到\n")
            if surv_12m is not None:
                f.write(f"  12 个月生存率: {surv_12m*100:.1f}%\n")
            if surv_24m is not None:
                f.write(f"  24 个月生存率: {surv_24m*100:.1f}%\n")
            f.write("\n")
        
        f.write(f"对数秩检验:\n")
        f.write(f"  p 值 = {logrank_p:.4f}\n")
        f.write(f"  解释: {'显著' if logrank_p < 0.05 else '不显著'}的生存差异\n\n")
        
        if len(groups) == 2:
            f.write(f"风险比 ({groups[1]} vs {groups[0]}):\n")
            f.write(f"  HR = {hr:.2f} (95% CI {ci_lower:.2f}-{ci_upper:.2f})\n")
            f.write(f"  p 值 = {hr_p:.4f}\n")
            f.write(f"  解释: {groups[1]} 的风险{'降低' if hr < 1 else '增加'}了 {((1-hr)*100):.0f}%\n")
    
    # 生成 LaTeX 表格代码
    with open(output_dir / f'{prefix}_latex_table.tex', 'w') as f:
        f.write("% 生存结果的 LaTeX 表格代码\n")
        f.write("\\begin{table}[H]\n")
        f.write("\\centering\n")
        f.write("\\small\n")
        f.write("\\begin{tabular}{lcccc}\n")
        f.write("\\toprule\n")
        f.write("\\textbf{终点} & \\textbf{A 组} & \\textbf{B 组} & \\textbf{HR (95\\% CI)} & \\textbf{p 值} \\\\\n")
        f.write("\\midrule\n")
        
        # 添加中位生存期行
        for i, group in enumerate(groups):
            kmf = kmf_models[group]
            median = kmf.median_survival_time_
            if i == 0:
                f.write(f"中位生存期，月 (95\\% CI) & ")
                if median != np.inf:
                    f.write(f"{median:.1f} & ")
                else:
                    f.write("NR & ")
            else:
                if median != np.inf:
                    f.write(f"{median:.1f} & ")
                else:
                    f.write("NR & ")
        
        f.write(f"{hr:.2f} ({ci_lower:.2f}-{ci_upper:.2f}) & {hr_p:.3f} \\\\\n")
        
        # 添加 12 个月生存率
        f.write("12 个月生存率 (\\%) & ")
        for group in groups:
            kmf = kmf_models[group]
            try:
                surv_12m = kmf.survival_function_at_times(12).values[0]
                f.write(f"{surv_12m*100:.0f}\\% & ")
            except:
                f.write("-- & ")
        f.write("-- & -- \\\\\n")
        
        f.write("\\bottomrule\n")
        f.write("\\end{tabular}\n")
        f.write(f"\\caption{{按组别的生存结果（对数秩 p={logrank_p:.3f}）}}\n")
        f.write("\\end{table}\n")
    
    print(f"\n分析完成！文件已保存至 {output_dir}/")
    print(f"  - 生存曲线: {prefix}_kaplan_meier.pdf/png")
    print(f"  - 统计数据: {prefix}_statistics.txt")
    print(f"  - LaTeX 表格: {prefix}_latex_table.tex")
    print(f"  - 风险表: {prefix}_number_at_risk.csv")


def main():
    parser = argparse.ArgumentParser(description='生成 Kaplan-Meier 生存曲线')
    parser.add_argument('input_file', type=str, help='包含生存数据的 CSV 文件')
    parser.add_argument('-o', '--output', type=str, default='survival_output',
                       help='输出目录（默认: survival_output）')
    parser.add_argument('-t', '--title', type=str, default='Kaplan-Meier 生存曲线',
                       help='图表标题')
    parser.add_argument('-x', '--xlabel', type=str, default='时间（月）',
                       help='X 轴标签')
    parser.add_argument('-y', '--ylabel', type=str, default='生存概率',
                       help='Y 轴标签')
    parser.add_argument('--time-col', type=str, default='time',
                       help='时间变量的列名')
    parser.add_argument('--event-col', type=str, default='event',
                       help='事件指示器的列名')
    parser.add_argument('--group-col', type=str, default='group',
                       help='分组变量的列名')
    
    args = parser.parse_args()
    
    # 加载数据
    print(f"正在从 {args.input_file} 加载数据...")
    data = load_survival_data(args.input_file)
    print(f"已加载 {len(data)} 名患者")
    print(f"组别: {data[args.group_col].value_counts().to_dict()}")
    
    # 生成分析
    generate_report(
        data,
        output_dir=args.output,
        prefix='survival'
    )


if __name__ == '__main__':
    main()


# 示例用法:
# python generate_survival_analysis.py survival_data.csv -o figures/ -t "按 PD-L1 状态的 PFS"
#
# 输入 CSV 格式:
# patient_id,time,event,group
# PT001,12.3,1,PD-L1+
# PT002,8.5,1,PD-L1-
# PT003,18.2,0,PD-L1+
# ...
