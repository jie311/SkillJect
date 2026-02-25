"""
BRENDA 数据库可视化工具

此模块提供 BRENDA 酶数据的可视化函数，
包括动力学参数、环境条件和通路分析。

主要功能：
- 绘制 Km、kcat 和 Vmax 分布图
- 比较不同生物体的酶属性
- 可视化 pH 和温度活性曲线
- 绘制底物特异性和亲和力数据
- 生成 Michaelis-Menten 曲线
- 创建热图和相关图
- 支持通路可视化

安装：
    uv pip install matplotlib seaborn pandas numpy

用法：
    from scripts.brenda_visualization import plot_kinetic_parameters, plot_michaelis_menten

    plot_kinetic_parameters("1.1.1.1")
    plot_michaelis_menten("1.1.1.1", substrate="ethanol")
"""

import math
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    print("警告: 未安装 pandas。使用以下命令安装: uv pip install pandas")
    PANDAS_AVAILABLE = False

try:
    from brenda_queries import (
        get_km_values, get_reactions, parse_km_entry, parse_reaction_entry,
        compare_across_organisms, get_environmental_parameters,
        get_substrate_specificity, get_modeling_parameters,
        search_enzymes_by_substrate, search_by_pattern
    )
    BRENDA_QUERIES_AVAILABLE = True
except ImportError:
    print("警告: brenda_queries 不可用")
    BRENDA_QUERIES_AVAILABLE = False


# 设置绘图样式
plt.style.use('default')
sns.set_palette("husl")


def validate_dependencies():
    """验证已安装必需的依赖项。"""
    missing = []
    if not PANDAS_AVAILABLE:
        missing.append("pandas")
    if not BRENDA_QUERIES_AVAILABLE:
        missing.append("brenda_queries")
    if missing:
        raise ImportError(f"缺少必需的依赖项: {', '.join(missing)}")


def plot_kinetic_parameters(ec_number: str, save_path: str = None, show_plot: bool = True) -> str:
    """绘制酶的动力学参数分布图。"""
    validate_dependencies()

    try:
        # 获取 Km 数据
        km_data = get_km_values(ec_number)

        if not km_data:
            print(f"未找到 EC {ec_number} 的动力学数据")
            return save_path

        # 解析数据
        parsed_entries = []
        for entry in km_data:
            parsed = parse_km_entry(entry)
            if 'km_value_numeric' in parsed:
                parsed_entries.append(parsed)

        if not parsed_entries:
            print(f"未找到 EC {ec_number} 的数值 Km 数据")
            return save_path

        # 创建带有子图的图形
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle(f'EC {ec_number} 的动力学参数', fontsize=16, fontweight='bold')

        # 提取数据
        km_values = [entry['km_value_numeric'] for entry in parsed_entries]
        organisms = [entry.get('organism', 'Unknown') for entry in parsed_entries]
        substrates = [entry.get('substrate', 'Unknown') for entry in parsed_entries]

        # 图 1：Km 分布直方图
        ax1.hist(km_values, bins=30, alpha=0.7, edgecolor='black')
        ax1.set_xlabel('Km (mM)')
        ax1.set_ylabel('频数')
        ax1.set_title('Km 值分布')
        ax1.axvline(np.mean(km_values), color='red', linestyle='--', label=f'均值: {np.mean(km_values):.2f}')
        ax1.axvline(np.median(km_values), color='blue', linestyle='--', label=f'中位数: {np.median(km_values):.2f}')
        ax1.legend()

        # 图 2：按生物体的 Km（前 10）
        if PANDAS_AVAILABLE:
            df = pd.DataFrame({'Km': km_values, 'Organism': organisms})
            organism_means = df.groupby('Organism')['Km'].mean().sort_values(ascending=False).head(10)

            organism_means.plot(kind='bar', ax=ax2)
            ax2.set_ylabel('平均 Km (mM)')
            ax2.set_title('按生物体的平均 Km（前 10）')
            ax2.tick_params(axis='x', rotation=45)

        # 图 3：按底物的 Km（前 10）
        if PANDAS_AVAILABLE:
            df = pd.DataFrame({'Km': km_values, 'Substrate': substrates})
            substrate_means = df.groupby('Substrate')['Km'].mean().sort_values(ascending=False).head(10)

            substrate_means.plot(kind='bar', ax=ax3)
            ax3.set_ylabel('平均 Km (mM)')
            ax3.set_title('按底物的平均 Km（前 10）')
            ax3.tick_params(axis='x', rotation=45)

        # 图 4：按生物体的箱线图（前 5）
        if PANDAS_AVAILABLE:
            top_organisms = df.groupby('Organism')['Km'].count().sort_values(ascending=False).head(5).index
            top_data = df[df['Organism'].isin(top_organisms)]

            sns.boxplot(data=top_data, x='Organism', y='Km', ax=ax4)
            ax4.set_ylabel('Km (mM)')
            ax4.set_title('按生物体的 Km 分布（前 5）')
            ax4.tick_params(axis='x', rotation=45)

        plt.tight_layout()

        # 保存图形
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"动力学参数图已保存至 {save_path}")

        if show_plot:
            plt.show()
        else:
            plt.close()

        return save_path or f"kinetic_parameters_{ec_number.replace('.', '_')}.png"

    except Exception as e:
        print(f"绘制动力学参数图时出错: {e}")
        return save_path


def plot_organism_comparison(ec_number: str, organisms: List[str], save_path: str = None, show_plot: bool = True) -> str:
    """比较多个生物体的酶属性。"""
    validate_dependencies()

    try:
        # 获取比较数据
        comparison = compare_across_organisms(ec_number, organisms)

        if not comparison:
            print(f"未找到 EC {ec_number} 的比较数据")
            return save_path

        # 过滤掉没有数据的条目
        valid_data = [c for c in comparison if c.get('data_points', 0) > 0]

        if not valid_data:
            print(f"未找到 EC {ec_number} 的生物体比较有效数据")
            return save_path

        # 创建图形
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle(f'EC {ec_number} 的生物体比较', fontsize=16, fontweight='bold')

        # 提取数据
        names = [c['organism'] for c in valid_data]
        avg_kms = [c.get('average_km', 0) for c in valid_data if c.get('average_km')]
        optimal_phs = [c.get('optimal_ph', 0) for c in valid_data if c.get('optimal_ph')]
        optimal_temps = [c.get('optimal_temperature', 0) for c in valid_data if c.get('optimal_temperature')]
        data_points = [c.get('data_points', 0) for c in valid_data]

        # 图 1：平均 Km 比较
        if avg_kms:
            ax1.bar(names, avg_kms)
            ax1.set_ylabel('平均 Km (mM)')
            ax1.set_title('平均 Km 比较')
            ax1.tick_params(axis='x', rotation=45)

        # 图 2：最佳 pH 比较
        if optimal_phs:
            ax2.bar(names, optimal_phs)
            ax2.set_ylabel('最佳 pH')
            ax2.set_title('最佳 pH 比较')
            ax2.tick_params(axis='x', rotation=45)

        # 图 3：最佳温度比较
        if optimal_temps:
            ax3.bar(names, optimal_temps)
            ax3.set_ylabel('最佳温度 (°C)')
            ax3.set_title('最佳温度比较')
            ax3.tick_params(axis='x', rotation=45)

        # 图 4：数据点比较
        ax4.bar(names, data_points)
        ax4.set_ylabel('数据点数量')
        ax4.set_title('可用数据点')
        ax4.tick_params(axis='x', rotation=45)

        plt.tight_layout()

        # 保存图形
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"生物体比较图已保存至 {save_path}")

        if show_plot:
            plt.show()
        else:
            plt.close()

        return save_path or f"organism_comparison_{ec_number.replace('.', '_')}.png"

    except Exception as e:
        print(f"绘制生物体比较图时出错: {e}")
        return save_path


def plot_pH_profiles(ec_number: str, save_path: str = None, show_plot: bool = True) -> str:
    """绘制酶的 pH 活性曲线。"""
    validate_dependencies()

    try:
        # 获取动力学数据
        km_data = get_km_values(ec_number)

        if not km_data:
            print(f"未找到 EC {ec_number} 的 pH 数据")
            return save_path

        # 解析数据并提取 pH 信息
        ph_kms = []
        ph_organisms = []

        for entry in km_data:
            parsed = parse_km_entry(entry)
            if 'ph' in parsed and 'km_value_numeric' in parsed:
                ph_kms.append((parsed['ph'], parsed['km_value_numeric']))
                ph_organisms.append(parsed.get('organism', 'Unknown'))

        if not ph_kms:
            print(f"未找到 EC {ec_number} 的 pH-Km 数据")
            return save_path

        # 创建图形
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        fig.suptitle(f'EC {ec_number} 的 pH 活性曲线', fontsize=16, fontweight='bold')

        # 提取数据
        ph_values = [item[0] for item in ph_kms]
        km_values = [item[1] for item in ph_kms]

        # 图 1：pH 与 Km 的散点图
        scatter = ax1.scatter(ph_values, km_values, alpha=0.6, s=50)
        ax1.set_xlabel('pH')
        ax1.set_ylabel('Km (mM)')
        ax1.set_title('pH 与 Km 值')
        ax1.grid(True, alpha=0.3)

        # 添加趋势线
        if len(ph_values) > 2:
            z = np.polyfit(ph_values, km_values, 1)
            p = np.poly1d(z)
            ax1.plot(ph_values, p(ph_values), "r--", alpha=0.8, label=f'趋势: y={z[0]:.3f}x+{z[1]:.3f}')
            ax1.legend()

        # 图 2：pH 分布直方图
        ax2.hist(ph_values, bins=20, alpha=0.7, edgecolor='black')
        ax2.set_xlabel('pH')
        ax2.set_ylabel('频数')
        ax2.set_title('pH 分布')
        ax2.axvline(np.mean(ph_values), color='red', linestyle='--', label=f'均值: {np.mean(ph_values):.2f}')
        ax2.axvline(np.median(ph_values), color='blue', linestyle='--', label=f'中位数: {np.median(ph_values):.2f}')
        ax2.legend()

        plt.tight_layout()

        # 保存图形
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"pH 曲线图已保存至 {save_path}")

        if show_plot:
            plt.show()
        else:
            plt.close()

        return save_path or f"ph_profile_{ec_number.replace('.', '_')}.png"

    except Exception as e:
        print(f"绘制 pH 曲线图时出错: {e}")
        return save_path


def plot_temperature_profiles(ec_number: str, save_path: str = None, show_plot: bool = True) -> str:
    """绘制酶的温度活性曲线。"""
    validate_dependencies()

    try:
        # 获取动力学数据
        km_data = get_km_values(ec_number)

        if not km_data:
            print(f"未找到 EC {ec_number} 的温度数据")
            return save_path

        # 解析数据并提取温度信息
        temp_kms = []
        temp_organisms = []

        for entry in km_data:
            parsed = parse_km_entry(entry)
            if 'temperature' in parsed and 'km_value_numeric' in parsed:
                temp_kms.append((parsed['temperature'], parsed['km_value_numeric']))
                temp_organisms.append(parsed.get('organism', 'Unknown'))

        if not temp_kms:
            print(f"未找到 EC {ec_number} 的温度-Km 数据")
            return save_path

        # 创建图形
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        fig.suptitle(f'EC {ec_number} 的温度活性曲线', fontsize=16, fontweight='bold')

        # 提取数据
        temp_values = [item[0] for item in temp_kms]
        km_values = [item[1] for item in temp_kms]

        # 图 1：温度与 Km 的散点图
        scatter = ax1.scatter(temp_values, km_values, alpha=0.6, s=50)
        ax1.set_xlabel('温度 (°C)')
        ax1.set_ylabel('Km (mM)')
        ax1.set_title('温度与 Km 值')
        ax1.grid(True, alpha=0.3)

        # 添加趋势线
        if len(temp_values) > 2:
            z = np.polyfit(temp_values, km_values, 2)  # 温度最优值的二次拟合
            p = np.poly1d(z)
            x_smooth = np.linspace(min(temp_values), max(temp_values), 100)
            ax1.plot(x_smooth, p(x_smooth), "r--", alpha=0.8, label='多项式拟合')

            # 查找最佳温度
            optimum_idx = np.argmin(p(x_smooth))
            optimum_temp = x_smooth[optimum_idx]
            ax1.axvline(optimum_temp, color='green', linestyle=':', label=f'最佳: {optimum_temp:.1f}°C')
            ax1.legend()

        # 图 2：温度分布直方图
        ax2.hist(temp_values, bins=20, alpha=0.7, edgecolor='black')
        ax2.set_xlabel('温度 (°C)')
        ax2.set_ylabel('频数')
        ax2.set_title('温度分布')
        ax2.axvline(np.mean(temp_values), color='red', linestyle='--', label=f'均值: {np.mean(temp_values):.1f}°C')
        ax2.axvline(np.median(temp_values), color='blue', linestyle='--', label=f'中位数: {np.median(temp_values):.1f}°C')
        ax2.legend()

        plt.tight_layout()

        # 保存图形
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"温度曲线图已保存至 {save_path}")

        if show_plot:
            plt.show()
        else:
            plt.close()

        return save_path or f"temperature_profile_{ec_number.replace('.', '_')}.png"

    except Exception as e:
        print(f"绘制温度曲线图时出错: {e}")
        return save_path


def plot_substrate_specificity(ec_number: str, save_path: str = None, show_plot: bool = True) -> str:
    """绘制酶的底物特异性和亲和力图。"""
    validate_dependencies()

    try:
        # 获取底物特异性数据
        specificity = get_substrate_specificity(ec_number)

        if not specificity:
            print(f"未找到 EC {ec_number} 的底物特异性数据")
            return save_path

        # 创建图形
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle(f'EC {ec_number} 的底物特异性', fontsize=16, fontweight='bold')

        # 提取数据
        substrates = [s['name'] for s in specificity]
        kms = [s['km'] for s in specificity if s.get('km')]
        data_points = [s['data_points'] for s in specificity]

        # 获取用于绘图的顶级底物
        if PANDAS_AVAILABLE and kms:
            df = pd.DataFrame({'Substrate': substrates, 'Km': kms, 'DataPoints': data_points})
            top_substrates = df.nlargest(15, 'DataPoints')  # 按数据点前 15

            # 图 1：顶级底物的 Km 值（按亲和度排序）
            top_sorted = top_substrates.sort_values('Km')
            ax1.barh(range(len(top_sorted)), top_sorted['Km'])
            ax1.set_yticks(range(len(top_sorted)))
            ax1.set_yticklabels([s[:30] + '...' if len(s) > 30 else s for s in top_sorted['Substrate']])
            ax1.set_xlabel('Km (mM)')
            ax1.set_title('底物亲和力（Km 越低 = 亲和力越高）')
            ax1.invert_yaxis()  # 最佳亲和力在顶部

            # 图 2：按底物的数据点
            ax2.barh(range(len(top_sorted)), top_sorted['DataPoints'])
            ax2.set_yticks(range(len(top_sorted)))
            ax2.set_yticklabels([s[:30] + '...' if len(s) > 30 else s for s in top_sorted['Substrate']])
            ax2.set_xlabel('数据点数量')
            ax2.set_title('按底物的数据可用性')
            ax2.invert_yaxis()

            # 图 3：Km 分布
            ax3.hist(kms, bins=20, alpha=0.7, edgecolor='black')
            ax3.set_xlabel('Km (mM)')
            ax3.set_ylabel('频数')
            ax3.set_title('Km 值分布')
            ax3.axvline(np.mean(kms), color='red', linestyle='--', label=f'均值: {np.mean(kms):.2f}')
            ax3.axvline(np.median(kms), color='blue', linestyle='--', label=f'中位数: {np.median(kms):.2f}')
            ax3.legend()

            # 图 4：Km 与数据点的散点图
            ax4.scatter(df['DataPoints'], df['Km'], alpha=0.6)
            ax4.set_xlabel('数据点数量')
            ax4.set_ylabel('Km (mM)')
            ax4.set_title('Km 与数据点')
            ax4.grid(True, alpha=0.3)

        plt.tight_layout()

        # 保存图形
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"底物特异性图已保存至 {save_path}")

        if show_plot:
            plt.show()
        else:
            plt.close()

        return save_path or f"substrate_specificity_{ec_number.replace('.', '_')}.png"

    except Exception as e:
        print(f"绘制底物特异性图时出错: {e}")
        return save_path


def plot_michaelis_menten(ec_number: str, substrate: str = None, save_path: str = None, show_plot: bool = True) -> str:
    """生成酶的 Michaelis-Menten 曲线。"""
    validate_dependencies()

    try:
        # 获取建模参数
        model_data = get_modeling_parameters(ec_number, substrate)

        if not model_data or model_data.get('error'):
            print(f"未找到 EC {ec_number} 的建模数据")
            return save_path

        km = model_data.get('km')
        vmax = model_data.get('vmax')
        kcat = model_data.get('kcat')
        enzyme_conc = model_data.get('enzyme_conc', 1.0)

        if not km:
            print(f"没有可用于绘图的 Km 数据")
            return save_path

        # 创建图形
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        fig.suptitle(f'EC {ec_number} 的 Michaelis-Menten 动力学' + (f' - {substrate}' if substrate else ''),
                     fontsize=16, fontweight='bold')

        # 生成底物浓度范围
        substrate_range = np.linspace(0, km * 5, 1000)

        # 计算反应速率
        if vmax:
            # 如果有 Vmax 则使用实际值
            rates = (vmax * substrate_range) / (km + substrate_range)
        elif kcat and enzyme_conc:
            # 从 kcat 和酶浓度计算 Vmax
            vmax_calc = kcat * enzyme_conc
            rates = (vmax_calc * substrate_range) / (km + substrate_range)
        else:
            # 使用归一化 Vmax = 1.0
            rates = substrate_range / (km + substrate_range)

        # 图 1：Michaelis-Menten 曲线
        ax1.plot(substrate_range, rates, 'b-', linewidth=2, label='Michaelis-Menten')
        ax1.axhline(y=rates[-1] * 0.5, color='r', linestyle='--', alpha=0.7, label='0.5 × Vmax')
        ax1.axvline(x=km, color='g', linestyle='--', alpha=0.7, label=f'Km = {km:.2f}')
        ax1.set_xlabel('底物浓度 (mM)')
        ax1.set_ylabel('反应速率')
        ax1.set_title('Michaelis-Menten 曲线')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # 添加 Km 注释
        km_rate = (substrate_range[km == min(substrate_range, key=lambda x: abs(x-km))] *
                  (vmax if vmax else kcat * enzyme_conc if kcat else 1.0)) / (km +
                  substrate_range[km == min(substrate_range, key=lambda x: abs(x-km))])
        ax1.plot(km, km_rate, 'ro', markersize=8)

        # 图 2：Lineweaver-Burk 图（双倒数）
        substrate_range_nonzero = substrate_range[substrate_range > 0]
        rates_nonzero = rates[substrate_range > 0]

        reciprocal_substrate = 1 / substrate_range_nonzero
        reciprocal_rate = 1 / rates_nonzero

        ax2.scatter(reciprocal_substrate, reciprocal_rate, alpha=0.6, s=10)

        # 拟合线性回归
        z = np.polyfit(reciprocal_substrate, reciprocal_rate, 1)
        p = np.poly1d(z)
        x_fit = np.linspace(min(reciprocal_substrate), max(reciprocal_substrate), 100)
        ax2.plot(x_fit, p(x_fit), 'r-', linewidth=2, label=f'1/Vmax = {z[1]:.3f}')

        ax2.set_xlabel('1/[底物] (1/mM)')
        ax2.set_ylabel('1/速率')
        ax2.set_title('Lineweaver-Burk 图')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # 添加参数信息
        info_text = f"Km = {km:.3f} mM"
        if vmax:
            info_text += f"\nVmax = {vmax:.3f}"
        if kcat:
            info_text += f"\nkcat = {kcat:.3f} s⁻¹"
        if enzyme_conc:
            info_text += f"\n[酶] = {enzyme_conc:.3f} μM"

        fig.text(0.02, 0.98, info_text, transform=fig.transFigure,
                fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

        plt.tight_layout()

        # 保存图形
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Michaelis-Menten 图已保存至 {save_path}")

        if show_plot:
            plt.show()
        else:
            plt.close()

        return save_path or f"michaelis_menten_{ec_number.replace('.', '_')}_{substrate or 'all'}.png"

    except Exception as e:
        print(f"绘制 Michaelis-Menten 图时出错: {e}")
        return save_path


def create_heatmap_data(ec_number: str, parameters: List[str] = None) -> Dict[str, Any]:
    """创建用于热图可视化的数据。"""
    validate_dependencies()

    try:
        # 获取跨生物体的比较数据
        organisms = ["大肠杆菌", "酿酒酵母", "枯草芽孢杆菌",
                    "智人", "小家鼠", "褐家鼠"]
        comparison = compare_across_organisms(ec_number, organisms)

        if not comparison:
            return None

        # 创建热图数据
        heatmap_data = {
            'organisms': [],
            'average_km': [],
            'optimal_ph': [],
            'optimal_temperature': [],
            'data_points': []
        }

        for comp in comparison:
            if comp.get('data_points', 0) > 0:
                heatmap_data['organisms'].append(comp['organism'])
                heatmap_data['average_km'].append(comp.get('average_km', 0))
                heatmap_data['optimal_ph'].append(comp.get('optimal_ph', 0))
                heatmap_data['optimal_temperature'].append(comp.get('optimal_temperature', 0))
                heatmap_data['data_points'].append(comp.get('data_points', 0))

        return heatmap_data

    except Exception as e:
        print(f"创建热图数据时出错: {e}")
        return None


def plot_heatmap(ec_number: str, save_path: str = None, show_plot: bool = True) -> str:
    """创建酶属性的热图可视化。"""
    validate_dependencies()

    try:
        heatmap_data = create_heatmap_data(ec_number)

        if not heatmap_data or not heatmap_data['organisms']:
            print(f"未找到 EC {ec_number} 的热图数据")
            return save_path

        if not PANDAS_AVAILABLE:
            print("热图绘图需要 pandas")
            return save_path

        # 创建热图 DataFrame
        df = pd.DataFrame({
            'Organism': heatmap_data['organisms'],
            'Avg Km (mM)': heatmap_data['average_km'],
            'Optimal pH': heatmap_data['optimal_ph'],
            'Optimal Temp (°C)': heatmap_data['optimal_temperature'],
            'Data Points': heatmap_data['data_points']
        })

        # 归一化数据以便更好地可视化
        df_normalized = df.copy()
        for col in ['Avg Km (mM)', 'Optimal pH', 'Optimal Temp (°C)', 'Data Points']:
            if col in df.columns:
                df_normalized[col] = (df[col] - df[col].min()) / (df[col].max() - df[col].min())

        # 创建图形
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
        fig.suptitle(f'EC {ec_number} 的酶属性热图', fontsize=16, fontweight='bold')

        # 图 1：原始数据热图
        heatmap_data_raw = df.set_index('Organism')[['Avg Km (mM)', 'Optimal pH', 'Optimal Temp (°C)', 'Data Points']].T
        sns.heatmap(heatmap_data_raw, annot=True, fmt='.2f', cmap='viridis', ax=ax1)
        ax1.set_title('原始值')

        # 图 2：归一化数据热图
        heatmap_data_norm = df_normalized.set_index('Organism')[['Avg Km (mM)', 'Optimal pH', 'Optimal Temp (°C)', 'Data Points']].T
        sns.heatmap(heatmap_data_norm, annot=True, fmt='.2f', cmap='viridis', ax=ax2)
        ax2.set_title('归一化值 (0-1)')

        plt.tight_layout()

        # 保存图形
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"热图已保存至 {save_path}")

        if show_plot:
            plt.show()
        else:
            plt.close()

        return save_path or f"heatmap_{ec_number.replace('.', '_')}.png"

    except Exception as e:
        print(f"绘制热图时出错: {e}")
        return save_path


def generate_summary_plots(ec_number: str, save_dir: str = None) -> List[str]:
    """为酶生成一组综合图形。"""
    validate_dependencies()

    if save_dir is None:
        save_dir = f"enzyme_plots_{ec_number.replace('.', '_')}"

    # 创建保存目录
    Path(save_dir).mkdir(exist_ok=True)

    generated_files = []

    # 生成所有图形类型
    plot_functions = [
        ('kinetic_parameters', plot_kinetic_parameters),
        ('ph_profiles', plot_pH_profiles),
        ('temperature_profiles', plot_temperature_profiles),
        ('substrate_specificity', plot_substrate_specificity),
        ('heatmap', plot_heatmap),
    ]

    for plot_name, plot_func in plot_functions:
        try:
            save_path = f"{save_dir}/{plot_name}_{ec_number.replace('.', '_')}.png"
            result_path = plot_func(ec_number, save_path=save_path, show_plot=False)
            if result_path:
                generated_files.append(result_path)
                print(f"已生成 {plot_name} 图")
            else:
                print(f"未能生成 {plot_name} 图")
        except Exception as e:
            print(f"生成 {plot_name} 图时出错: {e}")

    # 为常见模式生物生成生物体比较图
    model_organisms = ["大肠杆菌", "酿酒酵母", "智人"]
    try:
        save_path = f"{save_dir}/organism_comparison_{ec_number.replace('.', '_')}.png"
        result_path = plot_organism_comparison(ec_number, model_organisms, save_path=save_path, show_plot=False)
        if result_path:
            generated_files.append(result_path)
            print("已生成生物体比较图")
    except Exception as e:
        print(f"生成生物体比较图时出错: {e}")

    # 为最常见的底物生成 Michaelis-Menten 图
    try:
        specificity = get_substrate_specificity(ec_number)
        if specificity:
            most_common = max(specificity, key=lambda x: x.get('data_points', 0))
            substrate_name = most_common['name'].split()[0]  # 取第一个词
            save_path = f"{save_dir}/michaelis_menten_{ec_number.replace('.', '_')}_{substrate_name}.png"
            result_path = plot_michaelis_menten(ec_number, substrate_name, save_path=save_path, show_plot=False)
            if result_path:
                generated_files.append(result_path)
                print(f"已为 {substrate_name} 生成 Michaelis-Menten 图")
    except Exception as e:
        print(f"生成 Michaelis-Menten 图时出错: {e}")

    print(f"\n已在目录中生成 {len(generated_files)} 个图形: {save_dir}")
    return generated_files


if __name__ == "__main__":
    # 示例用法
    print("BRENDA 可视化示例")
    print("=" * 40)

    try:
        ec_number = "1.1.1.1"  # 乙醇脱氢酶

        print(f"\n1. 为 EC {ec_number} 生成动力学参数图")
        plot_kinetic_parameters(ec_number, show_plot=False)

        print(f"\n2. 为 EC {ec_number} 生成 pH 曲线图")
        plot_pH_profiles(ec_number, show_plot=False)

        print(f"\n3. 为 EC {ec_number} 生成底物特异性图")
        plot_substrate_specificity(ec_number, show_plot=False)

        print(f"\n4. 为 EC {ec_number} 生成 Michaelis-Menten 图")
        plot_michaelis_menten(ec_number, substrate="ethanol", show_plot=False)

        print(f"\n5. 为 EC {ec_number} 生成生物体比较图")
        organisms = ["大肠杆菌", "酿酒酵母", "智人"]
        plot_organism_comparison(ec_number, organisms, show_plot=False)

        print(f"\n6. 为 EC {ec_number} 生成综合摘要图")
        summary_files = generate_summary_plots(ec_number, show_plot=False)
        print(f"已生成 {len(summary_files)} 个摘要图")

    except Exception as e:
        print(f"示例失败: {e}")
