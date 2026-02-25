"""
综合统计假设检验工具。

此模块提供检验常见统计假设的函数：
- 正态性
- 方差齐性
- 独立性
- 线性
- 异常值
"""

import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple, Optional, Union


def check_normality(
    data: Union[np.ndarray, pd.Series, List],
    name: str = "data",
    alpha: float = 0.05,
    plot: bool = True
) -> Dict:
    """
    使用 Shapiro-Wilk 检验和可视化检验正态性假设。

    参数
    ----------
    data : 类数组
        待检验正态性的数据
    name : str
        变量名称（用于标签）
    alpha : float
        Shapiro-Wilk 检验的显著性水平
    plot : bool
        是否创建 Q-Q 图和直方图

    返回
    -------
    dict
        包括检验统计量、p 值和解释的结果
    """
    data = np.asarray(data)
    data_clean = data[~np.isnan(data)]

    # Shapiro-Wilk 检验
    statistic, p_value = stats.shapiro(data_clean)

    # 解释
    is_normal = p_value > alpha
    interpretation = (
        f"数据{'看起来' if is_normal else '不'}符合正态分布 "
        f"(W = {statistic:.3f}, p = {p_value:.3f})"
    )

    # 可视化检验
    if plot:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

        # Q-Q 图
        stats.probplot(data_clean, dist="norm", plot=ax1)
        ax1.set_title(f"Q-Q 图: {name}")
        ax1.grid(alpha=0.3)

        # 带正态曲线的直方图
        ax2.hist(data_clean, bins='auto', density=True, alpha=0.7, color='steelblue', edgecolor='black')
        mu, sigma = data_clean.mean(), data_clean.std()
        x = np.linspace(data_clean.min(), data_clean.max(), 100)
        ax2.plot(x, stats.norm.pdf(x, mu, sigma), 'r-', linewidth=2, label='正态曲线')
        ax2.set_xlabel('值')
        ax2.set_ylabel('密度')
        ax2.set_title(f'直方图: {name}')
        ax2.legend()
        ax2.grid(alpha=0.3)

        plt.tight_layout()
        plt.show()

    return {
        'test': 'Shapiro-Wilk',
        'statistic': statistic,
        'p_value': p_value,
        'is_normal': is_normal,
        'interpretation': interpretation,
        'n': len(data_clean),
        'recommendation': (
            "继续进行参数检验" if is_normal
            else "考虑非参数替代方法或数据变换"
        )
    }


def check_normality_per_group(
    data: pd.DataFrame,
    value_col: str,
    group_col: str,
    alpha: float = 0.05,
    plot: bool = True
) -> pd.DataFrame:
    """
    分别检验每组的正态性假设。

    参数
    ----------
    data : pd.DataFrame
        包含值和组标签的数据
    value_col : str
        待检验值的列名
    group_col : str
        组标签的列名
    alpha : float
        显著性水平
    plot : bool
        是否为每组的创建 Q-Q 图

    返回
    -------
    pd.DataFrame
        每组的结果
    """
    groups = data[group_col].unique()
    results = []

    if plot:
        n_groups = len(groups)
        fig, axes = plt.subplots(1, n_groups, figsize=(5 * n_groups, 4))
        if n_groups == 1:
            axes = [axes]

    for idx, group in enumerate(groups):
        group_data = data[data[group_col] == group][value_col].dropna()
        stat, p = stats.shapiro(group_data)

        results.append({
            '组别': group,
            '样本量': len(group_data),
            'W': stat,
            'p值': p,
            '正态': '是' if p > alpha else '否'
        })

        if plot:
            stats.probplot(group_data, dist="norm", plot=axes[idx])
            axes[idx].set_title(f"Q-Q 图: {group}")
            axes[idx].grid(alpha=0.3)

    if plot:
        plt.tight_layout()
        plt.show()

    return pd.DataFrame(results)


def check_homogeneity_of_variance(
    data: pd.DataFrame,
    value_col: str,
    group_col: str,
    alpha: float = 0.05,
    plot: bool = True
) -> Dict:
    """
    使用 Levene 检验检验方差齐性。

    参数
    ----------
    data : pd.DataFrame
        包含值和组标签的数据
    value_col : str
        值的列名
    group_col : str
        组标签的列名
    alpha : float
        显著性水平
    plot : bool
        是否创建箱线图

    返回
    -------
    dict
        包括检验统计量、p 值和解释的结果
    """
    groups = [group[value_col].values for name, group in data.groupby(group_col)]

    # Levene 检验（对非正态性稳健）
    statistic, p_value = stats.levene(*groups)

    # 方差比（最大/最小）
    variances = [np.var(g, ddof=1) for g in groups]
    var_ratio = max(variances) / min(variances)

    is_homogeneous = p_value > alpha
    interpretation = (
        f"方差{'看起来' if is_homogeneous else '不'}齐性 "
        f"(F = {statistic:.3f}, p = {p_value:.3f}, 方差比 = {var_ratio:.2f})"
    )

    if plot:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

        # 箱线图
        data.boxplot(column=value_col, by=group_col, ax=ax1)
        ax1.set_title('按组别的箱线图')
        ax1.set_xlabel(group_col)
        ax1.set_ylabel(value_col)
        plt.sca(ax1)
        plt.xticks(rotation=45)

        # 方差图
        group_names = data[group_col].unique()
        ax2.bar(range(len(variances)), variances, color='steelblue', edgecolor='black')
        ax2.set_xticks(range(len(variances)))
        ax2.set_xticklabels(group_names, rotation=45)
        ax2.set_ylabel('方差')
        ax2.set_title('按组别的方差')
        ax2.grid(alpha=0.3, axis='y')

        plt.tight_layout()
        plt.show()

    return {
        'test': 'Levene',
        'statistic': statistic,
        'p_value': p_value,
        'is_homogeneous': is_homogeneous,
        'variance_ratio': var_ratio,
        'interpretation': interpretation,
        'recommendation': (
            "继续进行标准检验" if is_homogeneous
            else "考虑 Welch 校正或数据变换"
        )
    }


def check_linearity(
    x: Union[np.ndarray, pd.Series],
    y: Union[np.ndarray, pd.Series],
    x_name: str = "X",
    y_name: str = "Y"
) -> Dict:
    """
    检验回归的线性假设。

    参数
    ----------
    x : 类数组
        预测变量
    y : 类数组
        结果变量
    x_name : str
        预测变量名称
    y_name : str
        结果变量名称

    返回
    -------
    dict
        可视化和建议
    """
    x = np.asarray(x)
    y = np.asarray(y)

    # 拟合线性回归
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    y_pred = intercept + slope * x

    # 计算残差
    residuals = y - y_pred

    # 可视化
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

    # 带回归线的散点图
    ax1.scatter(x, y, alpha=0.6, s=50, edgecolors='black', linewidths=0.5)
    ax1.plot(x, y_pred, 'r-', linewidth=2, label=f'y = {intercept:.2f} + {slope:.2f}x')
    ax1.set_xlabel(x_name)
    ax1.set_ylabel(y_name)
    ax1.set_title('带回归线的散点图')
    ax1.legend()
    ax1.grid(alpha=0.3)

    # 残差与拟合值图
    ax2.scatter(y_pred, residuals, alpha=0.6, s=50, edgecolors='black', linewidths=0.5)
    ax2.axhline(y=0, color='r', linestyle='--', linewidth=2)
    ax2.set_xlabel('拟合值')
    ax2.set_ylabel('残差')
    ax2.set_title('残差与拟合值图')
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.show()

    return {
        'r': r_value,
        'r_squared': r_value ** 2,
        'interpretation': (
            "检查残差图。点应随机散布在零周围。"
            "模式（曲线、漏斗）表明非线性或异方差性。"
        ),
        'recommendation': (
            "如果检测到非线性模式：考虑多项式项、"
            "变换或非线性模型"
        )
    }


def detect_outliers(
    data: Union[np.ndarray, pd.Series, List],
    name: str = "data",
    method: str = "iqr",
    threshold: float = 1.5,
    plot: bool = True
) -> Dict:
    """
    使用 IQR 方法或 z-score 方法检测异常值。

    参数
    ----------
    data : 类数组
        待检验异常值的数据
    name : str
        变量名称
    method : str
        使用方法：'iqr' 或 'zscore'
    threshold : float
        异常值检测阈值
        对于 IQR：通常为 1.5（温和）或 3（极端）
        对于 z-score：通常为 3
    plot : bool
        是否创建可视化

    返回
    -------
    dict
        异常值索引、值和可视化
    """
    data = np.asarray(data)
    data_clean = data[~np.isnan(data)]

    if method == "iqr":
        q1 = np.percentile(data_clean, 25)
        q3 = np.percentile(data_clean, 75)
        iqr = q3 - q1
        lower_bound = q1 - threshold * iqr
        upper_bound = q3 + threshold * iqr
        outlier_mask = (data_clean < lower_bound) | (data_clean > upper_bound)

    elif method == "zscore":
        z_scores = np.abs(stats.zscore(data_clean))
        outlier_mask = z_scores > threshold
        lower_bound = data_clean.mean() - threshold * data_clean.std()
        upper_bound = data_clean.mean() + threshold * data_clean.std()

    else:
        raise ValueError("method 必须是 'iqr' 或 'zscore'")

    outlier_indices = np.where(outlier_mask)[0]
    outlier_values = data_clean[outlier_mask]
    n_outliers = len(outlier_indices)
    pct_outliers = (n_outliers / len(data_clean)) * 100

    if plot:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

        # 箱线图
        bp = ax1.boxplot(data_clean, vert=True, patch_artist=True)
        bp['boxes'][0].set_facecolor('steelblue')
        ax1.set_ylabel('值')
        ax1.set_title(f'箱线图: {name}')
        ax1.grid(alpha=0.3, axis='y')

        # 突出异常值的散点图
        x_coords = np.arange(len(data_clean))
        ax2.scatter(x_coords[~outlier_mask], data_clean[~outlier_mask],
                   alpha=0.6, s=50, color='steelblue', label='正常', edgecolors='black', linewidths=0.5)
        if n_outliers > 0:
            ax2.scatter(x_coords[outlier_mask], data_clean[outlier_mask],
                       alpha=0.8, s=100, color='red', label='异常值', marker='D', edgecolors='black', linewidths=0.5)
        ax2.axhline(y=lower_bound, color='orange', linestyle='--', linewidth=1.5, label='界限')
        ax2.axhline(y=upper_bound, color='orange', linestyle='--', linewidth=1.5)
        ax2.set_xlabel('索引')
        ax2.set_ylabel('值')
        ax2.set_title(f'异常值检测: {name}')
        ax2.legend()
        ax2.grid(alpha=0.3)

        plt.tight_layout()
        plt.show()

    return {
        'method': method,
        'threshold': threshold,
        'n_outliers': n_outliers,
        'pct_outliers': pct_outliers,
        'outlier_indices': outlier_indices,
        'outlier_values': outlier_values,
        'lower_bound': lower_bound,
        'upper_bound': upper_bound,
        'interpretation': f"发现 {n_outliers} 个异常值（占数据的 {pct_outliers:.1f}%）",
        'recommendation': (
            "调查异常值是否为数据录入错误。"
            "考虑：（1）如果是错误则删除，（2）缩尾处理，"
            "（3）如果合法则保留，（4）使用稳健方法"
        )
    }


def comprehensive_assumption_check(
    data: pd.DataFrame,
    value_col: str,
    group_col: Optional[str] = None,
    alpha: float = 0.05
) -> Dict:
    """
    对常见统计检验进行综合假设检验。

    参数
    ----------
    data : pd.DataFrame
        待检验的数据
    value_col : str
        因变量的列名
    group_col : str, 可选
        分组变量的列名（如适用）
    alpha : float
        显著性水平

    返回
    -------
    dict
        所有假设检验的摘要
    """
    print("=" * 70)
    print("综合假设检验")
    print("=" * 70)

    results = {}

    # 异常值检测
    print("\n1. 异常值检测")
    print("-" * 70)
    outlier_results = detect_outliers(
        data[value_col].dropna(),
        name=value_col,
        method='iqr',
        plot=True
    )
    results['outliers'] = outlier_results
    print(f"   {outlier_results['interpretation']}")
    print(f"   {outlier_results['recommendation']}")

    # 检查是否为分组数据
    if group_col is not None:
        # 各组的正态性
        print(f"\n2. 正态性检验（按 {group_col}）")
        print("-" * 70)
        normality_results = check_normality_per_group(
            data, value_col, group_col, alpha=alpha, plot=True
        )
        results['normality_per_group'] = normality_results
        print(normality_results.to_string(index=False))

        all_normal = normality_results['正态'].eq('是').all()
        print(f"\n   所有组均正态: {'是' if all_normal else '否'}")
        if not all_normal:
            print("   → 考虑非参数替代方法（Mann-Whitney、Kruskal-Wallis）")

        # 方差齐性
        print(f"\n3. 方差齐性")
        print("-" * 70)
        homogeneity_results = check_homogeneity_of_variance(
            data, value_col, group_col, alpha=alpha, plot=True
        )
        results['homogeneity'] = homogeneity_results
        print(f"   {homogeneity_results['interpretation']}")
        print(f"   {homogeneity_results['recommendation']}")

    else:
        # 整体正态性
        print(f"\n2. 正态性检验")
        print("-" * 70)
        normality_results = check_normality(
            data[value_col].dropna(),
            name=value_col,
            alpha=alpha,
            plot=True
        )
        results['normality'] = normality_results
        print(f"   {normality_results['interpretation']}")
        print(f"   {normality_results['recommendation']}")

    # 摘要
    print("\n" + "=" * 70)
    print("摘要")
    print("=" * 70)

    if group_col is not None:
        all_normal = results.get('normality_per_group', pd.DataFrame()).get('正态', pd.Series()).eq('是').all()
        is_homogeneous = results.get('homogeneity', {}).get('is_homogeneous', False)

        if all_normal and is_homogeneous:
            print("✓ 所有假设均满足。继续进行参数检验（t 检验、方差分析）。")
        elif not all_normal:
            print("✗ 正态性假设违反。使用非参数替代方法。")
        elif not is_homogeneous:
            print("✗ 方差齐性假设违反。使用 Welch 校正或数据变换。")
    else:
        is_normal = results.get('normality', {}).get('is_normal', False)
        if is_normal:
            print("✓ 正态性假设满足。")
        else:
            print("✗ 正态性假设违反。考虑变换或非参数方法。")

    print("=" * 70)

    return results


if __name__ == "__main__":
    # 示例用法
    np.random.seed(42)

    # 模拟数据
    group_a = np.random.normal(75, 8, 50)
    group_b = np.random.normal(68, 10, 50)

    df = pd.DataFrame({
        'score': np.concatenate([group_a, group_b]),
        'group': ['A'] * 50 + ['B'] * 50
    })

    # 运行综合检验
    results = comprehensive_assumption_check(
        df,
        value_col='score',
        group_col='group',
        alpha=0.05
    )
